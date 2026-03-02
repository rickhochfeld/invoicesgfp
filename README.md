# Invoice Generator

Simple CLI program that creates invoice PDFs from timesheet rows using a reusable JSON template.

## Input formats

### Timesheet CSV columns
Required columns:
- `date` (format: `YYYY-MM-DD`)
- `project`
- `description`
- `hours`
- `hourly_rate`

### Template JSON format
See `sample_template.json` for a ready-to-use template.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```bash
python3 invoice_generator.py \
  --timesheet sample_timesheet.csv \
  --template sample_template.json \
  --out invoice-0001.pdf \
  --invoice-number 0001 \
  --due-days 14
```

## Output

The script produces a PDF invoice containing:
- Sender and billing details
- Invoice metadata (number, issue date, due date)
- Line-item table based on timesheet entries
- Subtotal and optional notes
