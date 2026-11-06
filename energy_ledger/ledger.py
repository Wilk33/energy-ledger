from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any

from .tariff import G13Zone, TariffRates, WARSAW, g13_zone


ZERO=Decimal("0")
MONEY=Decimal("0.01")


def _money(value: Decimal) -> Decimal:
	return value.quantize(MONEY, rounding=ROUND_HALF_UP)


class MeterKind(str, Enum):
	IMPORT="import"
	EXPORT="export"


@dataclass
class DeficitLot:
	zone: G13Zone
	kwh: Decimal

	def to_dict(self) -> dict[str, str]:
		return {"zone": self.zone.value, "kwh": str(self.kwh)}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "DeficitLot":
		return cls(G13Zone(value["zone"]), Decimal(value["kwh"]))


@dataclass
class ClosedPeriod:
	period: str
	shortage_kwh: Decimal
	variable_cost_pln: Decimal
	fixed_cost_pln: Decimal
	import_kwh: Decimal
	export_kwh: Decimal

	def to_dict(self) -> dict[str, str]:
		return {
			"period": self.period,
			"shortage_kwh": str(self.shortage_kwh),
			"variable_cost_pln": str(self.variable_cost_pln),
			"fixed_cost_pln": str(self.fixed_cost_pln),
			"import_kwh": str(self.import_kwh),
			"export_kwh": str(self.export_kwh),
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "ClosedPeriod":
		return cls(
			period=value["period"],
			shortage_kwh=Decimal(value["shortage_kwh"]),
			variable_cost_pln=Decimal(value["variable_cost_pln"]),
			fixed_cost_pln=Decimal(value["fixed_cost_pln"]),
			import_kwh=Decimal(value["import_kwh"]),
			export_kwh=Decimal(value["export_kwh"]),
		)


@dataclass
class LedgerState:
	current_period: str
	balance_kwh: Decimal=ZERO
	baselines: dict[str, Decimal]=field(default_factory=dict)
	last_event_at: dict[str, str]=field(default_factory=dict)
	import_month_kwh: Decimal=ZERO
	export_month_kwh: Decimal=ZERO
	imports_by_zone: dict[G13Zone, Decimal]=field(default_factory=lambda: {zone: ZERO for zone in G13Zone})
	deficit_lots: list[DeficitLot]=field(default_factory=list)
	closed_periods: list[ClosedPeriod]=field(default_factory=list)
	exports_by_zone: dict[G13Zone, Decimal] | None=field(default_factory=lambda: {zone: ZERO for zone in G13Zone})

	@property
	def uncovered_kwh(self) -> Decimal:
		return sum((lot.kwh for lot in self.deficit_lots), ZERO)

	def to_dict(self) -> dict[str, Any]:
		return {
			"current_period": self.current_period,
			"balance_kwh": str(self.balance_kwh),
			"baselines": {key: str(value) for key,value in self.baselines.items()},
			"last_event_at": dict(self.last_event_at),
			"import_month_kwh": str(self.import_month_kwh),
			"export_month_kwh": str(self.export_month_kwh),
			"imports_by_zone": {key.value: str(value) for key,value in self.imports_by_zone.items()},
			"deficit_lots": [lot.to_dict() for lot in self.deficit_lots],
			"closed_periods": [period.to_dict() for period in self.closed_periods],
			"exports_by_zone": None if self.exports_by_zone is None else {zone.value: str(kwh) for zone,kwh in self.exports_by_zone.items()},
		}

	@classmethod
	def from_dict(cls, value: dict[str, Any]) -> "LedgerState":
		return cls(
			current_period=value["current_period"],
			balance_kwh=Decimal(value.get("balance_kwh", "0")),
			baselines={key: Decimal(item) for key,item in value.get("baselines", {}).items()},
			last_event_at=dict(value.get("last_event_at", {})),
			import_month_kwh=Decimal(value.get("import_month_kwh", "0")),
			export_month_kwh=Decimal(value.get("export_month_kwh", "0")),
			imports_by_zone={zone: Decimal(value.get("imports_by_zone", {}).get(zone.value, "0")) for zone in G13Zone},
			deficit_lots=[DeficitLot.from_dict(item) for item in value.get("deficit_lots", [])],
			closed_periods=[ClosedPeriod.from_dict(item) for item in value.get("closed_periods", [])],
			exports_by_zone=None if value.get("exports_by_zone") is None else {zone: Decimal(value["exports_by_zone"][zone.value]) for zone in G13Zone},
		)


def _period(value: datetime) -> str:
	return value.astimezone(WARSAW).strftime("%Y-%m")


def _next_period(period: str) -> str:
	year,month=(int(part) for part in period.split("-"))
	if month == 12:
		return f"{year+1:04d}-01"
	return f"{year:04d}-{month+1:02d}"


class EnergyLedger:
	def __init__(self, discount: Decimal, rates: TariffRates, now: datetime | None=None, state: LedgerState | None=None):
		if discount not in (Decimal("0.7"), Decimal("0.8")):
			raise ValueError("Discount must be 0.7 or 0.8")
		self.discount=discount
		self.rates=rates
		current=now or datetime.now(tz=WARSAW)
		self.state=state or LedgerState(current_period=_period(current))

	@property
	def _deficit_by_zone(self) -> dict[G13Zone, Decimal]:
		values={zone: ZERO for zone in G13Zone}
		for lot in self.state.deficit_lots:
			values[lot.zone]+=lot.kwh
		return values

	def _settlement_lines(self) -> list[Decimal]:
		lines=[]
		for zone,kwh in self._deficit_by_zone.items():
			if kwh <= 0:
				continue
			lines.extend((kwh*self.rates.energy[zone], kwh*self.rates.distribution[zone], kwh*self.rates.quality))
		return lines

	def _full_import_lines(self) -> list[Decimal]:
		lines=[]
		for zone,kwh in self.state.imports_by_zone.items():
			if kwh <= 0:
				continue
			lines.extend(kwh*rate for rate in self.rates.import_fees.values())
		return lines

	@staticmethod
	def _net(lines: list[Decimal]) -> Decimal:
		return sum((_money(line) for line in lines), ZERO)

	def _vat(self, lines: list[Decimal]) -> Decimal:
		return sum((_money(_money(line)*self.rates.vat_rate) for line in lines), ZERO)

	@property
	def settlement_cost_net(self) -> Decimal:
		return self._net(self._settlement_lines())

	@property
	def full_import_fees_net(self) -> Decimal:
		return self._net(self._full_import_lines())

	@property
	def full_import_fees_vat(self) -> Decimal:
		return self._vat(self._full_import_lines())

	@property
	def full_import_fees_gross(self) -> Decimal:
		return self.full_import_fees_net+self.full_import_fees_vat

	@property
	def variable_cost_net(self) -> Decimal:
		return self.settlement_cost_net+self.full_import_fees_net

	@property
	def variable_vat(self) -> Decimal:
		return self._vat(self._settlement_lines()+self._full_import_lines())

	@property
	def variable_cost_gross(self) -> Decimal:
		return self.variable_cost_net+self.variable_vat

	@property
	def fixed_cost_net(self) -> Decimal:
		return _money(self.rates.fixed_monthly)

	@property
	def fixed_vat(self) -> Decimal:
		return _money(self.rates.fixed_monthly*self.rates.vat_rate)

	@property
	def fixed_cost_gross(self) -> Decimal:
		return self.fixed_cost_net+self.fixed_vat

	@property
	def estimated_bill_net(self) -> Decimal:
		return self.variable_cost_net+self.fixed_cost_net

	@property
	def estimated_vat(self) -> Decimal:
		return self.variable_vat+self.fixed_vat

	@property
	def estimated_bill_gross(self) -> Decimal:
		return self.estimated_bill_net+self.estimated_vat

	@property
	def variable_cost(self) -> Decimal:
		return self.variable_cost_gross

	@property
	def estimated_bill(self) -> Decimal:
		return self.estimated_bill_gross

	def process_total(self, kind: MeterKind, raw_value: str, occurred_at: datetime) -> bool:
		if occurred_at.tzinfo is None:
			raise ValueError("Timestamp must include a timezone")
		try:
			value=Decimal(str(raw_value))
		except (InvalidOperation, ValueError):
			return False
		if not value.is_finite() or value < 0:
			return False
		key=kind.value
		last=self.state.last_event_at.get(key)
		utc_time=occurred_at.astimezone(timezone.utc).isoformat()
		if last is not None and utc_time <= last:
			return False
		self.advance_to(occurred_at)
		previous=self.state.baselines.get(key)
		self.state.baselines[key]=value
		self.state.last_event_at[key]=utc_time
		if previous is None or value < previous:
			return True
		delta=value-previous
		if delta == 0:
			return True
		if kind is MeterKind.IMPORT:
			self._apply_import(delta, g13_zone(occurred_at))
		else:
			self._apply_export(delta, g13_zone(occurred_at))
		return True

	def _apply_import(self, delta: Decimal, zone: G13Zone):
		available=max(self.state.balance_kwh, ZERO)
		uncovered=max(delta-available, ZERO)
		self.state.balance_kwh-=delta
		self.state.import_month_kwh+=delta
		self.state.imports_by_zone[zone]+=delta
		if uncovered > 0:
			self.state.deficit_lots.append(DeficitLot(zone, uncovered))
		self.reconcile_zones()

	def _apply_export(self, delta: Decimal, zone: G13Zone=G13Zone.OTHER):
		credit=delta*self.discount
		self.state.balance_kwh+=credit
		self.state.export_month_kwh+=delta
		self._cover_deficit(credit)
		if self.state.exports_by_zone is not None:
			self.state.exports_by_zone[zone]+=delta
		self.reconcile_zones()

	def reconcile_zones(self):
		if self.state.exports_by_zone is None:
			return
		# Recompute the whole month: credits first cover their own tariff zone.
		net={zone:self.state.imports_by_zone[zone]-self.state.exports_by_zone[zone]*self.discount for zone in G13Zone}
		opening=self.state.balance_kwh+self.state.import_month_kwh-self.state.export_month_kwh*self.discount
		if opening < 0:
			net[G13Zone.OTHER]-=opening
		credit=max(opening,ZERO)+sum((max(-value,ZERO) for value in net.values()),ZERO)
		deficits={zone:max(value,ZERO) for zone,value in net.items()}
		for zone in sorted(G13Zone,key=lambda item:self.rates.distribution[item],reverse=True):
			covered=min(credit,deficits[zone])
			deficits[zone]-=covered
			credit-=covered
		self.state.deficit_lots=[DeficitLot(zone,kwh) for zone,kwh in deficits.items() if kwh > 0]

	def _cover_deficit(self, credit: Decimal):
		remaining=credit
		while remaining > 0 and self.state.deficit_lots:
			lot=self.state.deficit_lots[0]
			covered=min(lot.kwh, remaining)
			lot.kwh-=covered
			remaining-=covered
			if lot.kwh == 0:
				self.state.deficit_lots.pop(0)

	def apply_correction(self, correction: Decimal, negative_zone: G13Zone=G13Zone.OTHER):
		if not correction.is_finite():
			raise ValueError("Correction must be finite")
		deficit_before=max(-self.state.balance_kwh, ZERO)
		self.state.balance_kwh+=correction
		if correction > 0:
			self._cover_deficit(correction)
		elif correction < 0:
			new_deficit=max(-self.state.balance_kwh, ZERO)-deficit_before
			if new_deficit > 0:
				self.state.deficit_lots.append(DeficitLot(negative_zone, new_deficit))
		self.reconcile_zones()

	def advance_to(self, value: datetime):
		target=_period(value)
		while self.state.current_period < target:
			self._close_current_period()

	def _close_current_period(self):
		shortage=max(-self.state.balance_kwh, ZERO)
		self.state.closed_periods.append(ClosedPeriod(
			period=self.state.current_period,
			shortage_kwh=shortage,
			variable_cost_pln=self.variable_cost,
			fixed_cost_pln=self.fixed_cost_gross,
			import_kwh=self.state.import_month_kwh,
			export_kwh=self.state.export_month_kwh,
		))
		if self.state.balance_kwh < 0:
			self.state.balance_kwh=ZERO
		self.state.current_period=_next_period(self.state.current_period)
		self.state.import_month_kwh=ZERO
		self.state.export_month_kwh=ZERO
		self.state.imports_by_zone={zone: ZERO for zone in G13Zone}
		self.state.deficit_lots=[]
		self.state.exports_by_zone={zone: ZERO for zone in G13Zone}

	def to_dict(self) -> dict[str, Any]:
		return {"discount": str(self.discount), "state": self.state.to_dict()}

	@classmethod
	def from_dict(cls, value: dict[str, Any], rates: TariffRates) -> "EnergyLedger":
		return cls(discount=Decimal(value["discount"]), rates=rates, state=LedgerState.from_dict(value["state"]))
