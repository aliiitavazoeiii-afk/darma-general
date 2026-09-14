from datetime import date

import jdatetime


PERSIAN_MONTHS = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def format_jalali(value):
    if not value:
        return ""
    j = jdatetime.date.fromgregorian(date=value)
    return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"


def parse_jalali_date(text, default=None):
    raw = str(text or "").strip().replace("-", "/")
    if not raw:
        return default or date.today()
    try:
        y, m, d = [int(x) for x in raw.split("/")]
        return jdatetime.date(y, m, d).togregorian()
    except Exception as exc:
        raise ValueError("تاریخ شمسی معتبر نیست. نمونه: 1405/06/23") from exc


def jalali_month_bounds(value=None):
    value = value or date.today()
    j = jdatetime.date.fromgregorian(date=value)
    start = jdatetime.date(j.year, j.month, 1).togregorian()
    if j.month == 12:
        next_start = jdatetime.date(j.year + 1, 1, 1).togregorian()
    else:
        next_start = jdatetime.date(j.year, j.month + 1, 1).togregorian()
    return start, next_start, f"{PERSIAN_MONTHS[j.month - 1]} {j.year}"


def _jalali_month_days(jy, jm):
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    try:
        jdatetime.date(jy, 12, 30)
        return 30
    except ValueError:
        return 29


def month_calendar(jy=None, jm=None):
    today_j = jdatetime.date.fromgregorian(date=date.today())
    jy = int(jy or today_j.year)
    jm = int(jm or today_j.month)
    if jm < 1 or jm > 12:
        raise ValueError("ماه نامعتبر است.")
    days_count = _jalali_month_days(jy, jm)
    first = jdatetime.date(jy, jm, 1)
    # Python weekday: Mon=0. Persian week starts Saturday.
    offset = (first.togregorian().weekday() + 2) % 7
    cells = [None] * offset + list(range(1, days_count + 1))
    while len(cells) % 7:
        cells.append(None)
    weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]
    if jm == 1:
        py, pm = jy - 1, 12
    else:
        py, pm = jy, jm - 1
    if jm == 12:
        ny, nm = jy + 1, 1
    else:
        ny, nm = jy, jm + 1
    return {
        "jy": jy,
        "jm": jm,
        "month_name": PERSIAN_MONTHS[jm - 1],
        "weeks": weeks,
        "weekdays": ["ش", "ی", "د", "س", "چ", "پ", "ج"],
        "prev_y": py,
        "prev_m": pm,
        "next_y": ny,
        "next_m": nm,
    }
