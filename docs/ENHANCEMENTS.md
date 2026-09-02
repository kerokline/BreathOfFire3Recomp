# BoF3 enhancements — post-faithfulness work

**Status:** IN PROGRESS (established 2026-08-30; E1 shipped upstream
2026-09-01). E2 and the backlog are design only, nothing scheduled. This file
exists so ideas raised during bringup are recorded with their real cost instead
of being re-derived later.

## The gate

Framework rule (`psxrecomp/CLAUDE.md`, inherited via `/CLAUDE.md`): **no
per-game hacks during foundation work.** Enhancements become legitimate only
after the faithful core is proven. BoF3 plays at full speed but has not been
soaked end to end — see [`STATUS.md`](STATUS.md). E1 was acceptable early
because it is a *framework* presentation feature, off by default, with no
per-title code.

A second constraint shapes every item below: `psxrecomp/` and `recomp-ui/` are
**read-only submodules**. Anything that needs runtime or renderer code is an
upstream `mstan/psxrecomp` change plus a deliberate gitlink bump here — it
cannot be done from inside this repo. That distinction is the difference
between a config edit and a multi-backend shader PR, so each item names which
it is.

Line numbers below were taken against psxrecomp `a91884a4` (2026-08-30) and
have drifted; re-verify before citing.

---

## E1 — CRT scanlines / display filter

