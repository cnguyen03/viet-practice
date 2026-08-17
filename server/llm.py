import json

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

    return f"""You are a friendly, patient Vietnamese conversation partner helping the user practice \
speaking Vietnamese out loud. Speak Vietnamese by default; only switch to English briefly to \
explain a correction, then return to Vietnamese.

The user's Duolingo progress says they reliably know these words/phrases — use them freely: \
{known or "(none yet)"}.

These words are still weak for them — look for natural opportunities to work them into the \
conversation for reinforcement, without forcing it every turn: {weak or "(none yet)"}.

Conversation rules:
- Pick ONE simple, concrete topic for the whole conversation (e.g. ordering food, greeting a \
friend, talking about family) grounded in the vocabulary above, and stay on it.
- Keep each of your turns short (1-3 short Vietnamese sentences), like a real spoken exchange.
- If the user makes a vocabulary or grammar mistake, or says they don't know how to respond: \
gently tell them the correct word or phrase (you may briefly use English here), ask them to try \
saying it again, and only continue the conversation once they respond correctly.
- The conversation should last no more than about {MAX_TURNS_PER_TOPIC} exchanges on this topic. \
When you're told the topic is wrapping up, bring it to a natural, friendly close.
"""


def chat(state: SessionState, user_message: str, progress: dict) -> str:
    if state.topic is None:
        state.reset_topic("(let the model choose based on vocab)")

    system_prompt = build_system_prompt(progress)
    state.add_message("user", user_message)
    state.record_turn()

    messages = [{"role": "system", "content": system_prompt}] + state.history

    if state.should_wrap_up():
        messages.append(
            {
                "role": "system",
                "content": "This topic has reached its turn limit. Wrap up the conversation "
                "naturally and warmly in your next reply.",
            }
        )

    response = _client.chat(model=OLLAMA_MODEL, messages=messages)
    reply = response["message"]["content"]
    state.add_message("assistant", reply)
    return reply
