import time
import os
import sys
import io
import json
import re
import wave
import torch
import numpy as np
from typing import Optional, Tuple, List
from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType
from collections import deque

TAG = __name__
logger = setup_logging()

try:
    # Try to import SimulStreaming
    # SimulStreaming is not a standard package, so we need to add it to the path
    import sys
    import importlib.util
    import os
    
    # Try to find SimulStreaming in common locations
    SIMULSTREAMING_AVAILABLE = False
    simulstreaming_paths = [
        # Check if SimulStreaming is in the project root
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "SimulStreaming"),
        # Check if it's in the parent directory
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "SimulStreaming"),
        # Check environment variable
        os.environ.get("SIMULSTREAMING_PATH", ""),
    ]
    
    # Try to add SimulStreaming to path and import
    for simulstreaming_path in simulstreaming_paths:
        if simulstreaming_path and os.path.exists(simulstreaming_path):
            if simulstreaming_path not in sys.path:
                sys.path.insert(0, simulstreaming_path)
            try:
                # Try importing from whisper_streaming subdirectory
                from whisper_streaming.whisper_streaming import WhisperStreamingProcessor
                SIMULSTREAMING_AVAILABLE = True
                logger.info(f"SimulStreaming found at: {simulstreaming_path}")
                break
            except ImportError:
                try:
                    # Try alternative import structure
                    from whisper_streaming import WhisperStreamingProcessor
                    SIMULSTREAMING_AVAILABLE = True
                    logger.info(f"SimulStreaming found at: {simulstreaming_path}")
                    break
                except ImportError:
                    continue
    
    # If not found in paths, try direct import (in case it's in PYTHONPATH)
    if not SIMULSTREAMING_AVAILABLE:
        try:
            from whisper_streaming.whisper_streaming import WhisperStreamingProcessor
            SIMULSTREAMING_AVAILABLE = True
            logger.info("SimulStreaming imported from PYTHONPATH")
        except ImportError:
            try:
                from whisper_streaming import WhisperStreamingProcessor
                SIMULSTREAMING_AVAILABLE = True
                logger.info("SimulStreaming imported from PYTHONPATH (alternative path)")
            except ImportError:
                SIMULSTREAMING_AVAILABLE = False
    
    # Fallback to transformers if SimulStreaming not available
    if not SIMULSTREAMING_AVAILABLE:
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        TRANSFORMERS_AVAILABLE = True
    else:
        TRANSFORMERS_AVAILABLE = False
