"""Tangent (天正 T20) consolidated MCP tool — LISP 模板 + 参数注入。

本模块在不改动 dispatcher / IPC 层的前提下, 新增 ``tangent`` 工具, 仿照上游
8 个 consolidated tools 的风格, 通过 ``operation`` (子命令) 分派到各类天正建筑实体。

设计要点 (遵循 PROJECT_RULES.md 铁律):
  * 每个子命令对应 ``lisp_templates/tangent/<name>.lsp`` 模板, 仅做占位符注入,
    绝不在 Python 侧拼接键击序列。
  * 所有参数在注入前完成 **类型 + 取值范围** 校验, 非法参数抛出 ``ParamError``。
  * 生成的 LISP 字符串经过括号平衡自检, 再经现有 ``execute_lisp`` 通道下发。

纯生成逻辑 (``generate_lisp`` / ``is_paren_balanced``) 不依赖 AutoCAD, 可离线测试。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# 模板加载
# ---------------------------------------------------------------------------

_TEMPLATE_DIR: Path = Path(__file__).resolve().parent.parent / "lisp_templates" / "tangent"

_PRELUDE_NAME: str = "_prelude"

_TEMPLATE_CACHE: dict[str, str] = {}


class ParamError(ValueError):
    """参数类型 / 取值范围非法, 或模板渲染未完成时抛出。"""


def _load_template(name: str) -> str:
    """读取并缓存模板文件内容 (仓库内统一 UTF-8 存储)。"""
    if name not in _TEMPLATE_CACHE:
        path = _TEMPLATE_DIR / f"{name}.lsp"
        if not path.is_file():
            raise ParamError(f"模板缺失: {path}")
        _TEMPLATE_CACHE[name] = path.read_text(encoding="utf-8")
    return _TEMPLATE_CACHE[name]


def _load_prelude() -> str:
    """加载防御性前置 (_prelude.lsp): 环境保存/静默/恢复、局部 *error*、UNDO
    回滚、命令存在性预检与 vl-cmdf 防级联。所有 tangent 模板共享这套骨架,
    渲染时拼接在模板之前 (重复加载幂等)。"""
    return _load_template(_PRELUDE_NAME)


# ---------------------------------------------------------------------------
# 取值范围常量 (单位: 毫米 / 度) —— 均为防御性上下限, 真机可再收紧
# ---------------------------------------------------------------------------

COORD_ABS_MAX: float = 1.0e9          # 坐标绝对值上限
WALL_WIDTH_RANGE: tuple[float, float] = (1.0, 2000.0)       # 墙体单侧宽度
HEIGHT_RANGE: tuple[float, float] = (1.0, 100_000.0)        # 墙/门/窗 高度
OPENING_WIDTH_RANGE: tuple[float, float] = (1.0, 20_000.0)  # 门窗洞口宽度
SILL_RANGE: tuple[float, float] = (0.0, 100_000.0)          # 窗台高 / 距墙垛距离
SPACING_RANGE: tuple[float, float] = (1.0, 100_000.0)       # 轴网单段间距
SPACING_COUNT_MAX: int = 200          # 轴网间距段数上限
POINT_LIST_COUNT_MAX: int = 200       # 轮廓点列点数上限 (阳台/台阶等)
ANGLE_RANGE: tuple[float, float] = (-360.0, 360.0)
LAYER_NAME_MAX: int = 255
COLUMN_HEIGHT_RANGE: tuple[float, float] = (1.0, 100_000.0)   # 柱高
COLUMN_SECTION_RANGE: tuple[float, float] = (1.0, 20_000.0)   # 柱截面横向/纵向


# ---------------------------------------------------------------------------
# 基础校验 / 格式化辅助
# ---------------------------------------------------------------------------


def _require_number(value: Any, field: str) -> float:
    """要求是有限实数 (拒绝 bool / None / NaN / inf / 非数字)。"""
    # bool 是 int 子类, 必须显式排除, 避免 True 被当作 1。
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParamError(f"参数 {field} 必须为数字, 实际为 {value!r}")
    fv = float(value)
    if not math.isfinite(fv):
        raise ParamError(f"参数 {field} 必须为有限数, 实际为 {value!r}")
    return fv


def _require_range(value: Any, field: str, lo: float, hi: float) -> float:
    fv = _require_number(value, field)
    if fv < lo or fv > hi:
        raise ParamError(f"参数 {field}={fv:g} 超出允许范围 [{lo:g}, {hi:g}]")
    return fv


def _require_coord(value: Any, field: str) -> float:
    fv = _require_number(value, field)
    if abs(fv) > COORD_ABS_MAX:
        raise ParamError(f"坐标 {field}={fv:g} 超出允许范围 ±{COORD_ABS_MAX:g}")
    return fv


def _require_str(value: Any, field: str, *, max_len: int) -> str:
    if not isinstance(value, str):
        raise ParamError(f"参数 {field} 必须为字符串, 实际为 {value!r}")
    if value == "":
        raise ParamError(f"参数 {field} 不能为空字符串")
    if len(value) > max_len:
        raise ParamError(f"参数 {field} 长度 {len(value)} 超过上限 {max_len}")
    # 控制字符 (换行/制表/回车等) 会破坏 LISP 单行字符串与命令序列。
    if any(ord(ch) < 0x20 for ch in value):
        raise ParamError(f"参数 {field} 含非法控制字符")
    # GBK 可编码校验 (P1-3): 天正/AutoCAD 按 GBK 加载 .lsp, GBK 外字符(emoji、
    # 部分扩展区汉字)会在传输层 errors="strict" 处报错; 这里提前给出带字段名的
    # 友好提示, 作为第一道防线。
    try:
        value.encode("gbk")
    except UnicodeEncodeError as e:
        bad = value[e.start:e.end]
        raise ParamError(
            f"参数 {field} 含 GBK 无法编码的字符 {bad!r} (天正按 GBK 加载, 请避免 emoji/扩展区字符)"
        )
    return value


def _require_spacings(value: Any, field: str) -> list[float]:
    """轴网间距: 非空数字列表, 每段在 SPACING_RANGE 内。"""
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise ParamError(f"参数 {field} 必须为数字列表, 实际为 {value!r}")
    if not value:
        raise ParamError(f"参数 {field} 不能为空列表")
    if len(value) > SPACING_COUNT_MAX:
        raise ParamError(f"参数 {field} 段数 {len(value)} 超过上限 {SPACING_COUNT_MAX}")
    out: list[float] = []
    for i, item in enumerate(value):
        out.append(_require_range(item, f"{field}[{i}]", *SPACING_RANGE))
    return out


def _require_point_list(value: Any, field: str, *, min_points: int = 2) -> list[tuple[float, float]]:
    """轮廓点列: [[x, y], ...]; 至少 min_points 个点, 每点坐标在范围内, 相邻点不重合。"""
    if not isinstance(value, (list, tuple)) or isinstance(value, (str, bytes)):
        raise ParamError(f"参数 {field} 必须为点列表 [[x, y], ...], 实际为 {value!r}")
    if len(value) < min_points:
        raise ParamError(f"参数 {field} 至少需要 {min_points} 个点, 实际 {len(value)}")
    if len(value) > POINT_LIST_COUNT_MAX:
        raise ParamError(f"参数 {field} 点数 {len(value)} 超过上限 {POINT_LIST_COUNT_MAX}")
    out: list[tuple[float, float]] = []
    prev: tuple[float, float] | None = None
    for i, p in enumerate(value):
        if not isinstance(p, (list, tuple)) or isinstance(p, (str, bytes)) or len(p) != 2:
            raise ParamError(f"参数 {field}[{i}] 必须为 [x, y], 实际为 {p!r}")
        x = _require_coord(p[0], f"{field}[{i}].x")
        y = _require_coord(p[1], f"{field}[{i}].y")
        if prev is not None and prev == (x, y):
            raise ParamError(f"参数 {field}[{i}] 与前一点重合")
        out.append((x, y))
        prev = (x, y)
    return out


def _pt_list_lisp(points: list[tuple[float, float]]) -> str:
    """把点列渲染为一串 ``(t20mcp:pt x y)`` 表单 (空格分隔)。"""
    return " ".join(f"(t20mcp:pt {_num(x)} {_num(y)})" for x, y in points)


def _num(value: float) -> str:
    """格式化为紧凑的十进制字面量 (整数不带小数点)。"""
    fv = float(value)
    if fv == int(fv) and abs(fv) < 1e15:
        return str(int(fv))
    return f"{fv:.6f}".rstrip("0").rstrip(".")


def _lisp_escape(text: str) -> str:
    """转义字符串内容, 使其可安全置于 LISP 双引号字面量内部 (不含外层引号)。"""
    return text.replace("\\", "\\\\").replace('"', '\\"')


# 标注类文本参数上限 (drawing_name/arrow/elevation 的 COM 文本注入)。
LABEL_TEXT_MAX: int = 100


def _com_put_text(props: list[tuple[str, str]]) -> str:
    """生成 ``{{COM_INJECT}}`` 占位内容: 逐属性 vlax-put-property 注入文本。

    props 为 (COM 属性名, 已经 _require_str 校验的文本) 列表; 空列表返回空串
    (模板中该占位符所在行留白, 不注入)。Handoff 35 真机验证:
    TDbDrawingName.NameText/ScaleText、TDbSymbArrow.Text/Text2、
    TDbSymbElevation.Text 均可写且读回精确匹配。
    """
    return "\n".join(
        f"        (vl-catch-all-apply 'vlax-put-property"
        f' (list t20mcp:obj "{prop}" "{_lisp_escape(text)}"))'
        for prop, text in props
    )


def _set_layer_cmd(layer: Any) -> str:
    """生成 ``{{SET_LAYER}}`` 占位内容: 设置/新建当前图层, 或空 (不指定图层)。"""
    if layer is None:
        return ""
    name = _require_str(layer, "layer", max_len=LAYER_NAME_MAX)
    return f'  (command "_.-LAYER" "_M" "{_lisp_escape(name)}" "")'


# ---------------------------------------------------------------------------
# 括号平衡自检 (忽略字符串字面量与 ; 行注释)
# ---------------------------------------------------------------------------


def is_paren_balanced(code: str) -> bool:
    """判断 LISP 代码圆括号是否平衡 (字符串与注释内的括号不计)。"""
    depth = 0
    in_string = False
    in_comment = False
    escaped = False
    for ch in code:
        if in_comment:
            if ch == "\n":
                in_comment = False
            continue
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == ";":
            in_comment = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0 and not in_string


def _strip_line_comments(code: str) -> str:
    """把 ``;`` 行注释区域替换为空白 (字符串字面量内的 ``;`` 不算注释)。

    用于残留占位符自检: 模板头注释里合法地写有 ``{{TOKEN}}`` 说明文字,
    不应被误判为未注入占位符; 而字符串字面量内的 ``"{{WIDTH}}"`` 必须仍被检出。
    """
    out: list[str] = []
    in_string = False
    in_comment = False
    escaped = False
    for ch in code:
        if in_comment:
            out.append("\n" if ch == "\n" else " ")
            if ch == "\n":
                in_comment = False
            continue
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
        elif ch == ";":
            in_comment = True
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)


def _render(template_name: str, tokens: dict[str, str]) -> str:
    """加载模板并替换 ``{{TOKEN}}`` 占位符, 拼接 _prelude.lsp 骨架于产物之前,
    校验无残留占位符与括号平衡。

    prelude 提供 t20mcp:begin / on-error / call / end / fail / pt 等函数;
    模板必须长成 _prelude.lsp 文末描述的骨架形态 (局部 *error* + t20mcp:call)。
    传输层会把整体 (prelude + 模板) 一并转码为 GBK 写盘下发。
    """
    body = _load_template(template_name)
    # 模板含 ;| ... |; 块注释会骗过 is_paren_balanced (它只识别 ; 行注释)。
    # prelude 已规范禁止块注释, 这里再加一道 lint 拦截 (P2-2)。
    if ";|" in body:
        raise ParamError(f"模板 {template_name} 含禁止的 ;| |; 块注释")
    for key, val in tokens.items():
        body = body.replace("{{" + key + "}}", val)
    # 残留占位符自检: 忽略注释里的 {{TOKEN}} 说明文字, 字符串内的占位符仍检出。
    if "{{" in _strip_line_comments(body):
        raise ParamError(f"模板 {template_name} 渲染后仍存在未注入占位符")
    code = _load_prelude() + "\n" + body
    if not is_paren_balanced(code):
        raise ParamError(f"模板 {template_name} 渲染后括号不平衡")
    return code


# ---------------------------------------------------------------------------
# 各子命令的 LISP 生成器
# ---------------------------------------------------------------------------


def _gen_axis_lines(data: dict[str, Any]) -> str:
    """普通 LINE 轴线网格。data: {base_x, base_y, hspacings:[...], vspacings:[...], angle?, layer?}"""
    base_x = _require_coord(data.get("base_x", 0.0), "base_x")
    base_y = _require_coord(data.get("base_y", 0.0), "base_y")
    hspacings = _require_spacings(data.get("hspacings"), "hspacings")
    vspacings = _require_spacings(data.get("vspacings"), "vspacings")
    angle = _require_range(data.get("angle", 0.0), "angle", *ANGLE_RANGE)

    xs = [0.0]
    for spacing in hspacings:
        xs.append(xs[-1] + spacing)
    ys = [0.0]
    for spacing in vspacings:
        ys.append(ys[-1] + spacing)

    theta = math.radians(angle)
    cos_a = math.cos(theta)
    sin_a = math.sin(theta)

    def transform(x: float, y: float) -> tuple[float, float]:
        tx = base_x + x * cos_a - y * sin_a
        ty = base_y + x * sin_a + y * cos_a
        return _require_coord(tx, "axis_lines.x"), _require_coord(ty, "axis_lines.y")

    segments: list[tuple[float, float, float, float]] = []
    max_x = xs[-1]
    max_y = ys[-1]
    for x in xs:
        x1, y1 = transform(x, 0.0)
        x2, y2 = transform(x, max_y)
        segments.append((x1, y1, x2, y2))
    for y in ys:
        x1, y1 = transform(0.0, y)
        x2, y2 = transform(max_x, y)
        segments.append((x1, y1, x2, y2))

    segment_code = " ".join(
        f"(list {_num(x1)} {_num(y1)} {_num(x2)} {_num(y2)})"
        for x1, y1, x2, y2 in segments
    )
    return _render(
        "axis_lines",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "SEGMENTS": segment_code,
            "EXPECTED_COUNT": str(len(segments)),
        },
    )


def _gen_wall(data: dict[str, Any]) -> str:
    """单段墙体。data: {x1,y1,x2,y2, left_width?, right_width?, height?, wall_type?, layer?}"""
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("墙体起点与终点不能重合")
    left_width = _require_range(data.get("left_width", 120.0), "left_width", *WALL_WIDTH_RANGE)
    right_width = _require_range(data.get("right_width", 120.0), "right_width", *WALL_WIDTH_RANGE)
    height = _require_range(data.get("height", 3000.0), "height", *HEIGHT_RANGE)
    # wall_type 注入 TCH_WALL 的 Style (墙体材料) 属性; 真机回读默认值为 "砖"。
    wall_type = _require_str(data.get("wall_type", "砖"), "wall_type", max_len=32)
    return _render(
        "wall",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "LEFT_WIDTH": _num(left_width),
            "RIGHT_WIDTH": _num(right_width),
            "HEIGHT": _num(height),
            "WALL_TYPE": _lisp_escape(wall_type),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
        },
    )


def _gen_opening(data: dict[str, Any], mode: str = "door") -> str:
    """门窗 (TOpening)。data: {ins_x, ins_y, width?, height?, sill_distance?|sill_height?, layer?}

    mode="door": 注入 DoorSill (距墙垛距离), 默认宽900高2100。DXF group 71 = 0。
    mode="window": 写 DoorSill 字段承载窗台高 (Handoff 33 真机证实 TCH_OPENING 不暴露
      独立 SillHeight 属性, 门/窗共用 DoorSill, 模式由面板 + DXF group 71=0/1 决定),
      默认宽1500高1500台高900。创建后校验 group71；面板模式不符时删除错误实体，
      返回结构化重试信息，不允许把错误类型伪装成目标类型。
    """
    ins_x = _require_coord(data.get("ins_x"), "ins_x")
    ins_y = _require_coord(data.get("ins_y"), "ins_y")
    # TOPENING 忽略 CLAYER, 总是把 TCH_OPENING 放到 WINDOW 图层。
    # 创建后用 vla-put-Layer 强制修正: 门->DOOR_FIRE, 窗->WINDOW (或用户指定层)。
    if data.get("layer"):
        _target_layer = str(data["layer"])
    elif mode == "door":
        _target_layer = "DOOR_FIRE"
    else:
        _target_layer = "WINDOW"
    _layer_fix = (
        f'\n        (vl-catch-all-apply '
        f"'vlax-put-property (list t20mcp:obj \"Layer\" \"{_lisp_escape(_target_layer)}\")) "
    )
    if mode == "door":
        width = _require_range(data.get("width", 900.0), "width", *OPENING_WIDTH_RANGE)
        height = _require_range(data.get("height", 2100.0), "height", *HEIGHT_RANGE)
        sill = _require_range(data.get("sill_distance", 0.0), "sill_distance", *SILL_RANGE)
        com = (
            f'(foreach pv (list (cons "Width" (float {_num(width)}))'
            f' (cons "Height" (float {_num(height)}))'
            f' (cons "DoorSill" (float {_num(sill)})))\n'
            f'           (vl-catch-all-apply \'vlax-put-property (list t20mcp:obj (car pv) (cdr pv))))'
            + _layer_fix
        )
    else:
        width = _require_range(data.get("width", 1500.0), "width", *OPENING_WIDTH_RANGE)
        height = _require_range(data.get("height", 1500.0), "height", *HEIGHT_RANGE)
        sill = _require_range(data.get("sill_height", 900.0), "sill_height", *SILL_RANGE)
        # Handoff 33 真机证据 (itest_35 + COM 属性枚举):
        # TCH_OPENING 在窗模式下不暴露 SillHeight 属性 (ERR 未知名称),
        # 门/窗 共用 DoorSill — 模式由 DXF group 71 (0=门, 1=窗) + 面板模式决定。
        # 因此窗模式注入仍写 DoorSill, 但语义上代表"窗台高 (sill_height)"。
        com = (
            f'(foreach pv (list (cons "Width" (float {_num(width)}))'
            f' (cons "Height" (float {_num(height)}))'
            f' (cons "DoorSill" (float {_num(sill)})))\n'
            f'           (vl-catch-all-apply \'vlax-put-property (list t20mcp:obj (car pv) (cdr pv))))'
            + _layer_fix
        )
    return _render(
        "opening",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "MODE": mode,
            "EXPECTED_GROUP71": "0" if mode == "door" else "1",
            "INS_X": _num(ins_x),
            "INS_Y": _num(ins_y),
            "COM_INJECT": com,
        },
    )


def _gen_door(data: dict[str, Any]) -> str:
    return _gen_opening(data, "door")


def _gen_window(data: dict[str, Any]) -> str:
    return _gen_opening(data, "window")


def _gen_dimension(data: dict[str, Any]) -> str:
    """逐点标注 (两点)。data: {p1_x,p1_y,p2_x,p2_y, pos_x?, pos_y?, layer?}"""
    p1_x = _require_coord(data.get("p1_x"), "p1_x")
    p1_y = _require_coord(data.get("p1_y"), "p1_y")
    p2_x = _require_coord(data.get("p2_x"), "p2_x")
    p2_y = _require_coord(data.get("p2_y"), "p2_y")
    if p1_x == p2_x and p1_y == p2_y:
        raise ParamError("标注两点不能重合")
    # 尺寸线位置: 缺省取两点中点上方 1000mm, 仍走坐标校验
    pos_x = _require_coord(data.get("pos_x", (p1_x + p2_x) / 2.0), "pos_x")
    pos_y = _require_coord(data.get("pos_y", (p1_y + p2_y) / 2.0 + 1000.0), "pos_y")
    return _render(
        "dimension",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "POS_X": _num(pos_x),
            "POS_Y": _num(pos_y),
            "P1_X": _num(p1_x),
            "P1_Y": _num(p1_y),
            "P2_X": _num(p2_x),
            "P2_Y": _num(p2_y),
        },
    )


def _gen_wall_thickness_dimension(data: dict[str, Any]) -> str:
    """墙厚标注。data: {p1_x,p1_y,p2_x,p2_y,layer?}"""
    p1_x = _require_coord(data.get("p1_x"), "p1_x")
    p1_y = _require_coord(data.get("p1_y"), "p1_y")
    p2_x = _require_coord(data.get("p2_x"), "p2_x")
    p2_y = _require_coord(data.get("p2_y"), "p2_y")
    if p1_x == p2_x and p1_y == p2_y:
        raise ParamError("墙厚标注两点不能重合")
    return _render(
        "wall_thickness_dimension",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "P1_X": _num(p1_x),
            "P1_Y": _num(p1_y),
            "P2_X": _num(p2_x),
            "P2_Y": _num(p2_y),
        },
    )


def _gen_opening_dimension(data: dict[str, Any]) -> str:
    """门窗标注。data: {p1_x,p1_y,p2_x,p2_y,layer?}"""
    p1_x = _require_coord(data.get("p1_x"), "p1_x")
    p1_y = _require_coord(data.get("p1_y"), "p1_y")
    p2_x = _require_coord(data.get("p2_x"), "p2_x")
    p2_y = _require_coord(data.get("p2_y"), "p2_y")
    if p1_x == p2_x and p1_y == p2_y:
        raise ParamError("门窗标注线选两点不能重合")
    return _render(
        "opening_dimension",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "P1_X": _num(p1_x),
            "P1_Y": _num(p1_y),
            "P2_X": _num(p2_x),
            "P2_Y": _num(p2_y),
        },
    )


def _gen_two_point_dimension(data: dict[str, Any]) -> str:
    """两点标注 (TDimTP)。data: {p1_x,p1_y,p2_x,p2_y, pos_x?, pos_y?, layer?}

    起点/终点连成穿越线, 标注该线穿过的一排对象 (墙/柱/门窗/轴线) 的间距;
    pos 定尺寸线位置 (缺省取两点中点上方 1000mm)。穿过对象不足会报"对象数目太少"。
    """
    p1_x = _require_coord(data.get("p1_x"), "p1_x")
    p1_y = _require_coord(data.get("p1_y"), "p1_y")
    p2_x = _require_coord(data.get("p2_x"), "p2_x")
    p2_y = _require_coord(data.get("p2_y"), "p2_y")
    if p1_x == p2_x and p1_y == p2_y:
        raise ParamError("两点标注的起点与终点不能重合")
    pos_x = _require_coord(data.get("pos_x", (p1_x + p2_x) / 2.0), "pos_x")
    pos_y = _require_coord(data.get("pos_y", (p1_y + p2_y) / 2.0 + 1000.0), "pos_y")
    return _render(
        "two_point_dimension",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "P1_X": _num(p1_x),
            "P1_Y": _num(p1_y),
            "P2_X": _num(p2_x),
            "P2_Y": _num(p2_y),
            "POS_X": _num(pos_x),
            "POS_Y": _num(pos_y),
        },
    )


def _gen_elevation(data: dict[str, Any]) -> str:
    """标高标注。data: {base_x,base_y,label_x?,label_y?,text?,layer?}

    text (标高文字, 如 "3.000") 经 ActiveX 注入 Text (Handoff 35 真机验证);
    未提供时由天正按基准点自动计算。
    """
    base_x = _require_coord(data.get("base_x"), "base_x")
    base_y = _require_coord(data.get("base_y"), "base_y")
    # TMElev 真机试验中单点序列会挂起等待输入; 缺省给出第二点, 永远双点下发。
    label_x = _require_coord(data.get("label_x", base_x + 1000.0), "label_x")
    label_y = _require_coord(data.get("label_y", base_y + 1000.0), "label_y")
    if base_x == label_x and base_y == label_y:
        raise ParamError("标高基准点与标注放置点不能重合")
    props: list[tuple[str, str]] = []
    if data.get("text") is not None:
        props.append(("Text", _require_str(data["text"], "text", max_len=LABEL_TEXT_MAX)))
    return _render(
        "elevation",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "BASE_X": _num(base_x),
            "BASE_Y": _num(base_y),
            "LABEL_X": _num(label_x),
            "LABEL_Y": _num(label_y),
            "COM_INJECT": _com_put_text(props),
        },
    )


def _gen_coordinate(data: dict[str, Any]) -> str:
    """坐标标注。data: {point_x,point_y,label_x?,label_y?,layer?}

    真机验证序列: 标注点 -> 坐标标注方向点 -> 回车, 生成 TCH_COORD。
    label 点只决定标注方向/放置侧, 缺省为标注点正上方 1000mm。
    """
    point_x = _require_coord(data.get("point_x"), "point_x")
    point_y = _require_coord(data.get("point_y"), "point_y")
    label_x = _require_coord(data.get("label_x", point_x), "label_x")
    label_y = _require_coord(data.get("label_y", point_y + 1000.0), "label_y")
    if point_x == label_x and point_y == label_y:
        raise ParamError("坐标标注点与方向点不能重合")
    return _render(
        "coordinate",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "POINT_X": _num(point_x),
            "POINT_Y": _num(point_y),
            "LABEL_X": _num(label_x),
            "LABEL_Y": _num(label_y),
        },
    )


def _gen_symmetry(data: dict[str, Any]) -> str:
    """画对称轴。data: {x1,y1,x2,y2,layer?}

    真机验证序列: 起点 -> 终点, 两点即收尾 (active=0), 生成 TCH_SYMMETRY。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("对称轴的起点与终点不能重合")
    return _render(
        "symmetry",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
        },
    )


