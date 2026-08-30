# BoF3 enhancements — post-faithfulness work

**Status:** IN PROGRESS (established 2026-08-30) — *design only, nothing
implemented.* No item here is scheduled. This file exists so ideas raised
during bringup are recorded with their real cost instead of being re-derived
later.

## The gate

Framework rule (`psxrecomp/CLAUDE.md`, inherited via `/CLAUDE.md`): **no
per-game hacks during foundation work.** Enhancements become legitimate only
after the faithful core is proven. BoF3 is not there — see
[`STATUS.md`](STATUS.md). Nothing in this file should be started before the
title boots and soaks clean.

A second constraint shapes every item below: `psxrecomp/` and `recomp-ui/` are
**read-only submodules**. Anything that needs runtime or renderer code is an
upstream `mstan/psxrecomp` change plus a deliberate gitlink bump here — it
cannot be done from inside this repo. That distinction is the difference
between a config edit and a multi-backend shader PR, so each item names which
it is.

**Verified against** psxrecomp `a91884a4` (the checked-out submodule tree; note
the committed gitlink is `f24b7e5d` — re-verify the line numbers below if that
gap has since been closed).

---

## E1 — CRT scanlines / display filter

**Kind:** upstream framework change (GL + Vulkan + SW present paths).
**Requested:** 2026-08-30. **Status:** designed, not built.

Goal: reproduce the horizontal line structure a CRT gave PSX output, as a
presentation-only effect. Guest rendering is untouched; this is a pass over the
finished display image on its way to the window.

### What exists today

Nothing. A tree-wide grep for `scanline` / `crt` / post-process over
`psxrecomp/` returns only rasterizer vocabulary (`gpu_sw_renderer.c` triangle
fills), per-scanline VRAM dirty tracking (`gpu_vram_dirty.h`), and FMV depth24
row conversion. There is no post-processing stage of any kind.

What *does* exist is the hook the effect belongs in. The GL present is a
full-screen fragment shader, `PRESENT_FS` at
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

## Backlog — ideas, not designs

Recorded so they are not re-derived. None has been costed or validated for
BoF3, and none should be read as planned.

| Idea | Kind | Note |
|---|---|---|
| Load-time reduction | config / builtin mod | `psx.enhancement.cd-speed` and `psx.enhancement.fast-loading` already ship in the framework. Mostly "enable and validate", not new code. |
| PGXP (geometry precision) | builtin mod | `psx.enhancement.pgxp` exists. Needs per-title validation — BoF3's mixed 2D/3D presentation is exactly where PGXP artifacts show up. |
| Widescreen | upstream + per-title | Framework has `WIDESCREEN.md` and native-wide GL support, but per-title UI grouping work is real. BoF3's 2D field maps make this a poor early candidate. |
| Bezel artwork | config only | `psx.presentation.bezel` ships today; the 4:3 pillarbox margins are where it applies. The one item here needing no code at all. |
| Overlay DLL cache for speed | config + capture work | `[runtime] overlay_cache`. Correctness-only benefit upstream so far (see `psxrecomp/docs/overlay-status.md`); speed needs broad overlay coverage, and BoF3 has no overlay map yet. |

Enhancements that touch **text rendering** are deliberately excluded here — the
JP→EN work in [`LOCALIZATION.md`](LOCALIZATION.md) and
[`TEXT_ENGINE.md`](TEXT_ENGINE.md) is bringup scope, not enhancement scope.
