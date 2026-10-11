# clean-invisible-unicode

Text can carry characters you cannot see. Some are a nuisance: a zero-width space pasted
into an identifier makes `grep` and string comparison fail on text that looks identical.
Some are attacks: bidi controls make a reviewer read different code than the compiler runs
(Trojan Source), tag characters spell out hidden instructions for an AI agent, and a Hangul
filler can name a variable nobody can see.

This skill gives your agent a stdlib-only Python scanner that finds them, explains each
one, and removes only the ones that are carriers. Emoji sequences, Persian and Devanagari
joiners, the Scotland/England/Wales flags and Braille art keep working.

## What a scan looks like

A planted file: a bidi override in a comment, a zero-width space inside `'admin'`, a
family emoji, a Hangul-filler variable, and a fake flag wrapping a hidden instruction.

```
$ python3 scripts/unicode_scan.py scan auth.py
auth.py
  [HIGH  ] bidi-control: 2 (2 to strip)
      2:17  U+202E RIGHT-TO-LEFT OVERRIDE  [remove]
      2:21  U+2066 LEFT-TO-RIGHT ISOLATE  [remove]
  [HIGH  ] blank-glyph: 1 (1 to strip)
      5:5  U+3164 HANGUL FILLER  [remove] - renders as blank space but counts as a letter or symbol
  [HIGH  ] tag-char: 31 (31 to strip)
      6:15  U+E0073 TAG LATIN SMALL LETTER S  [remove]
      6:16  U+E0065 TAG LATIN SMALL LETTER E  [remove]
      6:17  U+E006E TAG LATIN SMALL LETTER N  [remove]
      6:18  U+E0064 TAG LATIN SMALL LETTER D  [remove]
      6:19  U+E0020 TAG SPACE  [remove]
      ... 26 more (use --verbose)
  [MEDIUM] zero-width: 3 (1 to strip, 2 preserved)
      3:24  U+200B ZERO WIDTH SPACE  [remove]
      4:23  U+200D ZERO WIDTH JOINER  [keep] - emoji ZWJ sequence
      4:25  U+200D ZERO WIDTH JOINER  [keep] - emoji ZWJ sequence
  => 35 character(s) would be removed or replaced; 2 preserved as load-bearing.
```

`clean` writes `auth.py.cleaned` (or rewrites in place with `--in-place`). Exit codes make
it a CI gate: `0` clean, `1` findings, `2` when it could not look (a bad path, a directory
without `-r`, nothing scanned), so a typo never passes silently.

## Install

See the [repository README](../../README.md#install).

## Scope

Character-level only. It does not strip file metadata (see
`references/metadata-hygiene.md` for that), and it is not a tool for removing
AI-provenance signals such as C2PA Content Credentials or SynthID.

Prior art and sources are listed in `references/codepoint-classes.md`.
