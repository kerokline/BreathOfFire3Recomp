/* bof3_localize.c -- deliver the English area script to the dialogue box.
 *
 * BoF3 never passes a string pointer through psx_dispatch, so the framework's
 * generic capture/apply hook cannot see its dialogue (docs/TEXT_ENGINE.md
 * "The resolver"). What it does do is store the resolved pointer into two
 * globals and then call MsgBox_Reset:
 *
 *     Msg_OpenScript(idx)   0x8015034C
 *         ptr = 0x80010000 + u16[0x80010000 + 2*idx]
 *         0x801490A8 = 0x801490AC = ptr
 *         MsgBox_Reset()    0x8015042C      <-- this plugin runs at its entry
 *
 * game.toml lists 0x8015042C in [recompiler].mod_function_entry_funcs, so the
 * generated C calls psx_mod_function_entry() there. The plugin reads the
 * pointer back, hashes the JP bytes as they sit in guest RAM, looks the hash
 * up in the generated table, copies the English bytes into enhancement memory
 * (Expansion 1, host-backed, readable by ordinary guest loads) and repoints
 * both globals. MsgBox_Reset then eats the leading 0x0C speaker byte from the
 * English copy exactly as it would from the JP, and the stepper and renderer
 * never know the difference. Nothing in game RAM is written; the JP script
 * block stays intact for the next message.
 *
 * Scope: area scripts only (pointers inside 0x80010000..0x80013FFF). The
 * system pool at 0x80014000 (menus, items, name entry) goes through
 * Msg_OpenSystem and lands here too, but no table covers it yet, so those
 * messages miss the lookup and stay Japanese by construction.
 *
 * Language: the launcher's Localization dropdown, settings.toml and PSX_LANG
 * all resolve into the framework's text_xlate module; it exposes no getter,
 * so the resolved code is read back from its "stats" debug JSON (a public
 * entry point) and cached. The code selects one of the generated tables
 * (BOF3_XLATE_HAVE_<CODE>, one per generated/bof3_xlate_<code>.c): "en" is
 * the US-disc English, "jp_ruby" the JP script with readings inline once per
 * word per area, "jp_ruby_all" the same with every occurrence read. A code
 * with no table ("jp", "off") leaves the JP bytes.
 */
#include "mod_plugins.h"
#include "text_xlate.h"
#include "bof3_xlate_table.h"

#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#define MSGBOX_RESET_PC 0x8015042Cu
/* The second door. MsgBox_Replay 0x801515F8 (boot EXE, callers 0x801511B4 in
 * the page-break state and 0x80151554 when the window is re-shown -- the
 * master apprenticeship talk is the first sighting, 2026-09-11) re-derives
 * ptr = 0x80010000 + u16[0x80010000 + 2 * 0x801490A4], stores it into BOTH
 * globals and sets state 1 with an 8- or 16-frame delay, never calling
 * MsgBox_Reset -- so a message this hook already redirected snaps back to the
 * JP block. The replay cannot be intercepted at its own entry (the stores
 * come after), but every replay lands in state 1, whose handler
 * MsgBox_DelayState 0x80150F3C runs each frame of the delay before the
 * stepper touches the pointer again. Hooking that entry and redirecting when
 * the base still points at the JP block catches every such path, whoever
 * the caller was. */
#define MSGBOX_DELAY_PC 0x80150F3Cu
#define MSG_STR_BASE    0x801490A8u    /* renderer's string base */
#define MSG_STR_CUR     0x801490ACu    /* stepper's current pointer */
/* The two message pools the box reads: the area script at 0x80010000 (16 KiB
 * window) and, right after it, the system block AFLDKWA.EMI at 0x80014000
 * (13,864 bytes: search / pickup / inn / save-point lines and the menu strings,
 * which never reach this hook -- docs/FURIGANA.md).  One contiguous gate. */
#define AREA_BLOCK_LO   0x80010000u
#define AREA_BLOCK_HI   0x80017628u

