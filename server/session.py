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
