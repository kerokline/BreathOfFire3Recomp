/*
 * bof3_exp_boost.c -- EXP / zenny multiplier plugin (docs/EXP_BOOST.md).
 *
 * Trusted static plugin selected by mods/preloaded/packages/bof3.exp-boost:
 * one default-off feature "boost" with two bounded integer options ("exp",
 * "zenny", 0..50; 0 = grant nothing, so no level-ups), activated under the
 * id "bof3.exp-boost". The recompiler emits psx_mod_function_entry() at
 * Battle_EnemyDefeated 0x801E542C (BATTLE.EMI#3, game.toml
 * mod_function_entry_funcs). It is a plain jal target, which matters: the
 * hook is emitted only at a function's prologue, and the results-screen
 * phases (BattleResult_Setup / ExpTick / ZennyTick) are alias entries into
 * larger hosts, so hooking them emitted nothing (2026-09-13).
 *
 * The body reads the dying enemy through the current-object pointer
 * 0x801EB458 (not a0) and adds the record's yields (obj+0x86 EXP, obj+0x84
 * zenny, both u16) to the battle totals 0x80146328 / 0x8014632C. Scaling
 * the yields here scales the totals, the results-screen numbers, the
 * per-member award and level-ups. The results screen derives each phase's
 * tick step from its own total (/30), so the counters take the same time
 * at any multiplier. Zenny_Add and the EXP writer both cap at 9,999,999.
 *
 * Function-entry callbacks fire whether or not a feature is enabled, so the
 * multipliers stay at 1 until the activation callback (invoked only for an
 * enabled feature) reads the option. The 0x801D0C00 band is shared
 * (BATTLE / SHOP / STATUS / START): the hook first checks the resident
 * registry id at 0x801D0C00 is BATTLE.EMI#3's 0x10.
 *
 * An earlier revision also hooked BattleResult_AddExp 0x801DD564 to adjust
 * the tick step; it is gone from game.toml, and the built overlays carry
 * that inert hook only until the next overlay recompile.
 */
#include "mod_plugins.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PKG            "bof3.exp-boost"
#define FEAT           "boost"
#define OPT_EXP        "exp"
#define OPT_ZENNY      "zenny"

#define BAND_BASE      0x801D0C00u
#define BATTLE3_ID     0x10u

#define PC_DEFEATED    0x801E542Cu

#define CUR_OBJECT     0x801EB458u   /* pointer to the object being processed */
#define OBJ_ZENNY      0x84u         /* enemy object + 0x84 = record +0x04, u16 */
#define OBJ_EXP        0x86u         /* enemy object + 0x86 = record +0x06, u16 */

static unsigned g_exp_mult = 1;
static unsigned g_zenny_mult = 1;

static unsigned option_multiplier(const char *option) {
    char text[32] = "";
    char *end = NULL;
    long v;
    if (!psx_mod_option_value(PKG, FEAT, option, text, sizeof text) || !text[0])
        return 1;
    v = strtol(text, &end, 10);
    if (!end || *end != '\0' || v < 0 || v > 50) return 1;   /* 0 = grant nothing */
    return (unsigned)v;
}

static void activate(void) {
    g_exp_mult = option_multiplier(OPT_EXP);
    g_zenny_mult = option_multiplier(OPT_ZENNY);
    fprintf(stdout, "bof3_exp_boost: EXP x%u, zenny x%u\n", g_exp_mult, g_zenny_mult);
}

static uint16_t scaled16(uint16_t v, unsigned mult) {
    uint32_t r = (uint32_t)v * mult;
    return r > 0xFFFFu ? 0xFFFFu : (uint16_t)r;
}

static void on_enemy_defeated(struct CPUState *cpu, uint32_t address) {
    uint32_t obj;
    uint16_t exp, zen;
    (void)cpu; (void)address;
    if (g_exp_mult == 1 && g_zenny_mult == 1) return;
    if (psx_mod_read_word(BAND_BASE) != BATTLE3_ID) return;
    obj = psx_mod_read_word(CUR_OBJECT);
    if (obj < 0x80000000u || obj >= 0x80200000u) return;
    exp = psx_mod_read_half(obj + OBJ_EXP);
    zen = psx_mod_read_half(obj + OBJ_ZENNY);
    if (g_exp_mult != 1) psx_mod_write_half(obj + OBJ_EXP, scaled16(exp, g_exp_mult));
    if (g_zenny_mult != 1) psx_mod_write_half(obj + OBJ_ZENNY, scaled16(zen, g_zenny_mult));
    fprintf(stdout, "bof3_exp_boost: kill %08X EXP %u -> %u, zenny %u -> %u\n", obj, exp,
            psx_mod_read_half(obj + OBJ_EXP), zen, psx_mod_read_half(obj + OBJ_ZENNY));
}

PSX_MOD_CONSTRUCTOR(bof3_register_exp_boost_plugin) {
    int a = psx_mod_register_activation_plugin("bof3.exp-boost", activate);
    int h = psx_mod_register_function_entry_plugin("bof3.exp-boost", PC_DEFEATED, on_enemy_defeated);
    fprintf(stdout, "bof3_exp_boost: %s\n",
            a && h ? "registered (Battle_EnemyDefeated)" : "REGISTRATION FAILED");
}
