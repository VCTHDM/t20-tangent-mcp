"""Offline tests for environment configuration validation."""

from __future__ import annotations

import pytest

from t20_mcp import config


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0", 1.0),
        ("1.5", 1.5),
        ("300", 300.0),
        ("999", 300.0),
    ],
)
def test_parse_ipc_timeout_clamps_supported_values(raw: str, expected: float) -> None:
    assert config._parse_ipc_timeout(raw) == expected


@pytest.mark.parametrize("raw", ["", "ten", "nan", "inf", "-inf"])
def test_parse_ipc_timeout_rejects_invalid_values(raw: str) -> None:
    with pytest.raises(RuntimeError, match="finite number"):
        config._parse_ipc_timeout(raw)


def test_detect_backend_rejects_unknown_explicit_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config, "_current_backend_env", lambda: "typo")

    with pytest.raises(RuntimeError, match="Unknown AUTOCAD_MCP_BACKEND"):
        config.detect_backend()
