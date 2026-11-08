standalone\tools\patch-offline-gate.mjs 是上游 v2.5.1 的工具，用于把「官方 DLL」的离线门
打 12 字节 NOP 补丁。它自带 SHA-256 校验，只接受官方那个文件（f66a8cf8…），对任何其它 DLL
都会直接报错退出，因此不会误伤本包的 DLL。

本包不需要它：本包的 DLL 是针对 Build 26002268 从源码重编的，离线门通过编译宏
AC8_MOUSE_AIM_LAUNCHER_SAFE 关闭（见 ../README.md 第 4 节）。
