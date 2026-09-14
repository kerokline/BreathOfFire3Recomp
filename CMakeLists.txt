cmake_minimum_required(VERSION 3.20)
set(PSXRECOMP_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/psxrecomp" CACHE PATH
    "Path to psxrecomp")
if(NOT EXISTS "${PSXRECOMP_ROOT}/runtime/runtime.cmake")
    message(FATAL_ERROR
        "PSXRecomp runtime is missing: ${PSXRECOMP_ROOT}/runtime/runtime.cmake\n"
        "This project expects the psxrecomp framework checkout at ${PSXRECOMP_ROOT}.\n"
        "Run: git submodule update --init --recursive\n"
        "If psxrecomp/ is not a submodule, set -DPSXRECOMP_ROOT=<path-to-psxrecomp>.")
endif()

project(BreathOfFire3Recomp LANGUAGES C CXX)

# --- Opt-in product surfaces (OFF by default in the framework) -------------
# Scaffold prompts / flags fill these. Without recomp-ui, PSX_RECOMP_UI is OFF.
# Setup-host CI requires WIZARD_CMAKE_BLOCK / ENABLE_SETUP_WIZARD (FORCE_SETUP_HOST
# alone does not open first-run / Generate & rebuild).
# recomp-ui submodule present (PSX_RECOMP_UI defaults ON).
# Full netplay UI -- enable after adding recomp-ui + testing:
# if(EXISTS "${PSXRECOMP_ROOT}/lib/recomp-net/CMakeLists.txt")
#     set(PSX_NETPLAY ON CACHE BOOL "..." FORCE)
# endif()
set(PSX_SETUP_WIZARD ON CACHE BOOL
    "Advertise first-run setup wizard + Generate & rebuild in recomp-ui" FORCE)
include("${PSXRECOMP_ROOT}/runtime/runtime.cmake")

psxrecomp_add_game_runtime(psx-runtime
    # ENABLE_NETPLAY_IF_PRESENT
    # NETPLAY_LOBBY_URL ws://netplay.retcomm.net:8765
    ENABLE_SETUP_WIZARD
    WINDOW_TITLE "BreathOfFire3 Recompiled"
    DEFAULT_GAME_CONFIG_PATH "game.toml"
    MAX_PLAYERS 1
    # Reviewed, default-off packages staged to <exe-dir>/mods/bundled on every
    # build (psxrecomp/docs/MOD_PACKAGES.md "How bundled/ gets staged").
    PRELOADED_MODS_DIR "${CMAKE_CURRENT_SOURCE_DIR}/mods/preloaded"
    LAUNCHER_BOXART "${CMAKE_CURRENT_SOURCE_DIR}/launcher_assets/img/boxart.tga"
    APP_ICON "${CMAKE_CURRENT_SOURCE_DIR}/assets/psxrecomp.ico"
    # Layer B: overlays statically extracted from the disc's .EMI containers
    # (docs/OVERLAYS.md). Forwarded through UNPARSED_ARGUMENTS to
    # psxrecomp_add_runtime_target, so it must NOT follow a multi-value keyword
    # such as GEN_FULL_GLOB -- cmake_parse_arguments would swallow it into that
    # list and PSX_HAS_OVERLAY_DISPATCH would silently stay undefined.
    GAME_OVERLAY_STATIC_C "${CMAKE_CURRENT_SOURCE_DIR}/generated/overlays_static.c"
    GEN_MARKER "generated/SLPS_009.90_dispatch.c"
    GEN_FULL_GLOB "generated/SLPS_009.90_full_*.c"
    CODEGEN_SETUP_SOURCES "${CMAKE_CURRENT_SOURCE_DIR}/codegen_setup.c"
)

# Stage runtime configs next to the exe for direct build/ launches. Only copy
# files that exist — never fail POST_BUILD when game_options.toml is absent.
foreach(_PSX_RUNTIME_CONFIG game.toml game_options.toml)
    if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}")
        add_custom_command(TARGET psx-runtime POST_BUILD
            COMMAND ${CMAKE_COMMAND} -E copy_if_different
                "${CMAKE_CURRENT_SOURCE_DIR}/${_PSX_RUNTIME_CONFIG}"
                "$<TARGET_FILE_DIR:psx-runtime>/${_PSX_RUNTIME_CONFIG}"
            COMMENT "Staging ${_PSX_RUNTIME_CONFIG}"
            VERBATIM)
    endif()
endforeach()

# Split the DWARF out of the exe into a sidecar (docs/STATUS.md 2026-09-11).
# With generated/ past 2 GB the RelWithDebInfo link carries ~860 MB of
# .debug_* sections; mingw ld maps them into the image, SizeOfImage passes
# 1.9 GiB and Windows refuses to load the exe ("not a valid Win32
# application"). The code is unchanged -- only the debug sections move to
# <exe>.debug next to it, linked back with .gnu_debuglink so gdb (the FMV
# bench sampler) and addr2line (freeze_heartbeat RVAs) still find symbols.
# Release / MinSizeRel carry no DWARF and skip this; set
# -DPSX_SPLIT_DEBUG=OFF to keep a single file.
if(CMAKE_BUILD_TYPE MATCHES "Debug|RelWithDebInfo")
    set(_PSX_SPLIT_DEBUG_DEFAULT ON)
