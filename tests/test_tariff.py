import unittest
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from energy_ledger.tariff import G13Zone, TariffRates, g13_zone


WARSAW=ZoneInfo("Europe/Warsaw")


class G13ZoneTests(unittest.TestCase):
	def test_summer_workday_boundaries(self):
		cases=[
			("2026-06-15T06:59:59", G13Zone.OTHER),
			("2026-06-15T07:00:00", G13Zone.MORNING_PEAK),
			("2026-06-15T12:59:59", G13Zone.MORNING_PEAK),
			("2026-06-15T13:00:00", G13Zone.OTHER),
			("2026-06-15T19:00:00", G13Zone.AFTERNOON_PEAK),
			("2026-06-15T22:00:00", G13Zone.OTHER),
		]
		for value,expected in cases:
			with self.subTest(value=value):
				self.assertEqual(g13_zone(datetime.fromisoformat(value).replace(tzinfo=WARSAW)), expected)

	def test_winter_workday_afternoon_peak(self):
		self.assertEqual(g13_zone(datetime(2026, 1, 15, 16, 0, tzinfo=WARSAW)), G13Zone.AFTERNOON_PEAK)
		self.assertEqual(g13_zone(datetime(2026, 1, 15, 21, 0, tzinfo=WARSAW)), G13Zone.OTHER)

	def test_weekend_and_public_holiday_are_other_zone(self):
		self.assertEqual(g13_zone(datetime(2026, 6, 14, 9, 0, tzinfo=WARSAW)), G13Zone.OTHER)
		self.assertEqual(g13_zone(datetime(2026, 12, 24, 9, 0, tzinfo=WARSAW)), G13Zone.OTHER)
		self.assertEqual(g13_zone(datetime(2026, 12, 25, 9, 0, tzinfo=WARSAW)), G13Zone.OTHER)
		self.assertEqual(g13_zone(datetime(2026, 4, 6, 9, 0, tzinfo=WARSAW)), G13Zone.OTHER)

	def test_christmas_eve_is_not_a_public_holiday_before_2025(self):
		self.assertEqual(g13_zone(datetime(2024, 12, 24, 9, 0, tzinfo=WARSAW)), G13Zone.MORNING_PEAK)

	def test_utc_timestamp_is_classified_after_warsaw_conversion(self):
		utc=ZoneInfo("UTC")
		self.assertEqual(g13_zone(datetime(2026, 6, 15, 5, 0, tzinfo=utc)), G13Zone.MORNING_PEAK)


class TariffRateTests(unittest.TestCase):
	def test_variable_price_combines_energy_distribution_and_common_fees(self):
		rates=TariffRates(
			energy={G13Zone.MORNING_PEAK: Decimal("0.50"), G13Zone.AFTERNOON_PEAK: Decimal("0.70"), G13Zone.OTHER: Decimal("0.30")},
			distribution={G13Zone.MORNING_PEAK: Decimal("0.20"), G13Zone.AFTERNOON_PEAK: Decimal("0.40"), G13Zone.OTHER: Decimal("0.05")},
			common_variable=Decimal("0.04"),
			fixed_monthly=Decimal("35.00"),
		)
		self.assertEqual(rates.variable_price(G13Zone.AFTERNOON_PEAK), Decimal("1.14"))


if __name__ == "__main__":
	unittest.main()
