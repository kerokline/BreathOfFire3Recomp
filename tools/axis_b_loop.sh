#!/usr/bin/env bash
#
# axis_b_loop.sh — one-shot Axis B data-gathering loop (steps 2-5 of HANDOFF.md).
#
# Run this AFTER a live build-dbg play session, with the game still up and its
# debug server listening (launch:  BreathOfFire3_Recompiled.exe --game game.toml
# --no-launcher --debug-port 4370). This script does NOT launch or play the game
# — a play session reaching new content is the one manual input the loop needs.
#
# The phases, straight from docs/HANDOFF.md "The next task":
#   2. harvest   — union this session's proven interpreted entry PCs into
#                  analysis/observed_interp_pcs.json; report how many are NEW.
#   2a. residency — area_poller.py harvest: snapshot the resident AREA script +
#                  drain the overlay native ring into analysis/area_timeline.jsonl
#                  (name evidence; see docs/NAME_MAP.md). One-shot — for a full
#                  per-area timeline run `area_poller.py watch` DURING play.
#   3. extract   — rebuild analysis/overlay_captures_all.json from the observed set.
#   4. hash      — regenerate overlay_codegen_hash.h BEFORE compiling overlays
#                  (skippable with --skip-hash when there was no framework bump).
#   5a. compile  — compile ALL bands together into generated/overlays_static.c.
#   5b. build    — rebuild the psx-runtime target.
#   6. maps      — refresh names/ sidecar from the new catalog and regenerate
#                  docs/subsystem_map.html (runs on every non-harvest-only path,
#                  including --skip-harvest).
#
# Convergence caveat (HANDOFF): repetition of already-seen content adds ~0 new
# PCs. If harvest reports 0 new, the rebuild is wasted work, so this script stops
# before it unless you pass --force. New areas/characters/battles are what add.
#
set -euo pipefail

# ---- config / defaults ------------------------------------------------------
PORT=4370
CUE="isos/Breath of Fire III (Japan).cue"
BUILD_DIR="build-dbg"
GCC="C:/msys64/mingw64/bin/gcc.exe"
MSYS_BIN="/c/msys64/mingw64/bin"          # cmake/ninja/gcc live here (env note)
OBSERVED="analysis/observed_interp_pcs.json"
CAPTURES="analysis/overlay_captures_all.json"
OVERLAY_C="generated/overlays_static.c"
RECOMPILER="build-recompiler/psxrecomp-game.exe"

SKIP_HARVEST=0
SKIP_HASH=0
HARVEST_ONLY=0
FORCE=0
PRUNE=1

usage() {
  cat <<'EOF'
Usage: tools/axis_b_loop.sh [options]

  --port N          debug port of the live session (default 4370)
  --cue PATH        disc .cue for extraction (default the Japan disc)
  --skip-harvest    start from extract; reuse the observed file as-is
  --harvest-only    run only the harvest phase, then stop
  --skip-hash       skip the codegen-hash rebuild (only safe with no framework bump)
  --force           rebuild even when harvest reports 0 new PCs
  --no-prune        keep build-dbg freeze dumps (default: prune them at the end)
  -h, --help        this text

Run it with the game still live on --port. See docs/HANDOFF.md.
EOF
}

# ---- arg parsing ------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --port)         PORT="$2"; shift 2 ;;
    --cue)          CUE="$2";  shift 2 ;;
    --skip-harvest) SKIP_HARVEST=1; shift ;;
    --harvest-only) HARVEST_ONLY=1; shift ;;
    --skip-hash)    SKIP_HASH=1; shift ;;
    --force)        FORCE=1; shift ;;
    --no-prune)     PRUNE=0; shift ;;
    -h|--help)      usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

# Run from repo root regardless of where the script was invoked.
cd "$(dirname "$0")/.."
export PATH="$MSYS_BIN:$PATH"
export PYTHONIOENCODING=utf-8   # tool banners use non-cp1252 glyphs

say() { printf '\n\033[1;36m=== %s ===\033[0m\n' "$*"; }
die() { printf '\n\033[1;31mFATAL: %s\033[0m\n' "$*" >&2; exit 1; }

# ---- preflight --------------------------------------------------------------
say "preflight"
[ -f game.toml ]        || die "not at repo root (no game.toml)"
[ -f "$CUE" ]           || die "disc not found: $CUE"
[ -x "$RECOMPILER" ]    || die "recompiler missing: $RECOMPILER (build emitters + generate first)"
[ -x "$GCC" ]           || die "gcc missing: $GCC"
[ -d "$BUILD_DIR" ]     || die "build tree missing: $BUILD_DIR (configure it first)"
command -v python >/dev/null || die "python not on PATH"
command -v cmake  >/dev/null || die "cmake not on PATH (MSYS2 mingw64 not exported?)"
echo "ok — cue='$CUE' port=$PORT build=$BUILD_DIR"

