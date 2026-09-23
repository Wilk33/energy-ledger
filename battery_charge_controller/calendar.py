from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum

from .config import AppConfig, ClockTime


class Season(str, Enum):
	SUMMER="summer"
	WINTER="winter"


class Segment(str, Enum):
	NIGHT="night"
	DAY="day"


@dataclass(frozen=True)
class ChargeWindow:
	segment: Segment
	season: Season
	start: datetime
	end: datetime
	execution_key: str

	def contains(self, value: datetime) -> bool:
		utc=value.astimezone(timezone.utc)
		return self.start.astimezone(timezone.utc) <= utc < self.end.astimezone(timezone.utc)


def _easter_sunday(year: int) -> date:
	a=year%19
	b=year//100
	c=year%100
	d=b//4
	e=b%4
	f=(b+8)//25
	g=(b-f+1)//3
	h=(19*a+b-d-g+15)%30
	i=c//4
	k=c%4
	l=(32+2*e+2*i-h-k)%7
	m=(a+11*h+22*l)//451
	month=(h+l-7*m+114)//31
	day=((h+l-7*m+114)%31)+1
	return date(year, month, day)


def polish_public_holidays(year: int) -> set[date]:
	easter=_easter_sunday(year)
	result={
		date(year, 1, 1),
		date(year, 1, 6),
		easter,
		easter+timedelta(days=1),
		date(year, 5, 1),
		date(year, 5, 3),
		easter+timedelta(days=49),
		easter+timedelta(days=60),
		date(year, 8, 15),
		date(year, 11, 1),
		date(year, 11, 11),
		date(year, 12, 25),
		date(year, 12, 26),
	}
	if year >= 2025:
		result.add(date(year, 12, 24))
	return result


def is_workday(value: date) -> bool:
	return value.weekday() < 5 and value not in polish_public_holidays(value.year)


def season_for(value: date, config: AppConfig) -> Season:
	marker=(value.month, value.day)
	start=(config.summer_start.month, config.summer_start.day)
	end=(config.winter_start.month, config.winter_start.day)
	return Season.SUMMER if start <= marker < end else Season.WINTER


def _at(day: date, clock: ClockTime, config: AppConfig) -> datetime:
	return datetime.combine(day, time(clock.hour, clock.minute), config.timezone)


def window_for(value: datetime, segment: Segment, config: AppConfig) -> ChargeWindow:
	if value.tzinfo is None:
		raise ValueError("Timestamp must include a timezone")
	local=value.astimezone(config.timezone)
	season=season_for(local.date(), config)
	if segment is Segment.DAY:
		start_clock=config.summer_day_start if season is Season.SUMMER else config.winter_day_start
		end_clock=config.summer_day_end if season is Season.SUMMER else config.winter_day_end
		start=_at(local.date(), start_clock, config)
		end=_at(local.date(), end_clock, config)
		return ChargeWindow(segment, season, start, end, f"day:{local.date().isoformat()}")
	minutes=local.hour*60+local.minute
	if minutes < config.night_end.minutes:
		end_day=local.date()
		start_day=end_day-timedelta(days=1)
	else:
		start_day=local.date()
		end_day=start_day+timedelta(days=1)
	start=_at(start_day, config.night_start, config)
	end=_at(end_day, config.night_end, config)
	return ChargeWindow(segment, season_for(end_day, config), start, end, f"night:{end_day.isoformat()}")
