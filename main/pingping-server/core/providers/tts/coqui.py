import os
import io
import wave
import numpy as np
from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        
        # Device configuration (cuda or cpu)
        self.device = config.get("device", "cuda")
        use_gpu = self.device == "cuda"
        
        # Model name (e.g., "tts_models/en/ljspeech/tacotron2-DDC")
        # Available models can be listed with: tts --list_models
        self.model_name = config.get("model_name", "tts_models/en/ljspeech/tacotron2-DDC")
        
        # Speaker ID for multi-speaker models (optional)
        self.speaker_id = config.get("speaker_id", None)
        
        # Language code for multilingual models (optional)
        self.language = config.get("language", None)
        
        # Sample rate (default 22050, but depends on model)
        sample_rate = config.get("sample_rate", "22050")
        self.sample_rate = int(sample_rate) if sample_rate else 22050
        
        # Initialize model
        try:
            from TTS.api import TTS
            self.tts = TTS(
                model_name=self.model_name,
                progress_bar=False,
                gpu=use_gpu
            )
            logger.bind(tag=TAG).info(f"Coqui TTS initialized with model '{self.model_name}' on {self.device}")
        except ImportError:
            raise ImportError(
                "TTS (Coqui) package not installed. Please install it with: pip install TTS"
            )
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to initialize Coqui TTS: {e}")
            raise

    async def text_to_speak(self, text, output_file):
        """
        Generate speech from text using Coqui TTS
        
        Args:
            text: Text to synthesize
            output_file: Output file path (if None, returns audio bytes)
            
        Returns:
            Audio bytes if output_file is None, otherwise None
        """
        try:
            # Generate audio
            # Coqui TTS can generate to file or return wav as numpy array
            if output_file:
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
                
                # Generate to file
                self.tts.tts_to_file(
                    text=text,
                    file_path=output_file,
                    speaker=self.speaker_id if self.speaker_id else None,
                    language=self.language if self.language else None
                )
            else:
                # Generate to numpy array (wav format)
                wav = self.tts.tts(
                    text=text,
                    speaker=self.speaker_id if self.speaker_id else None,
                    language=self.language if self.language else None
                )
                
                # Get sample rate from model if available
                sr = self.sample_rate
                if hasattr(self.tts, 'synthesizer') and hasattr(self.tts.synthesizer, 'output_sample_rate'):
                    sr = self.tts.synthesizer.output_sample_rate
                elif hasattr(self.tts, 'output_sample_rate'):
                    sr = self.tts.output_sample_rate
                
                # Convert numpy array to WAV bytes
                # Ensure it's 1D
                if len(wav.shape) > 1:
                    wav = wav.squeeze()
                
                # Normalize to [-1, 1] range if needed
                if wav.dtype != np.int16:
                    # Normalize to [-1, 1] if not already
                    if wav.max() > 1.0 or wav.min() < -1.0:
                        wav = wav / (np.abs(wav).max() + 1e-8)
                    # Convert to int16 PCM format
                    wav_int16 = (wav * 32767).astype(np.int16)
                else:
                    wav_int16 = wav
                
                # Create WAV file in memory
                wav_io = io.BytesIO()
                with wave.open(wav_io, 'wb') as wav_file:
                    wav_file.setnchannels(1)  # Mono
                    wav_file.setsampwidth(2)  # 16-bit = 2 bytes
                    wav_file.setframerate(int(sr))
                    wav_file.writeframes(wav_int16.tobytes())
                
                return wav_io.getvalue()
                
        except Exception as e:
            # Safely encode error message to avoid encoding errors
            try:
                error_msg = str(e)
                if isinstance(error_msg, str):
                    error_msg = error_msg.encode('utf-8', errors='ignore').decode('utf-8', errors='replace')
            except Exception:
                error_msg = repr(e) if hasattr(e, '__repr__') else "Unknown error"
            logger.bind(tag=TAG).error(f"Coqui TTS generation failed: {error_msg}")
            raise Exception(f"Coqui TTS error: {error_msg}")

