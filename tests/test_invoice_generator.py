import unittest
from decimal import Decimal

from invoice_generator import TimeEntry, infer_invoice_meta, money_fmt, parse_date, quantize_money


class InvoiceGeneratorTests(unittest.TestCase):
    def test_quantize_money_rounds_half_up(self):
        self.assertEqual(quantize_money(Decimal("12.345")), Decimal("12.35"))

    def test_money_format(self):
        self.assertEqual(money_fmt(Decimal("1234.5"), "$"), "$1,234.50")

    def test_infer_invoice_meta_uses_latest_entry_date(self):
        entries = [
            TimeEntry(parse_date("2026-01-01"), "A", "x", Decimal("1"), Decimal("100")),
            TimeEntry(parse_date("2026-01-05"), "B", "y", Decimal("2"), Decimal("200")),
        ]
        meta = infer_invoice_meta(entries, "INV-1", due_days=10)
        self.assertEqual(meta.issue_date.isoformat(), "2026-01-05")
        self.assertEqual(meta.due_date.isoformat(), "2026-01-15")


if __name__ == "__main__":
    unittest.main()
