# Codepoint classes

What the scanner detects, why it matters, and what it does by default.

| Class | Codepoints | Severity | Default |
| --- | --- | --- | --- |
| `zero-width` | `U+200B` ZWSP, `U+200C` ZWNJ, `U+200D` ZWJ, `U+2060` WJ, `U+FEFF` BOM, `U+00AD` SHY, `U+180E`, `U+2061`–`U+2064` | medium | remove unless load-bearing; joiners denser than prose are flagged **high** |
| `bidi-control` | `U+202A`–`U+202E`, `U+2066`–`U+2069` | **high** | remove (`--keep-rtl-bidi` keeps balanced embeddings/isolates on RTL lines; overrides never) |
| `bidi-mark` | `U+200E` LRM, `U+200F` RLM | medium | remove unless the document contains RTL script |
| `tag-char` | `U+E0000`–`U+E007F` | **high** | remove unless inside one of the three RGI subdivision flags |
| `variation-selector` | `U+FE00`–`U+FE0F`, `U+E0100`–`U+E01EF` | **high** | remove unless `U+FE0E`/`U+FE0F` after an emoji or keycap digit, or one ideographic selector after an ideograph (more than 3 per file flagged unless `--allow-ivs`) |
| `private-use` | `U+E000`–`U+F8FF`, `U+F0000`–`U+FFFFD`, `U+100000`–`U+10FFFD` | **high** | remove |
| `deprecated-format` | `U+206A`–`U+206F` | **high** | remove |
| `line-separator` | `U+2028`, `U+2029` | medium | replace with a newline |
| `blank-glyph` | `U+115F`, `U+1160`, `U+3164`, `U+FFA0` Hangul fillers, `U+2800` blank Braille | **high** | remove unless the run borders a real jamo or a visible Braille dot |
| `exotic-space` | `U+00A0`, `U+1680`, `U+2000`–`U+200A`, `U+202F`, `U+205F`, `U+3000` | low | keep (opt in with `--normalize-spaces`) |
| `format-control` | any other `Cf` general category | medium | remove |
| `control` | `Cc` other than tab/LF/CR | medium | report only (opt in with `--strip-controls`) |
| `mixed-script` | Latin + another script inside one word | **high** | report only, never auto-fixed |

## Why each class matters

**Zero-width.** Breaks `grep`, string equality, and identifier matching while looking
identical on screen. `U+00AD` (soft hyphen) is the sneakiest: invisible until a line wraps.
Also the classic channel for steganographic payloads — a run of ZWSP/ZWNJ encodes bits.

**Bidi controls.** The Trojan Source attack (CVE-2021-42574, Boucher & Anderson 2021). An
`U+202E` RIGHT-TO-LEFT OVERRIDE inside a comment reorders the *rendered* line so a reviewer
sees `if (isAdmin) { … }` where the compiler sees a comment and unguarded code. Affects
essentially every language with block comments and string literals. Treat any bidi control
in source as high severity until proven intentional. The scanner does, even in documents
that contain right-to-left text: if one Hebrew letter anywhere in a file switched the check
off, an attacker would add one. `--keep-rtl-bidi` is the opt-in for RTL prose: it keeps
embeddings and isolates only when the same line has RTL letters and every one of them
closes on that line. Overrides (`U+202D`, `U+202E`) are never kept.

**Tag characters.** `U+E0000`–`U+E007F` mirror ASCII, render as nothing, and survive most
copy-paste. Their only sanctioned use is subdivision flag emoji, and only three of those
are recommended for general interchange: England, Scotland and Wales. Anywhere else,
including any other `U+1F3F4 … U+E007F` wrapper, they are a covert channel — the current
favourite for hiding instructions inside text that a human reviewer cannot see.

**Variation selectors.** `U+FE00`–`U+FE0F` and `U+E0100`–`U+E01EF` legitimately pick a
glyph variant, but there are 256 of them, so a run after any base character carries one
byte per selector and is invisible everywhere. After an emoji only `U+FE0E` (text style)
and `U+FE0F` (emoji style) mean anything; every other selector there is payload. After an
ideograph, a registered variation sequence uses exactly one selector from `U+E0100`–`U+E01EF`
(or `U+FE00`–`U+FE02`), and ordinary text almost never contains one. So the scanner keeps
up to 3 per file and flags them all beyond that: otherwise a payload hides one byte behind
each ideograph of a Chinese or Japanese sentence.

**Private use.** No assigned meaning. Renders as whatever the origin font decides and as
tofu everywhere else, so it survives review while carrying out-of-band data.

**Line separators.** `U+2028` and `U+2029` end a line for some parsers (JavaScript, many
Unicode-aware readers) and not for others (most editors, `grep`, diff tools). The same file
then has different line structure depending on who reads it. Cleaning converts them to a
plain newline.

**Blank glyphs.** The Hangul fillers render as empty space but are classified as letters,
so they are valid in identifiers: a JavaScript variable named `U+3164` is invisible in
review (the "invisible backdoor"). `U+2800` BRAILLE PATTERN BLANK does the same job in
prose and usernames. Kept only where they belong: a jamo filler whose run borders a real
jamo, a blank Braille cell whose run borders a visible dot. A run of blanks never counts
as its own context.

