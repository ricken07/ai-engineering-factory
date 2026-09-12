from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from time import monotonic_ns
from typing import Protocol


class Clock(Protocol):
    """Two-source clock: UTC wall time for timestamps, monotonic time for durations."""

    def now(self) -> datetime: ...

    def monotonic_ns(self) -> int: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic_ns(self) -> int:
        return monotonic_ns()


@dataclass
class FakeClock:
    """Deterministic clock for contract tests; no sleeping is necessary."""

    wall_time: datetime
    elapsed_ns: int = 0

    def now(self) -> datetime:
        return self.wall_time

    def monotonic_ns(self) -> int:
        return self.elapsed_ns

    def advance(self, *, milliseconds: int = 0) -> None:
        self.elapsed_ns += milliseconds * 1_000_000
        self.wall_time += timedelta(milliseconds=milliseconds)


def timestamp(clock: Clock) -> str:
    return clock.now().astimezone(timezone.utc).isoformat()


def unavailable_metric() -> dict[str, object]:
    return {"value": None, "availability": "UNAVAILABLE"}


def observed_duration(nanoseconds: int) -> dict[str, object]:
    if nanoseconds < 0:
        # A monotonic epoch moved backwards (for example a persisted execution
        # resumed after reboot). It is unknown, never an observed zero.
        return unavailable_metric()
    return {"value": nanoseconds // 1_000_000, "availability": "OBSERVED"}
