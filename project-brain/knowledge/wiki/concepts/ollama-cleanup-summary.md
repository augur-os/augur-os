---
title: Ollama Cleanup Summary - 2026-01-04
type: setup-summary
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


# Ollama Cleanup Summary - 2026-01-04

## ✅ Space Freed: 9.1 GB

### Models Removed:
1. ❌ **gemma3:4b** (3.3 GB) - Redundant with llama3.2
2. ❌ **qwen3:latest** (5.2 GB) - Only needed for Chinese/multilingual tasks
3. ❌ **dengcao/Qwen3-Embedding-0.6B** (639 MB) - Specialized embeddings model

### Models Kept (7.8 GB total):
1. ✅ **llama3.2:3b-instruct-q8_0** (3.4 GB) - **PRIMARY MODEL** - Optimized for M4
2. ✅ **mistral:latest** (4.4 GB) - Excellent general-purpose model

## 🚀 Quick Usage

### Use the optimized model (recommended):
```bash
ollama run llama3.2:3b-instruct-q8_0
```

### Use Mistral for comparison:
```bash
ollama run mistral
```

### View installed models:
```bash
ollama list
```

### Check performance:
```bash
ollama ps
```

## 📊 Storage Impact
- **Before**: 16.9 GB
- **After**: 7.8 GB
- **Saved**: 9.1 GB (54% reduction)

## 🎯 When to Download New Models

### For Coding Tasks:
```bash
ollama pull qwen2.5-coder:7b-instruct-q5_K_M  # 5 GB, specialized for code
```

### For Speed (smallest/fastest):
```bash
ollama pull llama3.2:1b  # 1.3 GB, ultra-fast
```

### For Quality (best responses):
```bash
ollama pull llama3.1:8b-instruct-q5_K_M  # 5.5 GB, higher quality
```

## 💡 Tips
- Keep only 2-3 models for your main use cases
- The M4's 16GB RAM can handle models up to ~8B parameters efficiently
- Q5_K_M and Q8_0 quantizations offer the best quality/speed balance
- Remove models you haven't used in 30+ days

---
✅ Your Ollama setup is now lean, optimized, and ready for maximum performance!
