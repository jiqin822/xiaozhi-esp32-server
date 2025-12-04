import time
from typing import Dict, Any

from core.handle.receiveAudioHandle import handleAudioMessage, startToChat
from core.handle.reportHandle import enqueue_asr_report
from core.handle.sendAudioHandle import send_stt_message, send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType
from core.utils.util import remove_punctuation_and_length

TAG = __name__

class ListenTextMessageHandler(TextMessageHandler):
    """Listen消息处理器"""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.LISTEN

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        if "mode" in msg_json:
            conn.client_listen_mode = msg_json["mode"]
            conn.logger.bind(tag=TAG).debug(
                f"客户端拾音模式：{conn.client_listen_mode}"
            )
        if msg_json["state"] == "start":
            # Start listening: enable continuous ASR processing
            conn.client_have_voice = True
            conn.client_voice_stop = False
            conn.logger.bind(tag=TAG).info("Listen started: ASR will process audio continuously")
        elif msg_json["state"] == "stop":
            # Stop listening: finalize ASR and send complete sentence to LLM
            conn.client_have_voice = True
            conn.client_voice_stop = True
            conn.logger.bind(tag=TAG).info("Listen stopped: finalizing ASR and sending to LLM")
            # Trigger final ASR processing on accumulated audio
            # The client_voice_stop flag will cause ASR to finalize and send to LLM
            if len(conn.asr_audio) > 0:
                # Directly call receive_audio with an empty audio packet to trigger finalization
                # This ensures the final accumulated audio is processed and sent to LLM
                await conn.asr.receive_audio(conn, b"", False)
            else:
                # Even if no audio accumulated, ensure voice_stop is processed
                # This handles the case where audio might have been processed already
                conn.logger.bind(tag=TAG).warning(
                    "Listen stop received but no audio accumulated in asr_audio buffer"
                )
        elif msg_json["state"] == "detect":
            conn.client_have_voice = False
            conn.asr_audio.clear()
            if "text" in msg_json:
                conn.last_activity_time = time.time() * 1000
                original_text = msg_json["text"]  # 保留原始文本
                filtered_len, filtered_text = remove_punctuation_and_length(
                    original_text
                )

                # 识别是否是唤醒词
                is_wakeup_words = filtered_text in conn.config.get("wakeup_words")
                # 是否开启唤醒词回复
                enable_greeting = conn.config.get("enable_greeting", True)

                if is_wakeup_words and not enable_greeting:
                    # 如果是唤醒词，且关闭了唤醒词回复，就不用回答
                    await send_stt_message(conn, original_text)
                    await send_tts_message(conn, "stop", None)
                    conn.client_is_speaking = False
                elif is_wakeup_words:
                    conn.just_woken_up = True
                    # 上报纯文字数据（复用ASR上报功能，但不提供音频数据）
                    enqueue_asr_report(conn, "嘿，你好呀", [])
                    await startToChat(conn, "嘿，你好呀")
                else:
                    # 上报纯文字数据（复用ASR上报功能，但不提供音频数据）
                    enqueue_asr_report(conn, original_text, [])
                    # 否则需要LLM对文字内容进行答复
                    await startToChat(conn, original_text)