/* One message is at most a couple of KiB after re-wrapping (the build tool
 * refuses anything over --max-len); eight slots ring so a message that is
 * still on screen is never overwritten by the next open. */
#define SLOT_SIZE  2048u
#define SLOT_COUNT 8u
#define JP_MAX     1024u               /* the longest JP message is 391 bytes */

#ifdef BOF3_XLATE_HAVE_EN
BOF3_XLATE_DECLARE(en)
#endif
#ifdef BOF3_XLATE_HAVE_JP_RUBY
BOF3_XLATE_DECLARE(jp_ruby)
#endif
#ifdef BOF3_XLATE_HAVE_JP_RUBY_ALL
BOF3_XLATE_DECLARE(jp_ruby_all)
#endif
static const Bof3XlateTable g_tables[] = {
#ifdef BOF3_XLATE_HAVE_EN
    BOF3_XLATE_TABLE("en", en),
#endif
#ifdef BOF3_XLATE_HAVE_JP_RUBY
    BOF3_XLATE_TABLE("jp_ruby", jp_ruby),
#endif
#ifdef BOF3_XLATE_HAVE_JP_RUBY_ALL
    BOF3_XLATE_TABLE("jp_ruby_all", jp_ruby_all),
#endif
};
#define TABLE_COUNT (sizeof g_tables / sizeof g_tables[0])

/* Runtime inserts (docs/INSERT_RUBY.md). An item, skill or zenny amount is
 * not in the message: the box carries <07><nn> and the stepper (MsgBox_Step
 * 0x8015096C, case 7) reads the name at draw time from a 32-byte scratch
 * record at 0x801490D4 + 0x20*nn, NUL-terminated, at most 32 bytes. Every
 * caller fills the record BEFORE opening the message (the pickup path at
 * GAME.EMI 0x801B4094 copies the 8 name bytes from Item_NamePtr(cat, id)
 * 0x80166720, NULs byte 8, then Msg_OpenSystem(2); Field_GiveZenny and the
 * battle-result tick sprintf the digits first, likewise), so at this hook
 * the record already holds the bytes the player will read. For a Ruby
 * language the plugin hashes those bytes, looks them up in the language's
 * insert table (the same names, with readings) and writes the annotated
 * name back into the record -- the stepper's own scratch for the message
 * being opened, not game state. A record that misses (digits, a name with
 * no kanji, a record already rewritten) is left untouched. */
#define INSERT_RECORD_BASE 0x801490D4u
#define INSERT_RECORD_SIZE 0x20u
#define INSERT_MAX 16u                 /* distinct <07><nn> in one message */

#ifdef BOF3_INSERT_HAVE_JP_RUBY
BOF3_INSERT_DECLARE(jp_ruby)
#endif
#ifdef BOF3_INSERT_HAVE_JP_RUBY_ALL
BOF3_INSERT_DECLARE(jp_ruby_all)
#endif
static const Bof3XlateTable g_inserts[] = {
#ifdef BOF3_INSERT_HAVE_JP_RUBY
    BOF3_INSERT_TABLE("jp_ruby", jp_ruby),
#endif
#ifdef BOF3_INSERT_HAVE_JP_RUBY_ALL
    BOF3_INSERT_TABLE("jp_ruby_all", jp_ruby_all),
#endif
    { NULL, NULL, NULL, NULL, NULL, NULL }   /* keeps the array non-empty */
};
#define INSERT_TABLE_COUNT (sizeof g_inserts / sizeof g_inserts[0] - 1u)

static uint32_t g_ring;                /* guest address of the slot ring, 0 until first use */
static uint32_t g_next_slot;
static const Bof3XlateTable *g_table;  /* the active language's table, NULL = leave JP */
static const Bof3XlateTable *g_insert; /* its insert table, NULL = leave the records */
static int      g_lang_known;          /* 0 until the first readback */
static char     g_lang[16];
static uint32_t g_lang_tick;
static uint32_t g_hits, g_misses, g_skipped;
static uint32_t g_ins_hits, g_ins_misses;