**Kind:** upstream framework change (GL present path + launcher).
**Requested:** 2026-08-30. **Status:** **SHIPPED upstream.** The runtime side
(present-time scanline post-process, `[video]` settings persistence) merged as
[mstan/psxrecomp#290](https://github.com/mstan/psxrecomp/pull/290) on
2026-09-01 and is in the current pin. The launcher side (Scanlines toggle +
strength on the PSX Display card) is
[mstan/recomp-ui#42](https://github.com/mstan/recomp-ui/pull/42), open; the
`recomp-ui` submodule is pinned to the fork branch carrying it until then.
The design notes below are kept as the record of what was built and why.

Goal: reproduce the horizontal line structure a CRT gave PSX output, as a
presentation-only effect. Guest rendering is untouched; this is a pass over the
finished display image on its way to the window.

### Where it hooks in

The GL present is a full-screen fragment shader, `PRESENT_FS` at
[`gpu_gl_renderer.c:877`](../psxrecomp/runtime/src/gpu_gl_renderer.c), which
already carries the shape a scanline term needs:

| Uniform | Meaning | Why it matters here |
|---|---|---|
| `u_sharp` | 0 straight sample, 1 sharp-bilinear, 2 bicubic | Precedent for a mode enum on the present pass |
| `u_tex_size` | source texture size in texels | Source line count |
| `u_sharp_scale` | output pixels per source texel | **Output pixels per source scanline** — exactly the period the effect needs |

Those are set in `present_set_sharp()`
([`gpu_gl_renderer.c:2584`](../psxrecomp/runtime/src/gpu_gl_renderer.c)), which
deliberately re-states every uniform on every call because the program is
shared by the CPU present and both VRAM/FBO quad paths and GL program uniforms
persist. Any new uniform must follow that rule or it will leak across present
paths.

### Design

**Shader.** A darkening term on `frag.rgb` derived from `gl_FragCoord.y`,
periodic in `u_sharp_scale.y` (output pixels per source line). Two knobs:
strength (0..1, depth of the dark line) and beam width (fraction of the period
left bright). Guard `u_sharp_scale.y < 2.0` → pass through unmodified: below
two output pixels per source line there is nowhere to put a dark line, and
attempting it aliases into moiré. This mirrors the degrade-gracefully logic
`u_sharp == 1` already applies at `scale <= 1`.

Apply the term **after** the sampling branch, so it composes with nearest,
sharp-bilinear and bicubic rather than replacing a mode.

**Gamma.** A naive multiply darkens the image overall, which is the usual
reason software scanlines look wrong next to a real CRT. Compensating the
bright rows to preserve mean luminance is the difference between "looks like a
CRT" and "looks dim". Worth doing in the first version, not deferred.

**Interlace.** BoF3 field-renders in places, and the display height varies
(240- vs 480-class modes) even with `[video] aspect_ratio = "4:3"` pinned in
`game.toml`. `u_tex_size.y` is the authority for the source line count, not a
constant — a 480-line source must not get 240-line spacing.

### Scope beyond the GL shader

This is the part that makes E1 a real project rather than a ten-line patch:

1. **OpenGL** — `PRESENT_FS` + uniform plumbing + `present_set_sharp()`'s
   restate discipline. The tractable half.
2. **Vulkan** — *there is no present fragment shader to extend.* The Vulkan
   backend blits the displayed VRAM region straight to the swapchain with
   `vkCmdBlitImage`
   ([`gpu_vk_renderer.c:1817`](../psxrecomp/runtime/src/gpu_vk_renderer.c)) —
   no shader stage in the present path at all. Scanlines there means
   introducing a present render pass with its own pipeline: substantially more
   work than the GL side, and it changes the backend's present structure.
3. **Software renderer** — presents via SDL_Renderer in
   `runtime/src/main.cpp`; no shader anywhere. Either a CPU row-multiply, or
   the feature is honestly GL-only.

A backend-gated feature is acceptable (the bezel precedent below is
OpenGL-only), but that must be stated in the manifest description rather than
discovered by a player who happens to be on the Vulkan backend.

### User-facing surface

Follow **`psx.presentation.bezel`**, the existing framework-owned presentation
mod and the closest precedent in the tree:

- Manifest:
  [`mods/builtin/packages/psx.presentation.bezel/1.0.0/manifest.toml`](../psxrecomp/mods/builtin/packages/psx.presentation.bezel/1.0.0/manifest.toml)
  — `[[feature]]` in group `Visual`, `default_enabled = false`,
  `[[target]] game_id = "*"`, plus a `[[plugin]]` id.
- Implementation:
  [`mod_builtin_bezel.c`](../psxrecomp/runtime/src/mod_builtin_bezel.c),
  registered with `PSX_MOD_CONSTRUCTOR`.

**Mod packages cannot ship native code or shaders.** A format-5 `[[plugin]]`
id only *selects* an implementation already statically compiled into the
runtime (`psxrecomp/docs/MOD_PACKAGES.md`, "Trusted static plugins"). So there
is no path where a scanline shader arrives as a package dropped into
`mods/preloaded/` — the shader must land upstream first. This is the single
most important fact for anyone picking this up expecting a data-only mod.

Strength and beam width belong as mod resources, or as a `[video]` key
alongside `fmv_filter` — the existing precedent for a present-path enum
(`recompiler/src/config_loader.cpp:595`, `gl_renderer_set_fmv_filter`).

### Acceptance

Enhancement work still owes evidence. A screenshot is not enough:

- Scanline period matches the source line count at several window sizes and at
  both 240- and 480-class display heights.
- Mean luminance within a stated tolerance of the unfiltered present — the
  gamma claim, measured, not eyeballed.
- Off by default, and with the feature off the present path is byte-identical
  to today's output. The bezel mod holds the same line ("with the feature off,
  margins remain the normal black clear").
- No regression in `gl_present_ring`, the present instrumentation from
  framework R1 that caught the black-frame flicker.

### Sequencing

Upstream PR against `mstan/psxrecomp` → merged → gitlink bump here → enable in
`game.toml`. Do not fork the submodule to prototype; a local psxrecomp checkout
outside this repo is the right scratch space.

---

## E2 — Pause / hold-frame and frame advance

**Kind:** upstream framework change (host loop + one Vulkan present fix).
**Requested:** 2026-08-30. **Status:** designed, not built.

Goal: hold the image still so on-screen text can be read. BoF3 has scenes with
no in-game pause and dialogue that advances faster than it can be read, which
matters during localization review as much as during play.

### What exists today

There is **no dedicated pause hotkey, no frame advance, and no slow-motion.**
There is a turbo (speed-up) path but no fractional speed control.

There *are* two host-level guest freezes, both built for other features, and
both proving the mechanism this item needs:

| Hotkey | Feature | Loop | Overlay |
|---|---|---|---|
| **F7** (pad select+R1) | Save-state slot menu | `savestate_menu_host_pause_loop()` [`main.cpp:6111`](../psxrecomp/runtime/src/main.cpp) | Full slot panel — **covers the image** |
| **F8** (pad select+R3) | Rewind filmstrip | `rewind_host_pause_loop()` [`main.cpp:6070`](../psxrecomp/runtime/src/main.cpp) | Bottom filmstrip — mostly clear |

Both are modal `while (...) { SDL_PollEvent; ...; SDL_Delay(8); }` loops entered
from inside the vblank present body ([`main.cpp:6424`](../psxrecomp/runtime/src/main.cpp)),
so the guest is genuinely halted mid-vblank rather than throttled. The
save-state one is commented *"Freeze guest in vblank present while the
save-state slot menu is open"* — that is already the feature, minus a UI that
gets out of the way.

Keyboard defaults are registered in
[`host_keymap.c`](../psxrecomp/runtime/src/host_keymap.c) as
`HOST_KEYMAP_REWIND` (F8) and `HOST_KEYMAP_SAVE_STATE_MENU` (F7); pad binds are
`[hotkeys] hotkey_pad_rewind` / `hotkey_pad_save_state_menu`
(`config_loader.h:1231`). A pause action would be a third `HOST_KEYMAP_*` entry
in that enum, which is the cheap part.

**Workaround until then:** F8 rewind is the better of the two — the filmstrip
obscures least, and it scrubs. It is **off by default** and snapshots only every
15 frames, so it cannot hold a specific frame of text as shipped. Enable
`[video] rewind = true` and lower `rewind_interval` (accepts 1/4/8/12/15);
`rewind_depth` is 50–200. Each snap is ~3.5 MB (2 MB RAM + 1 MB VRAM + 512 KB
SPU RAM), so interval 4 / depth 200 buys ~13 s of scrollback at ~700 MB, and
interval 1 / depth 200 gives frame-exact scrubbing over only ~3.3 s. Env
`PSX_REWIND`, `PSX_REWIND_INTERVAL`, `PSX_REWIND_DEPTH` outrank the UI
([`psx_rewind.h`](../psxrecomp/runtime/include/psx_rewind.h)).

### The defect this would have to fix first

`rewind_pause_present()` ([`main.cpp:6049`](../psxrecomp/runtime/src/main.cpp))
is what both loops call to keep the window alive while frozen, and it does not
behave the same on all three backends:

- **OpenGL** — `gl_renderer_present_hold_last()`: re-presents the held frame.
- **Software** — re-copies the `s_sw_hold_*` texture: held frame.
- **Vulkan** — `vk_renderer_present_blank()`, which
  `vkCmdClearColorImage`s the swapchain to **black**
  ([`gpu_vk_renderer.c:1715`](../psxrecomp/runtime/src/gpu_vk_renderer.c)).

So on Vulkan the existing freezes show a black screen, not the paused image.
That is tolerable for a slot menu drawn over the top; it is fatal for a feature
whose entire purpose is *looking at the frozen frame*. A hold-frame pause
requires a real Vulkan hold-last present first. BoF3 ships `renderer = "opengl"`
(`game.toml:59`), so this does not block the title — but it blocks calling the
feature done upstream.

### Design

1. **Hold-frame pause** — a third pause loop, structurally the same as the two
   above, with no panel: hold the last frame, draw only a small OSD marker via
   the existing `host_osd_push()`. New `HOST_KEYMAP_PAUSE` action plus a pad
   bind alongside the other two.
2. **Frame advance** — while paused, one keypress runs exactly one vblank and
   re-freezes. This is the part that does *not* fall out of the existing loops:
   they hold the guest outside the scheduler, and stepping means re-entering it
   for a single quantum and coming back. Expect that to be where the real work
   is, and treat the netplay/rollback paths as out of scope (rewind already
   disables itself under `psx_netplay_active()`).
3. **Audio** — the existing loops leave the audio path untouched across an
   8 ms-polled freeze. Whatever a long pause does to the SPU sink needs to be
   checked rather than assumed; a pause held for a minute is not a case those
   two features exercise.
4. **Input guard** — both existing loops call `savestate_input_guard_arm()` on
   exit to swallow the still-held key so it does not bleed into the guest. A
   pause loop needs the same, and the tap-to-pause/tap-to-resume pattern makes
   it more likely to matter, not less.

### Acceptance

- Paused frame is the actual last frame on **all three backends** (the Vulkan
  fix above), verified by comparing the held present against the pre-pause
  frame.
- Frame advance steps exactly one vblank — verified against the frame counter,
  not by eye.
- Resume is clean: no input bleed, no dropped or duplicated guest frame.
- A multi-minute pause resumes without audio artifacts.
- Off-path when unused: with the hotkey never pressed, guest timing is
  unchanged.

### Sequencing

Cheaper than E1 and more useful during bringup, but it is still an upstream PR
(`mstan/psxrecomp`) followed by a gitlink bump. The Vulkan hold-last fix is
independently worth upstreaming and could go first as its own change.

---

## Backlog — ideas, not designs

Recorded so they are not re-derived. None has been costed or validated for
BoF3, and none should be read as planned.

| Idea | Kind | Note |
|---|---|---|
| Load-time reduction | config / builtin mod | `psx.enhancement.cd-speed` and `psx.enhancement.fast-loading` already ship in the framework. Mostly "enable and validate", not new code. |
| PGXP (geometry precision) | builtin mod | `psx.enhancement.pgxp` exists. Needs per-title validation — BoF3's mixed 2D/3D presentation is exactly where PGXP artifacts show up. |
| Widescreen | upstream + per-title | Framework has `WIDESCREEN.md` and native-wide GL support, but per-title UI grouping work is real. BoF3's 2D field maps make this a poor early candidate. |
| Bezel artwork | config only | `psx.presentation.bezel` ships today; the 4:3 pillarbox margins are where it applies. The one item here needing no code at all. |
| Overlay DLL cache for speed | — | **Not applicable.** BoF3's overlays are compiled statically from the disc (all ten bands + `LOGO.EXE`, ~99% native dispatch); `[runtime] overlay_cache` stays off by design. See [`OVERLAY_EXTRACTION.md`](OVERLAY_EXTRACTION.md). |

Enhancements that touch **text rendering** are deliberately excluded here — the
JP→EN work in [`LOCALIZATION.md`](LOCALIZATION.md) and
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) is bringup scope, not enhancement scope.
