from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.job_seed_loader import load_job_seed_records


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a JSON or SQL job seed file into the JSON format expected by CareerMatch."
    )
    parser.add_argument("--input", required=True, help="Source file path. Supports .json and .sql")
    parser.add_argument("--output", required=True, help="Target JSON file path")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of jobs to export")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    records = load_job_seed_records(input_path, limit=args.limit)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Exported {len(records)} jobs to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
