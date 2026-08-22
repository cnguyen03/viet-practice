#!/usr/bin/env python3
"""Compare candidate models on the failures seen in real practice sessions.

Every case here came from an actual conversation, not a hypothetical:

  greeting      a normal opening — must not be reported as an error
  word_error    "anh" for "ăn"; the model must name the RIGHT fix
  gibberish     mistranscribed speech that qwen2.5 praised as "Rất tốt!"
  stuck         "I'm stuck" must trigger teaching, not a change of subject

Usage:
  uv run scripts/bench_models.py                       # default candidates
  uv run scripts/bench_models.py --runs 5 --models a b
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import PROGRESS_JSON_PATH  # noqa: E402
from server.llm import chat, has_cjk, load_progress  # noqa: E402
from server.session import SessionState  # noqa: E402

DEFAULT_MODELS = [
    "qwen2.5:7b-instruct",
    "hf.co/aisingapore/Gemma-SEA-LION-v3-9B-IT-GGUF:Q4_K_M",
    "gemma3:12b",
]

CASES = [
    {
        "id": "greeting",
        "say": "Xin chào, tôi là Calvin",
        "want_assessment": {"good"},
    },
    {
        "id": "word_error",
        "say": "Tôi thích anh phở với bò.",
        "want_assessment": {"needs_work"},
        # The correction has to actually contain the right word.
        "want_in_correction": "ăn",
    },
    {
        "id": "gibberish",
        "say": "Đôi quỳ, bán quỳ cầm.",
        "want_assessment": {"needs_work", "unintelligible"},
    },
    {
        "id": "stuck",
        "say": "I'm stuck.",
        "want_teaching": True,
    },
]

_VIETNAMESE = re.compile(
    r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]",
    re.IGNORECASE,
)
_TEACHES = re.compile(r"say|try|repeat|means", re.IGNORECASE)


def score_case(case: dict, result: dict) -> list[str]:
    """Return a list of failures for this response ([] means it passed)."""
    problems = []

    if any(has_cjk(str(result.get(f, ""))) for f in
           ("reply", "reply_en", "feedback", "correction")):
        problems.append("CJK")

    want = case.get("want_assessment")
    if want and result["assessment"] not in want:
        problems.append(f"assessment={result['assessment']}")

    needle = case.get("want_in_correction")
    if needle and needle not in result.get("correction", ""):
        problems.append(f"correction missing '{needle}'")

    feedback = result.get("feedback", "")
    if not feedback:
        problems.append("no feedback")
    elif _VIETNAMESE.search(feedback) and not re.search(r"[a-zA-Z]{3,}", feedback):
        problems.append("feedback not English")

    if case.get("want_teaching") and not _TEACHES.search(feedback):
        problems.append("did not teach a phrase")

    if not result.get("reply"):
        problems.append("empty reply")
    if result.get("reply") and not _VIETNAMESE.search(result["reply"]):
        problems.append("reply not Vietnamese")

    return problems


def run_model(model: str, progress: dict, runs: int) -> dict:
    print(f"\n{'=' * 72}\n{model}\n{'=' * 72}")
    tally = {"pass": 0, "fail": 0, "cjk": 0}
    latencies = []

    for case in CASES:
        results = []
        for _ in range(runs):
            state = SessionState()
            # A greeting first, so every case is judged mid-conversation.
            if case["id"] != "greeting":
                chat(state, "Xin chào", progress, model=model)

            started = time.time()
            try:
                result = chat(state, case["say"], progress, model=model)
            except Exception as err:  # noqa: BLE001
                results.append([f"error: {type(err).__name__}"])
                continue
            latencies.append(time.time() - started)

            problems = score_case(case, result)
            results.append(problems)
            if "CJK" in problems:
                tally["cjk"] += 1
            tally["pass" if not problems else "fail"] += 1

        ok = sum(1 for r in results if not r)
        flat = sorted({p for r in results for p in r})
        status = "PASS" if ok == runs else ("part" if ok else "FAIL")
        print(f"  [{status}] {case['id']:<11} {ok}/{runs} clean"
              + (f"   issues: {', '.join(flat)}" if flat else ""))

    total = tally["pass"] + tally["fail"]
    avg = sum(latencies) / len(latencies) if latencies else 0
    print(f"  ---> {tally['pass']}/{total} clean responses, "
          f"{tally['cjk']} with Chinese, {avg:.1f}s avg")
    return {"model": model, **tally, "avg_latency": avg}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--models", nargs="*", default=DEFAULT_MODELS)
    args = parser.parse_args()

    progress = load_progress(PROGRESS_JSON_PATH)
    summary = [run_model(m, progress, args.runs) for m in args.models]

    print(f"\n{'=' * 72}\nSUMMARY\n{'=' * 72}")
    print(f"  {'model':<52} {'clean':>8} {'CJK':>5} {'avg':>6}")
    for row in sorted(summary, key=lambda r: -r["pass"]):
        total = row["pass"] + row["fail"]
        name = row["model"]
        if len(name) > 50:
            name = name[:24] + "…" + name[-25:]
        print(f"  {name:<52} {row['pass']:>4}/{total:<3} "
              f"{row['cjk']:>5} {row['avg_latency']:>5.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