/* The runtime's stdout is a pipe or a file under the harness (fully
 * buffered) and a killed process never flushes it, so every line is flushed. */
static void say(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    vfprintf(stdout, fmt, ap);
    va_end(ap);
    fflush(stdout);
}

/* --- language ------------------------------------------------------------ */
static const Bof3XlateTable *table_for(const char *code) {
    size_t i;
    for (i = 0; i < TABLE_COUNT; i++)
        if (strcmp(g_tables[i].code, code) == 0) return &g_tables[i];
    return NULL;
}

static const Bof3XlateTable *insert_table_for(const char *code) {
    size_t i;
    for (i = 0; i < INSERT_TABLE_COUNT; i++)
        if (strcmp(g_inserts[i].code, code) == 0) return &g_inserts[i];
    return NULL;
}

/* Re-read every 64 opens so a launcher-side switch is picked up without a
 * restart; the JSON is ~300 bytes, the parse is a strstr. */
static const Bof3XlateTable *active_table(void) {
    if (!g_lang_known || (g_lang_tick++ & 63u) == 0u) {
        char buf[512];
        int n = text_xlate_debug_json("stats", buf, (int)sizeof buf);
        const char *p = (n > 0) ? strstr(buf, "\"lang\":\"") : NULL;
        g_lang[0] = '\0';
        if (p) {
            size_t k = 0;
            p += 8;
            while (*p && *p != '"' && k + 1 < sizeof g_lang) g_lang[k++] = *p++;
            g_lang[k] = '\0';
        }
        g_table = table_for(g_lang);
        g_insert = insert_table_for(g_lang);
        g_lang_known = 1;
    }
    return g_table;
}

/* --- the message walker -------------------------------------------------- */
/* Length of the message at `p`, control-aware. Mirrors message_extent() in
 * tools/build_script_xlate.py -- the hash covers exactly these bytes on both
 * sides, so the two walkers must agree. Copies the bytes into `out`. Returns
 * 0 if the message is unterminated within `cap` bytes. The record index of
 * every <07><nn> met on the way goes into `ins` (at most INSERT_MAX, counted
 * in *nins) for the insert pass -- the walker already knows which 0x07 is a
 * control and which is the second byte of a kanji pair. */
static uint32_t msg_extent(uint32_t p, uint8_t *out, uint32_t cap,
                           uint8_t *ins, uint32_t *nins) {
    uint32_t i = 0;
    while (i < cap) {
        uint8_t b = psx_mod_read_byte(p + i);
        out[i] = b;
        if (b == 0x00) return i + 1;
        if (b == 0x14) {                       /* choice: 3 args, then count NUL-terminated options */
            uint32_t count, k;
            if (i + 3 >= cap) return 0;
            for (k = 1; k <= 3; k++) out[i + k] = psx_mod_read_byte(p + i + k);
            count = out[i + 3] & 0xFu;
            i += 4;
            for (k = 0; k < count; k++) {
                for (;;) {
                    if (i >= cap) return 0;
                    b = psx_mod_read_byte(p + i);
                    out[i++] = b;
                    if (b == 0x00) break;
                }
            }
            return i;
        }
        switch (b) {                            /* one argument byte / two-byte glyph */
        case 0x04: case 0x05: case 0x07: case 0x08: case 0x0A: case 0x0C:
        case 0x0F: case 0x16: case 0x12: case 0x13: case 0x15:
            if (i + 1 >= cap) return 0;
            out[i + 1] = psx_mod_read_byte(p + i + 1);
            if (b == 0x07 && ins && *nins < INSERT_MAX) ins[(*nins)++] = out[i + 1];
            i += 2;
            break;
        default:
            i += 1;
            break;
        }
    }
    return 0;
}

