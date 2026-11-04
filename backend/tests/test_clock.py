"""Sample shift times only: the real ones are open question O-3."""
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import pytest

from app.clock import IST, FakeClock, ShiftTimes, shift_at, shift_bounds, to_local, to_utc, work_date

A = ShiftTimes("A", time(6), time(14))
B = ShiftTimes("B", time(14), time(22))
C = ShiftTimes("C", time(22), time(6))
SHIFTS = [A, B, C]


def ist(*args):
    return datetime(*args, tzinfo=IST)


def test_fake_clock_moves_only_when_told():
    clock = FakeClock(datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc))
    assert clock.now() == clock.now()
    clock.advance(minutes=10)
    assert clock.now() == datetime(2026, 11, 4, 0, 10, tzinfo=timezone.utc)


def test_fake_clock_refuses_naive_time():
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 11, 4))


def test_ist_is_five_thirty_ahead_of_utc():
    assert to_local(datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc)).utcoffset() == timedelta(hours=5, minutes=30)
    assert to_utc(datetime(2026, 11, 4, 5, 30)) == datetime(2026, 11, 4, 0, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "moment, code",
    [
        (ist(2026, 11, 4, 6, 0), "A"),
        (ist(2026, 11, 4, 13, 59), "A"),
        (ist(2026, 11, 4, 14, 0), "B"),
        (ist(2026, 11, 4, 22, 0), "C"),
        (ist(2026, 11, 5, 3, 0), "C"),
        (ist(2026, 11, 5, 5, 59), "C"),
    ],
)
def test_shift_at(moment, code):
    assert shift_at(moment, SHIFTS).code == code


def test_shift_at_returns_none_outside_all_shifts():
    assert shift_at(ist(2026, 11, 4, 5, 0), [A, B]) is None


def test_night_shift_belongs_to_its_start_date():
    assert work_date(ist(2026, 11, 4, 23, 0), C) == date(2026, 11, 4)
    assert work_date(ist(2026, 11, 5, 3, 0), C) == date(2026, 11, 4)


def test_night_shift_work_date_across_month_end():
    assert work_date(ist(2026, 12, 1, 2, 0), C) == date(2026, 11, 30)


def test_day_shift_work_date_is_the_calendar_date():
    assert work_date(ist(2026, 11, 4, 7, 0), A) == date(2026, 11, 4)


def test_shift_bounds_cross_midnight():
    start, end = shift_bounds(date(2026, 11, 4), C)
    assert start == ist(2026, 11, 4, 22, 0)
    assert end == ist(2026, 11, 5, 6, 0)


def test_no_direct_wall_clock_outside_clock_module():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        if path.name == "clock.py":
            continue
        text = path.read_text(encoding="utf-8")
        for needle in ("datetime.now(", "datetime.utcnow(", "date.today(", "time.time("):
            if needle in text:
                offenders.append(f"{path.name}: {needle}")
    assert offenders == []