def _gen_line_pattern(data: dict[str, Any]) -> str:
    """线图案。data: {x1,y1,x2,y2,layer?}

    真机验证序列: 起点 -> 终点 -> 回车 -> 回车, 生成 TCH_PATH_ARRAY。
    第二个空回车退出外层循环; 线图案样式走天正面板记忆值。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("线图案的起点与终点不能重合")
    return _render(
        "line_pattern",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
        },
    )


def _gen_north_arrow(data: dict[str, Any]) -> str:
    """画指北针。data: {pos_x,pos_y,dir_x?,dir_y?,layer?}

    真机验证序列: 指北针位置点 -> 方向点, 两点即收尾 (active=0), 生成 TCH_NORTHTHUMB。
    dir 点只决定指北针朝向, 缺省为位置点正上方 1000mm (北向)。
    """
    pos_x = _require_coord(data.get("pos_x"), "pos_x")
    pos_y = _require_coord(data.get("pos_y"), "pos_y")
    dir_x = _require_coord(data.get("dir_x", pos_x), "dir_x")
    dir_y = _require_coord(data.get("dir_y", pos_y + 1000.0), "dir_y")
    if pos_x == dir_x and pos_y == dir_y:
        raise ParamError("指北针位置点与方向点不能重合")
    return _render(
        "north_arrow",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "POS_X": _num(pos_x),
            "POS_Y": _num(pos_y),
            "DIR_X": _num(dir_x),
            "DIR_Y": _num(dir_y),
        },
    )


def _gen_break_line(data: dict[str, Any]) -> str:
    """加折断线 (单折断线)。data: {x1,y1,x2,y2,layer?}

    真机验证序列: 折断线起点 -> 终点 -> 回车 (接受 <不切割> 默认), 生成 TCH_RUPTURE。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("折断线的起点与终点不能重合")
    return _render(
        "break_line",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
        },
    )


