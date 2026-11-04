"""The only place that reads the wall clock.

Domain code gets the time from `now()`, so tests can move time with a FakeClock.
Also holds IST/UTC conversion and the shift and work-date rules
(a night shift belongs to the date it started).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable, Protocol
from zoneinfo import ZoneInfo

from flask import current_app

IST = ZoneInfo("Asia/Kolkata")


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FakeClock:
    """A clock that only moves when told to. For tests."""

    def __init__(self, start: datetime):
        if start.tzinfo is None:
            raise ValueError("FakeClock needs an aware datetime")
        self._now = start.astimezone(timezone.utc)

    def now(self) -> datetime:
        return self._now

    def advance(self, **delta) -> None:
        self._now += timedelta(**delta)

    def set(self, value: datetime) -> None:
        self._now = value.astimezone(timezone.utc)


def now() -> datetime:
    """Current time in UTC, from the app's clock."""
    return current_app.extensions["clock"].now()


def to_local(value: datetime) -> datetime:
    return value.astimezone(IST)


def to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=IST)
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ShiftTimes:
    code: str
    starts: time
    ends: time

    @property
    def crosses_midnight(self) -> bool:
        return self.ends <= self.starts

    def contains(self, moment: time) -> bool:
        if self.crosses_midnight:
            return moment >= self.starts or moment < self.ends
        return self.starts <= moment < self.ends


def shift_at(moment: datetime, shifts: Iterable[ShiftTimes]) -> ShiftTimes | None:
    local = to_local(moment).time()
    for shift in shifts:
        if shift.contains(local):
            return shift
    return None


def work_date(moment: datetime, shift: ShiftTimes) -> date:
    """The date a moment counts towards: a night shift belongs to its start date."""
    local = to_local(moment)
    if shift.crosses_midnight and local.time() < shift.ends:
        return local.date() - timedelta(days=1)
    return local.date()


def shift_bounds(day: date, shift: ShiftTimes) -> tuple[datetime, datetime]:
    """UTC start and end of a shift on its work date."""
    start = datetime.combine(day, shift.starts, IST)
    end_day = day + timedelta(days=1) if shift.crosses_midnight else day
    end = datetime.combine(end_day, shift.ends, IST)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
