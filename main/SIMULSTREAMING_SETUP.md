# SimulStreaming Setup Guide

This guide explains how to set up SimulStreaming for streaming Whisper ASR in the pingping-server.

## What is SimulStreaming?

SimulStreaming is a streaming implementation of OpenAI's Whisper model that provides real-time speech recognition with low latency. It uses the AlignAtt policy for efficient simultaneous decoding.

**Repository**: https://github.com/ufal/SimulStreaming

## Installation

**Note**: SimulStreaming is not a standard Python package (no setup.py or pyproject.toml), so it cannot be installed with `pip install`. Instead, you need to add it to your Python path.

### Option 1: Clone to Project Root (Recommended)

```bash
# From the pingping-server directory, clone SimulStreaming
cd /Users/barbaraw/projects/pingping/pingping-esp32-server/main
git clone https://github.com/ufal/SimulStreaming.git

# Install SimulStreaming dependencies
cd SimulStreaming
pip install -r requirements.txt
cd ..
```

The code will automatically detect SimulStreaming if it's in the project root directory.

### Option 2: Add to PYTHONPATH

If you prefer to clone SimulStreaming elsewhere:

```bash
# Clone the repository to a location of your choice
git clone https://github.com/ufal/SimulStreaming.git /path/to/SimulStreaming

# Install dependencies
cd /path/to/SimulStreaming
pip install -r requirements.txt

# Add to PYTHONPATH (in your shell or environment)
export PYTHONPATH="${PYTHONPATH}:/path/to/SimulStreaming"
```

### Option 3: Use Environment Variable

You can also set the `SIMULSTREAMING_PATH` environment variable:

```bash
# Clone and install dependencies
git clone https://github.com/ufal/SimulStreaming.git /path/to/SimulStreaming
cd /path/to/SimulStreaming
pip install -r requirements.txt

# Set environment variable
export SIMULSTREAMING_PATH="/path/to/SimulStreaming"
```

## Configuration

In your `config.yaml` or `.config.yaml`, configure Whisper ASR to use SimulStreaming:

```yaml
ASR:
  Whisper:
    type: whisper
    model_id: openai/whisper-large-v3  # or whisper-large-v2
    device: null  # null = auto-detect (cuda/cpu)
    torch_dtype: null  # null = auto-detect (float16 for CUDA, float32 for CPU)
    language: null  # null = auto-detect, or "en", "zh", etc.
    task: transcribe  # "transcribe" or "translate"
    output_dir: tmp/
    enable_streaming: true  # Enable streaming mode (default: true)
    streaming_chunk_duration: 2.0  # Process chunks every N seconds
    streaming_overlap: 0.5  # Overlap between chunks in seconds
    # SimulStreaming specific options:
    min_chunk_size: 1.0  # Minimum chunk size in seconds
    frame_threshold: 1.0  # AlignAtt threshold (in frames, 1 frame = 0.02s for large-v3)
    beams: 1  # Number of beams for beam search (1 = greedy)
    use_vac: false  # Voice Activity Controller (requires torch)

selected_module:
  ASR: Whisper
```

## Features

### Streaming ASR
- **Real-time processing**: Audio is processed incrementally as it arrives
- **Low latency**: Results are available as soon as speech is detected
- **Overlap handling**: Automatically handles overlapping audio segments
- **Partial results**: Sends incremental transcriptions via STT messages

### Fallback Support
If SimulStreaming is not installed, the system will automatically fall back to Hugging Face Transformers Whisper (non-streaming mode).

## Troubleshooting

### Import Error: "No module named 'whisper_streaming'"

**Solution**: Make sure SimulStreaming is installed and in your Python path.

```bash
# Verify installation
python -c "from whisper_streaming.whisper_streaming import WhisperStreamingProcessor; print('OK')"
```

### API Compatibility Issues

If you encounter errors about missing methods or incorrect API calls, the SimulStreaming API may have changed. Check the [SimulStreaming repository](https://github.com/ufal/SimulStreaming) for the latest API documentation.

The implementation includes fallback logic to handle different API patterns:
- `process_chunk()` method
- `process()` method  
- `transcribe_chunk()` method

### Performance Tips

1. **GPU Acceleration**: Use CUDA if available for faster processing
   ```yaml
   device: cuda:0
   torch_dtype: float16
   ```

2. **Chunk Size**: Adjust `streaming_chunk_duration` based on your latency requirements
   - Smaller chunks = lower latency but more processing overhead
   - Larger chunks = higher latency but better accuracy

3. **Frame Threshold**: Adjust `frame_threshold` to control when decoding starts
   - Lower values = earlier decoding (lower latency)
   - Higher values = more context before decoding (better accuracy)

## Differences from Hugging Face Whisper

| Feature | SimulStreaming | Hugging Face Whisper |
|---------|---------------|---------------------|
| Streaming | ✅ Native support | ❌ Batch processing only |
| Latency | Low (real-time) | Higher (waits for full audio) |
| Overlap handling | ✅ Automatic | ❌ Manual stitching required |
| AlignAtt policy | ✅ Included | ❌ Not available |
| Installation | From GitHub | pip install transformers |

## References

- [SimulStreaming GitHub Repository](https://github.com/ufal/SimulStreaming)
- [SimulStreaming Documentation](https://github.com/ufal/SimulStreaming#readme)

