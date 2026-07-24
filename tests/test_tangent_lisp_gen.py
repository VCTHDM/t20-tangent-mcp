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
    EXECUTE_DISABLED_SUBCOMMANDS,
    LOW_CONFIDENCE_SUBCOMMANDS,
    LOW_CONFIDENCE_WARNINGS,
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
    "wall_thickness_dimension": {"p1_x": 1500, "p1_y": -500, "p2_x": 1500, "p2_y": 500},
    "opening_dimension": {"p1_x": -200, "p1_y": 600, "p2_x": 3200, "p2_y": 600},
    "two_point_dimension": {"p1_x": -1000, "p1_y": 0, "p2_x": 7000, "p2_y": 0, "pos_x": 3000, "pos_y": 1500},
    "elevation": {"base_x": 0, "base_y": 0, "label_x": 1000, "label_y": 1000, "text": "3.000"},
    "coordinate": {"point_x": 1234, "point_y": 5678, "label_x": 1234, "label_y": 6678},
    "symmetry": {"x1": 0, "y1": 0, "x2": 0, "y2": 3000},
    "line_pattern": {"x1": 0, "y1": 0, "x2": 3000, "y2": 0},
    "north_arrow": {"pos_x": 0, "pos_y": 0, "dir_x": 0, "dir_y": 1000},
    "break_line": {"x1": 0, "y1": 0, "x2": 3000, "y2": 0},
    "section_symbol": {"x1": 0, "y1": 0, "x2": 3000, "y2": 0, "dir_x": 1500, "dir_y": -1000},
    "drawing_name": {"ins_x": 0, "ins_y": 0, "name_text": "一层平面图", "scale_text": "1:100"},
    "rectangle": {"x1": 0, "y1": 0, "x2": 3000, "y2": 2000},
    "balcony": {"points": [[0, 0], [3000, 0], [3000, 1500], [0, 1500]]},
    "step": {"points": [[0, 0], [3000, 0], [3000, 600], [0, 600]]},
    "ramp": {"x": 0, "y": 0},
    "arrow": {"x1": 0, "y1": 0, "x2": 2000, "y2": 0, "text": "见详图", "text2": "1:20"},
    "column": {"x": 20000, "y": 15000, "height": 3300, "rotation": 45,
               "sec_w": 500, "sec_h": 400, "material": "钢筋砼"},
    "rect_roof": {"x1": 0, "y1": 0, "x2": 6000, "y2": 0, "x3": 6000, "y3": 4000},
    "cusp_roof": {"center_x": 3000, "center_y": 3000, "base_x": 6000, "base_y": 3000},
    "insight": {"x": 0, "y": 0},
    "tree": {"x": 0, "y": 0},
    "line_stair": {"x": 0, "y": 0},
    "arc_stair": {"x": 0, "y": 0},
    "double_stair": {"x": 0, "y": 0},
    "multi_stair": {"x1": 0, "y1": 0, "x2": 0, "y2": 6000},
    "wheelchair_diameter": {"center_x": 0, "center_y": 0, "edge_x": 1500, "edge_y": 0},
    "explode_read": {"handle": "1a3f", "offset_x": 1_000_000, "offset_y": 1_000_000},
    "search_room": {"layer": "SPACE"},
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


class TestDispatchInvariants:
    def test_warning_map_references_known_subcommands(self) -> None:
        subcommands = set(SUBCOMMANDS)
        assert set(LOW_CONFIDENCE_SUBCOMMANDS) <= subcommands
        assert set(LOW_CONFIDENCE_WARNINGS) <= subcommands

    def test_low_confidence_warning_keys_match_subcommands(self) -> None:
        assert set(LOW_CONFIDENCE_WARNINGS) == set(LOW_CONFIDENCE_SUBCOMMANDS)

    def test_execute_disabled_frozen(self) -> None:
        assert EXECUTE_DISABLED_SUBCOMMANDS == {}


# ---------------------------------------------------------------------------
# 参数注入正确性
# ---------------------------------------------------------------------------


