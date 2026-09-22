import tempfile
import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from energy_ledger.correction import CorrectionCoordinator
from energy_ledger.ledger import EnergyLedger
from energy_ledger.storage import JsonStateStore
from energy_ledger.tariff import G13Zone, TariffRates


def rates():
	zero={zone: Decimal("0") for zone in G13Zone}
	return TariffRates(energy=zero, distribution=zero, common_variable=Decimal("0"), fixed_monthly=Decimal("0"))


class CorrectionTests(unittest.TestCase):
	def test_restart_after_failed_reset_does_not_apply_correction_twice(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory) / "state.json")
			ledger=EnergyLedger(discount=Decimal("0.8"), rates=rates(), now=datetime(2026, 9, 1, tzinfo=ZoneInfo("Europe/Warsaw")))
			coordinator=CorrectionCoordinator(store)
			with self.assertRaises(RuntimeError):
				coordinator.consume(Decimal("10"), ledger, lambda: (_ for _ in ()).throw(RuntimeError("offline")))
			self.assertEqual(ledger.state.balance_kwh, Decimal("10"))

			restored=EnergyLedger.from_dict(store.load()["ledger"], rates())
			reset_calls=[]
			CorrectionCoordinator(store).consume(Decimal("10"), restored, lambda: reset_calls.append(True))
			self.assertEqual(restored.state.balance_kwh, Decimal("10"))
			self.assertEqual(reset_calls, [True])

	def test_same_value_can_be_used_again_after_zero_was_observed(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory) / "state.json")
			ledger=EnergyLedger(discount=Decimal("0.8"), rates=rates(), now=datetime(2026, 9, 1, tzinfo=ZoneInfo("Europe/Warsaw")))
			coordinator=CorrectionCoordinator(store)
			coordinator.consume(Decimal("10"), ledger, lambda: None)
			coordinator.consume(Decimal("0"), ledger, lambda: None)
			coordinator.consume(Decimal("10"), ledger, lambda: None)
			self.assertEqual(ledger.state.balance_kwh, Decimal("20"))

	def test_successful_reset_completes_pending_correction(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory) / "state.json")
			ledger=EnergyLedger(discount=Decimal("0.8"), rates=rates(), now=datetime(2026, 9, 1, tzinfo=ZoneInfo("Europe/Warsaw")))
			CorrectionCoordinator(store).consume(Decimal("10"), ledger, lambda: None)
			self.assertNotIn("correction_awaiting_reset", store.load())

	def test_state_store_rejects_corrupt_json_without_overwriting_it(self):
		with tempfile.TemporaryDirectory() as directory:
			path=Path(directory) / "state.json"
			path.write_text("not-json", encoding="utf-8")
			with self.assertRaises(ValueError):
				JsonStateStore(path).load()
			self.assertEqual(path.read_text(encoding="utf-8"), "not-json")


class AsyncCorrectionTests(unittest.IsolatedAsyncioTestCase):
	async def test_async_reset_failure_is_retried_without_reapplying(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory) / "state.json")
			ledger=EnergyLedger(discount=Decimal("0.8"), rates=rates(), now=datetime(2026, 9, 1, tzinfo=ZoneInfo("Europe/Warsaw")))
			coordinator=CorrectionCoordinator(store)
			async def fail():
				raise RuntimeError("offline")
			with self.assertRaises(RuntimeError):
				await coordinator.consume_async(Decimal("7"), ledger, fail)
			restored=EnergyLedger.from_dict(store.load()["ledger"], rates())
			calls=[]
			async def succeed():
				calls.append(True)
			await CorrectionCoordinator(store).consume_async(Decimal("7"), restored, succeed)
			self.assertEqual(restored.state.balance_kwh, Decimal("7"))
			self.assertEqual(calls, [True])


if __name__ == "__main__":
	unittest.main()
