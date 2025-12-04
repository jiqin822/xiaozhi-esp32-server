import os
import io
import wave
import uuid
import json
import time
import queue
import asyncio
import traceback
import threading
import opuslib_next
import concurrent.futures
import gc
from abc import ABC, abstractmethod
from config.logger import setup_logging
from typing import Optional, Tuple, List
from core.handle.receiveAudioHandle import startToChat
from core.handle.reportHandle import enqueue_asr_report
from core.utils.util import remove_punctuation_and_length
from core.handle.receiveAudioHandle import handleAudioMessage

TAG = __name__
logger = setup_logging()


class ASRProviderBase(ABC):
    def __init__(self):
        pass

    # 打开音频通道
    async def open_audio_channels(self, conn):
        conn.asr_priority_thread = threading.Thread(
            target=self.asr_text_priority_thread, args=(conn,), daemon=True
        )
        conn.asr_priority_thread.start()

    # 有序处理ASR音频
    def asr_text_priority_thread(self, conn):
        while not conn.stop_event.is_set():
            try:
                message = conn.asr_audio_queue.get(timeout=1)
                future = asyncio.run_coroutine_threadsafe(
                    handleAudioMessage(conn, message),
                    conn.loop,
                )
                future.result()
            except queue.Empty:
                continue
            except Exception as e:
                logger.bind(tag=TAG).error(
                    f"处理ASR文本失败: {str(e)}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}"
                )
                continue

    # 接收音频
    async def receive_audio(self, conn, audio, audio_have_voice):
        if conn.client_listen_mode == "auto" or conn.client_listen_mode == "realtime":
            have_voice = audio_have_voice
        else:
            have_voice = conn.client_have_voice
        
        conn.asr_audio.append(audio)
        if not have_voice and not conn.client_have_voice:
            conn.asr_audio = conn.asr_audio[-10:]
            return

        if conn.client_voice_stop:
            asr_audio_task = conn.asr_audio.copy()
            audio_chunk_count = len(asr_audio_task)
            conn.asr_audio.clear()
            conn.reset_vad_states()

            # Lower threshold from 15 to 5 to process shorter speech segments
            # This helps capture speech even if VAD cuts off early
            if audio_chunk_count > 5:
                logger.bind(tag=TAG).debug(
                    f"Processing ASR: audio_chunks={audio_chunk_count}, "
                    f"estimated_duration={audio_chunk_count * 0.06:.2f}s (assuming 60ms per chunk)"
                )
                await self.handle_voice_stop(conn, asr_audio_task)
            else:
                logger.bind(tag=TAG).warning(
                    f"ASR audio too short: {audio_chunk_count} chunks (minimum 5 required). "
                    f"This may indicate VAD is cutting off speech too early."
                )

    # 处理语音停止
    async def handle_voice_stop(self, conn, asr_audio_task: List[bytes]):
        """并行处理ASR和声纹识别"""
        try:
            total_start_time = time.monotonic()
            
            # 获取ASR超时配置，默认30秒
            asr_timeout = int(conn.config.get("asr_timeout", 30))
            
            # 准备音频数据
            try:
                if conn.audio_format == "pcm":
                    pcm_data = asr_audio_task
                else:
                    pcm_data = self.decode_opus(asr_audio_task)
                
                if not pcm_data:
                    logger.bind(tag=TAG).warning("解码后的音频数据为空")
                    return
                
                combined_pcm_data = b"".join(pcm_data)
                
                if not combined_pcm_data:
                    logger.bind(tag=TAG).warning("合并后的音频数据为空")
                    return
            except Exception as e:
                logger.bind(tag=TAG).error(f"音频数据准备失败: {type(e).__name__}: {e}")
                raise
            
            # 预先准备WAV数据
            wav_data = None
            if conn.voiceprint_provider and combined_pcm_data:
                try:
                    wav_data = self._pcm_to_wav(combined_pcm_data)
                except Exception as e:
                    logger.bind(tag=TAG).warning(f"WAV数据准备失败(声纹识别可能不可用): {e}")
                    wav_data = None
            
            # 定义ASR任务
            def run_asr():
                start_time = time.monotonic()
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            self.speech_to_text(asr_audio_task, conn.session_id, conn.audio_format)
                        )
                        end_time = time.monotonic()
                        logger.bind(tag=TAG).debug(f"ASR耗时: {end_time - start_time:.3f}s")
                        return result
                    finally:
                        loop.close()
                except Exception as e:
                    end_time = time.monotonic()
                    logger.bind(tag=TAG).error(f"ASR失败: {e}")
                    return ("", None)
            
            # 定义声纹识别任务
            def run_voiceprint():
                if not wav_data:
                    return None
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # 使用连接的声纹识别提供者
                        result = loop.run_until_complete(
                            conn.voiceprint_provider.identify_speaker(wav_data, conn.session_id)
                        )
                        return result
                    finally:
                        loop.close()
                except Exception as e:
                    logger.bind(tag=TAG).error(f"声纹识别失败: {e}")
                    return None
            
            # 使用线程池执行器并行运行
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as thread_executor:
                asr_future = thread_executor.submit(run_asr)
                
                if conn.voiceprint_provider and wav_data:
                    voiceprint_future = thread_executor.submit(run_voiceprint)
                    
                    # 等待两个线程都完成
                    try:
                        asr_result = asr_future.result(timeout=asr_timeout)
                        voiceprint_result = voiceprint_future.result(timeout=asr_timeout)
                        results = {"asr": asr_result, "voiceprint": voiceprint_result}
                    except concurrent.futures.TimeoutError:
                        logger.bind(tag=TAG).error(f"ASR或声纹识别超时({asr_timeout}秒)")
                        # 如果超时，检查是否已完成，如果已完成则获取结果，否则返回空结果
                        if asr_future.done():
                            try:
                                asr_result = asr_future.result()  # No timeout since it's done
                            except Exception as e:
                                logger.bind(tag=TAG).warning(f"获取ASR结果失败: {e}")
                                asr_result = ("", None)
                        else:
                            asr_result = ("", None)
                            logger.bind(tag=TAG).warning("ASR任务未完成，返回空结果")
                        
                        if voiceprint_future.done():
                            try:
                                voiceprint_result = voiceprint_future.result()  # No timeout since it's done
                            except Exception as e:
                                logger.bind(tag=TAG).warning(f"获取声纹识别结果失败: {e}")
                                voiceprint_result = None
                        else:
                            voiceprint_result = None
                        
                        results = {"asr": asr_result, "voiceprint": voiceprint_result}
                else:
                    try:
                        asr_result = asr_future.result(timeout=asr_timeout)
                        results = {"asr": asr_result, "voiceprint": None}
                    except concurrent.futures.TimeoutError:
                        logger.bind(tag=TAG).error(f"ASR处理超时({asr_timeout}秒)")
                        # 如果超时，检查是否已完成，如果已完成则获取结果，否则返回空结果
                        if asr_future.done():
                            try:
                                asr_result = asr_future.result()  # No timeout since it's done
                            except Exception as e:
                                logger.bind(tag=TAG).warning(f"获取ASR结果失败: {e}")
                                asr_result = ("", None)
                        else:
                            asr_result = ("", None)
                            logger.bind(tag=TAG).warning("ASR任务未完成，返回空结果")
                        results = {"asr": asr_result, "voiceprint": None}
            
            
            # 处理结果
            raw_text, _ = results.get("asr", ("", None))
            speaker_name = results.get("voiceprint", None)
            
            # 记录原始ASR结果（用于调试）
            logger.bind(tag=TAG).debug(f"ASR原始结果类型: {type(raw_text)}, 值: {repr(raw_text[:100]) if raw_text else 'None'}")
            
            # 确保文本是有效的UTF-8字符串
            if raw_text:
                if isinstance(raw_text, bytes):
                    try:
                        raw_text = raw_text.decode('utf-8', errors='replace')
                        logger.bind(tag=TAG).debug(f"从bytes解码后的文本: {raw_text[:100]}")
                    except Exception as e:
                        logger.bind(tag=TAG).error(f"解码ASR文本失败: {e}")
                        raw_text = ""
                elif not isinstance(raw_text, str):
                    raw_text = str(raw_text)
                    logger.bind(tag=TAG).debug(f"转换为字符串后的文本: {raw_text[:100]}")
                
                # 清理可能的编码问题
                try:
                    raw_text = raw_text.encode('utf-8', errors='ignore').decode('utf-8', errors='replace')
                except Exception as e:
                    logger.bind(tag=TAG).error(f"清理编码失败: {e}")
                    raw_text = ""
            
            # 记录识别结果
            if raw_text:
                logger.bind(tag=TAG).info(f"识别文本: {raw_text}")
            if speaker_name:
                logger.bind(tag=TAG).info(f"识别说话人: {speaker_name}")
            
            # 性能监控
            total_time = time.monotonic() - total_start_time
            logger.bind(tag=TAG).debug(f"总处理耗时: {total_time:.3f}s")
            
            # 检查文本长度
            text_len, _ = remove_punctuation_and_length(raw_text)
            
            # 安全调用stop_ws_connection (某些ASR提供商可能没有此方法)
            try:
                if hasattr(self, 'stop_ws_connection'):
                    self.stop_ws_connection()
            except Exception as e:
                logger.bind(tag=TAG).debug(f"stop_ws_connection调用失败(可忽略): {e}")
            
            if text_len > 0:
                # 构建包含说话人信息的JSON字符串
                enhanced_text = self._build_enhanced_text(raw_text, speaker_name)
                
                # 使用自定义模块进行上报
                await startToChat(conn, enhanced_text)
                enqueue_asr_report(conn, enhanced_text, asr_audio_task)
                
        except Exception as e:
            error_msg = str(e) if e else "Unknown error"
            error_type = type(e).__name__
            logger.bind(tag=TAG).error(
                f"处理语音停止失败: {error_type}: {error_msg}"
            )
            logger.bind(tag=TAG).error(
                f"异常详情: {traceback.format_exc()}"
            )

    def _build_enhanced_text(self, text: str, speaker_name: Optional[str]) -> str:
        """构建包含说话人信息的文本"""
        if speaker_name and speaker_name.strip():
            return json.dumps({
                "speaker": speaker_name,
                "content": text
            }, ensure_ascii=False)
        else:
            return text

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """将PCM数据转换为WAV格式"""
        if len(pcm_data) == 0:
            logger.bind(tag=TAG).warning("PCM数据为空，无法转换WAV")
            return b""
        
        # 确保数据长度是偶数（16位音频）
        if len(pcm_data) % 2 != 0:
            pcm_data = pcm_data[:-1]
        
        # 创建WAV文件头
        wav_buffer = io.BytesIO()
        try:
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)      # 单声道
                wav_file.setsampwidth(2)      # 16位
                wav_file.setframerate(16000)  # 16kHz采样率
                wav_file.writeframes(pcm_data)
            
            wav_buffer.seek(0)
            wav_data = wav_buffer.read()
            
            return wav_data
        except Exception as e:
            logger.bind(tag=TAG).error(f"WAV转换失败: {e}")
            return b""

    def stop_ws_connection(self):
        pass

    def save_audio_to_file(self, pcm_data: List[bytes], session_id: str) -> str:
        """PCM数据保存为WAV文件"""
        module_name = __name__.split(".")[-1]
        file_name = f"asr_{module_name}_{session_id}_{uuid.uuid4()}.wav"
        file_path = os.path.join(self.output_dir, file_name)

        with wave.open(file_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 2 bytes = 16-bit
            wf.setframerate(16000)
            wf.writeframes(b"".join(pcm_data))

        return file_path

    @abstractmethod
    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """将语音数据转换为文本"""
        pass

    @staticmethod
    def decode_opus(opus_data: List[bytes]) -> List[bytes]:
        """将Opus音频数据解码为PCM数据"""
        decoder = None
        try:
            decoder = opuslib_next.Decoder(16000, 1)
            pcm_data = []
            buffer_size = 960  # 每次处理960个采样点 (60ms at 16kHz)
            
            for i, opus_packet in enumerate(opus_data):
                try:
                    if not opus_packet or len(opus_packet) == 0:
                        continue
                    
                    pcm_frame = decoder.decode(opus_packet, buffer_size)
                    if pcm_frame and len(pcm_frame) > 0:
                        pcm_data.append(pcm_frame)
                        
                except opuslib_next.OpusError as e:
                    logger.bind(tag=TAG).warning(f"Opus解码错误，跳过数据包 {i}: {e}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"音频处理错误，数据包 {i}: {e}")
            
            return pcm_data
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"音频解码过程发生错误: {e}")
            return []
        finally:
            if decoder is not None:
                try:
                    del decoder
                    gc.collect()
                except Exception as e:
                    logger.bind(tag=TAG).debug(f"释放decoder资源时出错: {e}")
