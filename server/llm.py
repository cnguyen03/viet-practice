import json
import re

from ollama import Client

from server.config import OLLAMA_HOST, OLLAMA_MODEL, MAX_TURNS_PER_TOPIC
from server.session import SessionState

_client = Client(host=OLLAMA_HOST)


def load_progress(path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_system_prompt(progress: dict) -> str:
    known = ", ".join(w["vi"] for w in progress.get("known_words", []))
    weak = ", ".join(w["vi"] for w in progress.get("weak_words", []))

    return f"""You are a warm, patient Vietnamese conversation partner. The user is a learner \
practising SPEAKING out loud, so this is a spoken conversation, not a lesson.

Vocabulary they know well — use these freely: {known or "(none yet)"}.
Vocabulary that is still shaky: {weak or "(none yet)"}.

How to use the shaky words: at most ONE per reply, and only when the sentence would have been \
natural anyway. A forced sentence built around a word is worse than not using it — if it does \
not fit, simply don't use it. This applies double to abstract connectives (words like "mặc dù"): \
skip those unless the conversation genuinely calls for them.

Every turn you return five fields.

"assessment" — judge ONLY the user's most recent Vietnamese:
  "good"          it was understandable and essentially correct
  "needs_work"    understandable but with a real grammar or word-choice error
  "unintelligible" it was not recognisable Vietnamese at all

Be honest. Do NOT say something was good when it was not — false praise teaches \
them nothing. Their words reach you through speech recognition, so garbled input \
usually means they mispronounced it or the recogniser failed.

Use "unintelligible" whenever the words do not form a meaningful Vietnamese \
sentence, even if each word exists on its own. Never invent a meaning for \
gibberish and never guess at a "correction" for it — say you could not make it \
out and ask them to repeat.

"feedback" — ENGLISH ONLY, one or two sentences, addressed to the learner.
  good:           say briefly what they got right, e.g. "Nice - that's a correct sentence."
  needs_work:     name the actual mistake plainly, e.g. "Small fix: 'anh' should be \
'ăn' (to eat)." Correct ONE thing only, the one that most blocks understanding.
  unintelligible: say you couldn't make it out and suggest what to try, e.g. \
"I couldn't catch that. Try saying it a bit slower."
  Never write Vietnamese-only feedback, and never leave this empty.

"correction" — if assessment is "needs_work", THEIR WHOLE SENTENCE rewritten \
correctly in Vietnamese — not just the fixed word, and nothing else. Otherwise \
an empty string.
  If you cannot write a correction you are genuinely confident in, the input was \
not really a sentence: use "unintelligible" and leave this empty. A guessed \
correction that is still nonsense is worse than admitting you did not catch it.

"reply" — your conversational answer, in VIETNAMESE ONLY. 1-2 short spoken \
sentences that MOVE THE CONVERSATION FORWARD, usually ending in a simple \
question. This is read aloud, so no English, no parentheses, no notes — just \
what a person would say.
  NEVER open with praise ("Rất tốt", "Tốt lắm", "Giỏi lắm") — praise belongs in \
"feedback" and nowhere else.
  NEVER repeat their sentence back or restate the correction here — that is what \
"correction" is for. If you corrected them, reply to what they MEANT and carry \
on the conversation.

"reply_en" — a plain English translation of YOUR "reply" field. It must match \
your reply exactly. Do not translate the user's words here.

NEVER write Chinese, Japanese or Korean characters in any field. Vietnamese is \
written in the Latin alphabet with diacritics (e.g. "phở", not "河粉").

Keep the whole conversation on ONE everyday topic (greetings, food, family, \
directions), chosen from vocabulary they know. Do not drift between topics.

The conversation lasts about {MAX_TURNS_PER_TOPIC} exchanges. If you are told the topic is \
wrapping up, close it warmly.
"""


# Forcing the shape server-side is what stops the model blending conversation,
# correction and translation into one string — the failure that produced
# mismatched glosses and praise for gibberish.
REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "assessment": {"type": "string", "enum": ["good", "needs_work", "unintelligible"]},
        "feedback": {"type": "string"},
        "correction": {"type": "string"},
        "reply": {"type": "string"},
        "reply_en": {"type": "string"},
    },
    "required": ["assessment", "feedback", "correction", "reply", "reply_en"],
}


