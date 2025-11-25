# Whisper ASR Setup Guide

This guide explains how to set up and use OpenAI's Whisper ASR model via Hugging Face Transformers.

## Overview

Whisper is OpenAI's state-of-the-art automatic speech recognition (ASR) model. This implementation uses the open-source version from Hugging Face, which supports:
- **99 languages** including English, Chinese, Japanese, Korean, and many more
- **High accuracy** with 10-20% error reduction compared to previous versions
- **Automatic language detection**
- **Speech translation** (translate to English)
- **Local processing** (no API calls needed)

## Installation

### 1. Install Dependencies

Install the required Python packages:

```bash
pip install --upgrade transformers accelerate datasets[audio]
```

Or if you're using the project's requirements.txt:

```bash
pip install -r requirements.txt
```

### 2. Model Download

The model will be automatically downloaded from Hugging Face on first use. The default model is `whisper-large-v3` (~3GB), which provides the best accuracy.

**Available Models:**
- `openai/whisper-tiny` - Smallest, fastest (~39M parameters)
- `openai/whisper-base` - Base model (~74M parameters)
- `openai/whisper-small` - Small model (~244M parameters)
- `openai/whisper-medium` - Medium model (~769M parameters)
- `openai/whisper-large` - Large model (~1550M parameters)
- `openai/whisper-large-v2` - Large v2 (~1550M parameters)
- `openai/whisper-large-v3` - **Large v3 (recommended, ~1550M parameters)**

**Note:** Larger models provide better accuracy but require more memory and processing time.

## Configuration

### Basic Configuration

Edit `pingping-server/data/.config.yaml`:

```yaml
selected_module:
  ASR: Whisper  # Use Whisper ASR

ASR:
  Whisper:
    type: whisper
    model_id: openai/whisper-large-v3  # Model to use
    device: cuda:0  # "cuda:0" for GPU, "cpu" for CPU
    torch_dtype: float16  # "float16" for GPU, "float32" for CPU
    language: null  # null = auto-detect, or specify like "english", "chinese"
    task: transcribe  # "transcribe" or "translate"
    output_dir: tmp/
```

### Configuration Options

#### Device Configuration

**For GPU (Recommended):**
```yaml
device: cuda:0
torch_dtype: float16
```

**For CPU:**
```yaml
device: cpu
torch_dtype: float32
```

**Note:** GPU is highly recommended for faster processing. CPU will work but will be significantly slower.

#### Language Settings

**Auto-detect (Recommended):**
```yaml
language: null
```

**Specify Language:**
```yaml
language: english  # or "chinese", "japanese", "korean", etc.
```

Supported languages: https://github.com/openai/whisper/blob/main/whisper/tokenizer.py

#### Task Settings

**Transcribe (same language):**
```yaml
task: transcribe
```

**Translate (to English):**
```yaml
task: translate
```

## Usage

1. **Start the server:**
   ```bash
   python3 app.py
   ```

2. **The model will be downloaded automatically** on first use (this may take a few minutes)

3. **Test with audio input** - The ASR will automatically use Whisper for speech recognition

## Performance Tips

### GPU Acceleration

For best performance, use a GPU with CUDA support:

1. Install CUDA-compatible PyTorch (if not already installed)
2. Set `device: cuda:0` in config
3. Set `torch_dtype: float16` for faster inference

### Model Selection

- **For accuracy:** Use `whisper-large-v3` (default)
- **For speed:** Use `whisper-small` or `whisper-base`
- **For low-resource devices:** Use `whisper-tiny`

### Memory Requirements

- **whisper-tiny:** ~1GB RAM
- **whisper-base:** ~1GB RAM
- **whisper-small:** ~2GB RAM
- **whisper-medium:** ~5GB RAM
- **whisper-large-v3:** ~10GB RAM (with GPU), ~6GB RAM (CPU)

## Troubleshooting

### Import Error: "transformers library is required"

**Solution:** Install dependencies:
```bash
pip install transformers accelerate datasets[audio]
```

### CUDA Out of Memory

**Solutions:**
1. Use a smaller model (e.g., `whisper-small` instead of `whisper-large-v3`)
2. Use CPU instead of GPU: `device: cpu`
3. Use float32 instead of float16: `torch_dtype: float32`

### Slow Processing on CPU

**Solutions:**
1. Use a smaller model
2. Enable GPU acceleration if available
3. Consider using a cloud ASR service for better performance

### Model Download Fails

**Solutions:**
1. Check internet connection
2. Try downloading manually from: https://huggingface.co/openai/whisper-large-v3
3. Set `HF_HOME` environment variable to specify download location

## Comparison with FunASR

| Feature | Whisper | FunASR |
|---------|---------|--------|
| Languages | 99 languages | Primarily Chinese |
| Accuracy | Very high | High (for Chinese) |
| Model Size | Large (~3GB for large-v3) | Medium (~500MB) |
| Speed | Moderate (faster with GPU) | Fast |
| Offline | Yes | Yes |
| Auto Language Detection | Yes | Limited |

## References

- **Whisper Paper:** https://arxiv.org/abs/2212.04356
- **Hugging Face Model:** https://huggingface.co/openai/whisper-large-v3
- **Transformers Documentation:** https://huggingface.co/docs/transformers/model_doc/whisper

## Next Steps

After setup, test the ASR with audio input. The system will automatically:
1. Receive Opus audio from the client
2. Decode to PCM
3. Convert to WAV format
4. Process with Whisper
5. Return transcribed text

The transcribed text will be sent to the LLM for processing, just like with FunASR.

