from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable


@dataclass
class TimeTuple:
    hours: int
    minutes: int
    seconds: int


def seconds_to_timetuple(seconds: int) -> TimeTuple:
    return TimeTuple(seconds // 3600, seconds // 60 % 60, seconds % 60)


def timedelta_to_full_str(td: timedelta) -> str:
    s = ""
    if td.days > 0:
        s += f"{td.days} day{s_(td.days)} "

    t = seconds_to_timetuple(td.seconds)
    if t.hours > 0:
        s += f"{t.hours} hour{s_(t.hours)} "
    if t.minutes > 0:
        s += f"{t.minutes} minute{s_(t.minutes)} "
    if t.seconds > 0:
        s += f"{t.seconds} second{s_(t.seconds)}"

    return s


def timedelta_to_short_str(td: timedelta) -> str:
    return " ".join(timedelta_to_full_str(td).split()[:2])


def timedelta_to_timestamp(td: timedelta, modifier: str = "F") -> str:
    return datetime_to_timestamp(datetime.now() + td, modifier)


def datetime_to_timestamp(dt: datetime, modifier: str = "F") -> str:
    return f"<t:{int(dt.timestamp())}:{modifier}>"


def ordinal_num(num: int) -> str:
    d = {1: "st", 2: "nd", 3: "rd"}
    return str(num) + d.get(num % 10, "th")


def get_next_score(current_score: int, scores: Iterable[int]) -> None | int:
    if current_score > max(scores):
        return None

    return min(filter(lambda x: current_score < x, scores))


def sep_num(num: int, sep: str = None):
    s = f"{num:,}"
    if sep is not None:
        s = s.replace(",", sep)
    return s


def s_(num: int):
    if not str(num).endswith("1"):
        return "s"
    return ""
