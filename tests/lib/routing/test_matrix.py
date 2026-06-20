import pytest

from src.lib.routing.matrix import ROUTES, RoutingError, engine_id_for


@pytest.mark.parametrize(
    "activity,mode,os_name,expected",
    [
        ("chat", "regular", "win32", "agent-chat"),
        ("chat", "regular", "darwin", "agent-chat"),
        ("chat", "offline", "win32", "ollama-llm"),
        ("chat", "offline", "darwin", "ollama-llm"),
        ("ocr", "regular", "win32", "agent-vision"),
        ("ocr", "regular", "darwin", "agent-vision"),
        ("ocr", "offline", "win32", "ollama-glm-ocr"),
        ("ocr", "offline", "darwin", "ollama-glm-ocr"),
        ("transcript", "regular", "win32", "gemini-transcribe"),
        ("transcript", "regular", "darwin", "gemini-transcribe"),
        ("transcript", "offline", "win32", "openvino-whisper"),
        ("transcript", "offline", "darwin", "faster-whisper"),
        ("transcript", "offline", "linux", "openvino-whisper"),
    ],
)
def test_every_cell_resolves(activity, mode, os_name, expected):
    assert engine_id_for(activity, mode, os_name) == expected


def test_unknown_activity_raises():
    with pytest.raises(RoutingError):
        engine_id_for("translate", "regular", "win32")


def test_unknown_mode_raises():
    with pytest.raises(RoutingError):
        engine_id_for("chat", "airplane", "win32")


def test_unmapped_os_raises_for_os_specific_cell():
    # transcript/offline has no "*"; an unknown OS must raise, not silently default
    with pytest.raises(RoutingError):
        engine_id_for("transcript", "offline", "sunos5")


def test_routes_has_exactly_six_cells():
    assert set(ROUTES.keys()) == {
        ("chat", "regular"),
        ("chat", "offline"),
        ("ocr", "regular"),
        ("ocr", "offline"),
        ("transcript", "regular"),
        ("transcript", "offline"),
    }
