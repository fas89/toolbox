#!/usr/bin/env bash
# Every check CI runs. Run it before pushing: a green run here is a green run there.
# Needs: uv (https://docs.astral.sh/uv/), python3, and the `claude` CLI.
set -euo pipefail
cd "$(dirname "$0")/.."

fail=0
skills=()
while IFS= read -r -d '' d; do skills+=("$d"); done < <(find skills -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
if [ ${#skills[@]} -eq 0 ]; then echo "✗ no skills/ folders found"; exit 1; fi

echo "== Agent Skills spec (skills-ref)"
for d in "${skills[@]}"; do
  uvx --quiet --from skills-ref==0.1.1 agentskills validate "$d" || fail=1
done

echo "== License copies"
for d in "${skills[@]}"; do
  if cmp -s LICENSE "$d/LICENSE.txt"; then
    echo "✓ $d/LICENSE.txt"
  else
    echo "✗ $d/LICENSE.txt is missing or differs from LICENSE"
    fail=1
  fi
done

echo "== Marketplace entries match skills/"
python3 - "${skills[@]}" <<'PY' || fail=1
import json, sys
folders = {p.split("/", 1)[1] for p in sys.argv[1:]}
entries = json.load(open(".claude-plugin/marketplace.json"))["plugins"]
errors = []
for e in entries:
    if e["name"] not in folders:
        errors.append(f"entry {e['name']!r} has no skills/{e['name']}/ folder")
    if e.get("source") != f"./skills/{e['name']}":
        errors.append(f"entry {e['name']!r}: source must be ./skills/{e['name']}")
    if "version" in e:
        errors.append(f"entry {e['name']!r}: drop 'version' so installs track commits")
for name in sorted(folders - {e["name"] for e in entries}):
    errors.append(f"skills/{name}/ has no marketplace entry")
for msg in errors:
    print("✗", msg)
if not errors:
    print(f"✓ {len(entries)} entries")
sys.exit(1 if errors else 0)
PY

echo "== No hidden Unicode (skills are prompts; invisible characters in them are injection)"
python3 - <<'PY' || fail=1
import pathlib, sys
HIDDEN = [
    (0x00AD, 0x00AD),    # soft hyphen
    (0x034F, 0x034F),    # combining grapheme joiner
    (0x115F, 0x1160),    # Hangul fillers
    (0x180E, 0x180E),    # Mongolian vowel separator
    (0x200B, 0x200F),    # zero-width space/joiners, LRM/RLM
    (0x2028, 0x202E),    # line/paragraph separators, bidi embeddings and overrides
    (0x2060, 0x2064),    # word joiner, invisible operators
    (0x2066, 0x2069),    # bidi isolates
    (0x3164, 0x3164),    # Hangul filler
    (0xE000, 0xF8FF),    # private use
    (0xFE00, 0xFE0E),    # variation selectors; FE0F (emoji style) is allowed, a payload needs the rest
    (0xFEFF, 0xFEFF),    # BOM / zero-width no-break space
    (0xFFA0, 0xFFA0),    # halfwidth Hangul filler
    (0xFFF9, 0xFFFB),    # interlinear annotation
    (0xE0000, 0xE007F),  # tag characters
    (0xE0100, 0xE01EF),  # variation selectors supplement
]
TEXT = {"", ".md", ".txt", ".json", ".sh", ".py", ".js", ".mjs", ".ts", ".html", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".csv"}
bad = 0
for path in sorted(pathlib.Path(".").rglob("*")):
    if ".git" in path.parts or not path.is_file() or path.suffix.lower() not in TEXT:
        continue
    # split on "\n" only: splitlines() would swallow U+2028/U+2029 as line breaks
    for n, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
        for ch in line:
            if any(lo <= ord(ch) <= hi for lo, hi in HIDDEN):
                print(f"✗ {path}:{n}: U+{ord(ch):04X}")
                bad += 1
print("✓ clean" if not bad else f"{bad} hidden character(s)")
sys.exit(1 if bad else 0)
PY

echo "== Tests"
if out=$(PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests 2>&1); then
  echo "✓ $(printf '%s\n' "$out" | grep '^Ran')"
else
  printf '%s\n' "$out"
  fail=1
fi

echo "== Claude Code marketplace"
claude plugin validate . --strict || fail=1

exit $fail
