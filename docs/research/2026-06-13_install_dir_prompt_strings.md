# T20 V10 安装目录提示词与门窗线索离线检索

日期：2026-06-13  
范围：`C:\Tangent\TArchT20V10\`、`%APPDATA%\Tangent\TArch20V10\`、`HKCU\Software`。  
目标：补足 `TGColumn`、`TDimTP`、`TSWall`、`TUpdSpace`、`TOpening` 的本机安装目录证据，重点寻找命令行提示词、菜单宏、ARX/DLL 字符串和门/窗模式配置线索。

## 0. 结论摘要

本轮没有在安装目录中找到可直接用于 MCP 封装的完整命令行提示序列。安装目录能确认命令名、菜单入口、部分对象类型和若干内部字段，但不能确认 `TGColumn`、`TDimTP`、`TSWall`、`TUpdSpace` 的参数顺序。

主要发现：

- `SYS\tchcmd.txt`、`sys24x64\Tch.tmn`、CUI/CUIX 菜单均确认五个目标命令存在。
- CUI/CUIX 菜单宏大多只是 `命令名` 或 `^C^C命令名`，没有追加点选/关键字/回车序列。
- 未发现 `.chm/.html/.htm/.pdf` 帮助文件；无需也无法执行 `hh.exe -decompile`。
- `TOpening` 相关证据比其他命令多：`TCommonOpenning.xml` 有门/窗/洞口默认库字段，ARX 字符串有 `Sill`、`InsertMode`、`OpeningKind`、`SetKind@TDbOpening`、`GetSubKind/SetSubKind@TDbOpening` 等内部线索。
- `%APPDATA%\Tangent\TArch20V10\sys` 只有 `acad.pgp`、`KeyMap.txt`；未发现门/窗模式配置文件。
- `reg query HKCU\Software /f Tangent|TArch|TOpening /s` 无命中；`Opening` 仅命中 Microsoft Edge 的无关 `EnhancedLinkOpeningDefault`。

## 1. 文件枚举与帮助文件

安装目录枚举到的相关文本/菜单/二进制类型包括：

- `SYS\*.txt/*.xml/*.ini/*.lsp/*.cuix/*.dll`
- `Lisp\*.lsp/*.dcl/*.dat`
- `sys19x64` 到 `sys24x64` 下的 `*.arx/*.dll/*.tmn/*.cui/*.cuix`

没有发现：

- `*.chm`
- `*.html`
- `*.htm`
- `*.pdf`

因此本轮没有 CHM 可反编译。现有命令提示词证据只能来自文本配置、菜单和二进制字符串。

## 2. 命令名与中文功能名确认

`SYS\tchcmd.txt` 是最直接的命令表，GBK 解码可读：

```text
标准柱   TGColumn
单线变墙 TSWall
门窗     TOpening
搜索房间 TUpdSpace
两点标注 TDimTP
```

`SYS\TOptionsDef.xml` 也把这些命令归入对应面板：

- `TGColumn` 属于“柱子”
- `TSWall` 属于“墙体”
- `TOpening` 属于“门窗”
- `TUpdSpace` 属于“房间屋顶”
- `TDimTP` 属于“尺寸标注”

这只确认命令注册和功能分组，不提供交互序列。

## 3. CUI/CUIX 菜单宏

已解包 `SYS\tangent.cuix`、`sys24x64\TCH.cuix`、`sys24x64\TCH.bak.cuix` 到 `%TEMP%\t20_cuix_extract_*` 后检索。

关键命中：

```xml
<Name>单线变墙</Name>
<Command>TSWall  </Command>

<Command>TOpening  </Command>
<HelpString>在墙上插入各种门窗: MC</HelpString>

<Command>TGColumn  </Command>
<Name>标准柱</Name>
<Command>TGColumn </Command>

<Name>两点标注</Name>
<Command>^C^CTDimTP</Command>
<CLICommand>两点标注</CLICommand>
```

结论：

- `TDimTP` 菜单宏只做取消后启动命令：`^C^CTDimTP`。
- `TGColumn`、`TSWall`、`TOpening` 宏只启动命令。
- CUIX 没有发现附加参数、点选占位、关键字或回车序列。
- CUIX 未命中 `TUpdSpace` 的可执行宏条目；`Tch.tmn` 中有菜单条目，见下一节。

## 4. TMN 菜单与帮助说明

`sys24x64\Tch.tmn` 为 GBK 文本，包含比 CUIX 更完整的天正菜单说明。关键命中：

```text
Id_Fzh           [标 准 柱]TGColumn
Id_Stod          [单线变墙]TSWall
ID_TOpening      [门　　窗]TOpening
ID_UpdSpace      [搜索房间]TUpdSpace
ID_DimTP         [两点标注]TDimTP
Opening=0,"TCH_OPENING"
ID_TOpening = "Tch_Door", "在墙上插入各种门窗: MC"
ID_TReplaceOpening = "TCH_REPLACE_OPENING", "选中已经插入的门窗进行门窗替换，可把门窗替换为窗或者门：MCTH"
ID_ROFLNA = "TCH_SITE1", "自动跨越门窗洞口搜索墙线的封闭区域，生成屋顶平面轮廓线: SWDX"
ID_SpGround = "", "自动搜索房间轮廓，并生成平板作为房间地面: FJDM"
```

结论：

- TMN 确认 `TUpdSpace` 菜单入口存在。
- `TOpening` 的菜单说明是“在墙上插入各种门窗: MC”，仍未说明门/窗模式切换。
- `TReplaceOpening` 明确可把既有门窗替换为窗或门，但这是替换命令，不是 `TOpening` 初始插入模式。
- `Opening=0,"TCH_OPENING"` 只像菜单/对象过滤配置，不能证明模式变量。

## 5. SYS 配置与对象映射

`SYS\createobjcmd.ini`：

```ini
TCH_COLUMN=TGColumn
TCH_SPACE=TSpArea
TCH_DIMENSION2=TDimMP
TCH_OPENINGSLOT=TOpeningSlot
TCH_CORNER_WINDOW=TCornerWin
```

注意没有 `TCH_OPENING=TOpening` 映射。该文件说明对象创建命令映射，但不覆盖所有对象。

`SYS\Getxmlcfg.ini`：

```text
门窗     TCH_OPENING
房间对象 TCH_SPACE
柱子     TCH_COLUMN
```

`SYS\TFindRepFilter.xml`：

```xml
<content name="门窗编号" selected="-1">
  <DXF码>TCH_OPENING,TCH_CORNER_WINDOW,TCH_DORMER,</DXF码>
</content>
<content name="房间名称" selected="-1">
  <DXF码>TCH_SPACE,</DXF码>
</content>
```

这些文件可用于实体类型确认，不提供命令行交互。

## 6. TOpening 门/窗/洞口线索

`SYS\TCommonOpenning.xml` 是最有价值的配置文件。它以 UTF-8 存储门窗默认库，包含：

```xml
<门>
  <数据 名称="M1221" 类型="普通门" 门宽="1200" 门高="2100" 门槛高="0" ... />
</门>
<窗>
  <数据 名称="C1212" 类型="普通窗" 窗宽="1200" 窗高="1200" 窗台高="900" 高窗="0" ... />
</窗>
<洞口>
  <数据 名称="" 型式="" 洞宽="0" 洞高="0" 底高="0" 穿透="0" 洞深="0" 样式="" />
</洞口>
```

可推断但未验证：

- 门、窗、洞口是同一“门窗类型”配置树下的不同分类。
- “窗台高”在配置文件中是真实业务字段。
- “门槛高”对应当前模板中已部分验证的 `DoorSill` 方向更合理。

不能据此确认：

- COM 属性名就是 `SillHeight` 或 `WindowSillHeight`。
- `TOpening` 命令行有关键字可切换门/窗/洞口。
- 切换门/窗模式写入了某个文件或注册表项。

## 7. ARX/DLL 字符串

聚焦扫描了 AutoCAD 2024 对应目录 `sys24x64` 的相关模块：

- `tch_kerncmd.arx`
- `tch_kernal.arx`
- `tch_annotate.arx`
- `TCH_UIPanelWindowAndDoor.arx`
- `TCH_UIPanelColumn.arx`
- `TCH_UIPanelWall.arx`
- `tch10_com24.dll`

### 7.1 `tch_kerncmd.arx`

可见字符串/符号包括：

```text
CInsertOpeningDlg
General Opening parameters
门窗参数
Sill
InsertMode
同样编号的门窗参数不一致
SetKind@TDbOpening
OpeningKind@TOpeningData
GetSubKind@TDbOpening
SetSubKind@TDbOpening
GetWallElevation@TOpeningData
TSearchSpaceFromWall
SearchSpaces2@TSearchSpaceFromWall
TDbSpace
TDbColumn
```

结论：

- `TOpening` 很可能通过 `CInsertOpeningDlg` / 门窗参数面板持有当前插入参数。
- `Sill` 和 `InsertMode` 是内部参数名或资源字符串，但不是已确认的 ActiveX 属性名。
- `OpeningKind@TOpeningData`、`SetKind@TDbOpening` 支持“门/窗/洞口类型是内部枚举”的判断。
- `TUpdSpace` 对应内部 `TSearchSpaceFromWall` / `SearchSpaces2`，说明它确实是墙体搜索房间逻辑。

### 7.2 `TCH_UIPanelWindowAndDoor.arx`

可见字符串/符号包括：

```text
GlwDoorDlg
dWinWidth
tObjpDoor
tObjpOpening
TCH_UIPanelDoorsAndWindows.arx
GetSubKind@TDbOpening
SetSubKind@TDbOpening
UpdateOpenings@TArchCmdReactor
LAY_OPENING_DIM
```

结论：

- 门窗面板 ARX 明确持有门/窗/洞口参数。
- 这里更支持“当前门/窗模式在面板状态中”，不是 CUI 宏或注册表静态项。

### 7.3 `tch10_com24.dll`

可见字符串/符号包括：

```text
GetHeight@TColumnData
SetHeight@TColumnData
SetSectionShape@TColumnData
SetMaterial@TColumnData
TDbColumn
SetSpaceFlag
GetSpaceFlag
GetWidth@TWallData
SetWidth@TWallData
GetHeight@TWallData
SetHeight@TWallData
```

结论：

- COM DLL 暴露了柱、墙、空间等对象的内部数据方法符号。
- 本轮没有在 COM DLL 的可见字符串中找到可直接用的 `SillHeight` / `WindowSillHeight` 属性名。

## 8. `%APPDATA%` 与注册表

发现的用户态天正目录：

```text
%APPDATA%\Tangent\TArch20V10\sys\acad.pgp
%APPDATA%\Tangent\TArch20V10\sys\KeyMap.txt
```

`KeyMap.txt` 只包含图层/对象选择/隐藏/自由复制移动等快捷映射，没有门窗模式。

`acad.pgp` 未命中：

- `TOpening`
- `TGColumn`
- `TDimTP`
- `TSWall`
- `TUpdSpace`
- 门窗/标准柱/单线/房间/标注

注册表检索：

```text
reg query HKCU\Software /f Tangent /s
reg query HKCU\Software /f TArch /s
reg query HKCU\Software /f TOpening /s
reg query HKCU\Software /f Opening /s
```

结果：

- `Tangent`：0 match
- `TArch`：0 match
- `TOpening`：0 match
- `Opening`：仅 Edge 的 `EnhancedLinkOpeningDefault`，无关

结论：没有发现 `TOpening` 门/窗模式存在 HKCU 或 `%APPDATA%\Tangent` 的静态配置项。

## 9. 分命令可用结论

### `TGColumn` 标准柱

已确认：

- 命令表存在：`标准柱 TGColumn`
- CUI/TMN 菜单存在：`TGColumn`
- COM DLL 可见 `TColumnData`、`TDbColumn`、`SetHeight@TColumnData`、`SetSectionShape@TColumnData`

未确认：

- 启动后是否弹柱参数面板。
- 点选顺序或命令行关键字。
- 能否像墙体一样先生成实体再 COM 注入参数。

建议：只做真机提示捕获，不直接封装。

### `TDimTP` 两点标注

已确认：

- 命令表存在：`两点标注 TDimTP`
- CUI 宏：`^C^CTDimTP`
- TMN 菜单存在：`ID_DimTP [两点标注]TDimTP`

未确认：

- 点序列是否与 `TDimMP` 相同。
- 是否需要选择对象或墙体。

建议：下一步真机只启动命令并记录首个提示；不要复用 `TDimMP` 序列。

### `TSWall` 单线变墙

已确认：

- 命令表存在：`单线变墙 TSWall`
- CUI/TMN 菜单存在：`TSWall`
- `Lisp` 中有 `_ucswall`，但这是 `TUcsWall` / 墙面 UCS 相关函数，不是 `TSWall` 命令实现。

未确认：

- 是否首步选择原生 `LINE`。
- 墙宽来自面板记忆还是命令行输入。

建议：真机先建一条 `LINE`，启动 `TSWall`，捕获提示；成功判据为原线替换或新增 `TCH_WALL`。

### `TUpdSpace` 搜索房间

已确认：

- 命令表存在：`搜索房间 TUpdSpace`
- TMN 菜单存在：`ID_UpdSpace [搜索房间]TUpdSpace`
- ARX 内部符号：`TSearchSpaceFromWall`、`SearchSpaces2@TSearchSpaceFromWall`、`TDbSpace`

未确认：

- 命令是否全图搜索、框选搜索或点取内部点。
- 是否直接生成 `TCH_SPACE`，还是更新已有空间对象。

建议：构造闭合 `TCH_WALL` 矩形后真机捕获提示和实体增量。

### `TOpening` 门窗

已确认：

- 命令表存在：`门窗 TOpening`
- 菜单说明：`在墙上插入各种门窗: MC`
- 默认库区分 `<门>`、`<窗>`、`<洞口>`，并包含 `窗台高` 字段。
- ARX 内部有 `CInsertOpeningDlg`、`Sill`、`InsertMode`、`OpeningKind@TOpeningData`、`SetKind@TDbOpening`、`GetSubKind/SetSubKind@TDbOpening`。

未确认：

- 命令行关键字能否切换门/窗。
- 当前模式是否可通过 COM 属性设置。
- `窗台高` 的真实 ActiveX 属性名。
- `%APPDATA%` / HKCU 没有发现可直接改写的模式配置。

建议：

1. 继续保留 `door` 子命令的“门模式”中置信路线。
2. `window` 不应因本轮发现而升置信；`Sill` 只是内部线索。
3. 后续真机实验优先枚举 `TCH_OPENING` 的 COM 可读/可写属性，同时对比门模式和窗模式的 `GetSubKind`/对象数据差异。
4. 如果需要脚本化切换窗模式，优先研究 `SetKind@TDbOpening` / `SetSubKind@TDbOpening` 是否通过 ActiveX 暴露；其次再考虑面板 UI 自动化。

## 10. 对 MCP 封装的影响

本轮安装目录证据不足以新增可执行封装。建议保持：

- `TGColumn`：待验证，不开放 `execute=True`
- `TDimTP`：待验证，不开放 `execute=True`
- `TSWall`：待验证，不开放 `execute=True`
- `TUpdSpace`：待验证，不开放 `execute=True`
- `window` / `TOpening` 窗模式：待验证，不因 `Sill` 字符串提高置信度

最小下一步不是继续离线 grep，而是真机捕获：

1. 用只启动命令的 LISP 捕获首个提示。
2. 每个命令单独恢复环境，避免残留 `CMDACTIVE`。
3. 每条候选序列都以实体增量、实体类型和属性回读作为成功判据。