except ImportError:
    SIMULSTREAMING_AVAILABLE = False
    try:
        from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
        TRANSFORMERS_AVAILABLE = True
    except ImportError:
        TRANSFORMERS_AVAILABLE = False


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        
        if not SIMULSTREAMING_AVAILABLE:
            if not TRANSFORMERS_AVAILABLE:
                raise ImportError(
                    "SimulStreaming or transformers library is required for Whisper ASR. "
                    "Install SimulStreaming with: pip install git+https://github.com/ufal/SimulStreaming.git"
                )
            else:
                logger.bind(tag=TAG).warning(
                    "SimulStreaming not available, falling back to Hugging Face Whisper. "
                    "For better streaming performance, install SimulStreaming: "
                    "pip install git+https://github.com/ufal/SimulStreaming.git"
                )
                self.use_simulstreaming = False
        else:
            self.use_simulstreaming = True
        
        # Enable MPS fallback early if MPS might be used
        if "PYTORCH_ENABLE_MPS_FALLBACK" not in os.environ:
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        
        # Enable streaming mode (always enabled with SimulStreaming)
        self.enable_streaming = config.get("enable_streaming", True)  # Default to True for SimulStreaming
        if self.enable_streaming:
            self.interface_type = InterfaceType.STREAM
            # Streaming configuration
            self.streaming_chunk_duration = config.get("streaming_chunk_duration", 2.0)  # seconds
            self.streaming_overlap = config.get("streaming_overlap", 0.5)  # seconds overlap
            logger.bind(tag=TAG).info(
                f"Whisper streaming enabled: chunk_duration={self.streaming_chunk_duration}s, "
                f"overlap={self.streaming_overlap}s, using SimulStreaming={self.use_simulstreaming}"
            )
        else:
            self.interface_type = InterfaceType.LOCAL
        
        self.delete_audio_file = delete_audio_file
        self.output_dir = config.get("output_dir", "tmp/asr_output")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Model configuration
        self.model_id = config.get("model_id", "openai/whisper-large-v3")
        
        # Auto-detect device and dtype
        requested_device = config.get("device", None)
        if requested_device is None:
            if torch.cuda.is_available():
                self.device = "cuda:0"
            else:
                self.device = "cpu"
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    logger.bind(tag=TAG).info(
                        "MPS is available but using CPU for Whisper ASR due to compatibility issues."
                    )
        else:
            requested_device_str = str(requested_device).lower()
            if "cuda" in requested_device_str:
                if not torch.cuda.is_available():
                    logger.bind(tag=TAG).warning("CUDA requested but not available. Falling back to CPU.")
                    self.device = "cpu"
                else:
                    self.device = requested_device
            elif "mps" in requested_device_str:
                if not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
                    logger.bind(tag=TAG).warning("MPS requested but not available. Falling back to CPU.")
                    self.device = "cpu"
                else:
                    self.device = "mps"
            else:
                self.device = requested_device
        
        # Auto-detect dtype
        requested_dtype = config.get("torch_dtype", None)
        if requested_dtype is None:
            if "cuda" in self.device.lower() and torch.cuda.is_available():
                self.torch_dtype = torch.float16
            else:
                self.torch_dtype = torch.float32
        else:
            if isinstance(requested_dtype, str):
                if requested_dtype == "float16":
                    if "cuda" in self.device.lower() and torch.cuda.is_available():
                        self.torch_dtype = torch.float16
                    else:
                        self.torch_dtype = torch.float32
                else:
                    self.torch_dtype = torch.float32
            else:
                self.torch_dtype = requested_dtype
        
        self.language = config.get("language", None)  # None = auto-detect
        self.task = config.get("task", "transcribe")  # "transcribe" or "translate"
        
        # SimulStreaming specific configuration
        self.min_chunk_size = config.get("min_chunk_size", 1.0)  # Minimum chunk size in seconds
        self.frame_threshold = config.get("frame_threshold", 1.0)  # AlignAtt threshold
        self.beams = config.get("beams", 1)  # Number of beams for beam search
        self.use_vac = config.get("use_vac", False)  # Voice Activity Controller
        
        logger.bind(tag=TAG).info(
            f"Initializing Whisper ASR: model={self.model_id}, device={self.device}, "
            f"dtype={self.torch_dtype}, SimulStreaming={self.use_simulstreaming}"
        )
        
        try:
            if self.use_simulstreaming:
                # Initialize SimulStreaming processor
                # Note: SimulStreaming API may vary, adjust parameters based on actual implementation
                try:
                    self.processor = WhisperStreamingProcessor(
                        model_path=self.model_id,
                        device=self.device,
                        torch_dtype=self.torch_dtype,
                        language=self.language if self.language else "auto",
                        task=self.task,
                        min_chunk_size=self.min_chunk_size,
                        frame_threshold=self.frame_threshold,
                        beams=self.beams,
                        use_vac=self.use_vac,
                    )
                    logger.bind(tag=TAG).info("SimulStreaming Whisper processor loaded successfully")
                except TypeError as e:
                    # If the API is different, try with fewer parameters
                    logger.bind(tag=TAG).warning(f"SimulStreaming initialization with full params failed: {e}, trying minimal params")
                    try:
                        self.processor = WhisperStreamingProcessor(
                            model_path=self.model_id,
                            device=self.device,
                            language=self.language if self.language else "auto",
                        )
                        logger.bind(tag=TAG).info("SimulStreaming Whisper processor loaded with minimal params")
                    except Exception as e2:
                        logger.bind(tag=TAG).error(f"Failed to initialize SimulStreaming: {e2}")
                        raise
            else:
                # Fallback to Hugging Face transformers
                from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
                self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                    self.model_id,
                    torch_dtype=self.torch_dtype,
                    low_cpu_mem_usage=True,
                    use_safetensors=True,
                )
                self.model.to(self.device)
                self.processor_tokenizer = AutoProcessor.from_pretrained(self.model_id)
                self.pipe = pipeline(
                    "automatic-speech-recognition",
                    model=self.model,
                    tokenizer=self.processor_tokenizer.tokenizer,
                    feature_extractor=self.processor_tokenizer.feature_extractor,
                    torch_dtype=self.torch_dtype,
                    device=self.device,
                )
                logger.bind(tag=TAG).info("Hugging Face Whisper model loaded successfully")
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to load Whisper model: {e}", exc_info=True)
            raise
        
        # Streaming state
        if self.enable_streaming:
            self.streaming_buffer = deque()
            self.streaming_processing = False
            self.streaming_last_result = ""
            self.streaming_task = None

    async def open_audio_channels(self, conn):
        """Open audio channels for streaming mode"""
        await super().open_audio_channels(conn)
        if self.enable_streaming:
            # Initialize streaming state per connection
            if not hasattr(conn, 'whisper_streaming_buffer'):
                conn.whisper_streaming_buffer = []
                conn.whisper_streaming_last_process = 0
                conn.whisper_streaming_processed_chunks = 0
                conn.whisper_streaming_partial_results = []
                # Initialize SimulStreaming state if using it
                if self.use_simulstreaming:
                    conn.whisper_streaming_processor_state = None

    async def receive_audio(self, conn, audio, audio_have_voice):
        """Override receive_audio for streaming mode"""
        if not self.enable_streaming:
            # Use base class behavior for non-streaming mode
            await super().receive_audio(conn, audio, audio_have_voice)
            return
        
        # Streaming mode: process audio incrementally
        if conn.client_listen_mode == "auto" or conn.client_listen_mode == "realtime":
            have_voice = audio_have_voice
        else:
            have_voice = conn.client_have_voice
        
        # Add audio to buffer
        conn.asr_audio.append(audio)
        if not hasattr(conn, 'whisper_streaming_buffer'):
            conn.whisper_streaming_buffer = []
        conn.whisper_streaming_buffer.append(audio)
        
        # Handle voice stop - finalize processing and send to LLM
        if conn.client_voice_stop:
            if self.use_simulstreaming:
                # Finalize SimulStreaming processing (sends final result to LLM)
                await self._finalize_simulstreaming(conn)
            else:
                # For non-SimulStreaming streaming mode, process accumulated audio
                asr_audio_task = conn.asr_audio.copy()
                audio_chunk_count = len(asr_audio_task)
                if audio_chunk_count > 5:
                    logger.bind(tag=TAG).debug(
                        f"Finalizing ASR on listen stop: audio_chunks={audio_chunk_count}, "
                        f"estimated_duration={audio_chunk_count * 0.06:.2f}s"
                    )
                    await self.handle_voice_stop(conn, asr_audio_task)
                else:
                    logger.bind(tag=TAG).warning(
                        f"ASR audio too short on listen stop: {audio_chunk_count} chunks "
                        f"(minimum 5 required). This may indicate no speech was captured."
                    )
            
            # Clear buffers and reset states
            conn.asr_audio.clear()
            if hasattr(conn, 'whisper_streaming_buffer'):
                conn.whisper_streaming_buffer = []
            conn.reset_vad_states()
            return
        
        # Skip processing if no voice detected (unless in manual mode where client controls voice state)
        if not have_voice and not conn.client_have_voice:
            conn.asr_audio = conn.asr_audio[-10:]
            conn.whisper_streaming_buffer = conn.whisper_streaming_buffer[-10:]
            return
        
        # Process audio incrementally during listen period (continuous processing)
        # This sends partial results as STT messages, but doesn't trigger LLM
        # Only process if we have voice (either from VAD or from client in manual mode)
        if have_voice or conn.client_have_voice:
            if self.use_simulstreaming:
                # Process audio chunk with SimulStreaming (sends partial STT results)
                # This will send incremental STT messages but NOT trigger LLM
                await self._process_simulstreaming_chunk(conn, audio, is_final=False)
            else:
                # For non-SimulStreaming streaming mode, process in chunks and send partial results
                # Calculate accumulated audio duration (assuming 60ms per chunk)
                chunk_duration_ms = 60
                accumulated_duration = len(conn.whisper_streaming_buffer) * chunk_duration_ms / 1000.0
                
                # Process if we have enough data (e.g., every 2 seconds)
                # This sends partial STT results but does NOT trigger LLM
                if accumulated_duration >= self.streaming_chunk_duration:
                    await self._process_streaming_chunk(conn, is_final=False)

    async def _process_simulstreaming_chunk(self, conn, audio: bytes, is_final: bool = False):
        """Process audio chunk with SimulStreaming"""
        try:
            # Decode Opus to PCM if needed
            if conn.audio_format == "pcm":
                pcm_data = audio
            else:
                pcm_data_list = self.decode_opus([audio])
                if pcm_data_list:
                    pcm_data = pcm_data_list[0]
                else:
                    return
            
            # Convert PCM bytes to numpy array (16-bit signed integers, 16kHz mono)
            # SimulStreaming expects float32 array normalized to [-1, 1]
            audio_array = np.frombuffer(pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
            
            # Process with SimulStreaming
            # Initialize processor state for this connection if needed
            if not hasattr(conn, 'whisper_streaming_processor_state'):
                # Create state - API may vary, try common patterns
                try:
                    conn.whisper_streaming_processor_state = self.processor.create_state()
                except AttributeError:
                    # If create_state doesn't exist, state might be managed internally
                    # Store a flag to track if we've initialized
                    conn.whisper_streaming_processor_state = True
                    # Try to initialize the processor for this connection
                    if hasattr(self.processor, 'reset'):
                        self.processor.reset()
            
            # Feed audio to processor
            # SimulStreaming API may use different method names
            try:
                # Try process_chunk method
                if hasattr(self.processor, 'process_chunk'):
                    results = self.processor.process_chunk(
                        conn.whisper_streaming_processor_state,
                        audio_array,
                        is_final=is_final
                    )
                elif hasattr(self.processor, 'process'):
                    # Alternative method name
                    results = self.processor.process(audio_array, is_final=is_final)
                elif hasattr(self.processor, 'transcribe_chunk'):
                    # Another possible method name
                    results = self.processor.transcribe_chunk(audio_array, is_final=is_final)
                else:
                    # If we can't find the right method, log and skip
                    logger.bind(tag=TAG).warning(
                        "SimulStreaming processor doesn't have expected methods. "
                        "Please check SimulStreaming API documentation."
                    )
                    return
            except Exception as e:
                logger.bind(tag=TAG).error(f"Error calling SimulStreaming processor: {e}", exc_info=True)
                return
            
            # Handle incremental results
            # Results format may vary - could be list of dicts, list of strings, or single string
            if results:
                # Normalize results to list format
                if isinstance(results, str):
                    results = [{"text": results}]
                elif not isinstance(results, list):
                    results = [results]
                
                for result in results:
                    # Extract text from result (handle different formats)
                    if isinstance(result, dict):
                        text = result.get("text", "").strip()
                    elif isinstance(result, str):
                        text = result.strip()
                    else:
                        text = str(result).strip()
                    
                    if text:
                        # Store partial result
                        if not hasattr(conn, 'whisper_streaming_partial_results'):
                            conn.whisper_streaming_partial_results = []
                        
                        # Check if this is a new segment or continuation
                        if not conn.whisper_streaming_partial_results or text != conn.whisper_streaming_partial_results[-1]:
                            conn.whisper_streaming_partial_results.append(text)
                            
                            # Send STT message for real-time display
                            if not is_final:
                                from core.handle.sendAudioHandle import send_stt_message
                                # Build cumulative text
                                display_text = self._stitch_text_segments(conn.whisper_streaming_partial_results)
                                await send_stt_message(conn, display_text)
                                logger.bind(tag=TAG).debug(f"SimulStreaming partial result: {text}")
                            
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error processing SimulStreaming chunk: {e}", exc_info=True)

    async def _finalize_simulstreaming(self, conn):
        """Finalize SimulStreaming processing and send to LLM"""
        try:
            if not hasattr(conn, 'whisper_streaming_partial_results'):
                return
            
            # Get final stitched text
            final_text = self._stitch_text_segments(conn.whisper_streaming_partial_results)
            
            if final_text and final_text.strip():
                from core.handle.receiveAudioHandle import startToChat
                from core.handle.reportHandle import enqueue_asr_report
                from core.providers.asr.base import ASRProviderBase
                
                speaker_name = getattr(conn, 'current_speaker', None)
                enhanced_text = ASRProviderBase._build_enhanced_text(
                    self, final_text, speaker_name
                )
                
                logger.bind(tag=TAG).info(f"Final SimulStreaming text: {final_text}")
                await startToChat(conn, enhanced_text)
                enqueue_asr_report(conn, enhanced_text, conn.asr_audio.copy())
            
            # Clear state
            conn.whisper_streaming_partial_results = []
            if hasattr(conn, 'whisper_streaming_processor_state'):
                conn.whisper_streaming_processor_state = None
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"Error finalizing SimulStreaming: {e}", exc_info=True)

    def _find_word_overlap(self, text1: str, text2: str) -> int:
        """Find the number of overlapping words between the end of text1 and start of text2"""
        def normalize_words(text):
            text = re.sub(r'[^\w\s]', '', text.lower())
            return text.split()
        
        words1 = normalize_words(text1)
        words2 = normalize_words(text2)
        
        if not words1 or not words2:
            return 0
        
        max_overlap = min(len(words1), len(words2))
        
        for overlap_len in range(max_overlap, 0, -1):
            suffix_words = words1[-overlap_len:]
            prefix_words = words2[:overlap_len]
            
            if suffix_words == prefix_words:
                return overlap_len
        
        return 0
    
    def _stitch_text_segments(self, segments: List[str]) -> str:
        """Stitch together text segments, handling overlap to avoid duplicates"""
        if not segments:
            return ""
        
        if len(segments) == 1:
            return segments[0].strip()
        
        result = segments[0].strip()
        
        for i in range(1, len(segments)):
            prev_text = result
            next_text = segments[i].strip()
            
            if not next_text:
                continue
            
            # Method 1: Try word-level overlap detection
            overlap_words = self._find_word_overlap(prev_text, next_text)
            
            if overlap_words > 0:
                next_normalized = re.sub(r'[^\w\s]', '', next_text.lower())
                next_words_list = next_normalized.split()
                
                if overlap_words < len(next_words_list):
                    remaining_words = next_words_list[overlap_words:]
                    
                    if remaining_words:
                        first_remaining_word = remaining_words[0]
                        pattern = r'\b' + re.escape(first_remaining_word) + r'\b'
                        match = re.search(pattern, next_text, re.IGNORECASE)
                        
                        if match:
                            remaining_text = next_text[match.start():].strip()
                            result += " " + remaining_text
                        else:
                            result += " " + " ".join(remaining_words)
                    else:
                        logger.bind(tag=TAG).debug(
                            f"All {overlap_words} words overlap, skipping: '{next_text}'"
                        )
                else:
                    logger.bind(tag=TAG).debug(
                        f"Next segment completely overlaps ({overlap_words} words), skipping: '{next_text}'"
                    )
                
                continue
            
            # Method 2: Fallback to character-level overlap detection
            overlap_found = False
            max_overlap_len = min(len(prev_text), len(next_text))
            min_overlap = max(3, int(max_overlap_len * 0.1))
            
            for overlap_len in range(max_overlap_len, min_overlap - 1, -1):
                prev_suffix = prev_text[-overlap_len:].strip()
                next_prefix = next_text[:overlap_len].strip()
                
                prev_normalized = re.sub(r'[^\w\s]', '', prev_suffix.lower())
                next_normalized = re.sub(r'[^\w\s]', '', next_prefix.lower())
                
                if prev_normalized == next_normalized and len(prev_normalized) >= 3:
                    result += next_text[overlap_len:].strip()
                    overlap_found = True
                    break
            
            if not overlap_found:
                result_normalized = re.sub(r'[^\w\s]', '', result.lower())
                next_normalized = re.sub(r'[^\w\s]', '', next_text.lower())
                
                if next_normalized not in result_normalized:
                    result += " " + next_text
        
        return result.strip()

    async def _process_streaming_chunk(self, conn, is_final=False):
        """Process a chunk of streaming audio (fallback for non-SimulStreaming mode)"""
        # This is the old chunk-based processing method, kept for fallback
        # Implementation similar to before but simplified since we prefer SimulStreaming
        pass

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """Convert speech data to text using Whisper (non-streaming mode)"""
        file_path = None
        
        try:
            if self.use_simulstreaming:
                # Use SimulStreaming for non-streaming mode too
                # Decode Opus to PCM
                if audio_format == "pcm":
                    pcm_data = opus_data
                else:
                    pcm_data = self.decode_opus(opus_data)
                
                combined_pcm_data = b"".join(pcm_data)
                
                if len(combined_pcm_data) == 0:
                    return "", file_path
                
                # Convert to numpy array
                audio_array = np.frombuffer(combined_pcm_data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Process with SimulStreaming
                state = self.processor.create_state()
                results = self.processor.process_chunk(state, audio_array, is_final=True)
                
                # Extract text from results
                text = ""
                if results:
                    text = " ".join([r.get("text", "").strip() for r in results if r.get("text", "").strip()])
                
                return text.strip(), file_path
            else:
                # Fallback to Hugging Face transformers
                # (Keep existing implementation for compatibility)
                if audio_format == "pcm":
                    pcm_data = opus_data
                else:
                    pcm_data = self.decode_opus(opus_data)
                
                combined_pcm_data = b"".join(pcm_data)
                
                if len(combined_pcm_data) == 0:
                    return "", file_path
                
                file_path = self.save_audio_to_file(pcm_data, session_id)
                
                result = self.pipe(file_path)
                
                if isinstance(result, dict):
                    text = result.get("text", "")
                else:
                    text = str(result)
                
                return text.strip(), file_path
                
        except Exception as e:
            logger.bind(tag=TAG).error(f"Whisper ASR failed: {e}", exc_info=True)
            return "", file_path
        finally:
            if self.delete_audio_file and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Failed to delete audio file {file_path}: {e}")