def _gen_section_symbol(data: dict[str, Any]) -> str:
    """剖切符号。data: {x1,y1,x2,y2,dir_x?,dir_y?,layer?}

    真机验证序列: 第一剖切点 -> 第二剖切点 -> 剖视方向点 -> 回车退出循环,
    生成 TCH_SYMB_SECTION。剖切编号文字走天正面板记忆值 (只参数化几何)。
    dir 点决定剖视方向, 缺省取剖切线中点向下偏移 1000mm。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("剖切符号的第一、第二剖切点不能重合")
    dir_x = _require_coord(data.get("dir_x", (x1 + x2) / 2.0), "dir_x")
    dir_y = _require_coord(data.get("dir_y", (y1 + y2) / 2.0 - 1000.0), "dir_y")
    return _render(
        "section_symbol",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
            "DIR_X": _num(dir_x),
            "DIR_Y": _num(dir_y),
        },
    )


def _gen_drawing_name(data: dict[str, Any]) -> str:
    """图名标注。data: {ins_x,ins_y,name_text?,scale_text?,layer?}

    真机验证序列: 插入位置点 -> 回车退出循环, 生成 TCH_DRAWINGNAME。
    name_text (图名文字) / scale_text (比例文字, 如 "1:50") 经 ActiveX 注入
    NameText/ScaleText (Handoff 35 真机验证); 未提供时走天正面板记忆值。
    """
    ins_x = _require_coord(data.get("ins_x"), "ins_x")
    ins_y = _require_coord(data.get("ins_y"), "ins_y")
    props: list[tuple[str, str]] = []
    if data.get("name_text") is not None:
        props.append(
            ("NameText", _require_str(data["name_text"], "name_text", max_len=LABEL_TEXT_MAX))
        )
    if data.get("scale_text") is not None:
        props.append(
            ("ScaleText", _require_str(data["scale_text"], "scale_text", max_len=LABEL_TEXT_MAX))
        )
    return _render(
        "drawing_name",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "INS_X": _num(ins_x),
            "INS_Y": _num(ins_y),
            "COM_INJECT": _com_put_text(props),
        },
    )


def _gen_rectangle(data: dict[str, Any]) -> str:
    """矩形 (天正矩形)。data: {x1,y1,x2,y2,layer?}

    真机验证序列: 第一角点 -> 第二角点 -> 回车退出循环, 生成 TCH_RECT。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 or y1 == y2:
        raise ParamError("矩形两角点不能在同一水平或垂直线上 (零面积)")
    return _render(
        "rectangle",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
        },
    )


