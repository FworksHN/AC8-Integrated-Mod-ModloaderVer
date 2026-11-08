#pragma once
#include <cstdint>

// Steam 1.01.002 / Build 26002268 anchors for the AC8 mouse-aim native module.
//
// Every value here was re-derived from the shipped executable and checked with
// tools/verify_anchors.py before this module was built:
//
//   * PE identity  : TimeDateStamp and SizeOfImage must both match, so a
//                    different game build is refused instead of patched blind;
//   * each RVA     : the bytes at that RVA are compared with the instruction
//                    fingerprint the module expects (see the call sites).
//
// Offsets from another build are not interchangeable: the PE gate turns them
// into a clean "signature mismatch" log line rather than a crash, but nothing
// else in the module will work either.
namespace ac8_build {
inline constexpr unsigned steam_build = 26002268;
inline constexpr unsigned pe_timestamp = 0x6AD2D0A7;
inline constexpr unsigned image_size = 0x215A2000;

// Input processor that turns the yaw/pitch/roll slots into a flight command.
inline constexpr std::uintptr_t input = 0x4D2C040;

// Camera: the post-update function, the camera vtable that holds it, and the
// two accessors used to prove the manager is the live player camera.
inline constexpr std::uintptr_t camera_update = 0x70B4960;
inline constexpr std::uintptr_t camera_table = 0xC9BCE20;
inline constexpr unsigned camera_update_slot = 241;
inline constexpr std::uintptr_t camera_cache_getter = 0x48EF260;
inline constexpr std::uintptr_t actor_location_exec = 0x3FCABB0;

// Helmet (HMD) target selection, plus the return address of the player-only
// release call site that is allowed to redirect the selection.
inline constexpr std::uintptr_t helmet_select = 0x7283700;
inline constexpr std::uintptr_t helmet_release_return = 0x7D529E0;
} // namespace ac8_build
