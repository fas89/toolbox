#!/usr/bin/env python3
"""
unicode_scan.py - inspect and clean invisible / deceptive Unicode.

Stdlib only, Python 3.8+. No network, no dependencies.

    unicode_scan.py scan  PATH...            report findings
    unicode_scan.py clean PATH...            write PATH.cleaned (or --in-place)
    echo "text" | unicode_scan.py scan -     read stdin

Exit codes: 0 = nothing at/above --fail-on, 1 = findings,
            2 = usage error, unreadable path, or nothing was scanned.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------- codepoints

ZERO_WIDTH = {
    0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x180E,
    0x2061, 0x2062, 0x2063, 0x2064,
}
BIDI_MARKS = {0x200E, 0x200F}
BIDI_CONTROLS = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
                 0x2066, 0x2067, 0x2068, 0x2069}
EXOTIC_SPACES = {0x00A0, 0x1680, 0x202F, 0x205F, 0x3000} | set(range(0x2000, 0x200B))
DEPRECATED_FORMAT = {0x206A, 0x206B, 0x206C, 0x206D, 0x206E, 0x206F}

TAG_RANGE = (0xE0000, 0xE007F)
VARIATION_SELECTORS = [(0xFE00, 0xFE0F), (0xE0100, 0xE01EF)]
PRIVATE_USE = [(0xE000, 0xF8FF), (0xF0000, 0xFFFFD), (0x100000, 0x10FFFD)]

# Scripts whose rendering legitimately depends on ZWJ / ZWNJ / fillers.
JOINING_SCRIPTS = [
    (0x0590, 0x05FF),  # Hebrew
    (0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),  # Arabic
    (0xFB50, 0xFDFF), (0xFE70, 0xFEFC),                    # Arabic pres. forms
    (0x0700, 0x074F),  # Syriac
    (0x0780, 0x07BF),  # Thaana
    (0x07C0, 0x07FF),  # NKo
    (0x0900, 0x0DFF),  # Indic block run (Devanagari .. Sinhala)
    (0x0F00, 0x0FFF),  # Tibetan
    (0x1000, 0x109F),  # Myanmar
    (0x1780, 0x17FF),  # Khmer
    (0x1800, 0x18AF),  # Mongolian
    (0x1100, 0x11FF), (0xA960, 0xA97F), (0xD7B0, 0xD7FF),  # Hangul jamo
    (0xAC00, 0xD7A3),  # Hangul syllables
]
RTL_SCRIPTS = [
    (0x0590, 0x05FF), (0x0600, 0x06FF), (0x0700, 0x074F), (0x0750, 0x077F),
    (0x0780, 0x07BF), (0x07C0, 0x07FF), (0x0800, 0x085F), (0x08A0, 0x08FF),
    (0xFB1D, 0xFDFF), (0xFE70, 0xFEFC), (0x10800, 0x10FFF), (0x1E800, 0x1EFFF),
]
# Approximation of Extended_Pictographic (not exposed by unicodedata).
PICTOGRAPHIC = [
    (0x00A9, 0x00A9), (0x00AE, 0x00AE), (0x203C, 0x203C), (0x2049, 0x2049),
    (0x2122, 0x2122), (0x2139, 0x2139), (0x2194, 0x21AA), (0x231A, 0x231B),
    (0x2328, 0x2328), (0x23CF, 0x23FA), (0x24C2, 0x24C2), (0x25AA, 0x25FE),
    (0x2600, 0x27BF), (0x2934, 0x2935), (0x2B00, 0x2BFF), (0x3030, 0x3030),
    (0x303D, 0x303D), (0x3297, 0x3299), (0x1F000, 0x1FAFF),
]
FLAG_BASE = 0x1F3F4
TAG_TERMINATOR = 0xE007F
# The only subdivision flags recommended for general interchange (Unicode
# emoji-sequences.txt, RGI_Emoji_Tag_Sequence). Any other flag-shaped tag run is
# also the cheapest wrapper for a hidden tag payload, so it is not load-bearing.
RGI_SUBDIVISION_FLAGS = {"gbeng", "gbsct", "gbwls"}
PRESENTATION_SELECTORS = {0xFE0E, 0xFE0F}  # text style / emoji style
KEYCAP = 0x20E3
# Ideographs only: CJK Unified (+ Ext A..), Compatibility. Not kana, not CJK
# punctuation, not U+3000 - none of those has a registered variation sequence.
IDEOGRAPHS = [(0x3400, 0x4DBF), (0x4E00, 0x9FFF), (0xF900, 0xFAFF), (0x20000, 0x3FFFF)]
# Selectors a real ideographic variation sequence uses (IVS, and the standardized
# variants of compatibility ideographs). Exactly one per base.
IDEOGRAPHIC_SELECTORS = [(0xFE00, 0xFE02), (0xE0100, 0xE01EF)]
IVS_REASON = "selects a glyph variant of the preceding ideograph"
JOINER_REASON = "joins letters in a complex script"
# Keep rules judge one character at a time, so a payload can satisfy them one byte
# (or bit) per visible base character. These limits catch the pattern instead.
# Calibrated on Wikipedia text (2026-10-12): Persian joiners average ~2% of letters,
# worst 200-letter window 8.1%; Urdu, Hindi, Malayalam stay under 2.1%.
IVS_LIMIT = 3            # more kept ideographic selectors than this in one file is data
JOINER_WINDOW = 200      # letters + joiners
JOINER_RATIO = 0.15      # joiners per letter inside the densest window
JOINER_MIN = 6           # ...and at least this many joiners in it
LINE_SEPARATORS = {0x2028, 0x2029}
# Letters and symbols that render as blank space, so they can name an invisible
# identifier (the Hangul-filler "invisible backdoor") or pad text unseen.
BLANK_GLYPHS = {0x115F, 0x1160, 0x3164, 0xFFA0, 0x2800}
HANGUL_JAMO = [(0x1100, 0x11FF), (0xA960, 0xA97F), (0xD7B0, 0xD7FF)]
JAMO_FILLERS = {0x115F, 0x1160}
BRAILLE_DOTS = [(0x2801, 0x28FF)]  # every Braille cell except the blank one
BIDI_OVERRIDES = {0x202D, 0x202E}
BIDI_CLOSER = {0x202A: 0x202C, 0x202B: 0x202C,                 # embeddings -> PDF
               0x2066: 0x2069, 0x2067: 0x2069, 0x2068: 0x2069}  # isolates -> PDI

# Non-Latin letters that render as Latin look-alikes (homoglyph spoofing).
SCRIPT_BLOCKS = [
    ("Latin", [(0x0041, 0x005A), (0x0061, 0x007A), (0x00C0, 0x024F)]),
    ("Greek", [(0x0370, 0x03FF), (0x1F00, 0x1FFF)]),
    ("Cyrillic", [(0x0400, 0x04FF), (0x0500, 0x052F)]),
    ("Armenian", [(0x0530, 0x058F)]),
    ("Hebrew", [(0x0590, 0x05FF)]),
    ("Arabic", [(0x0600, 0x06FF)]),
    ("Cherokee", [(0x13A0, 0x13FF), (0xAB70, 0xABBF)]),
    ("Fullwidth", [(0xFF00, 0xFF5E)]),
]

SEV_ORDER = {"low": 0, "medium": 1, "high": 2}


def _in(cp: int, ranges: Sequence[Tuple[int, int]]) -> bool:
    return any(lo <= cp <= hi for lo, hi in ranges)


def _is_tag(cp: int) -> bool:
    return TAG_RANGE[0] <= cp <= TAG_RANGE[1]


# unicodedata has no names for C0/C1 controls; supply the standard abbreviations.
C0_NAMES = {
    0x00: "NULL", 0x01: "START OF HEADING", 0x02: "START OF TEXT",
    0x03: "END OF TEXT", 0x04: "END OF TRANSMISSION", 0x05: "ENQUIRY",
    0x06: "ACKNOWLEDGE", 0x07: "BELL", 0x08: "BACKSPACE",
    0x0B: "LINE TABULATION", 0x0C: "FORM FEED", 0x0E: "SHIFT OUT",
    0x0F: "SHIFT IN", 0x10: "DATA LINK ESCAPE", 0x11: "DEVICE CONTROL ONE",
    0x12: "DEVICE CONTROL TWO", 0x13: "DEVICE CONTROL THREE",
    0x14: "DEVICE CONTROL FOUR", 0x15: "NEGATIVE ACKNOWLEDGE",
    0x16: "SYNCHRONOUS IDLE", 0x17: "END OF TRANSMISSION BLOCK",
    0x18: "CANCEL", 0x19: "END OF MEDIUM", 0x1A: "SUBSTITUTE",
    0x1B: "ESCAPE", 0x1C: "INFORMATION SEPARATOR FOUR (FILE)",
    0x1D: "INFORMATION SEPARATOR THREE (GROUP)",
    0x1E: "INFORMATION SEPARATOR TWO (RECORD)",
    0x1F: "INFORMATION SEPARATOR ONE (UNIT)", 0x7F: "DELETE",
}


def _name(ch: str) -> str:
    cp = ord(ch)
    if cp in C0_NAMES:
        return C0_NAMES[cp]
    return unicodedata.name(ch, "<unnamed / unassigned>")


# ------------------------------------------------------------------ findings

@dataclass
class Finding:
    index: int
    line: int
    col: int
    codepoint: int
    char_name: str
    klass: str
    severity: str
    action: str          # "remove" | "replace" | "keep" | "report"
    reason: str = ""
    replacement: str = ""

    def label(self) -> str:
        return f"U+{self.codepoint:04X} {self.char_name}"

    def to_json(self) -> Dict[str, object]:
        d = {
            "index": self.index, "line": self.line, "col": self.col,
            "codepoint": f"U+{self.codepoint:04X}", "name": self.char_name,
            "class": self.klass, "severity": self.severity, "action": self.action,
        }
        if self.reason:
            d["reason"] = self.reason
        return d


@dataclass
class Report:
    path: str
    findings: List[Finding] = field(default_factory=list)
    mixed_script: List[Tuple[int, str, List[str]]] = field(default_factory=list)

    def acted(self) -> List[Finding]:
        return [f for f in self.findings if f.action in ("remove", "replace")]

    def kept(self) -> List[Finding]:
        return [f for f in self.findings if f.action in ("keep", "report")]

    def max_severity(self) -> Optional[str]:
        """Severity of what actually needs action - drives the CI exit code.

        Findings preserved as load-bearing are reported but never fail a gate.
        """
        sevs = [f.severity for f in self.acted()]
        if self.mixed_script:
            sevs.append("high")
        return max(sevs, key=lambda s: SEV_ORDER[s]) if sevs else None


# ------------------------------------------------------- load-bearing checks

def _neighbour(text: str, i: int, step: int) -> Optional[str]:
    j = i + step
    return text[j] if 0 <= j < len(text) else None


def _joins_script(ch: Optional[str]) -> bool:
    return ch is not None and _in(ord(ch), JOINING_SCRIPTS)


def _is_pictographic(ch: Optional[str]) -> bool:
    return ch is not None and _in(ord(ch), PICTOGRAPHIC)


def _in_flag_sequence(text: str, i: int) -> bool:
    """True if text[i] is a tag char inside one of the RGI subdivision flags."""
    j = i - 1
    while j >= 0 and _is_tag(ord(text[j])) and ord(text[j]) != TAG_TERMINATOR:
        j -= 1
    if j < 0 or ord(text[j]) != FLAG_BASE:
        return False
    k = i
    while k < len(text) and _is_tag(ord(text[k])) and ord(text[k]) != TAG_TERMINATOR:
        k += 1
    if k >= len(text) or ord(text[k]) != TAG_TERMINATOR:
        return False
    spec = "".join(chr(ord(c) - 0xE0000) for c in text[j + 1:k])
    return spec in RGI_SUBDIVISION_FLAGS


def _run_touches(text: str, i: int, run: set, ranges: Sequence[Tuple[int, int]]) -> bool:
    """True if the run of `run` codepoints around text[i] borders a character in
    `ranges` that is not itself part of the run, so a run cannot vouch for itself."""
    j = i
    while j >= 0 and ord(text[j]) in run:
        j -= 1
    k = i
    while k < len(text) and ord(text[k]) in run:
        k += 1
    return any(0 <= x < len(text) and ord(text[x]) not in run and _in(ord(text[x]), ranges)
               for x in (j, k))


def _balanced_rtl_line(text: str, i: int) -> bool:
    """True if text[i]'s line has right-to-left letters and its bidi embeddings and
    isolates all close on that line. Any override makes it False."""
    start = text.rfind("\n", 0, i) + 1
    end = text.find("\n", i)
    line = text[start:] if end == -1 else text[start:end]
    if not _has_rtl(line):
        return False
    stack: List[int] = []
    for c in line:
        cp = ord(c)
        if cp in BIDI_OVERRIDES:
            return False
        if cp in BIDI_CLOSER:
            stack.append(BIDI_CLOSER[cp])
        elif cp in (0x202C, 0x2069) and (not stack or stack.pop() != cp):
            return False
    return not stack


def _has_rtl(text: str) -> bool:
    return any(_in(ord(c), RTL_SCRIPTS) for c in text)


# ---------------------------------------------------------------- the scanner

def analyse(text: str, path: str = "-", *, aggressive: bool = False,
            normalize_spaces: bool = False, strip_leading_bom: bool = False,
            strip_bidi: bool = False, strip_controls: bool = False,
            keep_rtl_bidi: bool = False, allow_ivs: bool = False) -> Report:
    rep = Report(path=path)
    doc_has_rtl = _has_rtl(text)
    line, col = 1, 1

    for i, ch in enumerate(text):
        cp = ord(ch)
        here = (i, line, col)
        if ch == "\n":
            line, col = line + 1, 1
        else:
            col += 1

        klass = sev = action = reason = ""
        replacement = ""

        if cp in ZERO_WIDTH:
            klass, sev, action = "zero-width", "medium", "remove"
            prev, nxt = _neighbour(text, i, -1), _neighbour(text, i, 1)
            if cp in (0x200C, 0x200D) and (_joins_script(prev) or _joins_script(nxt)):
                action, reason = "keep", JOINER_REASON
            elif cp == 0x200D and (_is_pictographic(prev) or _is_pictographic(nxt)):
                action, reason = "keep", "emoji ZWJ sequence"
            elif cp == 0xFEFF and i == 0:
                if strip_leading_bom:
                    action, reason = "remove", "leading BOM (--strip-leading-bom)"
                else:
                    action, reason = "keep", "leading BOM (use --strip-leading-bom)"
            if action == "keep" and aggressive:
                action, reason = "remove", f"{reason} (overridden by --aggressive)"

        elif cp in BIDI_MARKS:
            klass, sev, action = "bidi-mark", "medium", "remove"
            if doc_has_rtl:
                action, reason = "keep", "document contains right-to-left script"
            if action == "keep" and (aggressive or strip_bidi):
                action, reason = "remove", f"{reason} (overridden)"

        elif cp in BIDI_CONTROLS:
            # Trojan Source (CVE-2021-42574): reordering controls can make
            # rendered source differ from what the compiler sees. Flagged even in
            # right-to-left documents, as rustc does: one RTL letter anywhere must
            # not switch the check off.
            klass, sev, action = "bidi-control", "high", "remove"
            if keep_rtl_bidi and not aggressive and _balanced_rtl_line(text, i):
                action, reason = "keep", "balanced on a right-to-left line (--keep-rtl-bidi)"

        elif _is_tag(cp):
            klass, sev, action = "tag-char", "high", "remove"
            if _in_flag_sequence(text, i):
                klass, sev = "tag-char", "low"
                action, reason = "keep", "part of a valid flag emoji sequence"
                if aggressive:
                    action, reason = "remove", "flag sequence (--aggressive)"

        elif _in(cp, VARIATION_SELECTORS):
            # After an emoji only the two presentation selectors are meaningful;
            # any other selector there is a byte of a smuggled payload.
            klass, sev, action = "variation-selector", "high", "remove"
            prev, nxt = _neighbour(text, i, -1), _neighbour(text, i, 1)
            keycap = (prev is not None and prev in "0123456789#*"
                      and nxt is not None and ord(nxt) == KEYCAP)
            if cp in PRESENTATION_SELECTORS and (_is_pictographic(prev) or keycap):
                action, reason = "keep", "selects text or emoji style"
            elif (prev is not None and _in(ord(prev), IDEOGRAPHS)
                  and _in(cp, IDEOGRAPHIC_SELECTORS)):
                action, reason = "keep", IVS_REASON
            if action == "keep" and aggressive:
                action, reason = "remove", "variation selector (--aggressive)"

        elif _in(cp, PRIVATE_USE):
            klass, sev, action = "private-use", "high", "remove"
            reason = "unassigned meaning; renders as a placeholder outside its origin font"

        elif cp in DEPRECATED_FORMAT:
            klass, sev, action = "deprecated-format", "high", "remove"

        elif cp in LINE_SEPARATORS:
            klass, sev, action, replacement = "line-separator", "medium", "replace", "\n"
            reason = "most editors and tools do not break the line here; converted to a newline"

        elif cp in BLANK_GLYPHS:
            klass, sev, action = "blank-glyph", "high", "remove"
            reason = "renders as blank space but counts as a letter or symbol"
            if cp in JAMO_FILLERS and _run_touches(text, i, JAMO_FILLERS, HANGUL_JAMO):
                action, reason = "keep", "part of a Hangul jamo sequence"
            elif cp == 0x2800 and _run_touches(text, i, {0x2800}, BRAILLE_DOTS):
                action, reason = "keep", "blank cell in Braille art"
            if action == "keep" and aggressive:
                action, reason = "remove", f"{reason} (--aggressive)"

        elif cp in EXOTIC_SPACES:
            klass, sev = "exotic-space", "low"
            if normalize_spaces or aggressive:
                action, replacement, reason = "replace", " ", "normalised to U+0020"
            else:
                action, reason = "keep", "use --normalize-spaces to convert to U+0020"

        elif unicodedata.category(ch) == "Cf":
            klass, sev, action = "format-control", "medium", "remove"

        elif unicodedata.category(ch) == "Cc" and ch not in "\t\n\r":
            # A control character in a text file is usually deliberate: ANSI
            # colour codes, ASCII separators (Iceberg REST joins namespaces on
            # U+001F), protocol framing. Report, but never silently delete -
            # stripping these corrupts data and breaks tests.
            klass, sev, action = "control", "medium", "report"
            nxt = _neighbour(text, i, 1)
            if cp == 0x1B and nxt in ("[", "]", "(", ")", "=", ">", "P", "_"):
                reason = "ANSI escape sequence"
            elif 0x1C <= cp <= 0x1F:
                reason = "ASCII separator, commonly a deliberate delimiter"
            else:
                reason = "control character, usually deliberate"
            if strip_controls or aggressive:
                action, reason = "remove", f"{reason} (--strip-controls)"
            else:
                reason += " - use --strip-controls to remove"

        if klass:
            rep.findings.append(Finding(
                index=here[0], line=here[1], col=here[2], codepoint=cp,
                char_name=_name(ch), klass=klass, severity=sev,
                action=action, reason=reason, replacement=replacement,
            ))

    _flag_payload_patterns(rep, text, allow_ivs=allow_ivs)
    rep.mixed_script = _mixed_script_words(text)
    return rep


def _flag_payload_patterns(rep: Report, text: str, *, allow_ivs: bool) -> None:
    """Re-flag kept selectors and joiners whose numbers look like data, not text."""
    ivs = [f for f in rep.findings if f.action == "keep" and f.reason == IVS_REASON]
    if len(ivs) > IVS_LIMIT and not allow_ivs:
        for f in ivs:
            f.action, f.severity = "remove", "high"
            f.reason = (f"{len(ivs)} ideographic variation selectors in one file; ordinary "
                        f"text carries a few at most (--allow-ivs for name or registry data)")

    joiners = [f for f in rep.findings if f.action == "keep" and f.reason == JOINER_REASON]
    if len(joiners) < JOINER_MIN:
        return
    at = {f.index for f in joiners}
    seq = [1 if i in at else 0 for i, c in enumerate(text) if i in at or _joins_script(c)]
    width = min(JOINER_WINDOW, len(seq))
    count = densest = sum(seq[:width])
    for k in range(width, len(seq)):
        count += seq[k] - seq[k - width]
        densest = max(densest, count)
    if densest >= JOINER_MIN and densest > JOINER_RATIO * max(width - densest, 1):
        for f in joiners:
            f.action, f.severity = "remove", "high"
            f.reason = ("joiners too dense for prose (over 15% of letters in a 200-letter "
                        "window): the shape of a hidden bit stream")


def _script_of(ch: str) -> Optional[str]:
    if not ch.isalpha():
        return None
    cp = ord(ch)
    for name, ranges in SCRIPT_BLOCKS:
        if _in(cp, ranges):
            return name
    return None


def _mixed_script_words(text: str) -> List[Tuple[int, str, List[str]]]:
    """Words mixing Latin with another script - the homoglyph spoofing signal."""
    out: List[Tuple[int, str, List[str]]] = []
    word, start, scripts = [], 0, set()
    line = 1

    def flush() -> None:
        if len(scripts) > 1 and "Latin" in scripts:
            out.append((start, "".join(word), sorted(scripts)))

    for i, ch in enumerate(text):
        if ch.isalpha():
            if not word:
                start = line
            word.append(ch)
            s = _script_of(ch)
            if s:
                scripts.add(s)
        else:
            if word:
                flush()
            word, scripts = [], set()
            if ch == "\n":
                line += 1
    if word:
        flush()
    return out


def apply_clean(text: str, rep: Report) -> str:
    drop = {f.index: f for f in rep.acted()}
    return "".join(
        drop[i].replacement if i in drop else ch
        for i, ch in enumerate(text)
    )


# ------------------------------------------------------------------ reporting

_SEV_TAG = {"high": "HIGH  ", "medium": "MEDIUM", "low": "LOW   "}


def render(rep: Report, *, verbose: bool = False) -> str:
    lines: List[str] = []
    acted, kept = rep.acted(), rep.kept()
    if not rep.findings and not rep.mixed_script:
        return f"{rep.path}: clean - no invisible or deceptive characters found."

    lines.append(f"{rep.path}")
    by_class: Dict[str, List[Finding]] = {}
    for f in rep.findings:
        by_class.setdefault(f"{f.severity}|{f.klass}", []).append(f)

    for key in sorted(by_class, key=lambda k: -SEV_ORDER[k.split("|")[0]]):
        sev, klass = key.split("|")
        group = by_class[key]
        acts = sum(1 for f in group if f.action in ("remove", "replace"))
        keeps = len(group) - acts
        tail = f"{acts} to strip" + (f", {keeps} preserved" if keeps else "")
        lines.append(f"  [{_SEV_TAG[sev]}] {klass}: {len(group)} ({tail})")
        shown = group if verbose else group[:5]
        for f in shown:
            note = f" - {f.reason}" if f.reason else ""
            lines.append(f"      {f.line}:{f.col}  {f.label()}  [{f.action}]{note}")
        if len(group) > len(shown):
            lines.append(f"      ... {len(group) - len(shown)} more (use --verbose)")

    for line_no, word, scripts in rep.mixed_script:
        lines.append(f"  [{_SEV_TAG['high']}] mixed-script word: line {line_no} "
                     f"{word!r} mixes {' + '.join(scripts)} [report only]")

    lines.append(f"  => {len(acted)} character(s) would be removed or replaced; "
                 f"{len(kept)} preserved as load-bearing.")
    return "\n".join(lines)


# ----------------------------------------------------------------------- main

def iter_paths(paths: Sequence[str], recurse: bool) -> Iterator[str]:
    for p in paths:
        if p == "-":
            yield p
        elif os.path.isdir(p) and recurse:
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d not in
                           {".git", "node_modules", "__pycache__", ".venv", "dist", "build"}]
                for fn in sorted(files):
                    yield os.path.join(root, fn)
        else:
            yield p


def read_text(path: str) -> Optional[str]:
    """The file's text, or None when it is binary or not UTF-8. Raises OSError."""
    if path == "-":
        return sys.stdin.read()
    with open(path, "rb") as fh:
        raw = fh.read()
    if b"\x00" in raw[:8192]:
        return None  # binary
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="unicode_scan.py",
        description="Inspect and clean invisible / deceptive Unicode.")
    ap.add_argument("mode", choices=["scan", "clean"])
    ap.add_argument("paths", nargs="+", help="files, directories (with -r), or - for stdin")
    ap.add_argument("-r", "--recurse", action="store_true")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("-v", "--verbose", action="store_true", help="list every occurrence")
    ap.add_argument("--in-place", action="store_true", help="clean: overwrite the input")
    ap.add_argument("--suffix", default=".cleaned", help="clean: output suffix (default .cleaned)")
    ap.add_argument("--aggressive", action="store_true",
                    help="also strip load-bearing invisibles (emoji glue, script joiners, flags)")
    ap.add_argument("--normalize-spaces", action="store_true",
                    help="convert NBSP and exotic spaces to U+0020")
    ap.add_argument("--allow-ivs", action="store_true",
                    help="keep any number of ideographic variation sequences "
                         "(name or registry data); by default more than 3 in a file is flagged")
    ap.add_argument("--keep-rtl-bidi", action="store_true",
                    help="keep bidi embeddings/isolates that are balanced on a line "
                         "containing right-to-left text (overrides are never kept)")
    ap.add_argument("--strip-bidi", action="store_true",
                    help="strip bidi marks (LRM/RLM) even in documents containing RTL script")
    ap.add_argument("--strip-controls", action="store_true",
                    help="remove C0/C1 control characters (ANSI codes, ASCII separators); "
                         "report-only by default because they are usually deliberate")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="scan: only print files that have findings")
    ap.add_argument("--strip-leading-bom", action="store_true")
    ap.add_argument("--nfkc", action="store_true", help="clean: apply NFKC normalisation after stripping")
    ap.add_argument("--fail-on", choices=["never", "low", "medium", "high"], default="low",
                    help="exit 1 when a finding at/above this severity exists (default low)")
    args = ap.parse_args(argv)
    if args.json and args.mode == "clean" and "-" in args.paths:
        ap.error("--json cannot clean stdin: the cleaned text would be mixed into the JSON")
    for p in args.paths:
        if p != "-" and os.path.isdir(p) and not args.recurse:
            ap.error(f"{p} is a directory; pass -r to scan it")

    reports: List[Report] = []
    residual: List[Report] = []
    skipped: List[str] = []
    unreadable = 0
    changed = 0

    for path in iter_paths(args.paths, args.recurse):
        try:
            text = read_text(path)
        except OSError as exc:
            print(f"cannot read {path}: {exc}", file=sys.stderr)
            unreadable += 1
            continue
        if text is None:
            skipped.append(path)
            continue
        rep = analyse(text, path, aggressive=args.aggressive,
                      normalize_spaces=args.normalize_spaces,
                      strip_leading_bom=args.strip_leading_bom,
                      strip_bidi=args.strip_bidi, keep_rtl_bidi=args.keep_rtl_bidi,
                      allow_ivs=args.allow_ivs,
                      strip_controls=args.strip_controls)
        reports.append(rep)

        if args.mode == "clean":
            out = apply_clean(text, rep)
            if args.nfkc:
                out = unicodedata.normalize("NFKC", out)
            # The exit code reports RESIDUAL risk: what survived the clean and
            # still needs a human (mixed-script words, kept bidi in RTL docs).
            residual.append(analyse(out, path, aggressive=args.aggressive,
                                    normalize_spaces=args.normalize_spaces,
                                    strip_leading_bom=args.strip_leading_bom,
                                    strip_bidi=args.strip_bidi, keep_rtl_bidi=args.keep_rtl_bidi,
                      allow_ivs=args.allow_ivs,
                                    strip_controls=args.strip_controls))
            if out == text:
                continue
            changed += 1
            if path == "-":
                sys.stdout.write(out)
                continue
            dest = path if args.in_place else path + args.suffix
            with open(dest, "w", encoding="utf-8", newline="") as fh:
                fh.write(out)
            if not args.json:
                print(f"wrote {dest} ({len(rep.acted())} character(s) removed/replaced)",
                      file=sys.stderr)

    if args.json:
        print(json.dumps({
            "mode": args.mode,
            "files": [{
                "path": r.path,
                "max_severity": r.max_severity(),
                "removed": len(r.acted()),
                "preserved": len(r.kept()),
                "findings": [f.to_json() for f in r.findings],
                "mixed_script": [
                    {"line": ln, "word": w, "scripts": s} for ln, w, s in r.mixed_script
                ],
            } for r in reports],
        }, indent=2, ensure_ascii=False))
    elif args.mode == "scan":
        for r in reports:
            if args.quiet and not r.acted() and not r.mixed_script:
                continue
            print(render(r, verbose=args.verbose))
    elif changed == 0:
        print("nothing to clean.", file=sys.stderr)

    # A gate that could not look must never pass.
    if skipped:
        hint = "" if args.verbose else " (use --verbose to list them)"
        print(f"skipped {len(skipped)} file(s) that are binary or not UTF-8{hint}",
              file=sys.stderr)
        if args.verbose:
            for p in skipped:
                print(f"  skipped: {p}", file=sys.stderr)
    if unreadable:
        return 2
    if not reports:
        print("nothing scanned: no readable text files", file=sys.stderr)
        return 2

    if args.fail_on == "never":
        return 0
    threshold = SEV_ORDER[args.fail_on]
    gate = residual if args.mode == "clean" else reports
    worst = [SEV_ORDER[s] for s in (r.max_severity() for r in gate) if s]
    return 1 if worst and max(worst) >= threshold else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
