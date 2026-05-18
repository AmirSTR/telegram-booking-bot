from datetime import datetime, timedelta, date
from typing import List


def get_weekdays_for_next_days(days: int = 14) -> List[str]:
    """Returns list of upcoming weekday dates (Mon-Fri) as YYYY-MM-DD strings."""
    result = []
    current = date.today()
    count = 0
    while count < days:
        current += timedelta(days=1)
        if current.weekday() < 5:  # Monday=0, Friday=4
            result.append(current.strftime("%Y-%m-%d"))
            count += 1
    return result


def generate_time_slots(work_start: str, work_end: str, slot_duration: int) -> List[str]:
    """Generates all possible time slots for a day."""
    slots = []
    fmt = "%H:%M"
    start = datetime.strptime(work_start, fmt)
    end = datetime.strptime(work_end, fmt)
    current = start
    while current + timedelta(minutes=slot_duration) <= end:
        slots.append(current.strftime(fmt))
        current += timedelta(minutes=slot_duration)
    return slots


def get_free_slots(all_slots: List[str], booked_slots: list, service_duration: int) -> List[str]:
    """
    Filters out time slots that overlap with existing bookings.

    Fix #4: Previously blocked only slots aligned to master's slot_duration,
    which allowed overlapping bookings if service duration != slot_duration.
    Now we mark every minute occupied by a booking as busy, then reject any
    candidate slot whose full service_duration window overlaps a busy minute.

    booked_slots: list of dicts with 'booking_time' and 'duration'.
    service_duration: duration in minutes of the service being booked.
    """
    fmt = "%H:%M"

    # Build set of all busy minutes from existing bookings
    busy_minutes: set[int] = set()
    for booked in booked_slots:
        start_dt = datetime.strptime(booked["booking_time"], fmt)
        start_min = start_dt.hour * 60 + start_dt.minute
        for m in range(start_min, start_min + booked["duration"]):
            busy_minutes.add(m)

    # A slot is free only if the entire service window has no busy minutes
    free = []
    for slot in all_slots:
        slot_dt = datetime.strptime(slot, fmt)
        slot_start = slot_dt.hour * 60 + slot_dt.minute
        slot_range = range(slot_start, slot_start + service_duration)
        if not any(m in busy_minutes for m in slot_range):
            free.append(slot)
    return free


def format_date_ru(date_str: str) -> str:
    """Formats YYYY-MM-DD to human-readable Russian format."""
    months = [
        "", "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря"
    ]
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{weekdays[d.weekday()]}, {d.day} {months[d.month]}"