**Exotic spaces.** Mostly a formatting nuisance, but NBSP inside code or a URL is a real
bug, and a `U+3000` ideographic space in an identifier is deliberate. Low severity because
NBSP is frequently intentional in prose (French typography, `10 km`), so normalising is
opt-in.

**Control characters.** Report-only by design. A `Cc` codepoint in a text file is usually
deliberate: `U+001B` starts ANSI colour sequences (so any test fixture for terminal-log
rendering is full of them), and `U+001C`–`U+001F` are ASCII separators used as delimiters —
the Iceberg REST catalog spec joins multipart namespaces on `U+001F`. Deleting these
silently corrupts data and breaks tests, so the scanner names them and stops. Pass
`--strip-controls` when you genuinely want them gone.

**Mixed-script words.** The homoglyph signal. Cyrillic `U+0421`, Greek `U+039F`, and
Cherokee `U+13A0` are visually identical to Latin `C`, `O` and `D`. Used to spoof domains,
package names, and identifiers. Report-only by design: replacing them is a semantic
decision, since a genuinely Cyrillic word is not an attack.

## Load-bearing preservation

A carrier and a functional character can be the same codepoint. The rule is context:

| Character | Load-bearing when | Carrier when |
| --- | --- | --- |
| `U+200D` ZWJ | between emoji, or joining complex-script letters at prose density | between ASCII, or over 15% of letters in a 200-letter window |
| `U+200C` ZWNJ | inside Arabic/Persian/Indic/Hangul text at prose density | between ASCII, or over 15% of letters in a 200-letter window |
| `U+FE0E`/`U+FE0F` | follows an emoji or a keycap digit | follows anything else |
| `U+FE00`–`U+FE02`, `U+E0100`–`U+E01EF` | one after an ideograph, at most 3 per file (or `--allow-ivs`) | after kana, punctuation, a letter or a space; or the 4th in a file |
| `U+E00xx` tag | inside the England, Scotland or Wales flag | anywhere else, including other flag-shaped runs |
| `U+115F`/`U+1160` | the filler run borders a real jamo | anywhere else, including a run of fillers |
| `U+2800` | the blank run borders a visible Braille dot | anywhere else, including a run of blanks |
| `U+200F` RLM | document contains RTL letters | pure-LTR document |
| bidi embedding/isolate | `--keep-rtl-bidi`, RTL letters on the same line, all closed on that line | everywhere else, always for overrides |
| `U+FEFF` BOM | at offset 0 | anywhere else in the file |

`--aggressive` overrides all of these. It will visibly corrupt emoji sequences and Persian
or Devanagari text, so only reach for it when the user explicitly wants a paranoid pass and
accepts that cost.

## What it cannot catch

The keep rules and the two density limits are heuristics, so a patient attacker still has a
narrow channel. Name it rather than claim otherwise:

- **Up to 3 bytes per file** as ideographic variation selectors, under `IVS_LIMIT`.
- **About 1 bit per 7 letters** of Arabic-script or Indic text as joiners kept under the
  15% density limit: at most about 30 bits per 200 letters. Real Persian prose measured
  2% overall and 8.1% in its densest 200-letter window, so the limit sits at about twice that.
- **Look-alike words written wholly in another script.** Mixed-script detection needs Latin
  plus another script in one word; an all-Cyrillic word that reads as `admin` is not mixed.
- **Meaning-level steganography**: word choice, spacing patterns, whitespace at line ends.
  The scanner checks characters, not content.

The limits were calibrated on Wikipedia text on 2026-10-12. Tighten `IVS_LIMIT`,
`JOINER_RATIO` and `JOINER_WINDOW` in `scripts/unicode_scan.py` if your corpus allows it.

## Prior art

- [dcondrey/unicode-safety-check](https://github.com/dcondrey/unicode-safety-check) — GitHub
  Action covering the same classes at PR time; use it as a CI gate alongside this skill.
- [Trojan Source](https://trojansource.codes/) — the original CVE-2021-42574 paper and PoCs.
- [The Invisible JavaScript Backdoor](https://certitude.consulting/blog/en/invisible-backdoor/)
  — Hangul filler `U+3164` as an identifier.
- [Smuggling arbitrary data through an emoji](https://paulbutler.org/2025/smuggling-arbitrary-data-through-an-emoji/)
  — one byte per variation selector.
- [emoji-sequences.txt](https://www.unicode.org/Public/emoji/latest/emoji-sequences.txt) —
  the RGI tag sequences (the three flags above).
- Rust `unicode-security` and the `confusable_homoglyphs` Python package implement UTS #39
  confusable detection more completely than the block heuristic used here.
- `ftfy` fixes mojibake and encoding damage — a different problem, often present in the same
  files.

The scanner is stdlib-only because these tools either run as CI services, target one class,
or pull dependency trees; a single-file script with no install step composes better with an
agent that needs to inspect an arbitrary file right now.
