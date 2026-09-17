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
#include "cpu_state.h"
#include "bof3_small_font.h"
#include "text_xlate.h"
#include "bof3_xlate_table.h"

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
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
/* The third door, a placement probe (docs/FURIGANA.md "The rendering route,
 * reopened", step 2). MsgBox_DrawSprite 0x8014F6BC is the unscaled glyph
 * blitter, called once per glyph with x in a0 and y in a1. BOF3_RUBY_YBUMP=n
 * adds n to a1 at entry, which shows on screen whether a register write from
 * a function-entry plugin is honoured by the generated code -- the check the
 * per-glyph layout table depends on. Unset or 0, the hook does nothing. */
#define MSGBOX_SPRITE_PC 0x8014F6BCu
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
/* jp_furigana: the JP script with every kanji word read in an 8 px row
 * above it (docs/FURIGANA.md). The inline-bracket jp_ruby / jp_ruby_all and
 * the first-occurrence jp_furigana_area were retired 2026-09-12 once the
 * furigana rows cost no width; the builder still emits them on request. */
#ifdef BOF3_XLATE_HAVE_JP_FURIGANA
BOF3_XLATE_DECLARE(jp_furigana)
#endif
static const Bof3XlateTable g_tables[] = {
#ifdef BOF3_XLATE_HAVE_EN
    BOF3_XLATE_TABLE("en", en),
#endif
#ifdef BOF3_XLATE_HAVE_JP_FURIGANA
    BOF3_XLATE_TABLE("jp_furigana", jp_furigana),
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

/* For the furigana layout the insert table holds ruby-row FRAGMENTS, not
 * annotated names: hash of the inserted name's bytes -> the gaps and kana
 * that read it, padded to the name's width. The message's ruby row carries
 * INSERT_MARK where the inserted name begins, and expand_markers() splices
 * the fragment (or plain gaps of the name's width) in its place when the
 * message opens -- the records are already filled by then. Names are still
 * drawn verbatim in the text row. */
#ifdef BOF3_INSERT_HAVE_JP_FURIGANA
BOF3_INSERT_DECLARE(jp_furigana)
#endif
static const Bof3XlateTable g_inserts[] = {
#ifdef BOF3_INSERT_HAVE_JP_FURIGANA
    BOF3_INSERT_TABLE("jp_furigana", jp_furigana),
#endif
    { NULL, NULL, NULL, NULL, NULL, NULL }   /* keeps the array non-empty */
};
#define INSERT_MARK        0x11u
#define GAP_BYTE           0x09u
#define NAME_RECORD_BASE   0x80144964u  /* character records, 0xA4 apart; 6-glyph name at +0 */
#define NAME_RECORD_STRIDE 0xA4u
#define NAME_MAX           6u
#define CUR_CHAR_INDEX     0x80145F05u  /* the 0x03 insert's character */
#define MSG_INSERT_CELLS   11u          /* 0x08: a message by index, width unknown -- the budget */
#define INSERT_TABLE_COUNT (sizeof g_inserts / sizeof g_inserts[0] - 1u)

static uint32_t g_ring;                /* guest address of the slot ring, 0 = allocation failed */
static int      alloc_ring(void);
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
/* apply_inserts() -- rewriting a 0x07 record with an inline-annotated name --
 * went with the inline Ruby variants (2026-09-12); the furigana layout reads
 * the records instead (expand_markers below) and never writes them. */

/* --- the hook ------------------------------------------------------------ */
/* Redirect the message the box is about to read, if the active table has
 * it. `ptr` is the JP pointer both globals hold; `via` names the door;
 * `log_every` logs every hit rather than the first five. */
/* --- furigana insert markers ---------------------------------------------- */
static uint32_t g_marks_expanded, g_frag_hits;

/* Glyph cells in an inserted record (NUL-terminated): a two-byte glyph is
 * one cell, the separator 0xFF one cell. */
static uint32_t record_cells(const uint8_t *rec, uint32_t n) {
    uint32_t i = 0, cells = 0;
    while (i < n) {
        uint8_t b = rec[i];
        i += (b == 0x12u || b == 0x13u || b == 0x15u) ? 2u : 1u;
        cells++;
    }
    return cells;
}

/* Read the record an insert control draws: 0x07 nn = the 32-byte scratch
 * record, 0x04 nn / 0x03 = a character's name. Returns the byte count. */
static uint32_t insert_record(uint8_t code, uint8_t arg, uint8_t *rec, uint32_t *cells) {
    uint32_t base, cap, n;
    if (code == 0x07u) { base = INSERT_RECORD_BASE + INSERT_RECORD_SIZE * arg; cap = INSERT_RECORD_SIZE; }
    else if (code == 0x04u) { base = NAME_RECORD_BASE + NAME_RECORD_STRIDE * arg; cap = NAME_MAX; }
    else if (code == 0x03u) { base = NAME_RECORD_BASE + NAME_RECORD_STRIDE * psx_mod_read_byte(CUR_CHAR_INDEX); cap = NAME_MAX; }
    else { *cells = MSG_INSERT_CELLS; return 0; }
    for (n = 0; n < cap; n++) {
        rec[n] = psx_mod_read_byte(base + n);
        if (rec[n] == 0) break;
    }
    *cells = record_cells(rec, n);
    return n;
}

/* The k-th insert control of the text row that follows the ruby row at
 * src[i] (i at the row's INSERT_MARK). Returns 0 when there is none. */
static int kth_insert_after(const uint8_t *src, uint32_t len, uint32_t i, uint32_t k,
                            uint8_t *code, uint8_t *arg) {
    uint32_t j = i, seen = 0;
    while (j < len && src[j] != 0x0Eu) j += (src[j] == 0x12u || src[j] == 0x13u || src[j] == 0x15u) ? 2u : 1u;
    if (j >= len) return 0;
    j++;                                     /* past 0x0E */
    if (j < len && src[j] == 0x01u) j++;     /* the newline into the text row */
    while (j < len) {
        uint8_t b = src[j];
        if (b == 0x00u || b == 0x01u || b == 0x02u || b == 0x16u) return 0;
        if (b == 0x03u || b == 0x04u || b == 0x07u || b == 0x08u) {
            if (seen++ == k) {
                *code = b;
                *arg = (b == 0x03u) ? 0u : src[j + 1];
                return 1;
            }
        }
        switch (b) {
        case 0x04: case 0x05: case 0x07: case 0x08: case 0x0A: case 0x0C:
        case 0x0F: case 0x12: case 0x13: case 0x15: j += 2; break;
        default: j += 1; break;
        }
    }
    return 0;
}

/* Pixels the draw-time cursor consumes over a ruby fragment, by the
 * plugin's own rules (the builder's lint_row models the same): a gap byte is
 * 6 px; kana in a run are 8 px apart and the renderer adds 6 after the last,
 * so a run of n ends 8n - 2 past its start, snapped up to the half-cell
 * before the next gap counts. */
#define HALF_PX     6u
#define RUBY_PX_ADV 8u
static uint32_t fragment_px(const uint8_t *f, uint32_t n) {
    uint32_t px = 0, run = 0, i;
    for (i = 0; i < n; i++) {
        if (f[i] == GAP_BYTE) {
            if (run) { px += (RUBY_PX_ADV * run - 2u + HALF_PX - 1u) / HALF_PX * HALF_PX; run = 0; }
            px += HALF_PX;
        } else {
            run++;
        }
    }
    if (run) px += (RUBY_PX_ADV * run - 2u + HALF_PX - 1u) / HALF_PX * HALF_PX;
    return px;
}

/* Copy a furigana message, replacing each INSERT_MARK in a ruby row with the
 * inserted name's fragment from the insert table, or with gaps of the
 * name's real width. Everything else is copied byte for byte. */
static uint32_t expand_markers(const uint8_t *src, uint32_t len, uint8_t *dst, uint32_t cap) {
    uint32_t i = 0, o = 0, in_span = 0, k = 0;
    uint8_t rec[INSERT_RECORD_SIZE];
    while (i < len && o < cap) {
        uint8_t b = src[i];
        uint32_t adv = 1;
        if (b == 0x14u) {
            /* A choice block: three argument bytes, then NUL-terminated
             * options. msg_extent() already bounded `len` at the last
             * option's NUL, and the builder passes the block through
             * verbatim, so copy the rest as it is -- stopping at the first
             * NUL here dropped every option after the first (user's
             * scrambled / empty choice boxes, 2026-09-13). */
            while (i < len && o < cap) dst[o++] = src[i++];
            break;
        }
        if (b == 0x0Du) { in_span = 1; k = 0; }
        else if (b == 0x0Eu) in_span = 0;
        else if (b == INSERT_MARK && in_span) {
            uint8_t code = 0, arg = 0;
            uint32_t n = 0, cells = 0, off = 0, flen = 0, j;
            int have = kth_insert_after(src, len, i, k++, &code, &arg);
            if (have) n = insert_record(code, arg, rec, &cells);
            uint32_t eaten = 0;
            if (have && n && g_insert && lookup(g_insert, fnv1a64(rec, n), &off, &flen)
                && o + flen <= cap) {
                uint32_t px;
                for (j = 0; j < flen; j++) dst[o++] = g_insert->blob[off + j];
                g_frag_hits++;
                /* A reading wider than its name (やくそう over 薬草: 32 px on
                 * 24) leaves the cursor past the name's width, and every
                 * reading after the insert started late by the excess
                 * (user's pickup frame, 2026-09-13). Absorb it: drop one of
                 * the gap bytes the builder laid after the marker per
                 * half-cell of overrun. */
                px = fragment_px(g_insert->blob + off, flen);
                while (px >= 12u * cells + HALF_PX && i + 1u + eaten < len
                       && src[i + 1u + eaten] == GAP_BYTE) {
                    px -= HALF_PX;
                    eaten++;
                }
            } else {
                for (j = 0; j < 2u * cells && o < cap; j++) dst[o++] = GAP_BYTE;
            }
            if (g_marks_expanded++ < 6)
                say("bof3_localize: insert marker -> %s %02X/%02X, %u cells%s%s\n",
                    have ? "insert" : "no insert", code, arg, cells, flen ? " (fragment)" : "",
                    eaten ? ", overhang absorbed" : "");
            i += 1 + eaten;
            continue;
        }
        switch (b) {
        case 0x04: case 0x05: case 0x07: case 0x08: case 0x0A: case 0x0C:
        case 0x0F: case 0x16: case 0x12: case 0x13: case 0x15: adv = 2; break;
        default: break;
        }
        if (i + adv > len || o + adv > cap) break;
        for (; adv; adv--) dst[o++] = src[i++];
        if (b == 0x00u) break;
    }
    return o;
}

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
    h = fnv1a64(jp, n);
    if (!lookup(t, h, &off, &len)) {
        g_misses++;
        if (g_misses <= 20)
            say("bof3_localize: miss #%u (%s) ptr=%08X len=%u hash=%016llx head=%02x %02x %02x %02x\n",
                g_misses, via, ptr, n, (unsigned long long)h, jp[0], jp[1], jp[2], jp[3]);
        return;
    }
    if (len > SLOT_SIZE) { g_skipped++; return; }

    if (!g_ring && !alloc_ring()) {
        g_table = NULL;
        return;
    }
    dst = g_ring + (g_next_slot % SLOT_COUNT) * SLOT_SIZE;
    g_next_slot++;
    {
        static uint8_t out[SLOT_SIZE];
        uint32_t olen = expand_markers(t->blob + off, len, out, SLOT_SIZE);
        if (olen == 0 || olen == SLOT_SIZE) { g_skipped++; return; }
        for (i = 0; i < olen; i++) psx_mod_write_byte(dst + i, out[i]);
        len = olen;
    }
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

/* Row rule for true ruby (docs/FURIGANA.md "The rendering route, reopened",
 * step 3, 2026-09-12). A furigana page -- built by
 * tools/build_ruby_script.py --furigana -- starts with the shrink preset
 * <0f><13> and then alternates text row, ruby row: `text <01> <0d>ruby<0e>`.
 * No shipped page starts with a preset (every 0x0F in the disc follows a
 * closed span), so that byte pair is the signature: once per page the
 * renderer-entry hook reads the page base 0x801490A8 and looks for it past
 * the optional <0c>xx head, and only a page that carries it gets its rows
 * placed. Every other page (a plain JP message, a verbatim collision page,
 * another language) is never touched.
 *
 * Placement: the renderer 0x80150598 re-walks the string every frame from
 * the origin, so its entry resets the row counter. Each blitter entry then
 * reads the cursor y 0x801490BA: the value this hook last wrote means the
 * same row; a value 14k past it means k newlines fired (an empty ruby row
 * draws no glyph, so k can be 2) and the row advances by k. The RAM write
 * is what places the glyph (the quad path 0x80151F4C reads the cursor
 * after entry); the sprite path 0x8014F6BC already carries y in a1, so it
 * gets the same delta in the register. Rows alternate text / ruby with the
 * y offsets ROWY_TEXT / ROWY_RUBY from the origin per pair, PAIR_PITCH
 * apart: 8, 1, 29, 22 -- two pairs in the 42 px interior. Offsets are never
 * a multiple of 14, which keeps a written y apart from a stepped one.
 * BOF3_RUBY_ROWY="a,b,c,d" overrides the offsets and BOF3_RUBY_FORCE=1
 * applies the rule to every page (the probe tool's demo mode);
 * BOF3_RUBY_YBUMP=n is the older probe, a flat +n on the sprite path. */
#define MSGBOX_RENDER_PC 0x80150598u
#define MSGBOX_QUAD_PC   0x80151F4Cu
#define MSG_CUR_Y        0x801490BAu
#define MSG_ORIGIN_Y     0x801490BEu
#define FURIGANA_PRESET  0x13u         /* type 3 shrink, P = -6, forever */
#define ROWY_MAX 8
static int g_ybump, g_rowy_force;
/* A page is ruby row, text row, ruby row, text row: the ruby row comes
 * FIRST so the page ends on a text row -- the next-page arrow places itself
 * off the last row (user's screenshot, 2026-09-12). Ruby rows at -2 and 19,
 * text rows at 6 and 27: 8 px bands, the block moved up 2 px so the two
 * extra pixels per band are shared between the top and bottom margins. */
#define RUBY_ROW(row) (((row) & 1) == 0)
static int g_rowy[ROWY_MAX] = { -2, 6, 19, 27 }, g_rowy_n = 4;
static int g_row, g_row_valid, g_row_written_y;
static int g_ruby_last_row;            /* row of the last ruby glyph drawn this frame, -1 = none */
static uint32_t g_page_base;           /* page whose signature was last checked */
static int g_page_furigana;

/* A message the box can be reading: the JP pools, or this plugin's ring in
 * enhancement memory (a redirected message lives there, 2026-09-12). */
static int readable_text(uint32_t p) {
    if (p >= AREA_BLOCK_LO && p < AREA_BLOCK_HI) return 1;
    return g_ring && p >= g_ring && p < g_ring + SLOT_SIZE * SLOT_COUNT;
}

static int page_is_furigana(uint32_t base) {
    if (!readable_text(base)) return 0;
    if (psx_mod_read_byte(base) == 0x0Cu) base += 2;
    return psx_mod_read_byte(base) == 0x0Fu && psx_mod_read_byte(base + 1) == (uint8_t)FURIGANA_PRESET;
}

static void on_msgbox_render(struct CPUState *cpu, uint32_t address) {
    uint32_t base = psx_mod_read_word(MSG_STR_BASE);
    (void)cpu; (void)address;
    if (base != g_page_base) {
        g_page_base = base;
        g_page_furigana = g_rowy_force || page_is_furigana(base);
    }
    g_row = 0;
    g_row_valid = 0;
    g_ruby_last_row = -1;
}

static int row_offset(int row) {
    if (row < g_rowy_n) return g_rowy[row];
    return g_rowy[g_rowy_n - 1] + 14 * (row - g_rowy_n + 1);
}

/* Returns 1 when the glyph was placed (a furigana page), 0 otherwise. */
static int place_row(struct CPUState *cpu, int sprite_path) {
    int y, origin, want, delta;
    if (!g_page_furigana) return 0;
    y = (int16_t)psx_mod_read_half(MSG_CUR_Y);
    origin = (int16_t)psx_mod_read_half(MSG_ORIGIN_Y);
    if (g_row_valid && y != g_row_written_y) {
        int d = y - g_row_written_y;
        if (d > 0 && d % 14 == 0) g_row += d / 14;
    } else if (!g_row_valid) {
        /* First glyph this frame: the game's own y says how many newlines
         * already fired (an empty ruby row at the page head draws nothing). */
        int d = y - origin;
        g_row = (d > 0 && d % 14 == 0) ? d / 14 : 0;
    }
    g_row_valid = 1;
    want = origin + row_offset(g_row);
    delta = want - y;
    psx_mod_write_half(MSG_CUR_Y, (uint16_t)want);
    g_row_written_y = want;
    if (sprite_path)
        cpu->gpr[5] = (uint32_t)((int32_t)cpu->gpr[5] + delta);
    return 1;
}

/* Half-cell gaps in a ruby row. The font has no empty cell and 0xFF is a
 * separator only for full-size glyphs (drawn shrunk it is a junk cell,
 * 2026-09-12 demo), so a gap is a control byte the renderer ignores and the
 * stepper does not count: 0x09 (BOF3_RUBY_GAP=hex overrides). The shrunk
 * glyphs go through the quad blitter, whose a1 is the string walk pointer
 * at the glyph (the same s0 the sprite call stores at sp+0x10); on a ruby
 * row (odd rows) each gap byte right before the glyph moves the cursor x by
 * one shrunk cell (12 + P) before the glyph is drawn, and the renderer's own
 * advance continues from there. Text rows are never scanned, so a kanji
 * whose low byte equals the gap code cannot be misread. */
#define MSG_CUR_X   0x801490B8u
#define MSG_SIZE_P  0x801490C4u
static int g_gap_code = 0x09, g_gap_hits;

/* p = the string walk pointer at the glyph (a1 on the quad path, sp+0x10 on
 * the sprite path); x_reg = the register carrying x, or 0 when the blitter
 * reads x from RAM only. */
static int ruby_gap(struct CPUState *cpu, uint32_t p, int x_reg) {
    int n = 0, step, x;
    if (!readable_text(p)) return 0;
    while (n < 64 && psx_mod_read_byte(p - 1u - (uint32_t)n) == (uint8_t)g_gap_code)
        n++;
    if (!n) return 0;
    step = 12 + (int16_t)psx_mod_read_half(MSG_SIZE_P);
    x = (int16_t)psx_mod_read_half(MSG_CUR_X);
    {
        /* A reading's kana advance 8 each but the renderer adds only 6 after
         * the last, so the cursor sits off the half-cell grid after every
         * reading (8n - 2 past its start) and the next reading drifted left
         * by the remainder, accumulating along the row (user's frame,
         * 2026-09-12). Snap up to the next half-cell from the row's origin
         * before counting the gaps; the builder counts from the same place. */
        int origin_x = (int16_t)psx_mod_read_half(MSG_ORIGIN_Y - 2u);
        int rel = x - origin_x;
        int snapped = origin_x + ((rel + step - 1) / step) * step;
        int want = snapped + step * n;
        psx_mod_write_half(MSG_CUR_X, (uint16_t)want);
        if (x_reg)
            cpu->gpr[x_reg] = (uint32_t)((int32_t)cpu->gpr[x_reg] + (want - x));
        if (g_gap_hits++ < 4)
            say("bof3_localize: ruby gap x%d before glyph at %08X (x %d -> %d)\n", n, p, x, want);
    }
    return n;
}

/* The 8 px font (docs/FURIGANA.md "The 8 px font", 2026-09-12). The single-
 * byte page carries the game's own 8 x 8 kana below the 12 px cells; the box
 * mapper cannot address it, but the quad blitter builds an ordinary POLY_FT4
 * in RAM and commits it through 0x8014E494(1, 0x28) with the packet still at
 * *0x80145988 and every field written. A hook on that commit, filtered by
 * the blitter's return address, re-points a reading glyph's quad at the
 * small cell of the same kana (names/font_small.toml -> bof3_small_font.h):
 * UV origin and a 7-texel extent, an 8 px square from the game's own x0/y0,
 * same texture page and, unless BOF3_RUBY_PAL=n says otherwise, the same
 * CLUT (palette n = 0x7800 | n, the game's GetClut(n * 16, 0x1E0)).
 * The renderer still advances 12 + P = 6 per glyph, so a reading's kana
 * after the first get +2 to keep an 8 px pitch. */
#define PRIM_COMMIT_PC  0x8014E494u
#define PRIM_COMMIT_RA  0x80152D84u   /* return into the quad blitter */
#define MSG_PRIM_CUR    0x80145988u
#define RUBY_PX         8
static int g_pend, g_pal = -1, g_small_hits;
static unsigned g_pend_uv;

static void ruby_small_glyph(uint32_t p, int gaps) {
    unsigned c, uv = 0xFFFFu;
    int step, x;
    if (!readable_text(p)) return;
    c = psx_mod_read_byte(p);
    if (c >= 0x5Bu && c < 0xFFu)
        uv = bof3_small_font[c];
    if (!gaps && g_ruby_last_row == g_row) {
        step = 12 + (int16_t)psx_mod_read_half(MSG_SIZE_P);
        x = (int16_t)psx_mod_read_half(MSG_CUR_X);
        psx_mod_write_half(MSG_CUR_X, (uint16_t)(x + RUBY_PX - step));
    }
    g_ruby_last_row = g_row;
    if (uv != 0xFFFFu) {
        g_pend = 1;
        g_pend_uv = uv;
    }
}

static void on_prim_commit(struct CPUState *cpu, uint32_t address) {
    uint32_t pk;
    unsigned cmd, u, v;
    int x0, y0;
    (void)address;
    if (!g_pend || cpu->gpr[31] != PRIM_COMMIT_RA) return;
    g_pend = 0;
    pk = psx_mod_read_word(MSG_PRIM_CUR);
    cmd = psx_mod_read_byte(pk + 7u);
    if ((cmd & 0xFCu) != 0x2Cu) return;             /* not a textured quad */
    u = g_pend_uv & 0xFFu;
    v = g_pend_uv >> 8;
    x0 = (int16_t)psx_mod_read_half(pk + 0x08u);
    y0 = (int16_t)psx_mod_read_half(pk + 0x0Au);
    /* UV extent = the size, not size - 1: u is interpolated from the vertex,
     * so an extent of 7 over 8 px never reaches the eighth texel row (the
     * game's own 11-for-12 drops its cells' last row, which is empty). */
    psx_mod_write_byte(pk + 0x0Cu, (uint8_t)u);              psx_mod_write_byte(pk + 0x0Du, (uint8_t)v);
    psx_mod_write_byte(pk + 0x14u, (uint8_t)(u + RUBY_PX));  psx_mod_write_byte(pk + 0x15u, (uint8_t)v);
    psx_mod_write_byte(pk + 0x1Cu, (uint8_t)u);              psx_mod_write_byte(pk + 0x1Du, (uint8_t)(v + RUBY_PX));
    psx_mod_write_byte(pk + 0x24u, (uint8_t)(u + RUBY_PX));  psx_mod_write_byte(pk + 0x25u, (uint8_t)(v + RUBY_PX));
    psx_mod_write_half(pk + 0x10u, (uint16_t)(x0 + RUBY_PX)); psx_mod_write_half(pk + 0x12u, (uint16_t)y0);
    psx_mod_write_half(pk + 0x18u, (uint16_t)x0);             psx_mod_write_half(pk + 0x1Au, (uint16_t)(y0 + RUBY_PX));
    psx_mod_write_half(pk + 0x20u, (uint16_t)(x0 + RUBY_PX)); psx_mod_write_half(pk + 0x22u, (uint16_t)(y0 + RUBY_PX));
    if (g_pal >= 0)
        psx_mod_write_half(pk + 0x0Eu, (uint16_t)(0x7800u | (unsigned)g_pal));
    if (g_small_hits++ < 3)
        say("bof3_localize: small glyph uv=(%u,%u) at (%d,%d) packet %08X cmd %02X\n",
            u, v, x0, y0, pk, cmd);
}

/* Only the renderer's own calls are glyphs: the next-page arrow goes
 * through the same sprite blitter from another caller, and the row rule
 * re-placed it onto the current row (user's screenshot, 2026-09-12). */
#define RENDER_SPRITE_RA 0x80150870u
#define RENDER_QUAD_RA   0x80150800u

/* The next-page arrow is drawn at cursor y + 14 + P (measured on plain 1-,
 * 2- and 3-row pages: +14 with P = 0; +8 on a furigana page with its
 * shrink preset live, which put it inside the last text row). A furigana
 * page ends on a text glyph, so when the glyph being drawn is the page's
 * last one the RAM cursor y is left at (row y - P): the glyph itself takes
 * y from a1, and the arrow then lands one row under the text. */
static int last_glyph_of_page(uint32_t p) {
    unsigned c, n;
    if (!readable_text(p)) return 0;
    c = psx_mod_read_byte(p);
    n = psx_mod_read_byte(p + ((c == 0x12u || c == 0x13u || c == 0x15u) ? 2u : 1u));
    return n == 0x00u || n == 0x02u || n == 0x16u;
}

static void on_sprite_glyph(struct CPUState *cpu, uint32_t address) {
    (void)address;
    if (cpu->gpr[31] != RENDER_SPRITE_RA) return;
    if (place_row(cpu, 1)) {
        uint32_t p = psx_mod_read_word(cpu->gpr[29] + 0x10u);
        if (g_gap_code && RUBY_ROW(g_row))
            ruby_gap(cpu, p, 4);
        else if (!RUBY_ROW(g_row) && last_glyph_of_page(p)) {
            int P = (int16_t)psx_mod_read_half(MSG_SIZE_P);
            psx_mod_write_half(MSG_CUR_Y, (uint16_t)(g_row_written_y - P));
        }
    } else if (g_ybump)
        cpu->gpr[5] = (uint32_t)((int32_t)cpu->gpr[5] + g_ybump);
}

static void on_quad_glyph(struct CPUState *cpu, uint32_t address) {
    (void)address;
    g_pend = 0;
    if (cpu->gpr[31] != RENDER_QUAD_RA) return;
    if (place_row(cpu, 0) && RUBY_ROW(g_row)) {
        int gaps = g_gap_code ? ruby_gap(cpu, cpu->gpr[5], 0) : 0;
        ruby_small_glyph(cpu->gpr[5], gaps);
    }
}

static void parse_rowy(const char *spec) {
    g_rowy_n = 0;
    while (spec && *spec && g_rowy_n < ROWY_MAX) {
        char *end;
        long v = strtol(spec, &end, 10);
        if (end == spec) break;
        g_rowy[g_rowy_n++] = (int)v;
        spec = (*end == ',') ? end + 1 : end;
    }
}

/* The slot ring lives in enhancement memory (0x9F000000). Allocate it at
 * registration, not on the first translated message: the runtime stamps the
 * enhancement-memory layout into every savestate header and refuses a load
 * whose layout differs from the process's current one, so a lazily grown
 * aperture made states saved after the first dialogue unloadable in a fresh
 * session (and pre-dialogue states unloadable after one). One allocation at
 * startup keeps the layout identical for the life of every process. */
static int alloc_ring(void) {
    g_ring = psx_mod_alloc_guest_memory(SLOT_SIZE * SLOT_COUNT, 16u);
    if (!g_ring) {
        say("bof3_localize: enhancement memory allocation failed; script tables off\n");
        return 0;
    }
    say("bof3_localize: ring at %08X\n", g_ring);
    return 1;
}

PSX_MOD_CONSTRUCTOR(bof3_register_localize_plugin) {
    size_t i;
    const char *ybump = getenv("BOF3_RUBY_YBUMP");
    int okr, oks, okq;
    (void)alloc_ring();
    g_ybump = ybump ? atoi(ybump) : 0;
    if (getenv("BOF3_RUBY_ROWY"))
        parse_rowy(getenv("BOF3_RUBY_ROWY"));
    if (getenv("BOF3_RUBY_GAP"))
        g_gap_code = (int)strtol(getenv("BOF3_RUBY_GAP"), NULL, 16);
    g_rowy_force = getenv("BOF3_RUBY_FORCE") ? atoi(getenv("BOF3_RUBY_FORCE")) : 0;
    g_pal = getenv("BOF3_RUBY_PAL") ? atoi(getenv("BOF3_RUBY_PAL")) : -1;
    okr = psx_mod_register_function_entry_plugin("bof3.script.rowy.render", MSGBOX_RENDER_PC,
                                                 on_msgbox_render);
    oks = psx_mod_register_function_entry_plugin("bof3.script.rowy.sprite", MSGBOX_SPRITE_PC,
                                                 on_sprite_glyph);
    okq = psx_mod_register_function_entry_plugin("bof3.script.rowy.quad", MSGBOX_QUAD_PC,
                                                 on_quad_glyph);
    okq &= psx_mod_register_function_entry_plugin("bof3.script.rowy.commit", PRIM_COMMIT_PC,
                                                  on_prim_commit);
    say("bof3_localize: furigana row rule %s (offsets %d,%d,%d,%d gap %02X, 8 px font%s%s)\n",
        okr && oks && okq ? "registered" : "FAILED", g_rowy[0], g_rowy[1], g_rowy[2], g_rowy[3],
        g_gap_code, g_rowy_force ? ", forced on every page" : "",
        g_pal >= 0 ? ", palette override" : "");
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