class TestParamInjection:
    def test_axis_lines_injects_spacings_and_base(self) -> None:
        # axis_lines 使用 LINE 段而非 t20mcp:pt 点序列
        # (历史名 test_axis_grid_*: axis_grid 子命令已在 slimming 提交 441e890 中移除,
        #  当前仅保留 axis_lines 普通 LINE 轴网替代路径)
        code = generate_lisp("axis_lines", {
            "base_x": 100, "base_y": 200,
            "hspacings": [3000, 3600], "vspacings": [4500],
            "angle": 30, "layer": "AXIS",
        })
        assert '"_.-LAYER" "_M" "AXIS"' in code
        assert '"LINE"' in code
        assert "list" in code  # LINE 段用 (list x1 y1 x2 y2) 形式
        assert "3000 3600" not in code  # axis_lines 不用间距字符串
        assert "{{" not in _strip_line_comments(code)

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

    def test_wall_thickness_dimension_uses_tdimwall_two_points(self) -> None:
        code = generate_lisp("wall_thickness_dimension", {
            "p1_x": 1500, "p1_y": -500, "p2_x": 1500, "p2_y": 500,
        })
        assert '"TDIMWALL"' in code
        assert "t20mcp:pt 1500 -500" in code
        assert "t20mcp:pt 1500 500" in code

    def test_opening_templates_enforce_panel_mode_group71(self) -> None:
        door = generate_lisp("door", {"ins_x": 1500, "ins_y": 0})
        window = generate_lisp("window", {"ins_x": 3000, "ins_y": 0})
        assert "(= t20mcp:actual-mode 0)" in door
        assert "(= t20mcp:actual-mode 1)" in window
        assert "T20MCP-OPENING-MODE-MISMATCH" in door
        assert "vla-delete" in door

    def test_opening_dimension_uses_tdim3_line_select(self) -> None:
        code = generate_lisp("opening_dimension", {
            "p1_x": -200, "p1_y": 600, "p2_x": 3200, "p2_y": 600,
        })
        assert '"TDIM3"' in code
        assert "t20mcp:pt -200 600" in code
        assert "t20mcp:pt 3200 600" in code

    def test_two_point_dimension_uses_tdimtp_sequence(self) -> None:
        code = generate_lisp("two_point_dimension", {
            "p1_x": -1000, "p1_y": 0,
            "p2_x": 7000, "p2_y": 0,
            "pos_x": 3000, "pos_y": 1500,
        })
        assert '"TDIMTP"' in code
        p1 = code.index("t20mcp:pt -1000 0")
        p2 = code.index("t20mcp:pt 7000 0")
        pos = code.index("t20mcp:pt 3000 1500")
        done = code.index('""', pos)
        assert p1 < p2 < pos < done
        assert "TCH_DIM*" in code

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

    def test_coordinate_uses_tcoord_two_points(self) -> None:
        # TCoord 真机试验: 标注点 -> 坐标标注方向点 -> 回车, 生成 TCH_COORD。
        code = generate_lisp("coordinate", {
            "point_x": 1234, "point_y": 5678, "label_x": 1234, "label_y": 6678,
        })
        assert '"TCOORD"' in code
        point = code.index("t20mcp:pt 1234 5678")
        label = code.index("t20mcp:pt 1234 6678")
        done = code.index('""', label)
        assert point < label < done
        assert "TCH_COORD" in code

    def test_symmetry_uses_tsymmetry_two_points(self) -> None:
        # TSymmetry 真机试验: 起点 -> 终点, 两点收尾, 生成 TCH_SYMMETRY。
        code = generate_lisp("symmetry", {"x1": 0, "y1": 0, "x2": 0, "y2": 3000})
        assert '"TSYMMETRY"' in code
        assert code.index("t20mcp:pt 0 0") < code.index("t20mcp:pt 0 3000")
        assert "TCH_SYMMETRY" in code

    def test_line_pattern_uses_tlinepattern_with_double_enter(self) -> None:
        code = generate_lisp("line_pattern", {"x1": 0, "y1": 0, "x2": 3000, "y2": 0})
        assert '"TLINEPATTERN"' in code
        p1 = code.index("t20mcp:pt 0 0")
        p2 = code.index("t20mcp:pt 3000 0")
        d1 = code.index('""', p2)
        d2 = code.index('""', d1 + 2)
        assert p1 < p2 < d1 < d2
        assert '(t20mcp:pt 3000 0)\n                     ""\n                     "")' in code
        assert "TCH_PATH_ARRAY" in code

    def test_north_arrow_uses_tnorththumb_two_points(self) -> None:
        # TNorthThumb 真机试验: 位置点 -> 方向点, 两点收尾, 生成 TCH_NORTHTHUMB。
        code = generate_lisp("north_arrow", {"pos_x": 0, "pos_y": 0, "dir_x": 0, "dir_y": 1000})
        assert '"TNORTHTHUMB"' in code
        assert code.index("t20mcp:pt 0 0") < code.index("t20mcp:pt 0 1000")
        assert "TCH_NORTHTHUMB" in code

    def test_north_arrow_default_direction_is_north(self) -> None:
        # 缺省方向点应为位置点正上方 1000mm (北向)
        code = generate_lisp("north_arrow", {"pos_x": 500, "pos_y": 500})
        assert "t20mcp:pt 500 1500" in code

    def test_break_line_uses_tsymbcut_with_trailing_enter(self) -> None:
        # TSymbCut 真机试验: 起点 -> 终点 -> 回车 (接受<不切割>), 生成 TCH_RUPTURE。
        code = generate_lisp("break_line", {"x1": 0, "y1": 0, "x2": 3000, "y2": 0})
        assert '"TSYMBCUT"' in code
        x1 = code.index("t20mcp:pt 0 0")
        x2 = code.index("t20mcp:pt 3000 0")
        done = code.index('""', x2)
        assert x1 < x2 < done
        assert "TCH_RUPTURE" in code

    def test_section_symbol_uses_tsection_three_points(self) -> None:
        # TSection 真机试验: 第一剖切点 -> 第二剖切点 -> 剖视方向 -> 回车, 生成 TCH_SYMB_SECTION。
        code = generate_lisp("section_symbol", {
            "x1": 0, "y1": 0, "x2": 3000, "y2": 0, "dir_x": 1500, "dir_y": -1000,
        })
        assert '"TSECTION"' in code
        p1 = code.index("t20mcp:pt 0 0")
        p2 = code.index("t20mcp:pt 3000 0")
        d = code.index("t20mcp:pt 1500 -1000")
        done = code.index('""', d)
        assert p1 < p2 < d < done
        assert "TCH_SYMB_SECTION" in code

    def test_section_symbol_default_direction_below_midpoint(self) -> None:
        # 缺省剖视方向取剖切线中点向下偏移 1000mm
        code = generate_lisp("section_symbol", {"x1": 0, "y1": 0, "x2": 2000, "y2": 0})
        assert "t20mcp:pt 1000 -1000" in code

    def test_drawing_name_uses_tdrawingname_with_trailing_enter(self) -> None:
        # TDrawingName 真机试验: 插入位置 -> 回车退出循环, 生成 TCH_DRAWINGNAME。
        code = generate_lisp("drawing_name", {"ins_x": 1234, "ins_y": 5678})
        assert '"TDRAWINGNAME"' in code
        ins = code.index("t20mcp:pt 1234 5678")
        assert code.index('""', ins) > ins
        assert "TCH_DRAWINGNAME" in code

    def test_rectangle_uses_trect_two_corners(self) -> None:
        # TRect 真机试验: 第一角点 -> 第二角点 -> 回车, 生成 TCH_RECT。
        code = generate_lisp("rectangle", {"x1": 0, "y1": 0, "x2": 3000, "y2": 2000})
        assert '"TRECT"' in code
        c1 = code.index("t20mcp:pt 0 0")
        c2 = code.index("t20mcp:pt 3000 2000")
        done = code.index('""', c2)
        assert c1 < c2 < done
        assert "TCH_RECT" in code

    def test_balcony_emits_point_list_and_trailing_enter(self) -> None:
        # TBalcony 真机试验: 各轮廓点 -> 回车, 生成 TCH_BALCONY。
        code = generate_lisp("balcony", {"points": [[0, 0], [3000, 0], [3000, 1500]]})
        assert '"TBALCONY"' in code
        p0 = code.index("t20mcp:pt 0 0")
        p1 = code.index("t20mcp:pt 3000 0")
        p2 = code.index("t20mcp:pt 3000 1500")
        assert p0 < p1 < p2 < code.index('""', p2)
        assert "TCH_BALCONY" in code

    def test_step_emits_point_list(self) -> None:
        code = generate_lisp("step", {"points": [[0, 0], [3000, 0]]})
        assert '"TSTEP"' in code
        assert "t20mcp:pt 0 0" in code and "t20mcp:pt 3000 0" in code
        assert "TCH_STEP" in code

    def test_ramp_uses_tascent_single_point_with_trailing_enter(self) -> None:
        # TAscent 真机试验: 点取位置 -> 回车退出循环, 生成 TCH_ASCENT。
        code = generate_lisp("ramp", {"x": 1500, "y": 800})
        assert '"TASCENT"' in code
        pt = code.index("t20mcp:pt 1500 800")
        assert pt < code.index('""', pt)
        assert "TCH_ASCENT" in code

    def test_arrow_uses_tarrow_two_points_with_double_enter(self) -> None:
        # TArrow 真机试验: 起点 -> 终点 -> 回车 -> 回车, 生成 TCH_ARROW。
        code = generate_lisp("arrow", {"x1": 0, "y1": 0, "x2": 2000, "y2": 0})
        assert '"TARROW"' in code
        p1 = code.index("t20mcp:pt 0 0")
        p2 = code.index("t20mcp:pt 2000 0")
        # 两个相邻空回车: 结束本引线循环 + 退出外层循环
        d1 = code.index('""', p2)
        d2 = code.index('""', d1 + 2)
        assert p1 < p2 < d1 < d2
        assert "TCH_ARROW" in code

    # --- 标注文本 COM 注入 (Handoff 35: itest_40 真机验证可写) ---

    def test_drawing_name_injects_nametext_and_scaletext(self) -> None:
        code = generate_lisp("drawing_name", {
            "ins_x": 0, "ins_y": 0, "name_text": "一层平面图", "scale_text": "1:50",
        })
        assert '(list t20mcp:obj "NameText" "一层平面图")' in code
        assert '(list t20mcp:obj "ScaleText" "1:50")' in code
        assert "vlax-put-property" in code

    def test_drawing_name_without_text_params_has_no_injection(self) -> None:
        code = generate_lisp("drawing_name", {"ins_x": 0, "ins_y": 0})
        assert "vlax-put-property" not in code

    def test_arrow_injects_text_and_text2(self) -> None:
        code = generate_lisp("arrow", {
            "x1": 0, "y1": 0, "x2": 2000, "y2": 0, "text": "做法见详图", "text2": "1:20",
        })
        assert '(list t20mcp:obj "Text" "做法见详图")' in code
        assert '(list t20mcp:obj "Text2" "1:20")' in code

    def test_arrow_without_text_params_has_no_injection(self) -> None:
        code = generate_lisp("arrow", {"x1": 0, "y1": 0, "x2": 2000, "y2": 0})
        assert "vlax-put-property" not in code

    def test_elevation_injects_text_override(self) -> None:
        code = generate_lisp("elevation", {"base_x": 0, "base_y": 0, "text": "3.000"})
        assert '(list t20mcp:obj "Text" "3.000")' in code

    def test_elevation_without_text_keeps_auto_value(self) -> None:
        code = generate_lisp("elevation", {"base_x": 0, "base_y": 0})
        assert "vlax-put-property" not in code

    # --- column: 面板 UI 驱动 (Handoff 36) ---

    def test_column_launch_lisp_only_starts_tgcolumn(self) -> None:
        # column 的 LISP 仅是启动片段 (面板填参/插入点在 Python 侧 execute_column);
        # 不得包含 t20mcp:pt 点序列 (Handoff 13/33: vl-cmdf 点注入对面板命令无效)。
        code = generate_lisp("column", VALID_CASES["column"])
        assert '"TGCOLUMN"' in code
        launch_seg = code.rsplit("(progn", 1)[-1]  # 末段 = 启动 progn
        assert "t20mcp:pt" not in launch_seg
        assert is_paren_balanced(code)

    def test_column_minimal_params_accepted(self) -> None:
        # 只给 x/y, 其余走面板记忆值
        code = generate_lisp("column", {"x": 0, "y": 0})
        assert '"TGCOLUMN"' in code

    def test_column_missing_xy_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("column", {"y": 0, "height": 3000})
        with pytest.raises(ParamError):
            generate_lisp("column", {"x": 0, "height": 3000})

    def test_column_bad_material_rejected(self) -> None:
        with pytest.raises(ParamError, match="material"):
            generate_lisp("column", {"x": 0, "y": 0, "material": "木头"})
        with pytest.raises(ParamError, match="material"):
            generate_lisp("column", {"x": 0, "y": 0, "material": 123})

    @pytest.mark.parametrize("field,value", [
        ("height", 0), ("height", 200_000),
        ("rotation", 361), ("rotation", -361),
        ("sec_w", 0), ("sec_w", 50_000),
        ("sec_h", 0),
    ])
    def test_column_out_of_range_rejected(self, field: str, value: float) -> None:
        with pytest.raises(ParamError):
            generate_lisp("column", {"x": 0, "y": 0, field: value})

    def test_label_text_quotes_are_escaped(self) -> None:
        # 文本内的双引号必须转义, 不能逃逸出 LISP 字符串字面量。
        code = generate_lisp("arrow", {
            "x1": 0, "y1": 0, "x2": 2000, "y2": 0, "text": '打"引号"的文字',
        })
        assert '\\"引号\\"' in code
        assert is_paren_balanced(code)

    def test_rect_roof_uses_trectroof_three_corners_with_trailing_enter(self) -> None:
        # TRectRoof 真机试验: 左下 -> 右下 -> 右上 -> 回车, 生成 TCH_MOUNTROOF。
        code = generate_lisp(
            "rect_roof", {"x1": 0, "y1": 0, "x2": 6000, "y2": 0, "x3": 6000, "y3": 4000}
        )
        assert '"TRECTROOF"' in code
        p1 = code.index("t20mcp:pt 0 0")
        p2 = code.index("t20mcp:pt 6000 0")
        p3 = code.index("t20mcp:pt 6000 4000")
        assert p1 < p2 < p3 < code.index('""', p3)
        assert "TCH_MOUNTROOF" in code

    def test_cusp_roof_uses_tcusproof_center_and_radius_point(self) -> None:
        # TCuspRoof 真机试验: 中心 -> 第二点, 两点即收尾, 生成 TCH_CUSPROOF。
        code = generate_lisp("cusp_roof", {"center_x": 3000, "center_y": 3000})
        assert '"TCUSPROOF"' in code
        c = code.index("t20mcp:pt 3000 3000")
        # 缺省半径点为中心右侧 3000mm
        assert code.index("t20mcp:pt 6000 3000") > c
        assert "TCH_CUSPROOF" in code

    def test_insight_uses_tinsight_single_point_with_trailing_enter(self) -> None:
        # TInsight 真机试验: 标注位置点 -> 回车退出循环, 生成 TCH_TDBINSIGHT。
        code = generate_lisp("insight", {"x": 1500, "y": 800})
        assert '"TINSIGHT"' in code
        pt = code.index("t20mcp:pt 1500 800")
        assert pt < code.index('""', pt)
        assert "TCH_TDBINSIGHT" in code

    def test_tree_uses_tsingletree_single_point_inserts_block(self) -> None:
        # TSingleTree 真机试验: 插入点 -> 回车退出循环, 插入 INSERT 图块。
        code = generate_lisp("tree", {"x": 1500, "y": 800})
        assert '"TSINGLETREE"' in code
        pt = code.index("t20mcp:pt 1500 800")
        assert pt < code.index('""', pt)
        assert '"INSERT"' in code

    def test_line_stair_uses_tlstair_single_point_with_trailing_enter(self) -> None:
        # TLStair 真机试验: 点取位置 -> 回车退出循环, 生成 TCH_LINESTAIR。
        code = generate_lisp("line_stair", {"x": 1500, "y": 800})
        assert '"TLSTAIR"' in code
        pt = code.index("t20mcp:pt 1500 800")
        assert pt < code.index('""', pt)
        assert "TCH_LINESTAIR" in code

    def test_arc_stair_uses_tastair_single_point_with_trailing_enter(self) -> None:
        # TAStair 真机试验: 点取位置 -> 回车退出循环, 生成 TCH_ARCSTAIR。
        code = generate_lisp("arc_stair", {"x": 1500, "y": 800})
        assert '"TASTAIR"' in code
        pt = code.index("t20mcp:pt 1500 800")
        assert pt < code.index('""', pt)
        assert "TCH_ARCSTAIR" in code

    def test_wheelchair_diameter_uses_twheelchairdaim_two_points(self) -> None:
        code = generate_lisp("wheelchair_diameter", {"center_x": 0, "center_y": 0})
        assert '"TWHEELCHAIRDAIM"' in code
        center = code.index("t20mcp:pt 0 0")
        edge = code.index("t20mcp:pt 1500 0")
        done = code.index('""', edge)
        assert center < edge < done
        assert "TCH_RADIUSDIM" in code

    def test_wheelchair_diameter_accepts_explicit_edge_point(self) -> None:
        code = generate_lisp(
            "wheelchair_diameter",
            {"center_x": 100, "center_y": 200, "edge_x": 800, "edge_y": 900},
        )
        center = code.index("t20mcp:pt 100 200")
        edge = code.index("t20mcp:pt 800 900")
        done = code.index('""', edge)
        assert center < edge < done
        assert "t20mcp:pt 1600 200" not in code

    def test_wheelchair_diameter_accepts_partial_edge_defaults(self) -> None:
        code = generate_lisp(
            "wheelchair_diameter",
            {"center_x": 100, "center_y": 200, "edge_y": 900},
        )
        assert "t20mcp:pt 100 200" in code
        assert "t20mcp:pt 1600 900" in code

        code = generate_lisp(
            "wheelchair_diameter",
            {"center_x": 100, "center_y": 200, "edge_x": 800},
        )
        assert "t20mcp:pt 100 200" in code
        assert "t20mcp:pt 800 200" in code

    def test_float_formatting_is_compact(self) -> None:
        # 整数值不应带小数点; 小数值应保留
        code = generate_lisp("door", {"ins_x": 1500.0, "ins_y": 0, "width": 912.5, "height": 2100})
        assert "t20mcp:pt 1500 0" in code  # 1500.0 -> 1500
        assert "912.5" in code             # 保留小数

    def test_no_layer_means_no_layer_command(self) -> None:
        code = generate_lisp("door", {"ins_x": 1500, "ins_y": 0})
        assert "_.-LAYER" not in code

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

    @pytest.mark.parametrize("operation", ["wall_thickness_dimension", "opening_dimension", "two_point_dimension"])
    def test_two_point_dimension_coincident_points_rejected(self, operation: str) -> None:
        with pytest.raises(ParamError):
            generate_lisp(operation, {"p1_x": 1, "p1_y": 1, "p2_x": 1, "p2_y": 1})

    def test_elevation_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("elevation", {
                "base_x": 1, "base_y": 1, "label_x": 1, "label_y": 1,
            })

    def test_coordinate_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("coordinate", {
                "point_x": 1, "point_y": 1, "label_x": 1, "label_y": 1,
            })

    def test_symmetry_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("symmetry", {"x1": 1, "y1": 1, "x2": 1, "y2": 1})

    def test_line_pattern_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("line_pattern", {"x1": 1, "y1": 1, "x2": 1, "y2": 1})

    def test_north_arrow_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("north_arrow", {"pos_x": 1, "pos_y": 1, "dir_x": 1, "dir_y": 1})

    def test_break_line_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("break_line", {"x1": 1, "y1": 1, "x2": 1, "y2": 1})

    def test_section_symbol_coincident_cut_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("section_symbol", {"x1": 1, "y1": 1, "x2": 1, "y2": 1})

    def test_drawing_name_missing_coord_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("drawing_name", {"ins_x": 0})  # 缺 ins_y

    def test_rectangle_zero_area_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("rectangle", {"x1": 0, "y1": 0, "x2": 0, "y2": 2000})  # 同一垂直线
        with pytest.raises(ParamError):
            generate_lisp("rectangle", {"x1": 0, "y1": 5, "x2": 3000, "y2": 5})  # 同一水平线

    def test_ramp_missing_coord_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("ramp", {"x": 0})  # 缺 y

    def test_arrow_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("arrow", {"x1": 5, "y1": 5, "x2": 5, "y2": 5})

    @pytest.mark.parametrize("bad_text", [
        "",                 # 空字符串
        "x" * 101,          # 超长 (LABEL_TEXT_MAX=100)
        "换\n行",           # 控制字符
        "带\U0001f600表情",  # GBK 无法编码 (emoji)
        123,                # 非字符串
    ])
    def test_label_text_invalid_rejected(self, bad_text) -> None:
        with pytest.raises(ParamError):
            generate_lisp("arrow", {"x1": 0, "y1": 0, "x2": 2000, "y2": 0, "text": bad_text})
        with pytest.raises(ParamError):
            generate_lisp("drawing_name", {"ins_x": 0, "ins_y": 0, "name_text": bad_text})
        with pytest.raises(ParamError):
            generate_lisp("elevation", {"base_x": 0, "base_y": 0, "text": bad_text})

    def test_rect_roof_coincident_corners_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp(
                "rect_roof", {"x1": 0, "y1": 0, "x2": 0, "y2": 0, "x3": 6000, "y3": 4000}
            )

    def test_cusp_roof_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp(
                "cusp_roof", {"center_x": 1, "center_y": 1, "base_x": 1, "base_y": 1}
            )

    def test_insight_missing_coord_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("insight", {"x": 0})  # 缺 y

    def test_tree_missing_coord_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("tree", {"y": 0})  # 缺 x

    def test_line_stair_missing_coord_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("line_stair", {"x": 0})  # 缺 y

    def test_arc_stair_missing_coord_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("arc_stair", {"y": 0})  # 缺 x

    def test_wheelchair_diameter_coincident_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp(
                "wheelchair_diameter",
                {"center_x": 1, "center_y": 1, "edge_x": 1, "edge_y": 1},
            )

    def test_balcony_too_few_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("balcony", {"points": [[0, 0]]})

    def test_step_bad_point_shape_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("step", {"points": [[0, 0], [3000]]})  # 第二点不是 [x, y]

    def test_balcony_coincident_adjacent_points_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("balcony", {"points": [[0, 0], [0, 0], [3000, 0]]})

    def test_balcony_points_not_list_rejected(self) -> None:
        with pytest.raises(ParamError):
            generate_lisp("balcony", {"points": "0,0 3000,0"})

    def test_axis_lines_empty_spacings_rejected(self) -> None:
        # axis_lines: 至少各保留一段间距, 否则 ParamError 来自参数校验层
        with pytest.raises(ParamError):
            generate_lisp("axis_lines", {"hspacings": [], "vspacings": [3000]})

    def test_removed_axis_grid_subcommand_rejected(self) -> None:
        # axis_grid 已在 slimming 提交 441e890 中移除, 应作为 unknown subcommand 拒绝;
        # 这里同时覆盖 column / export_t3 两个同批移除的子命令, 防止意外回归。
        for removed in ("axis_grid", "column", "export_t3"):
            with pytest.raises(ParamError):
                generate_lisp(removed, {})

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


