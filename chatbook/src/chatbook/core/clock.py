"""Time source of the app: integer milliseconds since the epoch, injectable for tests."""

import time
from typing import Protocol


class Clock(Protocol):
    def now_ms(self) -> int: ...


class SystemClock:
    """The real clock."""

    def now_ms(self) -> int:
        return int(time.time() * 1000)


class FakeClock:
    """A clock that stands still until advance() is called (tests, demo)."""

    def __init__(self, start_ms: int = 1_700_000_000_000) -> None:
        self._now = start_ms

    def now_ms(self) -> int:
        return self._now

    def advance(self, ms: int) -> None:
        self._now += ms