def _gen_balcony(data: dict[str, Any]) -> str:
    """阳台。data: {points:[[x,y],...] (>=2), layer?}

    真机验证序列: 各轮廓点 -> 回车结束, 生成 TCH_BALCONY。
    阳台类型/挑出宽度走天正面板记忆值, 本工具只参数化轮廓点列。
    """
    points = _require_point_list(data.get("points"), "points", min_points=2)
    return _render(
        "balcony",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "POINTS": _pt_list_lisp(points),
        },
    )


def _gen_step(data: dict[str, Any]) -> str:
    """台阶。data: {points:[[x,y],...] (>=2), layer?}

    真机验证序列: 各轮廓点 -> 回车结束, 生成 TCH_STEP。
    踏步数/宽度走天正面板记忆值, 本工具只参数化轮廓点列。
    """
    points = _require_point_list(data.get("points"), "points", min_points=2)
    return _render(
        "step",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "POINTS": _pt_list_lisp(points),
        },
    )


def _gen_ramp(data: dict[str, Any]) -> str:
    """坡道。data: {x, y, layer?}

    真机验证序列: 点取位置 -> 回车退出循环, 生成 TCH_ASCENT。
    坡道宽度/坡长等构造参数走天正面板记忆值, 本工具只参数化插入点。
    """
    x = _require_coord(data.get("x"), "x")
    y = _require_coord(data.get("y"), "y")
    return _render(
        "ramp",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X": _num(x),
            "Y": _num(y),
        },
    )


