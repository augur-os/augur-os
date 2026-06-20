---
title: Ollama Setup for MacBook Air M4 - Optimized Configuration
type: setup-guide
skill: platform-admin
tags:
- platform-admin
- ollama
- setup
_relates_to:
- '[[ollama]]'
- '[[platform-admin]]'
- '[[setup]]'
---


# Ollama Setup for MacBook Air M4 - Optimized Configuration

## ✅ System Verified
- **Ollama Version**: 0.13.0
- **CPU**: Apple M4 (10 cores)
- **RAM**: 16 GB
- **GPU**: Apple M4 (integrated)
- **Status**: Working correctly ✓

## 🚀 Performance Optimizations Applied

### Environment Variables (in ~/.zshrc)
```bash
export OLLAMA_NUM_PARALLEL=2          # Run 2 models in parallel
export OLLAMA_MAX_LOADED_MODELS=2     # Keep max 2 models in memory
export OLLAMA_FLASH_ATTENTION=1       # Enable flash attention (faster inference)
export OLLAMA_KEEP_ALIVE=5m           # Keep models loaded for 5 minutes
```

### Configuration File (~/.ollama/config.json)
```json
{
  "num_gpu": -1,           // Use all GPU cores (-1 = auto)
  "num_thread": 8,         // Use 8 CPU threads (optimal for 10-core M4)
  "num_ctx": 8192,         // Context window: 8K tokens
  "num_batch": 512,        // Batch size for processing
  "numa": false,           // Disable NUMA (not needed on Mac)
  "low_vram": false,       // 16GB RAM = plenty of memory
  "f16_kv": true,          // Use FP16 for KV cache (faster)
  "use_mmap": true,        // Memory-mapped files (better performance)
  "use_mlock": true        // Lock model in RAM (prevent swapping)
}
```

## 📊 Current Performance Benchmark (Mistral 7B)
- **Total duration**: 1.64s
- **Prompt evaluation rate**: 16.44 tokens/s
- **Generation rate**: 21.73 tokens/s
- **GPU utilization**: 100% ✓

## 📦 Installed Models
1. **mistral:latest** (4.4 GB) - General purpose, great performance
2. **gemma3:4b** (3.3 GB) - Smaller, faster for simple tasks
3. **qwen3:latest** (5.2 GB) - Chinese/multilingual support
4. **dengcao/Qwen3-Embedding-0.6B** (639 MB) - Embeddings model
5. **llama3.2:3b-instruct-q8_0** (downloading) - Highly optimized for M-series

## 🎯 Recommended Models for M4 MacBook Air (16GB)

### Best Overall Performance
- `llama3.2:3b-instruct-q8_0` (3.3GB) - **★ Recommended** - Optimized quantization
- `mistral:7b-instruct-q4_K_M` (4.4GB) - Excellent quality/speed balance
- `gemma3:4b` (3.3GB) - Fast and efficient

### For Coding Tasks
- `qwen2.5-coder:7b-instruct-q5_K_M` (5GB) - Specialized for code
- `codellama:7b-instruct-q4_K_M` (4GB) - Meta's code model

### For Maximum Speed
- `llama3.2:1b` (1.3GB) - Ultra-fast for simple tasks
- `phi3:mini` (2.3GB) - Microsoft's efficient model

### For Best Quality (if you need it)
- `llama3.1:8b-instruct-q5_K_M` (5.5GB) - High quality responses
- `mistral:7b-instruct-v0.3-q6_K` (5.7GB) - Higher precision

## 🔧 Usage Tips

### Pull a model
```bash
ollama pull llama3.2:3b-instruct-q8_0
```

### Run a model
```bash
ollama run llama3.2:3b-instruct-q8_0
```

### Run with specific parameters
```bash
ollama run llama3.2:3b-instruct-q8_0 \
  --num-ctx 4096 \
  --num-predict 512 \
  --temperature 0.7
```

### View model info
```bash
ollama show llama3.2:3b-instruct-q8_0
```

### Remove unused models (save space)
```bash
ollama rm model-name
```

## 💡 Performance Tips

1. **Quantization Guide** (for 16GB RAM):
   - `Q8_0`: Best quality, ~8GB models max
   - `Q6_K`: Great balance, ~7GB models max
   - `Q5_K_M`: Good quality, ~6GB models max (★ recommended)
   - `Q4_K_M`: Fast & efficient, ~4GB models max

2. **Context Size**: Use 4096-8192 for most tasks. Larger = slower but more memory.

3. **Keep Models Loaded**: The first run loads the model (~5-10s), subsequent runs are instant.

4. **Monitor Performance**:
   ```bash
   ollama ps  # See loaded models
   ```

5. **Restart Ollama** if you change environment variables:
   ```bash
   # Ollama runs as a service, restart not typically needed
   # Just start a new terminal session or: source ~/.zshrc
   ```

## 🎨 Advanced: Create Custom Modelfiles

Create a file called `Modelfile`:
```
FROM llama3.2:3b-instruct-q8_0

PARAMETER temperature 0.8
PARAMETER num_ctx 8192
PARAMETER top_p 0.9

SYSTEM You are a helpful coding assistant specialized in Python and JavaScript.
```

Build it:
```bash
ollama create my-coding-assistant -f Modelfile
ollama run my-coding-assistant
```

## 📈 Expected Performance Ranges (M4 16GB)

| Model Size | Load Time | Tokens/sec | Memory Used |
|------------|-----------|------------|-------------|
| 1-3B Q8    | 2-5s      | 40-60      | 2-4 GB      |
| 3-7B Q5/Q6 | 5-8s      | 25-35      | 4-6 GB      |
| 7-8B Q4/Q5 | 8-12s     | 15-25      | 5-8 GB      |

## 🔄 Next Steps

1. ✅ Ollama verified and working
2. ✅ Optimized configuration applied
3. ✅ Environment variables set
4. ⏳ Download recommended model (llama3.2:3b-instruct-q8_0)
5. 🎯 Test the new model when download completes
6. 🧹 Consider removing unused models to save space

## 🆘 Troubleshooting

### Model running slow?
- Check GPU usage: `ollama ps` should show "100% GPU"
- Reduce context size: use `--num-ctx 4096` instead of 8192
- Try a smaller quantization (Q4 instead of Q6/Q8)

### Out of memory?
- Use smaller models or lower quantization
- Set `OLLAMA_MAX_LOADED_MODELS=1`
- Close other memory-heavy apps

### Configuration not applying?
- Restart terminal: `source ~/.zshrc`
- Check config file: `cat ~/.ollama/config.json`

---
Generated: 2026-01-04
