#!/usr/bin/env python3
"""Generate invoice PDFs from a timesheet and JSON template (stdlib only)."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class TimeEntry:
    date: dt.date
    project: str
    description: str
    hours: Decimal
    hourly_rate: Decimal

    @property
    def amount(self) -> Decimal:
        return quantize_money(self.hours * self.hourly_rate)


@dataclass(frozen=True)
class InvoiceMeta:
    invoice_number: str
    issue_date: dt.date
    due_date: dt.date


@dataclass(frozen=True)
class InvoiceTemplate:
    from_name: str
    from_email: str
    from_address_lines: list[str]
    bill_to_name: str
    bill_to_address_lines: list[str]
    notes: str
    currency_symbol: str


@dataclass(frozen=True)
class Invoice:
    meta: InvoiceMeta
    template: InvoiceTemplate
    entries: list[TimeEntry]

    @property
    def subtotal(self) -> Decimal:
        return quantize_money(sum((entry.amount for entry in self.entries), Decimal("0")))


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def parse_date(raw: str) -> dt.date:
    return dt.datetime.strptime(raw, "%Y-%m-%d").date()


def load_timesheet(path: Path) -> list[TimeEntry]:
    entries: list[TimeEntry] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"date", "project", "description", "hours", "hourly_rate"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(
                "Timesheet must include columns: date, project, description, hours, hourly_rate"
            )

        for row in reader:
            entries.append(
                TimeEntry(
                    date=parse_date(row["date"]),
                    project=row["project"].strip(),
                    description=row["description"].strip(),
                    hours=Decimal(row["hours"]),
                    hourly_rate=Decimal(row["hourly_rate"]),
                )
            )

    if not entries:
        raise ValueError("Timesheet is empty.")

    return sorted(entries, key=lambda item: item.date)


def load_template(path: Path) -> InvoiceTemplate:
    data = json.loads(path.read_text(encoding="utf-8"))
    return InvoiceTemplate(
        from_name=data["from"]["name"],
        from_email=data["from"]["email"],
        from_address_lines=data["from"].get("address_lines", []),
        bill_to_name=data["bill_to"]["name"],
        bill_to_address_lines=data["bill_to"].get("address_lines", []),
        notes=data.get("notes", ""),
        currency_symbol=data.get("currency_symbol", "$"),
    )


def infer_invoice_meta(entries: Iterable[TimeEntry], invoice_number: str, due_days: int) -> InvoiceMeta:
    entry_dates = [entry.date for entry in entries]
    issue_date = max(entry_dates)
    due_date = issue_date + dt.timedelta(days=due_days)
    return InvoiceMeta(invoice_number=invoice_number, issue_date=issue_date, due_date=due_date)


def money_fmt(value: Decimal, symbol: str) -> str:
    return f"{symbol}{value:,.2f}"


def pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_invoice_lines(invoice: Invoice) -> list[str]:
    t = invoice.template
    lines = [
        f"INVOICE #{invoice.meta.invoice_number}",
        "",
        "From:",
        t.from_name,
        t.from_email,
        *t.from_address_lines,
        "",
        "Bill To:",
        t.bill_to_name,
        *t.bill_to_address_lines,
        "",
        f"Issue Date: {invoice.meta.issue_date.isoformat()}",
        f"Due Date: {invoice.meta.due_date.isoformat()}",
        "",
        "Date       | Project      | Description                  | Hours | Rate     | Amount",
        "-----------+--------------+------------------------------+-------+----------+----------",
    ]

    for entry in invoice.entries:
        lines.append(
            f"{entry.date.isoformat():10} | {entry.project[:12]:12} | {entry.description[:28]:28} |"
            f" {str(entry.hours):>5} | {money_fmt(entry.hourly_rate, t.currency_symbol):>8} |"
            f" {money_fmt(entry.amount, t.currency_symbol):>8}"
        )

    lines.extend(["", f"Subtotal: {money_fmt(invoice.subtotal, t.currency_symbol)}"])
    if t.notes:
        lines.extend(["", "Notes:", t.notes])
    return lines


def create_single_page_pdf(lines: list[str], out_path: Path) -> None:
    content_commands = ["BT", "/F1 10 Tf", "1 0 0 1 40 760 Tm", "14 TL"]
    for line in lines:
        content_commands.append(f"({pdf_escape(line)}) Tj")
        content_commands.append("T*")
    content_commands.append("ET")
    content = "\n".join(content_commands).encode("latin-1", errors="replace")

    objects = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 4 0 R >> >> >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(f"<< /Length {len(content)} >>\nstream\n".encode("ascii") + content + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_start = len(pdf)
    pdf.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "ascii"
        )
    )

    out_path.write_bytes(pdf)


def render_invoice(invoice: Invoice, out_path: Path) -> None:
    lines = build_invoice_lines(invoice)
    create_single_page_pdf(lines, out_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create invoice PDF from a timesheet CSV and JSON template")
    parser.add_argument("--timesheet", required=True, type=Path, help="Path to input CSV timesheet")
    parser.add_argument("--template", required=True, type=Path, help="Path to JSON invoice template")
    parser.add_argument("--out", required=True, type=Path, help="Path to output PDF file")
    parser.add_argument("--invoice-number", required=True, help="Invoice number")
    parser.add_argument("--due-days", type=int, default=14, help="Days from issue date until due date")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    entries = load_timesheet(args.timesheet)
    template = load_template(args.template)
    meta = infer_invoice_meta(entries, args.invoice_number, args.due_days)
    invoice = Invoice(meta=meta, template=template, entries=entries)
    render_invoice(invoice, args.out)
    print(f"Invoice generated: {args.out}")


if __name__ == "__main__":
    main()