# ---- phase 2: harvest -------------------------------------------------------
NEW_PCS="(skipped)"
if [ "$SKIP_HARVEST" -eq 0 ]; then
  say "phase 2/5 — harvest (live session on port $PORT)"
  HARVEST_LOG="$(mktemp)"
  # harvest talks to the running game; a dead listener here is a real error.
  python tools/harvest_interp_pcs.py --port "$PORT" | tee "$HARVEST_LOG" \
    || die "harvest failed — is the game still running with --debug-port $PORT?"

  # Residency evidence for names/ (NAME_MAP.md). Off the build path: never fatal.
  say "phase 2a — residency snapshot (area + native ring → analysis/area_timeline.jsonl)"
  python tools/area_poller.py harvest --port "$PORT"     || echo "WARN: area_poller harvest failed — continuing (names evidence only)"

  # Parse "..., N new this session ..." to decide whether a rebuild is worth it.
  NEW_PCS="$(grep -oE '[0-9]+ new this session' "$HARVEST_LOG" | grep -oE '^[0-9]+' | head -1 || true)"
  rm -f "$HARVEST_LOG"
  [ -n "$NEW_PCS" ] || NEW_PCS="?"

  if [ "$HARVEST_ONLY" -eq 1 ]; then
    say "harvest-only: done ($NEW_PCS new PCs). Stopping before extract."
    echo "For a per-area timeline next session, run DURING play:"
    echo "  python tools/area_poller.py watch --port $PORT"
    exit 0
  fi

  if [ "$NEW_PCS" = "0" ] && [ "$FORCE" -eq 0 ]; then
    say "0 new PCs — nothing to add"
    echo "This session covered only already-seen content, so a rebuild would be"
    echo "wasted (~20 min). Play into NEW content and re-run, or pass --force to"
    echo "rebuild anyway. Observed set on disk is unchanged in substance."
    exit 0
  fi
else
  say "phase 2/5 — harvest SKIPPED (--skip-harvest); using $OBSERVED as-is"
fi
[ -f "$OBSERVED" ] || die "observed file missing: $OBSERVED"

# ---- phase 3: extract -------------------------------------------------------
say "phase 3/5 — extract all bands from observed set"
python tools/extract_overlays.py "$CUE" --out "$CAPTURES" \
  || die "extract_overlays failed"
[ -f "$CAPTURES" ] || die "extract produced no $CAPTURES"

# extract_overlays rebuilds $CAPTURES from .EMI sections only, so it drops the
# LOGO.EXE overlay (a separate PS-EXE at 0x801CE000, the opening/Capcom logo
# player — root-caused 2026-09-01). Re-merge it every run or the compiled logo
# player silently reverts to interpreted (~19fps Capcom lag). Idempotent.
say "phase 3a — merge LOGO.EXE overlay into captures"
python tools/extract_logo_overlay.py "$CUE" \
  --out analysis/logo_capture.json --append-to "$CAPTURES" \
  || die "extract_logo_overlay failed"

# ---- phase 3b: refresh the overlay catalog (sidecar) ------------------------
# Pure derived view over captures + observed + survey; a full OVERWRITE is
# correct because the cross-session accumulation already lives in the observed
# file (union-only). Non-fatal: a sidecar hiccup must never cost the rebuild.
say "phase 3b — refresh overlay catalog (sidecar)"
python tools/overlay_catalog.py --top 10 \
  || echo "WARN: overlay_catalog refresh failed — continuing, sidecar is off the build path"

# ---- phase 4: codegen hash --------------------------------------------------
# Must precede overlay compile, or the stale-recompiler guard trips FATAL. It is
# a runtime build step; harmless no-op when nothing changed.
if [ "$SKIP_HASH" -eq 0 ]; then
  say "phase 4/5 — regenerate overlay_codegen_hash.h"
  cmake --build "$BUILD_DIR" --target psxrecomp_codegen_hash \
    || die "codegen-hash target failed"
else
  say "phase 4/5 — codegen hash SKIPPED (--skip-hash)"
fi

