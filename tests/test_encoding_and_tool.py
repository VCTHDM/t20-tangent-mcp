"""离线测试: 编码链 (P0-1/P0-2)、dry-run 工具行为 (P0-5)、参数 GBK 校验 (P1-3)。

不连接 AutoCAD / 天正:
  * P0-1: 结果文件 GBK 字节解码无损, cp1252 不再静默放行中文乱码。
  * P0-2: 含中文的模板按 GBK 往返一致; GBK 外字符 (emoji) 被拒并提示 "GBK"。
  * P0-5: 默认 dry-run 不接触 backend (不产生 IPC); execute=True 行为不变;
          低置信子命令返回含 warning。
"""

from __future__ import annotations

import asyncio
import json

import pytest

from t20_mcp.backends.base import CommandResult
from t20_mcp.backends.file_ipc import FileIPCBackend, _decode_result_bytes
from t20_mcp.tools.tangent import generate_lisp


# ---------------------------------------------------------------------------
# P0-1 结果文件解码链 utf-8 -> cp936 -> ... -> cp1252
# ---------------------------------------------------------------------------


class TestDecodeResultBytes:
    def test_gbk_chinese_payload_lossless(self) -> None:
        # 模拟 AutoLISP (write-line) 在中文 Windows 写出的 GBK 结果文件
        data = {"request_id": "abc", "ok": True, "payload": {"层": "墙体", "msg": "砖墙已绘制"}}
        raw = json.dumps(data, ensure_ascii=False).encode("gbk")
        text = _decode_result_bytes(raw, ansi="cp936")
        back = json.loads(text)
        assert back["payload"]["层"] == "墙体"
        assert back["payload"]["msg"] == "砖墙已绘制"

    def test_pure_ascii_not_regressed(self) -> None:
        raw = b'{"request_id": "x", "ok": true, "payload": null}'
        assert json.loads(_decode_result_bytes(raw))["request_id"] == "x"

    def test_gbk_utf8_collision_char_not_mojibaked(self) -> None:
        # 真机E2E回归: "砖" 的 GBK 字节 D7A9 恰是合法 UTF-8 (U+05E9 ש)。
        # ANSI 优先解码链必须解出 "砖" 而非希伯来字母。
        raw = '{"v": "砖"}'.encode("gbk")
        assert json.loads(_decode_result_bytes(raw, ansi="cp936"))["v"] == "砖"

    def test_utf8_fallback_when_ansi_decode_fails(self) -> None:
        # "€" 的 UTF-8 字节 E282AC 不是合法 GBK 序列 → 回退 utf-8 解码。
        raw = '{"v": "€"}'.encode("utf-8")
        assert json.loads(_decode_result_bytes(raw, ansi="cp936"))["v"] == "€"


# ---------------------------------------------------------------------------
# P0-2 LISP 代码以 GBK 写出
# ---------------------------------------------------------------------------


class TestExecuteLispGbk:
    def test_wall_with_chinese_roundtrips_as_gbk(self, tmp_path) -> None:
        # 渲染含 "砖墙" 的 wall 模板, 经 execute_lisp 写盘后以 GBK 读回逐字一致。
        code = generate_lisp("wall", {
            "x1": 0, "y1": 0, "x2": 6000, "y2": 0, "wall_type": "砖墙",
        })
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path

        captured: dict[str, str] = {}

        async def fake_dispatch(command, params):
            captured.update(params)
            return CommandResult(ok=True, payload={})

        backend._dispatch = fake_dispatch  # type: ignore[assignment]
        result = asyncio.run(backend.execute_lisp(code))
        assert result.ok
        written = tmp_path / captured["code_file"].split("/")[-1]
        roundtrip = written.read_bytes().decode("gbk")
        assert "砖墙" in roundtrip
        assert roundtrip == code

    def test_emoji_rejected_with_gbk_hint(self, tmp_path) -> None:
        backend = FileIPCBackend()
        backend._ipc_dir = tmp_path
        result = asyncio.run(backend.execute_lisp('(princ "测试🔥")'))
        assert result.ok is False
        assert "GBK" in (result.error or "")
        assert "🔥" in (result.error or "")
        # 不应写出任何 .lsp 文件
        assert list(tmp_path.glob("*.lsp")) == []


# ---------------------------------------------------------------------------
# P0-5 dry-run 默认开 / execute=True / 低置信 warning
# ---------------------------------------------------------------------------


class _FakeMCP:
    """捕获被注册的 tangent 工具函数。"""

    def __init__(self) -> None:
        self.fn = None

    def tool(self, *args, **kwargs):
        def deco(fn):
            self.fn = fn
            return fn
        return deco


def _register_with_fake_backend(monkeypatch, backend_or_exc):
    """在注册 tangent 工具前替换 client.get_backend, 返回工具函数。"""
    import t20_mcp.client as client

    async def fake_get_backend():
        if isinstance(backend_or_exc, Exception):
            raise backend_or_exc
        return backend_or_exc

    monkeypatch.setattr(client, "get_backend", fake_get_backend)
    from t20_mcp.tools.tangent import register_tangent_tool

    mcp = _FakeMCP()
    register_tangent_tool(mcp)
    assert mcp.fn is not None
    return mcp.fn


class _FakeBackend:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def execute_lisp(self, code: str) -> CommandResult:
        self.calls.append(code)
        return CommandResult(ok=True, payload={"echo": "ok"})


