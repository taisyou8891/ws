from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_ai_loop_config_exists():
    assert (ROOT / ".claude" / "ai-loop.json").is_file()
