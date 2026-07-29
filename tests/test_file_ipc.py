"""Offline tests for AutoCAD window discovery."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

import t20_mcp.backends.file_ipc as file_ipc


class _LogRecorder:
    def __init__(self) -> None:
        self.warnings: list[tuple[str, dict[str, object]]] = []

    def warning(self, event: str, **fields: object) -> None:
        self.warnings.append((event, fields))


def _find_window(
    monkeypatch: pytest.MonkeyPatch,
    windows: list[tuple[int, str, int, str]],
) -> tuple[int | None, _LogRecorder]:
    """Run discovery against fake ``(hwnd, title, pid, image)`` windows."""
    titles = {hwnd: title for hwnd, title, _, _ in windows}
    pids = {hwnd: pid for hwnd, _, pid, _ in windows}
    images = {pid: image for _, _, pid, image in windows}

    def enum_windows(callback, extra) -> None:
        for hwnd, _, _, _ in windows:
            callback(hwnd, extra)

    fake_gui = SimpleNamespace(
        EnumWindows=enum_windows,
        GetWindowText=lambda hwnd: titles[hwnd],
        IsWindowVisible=lambda _hwnd: True,
    )
    fake_process = SimpleNamespace(
        GetWindowThreadProcessId=lambda hwnd: (1, pids[hwnd]),
    )
    recorder = _LogRecorder()

    monkeypatch.setattr(file_ipc.sys, "platform", "win32")
    monkeypatch.setattr(file_ipc, "ACAD_PROCESS_NAME", "acad.exe")
    monkeypatch.setattr(file_ipc, "_process_image_name", lambda pid: images[pid])
    monkeypatch.setattr(file_ipc, "log", recorder)
    monkeypatch.setitem(sys.modules, "win32gui", fake_gui)
    monkeypatch.setitem(sys.modules, "win32process", fake_process)

    return file_ipc.find_autocad_window(), recorder


def test_find_window_ignores_untitled_helper_when_titled_process_window_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen, recorder = _find_window(
        monkeypatch,
        [
            (101, "T20天正建筑 V10.0 - [Drawing1.dwg]", 7, "acad.exe"),
            (102, "", 7, "acad.exe"),
        ],
    )

    assert chosen == 101
    assert recorder.warnings == []


def test_find_window_warns_for_multiple_titled_dwg_process_windows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen, recorder = _find_window(
        monkeypatch,
        [
            (201, "AutoCAD - [First.dwg]", 8, "acad.exe"),
            (202, "T20天正建筑 - [Second.dwg]", 9, "acad.exe"),
            (203, "", 8, "acad.exe"),
        ],
    )

    assert chosen == 201
    assert recorder.warnings == [
        (
            "multiple_autocad_windows",
            {
                "count": 2,
                "used_process_match": True,
                "chose_dwg_title": True,
                "chosen_hwnd": 201,
            },
        )
    ]


def test_find_window_falls_back_to_untitled_process_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen, recorder = _find_window(
        monkeypatch,
        [(301, "", 10, "acad.exe")],
    )

    assert chosen == 301
    assert recorder.warnings == []


def test_find_window_keeps_title_only_match_ahead_of_untitled_process_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chosen, recorder = _find_window(
        monkeypatch,
        [
            (401, "", 11, "acad.exe"),
            (402, "T20天正建筑 - [Fallback.dwg]", 12, "launcher.exe"),
        ],
    )

    assert chosen == 402
    assert recorder.warnings == []
