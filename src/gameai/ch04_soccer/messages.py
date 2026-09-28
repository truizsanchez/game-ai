"""Messages between soccer players (C++ ``SoccerMessages.h``)."""

from __future__ import annotations

from enum import Enum, auto


class Message(Enum):
    RECEIVE_BALL = auto()  # extra: the Vector2D where the ball is being passed to
    PASS_TO_ME = auto()  # extra: the requesting FieldPlayer
    SUPPORT_ATTACKER = auto()
    GO_HOME = auto()
    WAIT = auto()
