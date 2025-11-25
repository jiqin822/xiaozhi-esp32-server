import time
import os
import sys
import io
import psutil
from config.logger import setup_logging
from typing import Optional, Tuple, List
from core.providers.asr.base import ASRProviderBase
from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess
import shutil
from core.providers.asr.dto.dto import InterfaceType

TAG = __name__
logger = setup_logging()

MAX_RETRIES = 2
RETRY_DELAY = 1  # 重试延迟（秒）


# 捕获标准输出
class CaptureOutput:
    def __enter__(self):
        self._output = io.StringIO()
        self._original_stdout = sys.stdout
        sys.stdout = self._output

    def __exit__(self, exc_type, exc_value, traceback):
        sys.stdout = self._original_stdout
        self.output = self._output.getvalue()
        self._output.close()

        # 将捕获到的内容通过 logger 输出
        if self.output:
            logger.bind(tag=TAG).info(self.output.strip())


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        
        # 内存检测，要求大于2G
        min_mem_bytes = 2 * 1024 * 1024 * 1024
        total_mem = psutil.virtual_memory().total
        if total_mem < min_mem_bytes:
            logger.bind(tag=TAG).error(f"可用内存不足2G，当前仅有 {total_mem / (1024*1024):.2f} MB，可能无法启动FunASR")
        
        self.interface_type = InterfaceType.LOCAL
        self.model_dir = config.get("model_dir")
        self.output_dir = config.get("output_dir")  # 修正配置键名
        self.delete_audio_file = delete_audio_file

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        with CaptureOutput():
            self.model = AutoModel(
                model=self.model_dir,
                vad_kwargs={"max_single_segment_time": 30000},
                disable_update=True,
                hub="hf",
                # device="cuda:0",  # 启用GPU加速
            )

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """语音转文本主处理逻辑"""
        file_path = None
        retry_count = 0

        while retry_count < MAX_RETRIES:
            try:
                # 合并所有opus数据包
                if audio_format == "pcm":
                    pcm_data = opus_data
                else:
                    pcm_data = self.decode_opus(opus_data)

                combined_pcm_data = b"".join(pcm_data)
                
                # 验证PCM数据
                if len(combined_pcm_data) == 0:
                    logger.bind(tag=TAG).warning("PCM数据为空，跳过识别")
                    return "", file_path
                
                # 检查PCM数据长度是否合理（至少要有一些音频数据）
                if len(combined_pcm_data) < 320:  # 至少20ms的16kHz单声道16位PCM数据
                    logger.bind(tag=TAG).warning(f"PCM数据太短: {len(combined_pcm_data)}字节，可能无法识别")
                    return "", file_path

                # 检查磁盘空间
                if not self.delete_audio_file:
                    free_space = shutil.disk_usage(self.output_dir).free
                    if free_space < len(combined_pcm_data) * 2:  # 预留2倍空间
                        raise OSError("磁盘空间不足")

                # 判断是否保存为WAV文件
                if self.delete_audio_file:
                    pass
                else:
                    file_path = self.save_audio_to_file(pcm_data, session_id)

                # 语音识别
                start_time = time.time()
                result = self.model.generate(
                    input=combined_pcm_data,
                    cache={},
                    language="auto",
                    use_itn=True,
                    batch_size_s=60,
                )
                
                # 验证结果格式
                if not result or len(result) == 0:
                    logger.bind(tag=TAG).warning("ASR返回空结果")
                    return "", file_path
                
                # 获取原始文本 - 处理不同的结果格式
                if isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict):
                        raw_text = result[0].get("text", "")
                    else:
                        raw_text = str(result[0])
                elif isinstance(result, dict):
                    raw_text = result.get("text", "")
                else:
                    raw_text = str(result)
                
                # 如果raw_text仍然是空，尝试其他可能的字段
                if not raw_text and isinstance(result, list) and len(result) > 0:
                    if isinstance(result[0], dict):
                        # 尝试其他可能的字段名
                        raw_text = result[0].get("pred", "") or result[0].get("transcription", "") or result[0].get("asr_text", "")
                
                # 记录完整结果结构用于调试
                logger.bind(tag=TAG).debug(f"ASR完整结果: {result}")
                logger.bind(tag=TAG).debug(f"ASR结果类型: {type(result)}, 长度: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")
                if isinstance(result, list) and len(result) > 0:
                    logger.bind(tag=TAG).debug(f"ASR结果[0]类型: {type(result[0])}, 内容: {result[0]}")
                
                # 记录原始结果用于调试
                logger.bind(tag=TAG).debug(f"ASR原始文本类型: {type(raw_text)}, 值: {repr(raw_text[:200])}")
                
                # 确保是字符串类型
                if isinstance(raw_text, bytes):
                    try:
                        raw_text = raw_text.decode('utf-8', errors='replace')
                        logger.bind(tag=TAG).debug(f"从bytes解码后的文本: {raw_text[:200]}")
                    except Exception as e:
                        logger.bind(tag=TAG).error(f"解码ASR文本失败: {e}")
                        return "", file_path
                elif not isinstance(raw_text, str):
                    raw_text = str(raw_text)
                
                # 清理编码问题
                try:
                    raw_text = raw_text.encode('utf-8', errors='ignore').decode('utf-8', errors='replace')
                except Exception as e:
                    logger.bind(tag=TAG).error(f"清理编码失败: {e}")
                    return "", file_path
                
                # 验证文本是否包含可打印字符
                if raw_text:
                    # 检查是否主要是乱码（包含大量非ASCII且非常见语言的字符）
                    non_ascii_count = sum(1 for c in raw_text[:200] if ord(c) > 127)
                    total_chars = len(raw_text[:200])
                    if total_chars > 0 and non_ascii_count / total_chars > 0.7:
                        # 如果超过70%是非ASCII字符，且看起来像乱码，记录警告
                        printable_count = sum(1 for c in raw_text[:200] if c.isprintable() or c.isspace())
                        if printable_count / total_chars < 0.5:
                            logger.bind(tag=TAG).warning(
                                f"ASR结果可能包含乱码数据 (非ASCII比例: {non_ascii_count/total_chars:.2%}, "
                                f"可打印字符比例: {printable_count/total_chars:.2%}): {repr(raw_text[:200])}"
                            )
                            # 不直接返回空，而是尝试清理
                            raw_text = ''.join(c for c in raw_text if c.isprintable() or c.isspace() or ord(c) < 128)
                
                # 后处理
                text = rich_transcription_postprocess(raw_text)
                
                logger.bind(tag=TAG).debug(
                    f"语音识别耗时: {time.time() - start_time:.3f}s | 结果: {text}"
                )
                
                # 最终验证
                if not text or len(text.strip()) == 0:
                    logger.bind(tag=TAG).warning("ASR处理后文本为空")
                    return "", file_path

                return text, file_path

            except OSError as e:
                retry_count += 1
                if retry_count >= MAX_RETRIES:
                    logger.bind(tag=TAG).error(
                        f"语音识别失败（已重试{retry_count}次）: {e}", exc_info=True
                    )
                    return "", file_path
                logger.bind(tag=TAG).warning(
                    f"语音识别失败，正在重试（{retry_count}/{MAX_RETRIES}）: {e}"
                )
                time.sleep(RETRY_DELAY)

            except Exception as e:
                logger.bind(tag=TAG).error(f"语音识别失败: {e}", exc_info=True)
                return "", file_path

            finally:
                # 文件清理逻辑
                if self.delete_audio_file and file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logger.bind(tag=TAG).debug(f"已删除临时音频文件: {file_path}")
                    except Exception as e:
                        logger.bind(tag=TAG).error(
                            f"文件删除失败: {file_path} | 错误: {e}"
                        )
