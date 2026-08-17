import uuid
from dataclasses import dataclass, field

from server.config import MAX_TURNS_PER_TOPIC


@dataclass
class SessionState:
    """Per-conversation state, held server-side for the lifetime of one session."""

    topic: str | None = None
    turn_count: int = 0
    in_correction_loop: bool = False
    history: list[dict] = field(default_factory=list)

    def record_turn(self) -> None:
        self.turn_count += 1

    def should_wrap_up(self) -> bool:
        return self.turn_count >= MAX_TURNS_PER_TOPIC

    def add_message(self, role: str, content: str) -> None:
        self.history.append({"role": role, "content": content})

    def reset_topic(self, new_topic: str | None = None) -> None:
        self.topic = new_topic
        self.turn_count = 0
        self.in_correction_loop = False
        self.history = []


# Sessions are keyed by an id the client holds, so several devices (or a phone
# and the laptop) can practice at once without sharing conversation history.
_sessions: dict[str, SessionState] = {}


def get_or_create(session_id: str | None) -> tuple[str, SessionState]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    new_id = session_id or uuid.uuid4().hex
    _sessions[new_id] = SessionState()
    return new_id, _sessions[new_id]


def drop(session_id: str) -> None:
    _sessions.pop(session_id, None)
