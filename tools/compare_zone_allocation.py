"""Offline sensitivity experiment, not a replacement for operator meter data."""
import csv
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from energy_ledger.tariff import g13_zone, G13Zone, WARSAW
from energy_ledger.catalog import load_catalog, select_tariff
from energy_ledger.ledger import EnergyLedger
from dataclasses import replace


def compare(path):
	rates=select_tariff(load_catalog(Path(__file__).resolve().parents[1]/'energy_ledger/data/tauron-g13.json'),datetime(2026,10,1).date()).rates
	rates=replace(rates,fixed_monthly=rates.fixed_monthly+D('24.05'))
	ledgers={mode:EnergyLedger(D('.8'),rates,now=datetime(2026,10,1,tzinfo=WARSAW)) for mode in ('endpoint','linear_short')}
	previous={}
	counts={'split_events':0,'split_kwh':D('0'),'long_crossings':0}
	entities={'sensor.energy_ledger_import_w_miesiacu':'import','sensor.energy_ledger_eksport_w_miesiacu':'export'}
	with open(path,encoding='utf-8-sig',newline='') as stream:
		rows=sorted(csv.DictReader(stream),key=lambda row:row['last_changed'])
	for row in rows:
		kind=entities.get(row['entity_id'])
		if kind is None:
			continue
		try:
			value=D(row['state'])
		except Exception:
			continue
		if not value.is_finite():
			continue
		now=datetime.fromisoformat(row['last_changed'].replace('Z','+00:00')).astimezone(timezone.utc)
		if now.astimezone(WARSAW).strftime('%Y-%m') != '2026-10':
			continue
		if kind not in previous:
			if value == 0:
				previous[kind]=(now,value)
			continue
		start,old=previous[kind]
		if value == old:
			continue
		previous[kind]=(now,value)
		delta=value-old
		if delta < 0:
			raise ValueError('Unexpected reset after month initialization')
		duration=(now-start).total_seconds()
		parts={g13_zone(now):delta}
		if g13_zone(start) != g13_zone(now):
			if 0 < duration <= 1800:
				counts['split_events']+=1
				counts['split_kwh']+=delta
				parts={zone:D('0') for zone in G13Zone}
				cursor=start
				remaining=delta
				while cursor < now:
					end=min(now,cursor.replace(second=0,microsecond=0)+timedelta(minutes=1))
					amount=remaining if end == now else delta*D(str((end-cursor).total_seconds()))/D(str(duration))
					parts[g13_zone(cursor)]+=amount
					remaining-=amount
					cursor=end
			else:
				counts['long_crossings']+=1
		for mode,ledger in ledgers.items():
			allocation=parts if mode == 'linear_short' else {g13_zone(now):delta}
			for zone,amount in allocation.items():
				if kind == 'import':
					ledger._apply_import(amount,zone)
				else:
					ledger._apply_export(amount,zone)
	print('Experiment: uniform energy between value changes, max 30 minutes; October 2026 only.')
	print(counts)
	baseline=ledgers['endpoint'].state
	for mode,ledger in ledgers.items():
		assert abs(ledger.state.import_month_kwh-baseline.import_month_kwh) < D('0.000000001')
		assert abs(ledger.state.export_month_kwh-baseline.export_month_kwh) < D('0.000000001')
		print(mode,'import',ledger.state.imports_by_zone,'export',ledger.state.exports_by_zone,'bill',ledger.estimated_bill_gross)


if __name__ == '__main__':
	compare(sys.argv[1])
