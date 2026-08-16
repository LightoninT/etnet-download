"""Unit tests for the .env loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.envconfig import DEFAULTS, load_settings, parse_env  # noqa: E402


def test_parse_env_basic():
    d = parse_env("A=1\n# comment\nB = \"two\"\n\nC='three'\nBADLINE\n")
    assert d == {"A": "1", "B": "two", "C": "three"}


def test_load_settings_defaults_when_no_file():
    s = load_settings(files=[])
    assert s["ETNET_FUTURES_URL"].endswith("/tc/futures/")
    assert s["REQUEST_TIMEOUT"] == "30"
    assert s["OUTPUT_DIR"] == ""


def test_load_settings_from_file(tmp_path):
    f = tmp_path / "custom.env"
    f.write_text(
        "ETNET_FUTURES_URL=https://example.com/futures\n"
        "OUTPUT_DIR=C:/MyData\n"
        "DOWNLOAD_PREFIX=hkfut\n",
        encoding="utf-8",
    )
    s = load_settings(files=[f])
    assert s["ETNET_FUTURES_URL"] == "https://example.com/futures"
    assert s["OUTPUT_DIR"] == "C:/MyData"
    assert s["DOWNLOAD_PREFIX"] == "hkfut"
    # untouched defaults remain
    assert s["REQUEST_TIMEOUT"] == DEFAULTS["REQUEST_TIMEOUT"]


def test_parse_env_ignores_inline_spaces_ok():
    d = parse_env("X = 1  ")
    assert d == {"X": "1"}


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
