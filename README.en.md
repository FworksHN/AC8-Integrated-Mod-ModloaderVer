# AC8MouseAim standalone · Build 26002268

A **single UE4SS mod** for mouse flight control, camera and HMD helmet aiming, split out of
[CreeperUX/AC8-Integrated-Mod](https://github.com/CreeperUX/AC8-Integrated-Mod) v2.5.1's
`standalone/` and **rebuilt for Steam 1.01.002 / Build 26002268**.

> **This repository maintains the standalone mod only.**
> The upstream integration layer (the `AC8-Integrated-Setup.exe` installer, the bundled launcher,
> session management, save backups, the Steam launch option) is still in the tree but is **not
> maintained and not released by this fork** — get that from
> [upstream](https://github.com/CreeperUX/AC8-Integrated-Mod).
>
> This fork exists for one reason: keeping the standalone mod usable on the current game build.

**Release build. Offline single-player only — never use this online or in multiplayer.**

---

## What it does

The mouse sets a **world-space target direction** (not a fixed screen cursor); the mod coordinates
aircraft attitude to fly there. **F4** switches between two flight controls:

- **WAR** (default): reconstructed AC8 rotation law with a War Thunder mouse-aimer style decision
  structure — the nose tracks straight lines, levels smoothly when the mouse stops, reacts faster to
  back-and-forth input, and hands over to War Thunder takeover rules while a control key is held.
- **PEACE**: the original CLASSIC 2.0.

Also included: a nose reference gun cross (shown during free look as well), helmet aiming in free look,
per-frame synced input with custom keys, and camera/HUD recovery after cutscenes.

---

## Install

**Requires** game build **26002268** and
[ACE8 Mod Launcher & Loader V 2.0.0](https://www.nexusmods.com/acecombat8wingsoftheve/mods/64).

1. Close the game and the launcher.
2. Drag the `standalone/AC8MouseAim/` folder into the launcher window (or Mods → “Add mods…”).
   It is recognised as `AC8MouseAim (script mod)` and installed to `ue4ss\Mods\AC8MouseAim`.
3. Keep the launcher in **Modded** mode and press Play.

`enabled.txt` (an empty file) is how this UE4SS build enables script mods; no `mods.txt` edit needed.

> **No compiled DLL is committed** (`scripts/validate-source.py` keeps binaries out of the tree, the
> same rule upstream follows). Build it as described below, or use the packaged asset on the Release page.
>
> Install steps, configuration, troubleshooting and the full keybind table:
> [`standalone/README.en.md`](standalone/README.en.md).

---

## Build the native module

Needs Visual Studio 2022 with the C++ x64 workload. `build.cmd` locates `vswhere`/`vcvars64` itself:

```powershell
cd native
cmd /c build.cmd        # produces native/build/ac8_mouse_aim_010.dll
```

Copy the DLL into `standalone/AC8MouseAim/Scripts/`.

**This is not a byte-reproducible build**: MSVC stamps the PE header with the build time, so your
SHA-256 differs from the recorded reference while the code is identical. Confirm a build with the size
and export count in `standalone/adapter-manifest.json` plus the scripts below.

---

## Verify

```powershell
tools\verify\verify-anchors.ps1                 # re-check all 10 anchors against the installed AceCombat8.exe
tools\verify\verify-build.ps1 <dll path>        # exports, imports and anchor immediates inside a built DLL
python tools\verify\retarget.py --self-test     # confirm the retargeting tool still matches this build
python scripts\validate-source.py               # source audit (also run by CI)
```

A healthy start logs this line in `ue4ss\Mods\AC8MouseAim\Logs\MouseAim-NNNNN.log`:

```
input processor ready: Steam Build 26002268 (anchors from game_build.h)
```

Missing that line means the build gate rejected the game — intended behaviour, not a crash.

---

## What changed from upstream v2.5.1

The update from build 25201480 to 26002268 moved **all seven function addresses**, and they are exactly
the entry points of the three hooks. Re-derived and verified:

| Purpose | 25201480 | 26002268 |
|---|---|---|
| Input processor | section scan | `0x4D2C040` |
| Camera post-update | `0x70C8ED0` | `0x70B4960` |
| Camera vtable | `0xC9D3160` | `0xC9BCE20` (slot 241 unchanged) |
| Camera cache getter | `0x48FC6B0` | `0x48EF260` |
| `ActorLocation` exec | `0x3FD7430` | `0x3FCABB0` |
| HMD `SelectTarget` | `0x7296F40` | `0x7283700` |
| HMD release call site | `0x7D630E0` | `0x7D529E0` |
| PE timestamp / image size | `0x6AA0E27D` / `0x2195A000` | `0x6AD2D0A7` / `0x215A2000` |

**Unchanged** (so untouched): every Lua script and UI asset, the input slot layout (slot 1 = yaw), the
UE object struct offsets, and the 2323-byte instruction fingerprint of the input processor.

Two engineering changes:

- Input lookup went from "scan the whole `.text` section, reject on ambiguity" to "PE identity, exact
  RVA, masked fingerprint". A wrong build now logs `expected Steam Build 26002268` instead of hooking
  something unrelated.
- The offline gate `EOS_USE_ANTICHEATCLIENTNULL` stays visible in source and is compiled out with
  `AC8_MOUSE_AIM_LAUNCHER_SAFE` (ACE8 Mod Launcher disables anti-cheat with `-eac-nop-loaded` and never
  forwards environment variables, so that gate cannot pass there).

Full evidence, per-anchor checks and the list of things **not** verified:
[`docs/ADAPTATION.md`](docs/ADAPTATION.md).

---

## Keys

| Key | Action |
|---|---|
| Mouse | sets the flight target direction |
| Hold **C** + mouse | free look |
| Hold **C + RMB** | free look + optical zoom |
| **F2** | HMD helmet aiming (off at every start) |
| **F3** | native vs far-follow camera (use it when a new aircraft looks wrong) |
| **F4** | PEACE / WAR flight control |
| **F5 / F6 / F7** | perf / view diagnostics / HUD toggle |
| **Alt+F7** | nose reference gun cross |
| **F8 / F9 / F10** | master switch / recenter / reload config |

Release Shift / Ctrl / Alt before F2, F3 or F4 — those modifiers are the throttle keys. Full keybinds
and the `config.ini` reference: [`standalone/README.en.md`](standalone/README.en.md).

---

## Compatibility

| Item | Requirement |
|---|---|
| Game | Steam 1.01.002 / **Build 26002268**. Any other build is refused at startup |
| Loader | ACE8 Mod Launcher & Loader V 2.0.0 (the only environment this fork was checked against) |
| UE4SS.dll | must be `680a026890abb4d0df2211251f8defc1681a584275f1521dcc0fe30af480006f` — pinned in the native module |
| Runtime | Microsoft Visual C++ 2015-2022 x64 Redistributable |

A hand-installed UE4SS, a different launcher or a different UE4SS build is **untested** and not guaranteed.

---

## Repository layout

```
standalone/         the standalone mod, its docs and the adapter manifest (main deliverable)
  AC8MouseAim/      the folder you drop into the launcher (Lua scripts and UI assets)
  adapter-manifest.json
native/             native module source (game_build.h holds the build anchors)
  src/  include/  vendor/minhook/
tools/verify/       anchor and artifact verification
docs/ADAPTATION.md  the Build 26002268 adaptation record
scripts/validate-source.py   source audit (run by CI)
```

Everything else (`package-template/`, the launcher parts of `scripts/`, `tests/`, `updates/`, `models/`,
most of `docs/`) is inherited from the upstream integration package and is not maintained here.

---

## Known limits

- **No in-game test was performed.** The port is backed by static anchors and artifact checks; feel, the
  F3 camera and the F2 helmet aim still need a pass in an offline mission.
- Aircraft whose airframe differs a lot from the original (e.g. AERIAL UAV TRANSPORT 'LADON') can show a
  wrong camera position — press **F3** to fall back to the stock camera.
- The native reticle is not guaranteed to reach 120 Hz, and F1 / notices are not guaranteed to be free
  on every device.
- WAR does not cover every aircraft and mission; see [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md).

---

## Origin and licence

- Upstream integration and modifications: MIT © 2026 CreeperUX — see [LICENSE](LICENSE).
- Standalone split: [Astervolans/AC8-Integrated-Mod](https://github.com/Astervolans/AC8-Integrated-Mod) (`standalone-v2.5.1`).
- Reference implementation for the 26002268 port: [GGforceP/AC8-Integrated-Mod-Enhanced](https://github.com/GGforceP/AC8-Integrated-Mod-Enhanced) v2.6.0.
- Original project: [FletcherMiya/AC8-Mouse-Aim](https://github.com/FletcherMiya/AC8-Mouse-Aim).
- UE4SS / MinHook / font notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and `licenses/`.

[中文](README.md)
