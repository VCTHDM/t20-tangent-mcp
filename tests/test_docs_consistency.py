"""Keep current user-facing docs synchronized with executable registries."""

from __future__ import annotations

import re
from pathlib import Path

from t20_mcp.tools.tangent import SUBCOMMANDS

ROOT = Path(__file__).resolve().parent.parent
CURRENT_DOCS = (
    ROOT / "README.md",
    ROOT / "PROJECT_RULES.md",
    ROOT / "PROJECT_CLOSEOUT_TODO.md",
    ROOT / "TODO_BACKLOG.md",
    ROOT / "docs" / "ARCHITECTURE_NOTES.md",
    ROOT / "docs" / "T20_COMMANDS.md",
)


def _section(text: str, start: str, end: str) -> str:
    _, separator, remainder = text.partition(start)
    assert separator, f"missing section start: {start}"
    body, separator, _ = remainder.partition(end)
    assert separator, f"missing section end: {end}"
    return body


def _first_column_commands(section: str) -> list[str]:
    return re.findall(r"^\|\s*`([a-z][a-z0-9_]*)`\s*\|", section, flags=re.MULTILINE)


def test_readme_and_command_catalog_list_the_executable_subcommands_once() -> None:
    expected = set(SUBCOMMANDS)

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_section = _section(readme, "### tangent 子命令", "## 项目结构")
    readme_commands = _first_column_commands(readme_section)
    assert len(readme_commands) == len(set(readme_commands)) == len(SUBCOMMANDS)
    assert set(readme_commands) == expected
    assert f"### tangent 子命令 ({len(SUBCOMMANDS)} 个)" in readme

    catalog = (ROOT / "docs" / "T20_COMMANDS.md").read_text(encoding="utf-8")
    catalog_section = _section(catalog, "## 3. 当前", "## 4.")
    catalog_commands = _first_column_commands(catalog_section)
    assert len(catalog_commands) == len(set(catalog_commands)) == len(SUBCOMMANDS)
    assert set(catalog_commands) == expected


def test_readme_lists_the_registered_mcp_tools() -> None:
    from t20_mcp.server import mcp

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    line = next(line for line in readme.splitlines() if line.startswith("共 9 个:"))
    documented = {name for name in re.findall(r"\b[a-z][a-z_]*\b", line) if name not in {"个"}}

    assert documented == set(mcp._tool_manager._tools)


def test_current_markdown_local_links_resolve() -> None:
    link_pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")

    for document in CURRENT_DOCS:
        text = document.read_text(encoding="utf-8")
        for raw_target in link_pattern.findall(text):
            target = raw_target.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (document.parent / target).resolve()
            assert resolved.exists(), f"{document.relative_to(ROOT)} -> {target}"