def _gen_arrow(data: dict[str, Any]) -> str:
    """箭头引注。data: {x1, y1, x2, y2, text?, text2?, layer?}

    真机验证序列: 箭头起点 -> 直段下一点 -> 回车 -> 回车, 生成 TCH_ARROW。
    text (上标文字) / text2 (下标文字) 经 ActiveX 注入 Text/Text2 (Handoff 35
    真机验证); 未提供时走天正面板记忆值; 箭头样式仍走面板。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("箭头引注的起点与终点不能重合")
    props: list[tuple[str, str]] = []
    if data.get("text") is not None:
        props.append(("Text", _require_str(data["text"], "text", max_len=LABEL_TEXT_MAX)))
    if data.get("text2") is not None:
        props.append(("Text2", _require_str(data["text2"], "text2", max_len=LABEL_TEXT_MAX)))
    return _render(
        "arrow",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
            "COM_INJECT": _com_put_text(props),
        },
    )


def _column_params(data: dict[str, Any]) -> dict[str, Any]:
    """column 参数校验 (面板 UI 驱动路线, Handoff 36)。

    T20 强制把柱落在 COLUMN 图层, 故不提供 layer 参数。
    material 合法值 = dialog_automation.COLUMN_MATERIALS (真机枚举)。
    """
    from t20_mcp.dialog_automation import COLUMN_MATERIALS

    out: dict[str, Any] = {
        "x": _require_coord(data.get("x"), "x"),
        "y": _require_coord(data.get("y"), "y"),
    }
    if data.get("height") is not None:
        out["height"] = _require_range(data["height"], "height", *COLUMN_HEIGHT_RANGE)
    if data.get("rotation") is not None:
        out["rotation"] = _require_range(data["rotation"], "rotation", *ANGLE_RANGE)
    if data.get("sec_w") is not None:
        out["sec_w"] = _require_range(data["sec_w"], "sec_w", *COLUMN_SECTION_RANGE)
    if data.get("sec_h") is not None:
        out["sec_h"] = _require_range(data["sec_h"], "sec_h", *COLUMN_SECTION_RANGE)
    if data.get("material") is not None:
        mat = data["material"]
        if not isinstance(mat, str) or mat not in COLUMN_MATERIALS:
            raise ParamError(
                f"参数 material={mat!r} 非法, 合法值: {list(COLUMN_MATERIALS)}"
            )
        out["material"] = mat
    return out


def _gen_column(data: dict[str, Any]) -> str:
    """标准柱 (面板 UI 驱动)。data: {x, y, height?, material?, rotation?, sec_w?, sec_h?}

    与其它子命令不同, TGColumn 的参数在 #32770 浮动面板上, 无法经 vl-cmdf
    注入 (Handoff 13/33)。本生成器只产出启动 LISP (面板浮起, CMDACTIVE=1);
    面板填参/插入点/ESC 由 Python 侧 execute_column 经 Win32 编排
    (Handoff 36 真机验证)。dry-run 时返回的 LISP 单独执行不会生成柱。
    """
    _column_params(data)  # 仅校验; 面板驱动在 execute_column
    return (
        _load_prelude()
        + '\n(progn (setvar "CMDECHO" 1)'
        ' (vl-catch-all-apply (quote vl-cmdf) (list "TGCOLUMN"))'
        ' (strcat "active=" (itoa (getvar "CMDACTIVE"))))'
    )


# execute_column 的环境复位 (对齐 itest 系列 RESET_ENV)。
_COLUMN_RESET_LISP = (
    '(progn (setq n 0)'
    ' (while (and (< n 8) (> (getvar "CMDACTIVE") 0)) (command) (setq n (1+ n)))'
    ' (setvar "CMDDIA" 1) (setvar "FILEDIA" 1) (setvar "OSMODE" 0)'
    ' (strcat "rst CMDACTIVE=" (itoa (getvar "CMDACTIVE"))))'
)

# TCH_COLUMN 五属性读回 (Handoff 36 dump 确认的属性名)。
_COLUMN_READBACK_LISP = '''
(vl-load-com)
(setq t20mcp:col-o (vlax-ename->vla-object (entlast)))
(strcat
  "type=" (cdr (assoc 0 (entget (entlast))))
  " handle=" (cdr (assoc 5 (entget (entlast))))
  " H=" (vl-prin1-to-string (vl-catch-all-apply 'vlax-get-property (list t20mcp:col-o "Height")))
  " R=" (vl-prin1-to-string (vl-catch-all-apply 'vlax-get-property (list t20mcp:col-o "Rotation")))
  " W=" (vl-prin1-to-string (vl-catch-all-apply 'vlax-get-property (list t20mcp:col-o "Width")))
  " D=" (vl-prin1-to-string (vl-catch-all-apply 'vlax-get-property (list t20mcp:col-o "Deep")))
  " S=" (vl-prin1-to-string (vl-catch-all-apply 'vlax-get-property (list t20mcp:col-o "Style"))))
'''


async def execute_column(backend: Any, data: dict[str, Any]) -> "Any":
    """tangent.column 的真机编排: 启动 TGCOLUMN → Win32 面板填参 → 打插入点
    → ESC 退出 → IPC 读回校验。失败路径撤销增量实体并复位环境。

    返回 CommandResult (延迟导入避免离线测试依赖 backend 栈)。
    """
    import asyncio as _asyncio

    import win32process

    from t20_mcp import dialog_automation as da
    from t20_mcp.backends.base import CommandResult

    params = _column_params(data)
    launch_code = _gen_column(data)

    async def _count() -> int:
        r = await backend.entity_count()
        return r.payload["count"] if r.ok else -1

    async def _rollback(base: int) -> None:
        await _asyncio.sleep(0.5)  # 等 ESC PostMessage 生效, 再走 IPC
        await backend.execute_lisp(_COLUMN_RESET_LISP)
        rounds = 0
        while rounds < 8:
            c = await _count()
            if c <= base or c < 0:
                break
            u = await backend.undo()
            if not u.ok:
                break
            rounds += 1
        await backend.execute_lisp(_COLUMN_RESET_LISP)

    base = await _count()
    _, pid = win32process.GetWindowThreadProcessId(backend._hwnd)
    cmd_hwnd = backend._command_hwnd or backend._hwnd
    exclude = set(da.find_acad_popups(pid))

    launch = await backend.execute_lisp(launch_code)
    if not launch.ok:
        return CommandResult(ok=False, error=f"[tangent.column] 启动 TGCOLUMN 失败: {launch.error}")

    # CMDACTIVE=1 窗口期: 纯 Win32, 禁 IPC (见 dialog_automation 模块 docstring)。
    drive = await da.drive_column_panel(
        pid,
        cmd_hwnd,
        (params["x"], params["y"]),
        height=params.get("height"),
        material=params.get("material"),
        rotation=params.get("rotation"),
        sec_w=params.get("sec_w"),
        sec_h=params.get("sec_h"),
        exclude=exclude,
    )
    if drive != "placed":
        await _rollback(base)
        return CommandResult(ok=False, error=f"[tangent.column] 面板驱动失败: {drive} (已 ESC 回滚)")

    await backend.execute_lisp(_COLUMN_RESET_LISP)
    after = await _count()
    if after != base + 1:
        await _rollback(base)
        return CommandResult(
            ok=False,
            error=f"[tangent.column] 实体增量异常 (delta={after - base}, 期望 +1), 已回滚",
        )

    rb = await backend.execute_lisp(_COLUMN_READBACK_LISP)
    payload_str = str(rb.payload or "")
    if "type=TCH_COLUMN" not in payload_str:
        await _rollback(base)
        return CommandResult(
            ok=False,
            error=f"[tangent.column] 生成实体非 TCH_COLUMN ({payload_str!r}), 已回滚",
        )
    return CommandResult(
        ok=True,
        payload={
            "operation": "column",
            "executed": True,
            "readback": payload_str,
            "requested": params,
        },
    )


def _gen_rect_roof(data: dict[str, Any]) -> str:
    """矩形屋顶。data: {x1,y1,x2,y2,x3,y3, layer?}

    真机验证序列: 左下角点 -> 右下角点 -> 右上角点 -> 回车退出循环, 生成 TCH_MOUNTROOF。
    三角点定屋顶底面矩形 (左下/右下/右上); 坡角/出檐/屋顶高走天正面板记忆值。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    x3 = _require_coord(data.get("x3"), "x3")
    y3 = _require_coord(data.get("y3"), "y3")
    if (x1, y1) == (x2, y2) or (x2, y2) == (x3, y3) or (x1, y1) == (x3, y3):
        raise ParamError("矩形屋顶的三个角点不能有重合")
    return _render(
        "rect_roof",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
            "X3": _num(x3),
            "Y3": _num(y3),
        },
    )


def _gen_cusp_roof(data: dict[str, Any]) -> str:
    """攒尖屋顶。data: {center_x, center_y, base_x?, base_y?, layer?}

    真机验证序列: 屋顶中心位置 -> 第二点(定半径/朝向), 两点即收尾, 生成 TCH_CUSPROOF。
    base 点缺省为中心点正右方 3000mm; 边数/屋顶高走天正面板记忆值。
    """
    center_x = _require_coord(data.get("center_x"), "center_x")
    center_y = _require_coord(data.get("center_y"), "center_y")
    base_x = _require_coord(data.get("base_x", center_x + 3000.0), "base_x")
    base_y = _require_coord(data.get("base_y", center_y), "base_y")
    if center_x == base_x and center_y == base_y:
        raise ParamError("攒尖屋顶的中心点与半径点不能重合")
    return _render(
        "cusp_roof",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "CENTER_X": _num(center_x),
            "CENTER_Y": _num(center_y),
            "BASE_X": _num(base_x),
            "BASE_Y": _num(base_y),
        },
    )


def _gen_insight(data: dict[str, Any]) -> str:
    """内视符号。data: {x, y, layer?}

    真机验证序列: 标注位置点 -> 回车退出循环, 生成 TCH_TDBINSIGHT。
    命令是循环式 (每点一个内视符号); 朝向/编号走天正面板记忆值, 只参数化标注位置。
    """
    x = _require_coord(data.get("x"), "x")
    y = _require_coord(data.get("y"), "y")
    return _render(
        "insight",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X": _num(x),
            "Y": _num(y),
        },
    )


def _gen_tree(data: dict[str, Any]) -> str:
    """任意布树 (单棵)。data: {x, y, layer?}

    真机验证序列: 插入点 -> 回车退出循环, 插入树木图块 (INSERT, 块名形如 "tree1")。
    命令是循环式 (每点一棵); 树种/尺寸走天正面板记忆值, 只参数化插入点。
    """
    x = _require_coord(data.get("x"), "x")
    y = _require_coord(data.get("y"), "y")
    return _render(
        "tree",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X": _num(x),
            "Y": _num(y),
        },
    )


def _gen_line_stair(data: dict[str, Any]) -> str:
    """直线梯段。data: {x, y, layer?}

    真机验证序列: 点取位置 -> 回车退出循环, 生成 TCH_LINESTAIR。
    命令是循环式插入; 梯段宽/踏步数/踏步高走天正面板记忆值, 只参数化插入点。
    """
    x = _require_coord(data.get("x"), "x")
    y = _require_coord(data.get("y"), "y")
    return _render(
        "line_stair",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X": _num(x),
            "Y": _num(y),
        },
    )


def _gen_arc_stair(data: dict[str, Any]) -> str:
    """圆弧梯段。data: {x, y, layer?}

    真机验证序列: 点取位置 -> 回车退出循环, 生成 TCH_ARCSTAIR。
    命令是循环式插入; 内外半径/踏步数/圆心角走天正面板记忆值, 只参数化插入点。
    """
    x = _require_coord(data.get("x"), "x")
    y = _require_coord(data.get("y"), "y")
    return _render(
        "arc_stair",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X": _num(x),
            "Y": _num(y),
        },
    )


def _gen_double_stair(data: dict[str, Any]) -> str:
    """双跑楼梯。data: {x, y, layer?}

    真机验证序列: 插入点 -> 回车退出循环, 生成 TCH_RECTSTAIR。
    命令是循环式插入; 梯段宽/踏步数/楼梯高/井宽走天正面板记忆值, 只参数化插入点。
    """
    x = _require_coord(data.get("x"), "x")
    y = _require_coord(data.get("y"), "y")
    return _render(
        "double_stair",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X": _num(x),
            "Y": _num(y),
        },
    )


