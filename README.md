# AC8MouseAim 独立版 · Build 26002268

鼠标飞控 + 摄像机 + HMD 头盔瞄准的**单个 UE4SS mod**，从
[CreeperUX/AC8-Integrated-Mod](https://github.com/CreeperUX/AC8-Integrated-Mod) v2.5.1 的
`standalone/` 分离出来，并**重建到 Steam 1.01.002 / Build 26002268**。

> **这个仓库只维护独立版。**
> 上游整合包那套（`AC8-Integrated-Setup.exe` 安装程序、自带启动器、会话管理、存档备份、Steam 启动选项）
> 的源码仍在仓库里，但**本 fork 不再维护也不提供发行版**——要那一套请去
> [上游仓库](https://github.com/CreeperUX/AC8-Integrated-Mod)。
>
> 本 fork 的定位：让独立版在新的游戏版本上继续能用。

**正式版。仅限离线单人，禁止用于线上或多人游戏。**

---

## 这是什么

鼠标指定**世界空间的目标方向**（不是屏幕上的固定光标），mod 协调飞机姿态飞向那个方向。

按 **F4** 在两种飞控之间切换：

- **WAR**（默认）：基于还原的 AC8 转动规律，决策结构参考 War Thunder 鼠标教官；机头走直线，鼠标停下后平滑改平，来回拖动时反应更快，按住操纵键可按 War Thunder 规则接管。
- **PEACE**：原 CLASSIC 2.0。

还包括：机头参考准星（按住 C 自由观察时也显示）、自由观察中的头瞄、逐帧同步输入与自定义按键、
过场后模组相机／HUD 恢复。

---

## 安装

**前提**：游戏是 **Build 26002268**，加载环境是
[ACE8 Mod Launcher & Loader V 2.0.0](https://www.nexusmods.com/acecombat8wingsoftheve/mods/64)。

1. 关闭游戏与启动器。
2. 把 `standalone/AC8MouseAim/` 文件夹拖进启动器窗口，或走 Mods 页 → “Add mods…”。
   启动器会识别成 `AC8MouseAim (script mod)`，装到 `ue4ss\Mods\AC8MouseAim`。
3. 启动器保持 **Modded** 模式，按 Play。

`enabled.txt`（空文件）就是这个 UE4SS 构建的启用标记，不需要改 `mods.txt`。

> **仓库里不带编译好的 DLL**（`scripts/validate-source.py` 禁止二进制进源码树，与上游规则一致）。
> 用下面「构建」一节自己编译，或下载 Release 附件里的成品包。
>
> 安装、配置、排错、完整键位表见 [`standalone/README.md`](standalone/README.md)。

---

## 构建原生模块

需要 Visual Studio 2022（C++ x64 工作负载）。`build.cmd` 会自己调 `vswhere` 与 `vcvars64`：

```powershell
cd native
cmd /c build.cmd        # 产出 native/build/ac8_mouse_aim_010.dll
```

把 DLL 放到 `standalone/AC8MouseAim/Scripts/` 即可。

**不是字节可复现构建**：MSVC 会把构建时间写进 PE 头，所以自己编出来的哈希与记录的参考值不同，
代码一致。用 `standalone/adapter-manifest.json` 里的大小／导出数，加上下面的校验脚本确认产物正确。

---

## 验证

```powershell
tools\verify\verify-anchors.ps1                 # 对实机 AceCombat8.exe 复核全部 10 个锚点
tools\verify\verify-build.ps1 <dll 路径>        # 复核导出/导入/锚点常量是否落进产物
python scripts\validate-source.py               # 仓库源码审计（CI 也会跑）
```

启动后原生模块日志（`ue4ss\Mods\AC8MouseAim\Logs\MouseAim-NNNNN.log`）里应有：

```
input processor ready: Steam Build 26002268 (anchors from game_build.h)
```

没有这句说明版本校验没过——那是设计行为，不是崩溃。

---

## 与上游 v2.5.1 的差异

游戏从 25201480 更新到 26002268 时，**7 个函数地址全变了**，正好是三条 hook 的入口。已重新定位并验证：

| 用途 | 25201480 | 26002268 |
|---|---|---|
| 输入处理函数 | 段扫描 | `0x4D2C040` |
| 相机 post-update | `0x70C8ED0` | `0x70B4960` |
| 相机 vtable | `0xC9D3160` | `0xC9BCE20`（槽 241 未变） |
| 相机缓存 getter | `0x48FC6B0` | `0x48EF260` |
| `ActorLocation` exec | `0x3FD7430` | `0x3FCABB0` |
| HMD `SelectTarget` | `0x7296F40` | `0x7283700` |
| HMD 释放调用点 | `0x7D630E0` | `0x7D529E0` |
| PE 时间戳 / 镜像大小 | `0x6AA0E27D` / `0x2195A000` | `0x6AD2D0A7` / `0x215A2000` |

**没变**（所以没动）：全部 Lua 脚本与 UI 资源、输入槽位布局（槽 1 = 偏航）、UE 对象结构偏移、
以及输入函数那段 2323 字节的指令指纹。

工程性改动两处：

- 输入定位从「全 `.text` 段扫签名、撞两处就拒启动」改成「PE 身份 + 精确 RVA + 掩码指纹」，
  版本不对会明确报 `expected Steam Build 26002268`，而不是乱挂钩。
- 离线门 `EOS_USE_ANTICHEATCLIENTNULL` 保留在源码里，靠编译宏 `AC8_MOUSE_AIM_LAUNCHER_SAFE` 关闭
  （ACE8 Mod Launcher 用 `-eac-nop-loaded` 关反作弊、不转发环境变量，这道门在目标环境必然失败）。

完整证据、逐项校验结果、以及**哪些没验证**：见 [`docs/ADAPTATION.md`](docs/ADAPTATION.md)。

---

## 键位速查

| 按键 | 功能 |
|---|---|
| 移动鼠标 | 指定飞行目标方向 |
| 按住 **C** + 移动鼠标 | 自由观察 |
| 按住 **C + 右键** | 自由观察 + 光学放大 |
| **F2** | HMD 头盔瞄准开关（每次启动默认关） |
| **F3** | 原生 / 拉远跟随机位（新机体相机异常时按它） |
| **F4** | PEACE / WAR 飞控切换 |
| **F5 / F6 / F7** | 性能诊断 / 视角诊断 / HUD 显隐 |
| **Alt+F7** | 机头参考准星 |
| **F8 / F9 / F10** | 飞控总开关 / 回中 / 重读配置 |

按 F2/F3/F4 前先松开 Shift / Ctrl / Alt（那是油门键）。完整键位与 `config.ini` 参数见
[`standalone/README.md`](standalone/README.md)。

---

## 兼容性

| 项目 | 要求 |
|---|---|
| 游戏 | Steam 1.01.002 / **Build 26002268**。其它版本会在启动时被明确拒绝 |
| 加载器 | ACE8 Mod Launcher & Loader V 2.0.0（本 fork 只在这个环境验证过） |
| UE4SS.dll | 必须是 `680a026890abb4d0df2211251f8defc1681a584275f1521dcc0fe30af480006f`，原生模块里锁死了这个 SHA-256 |
| 运行库 | Microsoft Visual C++ 2015-2022 x64 Redistributable |

换手动安装的 UE4SS、换别的启动器、换别的 UE4SS 构建——都**未经验证**，不保证有效。

---

## 仓库结构

```
standalone/         独立版本体 + 文档 + 适配清单（本 fork 的主要交付）
  AC8MouseAim/      拖进启动器的那个文件夹（含 Lua 脚本与 UI 资源）
  adapter-manifest.json
native/             原生模块源码（game_build.h 是版本锚点，换版本只改这里）
  src/  include/  vendor/minhook/
tools/verify/       锚点与产物校验脚本
docs/ADAPTATION.md  Build 26002268 适配记录
scripts/validate-source.py   源码审计（CI 跑）
```

其余目录（`package-template/`、`scripts/` 的启动器部分、`tests/`、`updates/`、`models/`、`docs/`
的大部分）继承自上游整合包，本 fork 未维护。

---

## 已知限制

- **没有做游戏内实测**。适配只做到「静态锚点全部命中 + 产物契约正确」；手感、F3 相机、F2 头盔瞄准
  需要自己在离线任务里确认。
- 新增机体（如 AERIAL UAV TRANSPORT 'LADON'）机体尺寸差异大时，相机位置可能不正常，按 **F3** 切回原版机位。
- 先保证原生圆环不一定达到 120 Hz，也不保证 F1／通知对所有设备零性能影响。
- WAR 未覆盖所有机型和任务，见 [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)。

---

## 来源与许可

- 上游整合与修改：MIT © 2026 CreeperUX，见 [LICENSE](LICENSE)。
- 独立版分离：[Astervolans/AC8-Integrated-Mod](https://github.com/Astervolans/AC8-Integrated-Mod)（`standalone-v2.5.1`）。
- 26002268 移植的参考实现：[GGforceP/AC8-Integrated-Mod-Enhanced](https://github.com/GGforceP/AC8-Integrated-Mod-Enhanced) v2.6.0。
- 原始项目：[FletcherMiya/AC8-Mouse-Aim](https://github.com/FletcherMiya/AC8-Mouse-Aim)。
- UE4SS / MinHook / 字体许可：见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 `licenses/`。

[English](README.en.md)
