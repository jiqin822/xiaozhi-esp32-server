import time
import os
import sys
import io
import wave
import torch
import numpy as np
from typing import Optional, Tuple, List
from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType

try:
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor, pipeline
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool):
        super().__init__()
        
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "transformers library is required for Whisper ASR. "
                "Install it with: pip install transformers accelerate datasets[audio]"
            )
        
        # Enable MPS fallback early if MPS might be used
        # This must be set before any PyTorch operations
        if "PYTORCH_ENABLE_MPS_FALLBACK" not in os.environ:
            os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
        
        self.interface_type = InterfaceType.LOCAL
        self.delete_audio_file = delete_audio_file
        self.output_dir = config.get("output_dir", "tmp/asr_output")
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Model configuration
        self.model_id = config.get("model_id", "openai/whisper-large-v3")
        
        # Auto-detect device and dtype based on availability
        requested_device = config.get("device", None)
        if requested_device is None:
            # Auto-detect: prefer CUDA > CPU > MPS
            # Note: MPS has compatibility issues with Whisper, so we prefer CPU over MPS
            if torch.cuda.is_available():
                self.device = "cuda:0"
            else:
                # Use CPU by default instead of MPS due to Whisper compatibility issues
                self.device = "cpu"
                if hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    logger.bind(tag=TAG).info(
                        "MPS is available but using CPU for Whisper ASR due to compatibility issues. "
                        "To force MPS, set device: mps in config (may have errors)."
                    )
        else:
            # Use requested device, but validate availability
            requested_device_str = str(requested_device).lower()
            if "cuda" in requested_device_str:
                if not torch.cuda.is_available():
                    logger.bind(tag=TAG).warning(
                        f"CUDA requested but not available. Falling back to CPU. "
                        f"To fix: install PyTorch with CUDA support or set device: cpu in config"
                    )
                    self.device = "cpu"
                else:
                    self.device = requested_device
            elif "mps" in requested_device_str:
                if not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
                    logger.bind(tag=TAG).warning(
                        f"MPS requested but not available (not on Apple Silicon Mac). Falling back to CPU."
                    )
                    self.device = "cpu"
                else:
                    self.device = "mps"
                    # MPS fallback is already enabled at the top of __init__
                    logger.bind(tag=TAG).warning(
                        "MPS device requested for Whisper. Note: MPS has compatibility issues with Whisper. "
                        "If you encounter errors, consider using CPU instead (device: cpu)."
                    )
            else:
                self.device = requested_device
        
        # Auto-detect dtype based on device
        requested_dtype = config.get("torch_dtype", None)
        if requested_dtype is None:
            # Auto-select: float16 for CUDA, float32 for MPS and CPU
            # Note: MPS doesn't fully support float16, so use float32
            if "cuda" in self.device.lower() and torch.cuda.is_available():
                self.torch_dtype = torch.float16
            else:
                self.torch_dtype = torch.float32
        else:
            # Convert torch_dtype string to actual type
            if isinstance(requested_dtype, str):
                if requested_dtype == "float16":
                    if "cuda" in self.device.lower() and torch.cuda.is_available():
                        self.torch_dtype = torch.float16
                    elif "mps" in self.device.lower():
                        logger.bind(tag=TAG).warning(
                            "float16 requested but MPS doesn't fully support it. Using float32 instead."
                        )
                        self.torch_dtype = torch.float32
                    else:
                        logger.bind(tag=TAG).warning(
                            "float16 requested but CUDA not available. Using float32 instead."
                        )
                        self.torch_dtype = torch.float32
                elif requested_dtype == "float32":
                    self.torch_dtype = torch.float32
                else:
                    self.torch_dtype = torch.float32
            else:
                self.torch_dtype = requested_dtype
        
        self.language = config.get("language", None)  # None = auto-detect
        self.task = config.get("task", "transcribe")  # "transcribe" or "translate"
        
        # Final validation: ensure device is valid before loading model
        device_str = str(self.device).lower()
        if "cuda" in device_str:
            if not torch.cuda.is_available():
                logger.bind(tag=TAG).warning(
                    "CUDA device requested but PyTorch was not compiled with CUDA support. "
                    "Falling back to CPU. For GPU support, install PyTorch with CUDA: "
                    "https://pytorch.org/get-started/locally/"
                )
                self.device = "cpu"
                # Also switch to float32 for CPU
                if self.torch_dtype == torch.float16:
                    self.torch_dtype = torch.float32
                    logger.bind(tag=TAG).info("Switched to float32 for CPU compatibility")
        elif "mps" in device_str:
            if not (hasattr(torch.backends, 'mps') and torch.backends.mps.is_available()):
                logger.bind(tag=TAG).warning(
                    "MPS device requested but not available (not on Apple Silicon Mac). "
                    "Falling back to CPU."
                )
                self.device = "cpu"
                if self.torch_dtype == torch.float16:
                    self.torch_dtype = torch.float32
                    logger.bind(tag=TAG).info("Switched to float32 for CPU compatibility")
            else:
                # MPS fallback is already enabled at the top of __init__
                logger.bind(tag=TAG).info(
                    "MPS device detected. PYTORCH_ENABLE_MPS_FALLBACK=1 is enabled for compatibility."
                )
        
        logger.bind(tag=TAG).info(
            f"Initializing Whisper ASR: model={self.model_id}, device={self.device}, dtype={self.torch_dtype}"
        )
        
        try:
            # Load model
            self.model = AutoModelForSpeechSeq2Seq.from_pretrained(
                self.model_id,
                torch_dtype=self.torch_dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
            )
            self.model.to(self.device)
            
            # Load processor
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            
            # Create pipeline
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=self.model,
                tokenizer=self.processor.tokenizer,
                feature_extractor=self.processor.feature_extractor,
                torch_dtype=self.torch_dtype,
                device=self.device,
            )
            
            logger.bind(tag=TAG).info("Whisper ASR model loaded successfully")
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to load Whisper model: {e}", exc_info=True)
            raise

    async def speech_to_text(
        self, opus_data: List[bytes], session_id: str, audio_format="opus"
    ) -> Tuple[Optional[str], Optional[str]]:
        """Convert speech data to text using Whisper"""
        file_path = None
        
        try:
            # Decode Opus to PCM if needed
            if audio_format == "pcm":
                pcm_data = opus_data
            else:
                pcm_data = self.decode_opus(opus_data)
            
            combined_pcm_data = b"".join(pcm_data)
            
            # Validate PCM data
            if len(combined_pcm_data) == 0:
                logger.bind(tag=TAG).warning("PCM data is empty, skipping recognition")
                return "", file_path
            
            # Check if PCM data length is reasonable (at least 20ms of 16kHz mono 16-bit PCM)
            if len(combined_pcm_data) < 320:
                logger.bind(tag=TAG).warning(
                    f"PCM data too short: {len(combined_pcm_data)} bytes, may not be recognizable"
                )
                return "", file_path
            
            # Save to WAV file for processing
            if self.delete_audio_file:
                # Use temporary file
                file_path = self.save_audio_to_file(pcm_data, session_id)
            else:
                file_path = self.save_audio_to_file(pcm_data, session_id)
            
            # Prepare generate kwargs
            # Note: Whisper's max_target_positions is 448, so we need to account for prompt tokens
            # The model adds special tokens (typically 4 tokens), so we reduce max_new_tokens accordingly
            # Using 448 - 4 (typical prompt tokens) = 444 to be safe
            max_new_tokens = 444
            
            # Check if model has max_length attribute and adjust if needed
            if hasattr(self.model.config, 'max_target_positions'):
                max_target = self.model.config.max_target_positions
                # Reserve 4 tokens for prompt/special tokens
                max_new_tokens = min(max_new_tokens, max_target - 4)
            elif hasattr(self.model.config, 'max_length'):
                max_target = self.model.config.max_length
                max_new_tokens = min(max_new_tokens, max_target - 4)
            
            generate_kwargs = {
                "max_new_tokens": max_new_tokens,
                "num_beams": 1,
                "condition_on_prev_tokens": False,
            }
            
            # Add language if specified
            if self.language:
                generate_kwargs["language"] = self.language
            
            # Add task (transcribe or translate)
            if self.task:
                generate_kwargs["task"] = self.task
            
            # Perform speech recognition
            start_time = time.time()
            logger.bind(tag=TAG).debug(f"Starting Whisper ASR on file: {file_path} (size: {len(combined_pcm_data)} bytes)")
            
            # Use the pipeline to transcribe the audio file
            # If MPS fails, fall back to CPU
            try:
                result = self.pipe(file_path, generate_kwargs=generate_kwargs)
            except RuntimeError as e:
                if "MPS device" in str(e) and "not currently implemented" in str(e):
                    logger.bind(tag=TAG).warning(
                        f"MPS operation not supported: {e}. Falling back to CPU for this operation."
                    )
                    # Temporarily switch to CPU for this operation
                    original_device = self.device
                    self.device = "cpu"
                    # Move model to CPU
                    self.model.to("cpu")
                    # Recreate pipeline with CPU
                    self.pipe = pipeline(
                        "automatic-speech-recognition",
                        model=self.model,
                        tokenizer=self.processor.tokenizer,
                        feature_extractor=self.processor.feature_extractor,
                        torch_dtype=torch.float32,
                        device="cpu",
                    )
                    # Try again with CPU
                    result = self.pipe(file_path, generate_kwargs=generate_kwargs)
                    # Restore original device (though we'll keep using CPU for now)
                    self.device = original_device
                    logger.bind(tag=TAG).info("Successfully completed ASR using CPU fallback")
                else:
                    raise
            
            # Extract text from result
            if isinstance(result, dict):
                text = result.get("text", "")
            elif isinstance(result, str):
                text = result
            else:
                text = str(result)
            
            # Ensure text is valid UTF-8
            if isinstance(text, bytes):
                try:
                    text = text.decode('utf-8', errors='replace')
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Failed to decode ASR text: {e}")
                    return "", file_path
            elif not isinstance(text, str):
                text = str(text)
            
            # Clean encoding issues
            try:
                text = text.encode('utf-8', errors='ignore').decode('utf-8', errors='replace')
            except Exception as e:
                logger.bind(tag=TAG).error(f"Failed to clean encoding: {e}")
                return "", file_path
            
            elapsed_time = time.time() - start_time
            logger.bind(tag=TAG).debug(
                f"Whisper ASR completed in {elapsed_time:.3f}s | Result: {text}"
            )
            
            # Validate result
            if not text or len(text.strip()) == 0:
                logger.bind(tag=TAG).warning("Whisper ASR returned empty text")
                return "", file_path
            
            return text.strip(), file_path
            
        except Exception as e:
            logger.bind(tag=TAG).error(f"Whisper ASR failed: {e}", exc_info=True)
            return "", file_path
            
        finally:
            # Clean up temporary file if configured
            if self.delete_audio_file and file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.bind(tag=TAG).debug(f"Deleted temporary audio file: {file_path}")
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Failed to delete audio file {file_path}: {e}")