def _gen_multi_stair(data: dict[str, Any]) -> str:
    """多跑楼梯。data: {x1,y1,x2,y2,layer?}

    真机验证序列: 起点 -> 下一点 -> 回车退出, 生成 TCH_MULTISTAIR。
    命令循环式 (起点->下一点 定义一跑后回到"起点<退出>", 空回车走 <退出> 收尾);
    跑数/梯段宽/踏步数/楼梯高走天正面板记忆值, 只参数化起点与方向点。
    """
    x1 = _require_coord(data.get("x1"), "x1")
    y1 = _require_coord(data.get("y1"), "y1")
    x2 = _require_coord(data.get("x2"), "x2")
    y2 = _require_coord(data.get("y2"), "y2")
    if x1 == x2 and y1 == y2:
        raise ParamError("多跑楼梯的起点与下一点不能重合")
    return _render(
        "multi_stair",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "X1": _num(x1),
            "Y1": _num(y1),
            "X2": _num(x2),
            "Y2": _num(y2),
        },
    )


def _gen_wheelchair_diameter(data: dict[str, Any]) -> str:
    """轮椅直径。data: {center_x,center_y,edge_x?,edge_y?,layer?}

    真机验证序列: 中心点 -> 半径/方向点 -> 回车, 生成 TCH_RADIUSDIM。
    官方命令拼写为 TWheelchairDaim; edge 点缺省为中心点正右 1500mm。
    """
    center_x = _require_coord(data.get("center_x"), "center_x")
    center_y = _require_coord(data.get("center_y"), "center_y")
    edge_x = _require_coord(data.get("edge_x", center_x + 1500.0), "edge_x")
    edge_y = _require_coord(data.get("edge_y", center_y), "edge_y")
    if center_x == edge_x and center_y == edge_y:
        raise ParamError("轮椅直径的中心点与半径/方向点不能重合")
    return _render(
        "wheelchair_diameter",
        {
            "SET_LAYER": _set_layer_cmd(data.get("layer")),
            "CENTER_X": _num(center_x),
            "CENTER_Y": _num(center_y),
            "EDGE_X": _num(edge_x),
            "EDGE_Y": _num(edge_y),
        },
    )


def _gen_search_room(data: dict[str, Any]) -> str:
    """搜索房间。data: {layer?}

    全图选择 TCH_WALL 后驱动 TUPDSPACE, 闭合墙体围合区域生成 TCH_SPACE
    (itest_26 真机验证: 选择集 + 回车序列, 一轮成功)。
    """
    return _render("search_room", {"SET_LAYER": _set_layer_cmd(data.get("layer"))})


EXPLODE_OFFSET_MIN: float = 100_000.0   # 副本暂存区最小偏移 (防重合墙对话框)
EXPLODE_MAX_ENTITIES_RANGE: tuple[int, int] = (1, 2000)


def _gen_explode_read(data: dict[str, Any]) -> str:
    """天正实体几何读回。data: {handle, offset_x?, offset_y?, max_entities?}

    副本分解管线 (itest_23/24 真机验证): COPY 到远处暂存区 → TEXPLODE 仅
    分解副本 → 序列化产物几何 → UNDO 回滚。execute 路径必须由调用方并发
    驱动「分解对象」对话框 (dialog_automation.drive_texplode_dialog)。
    """
    handle = data.get("handle")
    if (
        not isinstance(handle, str)
        or not handle
        or any(c not in "0123456789abcdefABCDEF" for c in handle)
    ):
        raise ParamError(
            f"参数 handle 必须为十六进制实体句柄字符串 (可经 entity 工具获取), 实际为 {handle!r}"
        )
    off_x = _require_coord(data.get("offset_x", 1_000_000.0), "offset_x")
    off_y = _require_coord(data.get("offset_y", 1_000_000.0), "offset_y")
    if max(abs(off_x), abs(off_y)) < EXPLODE_OFFSET_MIN:
        raise ParamError(
            f"暂存区偏移过小 (max(|offset_x|,|offset_y|) ≥ {EXPLODE_OFFSET_MIN:g}): "
            "副本太靠近既有实体会触发天正「处理重合的墙体」模态对话框"
        )
    max_entities = data.get("max_entities", 200)
    lo, hi = EXPLODE_MAX_ENTITIES_RANGE
    if isinstance(max_entities, bool) or not isinstance(max_entities, int) or not (
        lo <= max_entities <= hi
    ):
        raise ParamError(f"参数 max_entities 必须为 {lo}..{hi} 的整数, 实际为 {max_entities!r}")
    return _render(
        "explode_read",
        {
            "HANDLE": handle.upper(),
            "OFF_X": _num(off_x),
            "OFF_Y": _num(off_y),
            "MAX_ENTITIES": str(max_entities),
        },
    )


def parse_explode_payload(payload: str, off_x: float, off_y: float) -> dict[str, Any]:
    """解析 explode_read 模板返回串, 并把坐标平移回原位 (减去暂存偏移)。

    输入形如: ``rc=T clean=T n=4 data=LINE|x,y|x,y;LINE|...;``
    输出: {rc, clean, count, entities:[{type, points:[[x,y]..], props:{..}, text?}]}
    """
    text = payload or ""
    head, sep, body = text.partition(" data=")
    flags: dict[str, str] = {}
    for token in head.split():
        k, eq, v = token.partition("=")
        if eq:
            flags[k] = v
    entities: list[dict[str, Any]] = []
    if sep:
        for item in body.split(";"):
            if not item:
                continue
            parts = item.split("|")
            ent: dict[str, Any] = {"type": parts[0], "points": [], "props": {}}
            for tok in parts[1:]:
                if tok.startswith("s="):
                    ent["text"] = tok[2:]
                elif "=" in tok:
                    k, _, v = tok.partition("=")
                    try:
                        ent["props"][k] = float(v)
                    except ValueError:
                        ent["props"][k] = v
                elif "," in tok:
                    xs, _, ys = tok.partition(",")
                    try:
                        ent["points"].append(
                            [float(xs) - off_x, float(ys) - off_y]
                        )
                    except ValueError:
                        pass
            entities.append(ent)
    return {
        "rc": flags.get("rc") == "T",
        "clean": flags.get("clean") == "T",
        "count": int(flags.get("n", "0") or 0),
        "entities": entities,
    }


# 子命令 -> 生成器 映射
_GENERATORS: dict[str, Callable[[dict[str, Any]], str]] = {
    "axis_lines": _gen_axis_lines,
    "wall": _gen_wall,
    "door": _gen_door,
    "window": _gen_window,
    "dimension": _gen_dimension,
    "wall_thickness_dimension": _gen_wall_thickness_dimension,
    "opening_dimension": _gen_opening_dimension,
    "two_point_dimension": _gen_two_point_dimension,
    "elevation": _gen_elevation,
    "coordinate": _gen_coordinate,
    "symmetry": _gen_symmetry,
    "line_pattern": _gen_line_pattern,
    "north_arrow": _gen_north_arrow,
    "break_line": _gen_break_line,
    "section_symbol": _gen_section_symbol,
    "drawing_name": _gen_drawing_name,
    "rectangle": _gen_rectangle,
    "balcony": _gen_balcony,
    "step": _gen_step,
    "ramp": _gen_ramp,
    "arrow": _gen_arrow,
    "column": _gen_column,
    "rect_roof": _gen_rect_roof,
    "cusp_roof": _gen_cusp_roof,
    "insight": _gen_insight,
    "tree": _gen_tree,
    "line_stair": _gen_line_stair,
    "arc_stair": _gen_arc_stair,
    "double_stair": _gen_double_stair,
    "multi_stair": _gen_multi_stair,
    "wheelchair_diameter": _gen_wheelchair_diameter,
    "explode_read": _gen_explode_read,
    "search_room": _gen_search_room,
}

SUBCOMMANDS: tuple[str, ...] = tuple(_GENERATORS)

