---
title: Offline ASR benchmark — NPU vs GPU
x-augur-note-type: thought
content_hash: sha256:c080569520962f4f91e3a6d0351f540599be229fe1315210f26ce1b785344ce9
captured_at: '2026-05-22T21:21:47.936727Z'
tags:
- thought
_source_type: thought
_relates_to:
- '[[thought]]'
---


# Offline ASR benchmark — NPU vs GPU

Hardware: Intel Core Ultra 7 255U · OpenVINO 2026.1 · whisper int8-ov models. Measured 2026-05-23 on the demo laptop.

## Results (10 clips, 160 words, 89.3s audio; WER vs TTS ground truth)

| Model | Device | Speed ×realtime | WER% clean | WER% noisy (~10dB) |
|---|---|---|---|---|
| base | NPU | 36× | 0.5 | 2.2 |
| base | GPU | 38× | 0.5 | 2.8 |
| base | CPU | 23× | 0.5 | 2.5 |
| large-v3 | GPU | 3.2× | 0.0 | 0.6 |
| large-v3 | CPU | 1.2× | 0.0 | 0.6 |
| large-v3 | NPU | — | — | fails at Level-Zero execute (ZE_RESULT_ERROR_UNKNOWN); compiles but can't run |

## Key findings
- **Accuracy is model-driven, not device-driven.** Same model → ~same WER on NPU/GPU/CPU. Clean = identical (0.5% all); under noise a sub-word jitter appears (NPU 2.2 / GPU 2.8 / CPU 2.5, ≈1 word in 160) from int8 kernel numerical differences flipping borderline tokens — not a real device ranking.
- **large-v3 earns its place under noise:** 0.6% vs base ~2.5% (≈4× more accurate on degraded audio). Clean audio hides this.
- **NPU ≈ GPU speed** for the small model (~37×RT); NPU's real edge is power, not latency. GPU is required for large-v3 (NPU can't execute it).
- **Speed is content-independent** (depends on audio length, not noise). large-v3: GPU 3.2×RT vs CPU 1.2×RT.
- **Router behavior is correct:** small model → NPU (same speed, lower power); flagship → GPU fallback (NPU build OK but inference fails). NPU failure cached 24h per-model to skip the ~113s wasted compile.

## Demo / repro
- `.venv\Scripts\python.exe _dev\asr_demo.py <audio> --npu` (base→NPU) / `--gpu` (large-v3→GPU)
- `.venv\Scripts\python.exe _dev\asr_bench.py [bench|bench-noisy]`; clips in `_dev/bench*/`
- Models in `%LOCALAPPDATA%\Augur\Caches\models\` (whisper-base-int8-ov 85MB, whisper-large-v3-int8-ov 1568MB). `openvino-genai` comes from `uv sync --extra ai-pc-demo`.

Caveat: synthetic white noise at one SNR; real noise (babble/reverb/music) differs, but the relative story (large-v3 robust; accuracy device-agnostic) holds.
