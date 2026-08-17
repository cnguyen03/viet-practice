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

Style:
- Reply in Vietnamese. Keep it to 1-2 short, natural spoken sentences — this is being read \
aloud, so avoid anything long or written-sounding.
- Ask a simple question most turns to keep the conversation going.
- Stay on ONE everyday topic for the whole conversation (greetings, food, family, directions). \
Pick it from what they know. Do not drift between topics.
- If you need a word of English to unblock them, put it in parentheses, e.g. \
"Bạn thích món gì? (what dish do you like?)". Parentheses must contain ENGLISH ONLY — never \
repeat Vietnamese inside them. Only the Vietnamese is spoken aloud, so never put anything \
essential inside parentheses, and skip them entirely when the sentence is already clear.

When the user makes a mistake, or says they don't know how to answer:
1. Say the correct Vietnamese phrase clearly.
2. Add a very short English gloss in parentheses if it helps.
3. Ask them to say it back.
4. Do NOT move the conversation forward until they attempt it. Once they say it correctly \
(or close enough), praise them briefly and continue.
Correct only what actually blocks communication — ignore small slips, and never correct more \
than one thing at a time.

The conversation lasts about {MAX_TURNS_PER_TOPIC} exchanges. If you are told the topic is \
wrapping up, close it warmly in one or two sentences.
"""


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
    "The user just signalled they are stuck or don't know how to answer. For THIS reply only: "
    "give them one short, natural Vietnamese phrase they could say right now, followed by a "
    "brief English translation in parentheses. Then ask them to say it back. "
    "Do NOT change the subject, do NOT ask a different question, and do NOT move the "
    "conversation forward until they have tried it."
)

RETRY_DIRECTIVE = (
    "The user has just attempted the phrase you taught them. Briefly praise the attempt in "
    "Vietnamese, then continue the conversation naturally with one simple follow-up question."
)


def looks_stuck(text: str) -> bool:
    return bool(_STUCK_PATTERNS.search(text))


# Asking the learner to repeat the phrase is the whole point of the correction
# loop, and a 7B model drops it more often than not. Rather than trust the
# prompt, append it ourselves when the model has forgotten.
_ASKED_TO_REPEAT = re.compile(
    r"nói\s+lại|lặp\s+lại|nhắc\s+lại|thử\s+nói|nói\s+thử|say\s+it", re.IGNORECASE
)
REPEAT_NUDGE = "Bạn thử nói lại nhé! (try saying it back)"


def ensure_repeat_request(reply: str) -> str:
    if _ASKED_TO_REPEAT.search(reply):
        return reply
    return f"{reply.rstrip()} {REPEAT_NUDGE}"


def chat(state: SessionState, user_message: str, progress: dict) -> str:
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

    response = _client.chat(model=OLLAMA_MODEL, messages=messages)
    reply = response["message"]["content"].strip()

    if state.in_correction_loop:
        reply = ensure_repeat_request(reply)

    state.add_message("assistant", reply)
    return reply