# 真机部分验证的子命令 (2026-06-12, T20 V10 / AutoCAD 2024):
# execute=True 下发时附 warning。
LOW_CONFIDENCE_WARNINGS: dict[str, str] = {
    "dimension": (
        "dimension 调用天正 TDIMMP 逐点标注，会按墙体、门窗和洞口节点重新吸附，"
        "不保证结果等于 p1/p2 的直线距离；不要用于建筑总宽/总高。需要严格按两个"
        "坐标标注时，请调用 annotation.create_dimension_linear。"
    ),
    "door": (
        "door 会先通过门窗参数面板自动切到门模式，再创建并校验 DXF group71=0。"
        "最终 group71 门禁仍是权威证据；若自动切换未生效，错误实体会被删除并返回"
        "结构化失败，不会把窗伪装成门。"
    ),
    "window": (
        "window 会先通过门窗参数面板自动切到窗模式，再创建并校验 DXF group71=1。"
        "最终 group71 门禁仍是权威证据；若自动切换未生效，错误实体会被删除并返回"
        "结构化失败。窗台高通过 DoorSill 字段写入。"
    ),
    "elevation": (
        "TMElev 已验证双点序列可生成 TCH_ELEVATION; "
        "不要改成单点序列, 点不足曾导致 IPC 超时并触发 AutoCAD 闪退事故。"
        "text 参数经 COM 注入 Text 覆盖标高文字 (Handoff 35 真机验证); "
        "未提供时由天正按基准点自动计算"
    ),
    "drawing_name": (
        "name_text/scale_text 参数经 COM 注入 NameText/ScaleText, Handoff 35 真机"
        "写入+读回验证; 未提供这两个参数时图名/比例取天正面板记忆值。"
        "字体样式/字高仍走面板, 不可参数化。"
    ),
    "arrow": (
        "text/text2 参数经 COM 注入 Text(上标)/Text2(下标), Handoff 35 真机"
        "写入+读回验证; 未提供时引注文字取天正面板记忆值。"
        "箭头样式/大小仍走面板, 不可参数化。"
    ),
    "column": (
        "column 走面板 UI 自动化 (Handoff 36: WM_SETTEXT 填参 + 命令行打插入点), "
        "五参数 (height/rotation/sec_w/sec_h/material) 经 COM 读回精确匹配验证; "
        "需要 AutoCAD 图形界面会话; 若 T20 版本升级导致面板控件变化, 驱动会"
        "安全失败并 ESC 回滚, 不留残留。dry-run 返回的 LISP 仅为启动片段, "
        "单独执行不生成柱。柱形状固定为面板当前 tab (默认矩形), 图层由 T20 "
        "强制为 COLUMN。"
    ),
}

LOW_CONFIDENCE_SUBCOMMANDS: frozenset[str] = frozenset(LOW_CONFIDENCE_WARNINGS)


def parse_opening_status(payload: object) -> dict[str, str]:
    """解析 opening.lsp 返回的单行状态协议。"""
    text = str(payload or "").strip().strip('"')
    if not text.startswith("T20MCP-OPENING-"):
        return {}
    parts = text.split("|")
    status = {"status": parts[0].removeprefix("T20MCP-OPENING-")}
    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            status[key] = value
    return status


def _gen_opening_mode_launch() -> str:
    """只启动 TOpening 并让门窗参数面板浮起, 不输入插入点。"""
    return (
        _load_prelude()
        + '\n(progn (setvar "CMDECHO" 1)'
        ' (vl-catch-all-apply (quote vl-cmdf) (list "TOpening"))'
        ' (strcat "active=" (itoa (getvar "CMDACTIVE"))))'
    )


async def execute_opening(
    backend: Any,
    operation: str,
    data: dict[str, Any],
) -> "Any":
    """门/窗真机编排: 启动面板 → 自动切模式 → 空回车退出 → 正式创建。

    面板切换期间 CMDACTIVE=1, 因此只用 Win32 消息, 不走 IPC。随后仍执行
    opening.lsp 的 group71 硬门禁；UI 自动化只是前置动作, 不是成功依据。
    无 Win32 HWND 的测试/替代 backend 保留原来的直接执行路径。
    """
    from t20_mcp.backends.base import CommandResult

    code = generate_lisp(operation, data)
    hwnd = getattr(backend, "_hwnd", None)
    cmd_hwnd = getattr(backend, "_command_hwnd", None)
    if not hwnd or not cmd_hwnd:
        return await backend.execute_lisp(code)

    try:
        import win32process

        from t20_mcp import dialog_automation as da

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
    except Exception as exc:
        return CommandResult(
            ok=False,
            payload={
                "code": "OPENING_MODE_AUTOMATION_FAILED",
                "requested_mode": operation,
                "automation": "window-discovery-failed",
                "retry_operation": operation,
                "retry_data": data,
            },
            error=f"[tangent.{operation}] 门窗模式自动化初始化失败: {exc}",
        )

    exclude = set(da.find_acad_popups(pid))
    launch = await backend.execute_lisp(_gen_opening_mode_launch())
    if not launch.ok:
        return CommandResult(
            ok=False,
            payload={
                "code": "OPENING_MODE_AUTOMATION_FAILED",
                "requested_mode": operation,
                "automation": "launch-failed",
                "retry_operation": operation,
                "retry_data": data,
            },
            error=f"[tangent.{operation}] 启动 TOpening 面板失败: {launch.error}",
        )
    if "active=1" not in str(launch.payload or ""):
        return CommandResult(
            ok=False,
            payload={
                "code": "OPENING_MODE_AUTOMATION_FAILED",
                "requested_mode": operation,
                "automation": "launch-not-active",
                "retry_operation": operation,
                "retry_data": data,
            },
            error=(
                f"[tangent.{operation}] TOpening 未进入活动状态: "
                f"{launch.payload!r}"
            ),
        )

    # CMDACTIVE=1 窗口期: 禁止 IPC, 直到 drive_opening_mode 空回车退出。
    drive = await da.drive_opening_mode(
        pid,
        cmd_hwnd,
        operation,
        exclude=exclude,
    )
    if drive != "mode-selected":
        # 失败后不冒险继续下发 IPC；仅在面板确实未退出时标记下次请求先取消。
        if "panel-still-open" in drive and hasattr(backend, "_needs_cancel"):
            backend._needs_cancel = True
        return CommandResult(
            ok=False,
            payload={
                "code": "OPENING_MODE_AUTOMATION_FAILED",
                "requested_mode": operation,
                "automation": drive,
                "retry_operation": operation,
                "retry_data": data,
            },
            error=f"[tangent.{operation}] 门窗模式自动切换失败: {drive}",
        )

    return await backend.execute_lisp(code)


# 所有保留子命令均可命令行驱动 (已剔除 #32770 模态对话框阻塞项)。
EXECUTE_DISABLED_SUBCOMMANDS: dict[str, str] = {}


def generate_lisp(subcommand: str, data: dict[str, Any] | None = None) -> str:
    """根据子命令与参数生成已校验、括号平衡的 AutoLISP 代码字符串。

    Raises:
        ParamError: 子命令未知, 或参数类型/范围非法, 或渲染结果异常。
    """
    if subcommand not in _GENERATORS:
        raise ParamError(
            f"未知 tangent 子命令: {subcommand!r}, 可用: {list(SUBCOMMANDS)}"
        )
    return _GENERATORS[subcommand](data or {})


# ---------------------------------------------------------------------------
# MCP 工具注册 (additive — 不触碰 dispatcher / IPC 层)
# ---------------------------------------------------------------------------


