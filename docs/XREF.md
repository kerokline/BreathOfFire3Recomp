# Address cross-reference (`docs/` prose → the naming layer)

**Status:** STABLE (generated). Regenerate with `python tools/xref.py index --out docs/XREF.md` after editing docs, `symbols.toml` or `names/`; never hand-edit.

Every `0x80xxxxxx` literal cited in `docs/*.md`, joined to what the naming layer claims about it. An address alone does not say whether it is code or data (81.6% of `.text` is overlay zero fill, and named data shares addresses with sibling code — `DATA_ISLANDS.md`), and one address can resolve to several overlay functions because bands share load addresses (`AREA_PCS.md`). Unnamed is not a defect: most cited addresses are RAM variables, which `symbols.toml` has no table for.

973 distinct addresses · 147 resolve to a name · 826 do not.

| Address | Region | Identity | Cited by |
|---|---|---|---|
| `0x80000000` | kernel | kernel_area (base) | `ADDRESS_MAPS.md`, `HANDOFF.md` |
| `0x800000A0` | kernel | in kernel_area +0xA0 | `OVERLAYS.md`, `STATUS.md` |
| `0x800027AC` | kernel | in kernel_area +0x27AC | `OVERLAY_HEADERS.md` |
| `0x80003554` | kernel | in kernel_area +0x3554 | `OVERLAY_HEADERS.md` |
| `0x80010000` | pre-text | area_script_block [message pool] (base) | `ADDRESS_MAPS.md`, `FURIGANA.md`, `HANDOFF.md`, `IDEAS.md`, `LOCALIZATION.md`, `LOCALIZATION_APPLY.md`, `NAME_MAP.md`, `OVERLAYS.md`, `README.md`, `STATUS.md`, `TEXT_ENGINE.md`, `TEXT_TABLES.md`, `regional-builds.md`, `us-build-trial.md` |
| `0x80010004` | pre-text | in area_script_block [message pool] +0x4 | `LOCALIZATION.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80010008` | pre-text | in area_script_block [message pool] +0x8 | `IDEAS.md` |
| `0x800102A7` | pre-text | in area_script_block [message pool] +0x2A7 | `IDEAS.md` |
| `0x80010371` | pre-text | in area_script_block [message pool] +0x371 | `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80013FFF` | pre-text | in area_script_block [message pool] +0x3FFF | `LOCALIZATION.md`, `TEXT_ENGINE.md` |
| `0x80014000` | pre-text | system_message_block [message pool] (base) | `ADDRESS_MAPS.md`, `FURIGANA.md`, `HANDOFF.md`, `IDEAS.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md`, `TEXT_TABLES.md`, `loader_records/BOSS.md`, `regional-builds.md`, `us-build-trial.md` |
| `0x80014004` | pre-text | in system_message_block [message pool] +0x4 | `TEXT_ENGINE.md` |
| `0x80014A86` | pre-text | in system_message_block [message pool] +0xA86 | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x8001525C` | pre-text | in system_message_block [message pool] +0x125C | `TEXT_ENGINE.md`, `TEXT_TABLES.md` |
| `0x80017628` | pre-text | unknown | `ADDRESS_MAPS.md`, `FURIGANA.md`, `HANDOFF.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x8001A000` | pre-text | unknown | `regional-builds.md`, `us-build-trial.md` |
| `0x8002A000` | pre-text | unknown | `regional-builds.md` |
| `0x8002BA08` | pre-text | unknown | `GHIDRA.md` |
| `0x8002BE00` | pre-text | unknown | `HANDOFF.md`, `STATUS.md`, `TEXT_TABLES.md`, `regional-builds.md` |
| `0x8002D800` | pre-text | unknown | `regional-builds.md` |
| `0x8002EE00` | pre-text | unknown | `loader_records/BOSS.md` |
| `0x80032000` | pre-text | unknown | `regional-builds.md` |
| `0x80033800` | pre-text | unknown | `EMI_TYPES.md`, `README.md`, `STATUS.md`, `loader_records/PLCHAR.md` |
| `0x80033E00` | pre-text | unknown | `regional-builds.md` |
| `0x80035800` | pre-text | unknown | `regional-builds.md` |
| `0x80093000` | pre-text | unknown | `GHIDRA.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80093800` | text | boot EXE load address (disc_probe.json) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `BATTLE_RAM.md`, `BRINGUP.md`, `GHIDRA.md`, `HANDOFF.md`, `INVENTORY.md`, `LOCALIZATION.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `TEXT_ENGINE.md`, `loader_records/BOSS.md`, `loader_records/PLCHAR.md`, `regional-builds.md`, `remote-plan-2026-09-05.md`, `zero-fill-dispatch-audit.md` |
| `0x80093801` | text | in band_80093800 [overlay band] +0x1 | `ADDRESS_MAPS.md`, `OVERLAYS.md`, `STATUS.md` |
| `0x80093A74` | text | in band_80093800 [overlay band] +0x274 | `STATUS.md` |
| `0x80093B24` | text | Attack_TargetSetup [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80093E14` | text | Cmd_ConfirmAttack [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80093F00` | text | ≤ Cmd_ConfirmAttack (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0xEC (nearest below, span unknown) | `STATUS.md` |
| `0x80093FBC` | text | SkillMenu_Open [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x8009404C` | text | SkillMenu_Confirm [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80094768` | text | Skill_TargetSetup [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x8009521C` | text | Cmd_ConfirmWatch [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x800953D0` | text | ItemMenu_Open [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80095418` | text | ItemMenu_Confirm [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80095F9C` | text | ItemMenu_Reserve [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80096000` | text | ≤ ItemMenu_Reserve (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x64 (nearest below, span unknown) | `LOCALIZATION.md`, `regional-builds.md` |
| `0x80096800` | text | ≤ ItemMenu_Reserve (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x864 (nearest below, span unknown) | `LOCALIZATION.md`, `regional-builds.md` |
| `0x80098278` | text | Escape_Roll [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80098450` | text | Escape_Begin [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x800987F0` | text | Escape_Failed [hypothesis] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80098BB0` | text | EnemyAI_TurnCheck [hypothesis] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x80098F8C` | text | EnemyAI_ChooseActions [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md` |
| `0x8009A160` | text | Effect_ApplyResult [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md`, `GHIDRA.md`, `HANDOFF.md`, `STATUS.md` |
| `0x8009A3E4` | text | ≤ Effect_ApplyResult (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x284 (nearest below, span unknown) | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x8009A608` | text | ≤ Effect_ApplyResult (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x4A8 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x8009A6F8` | text | ≤ Effect_ApplyResult (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x598 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x8009FA78` | text | in band_80093800 [overlay band] +0xC278 | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x800A0680` | text | in band_80093800 [overlay band] +0xCE80 | `BATTLE_RAM.md`, `GHIDRA.md` |
| `0x800A783C` | text | in band_80093800 [overlay band] +0x1403C | `BATTLE_RAM.md` |
| `0x800A79AC` | text | Formation_ApplyStatMods [hypothesis] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x800A8AD4` | text | Battle_InitEncounterKind [hypothesis] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `GHIDRA.md`, `STATUS.md`, `loader_records/BOSS.md`, `remote-plan-2026-09-05.md` |
| `0x800A8AF8` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x24 (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A8B10` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x3C (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A8B40` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x6C (nearest below, span unknown) | `LOADER_RECORDS.md` |
| `0x800A8B58` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x84 (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A8B60` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x8C (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A8E8C` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x3B8 (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A8ED0` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x3FC (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A8F4C` | text | ≤ Battle_InitEncounterKind (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x478 (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x800A9FA4` | text | in band_80093800 [overlay band] +0x167A4 | `BATTLE_RAM.md` |
| `0x800AAF44` | text | in band_80093800 [overlay band] +0x17744 | `OVERLAY_HEADERS.md` |
| `0x800AB120` | text | Magic_LoadForAbility [verified] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x800AB160` | text | ≤ Magic_LoadForAbility (overlay BATTLE (BIN/BATTLE/BATTLE.EMI#15)) +0x40 (nearest below, span unknown) | `OVERLAY_HEADERS.md` |
| `0x800AB1FC` | text | Magic_LoadForItem [evidence] in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x800B1430` | text | in band_80093800 [overlay band] +0x1DC30 | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x800B1438` | text | in band_80093800 [overlay band] +0x1DC38 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x800B164C` | text | in band_80093800 [overlay band] +0x1DE4C | `BATTLE_RAM.md`, `STATUS.md` |
| `0x800B165C` | text | in band_80093800 [overlay band] +0x1DE5C | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md` |
| `0x800B19A4` | text | in band_80093800 [overlay band] +0x1E1A4 | `OVERLAY_HEADERS.md` |
| `0x800B19A8` | text | in band_80093800 [overlay band] +0x1E1A8 | `OVERLAY_HEADERS.md` |
| `0x800B2048` | text | in band_80093800 [overlay band] +0x1E848 | `ADDRESS_MAPS.md`, `HANDOFF.md`, `LOADER_RECORDS.md`, `README.md`, `STATUS.md`, `loader_records/BOSS.md` |
| `0x800B3450` | text | Magic_AbilityRow (struct) in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `HANDOFF.md`, `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x800B3538` | text | Magic_EffectTable (struct) in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `HANDOFF.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/SCENARIO.md` |
| `0x800B39F0` | text | Magic_ItemSubTables (pointer table) in BATTLE (BIN/BATTLE/BATTLE.EMI#15) | `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x800B3A00` | text | in band_80093800 [overlay band] +0x20200 | `OVERLAY_HEADERS.md` |
| `0x800B3A64` | text | in band_80093800 [overlay band] +0x20264 | `OVERLAY_HEADERS.md` |
| `0x800B3AC0` | text | in band_80093800 [overlay band] +0x202C0 | `OVERLAY_HEADERS.md` |
| `0x800B3B08` | text | in band_80093800 [overlay band] +0x20308 | `OVERLAY_HEADERS.md` |
| `0x800B4003` | text | in band_80093800 [overlay band] +0x20803 | `HANDOFF.md`, `OVERLAY_EXTRACTION.md` |
| `0x800C1800` | text | band_800C1800 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `BATTLE_RAM.md`, `HANDOFF.md`, `LOADER_RECORDS.md`, `NAME_MAP.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x800C1801` | text | in band_800C1800 [overlay band] +0x1 | `OVERLAYS.md`, `zero-fill-dispatch-audit.md` |
| `0x800C1CC0` | text | Boss021_HandlerTable (pointer table) in Boss battle script 021 (BIN/BOSS/BOSS021.EMI#16) | `DATA_ISLANDS.md` |
| `0x800C1E50` | text | engine loader entry: boss 1 boss in Boss battle script 001 (BIN/BOSS/BOSS001.EMI#13) | `loader_records/BOSS.md` |
| `0x800C1EA8` | text | engine loader entry: boss 34 boss in Boss battle script 034 (BIN/BOSS/BOSS034.EMI#16) | `loader_records/BOSS.md` |
| `0x800C1F60` | text | in band_800C1800 [overlay band] +0x760 | `loader_records/BOSS.md` |
| `0x800C2020` | text | in band_800C1800 [overlay band] +0x820 | `loader_records/BOSS.md` |
| `0x800C207C` | text | in band_800C1800 [overlay band] +0x87C | `loader_records/BOSS.md` |
| `0x800C2274` | text | in band_800C1800 [overlay band] +0xA74 | `loader_records/BOSS.md` |
| `0x800C2324` | text | engine loader entry: boss 41 boss in Boss battle script 034 (BIN/BOSS/BOSS034.EMI#16) | `loader_records/BOSS.md` |
| `0x800C23F8` | text | engine loader entry: boss 19 boss in Boss battle script 018 (BIN/BOSS/BOSS018.EMI#16) | `loader_records/BOSS.md` |
| `0x800C2488` | text | engine loader entry: boss 55 boss in Boss battle script 055 (BIN/BOSS/BOSS055.EMI#16) | `loader_records/BOSS.md` |
| `0x800C2588` | text | in band_800C1800 [overlay band] +0xD88 | `loader_records/SCENARIO.md` |
| `0x800C2680` | text | in band_800C1800 [overlay band] +0xE80 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x800C26DC` | text | engine loader entry: boss 20 boss in Boss battle script 018 (BIN/BOSS/BOSS018.EMI#16) | `loader_records/BOSS.md` |
| `0x800C2800` | text | in band_800C1800 [overlay band] +0x1000 | `loader_records/BOSS.md` |
| `0x800C2B00` | text | in band_800C1800 [overlay band] +0x1300 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x800D3800` | text | in band_800C1800 [overlay band] +0x12000 | `OVERLAYS.md`, `regional-builds.md` |
| `0x800DCD40` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x800E3800` | text | in band_800C1800 [overlay band] +0x22000 | `IDEAS.md`, `OVERLAYS.md`, `loader_records/BOSS.md` |
| `0x800E4000` | text | in band_800C1800 [overlay band] +0x22800 | `LOADER_RECORDS.md`, `loader_records/BOSS.md`, `regional-builds.md` |
| `0x800E407C` | text | in band_800C1800 [overlay band] +0x2287C | `BATTLE_RAM.md`, `STATUS.md` |
| `0x800E4800` | text | in band_800C1800 [overlay band] +0x23000 | `OVERLAY_HEADERS.md` |
| `0x800E7000` | text | in band_800C1800 [overlay band] +0x25800 | `OVERLAY_EXTRACTION.md` |
| `0x800E7CF0` | text | in band_800C1800 [overlay band] +0x264F0 | `STATUS.md` |
| `0x800F0800` | text | in band_800C1800 [overlay band] +0x2F000 | `loader_records/BOSS.md` |
| `0x800F5000` | text | band_800F5000 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `LOCALIZATION.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_SIZE.md`, `loader_records/AREA.md`, `zero-fill-dispatch-audit.md` |
| `0x800F5001` | text | in band_800F5000 [overlay band] +0x1 | `OVERLAYS.md` |
| `0x80104000` | text | in band_800F5000 [overlay band] +0xF000 | `IDEAS.md`, `OVERLAYS.md` |
| `0x80117000` | text | band_80117000 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `HANDOFF.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `STATUS.md`, `band-overlap-attribution.md`, `loader_records/SCENARIO.md` |
| `0x80117001` | text | in band_80117000 [overlay band] +0x1 | `OVERLAYS.md`, `zero-fill-dispatch-audit.md` |
| `0x8011CD40` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x80142A2C` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x80143B90` | text | in band_80117000 [overlay band] +0x2CB90 | `STATUS.md` |
| `0x80143BB0` | text | in band_80117000 [overlay band] +0x2CBB0 | `STATUS.md`, `TEXT_ENGINE.md`, `WORLD_ITEMS.md` |
| `0x80143F00` | text | in band_80117000 [overlay band] +0x2CF00 | `ADDRESS_MAPS.md`, `BATTLE_RAM.md`, `LOADER_RECORDS.md`, `LOCALIZATION_APPLY.md`, `OVERLAY_HEADERS.md`, `SAVE_IMPORT.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x80143F02` | text | in band_80117000 [overlay band] +0x2CF02 | `loader_records/AREA.md` |
| `0x80143F04` | text | in band_80117000 [overlay band] +0x2CF04 | `loader_records/AREA.md` |
| `0x80143F10` | text | in band_80117000 [overlay band] +0x2CF10 | `LOADER_RECORDS.md`, `loader_records/AREA.md` |
| `0x80143F14` | text | in band_80117000 [overlay band] +0x2CF14 | `loader_records/AREA.md` |
| `0x80143F18` | text | in band_80117000 [overlay band] +0x2CF18 | `loader_records/AREA.md` |
| `0x80143F1C` | text | in band_80117000 [overlay band] +0x2CF1C | `loader_records/AREA.md` |
| `0x80143F2C` | text | in band_80117000 [overlay band] +0x2CF2C | `STATUS.md` |
| `0x80144000` | text | in band_80117000 [overlay band] +0x2D000 | `WORLD_ITEMS.md` |
| `0x801448D4` | text | in band_80117000 [overlay band] +0x2D8D4 | `BATTLE_RAM.md`, `STATUS.md`, `loader_records/SCENARIO.md`, `remote-plan-2026-09-05.md` |
| `0x801448F8` | text | in band_80117000 [overlay band] +0x2D8F8 | `loader_records/AREA.md` |
| `0x80144944` | text | in band_80117000 [overlay band] +0x2D944 | `BATTLE_RAM.md` |
| `0x8014494E` | text | in band_80117000 [overlay band] +0x2D94E | `BATTLE_RAM.md` |
| `0x80144963` | text | in band_80117000 [overlay band] +0x2D963 | `INSERT_RUBY.md`, `TEXT_ENGINE.md` |
| `0x80144964` | text | in band_80117000 [overlay band] +0x2D964 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x8014496C` | text | in band_80117000 [overlay band] +0x2D96C | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x80144972` | text | in band_80117000 [overlay band] +0x2D972 | `BATTLE_RAM.md` |
| `0x80144984` | text | in band_80117000 [overlay band] +0x2D984 | `BATTLE_RAM.md` |
| `0x80144988` | text | in band_80117000 [overlay band] +0x2D988 | `BATTLE_RAM.md` |
| `0x80144A10` | text | in band_80117000 [overlay band] +0x2DA10 | `remote-plan-2026-09-05.md` |
| `0x80144AB4` | text | in band_80117000 [overlay band] +0x2DAB4 | `remote-plan-2026-09-05.md` |
| `0x80144B40` | text | in band_80117000 [overlay band] +0x2DB40 | `STATUS.md` |
| `0x80144B56` | text | in band_80117000 [overlay band] +0x2DB56 | `BATTLE_RAM.md` |
| `0x80144B58` | text | in band_80117000 [overlay band] +0x2DB58 | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x80144C10` | text | in band_80117000 [overlay band] +0x2DC10 | `STATUS.md` |
| `0x80144E84` | text | in band_80117000 [overlay band] +0x2DE84 | `BATTLE_RAM.md`, `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x80144F24` | text | in band_80117000 [overlay band] +0x2DF24 | `BATTLE_RAM.md`, `WORLD_ITEMS.md` |
| `0x80144F4C` | text | in band_80117000 [overlay band] +0x2DF4C | `BATTLE_RAM.md`, `STATUS.md`, `WORLD_ITEMS.md`, `remote-plan-2026-09-05.md` |
| `0x80144F50` | text | in band_80117000 [overlay band] +0x2DF50 | `WORLD_ITEMS.md` |
| `0x80144F54` | text | in band_80117000 [overlay band] +0x2DF54 | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x80144F56` | text | in band_80117000 [overlay band] +0x2DF56 | `BATTLE_RAM.md`, `STATUS.md`, `loader_records/PLCHAR.md` |
| `0x80144F57` | text | in band_80117000 [overlay band] +0x2DF57 | `loader_records/PLCHAR.md` |
| `0x80144F58` | text | in band_80117000 [overlay band] +0x2DF58 | `loader_records/PLCHAR.md` |
| `0x80144FBC` | text | in band_80117000 [overlay band] +0x2DFBC | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x80144FBE` | text | in band_80117000 [overlay band] +0x2DFBE | `BATTLE_RAM.md` |
| `0x80145000` | text | in band_80117000 [overlay band] +0x2E000 | `README.md`, `WORLD_ITEMS.md` |
| `0x80145002` | text | in band_80117000 [overlay band] +0x2E002 | `WORLD_ITEMS.md` |
| `0x80145020` | text | in band_80117000 [overlay band] +0x2E020 | `ADDRESS_MAPS.md`, `BATTLE_RAM.md`, `LOADER_RECORDS.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/PLCHAR.md` |
| `0x80145021` | text | in band_80117000 [overlay band] +0x2E021 | `BATTLE_RAM.md` |
| `0x80145025` | text | in band_80117000 [overlay band] +0x2E025 | `LOADER_RECORDS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x8014502C` | text | in band_80117000 [overlay band] +0x2E02C | `BATTLE_RAM.md`, `STATUS.md`, `WORLD_ITEMS.md` |
| `0x80145030` | text | in band_80117000 [overlay band] +0x2E030 | `WORLD_ITEMS.md` |
| `0x80145040` | text | in band_80117000 [overlay band] +0x2E040 | `BATTLE_RAM.md`, `remote-plan-2026-09-05.md` |
| `0x80145044` | text | in band_80117000 [overlay band] +0x2E044 | `loader_records/AREA.md` |
| `0x80145048` | text | in band_80117000 [overlay band] +0x2E048 | `BATTLE_RAM.md`, `STATUS.md`, `WORLD_ITEMS.md` |
| `0x801450C8` | text | in band_80117000 [overlay band] +0x2E0C8 | `BATTLE_RAM.md` |
| `0x801450CD` | text | in band_80117000 [overlay band] +0x2E0CD | `BATTLE_RAM.md` |
| `0x80145148` | text | in band_80117000 [overlay band] +0x2E148 | `BATTLE_RAM.md` |
| `0x801451C8` | text | in band_80117000 [overlay band] +0x2E1C8 | `BATTLE_RAM.md` |
| `0x80145248` | text | in band_80117000 [overlay band] +0x2E248 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x8014524C` | text | in band_80117000 [overlay band] +0x2E24C | `BATTLE_RAM.md` |
| `0x801452C8` | text | in band_80117000 [overlay band] +0x2E2C8 | `BATTLE_RAM.md` |
| `0x801452CA` | text | in band_80117000 [overlay band] +0x2E2CA | `BATTLE_RAM.md` |
| `0x801452CD` | text | in band_80117000 [overlay band] +0x2E2CD | `BATTLE_RAM.md` |
| `0x80145348` | text | in band_80117000 [overlay band] +0x2E348 | `BATTLE_RAM.md` |
| `0x801453C8` | text | in band_80117000 [overlay band] +0x2E3C8 | `BATTLE_RAM.md` |
| `0x80145440` | text | in band_80117000 [overlay band] +0x2E440 | `BATTLE_RAM.md` |
| `0x80145448` | text | in band_80117000 [overlay band] +0x2E448 | `BATTLE_RAM.md`, `STATUS.md`, `TEXT_TABLES.md`, `WORLD_ITEMS.md` |
| `0x80145468` | text | in band_80117000 [overlay band] +0x2E468 | `BATTLE_RAM.md` |
| `0x80145470` | text | in band_80117000 [overlay band] +0x2E470 | `BATTLE_RAM.md`, `remote-plan-2026-09-05.md` |
| `0x80145554` | text | in band_80117000 [overlay band] +0x2E554 | `BATTLE_RAM.md` |
| `0x80145574` | text | in band_80117000 [overlay band] +0x2E574 | `BATTLE_RAM.md` |
| `0x80145588` | text | in band_80117000 [overlay band] +0x2E588 | `BATTLE_RAM.md` |
| `0x80145590` | text | in band_80117000 [overlay band] +0x2E590 | `BATTLE_RAM.md` |
| `0x80145600` | text | in band_80117000 [overlay band] +0x2E600 | `BATTLE_RAM.md` |
| `0x80145984` | text | in band_80117000 [overlay band] +0x2E984 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801459F0` | text | in band_80117000 [overlay band] +0x2E9F0 | `loader_records/BOSS.md` |
| `0x80145AB0` | text | in band_80117000 [overlay band] +0x2EAB0 | `BATTLE_RAM.md` |
| `0x80145AC0` | text | in band_80117000 [overlay band] +0x2EAC0 | `IDEAS.md` |
| `0x80145AC6` | text | in band_80117000 [overlay band] +0x2EAC6 | `FURIGANA.md`, `IDEAS.md`, `TEXT_ENGINE.md` |
| `0x80145AC8` | text | in band_80117000 [overlay band] +0x2EAC8 | `TEXT_ENGINE.md` |
| `0x80145AD0` | text | in band_80117000 [overlay band] +0x2EAD0 | `BATTLE_RAM.md` |
| `0x80145E8C` | text | in band_80117000 [overlay band] +0x2EE8C | `BATTLE_RAM.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/PLCHAR.md`, `remote-plan-2026-09-05.md` |
| `0x80145E8D` | text | in band_80117000 [overlay band] +0x2EE8D | `BATTLE_RAM.md`, `LOADER_RECORDS.md`, `loader_records/BOSS.md` |
| `0x80145E8E` | text | in band_80117000 [overlay band] +0x2EE8E | `loader_records/BOSS.md` |
| `0x80145E91` | text | in band_80117000 [overlay band] +0x2EE91 | `BATTLE_RAM.md` |
| `0x80145E94` | text | in band_80117000 [overlay band] +0x2EE94 | `BATTLE_RAM.md` |
| `0x80145E95` | text | in band_80117000 [overlay band] +0x2EE95 | `BATTLE_RAM.md` |
| `0x80145E97` | text | in band_80117000 [overlay band] +0x2EE97 | `BATTLE_RAM.md` |
| `0x80145E98` | text | in band_80117000 [overlay band] +0x2EE98 | `BATTLE_RAM.md` |
| `0x80145EB0` | text | in band_80117000 [overlay band] +0x2EEB0 | `BATTLE_RAM.md` |
| `0x80145EB5` | text | in band_80117000 [overlay band] +0x2EEB5 | `BATTLE_RAM.md` |
| `0x80145EB7` | text | in band_80117000 [overlay band] +0x2EEB7 | `BATTLE_RAM.md` |
| `0x80145EBA` | text | in band_80117000 [overlay band] +0x2EEBA | `BATTLE_RAM.md` |
| `0x80145EC0` | text | in band_80117000 [overlay band] +0x2EEC0 | `BATTLE_RAM.md` |
| `0x80145ECA` | text | in band_80117000 [overlay band] +0x2EECA | `BATTLE_RAM.md` |
| `0x80145ED4` | text | in band_80117000 [overlay band] +0x2EED4 | `BATTLE_RAM.md` |
| `0x80145ED6` | text | in band_80117000 [overlay band] +0x2EED6 | `BATTLE_RAM.md` |
| `0x80145EE8` | text | in band_80117000 [overlay band] +0x2EEE8 | `BATTLE_RAM.md` |
| `0x80145EEC` | text | in band_80117000 [overlay band] +0x2EEEC | `BATTLE_RAM.md` |
| `0x80145F00` | text | in band_80117000 [overlay band] +0x2EF00 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80145F05` | text | in band_80117000 [overlay band] +0x2EF05 | `BATTLE_RAM.md`, `TEXT_ENGINE.md` |
| `0x80145F06` | text | in band_80117000 [overlay band] +0x2EF06 | `BATTLE_RAM.md` |
| `0x80145F08` | text | in band_80117000 [overlay band] +0x2EF08 | `BATTLE_RAM.md` |
| `0x80145F0C` | text | in band_80117000 [overlay band] +0x2EF0C | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md` |
| `0x80145F0E` | text | in band_80117000 [overlay band] +0x2EF0E | `BATTLE_RAM.md` |
| `0x80145F14` | text | in band_80117000 [overlay band] +0x2EF14 | `BATTLE_RAM.md`, `GHIDRA.md`, `STATUS.md` |
| `0x80145F16` | text | in band_80117000 [overlay band] +0x2EF16 | `BATTLE_RAM.md` |
| `0x80145F18` | text | in band_80117000 [overlay band] +0x2EF18 | `BATTLE_RAM.md` |
| `0x80145F1C` | text | in band_80117000 [overlay band] +0x2EF1C | `BATTLE_RAM.md` |
| `0x80145F1E` | text | in band_80117000 [overlay band] +0x2EF1E | `BATTLE_RAM.md` |
| `0x80145F3C` | text | in band_80117000 [overlay band] +0x2EF3C | `BATTLE_RAM.md` |
| `0x80145FA4` | text | in band_80117000 [overlay band] +0x2EFA4 | `BATTLE_RAM.md` |
| `0x80145FA5` | text | in band_80117000 [overlay band] +0x2EFA5 | `BATTLE_RAM.md`, `OVERLAY_HEADERS.md` |
| `0x80145FA8` | text | in band_80117000 [overlay band] +0x2EFA8 | `BATTLE_RAM.md` |
| `0x80145FAC` | text | in band_80117000 [overlay band] +0x2EFAC | `BATTLE_RAM.md` |
| `0x80145FB0` | text | in band_80117000 [overlay band] +0x2EFB0 | `BATTLE_RAM.md` |
| `0x80145FB4` | text | in band_80117000 [overlay band] +0x2EFB4 | `BATTLE_RAM.md` |
| `0x80145FB6` | text | in band_80117000 [overlay band] +0x2EFB6 | `BATTLE_RAM.md` |
| `0x80145FB8` | text | in band_80117000 [overlay band] +0x2EFB8 | `BATTLE_RAM.md` |
| `0x80145FC0` | text | in band_80117000 [overlay band] +0x2EFC0 | `BATTLE_RAM.md` |
| `0x80145FC4` | text | in band_80117000 [overlay band] +0x2EFC4 | `BATTLE_RAM.md` |
| `0x80145FC8` | text | in band_80117000 [overlay band] +0x2EFC8 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80145FCC` | text | in band_80117000 [overlay band] +0x2EFCC | `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x80146000` | text | in band_80117000 [overlay band] +0x2F000 | `WORLD_ITEMS.md` |
| `0x801460E5` | text | in band_80117000 [overlay band] +0x2F0E5 | `OVERLAY_HEADERS.md` |
| `0x8014624C` | text | in band_80117000 [overlay band] +0x2F24C | `BATTLE_RAM.md`, `GHIDRA.md`, `STATUS.md` |
| `0x80146250` | text | in band_80117000 [overlay band] +0x2F250 | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x80146254` | text | in band_80117000 [overlay band] +0x2F254 | `BATTLE_RAM.md` |
| `0x801462DC` | text | in band_80117000 [overlay band] +0x2F2DC | `BATTLE_RAM.md` |
| `0x801462DE` | text | in band_80117000 [overlay band] +0x2F2DE | `BATTLE_RAM.md` |
| `0x801462DF` | text | in band_80117000 [overlay band] +0x2F2DF | `BATTLE_RAM.md` |
| `0x801462E0` | text | in band_80117000 [overlay band] +0x2F2E0 | `BATTLE_RAM.md` |
| `0x801462E4` | text | in band_80117000 [overlay band] +0x2F2E4 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801462E6` | text | in band_80117000 [overlay band] +0x2F2E6 | `BATTLE_RAM.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/BOSS.md` |
| `0x801462E8` | text | in band_80117000 [overlay band] +0x2F2E8 | `loader_records/BOSS.md` |
| `0x801462EF` | text | in band_80117000 [overlay band] +0x2F2EF | `BATTLE_RAM.md` |
| `0x801462FF` | text | in band_80117000 [overlay band] +0x2F2FF | `BATTLE_RAM.md` |
| `0x80146300` | text | in band_80117000 [overlay band] +0x2F300 | `BATTLE_RAM.md` |
| `0x80146308` | text | in band_80117000 [overlay band] +0x2F308 | `BATTLE_RAM.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x80146316` | text | in band_80117000 [overlay band] +0x2F316 | `LOADER_RECORDS.md`, `loader_records/BOSS.md` |
| `0x8014631E` | text | in band_80117000 [overlay band] +0x2F31E | `BATTLE_RAM.md`, `STATUS.md` |
| `0x8014631F` | text | in band_80117000 [overlay band] +0x2F31F | `BATTLE_RAM.md` |
| `0x80146320` | text | in band_80117000 [overlay band] +0x2F320 | `BATTLE_RAM.md`, `HANDOFF.md`, `loader_records/BOSS.md` |
| `0x80146321` | text | in band_80117000 [overlay band] +0x2F321 | `loader_records/BOSS.md` |
| `0x80146322` | text | in band_80117000 [overlay band] +0x2F322 | `BATTLE_RAM.md` |
| `0x80146323` | text | in band_80117000 [overlay band] +0x2F323 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80146324` | text | in band_80117000 [overlay band] +0x2F324 | `BATTLE_RAM.md` |
| `0x80146328` | text | in band_80117000 [overlay band] +0x2F328 | `BATTLE_RAM.md` |
| `0x8014632C` | text | in band_80117000 [overlay band] +0x2F32C | `BATTLE_RAM.md` |
| `0x80146330` | text | in band_80117000 [overlay band] +0x2F330 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80146350` | text | in band_80117000 [overlay band] +0x2F350 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80146360` | text | in band_80117000 [overlay band] +0x2F360 | `BATTLE_RAM.md`, `HANDOFF.md` |
| `0x80146382` | text | in band_80117000 [overlay band] +0x2F382 | `OVERLAY_HEADERS.md` |
| `0x80146390` | text | in band_80117000 [overlay band] +0x2F390 | `BATTLE_RAM.md` |
| `0x8014639C` | text | in band_80117000 [overlay band] +0x2F39C | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801463AC` | text | in band_80117000 [overlay band] +0x2F3AC | `BATTLE_RAM.md` |
| `0x801463BC` | text | in band_80117000 [overlay band] +0x2F3BC | `OVERLAY_HEADERS.md` |
| `0x801463C4` | text | in band_80117000 [overlay band] +0x2F3C4 | `BATTLE_RAM.md` |
| `0x801463CC` | text | in band_80117000 [overlay band] +0x2F3CC | `BATTLE_RAM.md` |
| `0x80146460` | text | in band_80117000 [overlay band] +0x2F460 | `OVERLAY_HEADERS.md` |
| `0x80146464` | text | in band_80117000 [overlay band] +0x2F464 | `HANDOFF.md`, `IDEAS.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/BOSS.md`, `loader_records/PLCHAR.md` |
| `0x80146468` | text | in band_80117000 [overlay band] +0x2F468 | `OVERLAY_HEADERS.md` |
| `0x80146490` | text | in band_80117000 [overlay band] +0x2F490 | `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x8014649C` | text | in band_80117000 [overlay band] +0x2F49C | `OVERLAY_HEADERS.md` |
| `0x80146800` | text | in band_80117000 [overlay band] +0x2F800 | `regional-builds.md` |
| `0x80146860` | text | in band_80117000 [overlay band] +0x2F860 | `BATTLE_RAM.md` |
| `0x80146868` | text | in band_80117000 [overlay band] +0x2F868 | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x8014686C` | text | in band_80117000 [overlay band] +0x2F86C | `ADDRESS_MAPS.md`, `BATTLE_RAM.md`, `HANDOFF.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x8014686D` | text | in band_80117000 [overlay band] +0x2F86D | `loader_records/SCENARIO.md` |
| `0x8014686E` | text | in band_80117000 [overlay band] +0x2F86E | `loader_records/SCENARIO.md` |
| `0x8014686F` | text | in band_80117000 [overlay band] +0x2F86F | `loader_records/SCENARIO.md` |
| `0x80146870` | text | in band_80117000 [overlay band] +0x2F870 | `loader_records/SCENARIO.md` |
| `0x80146871` | text | in band_80117000 [overlay band] +0x2F871 | `loader_records/SCENARIO.md` |
| `0x80146872` | text | in band_80117000 [overlay band] +0x2F872 | `loader_records/SCENARIO.md` |
| `0x80146874` | text | in band_80117000 [overlay band] +0x2F874 | `loader_records/SCENARIO.md` |
| `0x80146878` | text | in band_80117000 [overlay band] +0x2F878 | `BATTLE_RAM.md`, `loader_records/SCENARIO.md` |
| `0x8014687B` | text | in band_80117000 [overlay band] +0x2F87B | `loader_records/SCENARIO.md` |
| `0x80146990` | text | in band_80117000 [overlay band] +0x2F990 | `crash-kernel-ram-2934.md` |
| `0x8014832F` | text | in band_80117000 [overlay band] +0x3132F | `TEXT_ENGINE.md` |
| `0x80148330` | text | in band_80117000 [overlay band] +0x31330 | `TEXT_ENGINE.md` |
| `0x801484B8` | text | in band_80117000 [overlay band] +0x314B8 | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md` |
| `0x801484C3` | text | in band_80117000 [overlay band] +0x314C3 | `BATTLE_RAM.md` |
| `0x801484CC` | text | in band_80117000 [overlay band] +0x314CC | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801484D4` | text | in band_80117000 [overlay band] +0x314D4 | `BATTLE_RAM.md` |
| `0x801484DC` | text | in band_80117000 [overlay band] +0x314DC | `BATTLE_RAM.md` |
| `0x80148500` | text | in band_80117000 [overlay band] +0x31500 | `BATTLE_RAM.md` |
| `0x8014850B` | text | in band_80117000 [overlay band] +0x3150B | `BATTLE_RAM.md` |
| `0x8014850C` | text | in band_80117000 [overlay band] +0x3150C | `BATTLE_RAM.md` |
| `0x8014852F` | text | in band_80117000 [overlay band] +0x3152F | `BATTLE_RAM.md` |
| `0x80148644` | text | in band_80117000 [overlay band] +0x31644 | `BATTLE_RAM.md`, `GHIDRA.md`, `HANDOFF.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80148668` | text | in band_80117000 [overlay band] +0x31668 | `BATTLE_RAM.md` |
| `0x8014909C` | text | in band_80117000 [overlay band] +0x3209C | `TEXT_ENGINE.md` |
| `0x8014909D` | text | in band_80117000 [overlay band] +0x3209D | `TEXT_ENGINE.md` |
| `0x8014909E` | text | in band_80117000 [overlay band] +0x3209E | `TEXT_ENGINE.md` |
| `0x801490A0` | text | in band_80117000 [overlay band] +0x320A0 | `IDEAS.md`, `INSERT_RUBY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490A2` | text | in band_80117000 [overlay band] +0x320A2 | `TEXT_ENGINE.md` |
| `0x801490A3` | text | in band_80117000 [overlay band] +0x320A3 | `INSERT_RUBY.md`, `TEXT_ENGINE.md` |
| `0x801490A4` | text | in band_80117000 [overlay band] +0x320A4 | `HANDOFF.md`, `IDEAS.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490A6` | text | in band_80117000 [overlay band] +0x320A6 | `TEXT_ENGINE.md` |
| `0x801490A8` | text | in band_80117000 [overlay band] +0x320A8 | `ADDRESS_MAPS.md`, `IDEAS.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490AC` | text | in band_80117000 [overlay band] +0x320AC | `ADDRESS_MAPS.md`, `IDEAS.md`, `INSERT_RUBY.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490B0` | text | in band_80117000 [overlay band] +0x320B0 | `HANDOFF.md`, `INSERT_RUBY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490B4` | text | in band_80117000 [overlay band] +0x320B4 | `TEXT_ENGINE.md` |
| `0x801490B5` | text | in band_80117000 [overlay band] +0x320B5 | `TEXT_ENGINE.md` |
| `0x801490B6` | text | in band_80117000 [overlay band] +0x320B6 | `TEXT_ENGINE.md` |
| `0x801490B8` | text | in band_80117000 [overlay band] +0x320B8 | `IDEAS.md`, `TEXT_ENGINE.md` |
| `0x801490BC` | text | in band_80117000 [overlay band] +0x320BC | `IDEAS.md`, `TEXT_ENGINE.md` |
| `0x801490C0` | text | in band_80117000 [overlay band] +0x320C0 | `TEXT_ENGINE.md` |
| `0x801490C1` | text | in band_80117000 [overlay band] +0x320C1 | `TEXT_ENGINE.md` |
| `0x801490C4` | text | in band_80117000 [overlay band] +0x320C4 | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490CA` | text | in band_80117000 [overlay band] +0x320CA | `TEXT_ENGINE.md` |
| `0x801490D3` | text | in band_80117000 [overlay band] +0x320D3 | `INSERT_RUBY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801490D4` | text | insert_scratch_records [scratch array] (base) | `ADDRESS_MAPS.md`, `HANDOFF.md`, `INSERT_RUBY.md`, `README.md`, `STATUS.md`, `WORLD_ITEMS.md` |
| `0x801490DC` | text | in insert_scratch_records [scratch array] +0x8 | `INSERT_RUBY.md` |
| `0x801492D4` | text | in band_80117000 [overlay band] +0x322D4 | `ADDRESS_MAPS.md` |
| `0x8014932E` | text | in band_80117000 [overlay band] +0x3232E | `BATTLE_RAM.md` |
| `0x8014933A` | text | in band_80117000 [overlay band] +0x3233A | `BATTLE_RAM.md` |
| `0x80149800` | text | in boot_exe_image [exe image] +0xB6000 | `ADDRESS_MAPS.md`, `OVERLAYS.md`, `zero-fill-dispatch-audit.md` |
| `0x80149A00` | text | in boot_exe_image [exe image] +0xB6200 | `TEXT_ENGINE.md` |
| `0x80149A5C` | text | in boot_exe_image [exe image] +0xB625C | `TEXT_ENGINE.md` |
| `0x80149AB4` | text | in boot_exe_image [exe image] +0xB62B4 | `TEXT_ENGINE.md` |
| `0x80149F9C` | text | in boot_exe_image [exe image] +0xB679C | `loader_records/PLCHAR.md` |
| `0x80149FAC` | text | in boot_exe_image [exe image] +0xB67AC | `loader_records/PLCHAR.md` |
| `0x8014A0DC` | text | in boot_exe_image [exe image] +0xB68DC | `BRINGUP.md` |
| `0x8014AA0C` | text | BootEntry [guessed] boot | `INVENTORY.md`, `LOCALIZATION.md`, `README.md`, `regional-builds.md` |
| `0x8014AB20` | text | ≤ stup0 (boot) +0x74 (nearest below, span unknown) | `LOCALIZATION.md` |
| `0x8014B70C` | text | ≤ stup0 (boot) +0xC60 (nearest below, span unknown) | `crash-kernel-ram-2934.md` |
| `0x8014B770` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/AREA.md`, `loader_records/SCENARIO.md` |
| `0x8014D5D0` | text | unnamed function root (seeds/ghidra_funcs.txt) | `GHIDRA.md` |
| `0x8014DC30` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/BOSS.md` |
| `0x8014E178` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/AREA.md` |
| `0x8014E294` | text | ≤ Actor_AnimTick (boot) +0xA28 (nearest below, span unknown) | `HANDOFF.md`, `remote-plan-2026-09-05.md` |
| `0x8014E494` | text | unnamed function root (seeds/ghidra_funcs.txt) | `AREA_PCS.md`, `GHIDRA.md`, `HANDOFF.md`, `STATUS.md` |
| `0x8014E974` | text | in boot_exe_image [exe image] +0xBB174 | `loader_records/AREA.md`, `loader_records/PLCHAR.md` |
| `0x8014E9A0` | text | in boot_exe_image [exe image] +0xBB1A0 | `OVERLAY_HEADERS.md`, `loader_records/AREA.md` |
| `0x8014EA20` | text | in boot_exe_image [exe image] +0xBB220 | `loader_records/PLCHAR.md` |
| `0x8014EB20` | text | in boot_exe_image [exe image] +0xBB320 | `GHIDRA.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/AREA.md` |
| `0x8014EB28` | text | in boot_exe_image [exe image] +0xBB328 | `loader_records/AREA.md` |
| `0x8014F6BC` | text | unnamed function root (seeds/ghidra_funcs.txt) | `BATTLE_RAM.md`, `FURIGANA.md`, `IDEAS.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x8014F708` | text | unnamed function root (seeds/ghidra_funcs.txt) | `FURIGANA.md`, `IDEAS.md`, `TEXT_ENGINE.md` |
| `0x8015034C` | text | Msg_OpenScript [confirmed] boot | `GHIDRA.md`, `IDEAS.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801503AC` | text | Msg_OpenSystem [confirmed] boot | `AREA_PCS.md`, `IDEAS.md`, `TEXT_ENGINE.md`, `WORLD_ITEMS.md` |
| `0x801503F8` | text | Msg_SystemPtr [confirmed] boot | `GHIDRA.md`, `IDEAS.md`, `TEXT_ENGINE.md` |
| `0x8015042C` | text | MsgBox_Reset [confirmed] boot | `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md`, `us-build-trial.md` |
| `0x80150508` | text | MsgBox_FrameTask [confirmed] boot | `TEXT_ENGINE.md` |
| `0x80150570` | text | ≤ MsgBox_FrameTask (boot) +0x68 (nearest below, span unknown) | `IDEAS.md`, `TEXT_ENGINE.md` |
| `0x80150598` | text | MsgBox_Render [confirmed] boot | `FURIGANA.md`, `IDEAS.md`, `STATUS.md`, `TEXT_ENGINE.md`, `regional-builds.md` |
| `0x80150688` | text | ≤ MsgBox_Render (boot) +0xF0 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80150690` | text | ≤ MsgBox_Render (boot) +0xF8 (nearest below, span unknown) | `FURIGANA.md`, `TEXT_ENGINE.md` |
| `0x80150770` | text | ≤ MsgBox_Render (boot) +0x1D8 (nearest below, span unknown) | `LOCALIZATION.md`, `TEXT_ENGINE.md` |
| `0x801507EC` | text | ≤ MsgBox_Render (boot) +0x254 (nearest below, span unknown) | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80150808` | text | ≤ MsgBox_Render (boot) +0x270 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80150850` | text | ≤ MsgBox_Render (boot) +0x2B8 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80150898` | text | ≤ MsgBox_Render (boot) +0x300 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x801508A0` | text | ≤ MsgBox_Render (boot) +0x308 (nearest below, span unknown) | `FURIGANA.md`, `IDEAS.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801508EC` | text | MsgBox_StateDispatch [confirmed] boot | `TEXT_ENGINE.md` |
| `0x80150910` | text | ≤ MsgBox_StateDispatch (boot) +0x24 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x8015096C` | text | MsgBox_Step [confirmed] boot | `IDEAS.md`, `INSERT_RUBY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80150D34` | text | ≤ MsgBox_Step (boot) +0x3C8 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80150DB0` | text | ≤ MsgBox_Step (boot) +0x444 (nearest below, span unknown) | `LOCALIZATION.md`, `TEXT_ENGINE.md` |
| `0x80150F04` | text | ≤ MsgBox_Step (boot) +0x598 (nearest below, span unknown) | `IDEAS.md` |
| `0x80150F3C` | text | MsgBox_DelayState [evidence] boot | `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md`, `us-build-trial.md` |
| `0x801511B4` | text | ≤ MsgBox_DelayState (boot) +0x278 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80151554` | text | MsgBox_ReplayIfShown [evidence] boot | `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801515F8` | text | MsgBox_Replay [evidence] boot | `HANDOFF.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80151A8C` | text | ≤ MsgBox_Replay (boot) +0x494 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80151A94` | text | ≤ MsgBox_Replay (boot) +0x49C (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80151BC0` | text | ≤ MsgBox_Replay (boot) +0x5C8 (nearest below, span unknown) | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80151D28` | text | ≤ MsgBox_Replay (boot) +0x730 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80151E64` | text | ≤ MsgBox_Replay (boot) +0x86C (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80151F4C` | text | Font_MapGlyph [confirmed] boot | `FURIGANA.md`, `IDEAS.md`, `LOCALIZATION.md`, `LOCALIZATION_APPLY.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80151FCC` | text | ≤ Font_MapGlyph (boot) +0x80 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80152010` | text | ≤ Font_MapGlyph (boot) +0xC4 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x80152740` | text | ≤ Font_MapGlyph (boot) +0x7F4 (nearest below, span unknown) | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x801529B8` | text | ≤ Font_MapGlyph (boot) +0xA6C (nearest below, span unknown) | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80152C5C` | text | ≤ Font_MapGlyph (boot) +0xD10 (nearest below, span unknown) | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80152D98` | text | ≤ Font_MapGlyph (boot) +0xE4C (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x801532A0` | text | in boot_exe_image [exe image] +0xBFAA0 | `GHIDRA.md`, `STATUS.md` |
| `0x80155238` | text | unnamed function root (seeds/ghidra_funcs.txt) | `BATTLE_RAM.md` |
| `0x80159828` | text | in boot_exe_image [exe image] +0xC6028 | `IDEAS.md` |
| `0x80159F00` | text | Window_Task [confirmed] boot | `TEXT_ENGINE.md` |
| `0x8015A58C` | text | Window_DrawFrame [confirmed] boot | `FURIGANA.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x8015AB2C` | text | ≤ Window_DrawFrame (boot) +0x5A0 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x8015AB94` | text | ≤ Window_DrawFrame (boot) +0x608 (nearest below, span unknown) | `TEXT_ENGINE.md` |
| `0x8015AD34` | text | Text_DrawImmediate [confirmed] boot | `IDEAS.md`, `LOCALIZATION.md`, `STATUS.md`, `TEXT_ENGINE.md`, `regional-builds.md` |
| `0x8015AE78` | text | ≤ Text_DrawImmediate (boot) +0x144 (nearest below, span unknown) | `LOCALIZATION.md`, `TEXT_ENGINE.md` |
| `0x8015B1D8` | text | ≤ Text_DrawImmediate (boot) +0x4A4 (nearest below, span unknown) | `GHIDRA.md` |
| `0x8015B67C` | text | ≤ Text_DrawImmediate (boot) +0x948 (nearest below, span unknown) | `loader_records/AREA.md` |
| `0x8015BF70` | text | Flag_Set [confirmed] boot | `AREA_PCS.md`, `WORLD_ITEMS.md` |
| `0x8015BF98` | text | Flag_Clear [confirmed] boot | `WORLD_ITEMS.md` |
| `0x8015BFC4` | text | Flag_Test [confirmed] boot | `AREA_PCS.md`, `BATTLE_RAM.md`, `STATUS.md`, `WORLD_ITEMS.md`, `remote-plan-2026-09-05.md` |
| `0x8015BFE4` | text | Flag_Toggle [confirmed] boot | `BATTLE_RAM.md`, `WORLD_ITEMS.md` |
| `0x8015C03C` | text | ≤ Flag_Toggle (boot) +0x58 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x8015D508` | text | in boot_exe_image [exe image] +0xC9D08 | `GHIDRA.md` |
| `0x8015D5F0` | text | in boot_exe_image [exe image] +0xC9DF0 | `GHIDRA.md` |
| `0x8015E908` | text | unnamed function root (seeds/ghidra_funcs.txt) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `GHIDRA.md`, `HANDOFF.md`, `STATUS.md`, `TEXT_ENGINE.md`, `WORLD_ITEMS.md` |
| `0x801625AC` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x801625B0` | text | in boot_exe_image [exe image] +0xCEDB0 | `loader_records/AREA.md` |
| `0x801625B4` | text | in boot_exe_image [exe image] +0xCEDB4 | `loader_records/AREA.md` |
| `0x801625B8` | text | in boot_exe_image [exe image] +0xCEDB8 | `loader_records/AREA.md` |
| `0x801625BC` | text | in boot_exe_image [exe image] +0xCEDBC | `loader_records/AREA.md` |
| `0x801625C8` | text | in boot_exe_image [exe image] +0xCEDC8 | `loader_records/AREA.md` |
| `0x801625CC` | text | in boot_exe_image [exe image] +0xCEDCC | `loader_records/AREA.md` |
| `0x801625F4` | text | in boot_exe_image [exe image] +0xCEDF4 | `loader_records/AREA.md` |
| `0x80162610` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/BOSS.md` |
| `0x801626C0` | text | in boot_exe_image [exe image] +0xCEEC0 | `loader_records/BOSS.md` |
| `0x80162710` | text | in boot_exe_image [exe image] +0xCEF10 | `loader_records/BOSS.md` |
| `0x801629CC` | text | File_LoadRequest [confirmed] boot | `HANDOFF.md`, `IDEAS.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/PLCHAR.md`, `loader_records/SCENARIO.md`, `remote-plan-2026-09-05.md` |
| `0x801629F0` | text | ≤ File_LoadRequest (boot) +0x24 (nearest below, span unknown) | `OVERLAY_HEADERS.md` |
| `0x80162B50` | text | File_LBA [confirmed] boot | `OVERLAY_HEADERS.md` |
| `0x801636F0` | text | File_LoadDone [confirmed] boot | `BATTLE_RAM.md`, `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/PLCHAR.md`, `loader_records/SCENARIO.md` |
| `0x80164E48` | text | in boot_exe_image [exe image] +0xD1648 | `LOADER_RECORDS.md`, `STATUS.md` |
| `0x80164E84` | text | in boot_exe_image [exe image] +0xD1684 | `HANDOFF.md`, `STATUS.md` |
| `0x80164E90` | text | in boot_exe_image [exe image] +0xD1690 | `LOADER_RECORDS.md` |
| `0x80165434` | text | Char_RecalcStats [confirmed] boot | `STATUS.md` |
| `0x80165AA4` | text | Inventory_Add [confirmed] boot | `AREA_PCS.md`, `BATTLE_RAM.md`, `STATUS.md` |
| `0x80165BCC` | text | AbilityList_Add [guessed] boot | `STATUS.md` |
| `0x80165EE4` | text | Stat_AddClamped [confirmed] boot | `STATUS.md` |
| `0x80166720` | text | Item_NamePtr [confirmed] boot | `AREA_PCS.md`, `INSERT_RUBY.md`, `STATUS.md` |
| `0x80166F30` | text | Inventory_Remove [confirmed] boot | `STATUS.md` |
| `0x80166FCC` | text | Zenny_Sub [confirmed] boot | `BATTLE_RAM.md`, `STATUS.md` |
| `0x80166FD4` | text | ≤ Zenny_Sub (boot) +0x8 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x80166FFC` | text | Zenny_Add [confirmed] boot | `AREA_PCS.md`, `BATTLE_RAM.md`, `STATUS.md`, `WORLD_ITEMS.md` |
| `0x80167514` | text | AbilityList_ForType [confirmed] boot | `BATTLE_RAM.md`, `STATUS.md` |
| `0x8016776C` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/PLCHAR.md` |
| `0x80167800` | text | ≤ AbilityList_ForType (boot) +0x2EC (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801678B4` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/PLCHAR.md` |
| `0x801678E4` | text | ≤ AbilityList_ForType (boot) +0x3D0 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801678FC` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/PLCHAR.md` |
| `0x80167954` | text | ≤ AbilityList_ForType (boot) +0x440 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167970` | text | unnamed function root (seeds/ghidra_funcs.txt) | `loader_records/PLCHAR.md` |
| `0x80167984` | text | ≤ AbilityList_ForType (boot) +0x470 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167994` | text | ≤ AbilityList_ForType (boot) +0x480 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x8016799C` | text | ≤ AbilityList_ForType (boot) +0x488 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679A0` | text | ≤ AbilityList_ForType (boot) +0x48C (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679A8` | text | ≤ AbilityList_ForType (boot) +0x494 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679BC` | text | ≤ AbilityList_ForType (boot) +0x4A8 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679D8` | text | ≤ AbilityList_ForType (boot) +0x4C4 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679DC` | text | ≤ AbilityList_ForType (boot) +0x4C8 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679E0` | text | ≤ AbilityList_ForType (boot) +0x4CC (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801679E4` | text | ≤ AbilityList_ForType (boot) +0x4D0 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167A40` | text | ≤ AbilityList_ForType (boot) +0x52C (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167A74` | text | ≤ AbilityList_ForType (boot) +0x560 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167AF0` | text | ≤ AbilityList_ForType (boot) +0x5DC (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167AF8` | text | ≤ AbilityList_ForType (boot) +0x5E4 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167B0C` | text | ≤ AbilityList_ForType (boot) +0x5F8 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167BE4` | text | ≤ AbilityList_ForType (boot) +0x6D0 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167BEC` | text | ≤ AbilityList_ForType (boot) +0x6D8 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C04` | text | unnamed function root (seeds/ghidra_funcs.txt) | `OVERLAY_HEADERS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/PLCHAR.md` |
| `0x80167C28` | text | ≤ AbilityList_ForType (boot) +0x714 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C2C` | text | ≤ AbilityList_ForType (boot) +0x718 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C34` | text | ≤ AbilityList_ForType (boot) +0x720 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C38` | text | ≤ AbilityList_ForType (boot) +0x724 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C84` | text | ≤ AbilityList_ForType (boot) +0x770 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C90` | text | ≤ AbilityList_ForType (boot) +0x77C (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167C9C` | text | ≤ AbilityList_ForType (boot) +0x788 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167CA0` | text | ≤ AbilityList_ForType (boot) +0x78C (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167CA4` | text | ≤ AbilityList_ForType (boot) +0x790 (nearest below, span unknown) | `LOADER_RECORDS.md`, `loader_records/AREA.md`, `loader_records/PLCHAR.md` |
| `0x80167CAC` | text | ≤ AbilityList_ForType (boot) +0x798 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x80167DA0` | text | unnamed function root (seeds/ghidra_funcs.txt) | `GHIDRA.md` |
| `0x80168178` | text | ≤ AbilityList_ForType (boot) +0xC64 (nearest below, span unknown) | `GHIDRA.md` |
| `0x8017487C` | text | ≤ SsVabOpenHeadWithMode (boot) +0x254 (nearest below, span unknown) | `us-build-trial.md` |
| `0x801751F4` | text | ≤ v_wait (boot) +0x34 (nearest below, span unknown) | `BRINGUP.md`, `STATUS.md` |
| `0x80175234` | text | ≤ v_wait (boot) +0x74 (nearest below, span unknown) | `crash-kernel-ram-2934.md` |
| `0x80177ACC` | text | CD_getsector [confirmed] boot | `OVERLAY_HEADERS.md` |
| `0x80177B6C` | text | ≤ CD_getsector (boot) +0xA0 (nearest below, span unknown) | `LOCALIZATION.md` |
| `0x80177B70` | text | ≤ CD_getsector (boot) +0xA4 (nearest below, span unknown) | `LOCALIZATION.md` |
| `0x80177B78` | text | ≤ CD_getsector (boot) +0xAC (nearest below, span unknown) | `LOCALIZATION.md`, `STATUS.md` |
| `0x80177B88` | text | ≤ CD_getsector (boot) +0xBC (nearest below, span unknown) | `LOCALIZATION.md` |
| `0x80177B90` | text | ≤ CD_getsector (boot) +0xC4 (nearest below, span unknown) | `LOCALIZATION.md` |
| `0x80178FD8` | text | InitGeom [confirmed] boot | `us-build-trial.md` |
| `0x801799B0` | text | SetColorMatrix [confirmed] boot | `loader_records/AREA.md` |
| `0x8017AC30` | text | _patch_gte [confirmed] boot | `kernel-patch-sites.md` |
| `0x8017AF98` | text | GetTPage [confirmed] boot | `GHIDRA.md`, `STATUS.md` |
| `0x8017CC50` | text | SetDrawMode [confirmed] boot | `GHIDRA.md`, `STATUS.md` |
| `0x8017DDA0` | text | ≤ _cwc (boot) +0x40 (nearest below, span unknown) | `BRINGUP.md` |
| `0x8017E23C` | text | ≤ _exeque (boot) +0x15C (nearest below, span unknown) | `BRINGUP.md` |
| `0x8017E328` | text | ≤ _exeque (boot) +0x248 (nearest below, span unknown) | `BRINGUP.md` |
| `0x8017EAA0` | text | ≤ StopCARD_2 (boot) +0x24 (nearest below, span unknown) | `HANDOFF.md`, `STATUS.md`, `kernel-patch-sites.md`, `upstream-kernel-bless-plan.md` |
| `0x8017EAE4` | text | _patch_card [confirmed] boot | `kernel-patch-sites.md` |
| `0x8017EB6C` | text | ≤ _patch_card (boot) +0x88 (nearest below, span unknown) | `kernel-patch-sites.md` |
| `0x8017EB9C` | text | _patch_card2 [confirmed] boot | `kernel-patch-sites.md` |
| `0x8017ED2C` | text | strlen [confirmed] boot | `us-build-trial.md` |
| `0x8017ED4C` | text | Rand [confirmed] boot | `GHIDRA.md`, `STATUS.md` |
| `0x8017ED6C` | text | sprintf [confirmed] boot | `AREA_PCS.md` |
| `0x8017F650` | text | ≤ InitHeap (boot) +0xC (nearest below, span unknown) | `zero-fill-dispatch-audit.md` |
| `0x8017F6E4` | text | TestEvent [confirmed] boot | `BATTLE_RAM.md` |
| `0x8017F7B0` | text | ≤ SetSp (boot) +0xC (nearest below, span unknown) | `GHIDRA.md`, `HANDOFF.md` |
| `0x8017F7B4` | text | open [confirmed] boot | `BATTLE_RAM.md`, `GHIDRA.md` |
| `0x8017F824` | text | nextfile [confirmed] boot | `BATTLE_RAM.md` |
| `0x8017F830` | text | ≤ nextfile (boot) +0xC (nearest below, span unknown) | `GHIDRA.md`, `HANDOFF.md` |
| `0x8017FD5C` | text | _patch_pad [confirmed] boot | `kernel-patch-sites.md` |
| `0x8017FED4` | text | ≤ _patch_pad (boot) +0x178 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x8017FEF8` | text | ≤ _patch_pad (boot) +0x19C (nearest below, span unknown) | `STATUS.md`, `TEXT_ENGINE.md` |
| `0x8017FF30` | text | ≤ _patch_pad (boot) +0x1D4 (nearest below, span unknown) | `IDEAS.md`, `STATUS.md`, `TEXT_ENGINE.md` |
| `0x80180000` | text | ≤ _patch_pad (boot) +0x2A4 (nearest below, span unknown) | `loader_records/AREA.md` |
| `0x801802EC` | text | ≤ _patch_pad (boot) +0x590 (nearest below, span unknown) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `HANDOFF.md`, `LOADER_RECORDS.md`, `README.md`, `STATUS.md`, `WORLD_ITEMS.md`, `loader_records/AREA.md`, `loader_records/SCENARIO.md` |
| `0x80181DFC` | text | in boot_exe_image [exe image] +0xEE5FC | `loader_records/BOSS.md` |
| `0x80182488` | text | in boot_exe_image [exe image] +0xEEC88 | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md`, `loader_records/PLCHAR.md` |
| `0x801824AC` | text | in boot_exe_image [exe image] +0xEECAC | `ADDRESS_MAPS.md`, `BATTLE_RAM.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/PLCHAR.md` |
| `0x80182830` | text | in boot_exe_image [exe image] +0xEF030 | `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x80182AC4` | text | in boot_exe_image [exe image] +0xEF2C4 | `loader_records/AREA.md` |
| `0x80182DBC` | text | in boot_exe_image [exe image] +0xEF5BC | `HANDOFF.md`, `OVERLAY_HEADERS.md`, `STATUS.md` |
| `0x80184F78` | text | in boot_exe_image [exe image] +0xF1778 | `OVERLAYS.md` |
| `0x80185FE8` | text | in boot_exe_image [exe image] +0xF27E8 | `OVERLAYS.md` |
| `0x8018603C` | text | in boot_exe_image [exe image] +0xF283C | `BRINGUP.md`, `HANDOFF.md`, `OVERLAY_EXTRACTION.md`, `STATUS.md`, `vblank-pacing-bug.md` |
| `0x80186400` | text | in boot_exe_image [exe image] +0xF2C00 | `LOCALIZATION.md` |
| `0x8018BBA8` | text | in boot_exe_image [exe image] +0xF83A8 | `BRINGUP.md` |
| `0x8018BBAC` | text | in boot_exe_image [exe image] +0xF83AC | `BRINGUP.md` |
| `0x8018BBB0` | text | in boot_exe_image [exe image] +0xF83B0 | `BRINGUP.md` |
| `0x8018BBB4` | text | in boot_exe_image [exe image] +0xF83B4 | `BRINGUP.md` |
| `0x8018BC2C` | text | in boot_exe_image [exe image] +0xF842C | `BRINGUP.md`, `OVERLAYS.md` |
| `0x80190000` | text | in boot_exe_image [exe image] +0xFC800 | `STATUS.md` |
| `0x80196800` | text | band_80196800 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `BATTLE_RAM.md`, `GHIDRA.md`, `HANDOFF.md`, `INSERT_RUBY.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/SCENARIO.md`, `regional-builds.md` |
| `0x80196801` | text | in band_80196800 [overlay band] +0x1 | `OVERLAYS.md`, `zero-fill-dispatch-audit.md` |
| `0x80196F0C` | text | in band_80196800 [overlay band] +0x70C | `INSERT_RUBY.md` |
| `0x80196FBC` | text | in band_80196800 [overlay band] +0x7BC | `INSERT_RUBY.md`, `WORLD_ITEMS.md` |
| `0x8019701C` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801970B4` | text | in band_80196800 [overlay band] +0x8B4 | `OVERLAYS.md`, `STATUS.md` |
| `0x80197718` | text | in band_80196800 [overlay band] +0xF18 | `BATTLE_RAM.md` |
| `0x80198004` | text | in band_80196800 [overlay band] +0x1804 | `loader_records/AREA.md` |
| `0x80198174` | text | in band_80196800 [overlay band] +0x1974 | `loader_records/BOSS.md` |
| `0x80198194` | text | in band_80196800 [overlay band] +0x1994 | `loader_records/AREA.md` |
| `0x801981F0` | text | in band_80196800 [overlay band] +0x19F0 | `loader_records/AREA.md` |
| `0x80198224` | text | in band_80196800 [overlay band] +0x1A24 | `loader_records/SCENARIO.md` |
| `0x80198380` | text | in band_80196800 [overlay band] +0x1B80 | `loader_records/SCENARIO.md` |
| `0x80198628` | text | in band_80196800 [overlay band] +0x1E28 | `loader_records/AREA.md` |
| `0x8019872C` | text | in band_80196800 [overlay band] +0x1F2C | `loader_records/PLCHAR.md` |
| `0x80198734` | text | in band_80196800 [overlay band] +0x1F34 | `loader_records/PLCHAR.md` |
| `0x8019873C` | text | in band_80196800 [overlay band] +0x1F3C | `loader_records/PLCHAR.md` |
| `0x80198740` | text | in band_80196800 [overlay band] +0x1F40 | `loader_records/PLCHAR.md` |
| `0x80198744` | text | in band_80196800 [overlay band] +0x1F44 | `loader_records/PLCHAR.md` |
| `0x80198784` | text | in band_80196800 [overlay band] +0x1F84 | `loader_records/PLCHAR.md` |
| `0x801987C4` | text | in band_80196800 [overlay band] +0x1FC4 | `loader_records/AREA.md` |
| `0x80198BC0` | text | in band_80196800 [overlay band] +0x23C0 | `loader_records/PLCHAR.md` |
| `0x80198C94` | text | in band_80196800 [overlay band] +0x2494 | `loader_records/BOSS.md` |
| `0x80198CF0` | text | in band_80196800 [overlay band] +0x24F0 | `loader_records/AREA.md` |
| `0x80198CFC` | text | in band_80196800 [overlay band] +0x24FC | `loader_records/AREA.md` |
| `0x80198DB0` | text | in band_80196800 [overlay band] +0x25B0 | `loader_records/BOSS.md` |
| `0x80198DD0` | text | in band_80196800 [overlay band] +0x25D0 | `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x80198DEC` | text | in band_80196800 [overlay band] +0x25EC | `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x8019910C` | text | in band_80196800 [overlay band] +0x290C | `loader_records/BOSS.md` |
| `0x80199358` | text | in band_80196800 [overlay band] +0x2B58 | `loader_records/AREA.md` |
| `0x801993E0` | text | in band_80196800 [overlay band] +0x2BE0 | `loader_records/PLCHAR.md` |
| `0x801993E4` | text | in band_80196800 [overlay band] +0x2BE4 | `loader_records/PLCHAR.md` |
| `0x801993E8` | text | in band_80196800 [overlay band] +0x2BE8 | `loader_records/PLCHAR.md` |
| `0x801993F8` | text | in band_80196800 [overlay band] +0x2BF8 | `loader_records/PLCHAR.md` |
| `0x801993FC` | text | in band_80196800 [overlay band] +0x2BFC | `loader_records/PLCHAR.md` |
| `0x80199440` | text | in band_80196800 [overlay band] +0x2C40 | `loader_records/AREA.md` |
| `0x801995FC` | text | in band_80196800 [overlay band] +0x2DFC | `loader_records/PLCHAR.md` |
| `0x801996D0` | text | in band_80196800 [overlay band] +0x2ED0 | `loader_records/AREA.md` |
| `0x801997D8` | text | in band_80196800 [overlay band] +0x2FD8 | `loader_records/AREA.md` |
| `0x8019986C` | text | in band_80196800 [overlay band] +0x306C | `loader_records/PLCHAR.md` |
| `0x80199998` | text | in band_80196800 [overlay band] +0x3198 | `loader_records/AREA.md` |
| `0x80199A2C` | text | in band_80196800 [overlay band] +0x322C | `loader_records/PLCHAR.md` |
| `0x8019A238` | text | in band_80196800 [overlay band] +0x3A38 | `loader_records/SCENARIO.md` |
| `0x8019A370` | text | in band_80196800 [overlay band] +0x3B70 | `loader_records/SCENARIO.md` |
| `0x8019B19C` | text | in band_80196800 [overlay band] +0x499C | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x8019CD40` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801A0A30` | text | in band_80196800 [overlay band] +0xA230 | `LOADER_RECORDS.md`, `loader_records/AREA.md` |
| `0x801A0A4C` | text | in band_80196800 [overlay band] +0xA24C | `loader_records/AREA.md` |
| `0x801A0A54` | text | in band_80196800 [overlay band] +0xA254 | `loader_records/AREA.md` |
| `0x801A0A5C` | text | in band_80196800 [overlay band] +0xA25C | `loader_records/AREA.md` |
| `0x801A0A64` | text | in band_80196800 [overlay band] +0xA264 | `loader_records/AREA.md` |
| `0x801A0A8C` | text | in band_80196800 [overlay band] +0xA28C | `loader_records/AREA.md` |
| `0x801A0AA8` | text | in band_80196800 [overlay band] +0xA2A8 | `loader_records/AREA.md`, `loader_records/SCENARIO.md` |
| `0x801A0BA8` | text | in band_80196800 [overlay band] +0xA3A8 | `loader_records/AREA.md` |
| `0x801A0BAC` | text | in band_80196800 [overlay band] +0xA3AC | `loader_records/AREA.md` |
| `0x801A0BB0` | text | in band_80196800 [overlay band] +0xA3B0 | `LOADER_RECORDS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x801A0BB4` | text | in band_80196800 [overlay band] +0xA3B4 | `loader_records/AREA.md` |
| `0x801A0D48` | text | in band_80196800 [overlay band] +0xA548 | `loader_records/SCENARIO.md` |
| `0x801A0D60` | text | in band_80196800 [overlay band] +0xA560 | `loader_records/SCENARIO.md` |
| `0x801A0D64` | text | in band_80196800 [overlay band] +0xA564 | `loader_records/SCENARIO.md` |
| `0x801A0D6C` | text | in band_80196800 [overlay band] +0xA56C | `loader_records/SCENARIO.md` |
| `0x801A0D74` | text | in band_80196800 [overlay band] +0xA574 | `loader_records/SCENARIO.md` |
| `0x801A0DF4` | text | in band_80196800 [overlay band] +0xA5F4 | `loader_records/SCENARIO.md` |
| `0x801A1538` | text | in band_80196800 [overlay band] +0xAD38 | `STATUS.md` |
| `0x801A1720` | text | in band_80196800 [overlay band] +0xAF20 | `STATUS.md` |
| `0x801A19A8` | text | in band_80196800 [overlay band] +0xB1A8 | `STATUS.md` |
| `0x801A27A8` | text | Script_ShowMessage [evidence] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `OVERLAYS.md`, `STATUS.md`, `TEXT_ENGINE.md`, `zero-fill-dispatch-audit.md` |
| `0x801A28D0` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801A290C` | text | ≤ Script_ShowMessage (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x164 (nearest below, span unknown) | `loader_records/SCENARIO.md` |
| `0x801A36BC` | text | ≤ Script_ShowMessage (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0xF14 (nearest below, span unknown) | `STATUS.md`, `crash-kernel-ram-2934.md` |
| `0x801A4A10` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801A4D24` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801A4F44` | text | in band_80196800 [overlay band] +0xE744 | `TEXT_ENGINE.md` |
| `0x801A5BC8` | text | in band_80196800 [overlay band] +0xF3C8 | `AREA_PCS.md` |
| `0x801A870C` | text | in band_80196800 [overlay band] +0x11F0C | `BATTLE_RAM.md`, `loader_records/SCENARIO.md` |
| `0x801A8728` | text | in band_80196800 [overlay band] +0x11F28 | `loader_records/SCENARIO.md` |
| `0x801A8794` | text | in band_80196800 [overlay band] +0x11F94 | `loader_records/SCENARIO.md` |
| `0x801A87EC` | text | in band_80196800 [overlay band] +0x11FEC | `loader_records/SCENARIO.md` |
| `0x801A880C` | text | in band_80196800 [overlay band] +0x1200C | `loader_records/AREA.md`, `loader_records/SCENARIO.md` |
| `0x801A8810` | text | in band_80196800 [overlay band] +0x12010 | `loader_records/AREA.md` |
| `0x801A881C` | text | in band_80196800 [overlay band] +0x1201C | `LOADER_RECORDS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x801A8820` | text | in band_80196800 [overlay band] +0x12020 | `loader_records/AREA.md` |
| `0x801A8834` | text | in band_80196800 [overlay band] +0x12034 | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x801A8880` | text | in band_80196800 [overlay band] +0x12080 | `loader_records/SCENARIO.md` |
| `0x801A8900` | text | in band_80196800 [overlay band] +0x12100 | `loader_records/SCENARIO.md` |
| `0x801A891C` | text | in band_80196800 [overlay band] +0x1211C | `loader_records/SCENARIO.md` |
| `0x801A89AC` | text | in band_80196800 [overlay band] +0x121AC | `loader_records/SCENARIO.md` |
| `0x801A8A3C` | text | in band_80196800 [overlay band] +0x1223C | `loader_records/SCENARIO.md` |
| `0x801A8BF8` | text | in band_80196800 [overlay band] +0x123F8 | `loader_records/SCENARIO.md` |
| `0x801A8C34` | text | in band_80196800 [overlay band] +0x12434 | `loader_records/AREA.md`, `loader_records/SCENARIO.md` |
| `0x801A8C58` | text | in band_80196800 [overlay band] +0x12458 | `INSERT_RUBY.md` |
| `0x801A8CB4` | text | in band_80196800 [overlay band] +0x124B4 | `loader_records/SCENARIO.md` |
| `0x801A8D44` | text | in band_80196800 [overlay band] +0x12544 | `loader_records/AREA.md` |
| `0x801A8DB8` | text | in band_80196800 [overlay band] +0x125B8 | `loader_records/PLCHAR.md` |
| `0x801A8FAC` | text | in band_80196800 [overlay band] +0x127AC | `loader_records/AREA.md` |
| `0x801A9680` | text | in band_80196800 [overlay band] +0x12E80 | `loader_records/AREA.md` |
| `0x801A9728` | text | in band_80196800 [overlay band] +0x12F28 | `loader_records/SCENARIO.md` |
| `0x801A9B5C` | text | in band_80196800 [overlay band] +0x1335C | `loader_records/AREA.md` |
| `0x801A9B84` | text | in band_80196800 [overlay band] +0x13384 | `loader_records/SCENARIO.md` |
| `0x801A9F94` | text | in band_80196800 [overlay band] +0x13794 | `loader_records/AREA.md` |
| `0x801AB470` | text | in band_80196800 [overlay band] +0x14C70 | `loader_records/AREA.md` |
| `0x801AD93C` | text | in band_80196800 [overlay band] +0x1713C | `INSERT_RUBY.md` |
| `0x801AD9D0` | text | in band_80196800 [overlay band] +0x171D0 | `INSERT_RUBY.md` |
| `0x801ADE10` | text | in band_80196800 [overlay band] +0x17610 | `LOADER_RECORDS.md`, `loader_records/AREA.md` |
| `0x801AEDD4` | text | Char_LevelUp [evidence] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801B1638` | text | in band_80196800 [overlay band] +0x1AE38 | `STATUS.md`, `crash-kernel-ram-2934.md` |
| `0x801B1C80` | text | in band_80196800 [overlay band] +0x1B480 | `BATTLE_RAM.md` |
| `0x801B1DF4` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801B1E3C` | text | unnamed function root (seeds/ghidra_funcs.txt) | `BATTLE_RAM.md`, `zero-fill-dispatch-audit.md` |
| `0x801B2028` | text | in band_80196800 [overlay band] +0x1B828 | `loader_records/SCENARIO.md` |
| `0x801B25E8` | text | in band_80196800 [overlay band] +0x1BDE8 | `loader_records/AREA.md` |
| `0x801B277C` | text | in band_80196800 [overlay band] +0x1BF7C | `loader_records/AREA.md` |
| `0x801B2868` | text | in band_80196800 [overlay band] +0x1C068 | `loader_records/AREA.md` |
| `0x801B29FC` | text | in band_80196800 [overlay band] +0x1C1FC | `loader_records/SCENARIO.md` |
| `0x801B3870` | text | in band_80196800 [overlay band] +0x1D070 | `INSERT_RUBY.md`, `STATUS.md` |
| `0x801B3C54` | text | in band_80196800 [overlay band] +0x1D454 | `loader_records/PLCHAR.md` |
| `0x801B3C78` | text | in band_80196800 [overlay band] +0x1D478 | `LOADER_RECORDS.md`, `loader_records/PLCHAR.md` |
| `0x801B3D4C` | text | in band_80196800 [overlay band] +0x1D54C | `loader_records/PLCHAR.md` |
| `0x801B3FC0` | text | Field_SearchSpot [evidence] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `AREA_PCS.md`, `WORLD_ITEMS.md` |
| `0x801B4028` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x68 (nearest below, span unknown) | `WORLD_ITEMS.md` |
| `0x801B4044` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x84 (nearest below, span unknown) | `WORLD_ITEMS.md` |
| `0x801B4094` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0xD4 (nearest below, span unknown) | `INSERT_RUBY.md`, `STATUS.md` |
| `0x801B4230` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x270 (nearest below, span unknown) | `loader_records/SCENARIO.md` |
| `0x801B468C` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x6CC (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801B46A8` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x6E8 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801B46B0` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x6F0 (nearest below, span unknown) | `LOADER_RECORDS.md`, `loader_records/PLCHAR.md` |
| `0x801B4CC4` | text | ≤ Field_SearchSpot (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0xD04 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801B6444` | text | in band_80196800 [overlay band] +0x1FC44 | `BATTLE_RAM.md` |
| `0x801B69AC` | text | unnamed function root (seeds/ghidra_funcs.txt) | `BATTLE_RAM.md`, `zero-fill-dispatch-audit.md` |
| `0x801B6C4C` | text | Field_FindSearchSpot [evidence] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `AREA_PCS.md`, `WORLD_ITEMS.md` |
| `0x801B6E50` | text | Field_GiveZenny [evidence] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `AREA_PCS.md`, `INSERT_RUBY.md`, `WORLD_ITEMS.md` |
| `0x801B6EA0` | text | ≤ Field_GiveZenny (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x50 (nearest below, span unknown) | `WORLD_ITEMS.md` |
| `0x801B731C` | text | ≤ Field_GiveZenny (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x4CC (nearest below, span unknown) | `loader_records/SCENARIO.md` |
| `0x801B7878` | text | ≤ Field_GiveZenny (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0xA28 (nearest below, span unknown) | `loader_records/AREA.md` |
| `0x801BE38C` | text | in band_80196800 [overlay band] +0x27B8C | `loader_records/PLCHAR.md` |
| `0x801BE4E4` | text | in band_80196800 [overlay band] +0x27CE4 | `loader_records/PLCHAR.md` |
| `0x801BE4E8` | text | in band_80196800 [overlay band] +0x27CE8 | `loader_records/PLCHAR.md` |
| `0x801BE4F0` | text | in band_80196800 [overlay band] +0x27CF0 | `loader_records/PLCHAR.md` |
| `0x801BE4F4` | text | in band_80196800 [overlay band] +0x27CF4 | `loader_records/PLCHAR.md` |
| `0x801BE4F8` | text | in band_80196800 [overlay band] +0x27CF8 | `loader_records/PLCHAR.md` |
| `0x801BE4FC` | text | in band_80196800 [overlay band] +0x27CFC | `loader_records/PLCHAR.md` |
| `0x801BE500` | text | in band_80196800 [overlay band] +0x27D00 | `loader_records/PLCHAR.md` |
| `0x801BE508` | text | in band_80196800 [overlay band] +0x27D08 | `LOADER_RECORDS.md`, `loader_records/PLCHAR.md` |
| `0x801C0E50` | text | ≤ Encounter_PlaceParty (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0xD3C (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x801C224C` | text | Battle_InitPartyMember [hypothesis] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `zero-fill-dispatch-audit.md` |
| `0x801C23F8` | text | Battle_InitPartyContexts [evidence] in Field/map core (large) (BIN/ETC/GAME.EMI#0) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801C253C` | text | ≤ Battle_InitPartyContexts (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x144 (nearest below, span unknown) | `STATUS.md` |
| `0x801C2DE8` | text | ≤ Battle_InitPartyContexts (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0x9F0 (nearest below, span unknown) | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x801C2E34` | text | ≤ Battle_InitPartyContexts (overlay Field/map core (large) (BIN/ETC/GAME.EMI#0)) +0xA3C (nearest below, span unknown) | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x801C34C8` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801C3530` | text | in band_80196800 [overlay band] +0x2CD30 | `BATTLE_RAM.md` |
| `0x801C388C` | text | in band_80196800 [overlay band] +0x2D08C | `BATTLE_RAM.md` |
| `0x801C3998` | text | in band_80196800 [overlay band] +0x2D198 | `BATTLE_RAM.md` |
| `0x801C5C40` | text | unnamed function root (seeds/ghidra_funcs.txt) | `zero-fill-dispatch-audit.md` |
| `0x801C6790` | text | in band_80196800 [overlay band] +0x2FF90 | `BATTLE_RAM.md` |
| `0x801C67AC` | text | in band_80196800 [overlay band] +0x2FFAC | `BATTLE_RAM.md` |
| `0x801C8A4C` | text | in band_80196800 [overlay band] +0x3224C | `LOADER_RECORDS.md`, `loader_records/BOSS.md` |
| `0x801C8A9C` | text | in band_80196800 [overlay band] +0x3229C | `loader_records/BOSS.md` |
| `0x801C8C04` | text | in band_80196800 [overlay band] +0x32404 | `loader_records/SCENARIO.md` |
| `0x801C8C80` | text | in band_80196800 [overlay band] +0x32480 | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x801C8F54` | text | in band_80196800 [overlay band] +0x32754 | `ADDRESS_MAPS.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/SCENARIO.md` |
| `0x801C8F68` | text | in band_80196800 [overlay band] +0x32768 | `loader_records/SCENARIO.md` |
| `0x801C8F6C` | text | in band_80196800 [overlay band] +0x3276C | `loader_records/SCENARIO.md` |
| `0x801C93B4` | text | in band_80196800 [overlay band] +0x32BB4 | `loader_records/SCENARIO.md` |
| `0x801C944C` | text | in band_80196800 [overlay band] +0x32C4C | `ADDRESS_MAPS.md`, `HANDOFF.md`, `LOADER_RECORDS.md`, `README.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/SCENARIO.md` |
| `0x801C95BC` | text | in band_80196800 [overlay band] +0x32DBC | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x801C95E8` | text | in band_80196800 [overlay band] +0x32DE8 | `loader_records/SCENARIO.md` |
| `0x801C96F4` | text | in band_80196800 [overlay band] +0x32EF4 | `loader_records/SCENARIO.md` |
| `0x801C9700` | text | in band_80196800 [overlay band] +0x32F00 | `LOADER_RECORDS.md`, `loader_records/SCENARIO.md` |
| `0x801C9904` | text | in band_80196800 [overlay band] +0x33104 | `loader_records/AREA.md` |
| `0x801C9934` | text | in band_80196800 [overlay band] +0x33134 | `BATTLE_RAM.md`, `IDEAS.md`, `STATUS.md` |
| `0x801C9948` | text | in band_80196800 [overlay band] +0x33148 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801C995C` | text | in band_80196800 [overlay band] +0x3315C | `IDEAS.md`, `STATUS.md`, `TEXT_TABLES.md` |
| `0x801C9E64` | text | in band_80196800 [overlay band] +0x33664 | `TEXT_TABLES.md` |
| `0x801C9F24` | text | in band_80196800 [overlay band] +0x33724 | `TEXT_TABLES.md` |
| `0x801C9F2F` | text | in band_80196800 [overlay band] +0x3372F | `BATTLE_RAM.md` |
| `0x801CA5A0` | text | in band_80196800 [overlay band] +0x33DA0 | `TEXT_TABLES.md` |
| `0x801CAA68` | text | in band_80196800 [overlay band] +0x34268 | `TEXT_TABLES.md` |
| `0x801CB230` | text | in band_80196800 [overlay band] +0x34A30 | `BATTLE_RAM.md`, `EMI_TYPES.md`, `IDEAS.md`, `STATUS.md`, `TEXT_TABLES.md` |
| `0x801CB231` | text | in band_80196800 [overlay band] +0x34A31 | `BATTLE_RAM.md`, `IDEAS.md`, `TEXT_TABLES.md` |
| `0x801CC068` | text | in band_80196800 [overlay band] +0x35868 | `BATTLE_RAM.md`, `EMI_TYPES.md`, `GHIDRA.md`, `STATUS.md` |
| `0x801CD8F0` | text | in band_80196800 [overlay band] +0x370F0 | `HANDOFF.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/PLCHAR.md`, `loader_records/SCENARIO.md` |
| `0x801CD964` | text | in band_80196800 [overlay band] +0x37164 | `HANDOFF.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/PLCHAR.md`, `loader_records/SCENARIO.md` |
| `0x801CDC4C` | text | in band_80196800 [overlay band] +0x3744C | `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/SCENARIO.md` |
| `0x801CDC9C` | text | in band_80196800 [overlay band] +0x3749C | `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/SCENARIO.md` |
| `0x801CDF18` | text | in band_80196800 [overlay band] +0x37718 | `ADDRESS_MAPS.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x801CDF1A` | text | in band_80196800 [overlay band] +0x3771A | `loader_records/BOSS.md` |
| `0x801CDF1B` | text | in band_80196800 [overlay band] +0x3771B | `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x801CDFF8` | text | in band_80196800 [overlay band] +0x377F8 | `ADDRESS_MAPS.md`, `LOADER_RECORDS.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/BOSS.md` |
| `0x801CE000` | text | band_801CE000 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `HANDOFF.md`, `IDEAS.md`, `STATUS.md`, `band-overlap-attribution.md`, `remote-plan-2026-09-05.md` |
| `0x801CE04A` | text | in band_801CE000 [overlay band] +0x4A | `loader_records/BOSS.md` |
| `0x801CE0E4` | text | in band_801CE000 [overlay band] +0xE4 | `OVERLAYS.md`, `loader_records/BOSS.md` |
| `0x801CE400` | text | band_801CE400 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `HANDOFF.md`, `IDEAS.md`, `LOADER_RECORDS.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `band-overlap-attribution.md`, `loader_records/PLCHAR.md`, `loader_records/SCENARIO.md`, `zero-fill-dispatch-audit.md` |
| `0x801CE401` | text | in band_801CE400 [overlay band] +0x1 | `OVERLAYS.md`, `STATUS.md` |
| `0x801CE404` | text | engine loader entry: combo 0 slot[0][0] in Party character set 012 (BIN/PLCHAR/PLP012.EMI#0) (+18 more) | `HANDOFF.md`, `STATUS.md` |
| `0x801CE724` | text | in band_801CE400 [overlay band] +0x324 | `STATUS.md` |
| `0x801CEEDC` | text | in band_801CE400 [overlay band] +0xADC | `ADDRESS_MAPS.md`, `HANDOFF.md`, `IDEAS.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `STATUS.md` |
| `0x801CF980` | text | in band_801CE400 [overlay band] +0x1580 | `STATUS.md` |
| `0x801CFD3C` | text | engine loader entry: combo 0 tableA in Party character set 012 (BIN/PLCHAR/PLP012.EMI#0) | `loader_records/PLCHAR.md` |
| `0x801CFD40` | text | in band_801CE400 [overlay band] +0x1940 | `loader_records/PLCHAR.md` |
| `0x801CFD4C` | text | in band_801CE400 [overlay band] +0x194C | `loader_records/PLCHAR.md` |
| `0x801CFD54` | text | in band_801CE400 [overlay band] +0x1954 | `loader_records/PLCHAR.md` |
| `0x801CFD58` | text | in band_801CE400 [overlay band] +0x1958 | `loader_records/PLCHAR.md` |
| `0x801CFD60` | text | in band_801CE400 [overlay band] +0x1960 | `loader_records/PLCHAR.md` |
| `0x801CFD68` | text | in band_801CE400 [overlay band] +0x1968 | `loader_records/PLCHAR.md` |
| `0x801CFDCC` | text | in band_801CE400 [overlay band] +0x19CC | `loader_records/PLCHAR.md` |
| `0x801D0000` | text | in band_801CE400 [overlay band] +0x1C00 | `loader_records/BOSS.md` |
| `0x801D0AA8` | text | in band_801CE400 [overlay band] +0x26A8 | `STATUS.md` |
| `0x801D0ACC` | text | in band_801CE000 [overlay band] +0x2ACC | `ADDRESS_MAPS.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md` |
| `0x801D0C00` | text | band_801D0C00 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `BATTLE_RAM.md`, `GHIDRA.md`, `HANDOFF.md`, `IDEAS.md`, `LOCALIZATION.md`, `NAME_MAP.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `band-overlap-attribution.md`, `loader_records/AREA.md`, `loader_records/BOSS.md`, `loader_records/PLCHAR.md`, `loader_records/SCENARIO.md`, `regional-builds.md` |
| `0x801D0C01` | text | in band_801D0C00 [overlay band] +0x1 | `OVERLAYS.md`, `zero-fill-dispatch-audit.md` |
| `0x801D0C04` | text | unnamed function root (seeds/ghidra_funcs.txt) | `ADDRESS_MAPS.md`, `BATTLE_RAM.md`, `GHIDRA.md`, `STATUS.md`, `TEXT_TABLES.md`, `zero-fill-dispatch-audit.md` |
| `0x801D0C64` | text | in band_801D0C00 [overlay band] +0x64 | `GHIDRA.md` |
| `0x801D0C68` | text | in band_801D0C00 [overlay band] +0x68 | `GHIDRA.md` |
| `0x801D0C7C` | text | in band_801D0C00 [overlay band] +0x7C | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801D0CA0` | text | in band_801D0C00 [overlay band] +0xA0 | `loader_records/AREA.md` |
| `0x801D0CB8` | text | in band_801D0C00 [overlay band] +0xB8 | `BATTLE_RAM.md`, `remote-plan-2026-09-05.md` |
| `0x801D0D94` | text | in band_801D0C00 [overlay band] +0x194 | `IDEAS.md`, `TEXT_TABLES.md` |
| `0x801D0E54` | text | in band_801D0C00 [overlay band] +0x254 | `STATUS.md` |
| `0x801D0EC0` | text | in band_801D0C00 [overlay band] +0x2C0 | `loader_records/SCENARIO.md` |
| `0x801D0ED4` | text | SaveFile_NameTemplate (ascii strings) in Field main menu (status / equip / items) (BIN/ETC/START.EMI#8) | `DATA_ISLANDS.md`, `SAVE_IMPORT.md` |
| `0x801D0F80` | text | in band_801D0C00 [overlay band] +0x380 | `GHIDRA.md`, `OVERLAY_HEADERS.md` |
| `0x801D0F9C` | text | in band_801D0C00 [overlay band] +0x39C | `GHIDRA.md` |
| `0x801D0FD4` | text | in band_801D0C00 [overlay band] +0x3D4 | `loader_records/PLCHAR.md` |
| `0x801D1014` | text | in band_801D0C00 [overlay band] +0x414 | `HANDOFF.md` |
| `0x801D10A8` | text | in band_801D0C00 [overlay band] +0x4A8 | `BATTLE_RAM.md` |
| `0x801D10DC` | text | Examine_ActiveTick [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md` |
| `0x801D112C` | text | ≤ Examine_ActiveTick (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x50 (nearest below, span unknown) | `GHIDRA.md` |
| `0x801D11D8` | text | ≤ Examine_ActiveTick (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xFC (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801D1228` | text | Battle_Init [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `HANDOFF.md`, `STATUS.md`, `remote-plan-2026-09-05.md` |
| `0x801D13D8` | text | ≤ Battle_Init (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x1B0 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801D1490` | text | ≤ Battle_Init (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x268 (nearest below, span unknown) | `STATUS.md` |
| `0x801D15A4` | text | ≤ Battle_Init (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x37C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801D1734` | text | ≤ Battle_Init (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x50C (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x801D1740` | text | ≤ Battle_Init (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x518 (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x801D1C4C` | text | ≤ Battle_Init (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xA24 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801D1C88` | text | Battle_RoundStart [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D1E84` | text | ≤ Battle_RoundStart (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x1FC (nearest below, span unknown) | `GHIDRA.md` |
| `0x801D1E9C` | text | ≤ Battle_RoundStart (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x214 (nearest below, span unknown) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801D2198` | text | BattleMenu_DirectionHold [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md` |
| `0x801D22EC` | text | ≤ BattleMenu_DirectionHold (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x154 (nearest below, span unknown) | `HANDOFF.md`, `STATUS.md` |
| `0x801D24CC` | text | BattleMenu_ConfirmDispatch [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D2520` | text | ≤ BattleMenu_ConfirmDispatch (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x54 (nearest below, span unknown) | `BATTLE_RAM.md`, `HANDOFF.md` |
| `0x801D2598` | text | Cmd_AutoBattle_Begin [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D2738` | text | ≤ Cmd_AutoBattle_Begin (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x1A0 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801D2774` | text | Battle_CommitRound [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D2B50` | text | Battle_BeginAction [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D3ED0` | text | in band_801D0C00 [overlay band] +0x32D0 | `OVERLAY_HEADERS.md` |
| `0x801D51D8` | text | in band_801D0C00 [overlay band] +0x45D8 | `BATTLE_RAM.md` |
| `0x801D69F0` | text | Save_BuildImage [evidence] in Shop / inn / save-point game-mode (BIN/ETC/SHOP.EMI#0) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801D6C58` | text | ≤ Save_BuildImage (overlay Shop / inn / save-point game-mode (BIN/ETC/SHOP.EMI#0)) +0x268 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801D6D94` | text | Menu_EquipConfirm [evidence] in Field main menu (status / equip / items) (BIN/ETC/START.EMI#8) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801D709C` | text | ≤ Menu_EquipConfirm (overlay Field main menu (status / equip / items) (BIN/ETC/START.EMI#8)) +0x308 (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801D710C` | text | ≤ Menu_EquipConfirm (overlay Field main menu (status / equip / items) (BIN/ETC/START.EMI#8)) +0x378 (nearest below, span unknown) | `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x801D7114` | text | Battle_PhaseStep_Escape [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D71E0` | text | Battle_PhaseStep_Exit1 [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D72F8` | text | Battle_PhaseStep_Exit2 [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801D7D88` | text | ≤ Battle_PhaseStep_Exit2 (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xA90 (nearest below, span unknown) | `STATUS.md` |
| `0x801D8060` | text | BattleMenu_TargetCursor [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `IDEAS.md` |
| `0x801D8CD0` | text | ≤ BattleMenu_TargetCursor (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xC70 (nearest below, span unknown) | `DATA_ISLANDS.md`, `STATUS.md` |
| `0x801D9A84` | text | in band_801D0C00 [overlay band] +0x8E84 | `GHIDRA.md` |
| `0x801D9C50` | text | in band_801D0C00 [overlay band] +0x9050 | `GHIDRA.md` |
| `0x801D9CA4` | text | in band_801D0C00 [overlay band] +0x90A4 | `STATUS.md` |
| `0x801DA484` | text | in band_801D0C00 [overlay band] +0x9884 | `GHIDRA.md` |
| `0x801DA578` | text | in band_801D0C00 [overlay band] +0x9978 | `GHIDRA.md` |
| `0x801DAAB4` | text | Battle_BuildTurnOrder [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801DAE14` | text | ≤ Battle_BuildTurnOrder (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x360 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801DB1C4` | text | ≤ Battle_BuildTurnOrder (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x710 (nearest below, span unknown) | `IDEAS.md` |
| `0x801DB214` | text | ≤ Battle_BuildTurnOrder (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x760 (nearest below, span unknown) | `BATTLE_RAM.md`, `IDEAS.md`, `TEXT_TABLES.md` |
| `0x801DB231` | text | ≤ Battle_BuildTurnOrder (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x77D (nearest below, span unknown) | `STATUS.md` |
| `0x801DB45C` | text | Battle_ClearCommands [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801DB4EC` | text | Battle_ActorFrameUpdate [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md`, `STATUS.md` |
| `0x801DB594` | text | ≤ Battle_ActorFrameUpdate (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xA8 (nearest below, span unknown) | `GHIDRA.md` |
| `0x801DBB40` | text | Battle_ApplyDamage [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `IDEAS.md`, `STATUS.md` |
| `0x801DBEAC` | text | ≤ Battle_ApplyDamage (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x36C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801DC00C` | text | Battle_CalcDamage [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `GHIDRA.md`, `IDEAS.md` |
| `0x801DC704` | text | Battle_HitCheck_PartyTarget [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `remote-plan-2026-09-05.md` |
| `0x801DC85C` | text | Battle_HitCheck_EnemyTarget [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `remote-plan-2026-09-05.md` |
| `0x801DCAA0` | text | Battle_BaseDamage [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `IDEAS.md`, `remote-plan-2026-09-05.md` |
| `0x801DCC78` | text | Battle_PartyAvgDef [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801DCD18` | text | Battle_ScaleDamage [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801DCD40` | text | unnamed function root (seeds/ghidra_funcs.txt) | `NAME_MAP.md`, `zero-fill-dispatch-audit.md` |
| `0x801DD264` | text | AutoBattle_FillCommands [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801DD564` | text | BattleResult_AddExp [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `STATUS.md` |
| `0x801DD644` | text | ≤ BattleResult_AddExp (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xE0 (nearest below, span unknown) | `STATUS.md` |
| `0x801DE074` | text | ≤ Battle_WriteBackMember (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x800 (nearest below, span unknown) | `GHIDRA.md` |
| `0x801DE098` | text | ≤ Battle_WriteBackMember (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x824 (nearest below, span unknown) | `OVERLAYS.md`, `STATUS.md` |
| `0x801DF3AC` | text | ≤ Battle_InitMemberActor (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x4E4 (nearest below, span unknown) | `BATTLE_RAM.md`, `GHIDRA.md` |
| `0x801DF9D0` | text | ≤ Attack_SetAnim (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x100 (nearest below, span unknown) | `IDEAS.md` |
| `0x801DFA04` | text | Attack_Action [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md` |
| `0x801DFB18` | text | ≤ Attack_Action (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x114 (nearest below, span unknown) | `IDEAS.md` |
| `0x801DFB90` | text | ≤ Attack_Action (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x18C (nearest below, span unknown) | `GHIDRA.md` |
| `0x801DFC68` | text | Battle_ResolveAction_Party [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801E00EC` | text | Examine_LearnCheck [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md` |
| `0x801E0400` | text | Defend_Action [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md` |
| `0x801E0434` | text | ≤ Defend_Action (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x34 (nearest below, span unknown) | `IDEAS.md` |
| `0x801E04B4` | text | Examine_State_Cue [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `IDEAS.md` |
| `0x801E06C8` | text | ≤ Examine_State_Nop (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x58 (nearest below, span unknown) | `IDEAS.md` |
| `0x801E19A0` | text | Actor_SkillItemDone [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801E1D58` | text | Actor_ActionDone [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801E2464` | text | ≤ Actor_ActionDone (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x70C (nearest below, span unknown) | `loader_records/SCENARIO.md` |
| `0x801E2500` | text | Examine_EnemyMove_Tick [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `IDEAS.md` |
| `0x801E3AE0` | text | in band_801D0C00 [overlay band] +0x12EE0 | `IDEAS.md` |
| `0x801E3B8C` | text | Battle_ResolveAction_Enemy [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801E42C0` | text | ≤ Battle_ResolveAction_Enemy (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x734 (nearest below, span unknown) | `IDEAS.md` |
| `0x801E5230` | text | in band_801D0C00 [overlay band] +0x14630 | `IDEAS.md` |
| `0x801E524C` | text | in band_801D0C00 [overlay band] +0x1464C | `IDEAS.md` |
| `0x801E525C` | text | Battle_RollDrops [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801E542C` | text | Battle_EnemyDefeated [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801E5710` | text | ≤ Battle_EnemyDefeated (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x2E4 (nearest below, span unknown) | `DATA_ISLANDS.md`, `STATUS.md` |
| `0x801E584C` | text | ≤ Battle_EnemyDefeated (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x420 (nearest below, span unknown) | `GHIDRA.md` |
| `0x801E5F7C` | text | ≤ Battle_EnemyDefeated (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xB50 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801E5F94` | text | ≤ Battle_EnemyDefeated (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xB68 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801E60A4` | text | ≤ Battle_EnemyDefeated (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xC78 (nearest below, span unknown) | `BATTLE_RAM.md`, `loader_records/SCENARIO.md` |
| `0x801E614C` | text | ≤ Battle_EnemyDefeated (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xD20 (nearest below, span unknown) | `loader_records/SCENARIO.md` |
| `0x801E69E0` | text | Examine_QuestionMark_Tick [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `IDEAS.md` |
| `0x801E6A68` | text | Examine_QuestionMark_Begin [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `IDEAS.md` |
| `0x801E6B58` | text | ≤ Examine_QuestionMark_Begin (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF0 (nearest below, span unknown) | `IDEAS.md` |
| `0x801E6C60` | text | ≤ Examine_QuestionMark_Begin (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x1F8 (nearest below, span unknown) | `HANDOFF.md`, `IDEAS.md` |
| `0x801E739C` | text | ≤ Examine_QuestionMark_Begin (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x934 (nearest below, span unknown) | `HANDOFF.md` |
| `0x801E8FAC` | text | Battle_FrameTask [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `GHIDRA.md`, `IDEAS.md` |
| `0x801E9538` | text | ≤ Battle_State_Nop (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xE4 (nearest below, span unknown) | `IDEAS.md` |
| `0x801E995C` | text | ≤ Battle_State_Nop (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x508 (nearest below, span unknown) | `IDEAS.md` |
| `0x801E9A50` | text | ≤ Battle_State_Nop (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x5FC (nearest below, span unknown) | `IDEAS.md` |
| `0x801E9B74` | text | Battle_MemberStatusTick [hypothesis] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `STATUS.md` |
| `0x801EA204` | text | HUD_GaugeUpdate [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801EA4D0` | text | ≤ HUD_GaugeUpdate (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x2CC (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EA600` | text | BattleBanner_Task [evidence] in Battle game-mode (BIN/BATTLE/BATTLE.EMI#3) | `BATTLE_RAM.md` |
| `0x801EAEEC` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x7C8 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EAEF8` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x7D4 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EAF38` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x814 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EAF3E` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x81A (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EAF50` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x82C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EAF70` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0x84C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB448` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xD24 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB460` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xD3C (nearest below, span unknown) | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801EB4A4` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xD80 (nearest below, span unknown) | `BATTLE_RAM.md`, `IDEAS.md`, `STATUS.md`, `TEXT_TABLES.md` |
| `0x801EB4C0` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xD9C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB5A0` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xE7C (nearest below, span unknown) | `OVERLAY_HEADERS.md`, `remote-plan-2026-09-05.md` |
| `0x801EB5A5` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xE81 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB61D` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xEF9 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB620` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xEFC (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB622` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xEFE (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB624` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF00 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB626` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF02 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB628` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF04 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB634` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF10 (nearest below, span unknown) | `BATTLE_RAM.md`, `HANDOFF.md`, `STATUS.md` |
| `0x801EB638` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF14 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB640` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF1C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB644` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF20 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB654` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF30 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB69C` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF78 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB69D` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF79 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB6A0` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF7C (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB6A4` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF80 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB6B4` | text | ≤ BattleBanner_SlideOut (overlay Battle game-mode (BIN/BATTLE/BATTLE.EMI#3)) +0xF90 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EB74C` | text | in band_801D0C00 [overlay band] +0x1AB4C | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801EB758` | text | in band_801D0C00 [overlay band] +0x1AB58 | `BATTLE_RAM.md` |
| `0x801EB800` | text | in band_801D0C00 [overlay band] +0x1AC00 | `ADDRESS_MAPS.md` |
| `0x801EB8D0` | text | in band_801D0C00 [overlay band] +0x1ACD0 | `remote-plan-2026-09-05.md` |
| `0x801EC258` | text | in band_801D0C00 [overlay band] +0x1B658 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801EC25E` | text | in band_801D0C00 [overlay band] +0x1B65E | `BATTLE_RAM.md` |
| `0x801EC273` | text | in band_801D0C00 [overlay band] +0x1B673 | `BATTLE_RAM.md` |
| `0x801EC278` | text | in band_801D0C00 [overlay band] +0x1B678 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801EC27C` | text | in band_801D0C00 [overlay band] +0x1B67C | `BATTLE_RAM.md` |
| `0x801EC27E` | text | in band_801D0C00 [overlay band] +0x1B67E | `BATTLE_RAM.md` |
| `0x801EC294` | text | in band_801D0C00 [overlay band] +0x1B694 | `BATTLE_RAM.md` |
| `0x801EC3E8` | text | in band_801D0C00 [overlay band] +0x1B7E8 | `BATTLE_RAM.md`, `STATUS.md` |
| `0x801ED5BC` | text | in band_801D0C00 [overlay band] +0x1C9BC | `BATTLE_RAM.md` |
| `0x801ED93F` | text | in band_801D0C00 [overlay band] +0x1CD3F | `GHIDRA.md` |
| `0x801ED940` | text | in boot_exe_image [exe image] +0x15A140 | `ADDRESS_MAPS.md` |
| `0x801EEC00` | text | band_801EEC00 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `BATTLE_RAM.md`, `GHIDRA.md`, `HANDOFF.md`, `IDEAS.md`, `NAME_MAP.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `gpu-polyline-terminator.md`, `loader_records/SCENARIO.md`, `zero-fill-dispatch-audit.md` |
| `0x801EEC01` | text | in band_801EEC00 [overlay band] +0x1 | `OVERLAYS.md` |
| `0x801EEC10` | text | in band_801EEC00 [overlay band] +0x10 | `DATA_ISLANDS.md`, `OVERLAY_HEADERS.md`, `README.md`, `STATUS.md` |
| `0x801EEC14` | text | in band_801EEC00 [overlay band] +0x14 | `DATA_ISLANDS.md` |
| `0x801EEC50` | text | BattleResult_TallyFormats (ascii strings) in Battle result screen (BIN/BATTLE/BATL_END.EMI#0) | `DATA_ISLANDS.md` |
| `0x801EEC9C` | text | in band_801EEC00 [overlay band] +0x9C | `DATA_ISLANDS.md`, `STATUS.md` |
| `0x801EECA0` | text | in band_801EEC00 [overlay band] +0xA0 | `DATA_ISLANDS.md` |
| `0x801EECF4` | text | in band_801EEC00 [overlay band] +0xF4 | `gpu-polyline-terminator.md` |
| `0x801EED78` | text | in band_801EEC00 [overlay band] +0x178 | `loader_records/PLCHAR.md` |
| `0x801EEF58` | text | BattleResult_ExpTick [evidence] in Battle result screen (BIN/BATTLE/BATL_END.EMI#0) | `BATTLE_RAM.md` |
| `0x801EF118` | text | ≤ Card_LoadDirectory (overlay Memory-card manager module (BIN/ETC/SHOP.EMI#8)) +0x54 (nearest below, span unknown) | `loader_records/BOSS.md` |
| `0x801EF188` | text | Examine_EnemyMove_Begin [hypothesis] in Battle FX: Heal (BIN/BMAGIC/MAGIC069.EMI#3) | `GHIDRA.md`, `IDEAS.md`, `STATUS.md` |
| `0x801EF390` | text | BattleResult_Setup [evidence] in Battle result screen (BIN/BATTLE/BATL_END.EMI#0) | `BATTLE_RAM.md` |
| `0x801EF39C` | text | ≤ BattleResult_Setup (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0xC (nearest below, span unknown) | `loader_records/PLCHAR.md` |
| `0x801EF400` | text | ≤ BattleResult_Setup (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x70 (nearest below, span unknown) | `ADDRESS_MAPS.md`, `BATTLE_RAM.md` |
| `0x801EF554` | text | ≤ BattleResult_Setup (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x1C4 (nearest below, span unknown) | `IDEAS.md` |
| `0x801EF68C` | text | ≤ BattleResult_Setup (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x2FC (nearest below, span unknown) | `loader_records/BOSS.md`, `loader_records/SCENARIO.md` |
| `0x801EF6C4` | text | ≤ BattleResult_Setup (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x334 (nearest below, span unknown) | `BATTLE_RAM.md` |
| `0x801EF810` | text | BattleResult_ZennyTick [evidence] in Battle result screen (BIN/BATTLE/BATL_END.EMI#0) | `BATTLE_RAM.md`, `GHIDRA.md` |
| `0x801EF824` | text | ≤ BattleResult_ZennyTick (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x14 (nearest below, span unknown) | `STATUS.md` |
| `0x801EF840` | text | ≤ BattleResult_ZennyTick (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x30 (nearest below, span unknown) | `BATTLE_RAM.md`, `GHIDRA.md` |
| `0x801EF848` | text | ≤ BattleResult_ZennyTick (overlay Battle result screen (BIN/BATTLE/BATL_END.EMI#0)) +0x38 (nearest below, span unknown) | `STATUS.md` |
| `0x801EF874` | text | BattleResult_AwardDrops [hypothesis] in Battle result screen (BIN/BATTLE/BATL_END.EMI#0) · Card_CopyIconFrame1 [hypothesis] in Memory-card manager module (BIN/ETC/SHOP.EMI#8) | `BATTLE_RAM.md` |
| `0x801EF92C` | text | Card_CopyIconFrame2 [hypothesis] in Memory-card manager module (BIN/ETC/SHOP.EMI#8) | `BATTLE_RAM.md` |
| `0x801EF9C4` | text | ≤ Card_CopyIconFrame2 (overlay Memory-card manager module (BIN/ETC/SHOP.EMI#8)) +0x98 (nearest below, span unknown) | `IDEAS.md` |
| `0x801EF9E4` | text | Card_Open [evidence] in Memory-card manager module (BIN/ETC/SHOP.EMI#8) | `DATA_ISLANDS.md` |
| `0x801EFA84` | text | ≤ Card_Open (overlay Memory-card manager module (BIN/ETC/SHOP.EMI#8)) +0xA0 (nearest below, span unknown) | `IDEAS.md` |
| `0x801EFAB8` | text | ≤ Card_Open (overlay Memory-card manager module (BIN/ETC/SHOP.EMI#8)) +0xD4 (nearest below, span unknown) | `DATA_ISLANDS.md` |
| `0x801F0000` | text | ≤ Card_NextFile (overlay Memory-card manager module (BIN/ETC/SHOP.EMI#8)) +0x1D8 (nearest below, span unknown) | `STATUS.md` |
| `0x801F1834` | text | in band_801EEC00 [overlay band] +0x2C34 | `loader_records/PLCHAR.md` |
| `0x801F2C00` | text | band_801F2C00 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `HANDOFF.md`, `IDEAS.md`, `LOADER_RECORDS.md`, `NAME_MAP.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `README.md`, `STATUS.md`, `WORLD_ITEMS.md`, `loader_records/AREA.md`, `loader_records/SCENARIO.md`, `regional-builds.md` |
| `0x801F2C01` | text | in band_801F2C00 [overlay band] +0x1 | `OVERLAYS.md`, `zero-fill-dispatch-audit.md` |
| `0x801F2C04` | text | engine loader entry: area 3 handler[2] in AREA003 (BIN/WORLD00/AREA003.EMI#13) (+26 more) | `GHIDRA.md`, `STATUS.md`, `zero-fill-dispatch-audit.md` |
| `0x801F2C3C` | text | engine loader entry: area 121 handler[0] in AREA121 (BIN/WORLD03/AREA121.EMI#14) | `loader_records/AREA.md` |
| `0x801F2C8C` | text | engine loader entry: area 0 handler[0] in AREA000 (BIN/WORLD00/AREA000.EMI#13) | `ADDRESS_MAPS.md`, `STATUS.md` |
| `0x801F2E6C` | text | in band_801F2C00 [overlay band] +0x26C | `IDEAS.md`, `STATUS.md` |
| `0x801F3BBC` | text | in band_801F2C00 [overlay band] +0xFBC | `WORLD_ITEMS.md` |
| `0x801F3DFC` | text | in band_801F2C00 [overlay band] +0x11FC | `WORLD_ITEMS.md` |
| `0x801F3FF8` | text | in band_801F2C00 [overlay band] +0x13F8 | `loader_records/AREA.md` |
| `0x801F403C` | text | engine loader entry: area 145 handler[4] in AREA145 (BIN/WORLD03/AREA145.EMI#14) | `loader_records/AREA.md` |
| `0x801F4154` | text | in band_801F2C00 [overlay band] +0x1554 | `IDEAS.md` |
| `0x801F46D4` | text | engine loader entry: area 151 hook[4] in AREA151 (BIN/WORLD03/AREA151.EMI#13) | `IDEAS.md` |
| `0x801F4814` | text | in band_801F2C00 [overlay band] +0x1C14 | `IDEAS.md` |
| `0x801F4A30` | text | in band_801F2C00 [overlay band] +0x1E30 | `WORLD_ITEMS.md` |
| `0x801F4CE4` | text | in band_801F2C00 [overlay band] +0x20E4 | `WORLD_ITEMS.md` |
| `0x801F4D20` | text | in band_801F2C00 [overlay band] +0x2120 | `WORLD_ITEMS.md` |
| `0x801F4F80` | text | in band_801F2C00 [overlay band] +0x2380 | `loader_records/SCENARIO.md` |
| `0x801F54C4` | text | in band_801F2C00 [overlay band] +0x28C4 | `loader_records/SCENARIO.md` |
| `0x801F5930` | text | in band_801F2C00 [overlay band] +0x2D30 | `loader_records/SCENARIO.md` |
| `0x801F6C00` | text | band_801F6C00 [overlay band] (base) | `ADDRESS_MAPS.md`, `AREA_PCS.md`, `HANDOFF.md`, `LOADER_RECORDS.md`, `OVERLAYS.md`, `OVERLAY_EXTRACTION.md`, `OVERLAY_HEADERS.md`, `OVERLAY_SIZE.md`, `STATUS.md`, `loader_records/AREA.md`, `loader_records/SCENARIO.md`, `zero-fill-dispatch-audit.md` |
| `0x801F6C90` | text | engine loader entry: chapter 16 vtable[0] in Scenario event bank 16 (BIN/SCENARIO/SCENA16.EMI#0) | `HANDOFF.md`, `STATUS.md` |
| `0x801F6FFF` | text | in boot_exe_image [exe image] +0x1637FF | `GHIDRA.md` |
| `0x801F7000` | post-text | end of the boot EXE .text span (load + text_size) | `ADDRESS_MAPS.md`, `BRINGUP.md`, `regional-builds.md` |
| `0x801F7144` | post-text | unknown | `HANDOFF.md` |
| `0x801F7170` | post-text | unknown | `HANDOFF.md` |
| `0x801F71FC` | post-text | Credits_StaffRoll (ascii strings) in Scenario event bank 17 (BIN/SCENARIO/SCENA17.EMI#0) | `DATA_ISLANDS.md` |
| `0x801F7348` | post-text | unknown | `STATUS.md` |
| `0x801F7568` | post-text | unknown | `DATA_ISLANDS.md`, `STATUS.md` |
| `0x801F8598` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801F8C40` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801F913C` | post-text | engine loader entry: chapter 0 vtable[0] in Scenario event bank 00 (BIN/SCENARIO/SCENA00.EMI#0) | `loader_records/AREA.md` |
| `0x801F92F4` | post-text | unknown | `OVERLAY_HEADERS.md`, `STATUS.md`, `loader_records/SCENARIO.md` |
| `0x801F95DC` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801F9CAC` | post-text | engine loader entry: chapter 15 vtable[0] in Scenario event bank 15 (BIN/SCENARIO/SCENA15.EMI#0) | `loader_records/AREA.md` |
| `0x801F9EF8` | post-text | unknown | `OVERLAY_HEADERS.md` |
| `0x801FAEFC` | post-text | unknown | `loader_records/BOSS.md` |
| `0x801FAFE0` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FB6A8` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FB7C0` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FBE6C` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FC69C` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FC9FC` | post-text | unknown | `loader_records/AREA.md` |
| `0x801FCC20` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FCC28` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FD090` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FDB58` | post-text | unknown | `loader_records/SCENARIO.md` |
| `0x801FDB70` | post-text | unknown | `loader_records/AREA.md` |
| `0x801FE5F4` | post-text | unknown | `loader_records/AREA.md` |
| `0x801FFF90` | post-text | unknown | `BRINGUP.md` |
| `0x801FFFF0` | post-text | stack base (disc_probe.json) | `INVENTORY.md` |
