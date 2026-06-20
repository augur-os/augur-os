# Ollama Setup Documentation

This directory contains the complete Ollama setup and optimization documentation for MacBook Air M4.

## 📚 Files

### Primary Documentation
- **[FINAL-SETUP-SUMMARY.md](./FINAL-SETUP-SUMMARY.md)** - ⭐ **Start here!** Complete setup summary with usage examples
- **[ollama-m4-setup.md](./ollama-m4-setup.md)** - Detailed M4 optimization guide with all settings explained
- **[ollama-cleanup-summary.md](./ollama-cleanup-summary.md)** - What models were removed and why

### Tools & References
- **[test-ollama.sh](./test-ollama.sh)** - Performance testing script
- **[quick-reference.txt](./quick-reference.txt)** - Quick command reference card

## 🚀 Quick Start

```bash
# Run Ollama
ollama run llama3.2:3b-instruct-q8_0

# View quick reference
cat horizontal/setup/ollama/quick-reference.txt

# Run performance tests
cd horizontal/setup/ollama
./test-ollama.sh
```

## ⚙️ Setup Summary

- **Model**: llama3.2:3b-instruct-q8_0 (3.4 GB)
- **Optimizations**: Flash Attention, Memory Locking, 100% GPU
- **Storage Saved**: 13.5 GB (80% reduction from original 16.9 GB)
- **Performance**: ~25+ tokens/sec on M4

## 📖 Documentation Order

1. Read [FINAL-SETUP-SUMMARY.md](./FINAL-SETUP-SUMMARY.md) for overview
2. Reference [quick-reference.txt](./quick-reference.txt) for daily commands
3. Consult [ollama-m4-setup.md](./ollama-m4-setup.md) for deep dives

---
*Created: 2026-01-04*
*System: MacBook Air M4, 16GB RAM*
*Ollama: v0.13.0*
