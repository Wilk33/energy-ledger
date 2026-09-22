from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from zoneinfo import ZoneInfo


WARSAW=ZoneInfo("Europe/Warsaw")


class G13Zone(str, Enum):
	MORNING_PEAK="morning_peak"
	AFTERNOON_PEAK="afternoon_peak"
	OTHER="other"


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
	holidays={
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
		holidays.add(date(year, 12, 24))
	return holidays


def g13_zone(value: datetime) -> G13Zone:
	if value.tzinfo is None:
		raise ValueError("Timestamp must include a timezone")
	local=value.astimezone(WARSAW)
	if local.weekday() >= 5 or local.date() in polish_public_holidays(local.year):
		return G13Zone.OTHER
	minutes=local.hour*60+local.minute
	if 7*60 <= minutes < 13*60:
		return G13Zone.MORNING_PEAK
	if 4 <= local.month <= 9:
		if 19*60 <= minutes < 22*60:
			return G13Zone.AFTERNOON_PEAK
	elif 16*60 <= minutes < 21*60:
		return G13Zone.AFTERNOON_PEAK
	return G13Zone.OTHER


@dataclass(frozen=True)
class TariffRates:
	energy: dict[G13Zone, Decimal]
	distribution: dict[G13Zone, Decimal]
	common_variable: Decimal
	fixed_monthly: Decimal

	def __post_init__(self):
		for name,values in (("energy", self.energy), ("distribution", self.distribution)):
			if set(values) != set(G13Zone):
				raise ValueError(f"{name} must contain every G13 zone")
			if any(value < 0 for value in values.values()):
				raise ValueError(f"{name} cannot contain negative prices")
		if self.common_variable < 0 or self.fixed_monthly < 0:
			raise ValueError("Tariff prices cannot be negative")

	def variable_price(self, zone: G13Zone) -> Decimal:
		return self.energy[zone]+self.distribution[zone]+self.common_variable
