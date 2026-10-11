---
name: clean-invisible-unicode
description: >-
  Find and remove invisible or deceptive Unicode in text and source files -
  zero-width characters, bidi controls (Trojan Source / CVE-2021-42574), tag-character
  payloads, variation-selector smuggling, blank-glyph identifiers, private-use codepoints,
  exotic spaces, and homoglyph/mixed-script spoofing. Preserves load-bearing invisibles
  (emoji ZWJ, script joiners, flag sequences) so real text is never corrupted. Use when
  the user asks to strip invisible/hidden/zero-width characters, clean up pasted or
  AI-generated text, fix text that breaks diffs, grep, or copy-paste, audit a repo for
  adversarial Unicode, or investigate suspicious characters in a file.
license: MIT
compatibility: Requires Python 3.8+ (standard library only). No network access.
metadata:
  author: fas89
  source: https://github.com/fas89/toolbox
---

# Clean invisible Unicode

Two jobs, one tool:

- **Hygiene** — pasted and generated text carries zero-width spaces, NBSPs, and soft
  hyphens that break `grep`, corrupt diffs, and split identifiers that look identical.
- **Security** — bidi controls make rendered source differ from what the compiler sees
  (Trojan Source, CVE-2021-42574); tag characters and variation selectors smuggle hidden
  payloads past human review; homoglyphs spoof identifiers and domains; blank-glyph
  letters such as `U+3164` name variables nobody can see.

Everything runs locally through `scripts/unicode_scan.py` — stdlib only, no network, no
dependencies, no service to start.

## Always inspect before cleaning

```bash
python3 scripts/unicode_scan.py scan FILE
```

Report the findings to the user *before* modifying anything. The scan groups by class and
severity, gives `line:col` for every occurrence, and states what it would strip versus what
it would preserve and why.

## Clean

```bash
python3 scripts/unicode_scan.py clean FILE            # writes FILE.cleaned
python3 scripts/unicode_scan.py clean FILE --in-place # only when the user asks
```

Default is a **new file**. Only use `--in-place` on explicit request, or when the file is
tracked by git and you have confirmed the working tree is clean.

Useful flags:

| Flag | Effect |
| --- | --- |
| `--normalize-spaces` | NBSP and exotic spaces → `U+0020` (off by default: NBSP is often deliberate) |
| `--keep-rtl-bidi` | keep bidi embeddings/isolates that close on a line containing RTL text; overrides are never kept |
| `--strip-bidi` | strip bidi marks (LRM/RLM) even in documents that contain RTL script |
| `--strip-controls` | remove C0/C1 controls (report-only by default: ANSI codes and ASCII separators are usually deliberate) |
| `--strip-leading-bom` | remove a byte-order mark at offset 0 (kept by default) |
| `--nfkc` | apply NFKC normalisation after stripping |
| `--aggressive` | also strip load-bearing invisibles — **breaks emoji and Persian/Devanagari text**, use only when the user wants a paranoid pass |
| `-r` | recurse into directories (skips `.git`, `node_modules`, `dist`, …) |
| `-q` | only print files that have findings — use this on any repo-wide scan |
| `--json` | machine-readable output |
| `-v` | list every occurrence instead of the first five, and every skipped file |

Read `references/codepoint-classes.md` for the full taxonomy and what each class implies.

## What it will not break

The scanner distinguishes carriers from **load-bearing** invisibles and preserves the
latter by default, reporting each one with a reason:

- `U+200D` inside an emoji ZWJ sequence (family: `U+1F468 U+200D U+1F469 U+200D U+1F467`)
- `U+200C`/`U+200D` joining letters in Arabic, Persian, Devanagari, Hangul, and other
  complex scripts
- tag characters inside the three recommended subdivision flags, England, Scotland and
  Wales (`U+1F3F4`, then tags spelling `gbsct`, then `U+E007F`). Any other flag-shaped
  tag run is treated as a payload: it is the cheapest wrapper for hidden text.
- `U+FE0E`/`U+FE0F` choosing text or emoji style after an emoji or a keycap digit (red
  heart: `U+2764 U+FE0F`). Any other selector after an emoji is removed, because that is
  how bytes are smuggled through an emoji.
- variation selectors after CJK ideographs (standardized and ideographic variants)
- `U+2800` blank cells next to visible Braille dots, and Hangul jamo fillers next to a real
  jamo. A run of blanks cannot vouch for itself.
- bidi marks (LRM/RLM) in documents that actually contain right-to-left script. Bidi
  *controls* are always flagged, as rustc does: one RTL letter anywhere in a file must not
  switch off Trojan Source detection. Pass `--keep-rtl-bidi` for RTL prose that uses
  balanced embeddings or isolates.
- C0/C1 control characters — ANSI colour codes in log-rendering tests, ASCII separators
  used as deliberate delimiters (the Iceberg REST spec joins namespaces on `U+001F`)

The same characters between plain ASCII are carriers and *are* stripped. This distinction is
the whole reason to use the script instead of a `sed` one-liner.

## Exit codes (CI gate)

`0` = nothing actionable, `1` = findings at or above `--fail-on` (default `low`), `2` = a
usage error, an unreadable path, or nothing scanned. A gate that could not look never
passes. Binary and non-UTF-8 files are skipped and counted on stderr.

In **clean** mode the exit code reflects *residual* risk — what survived the clean and still
needs a human, such as a mixed-script identifier. So this chains correctly:

```bash
python3 scripts/unicode_scan.py clean src.py --in-place && echo "fully neutralised"
```

As a pre-commit or CI check, gate on severity:

```bash
python3 scripts/unicode_scan.py scan . -r --fail-on high
```

Mixed-script words are **report-only** — never auto-rewritten, since replacing Cyrillic
`U+0421` with Latin `C` changes meaning if the word is genuinely Cyrillic. Surface them and
let the user decide.

## Reporting to the user

State plainly:

1. What was removed, by class, with counts — this is verifiable and exact.
2. What was preserved and why — so they can override with `--aggressive` if they meant to.
3. What is report-only and still needs a decision (mixed-script words).

Do not claim a cleaned file is "safe" or "human-written". The tool removes specific
codepoints; that is all it proves. For file metadata (EXIF GPS, device serials, author
names), see `references/metadata-hygiene.md` — a separate concern with separate tools.

## Scope

This skill handles **character-level** issues only. It does not remove statistical or
pixel-domain watermarks, and it is not a way to defeat AI-provenance systems: stripping
C2PA Content Credentials, SynthID, or similar disclosure signals is out of scope, as is
rewriting text to evade AI detectors. If a user wants that, say so directly rather than
half-doing it.
