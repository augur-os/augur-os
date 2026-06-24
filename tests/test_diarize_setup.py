"""Unit tests for src.lib.extraction.transcription.diarize_setup.

The real download hits gated Hugging Face models, so huggingface_hub is stubbed
via sys.modules and the model cache is redirected into tmp_path with the
AUGUR_DIARIZATION_MODEL_DIR override. No network access, no real cache writes.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from src.lib.extraction.transcription import diarize_setup
from src.lib.extraction.transcription.diarize import EMBEDDING_DIR, SEGMENTATION_DIR


def test_models_constant_pairs():
    repos = {repo for repo, _ in diarize_setup._MODELS}
    locals_ = {local for _, local in diarize_setup._MODELS}
    assert repos == {
        "pyannote/segmentation-3.0",
        "pyannote/wespeaker-voxceleb-resnet34-LM",
    }
    assert locals_ == {SEGMENTATION_DIR, EMBEDDING_DIR}


def _install_fake_hf(monkeypatch, *, download_side_effect):
    """Install a fake huggingface_hub + huggingface_hub.utils into sys.modules."""

    class GatedRepoError(Exception):
        pass

    class LocalEntryNotFoundError(Exception):
        pass

    hub = types.ModuleType("huggingface_hub")
    hub.hf_hub_download = download_side_effect

    utils = types.ModuleType("huggingface_hub.utils")
    utils.GatedRepoError = GatedRepoError
    utils.LocalEntryNotFoundError = LocalEntryNotFoundError

    monkeypatch.setitem(sys.modules, "huggingface_hub", hub)
    monkeypatch.setitem(sys.modules, "huggingface_hub.utils", utils)
    return GatedRepoError, LocalEntryNotFoundError


def test_download_models_import_error_returns_2(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(tmp_path / "cache"))
    # Setting the module entry to None makes `import huggingface_hub` raise ImportError.
    monkeypatch.setitem(sys.modules, "huggingface_hub", None)
    assert diarize_setup.download_models() == 2
    assert "huggingface_hub is required" in capsys.readouterr().err


def test_download_models_success_returns_0(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(cache))

    def fake_download(repo_id, filename, local_dir, token=None):
        # Write the weight file pyannote expects so models_present() is satisfied.
        target = Path(local_dir) / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"weights")
        return str(target)

    _install_fake_hf(monkeypatch, download_side_effect=fake_download)
    assert diarize_setup.download_models(token="hf_test") == 0
    assert (cache / SEGMENTATION_DIR / "pytorch_model.bin").is_file()
    assert (cache / EMBEDDING_DIR / "pytorch_model.bin").is_file()


def test_download_models_gated_returns_3(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(cache))

    gated_holder = {}

    def fake_download(repo_id, filename, local_dir, token=None):
        raise gated_holder["GatedRepoError"]()

    gated, _ = _install_fake_hf(monkeypatch, download_side_effect=fake_download)
    gated_holder["GatedRepoError"] = gated
    assert diarize_setup.download_models() == 3


def test_download_models_offline_returns_4(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(cache))

    holder = {}

    def fake_download(repo_id, filename, local_dir, token=None):
        raise holder["LocalEntryNotFoundError"]()

    _, offline = _install_fake_hf(monkeypatch, download_side_effect=fake_download)
    holder["LocalEntryNotFoundError"] = offline
    assert diarize_setup.download_models() == 4


def test_download_models_completed_but_missing_returns_5(monkeypatch, tmp_path):
    cache = tmp_path / "cache"
    monkeypatch.setenv("AUGUR_DIARIZATION_MODEL_DIR", str(cache))

    def fake_download(repo_id, filename, local_dir, token=None):
        # Pretend success but write nothing -> models_present() stays False.
        return "/dev/null"

    _install_fake_hf(monkeypatch, download_side_effect=fake_download)
    assert diarize_setup.download_models() == 5
