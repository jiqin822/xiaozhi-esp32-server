import os
import torchaudio as ta
from config.logger import setup_logging
from core.providers.tts.base import TTSProviderBase

TAG = __name__
logger = setup_logging()


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        
        # Device configuration (cuda or cpu)
        self.device = config.get("device", "cuda")
        
        # Model type: "english" or "multilingual"
        self.model_type = config.get("model_type", "multilingual")
        
        # Language ID for multilingual model (e.g., "en", "zh", "fr", "ja", etc.)
        # Supported: ar, da, de, el, en, es, fi, fr, he, hi, it, ja, ko, ms, nl, no, pl, pt, ru, sv, sw, tr, zh
        self.language_id = config.get("language_id", "en")
        
        # Voice cloning: path to reference audio file for zero-shot voice cloning
        self.audio_prompt_path = config.get("audio_prompt_path", None)
        
        # Emotion/exaggeration control (0.0 to 1.0, default 0.5)
        exaggeration = config.get("exaggeration", "0.5")
        self.exaggeration = float(exaggeration) if exaggeration else 0.5
        
        # CFG weight for guidance (0.0 to 1.0, default 0.5)
        cfg_weight = config.get("cfg_weight", "0.5")
        self.cfg_weight = float(cfg_weight) if cfg_weight else 0.5
        
        # Sample rate (default 24000)
        sample_rate = config.get("sample_rate", "24000")
        self.sample_rate = int(sample_rate) if sample_rate else 24000
        
        # Initialize model
        try:
            if self.model_type == "multilingual":
                from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                self.model = ChatterboxMultilingualTTS.from_pretrained(device=self.device)
                logger.bind(tag=TAG).info(f"Chatterbox Multilingual TTS initialized on {self.device}")
            else:
                from chatterbox.tts import ChatterboxTTS
                self.model = ChatterboxTTS.from_pretrained(device=self.device)
                logger.bind(tag=TAG).info(f"Chatterbox English TTS initialized on {self.device}")
        except ImportError:
            raise ImportError(
                "chatterbox-tts package not installed. Please install it with: pip install chatterbox-tts"
            )
        except Exception as e:
            logger.bind(tag=TAG).error(f"Failed to initialize Chatterbox TTS: {e}")
            raise

    async def text_to_speak(self, text, output_file):
        """
        Generate speech from text using Chatterbox TTS
        
        Args:
            text: Text to synthesize
            output_file: Output file path (if None, returns audio bytes)
            
        Returns:
            Audio bytes if output_file is None, otherwise None
        """
        try:
            # Generate audio
            if self.model_type == "multilingual":
                # Multilingual model requires language_id
                wav = self.model.generate(
                    text,
                    language_id=self.language_id,
                    audio_prompt_path=self.audio_prompt_path,
                    exaggeration=self.exaggeration,
                    cfg_weight=self.cfg_weight
                )
            else:
                # English-only model
                wav = self.model.generate(
                    text,
                    audio_prompt_path=self.audio_prompt_path,
                    exaggeration=self.exaggeration,
                    cfg_weight=self.cfg_weight
                )
            
            # Get sample rate from model
            sr = self.model.sr if hasattr(self.model, 'sr') else self.sample_rate
            
            # Save to file or return bytes
            if output_file:
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else '.', exist_ok=True)
                # Save as WAV file - torchaudio expects shape [channels, samples] or [samples]
                import torch
                if isinstance(wav, torch.Tensor):
                    # Ensure correct shape for torchaudio: [channels, samples] or [samples]
                    if len(wav.shape) == 1:
                        wav = wav.unsqueeze(0)  # Add channel dimension: [1, samples]
                    elif len(wav.shape) > 2:
                        wav = wav.squeeze()
                ta.save(output_file, wav, sr)
            else:
                # Convert tensor to WAV bytes
                import torch
                import numpy as np
                import io
                import wave
                
                # Convert torch.Tensor to numpy
                if isinstance(wav, torch.Tensor):
                    wav_np = wav.cpu().numpy()
                else:
                    wav_np = np.array(wav)
                
                # Ensure it's 1D
                if len(wav_np.shape) > 1:
                    wav_np = wav_np.squeeze()
                
                # Normalize to [-1, 1] range if needed
                if wav_np.max() > 1.0 or wav_np.min() < -1.0:
                    wav_np = wav_np / (np.abs(wav_np).max() + 1e-8)
                
                # Convert to int16 PCM format
                wav_int16 = (wav_np * 32767).astype(np.int16)
                
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
            logger.bind(tag=TAG).error(f"Chatterbox TTS generation failed: {error_msg}")
            raise Exception(f"Chatterbox TTS error: {error_msg}")