else()
    set(_PSX_SPLIT_DEBUG_DEFAULT OFF)
endif()
option(PSX_SPLIT_DEBUG
    "Move the runtime exe's DWARF into <exe>.debug after linking (keeps the image loadable)"
    ${_PSX_SPLIT_DEBUG_DEFAULT})
if(PSX_SPLIT_DEBUG)
    if(NOT CMAKE_OBJCOPY)
        message(FATAL_ERROR "PSX_SPLIT_DEBUG needs objcopy (CMAKE_OBJCOPY is unset)")
    endif()
    add_custom_command(TARGET psx-runtime POST_BUILD
        COMMAND "${CMAKE_OBJCOPY}" --only-keep-debug
            "$<TARGET_FILE:psx-runtime>" "$<TARGET_FILE:psx-runtime>.debug"
        COMMAND "${CMAKE_OBJCOPY}" --strip-debug
            "--add-gnu-debuglink=$<TARGET_FILE:psx-runtime>.debug"
            "$<TARGET_FILE:psx-runtime>"
        COMMENT "Splitting DWARF into $<TARGET_FILE_NAME:psx-runtime>.debug (PSX_SPLIT_DEBUG)"
        VERBATIM)
endif()

# EXP / zenny multiplier plugin (docs/EXP_BOOST.md): trusted static plugin
# selected by mods/preloaded/packages/bof3.exp-boost; hook PCs are the
# BATL_END entries in game.toml mod_function_entry_funcs. Always built --
# it is inert until the launcher enables a feature.
target_sources(psx-runtime PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src/bof3_exp_boost.c")

# Script localization plugin (docs/LOCALIZATION_APPLY.md). The tables are
# generated locally into generated/bof3_xlate_<code>.c -- English by
# tools/build_script_xlate.py from the player's US disc, Japanese (Ruby) by
# tools/build_ruby_script.py from the JP disc -- exactly like the game C:
# never committed, never shipped by CI. Each table found defines
# BOF3_XLATE_HAVE_<CODE> for the plugin, on that one source only (a
# target-wide definition or include dir would recompile every overlay
# object). Without any table the plugin is not built at all, and the hook
# site in the generated C calls into an empty plugin registry (a no-op).
file(GLOB _BOF3_XLATE_TABLES CONFIGURE_DEPENDS
     "${CMAKE_CURRENT_SOURCE_DIR}/generated/bof3_xlate_*.c")
# A Ruby language may also carry a runtime-insert table (item / ability
# names with readings, generated/bof3_insert_<code>.c, docs/INSERT_RUBY.md);
# BOF3_INSERT_HAVE_<CODE> tells the plugin which languages have one.
file(GLOB _BOF3_INSERT_TABLES CONFIGURE_DEPENDS
     "${CMAKE_CURRENT_SOURCE_DIR}/generated/bof3_insert_*.c")
if(_BOF3_XLATE_TABLES)
    set(_BOF3_XLATE_DEFS)
    foreach(_t IN LISTS _BOF3_XLATE_TABLES)
        get_filename_component(_n "${_t}" NAME_WE)
        string(REPLACE "bof3_xlate_" "" _code "${_n}")
        string(TOUPPER "${_code}" _CODE)
        list(APPEND _BOF3_XLATE_DEFS "BOF3_XLATE_HAVE_${_CODE}")
        message(STATUS "BoF3: script table '${_code}' (${_n}.c)")
    endforeach()
    foreach(_t IN LISTS _BOF3_INSERT_TABLES)
        get_filename_component(_n "${_t}" NAME_WE)
        string(REPLACE "bof3_insert_" "" _code "${_n}")
        string(TOUPPER "${_code}" _CODE)
        list(APPEND _BOF3_XLATE_DEFS "BOF3_INSERT_HAVE_${_CODE}")
        message(STATUS "BoF3: insert table '${_code}' (${_n}.c)")
    endforeach()
    target_sources(psx-runtime PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/src/bof3_localize.c"
        ${_BOF3_XLATE_TABLES} ${_BOF3_INSERT_TABLES})
    set_source_files_properties(
        "${CMAKE_CURRENT_SOURCE_DIR}/src/bof3_localize.c"
        ${_BOF3_XLATE_TABLES} ${_BOF3_INSERT_TABLES}
        PROPERTIES INCLUDE_DIRECTORIES "${CMAKE_CURRENT_SOURCE_DIR}/src")
    set_source_files_properties(
        "${CMAKE_CURRENT_SOURCE_DIR}/src/bof3_localize.c"
        PROPERTIES COMPILE_DEFINITIONS "${_BOF3_XLATE_DEFS}")
else()
    message(STATUS "BoF3: no generated/bof3_xlate_*.c; script localization plugin not built")
endif()