# A 7B model does not reliably notice "I'm stuck" on its own and will happily
# change the subject instead of teaching. Detecting it here and issuing a
# direct instruction for that one turn makes the behaviour dependable.
_STUCK_PATTERNS = re.compile(
    r"""
      không\s+biết        # "I don't know"
    | ko\s+biết
    | chưa\s+biết
    | quên\s+(rồi|mất)    # "I forgot"
    | nói\s+(sao|thế\s+nào|như\s+thế\s+nào)   # "how do I say"
    | tiếng\s+việt\s+là\s+gì                  # "what is it in Vietnamese"
    | i\s+(don'?t|do\s+not)\s+know
    | how\s+do\s+(i|you)\s+say
    | what'?s\s+the\s+word
    | no\s+idea
    | i'?m\s+stuck
    """,
    re.IGNORECASE | re.VERBOSE,
)

STUCK_DIRECTIVE = (
    "The user just signalled they are stuck or don't know how to answer — this is not a "
    "mistake, so set assessment to \"good\". In \"feedback\", give them one short Vietnamese "
    "phrase they could say right now with its English meaning, and ask them to say it back. "
    "Put that same Vietnamese phrase in \"correction\". Keep \"reply\" to a short encouraging "
    "Vietnamese line — do NOT change the subject or ask a new question, and do not move the "
    "conversation on until they have tried it."
)

RETRY_DIRECTIVE = (
    "The user has just attempted the phrase you taught them. Judge that attempt honestly in "
    "\"assessment\", then continue the conversation in \"reply\" with one simple follow-up "
    "question."
)


def looks_stuck(text: str) -> bool:
    return bool(_STUCK_PATTERNS.search(text))


# Asking the learner to repeat the phrase is the whole point of the correction
# loop, and a 7B model drops it more often than not. Rather than trust the
# prompt, append it ourselves when the model has forgotten.
_ASKED_TO_REPEAT = re.compile(
    r"nói\s+lại|lặp\s+lại|nhắc\s+lại|thử\s+nói|nói\s+thử|say\s+it|try\s+saying|repeat",
    re.IGNORECASE,
)
REPEAT_NUDGE = "Try saying it back."


def ensure_repeat_request(feedback: str) -> str:
    if _ASKED_TO_REPEAT.search(feedback):
        return feedback
    return f"{feedback.rstrip()} {REPEAT_NUDGE}"


# Vietnamese leaking into the English feedback field, or English into the spoken
# reply, both defeat the point — so strip the obvious cases rather than trusting
# the model to have obeyed.
_PARENTHETICAL = re.compile(r"\([^)]*\)")

# Praise belongs in the English feedback. The model still opens replies with it
# out of habit, which made every turn sound approving regardless of assessment.
_LEADING_PRAISE = re.compile(
    r"^\s*(rất\s+tốt|tốt\s+lắm|tốt\s+nhé|tốt\s+quá|giỏi\s+lắm|giỏi\s+quá"
    r"|hay\s+lắm|hay\s+quá|chính\s+xác|chuẩn\s+rồi|chuẩn|đúng\s+rồi|tốt)\s*[!,.…]+\s*",
    re.IGNORECASE,
)

# The learner asked for feedback in English, always. The model sometimes answers
# in Vietnamese instead, which is useless to them — detect it and substitute a
# plain English line rather than shipping feedback they cannot read.
_ENGLISH_MARKERS = re.compile(
    r"\b(the|is|are|was|should|you|your|that|this|to|it|try|say|said|good|nice|"
    r"correct|mean|means|instead|a|an|and|not|but|with|for|in|of|use|used|"
    r"catch|caught|understand|sentence|word|again|slower)\b",
    re.IGNORECASE,
)

_FALLBACK_FEEDBACK = {
    "good": "That was correct.",
    "needs_work": "Not quite right — check the sentence above.",
    "unintelligible": "I couldn't make that out. Try saying it again, a little slower.",
}


def looks_english(text: str) -> bool:
    return bool(_ENGLISH_MARKERS.search(text))


# Qwen is a Chinese-trained model and sometimes answers in Chinese mid-sentence.
# Spoken aloud by a Vietnamese voice this is gibberish, so it never ships.
_CJK = re.compile(r"[一-鿿㐀-䶿぀-ヿ가-힯]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?。！？])\s*")

NO_CJK_DIRECTIVE = (
    "Your previous answer contained Chinese characters. Vietnamese uses the Latin "
    "alphabet with diacritics. Rewrite it using ONLY Vietnamese in \"reply\" and ONLY "
    "English in \"feedback\" and \"reply_en\". Never output Chinese, Japanese or Korean."
)

