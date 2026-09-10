/* Script tables for src/bof3_localize.c, one per language code, generated
 * into generated/bof3_xlate_<code>.c (English by tools/build_script_xlate.py
 * from the US disc; Japanese (Ruby) by tools/build_ruby_script.py from the JP
 * disc). Each is sorted by the FNV-1a64 hash of the JP message bytes so the
 * plugin can binary-search it. CMake defines BOF3_XLATE_HAVE_<CODE> for every
 * table file it finds. docs/LOCALIZATION_APPLY.md */
#ifndef BOF3_XLATE_TABLE_H
#define BOF3_XLATE_TABLE_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define BOF3_XLATE_DECLARE(code)                                            \
    extern const uint32_t bof3_xlate_##code##_count;                        \
    extern const uint64_t bof3_xlate_##code##_hash[];  /* FNV-1a64 of the JP bytes */ \
    extern const uint32_t bof3_xlate_##code##_off[];   /* offset into the blob */     \
    extern const uint16_t bof3_xlate_##code##_len[];   /* length incl. terminator */  \
    extern const uint8_t  bof3_xlate_##code##_blob[];

#define BOF3_XLATE_TABLE(code_str, code)                                    \
    { code_str, &bof3_xlate_##code##_count, bof3_xlate_##code##_hash,       \
      bof3_xlate_##code##_off, bof3_xlate_##code##_len, bof3_xlate_##code##_blob }

/* The runtime-insert table of a Ruby language (generated/bof3_insert_<code>.c,
 * docs/INSERT_RUBY.md): the same layout, keyed by the FNV-1a64 of the name
 * bytes a 0x07 record holds (an item or ability name the game copied from
 * its tables), valued with the same name annotated with readings. */
#define BOF3_INSERT_DECLARE(code)                                           \
    extern const uint32_t bof3_insert_##code##_count;                       \
    extern const uint64_t bof3_insert_##code##_hash[];                      \
    extern const uint32_t bof3_insert_##code##_off[];                       \
    extern const uint16_t bof3_insert_##code##_len[];                       \
    extern const uint8_t  bof3_insert_##code##_blob[];

#define BOF3_INSERT_TABLE(code_str, code)                                   \
    { code_str, &bof3_insert_##code##_count, bof3_insert_##code##_hash,     \
      bof3_insert_##code##_off, bof3_insert_##code##_len, bof3_insert_##code##_blob }

typedef struct Bof3XlateTable {
    const char     *code;      /* [localization].languages code */
    const uint32_t *count;
    const uint64_t *hash;
    const uint32_t *off;
    const uint16_t *len;
    const uint8_t  *blob;
} Bof3XlateTable;

#ifdef __cplusplus
}
#endif

#endif
