# 从 Build 25201480 到 26002268：适配记录

本文件记录 **AC8MouseAim 独立版**（`standalone/AC8MouseAim/`）如何从上游 v2.5.1
（游戏 Build 25201480）重建到 **Steam 1.01.002 / Build 26002268**，以及每一步的证据。

适配的参考实现是 [GGforceP/AC8-Integrated-Mod-Enhanced](https://github.com/GGforceP/AC8-Integrated-Mod-Enhanced)
v2.6.0——它把同一批 hook 移植到了 26002268。本包**没有直接采信**它的常量，而是逐个对实机
`AceCombat8.exe` 复核后重编（见第 3 节）。

---

## 1. 结论先行

| 项目 | 结论 |
|---|---|
| 需要改的东西 | 只有 4 个文件：新增 `game_build.h`，改 `mouse_aim.cpp`、`native_camera.h`、`helmet_selection.h` |
| Lua 脚本 | **完全不用改**（12 个脚本与本包上游逐字节一致） |
| 输入槽位 | 不变：槽 0 俯仰、槽 1 偏航、槽 2 滚转 |
| UE 对象结构偏移 | 不变（相机管理器 `+0x14A0` / `+0x14D0`、pawn `+0x1A0`、root `+0x220` 等） |
| 输入函数指纹 | 不变（2323 字节函数体逐字节相同，仅 RIP 相对位移的地址部分按掩码忽略） |
| 变的东西 | 7 个 RVA + 2 个 PE 身份字段（见第 2 节） |

---

## 2. 锚点对照

所有常量集中在 `native/src/game_build.h`。

| 用途 | v2.5.1（25201480） | 本版（26002268） |
|---|---|---|
| PE `TimeDateStamp` | `0x6AA0E27D` | `0x6AD2D0A7` |
| PE `SizeOfImage` | `0x2195A000` | `0x215A2000` |
| 输入处理函数 `input` | 全 `.text` 段签名扫描 | RVA `0x4D2C040` |
| 相机 post-update `camera_update` | `0x70C8ED0` | `0x70B4960` |
| 相机 vtable `camera_table` | `0xC9D3160` | `0xC9BCE20` |
| 相机 vtable 槽位 | 241 | 241（**未变**） |
| 相机缓存 getter | `0x48FC6B0` | `0x48EF260` |
| `ActorLocation` exec | `0x3FD7430` | `0x3FCABB0` |
| HMD `SelectTarget` | `0x7296F40` | `0x7283700` |
| HMD 玩家释放调用点 | `0x7D630E0` | `0x7D529E0` |

> 上游还有一处版本相关线索：`native_camera.h` 里 `actor_location_exec` 的指纹检查地址是
> `RVA+0x19`（`0x3FCABC9`）。编译时会把这个加数折叠进指令位移，因此产物里看到的是
> `0x3FCABC9` 而不是 `0x3FCABB0`——`tools/verify/check_dll_constants.py` 按折叠后的值检查。

---

## 3. 验证：本机 exe 就是 26002268

测试机安装路径：`E:\SteamLibrary\steamapps\common\ACE COMBAT 8\Game\Binaries\Win64\AceCombat8.exe`

```
大小        551,201,904 字节
SHA-256     3E47FD42858D1F2B81E59D7F57394A014C0EB6AAF4C02EE3DA351B6A42936BE2
PE 时间戳   0x6AD2D0A7
镜像大小    0x215A2000
机器类型    0x8664 (x64)
节区数量    14
```

该 SHA-256 与 Enhanced v2.6.1 `version.json` 的 `game_sha256` **完全一致**，说明本机这份
可执行文件就是 Enhanced 适配并实测过的那个 Build 26002268 二进制，而不是"同版本号、不同补丁"的副本。

### 3.1 逐锚点字节校验

`tools/verify/verify-anchors.ps1` 用**独立实现**（直接读 PE 节表做 RVA→文件偏移换算，不复用模块代码）
复核 10 项，全部通过：

```
[OK] PE TimeDateStamp == 0x6AD2D0A7
[OK] PE SizeOfImage == 0x215A2000
[OK] input processor yaw signature @0x4D2C040 — 2323 bytes, 212 masked
[OK] camera_update prologue @0x70B4960
[OK] camera_cache_getter @0x48EF260
[OK] actor_location_exec+0x19 @0x3FCABC9
[OK] camera vtable slot 241 @0xC9BD5A8 -> camera_update — 0x1470B4960 vs 0x1470B4960
[OK] helmet select entry @0x7283700 — 21 bytes
[OK] helmet release call site @0x7D529CC
[OK] helmet release rel32 @0x7D529DC — -11334368 vs -11334368
```

其中两个检查值得单独说明：

- **相机 vtable 槽 241**：静态读取 `0xC9BCE20 + 241*8` 得到一个 8 字节指针，值恰为
  `0x1470B4960`（首选基址 `0x140000000` + `0x70B4960`）。这一条同时证明"vtable 位置"和
  "槽位编号"两项都对，不依赖登录游戏。
- **HMD 释放调用点**：`0x7D529E0` 往前 20 字节是 `call SelectTarget` 的指令序列，
  其中 `rel32 == select_rva - release_return_rva`。这是运行期判断"是不是玩家释放调用"的依据，
  偏移算错会让 HMD 静默失效，所以单独校验。

### 3.2 产物校验

`tools/verify/verify-build.ps1` 对编译出的 DLL 做两类检查：

```
导出符号        22 个（与 Scripts/main.lua 的 package.loadlib 逐一对应）
UE4SS.dll 导入  6 个 LuaMadeSimple 符号（构造/析构/get_number/is_number/get_stack_size/set_number）
PE 架构         0x8664
大小            8,400,896 字节（官方 v2.5.1 为 8,400,384，+512 字节来自新增的校验代码与日志字符串）
```

并确认 9 个锚点立即数、5 条新版日志字符串确实落进了二进制——避免"源码改了但编译的是旧产物"。

---

## 4. 为什么输入函数从"签名扫描"改成"RVA + 指纹"

上游做法是遍历所有可执行节区找 2323 字节指纹，且命中两处就判定歧义并拒绝（`if (found) return nullptr;`）。
在 25201480 上这没问题；在 26002268 上它有两个隐患：

1. 新版里同一指纹是否仍唯一，未经验证；
2. 扫描失败时的日志只说 "signature missing or ambiguous"，不告诉你是版本不对还是真的撞了。

本版改成：

```cpp
bool game_image_matches();   // PE 时间戳 + SizeOfImage 双字段
unsigned char* find_hook() {
    if (!game_image_matches()) return nullptr;
    auto* target = base + ac8_build::input;
    return matchesYawCode(target, sizeof(yawCode)) ? target : nullptr;
}
```

即：**先证明游戏是这个版本，再在确切 RVA 上复核那 2323 字节**。失败日志直接写期望的 build 号。
副作用是换版本必须改 `game_build.h`——但这本来就是必须做的，且失败是"明确拒绝"而不是"扫到别处乱挂钩"。

> 2323 字节指纹里 212 个字节被掩码为通配（RIP 相对寻址的位移），其余 2111 字节必须完全相同。
> 这比"只认 RVA"强得多：RVA 对但函数体不对（比如撞上另一个 build 的同址函数）会被拒绝。

---

## 5. Lua 侧为什么不用改

把上游独立版的 `Scripts/` 与 Enhanced v2.6.1 发布载荷里的 `AC8MouseAim/Scripts/`
逐字节比对，**12 个 Lua 脚本、4 个 PNG、2 个 TTF 全部一致**；整个目录只有 3 处差异：

| 文件 | 差异 |
|---|---|
| `config.ini` | 一行注释：`Build 25201480 input layout` → `Steam Build 26002268 input layout`（数值 `pitch_slot=0`、`roll_slot=2` 不变） |
| `README.txt` | Enhanced 把它压缩成一句说明 |
| `enabled.txt` | Enhanced 的打包模板不预置（由安装器写） |

因此本版对 Lua 的唯一改动也是一行注释，其余保持上游字节。这也反证了输入槽位布局在
25201480 → 26002268 之间没有变化。

---

## 6. 离线门处理

上游 `offline_authorized()` 要求进程环境变量 `EOS_USE_ANTICHEATCLIENTNULL=1`。
ACE8 Mod Launcher 用 `AceCombat8.exe -eac-nop-loaded -nosplash` 关反作弊，**不设置也不转发**
环境变量（实测见 `standalone/PROVENANCE.md` 第 4.1 节），所以这道门在目标环境里必然失败。

上游的发布 DLL 是靠**对二进制打 12 字节 NOP 补丁**绕过的（把两条条件跳转改成 NOP）。
本版改为**编译期开关**：

```cpp
#ifdef AC8_MOUSE_AIM_LAUNCHER_SAFE
    log_line("offline marker absent: launcher build continues (offline single-player only)");
    return true;
#else
    return false;
#endif
```

`build.cmd` 默认带 `-DAC8_MOUSE_AIM_LAUNCHER_SAFE`。好处是：源码里能直接看到这条门还在、
为什么关掉、日志会留痕；不需要靠"改完二进制再验证哈希"这种间接手段；去掉宏重编即可还原严格语义。

**边界不变**：这层保护依赖 ACE8 Mod Launcher 的 Modded/Unmodded 互斥架构。把这份 DLL 用在
别的安装方式（例如手工裸装 UE4SS）就失去这层保护——那种情况下请用官方 DLL，或自行确保只在
关闭反作弊时启动。**仅限离线单人，严禁线上或多人。**

---

## 7. 未验证的部分（请如实看待）

- **没有做游戏内实测**：本次适配只做到"静态锚点全部命中 + 产物契约正确"。
  鼠标飞控、F3 相机、F2 头盔瞄准在 26002268 的实际手感/功能需要你在离线任务里跑一遍确认。
- **UE4SS.dll 哈希锁定仍是 `680a0268…006f`**。本包没有改这个 pin：ACE8 Mod Launcher 2.0.0
  装的正是该构建。若你的加载器换了 UE4SS 版本，日志会写 `bridge refused: UE4SS runtime hash mismatch`，
  这是设计行为，不是 bug。
- **结构偏移未逐项复验**：`native_camera.h` / `helmet_selection.h` 里那些 UE 对象偏移
  （`+0x1A0`、`+0x220`、`+0x14A0`、`+0x14D0`、`+0x750`、`+0x870`、`+0x1AE8`）在两版之间没有变化——
  依据是 Enhanced 的适配 diff **只动了 RVA 与 PE 字段**，没有碰结构偏移。这条依据强度低于第 3 节的
  字节校验（它是"另一份实现没改"而不是"我逐字节验证了"）。

---

## 8. 复现步骤

```powershell
# 0) 前置：Visual Studio 2022（C++ x64 工作负载）、Python 3
# 1) 复核实机 exe 的全部锚点（换版本时先跑这个，看哪一项不匹配）
.\tools\verify\verify-anchors.ps1
.\tools\verify\verify-anchors.ps1 -Exe 'D:\path\to\AceCombat8.exe'

# 2) 重编原生模块（产出 native\build\ac8_mouse_aim_010.dll）
cd native; cmd /c build.cmd; cd ..

# 3) 复核产物：导出表、导入表、锚点常量、日志字符串
.\tools\verify\verify-build.ps1 .\native\build\ac8_mouse_aim_010.dll

# 4) 覆盖进分发包
Copy-Item .\native\build\ac8_mouse_aim_010.dll .\standalone\AC8MouseAim\Scripts\ -Force
```

---

## 9. 游戏再更新时怎么重取锚点

如果更新只是移动地址、没有改这几个函数本身（第 7 节的情况 B），不需要重新逆向：

```powershell
# 先确认工具本身还对得上当前版本（它会和自己仓库里的 game_build.h 对比）
python tools\verify\retarget.py --self-test

# 用新版 exe 重取全部锚点，直接生成 game_build.h
python tools\verify\retarget.py --new-exe "<新的 AceCombat8.exe>" --build <新构建号> --out native\src\game_build.h
```

工具对每个锚点用**两条独立证据**：一条指令指纹负责"定位"，一条结构关系负责"证明"。

| 锚点 | 定位 | 证明 |
|---|---|---|
| input | 2323 字节掩码指纹（2111 字节必须逐字节相同） | 唯一命中 |
| camera_update | 15 字节函数序言 | 只有被某个 vtable **槽 241** 指向的那个候选存活 |
| camera_table | —— | 由上面的 vtable 引用反推，槽位偏移再校验一遍 |
| camera_cache_getter | 9 字节 `lea rax,[rcx+0x14A0]; ret` | 唯一命中 |
| actor_location_exec | 48 字节函数头 | 唯一命中，且 `head+0x19` 仍是 `mov rax,[rcx+0x1A0]` |
| helmet_select | 21 字节入口 | 唯一命中 |
| helmet_release_return | 16 字节调用点 | `rel32` 必须正好指向前一步的 `helmet_select` |

当某个锚点命中的候选过多、或证明链不成立时，工具**退出码非 0 且不写 header**（不会产出半成品）。
若输出里出现 `function body probably changed`，说明那段指令只匹配了一部分——那是第 7 节的情况 C，
需要反汇编，`retarget.py` 帮不上忙。

重取之后照第 8 节第 2~4 步重编、复核、覆盖，另外还要跑一遍原生单测：

```powershell
cd native; cmd /c test.cmd; cd ..
```

> `camera_context_tests` 和 `cutscene_recovery_tests` 已经改成跟随 `ac8_build::camera_table`，
> 所以换版本后它们会自动用新值，不需要手工跟着改。
