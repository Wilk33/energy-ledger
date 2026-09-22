import unittest

from energy_ledger.supervisor import reset_correction_options


class SupervisorOptionsTests(unittest.TestCase):
	def test_reset_payload_preserves_all_options_and_only_zeros_correction(self):
		options={"discount_percent": 80, "balance_correction_kwh": -12.5, "nested": {"value": 1}}
		payload=reset_correction_options(options)
		self.assertEqual(payload["options"]["balance_correction_kwh"], 0)
		self.assertEqual(payload["options"]["discount_percent"], 80)
		self.assertEqual(payload["options"]["nested"], {"value": 1})
		self.assertEqual(options["balance_correction_kwh"], -12.5)


if __name__ == "__main__":
	unittest.main()
