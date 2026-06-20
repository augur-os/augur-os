from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_tts_skill_root_removed():
    assert not PROJECT_ROOT.joinpath("skills", "tts").exists()


def test_read_aloud_ui_wiring_removed():
    block_renderer = (PROJECT_ROOT / "apps" / "dashboard" / "components" / "blocks" / "BlockRenderer.tsx").read_text(
        encoding="utf-8"
    )
    block_types = (PROJECT_ROOT / "apps" / "dashboard" / "lib" / "blocks" / "types.ts").read_text(encoding="utf-8")

    assert "ReadAloudButton" not in block_renderer
    assert "readAloud" not in block_renderer
    assert "readAloud" not in block_types
