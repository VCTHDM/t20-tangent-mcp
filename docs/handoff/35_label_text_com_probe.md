# Handoff 35 — B2 闭合: drawing_name / arrow / elevation 文本 COM 注入

> 日期: 2026-07-02 · 环境: T20 V10 / AutoCAD 2024 (真机) · 脚本: scripts/itest_40_label_text_com_probe.py
> 原始证据: docs/handoff/35_label_com_raw.txt (probe all + inject 两轮完整输出)

## 0. 一句话结论

**B2 二选一结案: 可注入。** 三个标注命令的文字全部暴露可写 COM 属性,
写入+读回真机精确匹配 (含中文 GBK 全链路)。**S-4 "面板记忆值锁死" 对这三个
命令的候补判定被证伪** — S-4 收窄为仅 door/window 模式切换 (group 71)。

## 1. 探针方法 (itest_40, 三段式)

1. **Gate A dump**: 创建实体后 `LOGFILEMODE=1` 捕获 `vlax-dump-object obj T`
   到 AutoCAD 日志, 同机 Python 直读 (GBK) 解析 RW 属性清单。
   - 坑: 中文版 AutoCAD 的 dump 段落标记是本地化的 **";特性值:"** (不是
     "Property values:"), 首轮解析落空导致误判 fallback。
2. **COM put/get**: 逐 RW 属性 `vlax-put-property` 测试值 → 读回比对 → 就地
   恢复原值 (字符串写 "T20MCP-B2", 数值写 123.0)。
3. **DXF 对照**: entget 字符串组仅 0/100/410/8 结构组, 文本不落 DXF —
   COM 是唯一注入路径 (与 Handoff 33 三方证伪方法论对齐)。

cleanup 铁律全程满足: 实体回 baseline + CMDACTIVE=0/CMDDIA=1/FILEDIA=1/
OSMODE=0/LOGFILEMODE=0, 三命令探针与 E2E 共 7 轮全部 cleanup PASS。

## 2. 真机发现 (COM 接口全景)

| 子命令 | 实体/COM 接口 | 可写文本属性 (真机命中) | 其它可写 | put ERR (锁死) |
|---|---|---|---|---|
| drawing_name | TCH_DRAWINGNAME / IComDrawingName | **NameText** (图名), **ScaleText** (比例文字) | Scale, LayoutRotation, TextColor 等 | NameStyle, ScaleStyle |
| arrow | TCH_ARROW / IComSymbArrow | **Text** (上标), **Text2** (下标) | Scale, LayoutRotation, TextColor 等 | FontStyle |
| elevation | TCH_ELEVATION / IComSymbElev | **Text** (标高文字, 默认自动计算 "0.00000") | Scale, LayoutRotation 等 | FontStyle |

注:
- NameHeight/ScaleHeight/SpaceCoef 等 "字符串形数值" 属性 put OK 但写入
  "T20MCP-B2" 被静默归零 ("0.0") — 有类型协转, 不算文本注入点, 未参数化。
- ObjectControl/ShowScale/MaskFlag 等枚举字符串 put OK 但值不变 (静默拒绝)。
- 样式类 (NameStyle/ScaleStyle/FontStyle) put ERR — 样式仍走面板, 不可参数化。

## 3. 已落地的封装增强 (本轮一并实施)

- 模板 (`src/t20_mcp/lisp_templates/tangent/`): drawing_name/arrow/elevation
  三个 .lsp 增加 `{{COM_INJECT}}` 占位 (对齐 opening.lsp 范式, 类型校验通过
  后 `vlax-ename->vla-object` + 逐属性 put)。
- 生成器 (`src/t20_mcp/tools/tangent.py`):
  - `drawing_name`: 新增可选 `name_text` / `scale_text`
  - `arrow`: 新增可选 `text` (上标) / `text2` (下标)
  - `elevation`: 新增可选 `text` (覆盖自动计算的标高文字)
  - 共用 `_com_put_text()` + `LABEL_TEXT_MAX=100`; `_require_str` 复用
    (空串/超长/控制字符/GBK 外字符/非字符串 全部 ParamError 拒绝)。
  - LOW_CONFIDENCE_WARNINGS 三条同步改写 ("待评估" → "已验证可注入")。
- 离线测试: tests/test_tangent_lisp_gen.py 新增 12 case
  (注入代码断言 x6 + 引号转义 x1 + 非法文本拒绝 x5 参数化), 159 → **171 passed**。

## 4. 真机闭合证据 (inject E2E)

```
inject drawing_name: PASS  |NameText="一层平面图"|ScaleText="1:50"
inject arrow:        PASS  |Text="做法见详图"|Text2="1:20"
inject elevation:    PASS  |Text="3.000"
```

三例 delta=+1, 类型校验由模板内部完成, 读回中文精确匹配, cleanup 全绿。

## 5. 复跑命令

```bash
uv run python scripts/itest_40_label_text_com_probe.py all     # Gate A+B 探针
uv run python scripts/itest_40_label_text_com_probe.py inject  # 参数注入 E2E
```

## 6. 对 backlog 的影响

- B2: **DONE** (本文档)。
- S-4: 收窄 — "drawing_name / arrow / elevation 的文本" 从 S-4 候补移除;
  S-4 仅剩 door/window 模式切换 (group 71 面板决定)。
- 下一步主线: B1 (TGColumn Gate B 控件映射封装)。
- 方法论沉淀: TCH 自定义实体的 "面板记忆值" 不等于 "不可参数化" — dump 一次
  COM 接口再下结论; balcony/step/ramp/insight/tree 等其它 "取面板记忆值" 命令
  未来可按同法逐个 dump 评估 (候选后续任务)。