static uint64_t fnv1a64(const uint8_t *d, uint32_t n) {
    uint64_t h = 0xcbf29ce484222325ull;
    uint32_t i;
    for (i = 0; i < n; i++) { h ^= d[i]; h *= 0x100000001b3ull; }
    return h;
}

static int lookup(const Bof3XlateTable *t, uint64_t h, uint32_t *off, uint32_t *len) {
    uint32_t lo = 0, hi = *t->count;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2u;
        uint64_t v = t->hash[mid];
        if (v == h) { *off = t->off[mid]; *len = t->len[mid]; return 1; }
        if (v < h) lo = mid + 1; else hi = mid;
    }
    return 0;
}

/* --- the insert pass ----------------------------------------------------- */
/* Rewrite the <07><nn> records the message about to open will read, when the
 * active language has an insert table. Runs on the miss path too: a message
 * with no kanji of its own still carries the insert. A record is read to its
 * NUL (the stepper stops there, or after 32 bytes -- a record with no NUL in
 * 32 is not a name and is skipped), hashed as-is, and rewritten only on a
 * table hit that fits 31 bytes + NUL. Rewriting is idempotent: the annotated
 * bytes hash to nothing, so a message re-opened on the same record is left
 * as it is. */
static void apply_inserts(const uint8_t *ins, uint32_t nins) {
    uint8_t rec[INSERT_RECORD_SIZE];
    uint32_t k, j, n, off, len, base;
    uint64_t h;
    const Bof3XlateTable *t = g_insert;
    if (!t || !nins) return;
    for (k = 0; k < nins; k++) {
        for (j = 0; j < k; j++) if (ins[j] == ins[k]) break;
        if (j < k) continue;                   /* same record twice in one message */
        base = INSERT_RECORD_BASE + INSERT_RECORD_SIZE * ins[k];
        for (n = 0; n < INSERT_RECORD_SIZE; n++) {
            rec[n] = psx_mod_read_byte(base + n);
            if (rec[n] == 0) break;
        }
        if (n == 0 || n == INSERT_RECORD_SIZE) continue;
        h = fnv1a64(rec, n);
        if (!lookup(t, h, &off, &len) || len + 1 > INSERT_RECORD_SIZE) {
            g_ins_misses++;
            if (g_ins_misses <= 10)
                say("bof3_localize: insert miss #%u rec=%u len=%u hash=%016llx head=%02x %02x %02x %02x\n",
                    g_ins_misses, ins[k], n, (unsigned long long)h, rec[0], rec[1], rec[2], rec[3]);
            continue;
        }
        for (j = 0; j < len; j++) psx_mod_write_byte(base + j, t->blob[off + j]);
        psx_mod_write_byte(base + len, 0);
        g_ins_hits++;
        if (g_ins_hits <= 5)
            say("bof3_localize: insert hit #%u rec=%u at %08X (%u -> %u bytes)\n",
                g_ins_hits, ins[k], base, n, len);
    }
}

/* --- the hook ------------------------------------------------------------ */
/* Redirect the message the box is about to read, if the active table has
 * it. `ptr` is the JP pointer both globals hold; `via` names the door;
 * `log_every` logs every hit rather than the first five. */
