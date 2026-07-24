"""T20 MCP package metadata."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("t20-mcp")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"
