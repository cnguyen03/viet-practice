#!/usr/bin/env python3
"""Maintain data/vietnamese_progress.json — the file that grounds every session.

Duolingo has no working public API and no source exposes a learner's actual word
list, so vocabulary is supplied here instead: pasted by hand, or generated for a
course unit. Missing translations and example sentences are filled in by the
local Ollama model, so this still works with no internet once the model is
pulled.

Usage:
  # merge entries (JSON list on stdin), enriching anything incomplete
  echo '[{"vi":"nhà hàng","en":"restaurant","strength":0.4}]' \\
      | uv run scripts/vocab.py add

  uv run scripts/vocab.py enrich     # fill gaps in existing entries
  uv run scripts/vocab.py show       # summary
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import OLLAMA_HOST, OLLAMA_MODEL, PROGRESS_JSON_PATH  # noqa: E402

# Entries at or above this are safe for the agent to use freely; below it they
# get deliberately worked into conversation for reinforcement.
KNOWN_THRESHOLD = 0.6

EMPTY = {
    "synced_at": None,
    "streak_days": 0,
    "level": 0,
    "skills": [],
    "known_words": [],
    "weak_words": [],
}


def load(path: Path) -> dict:
    if not path.exists():
        return dict(EMPTY)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for key, default in EMPTY.items():
        data.setdefault(key, default)
    return data


def save(path: Path, data: dict) -> None:
    data["synced_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")  # write-then-rename: never leave a half file
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def all_entries(data: dict) -> list[dict]:
    return data["known_words"] + data["weak_words"]


def reroute(data: dict) -> None:
    """Sort every entry into known/weak by its current strength."""
    entries = {e["vi"]: e for e in all_entries(data)}.values()
    data["known_words"] = sorted(
        (e for e in entries if e.get("strength", 0) >= KNOWN_THRESHOLD),
        key=lambda e: e["vi"],
    )
    data["weak_words"] = sorted(
        (e for e in entries if e.get("strength", 0) < KNOWN_THRESHOLD),
        key=lambda e: e["vi"],
    )


def needs_enrichment(entry: dict) -> bool:
    return not entry.get("en") or not entry.get("example_sentences")


def enrich_entry(client, entry: dict) -> dict:
    """Ask the local model for a translation and one natural example sentence."""
    prompt = (
        f'For the Vietnamese word or phrase "{entry["vi"]}", reply with ONLY a JSON object:\n'
        '{"en": "<short English translation>", '
        '"examples": [{"vi": "<short natural Vietnamese sentence using it>", '
        '"en": "<English translation of that sentence>"}]}\n'
        "Use one simple beginner-level sentence. No markdown, no commentary."
    )
    try:
        raw = client.chat(
            model=OLLAMA_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )["message"]["content"]
        match = re.search(r"\{.*\}", raw, re.S)
        parsed = json.loads(match.group(0)) if match else {}
    except Exception as err:  # noqa: BLE001 - enrichment is best-effort
        print(f"  ! could not enrich {entry['vi']}: {err}", file=sys.stderr)
        return entry

    if not entry.get("en") and parsed.get("en"):
        entry["en"] = str(parsed["en"]).strip()
    if not entry.get("example_sentences") and parsed.get("examples"):
        examples = [
            {"vi": str(ex.get("vi", "")).strip(), "en": str(ex.get("en", "")).strip()}
            for ex in parsed["examples"]
            if isinstance(ex, dict) and ex.get("vi")
        ]
        if examples:
            entry["example_sentences"] = examples[:2]
    return entry


def enrich_all(data: dict, force: bool = False) -> int:
    from ollama import Client

    todo = [e for e in all_entries(data) if force or needs_enrichment(e)]
    if not todo:
        return 0
    client = Client(host=OLLAMA_HOST)
    print(f"Enriching {len(todo)} entr{'y' if len(todo) == 1 else 'ies'} via {OLLAMA_MODEL}…")
    for i, entry in enumerate(todo, 1):
        enrich_entry(client, entry)
        print(f"  [{i}/{len(todo)}] {entry['vi']} — {entry.get('en', '?')}")
    return len(todo)


def cmd_add(args) -> int:
    try:
        incoming = json.load(sys.stdin)
    except json.JSONDecodeError as err:
        print(f"stdin is not valid JSON: {err}", file=sys.stderr)
        return 1
    if isinstance(incoming, dict):
        incoming = [incoming]

    data = load(args.path)
    existing = {e["vi"]: e for e in all_entries(data)}

    added = updated = 0
    for item in incoming:
        vi = str(item.get("vi", "")).strip()
        if not vi:
            continue
        if vi in existing:
            entry = existing[vi]
            updated += 1
        else:
            entry = {"vi": vi}
            existing[vi] = entry
            added += 1
        for field in ("en", "strength", "unit"):
            if item.get(field) not in (None, ""):
                entry[field] = item[field]
        if item.get("example_sentences"):
            entry["example_sentences"] = item["example_sentences"]
        entry.setdefault("strength", 0.5)

    data["known_words"], data["weak_words"] = list(existing.values()), []
    if not args.no_enrich:
        enrich_all(data)
    reroute(data)
    save(args.path, data)

    print(f"\n{added} added, {updated} updated -> {args.path}")
    print(f"known: {len(data['known_words'])}  weak: {len(data['weak_words'])}")
    return 0


def cmd_enrich(args) -> int:
    data = load(args.path)
    count = enrich_all(data, force=args.force)
    reroute(data)
    save(args.path, data)
    print(f"\nEnriched {count} entries -> {args.path}")
    return 0


def cmd_show(args) -> int:
    data = load(args.path)
    print(f"file       : {args.path}")
    print(f"synced_at  : {data.get('synced_at')}")
    print(f"level      : {data.get('level')}   streak: {data.get('streak_days')}")
    print(f"known ({len(data['known_words']):>3}): "
          + ", ".join(e["vi"] for e in data["known_words"][:12])
          + (" …" if len(data["known_words"]) > 12 else ""))
    print(f"weak  ({len(data['weak_words']):>3}): "
          + ", ".join(e["vi"] for e in data["weak_words"][:12])
          + (" …" if len(data["weak_words"]) > 12 else ""))
    missing = [e["vi"] for e in all_entries(data) if needs_enrichment(e)]
    if missing:
        print(f"incomplete : {len(missing)} ({', '.join(missing[:8])}"
              + (" …" if len(missing) > 8 else "") + ")")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", type=Path, default=PROGRESS_JSON_PATH)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="merge JSON entries from stdin")
    p_add.add_argument("--no-enrich", action="store_true",
                       help="skip Ollama enrichment (entries are already complete)")
    p_add.set_defaults(func=cmd_add)

    p_enrich = sub.add_parser("enrich", help="fill missing translations/examples")
    p_enrich.add_argument("--force", action="store_true", help="redo every entry")
    p_enrich.set_defaults(func=cmd_enrich)

    sub.add_parser("show", help="summarise the file").set_defaults(func=cmd_show)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
