"""离线测试: 门窗参数面板强结构指纹与受控工具栏消息。"""

from __future__ import annotations

import win32gui

import t20_mcp.dialog_automation as da


class _FakeUser32:
    def __init__(self, button_count: int = 24, *, post_ok: bool = True) -> None:
        self.button_count = button_count
        self.post_ok = post_ok
        self.messages: list[tuple[int, int, int, int]] = []

    def SendMessageW(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        if message == da.TB_BUTTONCOUNT:
            return self.button_count
        return 0

    def PostMessageW(self, hwnd: int, message: int, wparam: int, lparam: int) -> int:
        self.messages.append((hwnd, message, wparam, lparam))
        return int(self.post_ok)


def _patch_opening_toolbar(
    monkeypatch,
    *,
    button_count: int = 24,
    rect: tuple[int, int, int, int] = (1, 116, 637, 143),
    post_ok: bool = True,
) -> _FakeUser32:
    fake_user32 = _FakeUser32(button_count, post_ok=post_ok)
    monkeypatch.setattr(da, "_user32", fake_user32)
    monkeypatch.setattr(da, "all_descendants", lambda _panel: [20])
    monkeypatch.setattr(
        win32gui,
        "GetClassName",
        lambda hwnd: "#32770" if hwnd == 10 else "ToolbarWindow32",
    )
    monkeypatch.setattr(
        win32gui,
        "GetWindowText",
        lambda hwnd: da.OPENING_PANEL_TITLE if hwnd == 10 else "",
    )
    monkeypatch.setattr(win32gui, "IsWindowVisible", lambda _hwnd: True)
    monkeypatch.setattr(win32gui, "GetDlgCtrlID", lambda hwnd: 134 if hwnd == 20 else 0)
    monkeypatch.setattr(win32gui, "GetWindowRect", lambda _hwnd: rect)
    return fake_user32


def test_locate_opening_toolbar_accepts_exact_fingerprint(monkeypatch) -> None:
    _patch_opening_toolbar(monkeypatch)
    assert da.locate_opening_toolbar(10) == 20


def test_locate_opening_toolbar_rejects_button_count_drift(monkeypatch) -> None:
    _patch_opening_toolbar(monkeypatch, button_count=23)
    assert da.locate_opening_toolbar(10) is None


def test_locate_opening_toolbar_rejects_size_drift(monkeypatch) -> None:
    _patch_opening_toolbar(monkeypatch, rect=(1, 116, 801, 150))
    assert da.locate_opening_toolbar(10) is None


def test_click_opening_window_posts_toolbar_client_messages(monkeypatch) -> None:
    fake_user32 = _patch_opening_toolbar(monkeypatch)
    assert da.click_opening_mode(10, "window") == "mode-clicked"

    lparam = (12 << 16) | 372
    assert fake_user32.messages == [
        (20, da.WM_LBUTTONDOWN, da.MK_LBUTTON, lparam),
        (20, da.WM_LBUTTONUP, 0, lparam),
    ]


def test_click_opening_mode_rejects_unknown_mode_without_click(monkeypatch) -> None:
    fake_user32 = _patch_opening_toolbar(monkeypatch)
    assert da.click_opening_mode(10, "skylight") == "unsupported-mode:skylight"
    assert fake_user32.messages == []


def test_click_opening_mode_reports_post_failure(monkeypatch) -> None:
    fake_user32 = _patch_opening_toolbar(monkeypatch, post_ok=False)
    assert da.click_opening_mode(10, "door") == "mode-click-failed"
    assert len(fake_user32.messages) == 2