class TestParamsCmdFileEncoding:
    def test_chinese_params_written_as_gbk_not_unicode_escape(self, tmp_path, monkeypatch) -> None:
        # P2-1: 命令文件以 GBK + ensure_ascii=False 写出, 中文不变 \uXXXX。
        import t20_mcp.backends.file_ipc as fip

        monkeypatch.setattr(fip, "TIMEOUT", 0.0)
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._ipc_dir = tmp_path
        backend._autocad_modal_dialog_present = lambda: False  # type: ignore[assignment]

        captured: dict[str, bytes] = {}

        def grab(send_cancel=False):
            for f in tmp_path.glob("t20_mcp_cmd_*.json"):
                captured["raw"] = f.read_bytes()

        backend._type_dispatch_trigger = grab  # type: ignore[assignment]
        asyncio.run(backend._dispatch("layer-create", {"name": "墙体图层"}))

        raw = captured["raw"]
        assert b"\\u" not in raw          # 不是 \uXXXX 转义
        assert "墙体图层" in raw.decode("gbk")


class TestModalDialogGuard:
    def test_blocked_when_modal_present(self) -> None:
        # P1-2: 检测到模态对话框时, dispatch 直接返回阻塞错误, 不发送触发串。
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._autocad_modal_dialog_present = lambda: True  # type: ignore[assignment]
        sent: list[bool] = []
        backend._type_dispatch_trigger = lambda send_cancel=False: sent.append(send_cancel)  # type: ignore[assignment]
        result = asyncio.run(backend._dispatch("ping", {}))
        assert result.ok is False
        assert "对话框" in (result.error or "")
        assert sent == []  # 未发送触发串

    def test_esc_only_after_timeout(self, tmp_path, monkeypatch) -> None:
        # P1-2: 正常首次 dispatch 不注入 ESC; 上次超时后的首次重发才注入。
        import t20_mcp.backends.file_ipc as fip

        monkeypatch.setattr(fip, "TIMEOUT", 0.0)  # 立即超时
        backend = FileIPCBackend()
        backend._hwnd = 1
        backend._ipc_dir = tmp_path
        backend._autocad_modal_dialog_present = lambda: False  # type: ignore[assignment]
        cancels: list[bool] = []
        backend._type_dispatch_trigger = lambda send_cancel=False: cancels.append(send_cancel)  # type: ignore[assignment]

        r1 = asyncio.run(backend._dispatch("ping", {}))  # 超时
        assert r1.ok is False
        r2 = asyncio.run(backend._dispatch("ping", {}))  # 超时后首次重发
        assert r2.ok is False
        assert cancels[0] is False   # 首次不注入 ESC
        assert cancels[1] is True    # 超时后重发注入 ESC


class TestTangentDryRun:
    def test_default_is_dry_run_no_backend(self, monkeypatch) -> None:
        # 默认 execute=False: 即便 get_backend 会抛错, dry-run 也不应触碰它。
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("backend must not be used"))
        out = asyncio.run(fn(operation="wall", data={"x1": 0, "y1": 0, "x2": 6000, "y2": 0}))
        payload = json.loads(out)
        assert payload["dry_run"] is True
        assert payload["executed"] is False
        assert "t20mcp:begin" in payload["lisp"]

    def test_execute_true_runs_backend(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(operation="wall", data={"x1": 0, "y1": 0, "x2": 6000, "y2": 0}, execute=True))
        payload = json.loads(out)
        assert payload["ok"] is True
        assert len(backend.calls) == 1  # 真正下发了一次

    def test_low_confidence_execute_has_warning(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(operation="door", data={"ins_x": 1500, "ins_y": 0}, execute=True))
        payload = json.loads(out)
        assert payload["ok"] is True
        assert "warning" in payload["payload"]

    def test_low_confidence_dry_run_has_warning(self, monkeypatch) -> None:
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("unused"))
        out = asyncio.run(fn(operation="window", data={"ins_x": 1500, "ins_y": 0}))
        payload = json.loads(out)
        assert payload["dry_run"] is True
        assert "warning" in payload

    def test_high_confidence_dry_run_no_warning(self, monkeypatch) -> None:
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("unused"))
        out = asyncio.run(fn(operation="wall", data={"x1": 0, "y1": 0, "x2": 6000, "y2": 0}))
        payload = json.loads(out)
        assert "warning" not in payload

    def test_execute_disabled_subcommand_refused(self, monkeypatch) -> None:
        # 高风险/待复核命令: execute=True 被拒, 不触碰 backend。
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        for op, data in (
            ("axis_grid", {"hspacings": [3000], "vspacings": [3000]}),
            ("export_t3", {"out_path": "C:/temp/out.dwg"}),
        ):
            out = asyncio.run(fn(operation=op, data=data, execute=True))
            payload = json.loads(out)
            assert "execute 已禁用" in payload["error"]
        assert backend.calls == []  # 从未下发

    def test_execute_disabled_subcommand_dry_run_notes_disabled(self, monkeypatch) -> None:
        fn = _register_with_fake_backend(monkeypatch, RuntimeError("unused"))
        out = asyncio.run(fn(operation="export_t3", data={"out_path": "C:/temp/out.dwg"}))
        payload = json.loads(out)
        assert payload["dry_run"] is True
        assert "execute_disabled" in payload

    def test_axis_lines_execute_allowed(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(
            operation="axis_lines",
            data={"hspacings": [3000], "vspacings": [3000]},
            execute=True,
        ))
        payload = json.loads(out)
        assert payload["ok"] is True
        assert len(backend.calls) == 1

    def test_elevation_execute_allowed_with_warning(self, monkeypatch) -> None:
        backend = _FakeBackend()
        fn = _register_with_fake_backend(monkeypatch, backend)
        out = asyncio.run(fn(
            operation="elevation",
            data={"base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000},
            execute=True,
        ))
        payload = json.loads(out)
        assert payload["ok"] is True
        assert "warning" in payload["payload"]
        assert len(backend.calls) == 1