static void redirect_message(uint32_t ptr, const char *via, int log_every) {
    uint8_t jp[JP_MAX];
    uint8_t ins[INSERT_MAX];
    uint32_t n, off, len, dst, i, nins = 0;
    uint64_t h;
    const Bof3XlateTable *t;

    t = active_table();
    if (g_hits + g_misses + g_skipped == 0)
        say("bof3_localize: first %s, ptr=%08X, language \"%s\" -> %s%s\n", via, ptr,
            g_lang, t ? t->code : "no table, leaving JP",
            g_insert ? " (+ insert table)" : "");
    if (!t) { g_skipped++; return; }
    if (ptr < AREA_BLOCK_LO || ptr >= AREA_BLOCK_HI) { g_skipped++; return; }

    n = msg_extent(ptr, jp, (AREA_BLOCK_HI - ptr < JP_MAX) ? AREA_BLOCK_HI - ptr : JP_MAX,
                   ins, &nins);
    if (!n) { g_skipped++; return; }
    apply_inserts(ins, nins);
    h = fnv1a64(jp, n);
    if (!lookup(t, h, &off, &len)) {
        g_misses++;
        if (g_misses <= 20)
            say("bof3_localize: miss #%u (%s) ptr=%08X len=%u hash=%016llx head=%02x %02x %02x %02x\n",
                g_misses, via, ptr, n, (unsigned long long)h, jp[0], jp[1], jp[2], jp[3]);
        return;
    }
    if (len > SLOT_SIZE) { g_skipped++; return; }

    if (!g_ring) {
        g_ring = psx_mod_alloc_guest_memory(SLOT_SIZE * SLOT_COUNT, 16u);
        if (!g_ring) {
            say("bof3_localize: enhancement memory allocation failed; script tables off\n");
            g_table = NULL;
            return;
        }
        say("bof3_localize: ring at %08X\n", g_ring);
    }
    dst = g_ring + (g_next_slot % SLOT_COUNT) * SLOT_SIZE;
    g_next_slot++;
    for (i = 0; i < len; i++) psx_mod_write_byte(dst + i, t->blob[off + i]);
    psx_mod_write_word(MSG_STR_BASE, dst);
    psx_mod_write_word(MSG_STR_CUR, dst);
    g_hits++;
    if (g_hits <= 5 || log_every)
        say("bof3_localize: hit #%u (%s) ptr=%08X -> %08X (%u -> %u bytes)\n",
            g_hits, via, ptr, dst, n, len);
}

static void on_msgbox_reset(struct CPUState *cpu, uint32_t address) {
    (void)cpu; (void)address;
    redirect_message(psx_mod_read_word(MSG_STR_CUR), "MsgBox_Reset", 0);
}

/* State 1 runs for every frame of a delay: after a replay (base == cur ==
 * the message start, both in the JP block) and after a 0x0B prompt mid-
 * message (cur past base -- not ours). One attempt per distinct base, so a
 * message the table lacks is hashed once, not once per frame. */
static uint32_t g_delay_last_base;
static void on_msgbox_delay(struct CPUState *cpu, uint32_t address) {
    uint32_t base, cur;
    (void)cpu; (void)address;
    base = psx_mod_read_word(MSG_STR_BASE);
    cur = psx_mod_read_word(MSG_STR_CUR);
    if (base != cur || base < AREA_BLOCK_LO || base >= AREA_BLOCK_HI) return;
    if (base == g_delay_last_base) return;
    g_delay_last_base = base;
    redirect_message(base, "MsgBox_Replay", 1);   /* rare: log each */
}

PSX_MOD_CONSTRUCTOR(bof3_register_localize_plugin) {
    size_t i;
    int ok = psx_mod_register_function_entry_plugin("bof3.script", MSGBOX_RESET_PC,
                                                    on_msgbox_reset);
    int ok2 = psx_mod_register_function_entry_plugin("bof3.script.replay", MSGBOX_DELAY_PC,
                                                     on_msgbox_delay);
    say("bof3_localize: plugin %s, %u table(s)\n",
        ok && ok2 ? "registered at MsgBox_Reset + MsgBox_DelayState"
                  : ok ? "registered at MsgBox_Reset only (replay hook FAILED)"
                       : "REGISTRATION FAILED", (unsigned)TABLE_COUNT);
    for (i = 0; i < TABLE_COUNT; i++)
        say("bof3_localize:   %s: %u messages\n", g_tables[i].code, (unsigned)*g_tables[i].count);
    for (i = 0; i < INSERT_TABLE_COUNT; i++)
        say("bof3_localize:   %s: %u insert names\n", g_inserts[i].code, (unsigned)*g_inserts[i].count);
}
