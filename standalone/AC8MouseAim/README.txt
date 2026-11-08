WorldAim1.3.6 — world-space aiming (the mouse sets a target direction, not a
fixed screen cursor).

AC8MouseAim v2.5.1+26002268, separated from the AC8 Integrated Mod and re-aimed
at Steam 1.01.002 (Build 26002268). Target environment: ACE8 Mod Launcher 2.0.0.

REBUILT FROM SOURCE, NOT PATCHED. Scripts\ac8_mouse_aim_010.dll was compiled
from the v2.5.1 sources in ..\..\native with the Build 26002268 game anchors
(moved input, camera and helmet-targeting RVAs) and an added PE identity gate.
It is therefore a different file from the official v2.5.1 DLL:

    official v2.5.1      f66a8cf8a298c535b123b9857a904f9ce9241c59e92f908a032c4cb15a1783cf
    this build            <reference hash in standalone/adapter-manifest.json>

The UE4SS.dll SHA-256 pin (680a0268...006f) is unchanged: ACE8 Mod Launcher
installs exactly that UE4SS build, so the pin passes here, and the module still
refuses to run on any other UE4SS runtime.

The offline launch gate is compiled out in this build. Upstream refuses to start
unless the game process sees EOS_USE_ANTICHEATCLIENTNULL=1; ACE8 Mod Launcher
does not set it (it disables anti-cheat with the "-eac-nop-loaded" argument
instead), so the gate can never pass under the launcher. Offline single-player
only — never use this with anti-cheat or in multiplayer.

See README.md in the package root for install steps, keybinds, the adapter
notes and how to reproduce the build.
