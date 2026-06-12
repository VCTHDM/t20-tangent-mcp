"""离线测试: tangent 子命令的 LISP 生成。

不连接 AutoCAD / 天正, 仅断言:
  1. 生成的 LISP 字符串括号平衡 (含字符串/注释内括号的正确忽略)。
  2. 参数被正确注入到 LISP 文本中。
  3. 非法参数 (类型错误 / 越界 / 缺失 / 注入逃逸) 被拒绝 (抛 ParamError)。

运行: ``uv run pytest tests/test_tangent_lisp_gen.py``
"""

from __future__ import annotations

import pytest

import t20_mcp.tools.tangent as tangent
from t20_mcp.tools.tangent import (
    ParamError,
    SUBCOMMANDS,
    _render,
    _strip_line_comments,
    generate_lisp,
    is_paren_balanced,
)

# ---------------------------------------------------------------------------
# 各子命令的一组合法参数 (用于通用性质测试)
# ---------------------------------------------------------------------------

VALID_CASES: dict[str, dict] = {
    "axis_grid": {
        "base_x": 0,
        "base_y": 0,
        "hspacings": [3000, 3600, 3000],
        "vspacings": [4500, 4500],
        "angle": 0,
        "layer": "AXIS",
    },
    "axis_lines": {
        "base_x": 0,
        "base_y": 0,
        "hspacings": [3000, 3600, 3000],
        "vspacings": [4500, 4500],
        "angle": 0,
        "layer": "AXIS",
    },
    "wall": {
        "x1": 0, "y1": 0, "x2": 6000, "y2": 0,
        "left_width": 120, "right_width": 120, "height": 3000,
        "wall_type": "砖墙", "layer": "WALL",
    },
    "door": {"ins_x": 1500, "ins_y": 0, "width": 900, "height": 2100},
    "window": {"ins_x": 3000, "ins_y": 0, "width": 1500, "height": 1500, "sill_height": 900},
    "dimension": {"p1_x": 0, "p1_y": 0, "p2_x": 6000, "p2_y": 0},
    "elevation": {"base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000},
    "export_t3": {"out_path": "C:/temp/out_t3.dwg", "target_ver": "t3"},
}


# ---------------------------------------------------------------------------
# is_paren_balanced 自身的单元测试
# ---------------------------------------------------------------------------


class TestParenBalance:
    @pytest.mark.parametrize("code", [
        "(a (b c) d)",
        "()",
        "",
        '(princ "())(")',          # 括号在字符串内, 应忽略
        "(setq x 1) ; (注释里的括号)",  # 括号在注释内, 应忽略
        '(strcat "he said \\"(\\"")',  # 转义引号
    ])
    def test_balanced(self, code: str) -> None:
        assert is_paren_balanced(code) is True

    @pytest.mark.parametrize("code", [
        "(a (b c) d",   # 缺右括号
        "(a)) ",        # 多右括号
        ")(",           # 顺序错误
        '(princ "未闭合字符串)',  # 字符串未闭合
    ])
    def test_unbalanced(self, code: str) -> None:
        assert is_paren_balanced(code) is False


# ---------------------------------------------------------------------------
# 通用性质: 所有子命令在合法参数下生成平衡的 LISP
# ---------------------------------------------------------------------------


class TestAllSubcommandsGenerateBalanced:
    def test_subcommand_set(self) -> None:
        assert set(SUBCOMMANDS) == set(VALID_CASES)

    @pytest.mark.parametrize("sub", SUBCOMMANDS)
    def test_generates_balanced_lisp(self, sub: str) -> None:
        code = generate_lisp(sub, VALID_CASES[sub])
        assert is_paren_balanced(code), f"{sub} 生成的 LISP 括号不平衡"
        # 应是可加载的 defun + 调用结构
        assert "defun" in code
        # OK 标记由 prelude 的 t20mcp:end 打印
        assert "T20MCP-OK" in code
        # 模板已迁移到 prelude 骨架: 含 t20mcp:begin, 不含裸 setvar (P0-4)
        assert "t20mcp:begin" in code
        assert 'setvar "CMDDIA"' not in code
        # 无残留占位符 (注释里的 {{TOKEN}} 说明文字除外)
        assert "{{" not in _strip_line_comments(code)

    def test_unknown_subcommand_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("nonexistent", {})

    def test_block_comment_template_rejected(self) -> None:
        # P2-2: 含 ;| ... |; 块注释的模板渲染时被明确拒绝 (is_paren_balanced 不识别)。
        tangent._TEMPLATE_CACHE["_fake_block"] = "(princ) ;| 块注释里的 ( |;\n"
        try:
            with pytest.raises(ParamError, match="块注释"):
                _render("_fake_block", {})
        finally:
            tangent._TEMPLATE_CACHE.pop("_fake_block", None)


# ---------------------------------------------------------------------------
# 参数注入正确性
# ---------------------------------------------------------------------------


class TestParamInjection:
    def test_axis_grid_injects_spacings_and_base(self) -> None:
        code = generate_lisp("axis_grid", {
            "base_x": 100, "base_y": 200,
            "hspacings": [3000, 3600], "vspacings": [4500],
            "angle": 30, "layer": "AXIS",
        })
        assert "t20mcp:pt 100 200" in code       # 基点 (经 t20mcp:pt 转命令行点)
        assert "3000 3600" in code               # 开间序列
        assert "4500" in code                    # 进深序列
        assert '"30"' in code                    # 旋转角
        assert '"_.-LAYER" "_M" "AXIS"' in code  # 图层注入

    def test_axis_lines_injects_line_segments(self) -> None:
        code = generate_lisp("axis_lines", {
            "base_x": 100, "base_y": 200,
            "hspacings": [3000], "vspacings": [4500],
            "angle": 0, "layer": "AXIS",
        })
        assert '"LINE"' in code
        assert "(list 100 200 100 4700)" in code
        assert "(list 3100 200 3100 4700)" in code
        assert "(list 100 200 3100 200)" in code
        assert "(list 100 4700 3100 4700)" in code
        assert "{{" not in _strip_line_comments(code)

    def test_axis_lines_applies_rotation(self) -> None:
        code = generate_lisp("axis_lines", {
            "base_x": 0, "base_y": 0,
            "hspacings": [1000], "vspacings": [1000],
            "angle": 90,
        })
        assert "(list 0 0 -1000 0)" in code
        assert "(list 0 1000 -1000 1000)" in code

    def test_wall_injects_endpoints_and_widths(self) -> None:
        # 真机验证后的 wall 路线: TGWALL 两点画墙 + ActiveX 属性注入宽/高
        code = generate_lisp("wall", {
            "x1": 0, "y1": 0, "x2": 6000, "y2": 1200,
            "left_width": 100, "right_width": 140, "height": 2900,
        })
        assert "t20mcp:pt 0 0" in code
        assert "t20mcp:pt 6000 1200" in code
        assert '"TGWALL"' in code
        assert '(cons "LeftWidth" (float 100))' in code
        assert '(cons "RightWidth" (float 140))' in code
        assert '(cons "Height" (float 2900))' in code

    def test_dimension_uses_tdimmp_pos_first(self) -> None:
        # 真机验证: TDIMMP, 顺序 = 尺寸线位置点 -> 点1 -> 点2 -> 回车
        code = generate_lisp("dimension", {
            "p1_x": 0, "p1_y": 0, "p2_x": 6000, "p2_y": 0,
            "pos_x": 3000, "pos_y": 1000,
        })
        assert '"TDIMMP"' in code
        pos = code.index("t20mcp:pt 3000 1000")
        p1 = code.index("t20mcp:pt 0 0")
        assert pos < p1  # 位置点在标注点之前

    def test_elevation_uses_tmelev_two_points(self) -> None:
        # TMElev 真机试验: 双点序列可生成 TCH_ELEVATION; 单点序列会挂起等待输入。
        code = generate_lisp("elevation", {
            "base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000,
        })
        assert '"TMELEV"' in code
        base = code.index("t20mcp:pt 0 0")
        label = code.index("t20mcp:pt 1000 1000")
        assert base < label
        assert '"")' in code

    def test_float_formatting_is_compact(self) -> None:
        # 整数值不应带小数点; 小数值应保留
        code = generate_lisp("door", {"ins_x": 1500.0, "ins_y": 0, "width": 912.5, "height": 2100})
        assert "t20mcp:pt 1500 0" in code  # 1500.0 -> 1500
        assert "912.5" in code             # 保留小数

    def test_no_layer_means_no_layer_command(self) -> None:
        code = generate_lisp("door", {"ins_x": 1500, "ins_y": 0})
        assert "_.-LAYER" not in code

    def test_export_t3_injects_path_and_version(self) -> None:
        code = generate_lisp("export_t3", {"out_path": "D:/dwg/proj.dwg", "target_ver": "天正3"})
        assert "D:/dwg/proj.dwg" in code
        assert '"3"' in code

    def test_string_escaping_keeps_balance(self) -> None:
        # 含引号的内容应被转义且不破坏括号平衡 (反斜杠路径见 P2-3 归一化测试)
        code = generate_lisp("export_t3", {"out_path": 'C:/a/b"c.dwg'})
        assert is_paren_balanced(code)
        assert '\\"c.dwg' in code          # 引号被转义

    def test_export_path_backslash_normalized_to_slash(self) -> None:
        # P2-3: 反斜杠路径在渲染产物中应统一为正斜杠
        code = generate_lisp("export_t3", {"out_path": "C:\\dwg\\proj.dwg"})
        assert "C:/dwg/proj.dwg" in code
        assert "C:\\dwg" not in code

    def test_layer_name_injection_balanced(self) -> None:
        # 图层名含特殊字符不应破坏平衡
        code = generate_lisp("wall", {
            "x1": 0, "y1": 0, "x2": 1000, "y2": 0,
            "layer": 'WALL"X',
        })
        assert is_paren_balanced(code)


# ---------------------------------------------------------------------------
# 非法参数拒绝
# ---------------------------------------------------------------------------


class TestInvalidParamsRejected:
    def test_missing_required_coord(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("wall", {"x1": 0, "y1": 0, "x2": 1000})  # 缺 y2

    def test_string_where_number_expected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("door", {"ins_x": "abc", "ins_y": 0})

    def test_bool_rejected_as_number(self) -> None:
        # bool 是 int 子类, 必须被显式拒绝
        with pytest.raises(ParamError):
            generate_lisp("door", {"ins_x": True, "ins_y": 0})

    def test_nan_and_inf_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("door", {"ins_x": float("nan"), "ins_y": 0})
        with pytest.raises(ParamError):
            generate_lisp("door", {"ins_x": float("inf"), "ins_y": 0})

    def test_coord_out_of_range(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("door", {"ins_x": 1e12, "ins_y": 0})

    def test_wall_width_out_of_range(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("wall", {"x1": 0, "y1": 0, "x2": 1000, "y2": 0, "left_width": 99999})

    def test_wall_zero_length_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("wall", {"x1": 5, "y1": 5, "x2": 5, "y2": 5})

    def test_dimension_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("dimension", {"p1_x": 1, "p1_y": 1, "p2_x": 1, "p2_y": 1})

    def test_elevation_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("elevation", {
                "base_x": 1, "base_y": 1, "label_x": 1, "label_y": 1,
            })

    def test_axis_grid_empty_spacings_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("axis_grid", {"hspacings": [], "vspacings": [3000]})

    def test_axis_grid_spacings_not_list(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("axis_grid", {"hspacings": "3000", "vspacings": [3000]})

    def test_axis_grid_spacing_value_out_of_range(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("axis_grid", {"hspacings": [0], "vspacings": [3000]})

    def test_axis_grid_too_many_spacings(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("axis_grid", {"hspacings": [3000] * 201, "vspacings": [3000]})

    def test_angle_out_of_range(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("axis_grid", {"hspacings": [3000], "vspacings": [3000], "angle": 999})

    def test_export_t3_bad_extension(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("export_t3", {"out_path": "C:/temp/out.dxf"})

    def test_export_t3_bad_version(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("export_t3", {"out_path": "C:/temp/out.dwg", "target_ver": "t5"})

    def test_export_t3_empty_path(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("export_t3", {"out_path": ""})

    def test_control_char_in_string_rejected(self) -> None:
        # 换行注入企图破坏单行 LISP 字符串 / 命令序列
        with pytest.raises(ParamError):
            generate_lisp("wall", {
                "x1": 0, "y1": 0, "x2": 1000, "y2": 0,
                "layer": "WALL\n(command \"erase\")",
            })

    def test_layer_too_long_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("door", {"ins_x": 0, "ins_y": 0, "layer": "L" * 300})

    def test_non_gbk_layer_rejected_with_field(self) -> None:
        # P1-3: GBK 外字符 (emoji) 应在参数层被拒, 报错含字段名。
        with pytest.raises(ParamError, match="layer"):
            generate_lisp("wall", {
                "x1": 0, "y1": 0, "x2": 1000, "y2": 0, "layer": "测试🔥",
            })

    def test_gbk_chinese_layer_accepted(self) -> None:
        # 常规中文图层名 (GBK 可编码) 不应被误拒。
        code = generate_lisp("wall", {
            "x1": 0, "y1": 0, "x2": 1000, "y2": 0, "layer": "墙体",
        })
        assert "墙体" in code
