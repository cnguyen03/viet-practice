---
name: update-vocab
description: Add Vietnamese vocabulary to data/vietnamese_progress.json, the file that grounds every practice session. Use when the user pastes words they've learned, says which Duolingo unit or section they've reached, wants their vocabulary refreshed or expanded, or asks to "update my vocab" / "sync my progress".
---

# Updating the practice vocabulary

`data/vietnamese_progress.json` decides what the agent talks about and which
words it reinforces. Duolingo has no working API and nothing exposes a learner's
real word list, so this file is populated here instead.

Everything goes through `scripts/vocab.py`, which merges by Vietnamese word
(so re-running is safe), fills gaps with the local Ollama model, sorts entries
into known vs. weak, and writes atomically.

## Which route to take

**The user pasted words** → build entries from exactly those words. Don't add
extras they didn't mention.

**The user named a unit or level** (e.g. "I finished Section 1 Unit 5",
"I'm a beginner") → generate the vocabulary a learner would plausibly know by
that point. Write the entries yourself rather than delegating to the local 7B
model: your Vietnamese and course knowledge are better than its. Aim for 25-60
words for a unit, weighted toward everyday nouns, verbs, and question words that
actually come up in conversation.

## Setting strength

`strength` is what splits the two lists, at a 0.6 cutoff:

- `0.8-0.95` — solid; the agent uses these freely
- `0.6-0.75` — comfortable but worth practising
- `0.3-0.55` — shaky; the agent deliberately works these into conversation

Default to ~0.5 for brand-new material and ~0.85 for older units the user has
drilled. If the user says a word is giving them trouble, put it below 0.6 —
that is the whole mechanism for getting it practised.

## Running it

Pass a JSON array on stdin. Include `en` and `example_sentences` when you can:
anything you supply is kept as-is, and only missing fields go to the local model
(which is slower and lower quality).

```bash
cd <project root>
cat <<'JSON' | uv run scripts/vocab.py add
[
  {"vi": "nhà hàng", "en": "restaurant", "strength": 0.45,
   "example_sentences": [{"vi": "Nhà hàng này rất ngon.", "en": "This restaurant is very good."}]},
  {"vi": "gọi món", "en": "to order food", "strength": 0.4}
]
JSON
```

Add `--no-enrich` when every entry is already complete — it skips the Ollama
pass entirely and returns immediately.

Other commands:

```bash
uv run scripts/vocab.py show      # counts, plus which entries are incomplete
uv run scripts/vocab.py enrich    # fill gaps left by earlier runs
```

## Afterwards

1. Run `show` and report the resulting counts to the user.
2. Mention that a running server picks the file up on the next message —
   `load_progress` re-reads it per request, so no restart is needed.

## Watch out for

- **Diacritics are meaning.** `ma`, `má`, `mà`, `mả`, `mã`, `mạ` are six
  different words. Never write Vietnamese without them.
- **Keep example sentences short** — they are read aloud by the TTS voice, and
  they should use only vocabulary at or below the learner's level.
- **Never put personal data anywhere but this file.** It is gitignored;
  `data/vietnamese_progress.example.json` is the committed sample and must keep
  its placeholder content.