# ---------------------------------------------------------------------------
# explode_read 专项
# ---------------------------------------------------------------------------


class TestExplodeRead:
    def test_render_injects_params(self) -> None:
        code = generate_lisp("explode_read", {"handle": "1a3f"})
        assert is_paren_balanced(code)
        assert "{{" not in _strip_line_comments(code)
        assert '(handent "1A3F")' in code  # handle 统一大写注入
        assert "TEXPLODE" in code

    def test_bad_handle_rejected(self) -> None:
        for bad in (None, "", "XYZ-1", "1A3G", 42, "(princ)"):
            with pytest.raises(ParamError):
                generate_lisp("explode_read", {"handle": bad})

    def test_small_offset_rejected(self) -> None:
        # 副本太靠近既有实体会触发天正「处理重合的墙体」对话框 (itest_23 教训)
        with pytest.raises(ParamError, match="偏移"):
            generate_lisp("explode_read", {"handle": "1F", "offset_x": 0, "offset_y": 0})

    def test_max_entities_validated(self) -> None:
        for bad in (0, -1, 2001, True, "10"):
            with pytest.raises(ParamError):
                generate_lisp("explode_read", {"handle": "1F", "max_entities": bad})

    def test_parse_payload_roundtrip(self) -> None:
        payload = (
            "rc=T clean=T n=2 data="
            "LINE|1000100.0,1000200.0|1003100.0,1000200.0;"
            "ARC|1000100.0,1000200.0|40=60.0|50=0.0|51=1.5707963;"
        )
        out = tangent.parse_explode_payload(payload, 1_000_000.0, 1_000_000.0)
        assert out["rc"] is True and out["clean"] is True and out["count"] == 2
        line, arc = out["entities"]
        assert line["type"] == "LINE"
        assert line["points"] == [[100.0, 200.0], [3100.0, 200.0]]
        assert arc["props"]["40"] == 60.0 and arc["props"]["51"] == 1.5707963

    def test_parse_payload_empty_and_malformed(self) -> None:
        out = tangent.parse_explode_payload("", 0.0, 0.0)
        assert out == {"rc": False, "clean": False, "count": 0, "entities": []}
        out = tangent.parse_explode_payload("rc=nil clean=nil n=0 data=", 0.0, 0.0)
        assert out["rc"] is False and out["entities"] == []

    def test_text_entity_preserved(self) -> None:
        payload = "rc=T clean=T n=1 data=TEXT|1000010.0,1000020.0|40=350.0|s=砖墙;"
        out = tangent.parse_explode_payload(payload, 1_000_000.0, 1_000_000.0)
        ent = out["entities"][0]
        assert ent["text"] == "砖墙"
        assert ent["points"] == [[10.0, 20.0]]


class TestDialogAutomationWhitelist:
    def test_forbidden_button_refused(self) -> None:
        import asyncio

        from t20_mcp.dialog_automation import click_dialog_buttons

        result = asyncio.run(
            click_dialog_buttons("分解对象", ("分解本图所有天正对象", "确定"), timeout=0.1)
        )
        assert result == "forbidden:分解本图所有天正对象"

    def test_empty_buttons_refused(self) -> None:
        import asyncio

        from t20_mcp.dialog_automation import click_dialog_buttons

        result = asyncio.run(click_dialog_buttons("分解对象", (), timeout=0.1))
        assert result == "no-buttons-specified"

    def test_texplode_sequence_is_whitelisted(self) -> None:
        from t20_mcp.dialog_automation import (
            FORBIDDEN_BUTTONS,
            TEXPLODE_BUTTONS,
            TEXPLODE_DIALOG_TITLE,
        )

        assert TEXPLODE_DIALOG_TITLE == "分解对象"
        assert not (set(TEXPLODE_BUTTONS) & FORBIDDEN_BUTTONS)