def register_tangent_tool(mcp: Any) -> None:
    """在传入的 FastMCP 实例上注册 ``tangent`` consolidated 工具。"""
    # 延迟导入, 避免与 client 的循环依赖, 并保持纯生成逻辑可离线测试。
    from t20_mcp.backends.base import CommandResult
    from t20_mcp.client import _json, _safe, add_screenshot_if_available, get_backend

    @mcp.tool(annotations={"title": "Tangent (天正 T20) Operations", "readOnlyHint": False})
    @_safe("tangent")
    async def tangent(  # type: ignore[reportUnusedFunction]
        operation: str,
        data: dict | None = None,
        execute: bool = False,
        include_screenshot: bool = False,
    ) -> str | list:
        """天正 T20 建筑实体封装 (LISP 模板 + 参数注入)。

        所有子命令均生成对应 AutoLISP 模板代码 (前置 _prelude.lsp 防御性骨架),
        参数在注入前做类型与范围校验, 非法参数会被拒绝。

        **execute (默认 False = dry-run)**: 默认只返回渲染后的 LISP 代码而**不**
        下发到 AutoCAD (不产生任何 IPC 文件); 传 execute=True 才经 execute_lisp
        真正执行。door/window/elevation 执行成功也会附 warning 字段。
        door/window 会先自动驱动「门窗参数」面板切换模式，再创建并硬校验
        DXF group71 (0=门, 1=窗)。模式不符会删除错误实体，返回
        OPENING_MODE_MISMATCH 和诊断/重试数据，不会把错误类型当成功。

        Operations (data 字段) — 真机验证状态 (T20 V10 / AutoCAD 2024):
          wall       — 单段墙体 [已验证]。{x1, y1, x2, y2, left_width?, right_width?, height?, wall_type?, layer?}
          dimension  — 天正逐点吸附标注 [已验证; 不适合总宽/总高, 见 warning]。
                       {p1_x, p1_y, p2_x, p2_y, pos_x?, pos_y?, layer?}
          wall_thickness_dimension — 墙厚标注 [已验证]。{p1_x, p1_y, p2_x, p2_y, layer?}
          opening_dimension — 门窗标注 [已验证]。{p1_x, p1_y, p2_x, p2_y, layer?}
          two_point_dimension — 两点标注 [已验证]。{p1_x, p1_y, p2_x, p2_y, pos_x?, pos_y?, layer?}
          elevation  — 标高标注 [已验证双点序列; text 经 COM 注入]。{base_x, base_y, label_x?, label_y?, text?, layer?}
          coordinate — 坐标标注 [已验证]。{point_x, point_y, label_x?, label_y?, layer?}
          symmetry   — 画对称轴 [已验证]。{x1, y1, x2, y2, layer?}
          line_pattern — 线图案 [已验证; 样式取面板记忆值]。{x1, y1, x2, y2, layer?}
          north_arrow — 画指北针 [已验证]。{pos_x, pos_y, dir_x?, dir_y?, layer?}
          break_line — 加折断线 [已验证]。{x1, y1, x2, y2, layer?}
          section_symbol — 剖切符号 [已验证]。{x1, y1, x2, y2, dir_x?, dir_y?, layer?}
          drawing_name — 图名标注 [已验证; name_text/scale_text 经 COM 注入]。{ins_x, ins_y, name_text?, scale_text?, layer?}
          rectangle  — 矩形     [已验证]。{x1, y1, x2, y2, layer?}
          balcony    — 阳台     [已验证; 类型/挑出宽取面板记忆值]。{points:[[x,y],...]>=2, layer?}
          step       — 台阶     [已验证; 踏步数/宽取面板记忆值]。{points:[[x,y],...]>=2, layer?}
          ramp       — 坡道     [已验证; 宽度/坡长取面板记忆值]。{x, y, layer?}
          arrow      — 箭头引注 [已验证; text/text2 经 COM 注入]。{x1, y1, x2, y2, text?, text2?, layer?}
          column     — 标准柱   [已验证; 面板 UI 自动化, 见 warning]。{x, y, height?, material?, rotation?, sec_w?, sec_h?}
                       material 合法值: 金属/钢筋砼/混凝土/石材/毛石/砖/耐火砖; 图层强制 COLUMN。
          rect_roof  — 矩形屋顶 [已验证; 坡角/出檐取面板记忆值]。{x1, y1, x2, y2, x3, y3, layer?}
          cusp_roof  — 攒尖屋顶 [已验证; 边数/屋顶高取面板记忆值]。{center_x, center_y, base_x?, base_y?, layer?}
          insight    — 内视符号 [已验证; 朝向/编号取面板记忆值]。{x, y, layer?}
          tree       — 任意布树 [已验证; 树种/尺寸取面板记忆值, 实体为 INSERT 图块]。{x, y, layer?}
          line_stair — 直线梯段 [已验证; 梯段宽/踏步数取面板记忆值]。{x, y, layer?}
          arc_stair  — 圆弧梯段 [已验证; 半径/踏步数取面板记忆值]。{x, y, layer?}
          double_stair — 双跑楼梯 [已验证; 梯段宽/楼梯高取面板记忆值]。{x, y, layer?}
          multi_stair — 多跑楼梯 [已验证; 跑数/梯段宽取面板记忆值]。{x1, y1, x2, y2, layer?}
          wheelchair_diameter — 轮椅直径 [已验证; edge 缺省为中心正右 1500mm]。{center_x, center_y, edge_x?, edge_y?, layer?}
          door       — 普通门   [已验证; group71 模式门禁]。{ins_x, ins_y, width?, height?, sill_distance?, layer?}
          window     — 普通窗   [已验证; group71 模式门禁]。{ins_x, ins_y, width?, height?, sill_height?, layer?}
          axis_lines — 普通线轴网 [可执行 LINE 替代]。{base_x?, base_y?, hspacings:[..], vspacings:[..], angle?, layer?}
          explode_read — 实体几何读回 [已验证]。{handle, offset_x?, offset_y?, max_entities?}
                       副本分解管线 (原生 EXPLODE, 不弹框), 不修改原实体。
          search_room — 搜索房间 [已验证]。{layer?} 全图墙体围合区域生成 TCH_SPACE。

        注: 验证记录详见 docs/T20_COMMANDS.md。
        """
        try:
            code = generate_lisp(operation, data or {})
        except ParamError as e:
            return _json({"error": f"[tangent.{operation}] {e}"})

        low_conf = operation in LOW_CONFIDENCE_SUBCOMMANDS
        disabled_reason = EXECUTE_DISABLED_SUBCOMMANDS.get(operation)

        # 默认 dry-run: 仅返回渲染后的 LISP, 不接触 backend / 不产生 IPC 文件。
        if not execute:
            payload: dict[str, Any] = {
                "operation": operation,
                "dry_run": True,
                "executed": False,
                "lisp": code,
                "hint": "传 execute=True 才会真正下发到 AutoCAD 执行",
            }
            if low_conf:
                payload["warning"] = LOW_CONFIDENCE_WARNINGS[operation]
            if disabled_reason:
                payload["execute_disabled"] = disabled_reason
            return _json(payload)

        # 真机证实的纯对话框命令: 拒绝下发, 避免阻塞 IPC / 崩溃风险。
        if disabled_reason:
            return _json({"error": f"[tangent.{operation}] execute 已禁用: {disabled_reason}"})

        backend = await get_backend()

        # column: 面板 UI 驱动编排 (Handoff 36), 不走通用 execute_lisp 路径。
        if operation == "column":
            result = await execute_column(backend, data or {})
            if result.ok and isinstance(result.payload, dict):
                result = CommandResult(
                    ok=True,
                    payload={**result.payload, "warning": LOW_CONFIDENCE_WARNINGS["column"]},
                )
            return await add_screenshot_if_available(result, include_screenshot)

        # explode_read: 原生 _.EXPLODE 不弹框 (itest_25 真机验证; TEXPLODE 方案
        # 弹「分解对象」框, 见 dialog_automation 模块的选型记录), 直接下发,
        # payload 经 parse_explode_payload 结构化并把坐标平移回原位。
        if operation == "explode_read":
            d = data or {}
            off_x = float(d.get("offset_x", 1_000_000.0))
            off_y = float(d.get("offset_y", 1_000_000.0))
            result = await backend.execute_lisp(code)
            if not result.ok:
                return _json({"error": f"[tangent.explode_read] {result.error}"})
            parsed = parse_explode_payload(str(result.payload or ""), off_x, off_y)
            parsed.update(
                {
                    "operation": operation,
                    "executed": True,
                    "warning": (
                        "已知 T20 缺陷: 墙体 explode 产物的起点侧顶点可能归零; "
                        "墙体精确几何请用 COM 曲线起终点 + LeftWidth/RightWidth。"
                        "若 clean=false 说明回滚未完全, 请检查并手动 UNDO"
                    ),
                }
            )
            result = CommandResult(ok=True, payload=parsed)
            return await add_screenshot_if_available(result, include_screenshot)

        if operation in ("door", "window"):
            result = await execute_opening(backend, operation, data or {})
        else:
            result = await backend.execute_lisp(code)
        if operation in ("door", "window") and result.ok:
            opening_status = parse_opening_status(result.payload)
            status_name = opening_status.get("status")
            if status_name == "MODE-MISMATCH":
                requested = opening_status.get("requested", operation)
                actual_code = opening_status.get("actual", "unknown")
                actual = {"0": "door", "1": "window"}.get(actual_code, "unknown")
                target_zh = "门" if requested == "door" else "窗"
                rolled_back = opening_status.get("rollback") == "ok"
                result = CommandResult(
                    ok=False,
                    payload={
                        "code": "OPENING_MODE_MISMATCH",
                        "requested_mode": requested,
                        "actual_mode": actual,
                        "wrong_entity_rolled_back": rolled_back,
                        "requires_user_action": (
                            f"自动切换到{target_zh}模式后 group71 仍不匹配；请检查"
                            f"天正门窗面板，必要时手工切换到{target_zh}模式，再用 "
                            "retry_operation 和 retry_data 原样重试。"
                        ),
                        "retry_operation": operation,
                        "retry_data": data or {},
                    },
                    error=(
                        f"[tangent.{operation}] OPENING_MODE_MISMATCH: "
                        f"requested={requested}, actual={actual}; "
                        f"wrong entity rollback={'ok' if rolled_back else 'failed'}"
                    ),
                )
            elif status_name == "NO-ENTITY":
                result = CommandResult(
                    ok=False,
                    payload={
                        "code": "OPENING_NOT_CREATED",
                        "retry_operation": operation,
                        "retry_data": data or {},
                    },
                    error=f"[tangent.{operation}] 插入点未生成 TCH_OPENING，请确认点位在有效墙段上",
                )
        # 低置信子命令: 在成功 payload 上附 warning (失败结果保持原 error 不动)。
        if low_conf and result.ok:
            base = result.payload
            if isinstance(base, dict):
                base = {**base, "warning": LOW_CONFIDENCE_WARNINGS[operation]}
            else:
                base = {"result": base, "warning": LOW_CONFIDENCE_WARNINGS[operation]}
            result = CommandResult(ok=True, payload=base)
        return await add_screenshot_if_available(result, include_screenshot)

    return None