# ---- phase 5a: compile overlays (all bands, one file) -----------------------
# Exit 2 is EXPECTED: a few shards fail audit as UNSUPPORTED_INSTRUCTION (data
# walked as code). Only OTHER failure classes are a real regression.
say "phase 5a/5 — compile all overlay bands"
OVERLAY_MTIME_BEFORE=$(stat -c %Y "$OVERLAY_C" 2>/dev/null || echo 0)
COMPILE_LOG="$(mktemp)"
set +e
python psxrecomp/tools/compile_overlays.py --static --force \
  --captures "$CAPTURES" --game-toml game.toml \
  --recompiler "$RECOMPILER" \
  --runtime-include psxrecomp/runtime/include \
  --out-dir generated --gcc "$GCC" --cps 2>&1 | tee "$COMPILE_LOG"
COMPILE_RC=${PIPESTATUS[0]}
set -e

# A shard audit failure is EXPECTED when it is the documented "data walked as
# code" case: class [audit], ZERO unknown_bad, only <N> unsupported (MIPS-II/IV
# opcodes the R3000A lacks). That count drifts UP as the observed set grows into
# new data regions — not a regression (HANDOFF). A REAL regression is any
# SHARD FAIL that is not that shape: a non-audit class, or unknown_bad > 0.
UNEXPECTED_FAILS="$(grep -E 'SHARD FAIL ' "$COMPILE_LOG" \
  | grep -vE '\[audit\] overlay 0x[0-9A-Fa-f]+ crc [0-9A-Fa-f]+: 0 unknown_bad, [0-9]+ unsupported' \
  || true)"
SHARD_RESULT="$(grep -E 'PSX_SHARD_RESULT' "$COMPILE_LOG" | tail -1 || true)"
rm -f "$COMPILE_LOG"

if [ -n "$UNEXPECTED_FAILS" ]; then
  echo "$UNEXPECTED_FAILS" >&2
  die "overlay compile had non-UNSUPPORTED_INSTRUCTION shard failures (see above) — a real regression, not the expected exit-2"
fi
if [ "$COMPILE_RC" -ne 0 ] && [ "$COMPILE_RC" -ne 2 ]; then
  die "overlay compile exited $COMPILE_RC (not the expected 0 or 2)"
fi

# The output file must have been (re)written.
OVERLAY_MTIME_AFTER=$(stat -c %Y "$OVERLAY_C" 2>/dev/null || echo 0)
[ "$OVERLAY_MTIME_AFTER" -gt "$OVERLAY_MTIME_BEFORE" ] \
  || die "$OVERLAY_C was not rewritten — overlay compile did not produce output"
echo "overlays ok — ${SHARD_RESULT:-(no PSX_SHARD_RESULT line)} (exit $COMPILE_RC, expected UNSUPPORTED_INSTRUCTION only)"

# ---- phase 5b: build runtime ------------------------------------------------
say "phase 5b/5 — build psx-runtime"
cmake --build "$BUILD_DIR" --target psx-runtime \
  || die "psx-runtime build failed. If it failed at LINK with undefined func_*, the shard count changed and $BUILD_DIR needs a CMake reconfigure."

# ---- phase 6: names sidecar + subsystem map ---------------------------------
# Derived views over the refreshed catalog. name_map init is a MERGE (hand edits
# survive); subsystem_map is a full regenerate. Off the build path: never fatal.
say "phase 6 — refresh names/ sidecar + docs/subsystem_map.html"
MAPS_OK=1
python tools/name_map.py init && python tools/name_map.py check   || { echo "WARN: name_map init/check failed"; MAPS_OK=0; }
python tools/subsystem_map.py   || { echo "WARN: subsystem_map failed"; MAPS_OK=0; }
[ "$MAPS_OK" -eq 1 ] || echo "WARN: maps not refreshed — rerun phase 6 by hand (docs/NAME_MAP.md)"

# ---- housekeeping -----------------------------------------------------------
if [ "$PRUNE" -eq 1 ]; then
  say "pruning freeze dumps"
  rm -f "$BUILD_DIR"/psx_freeze_dump_*.json 2>/dev/null || true
fi

say "DONE"
echo "new PCs banked this session : $NEW_PCS"
echo "captures                    : $CAPTURES"
echo "overlay source              : $OVERLAY_C"
echo "subsystem map               : docs/subsystem_map.html (refreshed=$MAPS_OK)"
echo
echo "Next: relaunch build-dbg and RE-MEASURE per-PC —"
echo "  BreathOfFire3_Recompiled.exe --game game.toml --no-launcher --debug-port $PORT"
echo "  python tools/harvest_interp_pcs.py --port $PORT"
echo "Never infer success from static_hits aggregates (see HANDOFF §9)."
