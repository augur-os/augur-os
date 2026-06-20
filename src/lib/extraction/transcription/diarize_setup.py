"""One-time download of the pyannote diarization models into the Augur cache.

The pyannote *segmentation* and *wespeaker embedding* models are gated on
Hugging Face: you must accept each model's license with your HF account and
provide a token before this will succeed.

    # 1. Accept the licenses (once, in a browser, signed into HF):
    #    https://huggingface.co/pyannote/segmentation-3.0
    #    https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM
    # 2. Provide a token, either:
    #    export HF_TOKEN=hf_...        (or `huggingface-cli login`)
    # 3. Download:
    uv run python -m src.lib.extraction.transcription.diarize_setup

Models land under ``get_cache_dir()/diarization/`` with the substring-preserving
directory names that pyannote's backend routing requires. Re-running is
idempotent (hf_hub_download skips files already present).
"""

from __future__ import annotations

import os
import sys

from .diarize import EMBEDDING_DIR, SEGMENTATION_DIR, models_dir, models_present

# (HF repo id, local directory name) — local names MUST preserve the substring
# pyannote routes on (see diarize.EMBEDDING_DIR).
_MODELS = [
    ("pyannote/segmentation-3.0", SEGMENTATION_DIR),
    ("pyannote/wespeaker-voxceleb-resnet34-LM", EMBEDDING_DIR),
]


def download_models(token: str | None = None) -> int:
    """Download both gated models into the cache. Returns a process exit code."""
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
        from huggingface_hub.utils import (  # type: ignore
            GatedRepoError,
            LocalEntryNotFoundError,
        )
    except ImportError:
        print(
            "huggingface_hub is required. Install the diarization extra:\n" "  uv sync --extra diarization",
            file=sys.stderr,
        )
        return 2

    token = token or os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    base = models_dir()
    base.mkdir(parents=True, exist_ok=True)

    for repo_id, local_name in _MODELS:
        target = base / local_name
        target.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {repo_id} -> {target} ...", file=sys.stderr)
        try:
            hf_hub_download(
                repo_id=repo_id,
                filename="pytorch_model.bin",
                local_dir=str(target),
                token=token,
            )
        except GatedRepoError:
            print(
                f"\nERROR: {repo_id} is gated. Accept its license while signed "
                f"into Hugging Face, then set HF_TOKEN and re-run:\n"
                f"  https://huggingface.co/{repo_id}",
                file=sys.stderr,
            )
            return 3
        except LocalEntryNotFoundError:
            print(
                f"\nERROR: could not reach Hugging Face to download {repo_id}. "
                "Check your network connection and try again.",
                file=sys.stderr,
            )
            return 4

    if models_present():
        print(f"\nDiarization models ready under {base}", file=sys.stderr)
        return 0
    print(
        f"\nERROR: download completed but model files are missing under {base}.",
        file=sys.stderr,
    )
    return 5


def main() -> int:
    return download_models()


if __name__ == "__main__":
    raise SystemExit(main())