FALLBACK_REPLY = "Xin lỗi, mình nói lại nhé. Bạn khỏe không?"
FALLBACK_REPLY_EN = "Sorry, let me start again. How are you?"


def has_cjk(text: str) -> bool:
    return bool(_CJK.search(text))


def strip_cjk(text: str) -> str:
    """Drop whole sentences containing CJK, keeping the usable remainder."""
    kept = [s for s in _SENTENCE_SPLIT.split(text) if s.strip() and not has_cjk(s)]
    return " ".join(kept).strip()


def chat(
    state: SessionState,
    user_message: str,
    progress: dict,
    model: str | None = None,
) -> dict:
    if state.topic is None:
        state.reset_topic("(let the model choose based on vocab)")

    system_prompt = build_system_prompt(progress)
    state.add_message("user", user_message)
    state.record_turn()

    messages = [{"role": "system", "content": system_prompt}] + state.history

    # Teaching a stuck user takes priority over everything else, including
    # wrapping up — being abandoned mid-correction is the worst outcome.
    if looks_stuck(user_message):
        state.in_correction_loop = True
        messages.append({"role": "system", "content": STUCK_DIRECTIVE})
    elif state.in_correction_loop:
        state.in_correction_loop = False
        messages.append({"role": "system", "content": RETRY_DIRECTIVE})
    elif state.should_wrap_up():
        messages.append(
            {
                "role": "system",
                "content": "This topic has reached its turn limit. Wrap up the conversation "
                "naturally and warmly in your next reply.",
            }
        )

    # Regenerate once if Chinese leaks in: a clean second attempt reads far
    # better than a salvaged first one.
    parsed = {}
    use_model = model or OLLAMA_MODEL
    for attempt in range(2):
        response = _client.chat(model=use_model, messages=messages, format=REPLY_SCHEMA)
        raw = response["message"]["content"].strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Never lose a turn to a malformed response — treat it as the reply.
            parsed = {"assessment": "good", "feedback": "", "reply": raw, "reply_en": ""}

        contaminated = any(
            has_cjk(str(parsed.get(field, "")))
            for field in ("reply", "reply_en", "feedback", "correction")
        )
        if not contaminated:
            break
        if attempt == 0:
            messages = messages + [{"role": "system", "content": NO_CJK_DIRECTIVE}]

    result = {
        "assessment": parsed.get("assessment", "good"),
        "feedback": str(parsed.get("feedback", "")).strip(),
        "correction": str(parsed.get("correction", "")).strip(),
        # The reply is spoken aloud, so drop any English aside that slipped in,
        # and strip habitual praise so approval is never implied by accident.
        "reply": _LEADING_PRAISE.sub(
            "", _PARENTHETICAL.sub("", str(parsed.get("reply", "")))
        ).strip(),
        "reply_en": str(parsed.get("reply_en", "")).strip(),
    }
    if result["assessment"] not in ("good", "needs_work", "unintelligible"):
        result["assessment"] = "good"

    # Last resort if the retry also came back contaminated: drop the offending
    # sentences outright rather than speak Chinese at a Vietnamese learner.
    for field in ("reply", "reply_en", "feedback", "correction"):
        if has_cjk(result[field]):
            result[field] = strip_cjk(result[field])
    if not result["reply"]:
        result["reply"] = FALLBACK_REPLY
        result["reply_en"] = FALLBACK_REPLY_EN

    # Feedback must be English and must exist — it is the whole point of the turn.
    if not result["feedback"] or not looks_english(result["feedback"]):
        if result["correction"]:
            # Don't throw away a phrase it was teaching just because the wording
            # around it came back in the wrong language.
            result["feedback"] = f"Try saying: {result['correction']}"
        else:
            result["feedback"] = _FALLBACK_FEEDBACK[result["assessment"]]

    # A correction is only meaningful alongside an actual error — except while
    # teaching a stuck learner, where it carries the phrase to repeat.
    if result["assessment"] != "needs_work" and not state.in_correction_loop:
        result["correction"] = ""

    if state.in_correction_loop and result["feedback"]:
        result["feedback"] = ensure_repeat_request(result["feedback"])

    # Only the Vietnamese belongs in the dialogue history; feeding the feedback
    # back in makes the model start narrating corrections inside its replies.
    state.add_message("assistant", result["reply"])
    return result
