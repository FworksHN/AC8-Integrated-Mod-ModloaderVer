# AC8MouseAim — Standalone v2.5.1

> ### ⚠️ Camera note
> **For newly added aircraft whose size differs greatly from the original (for example AERIAL UAV TRANSPORT 'LADON'), if the camera position looks wrong in use, press `F3` to switch back to the original camera setting.**

> ### 🧪 Tested scope
> This standalone build has **only been tested on [ACE8 Mod Launcher & Loader V 2.0.0](https://www.nexusmods.com/acecombat8wingsoftheve/mods/64)**.
> Any other setup — for example a **manual UE4SS installation**, a different launcher/loader combination, or a different UE4SS build — is **untested and not guaranteed to work**.

A **single UE4SS mod separated out of** [AC8 Integrated Mod](https://github.com/CreeperUX/AC8-Integrated-Mod) v2.5.1: mouse flight control, cameras and HMD helmet aiming.

**Offline single-player only. Do not use online or in multiplayer.**

- This folder (`standalone/`) holds the **sources and documentation**.
- **The ready-to-install zip is in [Releases](../../releases)** — same as upstream, the repository carries no DLL binaries.

---

## 1. What it is

The integrated package bundles an installer, a launcher, a session console, per-launch deployment, exit cleanup and save backups. This folder keeps only the mod itself:

- **drop it into [ACE8 Mod Launcher & Loader V 2.0.0](https://www.nexusmods.com/acecombat8wingsoftheve/mods/64) — the only environment this build has been tested on (section 3, option A);**
- or copy it into a game folder that already has UE4SS (section 3, option B) — **that path has not been tested and is not guaranteed.**

The two loading paths are independent — do not confuse them:

```
ACE8 Mod Launcher
├─ Pak mods     → ue4ss\Mods\IoStoreLoaderMod\*.utoc   ← IoStoreLoaderMod mounts .utoc/.ucas only
└─ Script mods  → ue4ss\Mods\<name>\Scripts\main.lua   ← loaded by UE4SS; this mod belongs here
```

IoStoreLoaderMod accepts only `.utoc` (`source/src/loader.c:396`) and explicitly skips `scripts`
directories (`:413`). A `.utoc` carries cooked game assets, not scripts, so this mod is neither
loadable by it nor in need of it.

---

## 2. Requirements

| Requirement | Detail |
|---|---|
| Game version | Build **26002268** (Steam 1.01.002, AppID 2288340). The native module checks the PE timestamp `0x6AD2D0A7` and `SizeOfImage 0x215A2000`, so any other build is refused explicitly instead of patched blind. |
| UE4SS.dll | Must be **`680a026890abb4d0df2211251f8defc1681a584275f1521dcc0fe30af480006f`** (`UE4SS3.0.1-1152-ge3ba1016`, 20,605,440 bytes). The native module hard-codes that SHA-256 in `native/src/lua_bridge.h`; any other build is refused with `bridge refused: UE4SS runtime hash mismatch`. ACE8 Mod Launcher installs exactly this build. |
| VC++ runtime | Microsoft Visual C++ 2015-2022 **x64** Redistributable (the DLL imports `MSVCP140.dll`, `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll`). |

> **Offline marker:** the official native module additionally requires
> `EOS_USE_ANTICHEATCLIENTNULL=1` in the game process environment, but ACE8 Mod Launcher does not
> forward its environment to the game it starts (measured — see [PROVENANCE.md](PROVENANCE.md)).
> This build turns that gate into a compile-time switch (`AC8_MOUSE_AIM_LAUNCHER_SAFE`) and ships with
> it off; respect the boundary in section 4.

---

## 3. Install

Download `AC8MouseAim-standalone-v2.5.1.zip` from [Releases](../../releases) and unpack the `AC8MouseAim\` folder.

**Option A — ACE8 Mod Launcher & Loader V 2.0.0 (✅ the only tested environment):**
[nexusmods.com/acecombat8wingsoftheve/mods/64](https://www.nexusmods.com/acecombat8wingsoftheve/mods/64).
Close the game and launcher, drop the `AC8MouseAim\` folder (or the whole zip) onto the launcher
window, or use Mods → "Add mods…". The launcher recognises it as `AC8MouseAim (script mod)`,
installs it into `ue4ss\Mods\AC8MouseAim` and writes `enabled.txt`. Then stay in **Modded** mode and
press Play.

**Option B — manual (⚠️ untested, not guaranteed):** the steps below follow from how UE4SS works but
have **not** been verified on a real install (for example a manual UE4SS setup or a different
loader). Copy `AC8MouseAim\` to
`<game root>\Game\Binaries\Win64\ue4ss\Mods\AC8MouseAim\` (game root = the folder containing
`Game\Binaries\Win64\AceCombat8.exe`), make sure `AC8MouseAim\enabled.txt` exists (an empty file is
enough), or add `AC8MouseAim : 1` to `ue4ss\Mods\mods.txt` if your UE4SS build only reads that.
You are responsible for the requirements in section 2 — in particular the `UE4SS.dll` hash pin.

An empty `enabled.txt` is how this UE4SS build enables a script mod; no `mods.txt` line is needed.

---

## 4. About the native module (important boundary)

The `ac8_mouse_aim_010.dll` here is **not** the official v2.5.1 file: it is **recompiled from the
v2.5.1 sources** against Build 26002268, not patched. Two kinds of change:

**1) Game anchors moved to 26002268 (mandatory)**

| Purpose | v2.5.1 (25201480) | this build (26002268) |
|---|---|---|
| Input processor | `.text` signature scan | RVA `0x4D2C040` + masked 2323-byte fingerprint |
| Camera post-update | `0x70C8ED0` | `0x70B4960` |
| Camera vtable | `0xC9D3160` (slot 241) | `0xC9BCE20` (slot 241, unchanged) |
| Camera cache getter | `0x48FC6B0` | `0x48EF260` |
| `ActorLocation` exec | `0x3FD7430` | `0x3FCABB0` |
| HMD `SelectTarget` | `0x7296F40` | `0x7283700` |
| HMD release call site | `0x7D630E0` | `0x7D529E0` |
| PE timestamp / image size | `0x6AA0E27D` / `0x2195A000` | `0x6AD2D0A7` / `0x215A2000` |

All anchors live in `native/src/game_build.h` and were byte-checked against the installed
`AceCombat8.exe` (method and evidence: [../docs/ADAPTATION.md](../docs/ADAPTATION.md)). The input
processor is now located by "PE identity + exact RVA + masked fingerprint" rather than a whole-section
scan, because a scan can hit multiple candidates on a new build and refuse to start. The 2323-byte
instruction fingerprint itself is **unchanged** — that function is still identical in 26002268.

**2) Offline gate (compile-time switch)**

The upstream check is kept in source; `build.cmd` compiles with `-DAC8_MOUSE_AIM_LAUNCHER_SAFE`, which
logs the missing marker and continues instead of refusing. Remove the define to restore the strict
upstream behaviour (which then cannot start under this launcher).

**Unchanged:** the `UE4SS.dll` SHA-256 pin, all 22 exports, the 6 `LuaMadeSimple` imports, and every
Lua script and UI asset (byte-identical to the upstream payload).

```
official v2.5.1   f66a8cf8a298c535b123b9857a904f9ce9241c59e92f908a032c4cb15a1783cf
this build        see native.reference_build_sha256 in standalone/adapter-manifest.json
```

`native/build.cmd` builds an equivalent DLL on any machine with the VS 2022 C++ x64 toolchain (section 8).
It is not byte-reproducible: MSVC stamps the PE header with the build time, so the SHA-256 of your
build will differ from the recorded reference while the code is the same.

> **Why it is needed:** the official gate demands `EOS_USE_ANTICHEATCLIENTNULL=1`, but ACE8 Mod
> Launcher disables anti-cheat with `AceCombat8.exe -eac-nop-loaded -nosplash` and neither sets nor
> forwards that variable (measurements in [PROVENANCE.md](PROVENANCE.md)). Under that launcher the
> official DLL cannot start.
>
> **Boundary:** the gate exists so the mod does not run while anti-cheat is active. ACE8 Mod
> Launcher already guarantees that — Modded mode runs with anti-cheat off, and switching to
> Unmodded moves `ue4ss\`, `dwmapi.dll`, `~mods` and `LogicMods` out of the game folder, so the mod
> is not installed at all. **But in any other installation (for example a hand-made bare UE4SS
> setup) that protection is gone.** Use the official DLL there, or make sure you only launch with
> anti-cheat off.

---

## 5. Keybinds

| Key | Action |
|---|---|
| Mouse movement | Sets the flight target direction; the mod coordinates aircraft attitude |
| Hold **C** + mouse | Mod free look; the previous flight target is kept on release |
| Hold **C + RMB** | Extra optical zoom during free look (`free_look_zoom`) |
| **F2** | Toggle HMD (off at every start) |
| **F3** | **Native relative / far follow camera** (press it when a newly added aircraft has a wrong camera) |
| **F4** | PEACE / WAR flight controller (WAR is the default) |
| **F5** | Performance diagnostics |
| **F6** | View diagnostics (writes a gaze-state file into `Scripts\`) |
| **F7** | Show / hide mod HUD and notices |
| **Alt+F7** | Show / hide the nose reference gun cross (this session only) |
| **F8** | Master toggle for mouse flight control |
| **F9** | Recenter the aim direction |
| **F10** | Reload `config.ini` and `camera-settings.lua`, then recenter |

Release Shift / Ctrl / Alt before pressing F2, F3 or F4 — those modifiers are the throttle keys.
`V` is the game's own view toggle and is not the same as `F3`; use the third-person view with this mod.

---

## 6. Configuration

`AC8MouseAim\config.ini` is read by the native module; press **F10** to apply most changes.
Notable entries: `control_mode` (3=WAR, 0=PEACE), `sensitivity`, `model_assist`, `hud_renderer`,
`hud_boresight`, `camera_mode` (**F3** toggles it), `camera_distance_m`/`camera_height_m`,
`free_look_zoom`, `flight_recording` (set to `1` for FE/Shadow CSV logs in `Logs\`), and
`pitch_slot`/`roll_slot`.

`AC8MouseAim\Scripts\camera-settings.lua` holds `follow_rate` (2..20) and `level_rate` (0..10).
It has **no compiled-in default** — a missing or malformed file makes the mod fail to load.

Keybinds live in the `[keybindings]` section as **Windows virtual-key codes**: `free_look=67` (C),
`free_look_zoom=2` (RMB), `pitch_up=83` (S), `pitch_down=87` (W), `roll_left=65` (A),
`roll_right=68` (D), `yaw_left=81` (Q), `yaw_right=69` (E).

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Game runs, no mouse flight control at all | Native module did not start | Read the last line of `Logs\MouseAim-NNNNN.log` |
| `bridge refused: UE4SS runtime hash mismatch` | Wrong `UE4SS.dll` | Use build `680a0268…006f` |
| `error game image or input signature mismatch (expected Steam Build 26002268)` | Game is not Build 26002268 (typical after a Steam update) | Run `..\tools\verify\verify-anchors.ps1`, then re-derive anchors per [../docs/ADAPTATION.md](../docs/ADAPTATION.md) |
| `native camera refused: executable identity/signature mismatch` | Same PE gate on the camera path | Same as above |
| `inactive: offline launch marker missing` | You are using the **official** DLL (this build never logs it) | Use the DLL from this package (section 4) |
| UE4SS cannot load the DLL | VC++ runtime missing | Install the x64 redistributable |
| No `[AC8MouseAim] Loaded.` in `UE4SS.log` | `enabled.txt` missing or wrong folder depth | Check `…\ue4ss\Mods\AC8MouseAim\Scripts\main.lua` exists |
| `Disabled: required game-thread callback unavailable.` | Wrong UE4SS build | Use the pinned build |
| Wrong axis responds | Different game build | Adjust `pitch_slot`/`roll_slot` or the `*_sign` values |
| **Camera wrong on a newly added aircraft** | Airframe size differs a lot from the original | **Press `F3` to switch back to the original camera** |

---

## 8. Building the native module yourself

This package **already contains** the compiled `Scripts\ac8_mouse_aim_010.dll`; you only need this to
reproduce or retarget the build:

```powershell
# needs Visual Studio 2022 + C++ x64 toolchain (build.cmd calls vswhere/vcvars64 itself)
cd native
cmd /c build.cmd      # produces native/build/ac8_mouse_aim_010.dll
```

`build.cmd` compiles `src/mouse_aim.cpp` plus the four MinHook C files with
`cl /std:c++20 /EHsc /MD /O2 /LD`, links the import library generated from `src/ue4ss_lua.def`, and
defines `AC8_MOUSE_AIM_LAUNCHER_SAFE` (section 4). Game anchors live in `src/game_build.h`; retargeting
a new build means editing that one file and rebuilding.

Verification helpers in the package root:

```powershell
tools\verify\verify-anchors.ps1                 # re-check every anchor against the installed exe
tools\verify\verify-build.ps1 <dll path>        # check exports/imports/anchors inside the artifact
```

---

## 9. Uninstall

Delete `<game root>\Game\Binaries\Win64\ue4ss\Mods\AC8MouseAim\`, remove the `AC8MouseAim : 1`
line if you added one, and only remove `dwmapi.dll` / `ue4ss\` if you are certain no other UE4SS
mod uses them. The mod writes no registry keys, installs no services, and leaves nothing outside
the game folder.

---

## 10. Licence and origin

MIT © 2026 CreeperUX for the mod and the integration (see the package root [LICENSE](../LICENSE)).
Upstream project: [FletcherMiya/AC8-Mouse-Aim](https://github.com/FletcherMiya/AC8-Mouse-Aim).
UE4SS is MIT; MinHook, MouseFlight and font licences are in [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)
and `licenses/`. The full record of the separation and the offline gate is in [PROVENANCE.md](PROVENANCE.md);
the Build 26002268 adaptation evidence is in [../docs/ADAPTATION.md](../docs/ADAPTATION.md).
Reference implementation for the port: [GGforceP/AC8-Integrated-Mod-Enhanced](https://github.com/GGforceP/AC8-Integrated-Mod-Enhanced).

[中文](README.md)
