"""Inspect the live schemas of the Phase 1 source datasets.

Run:
    python scripts/inspect_sources.py

This script deliberately does not assume field names beyond each dataset ID.
Its purpose is to freeze the current public schema before writing the
matching pipeline.
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sweepnyc.config import DATASETS  # noqa: E402
from sweepnyc.socrata import field_names, metadata  # noqa: E402


def main() -> None:
    for label, dataset_id in DATASETS.items():
        meta = metadata(dataset_id)
        print(f"\n{label.upper()} — {dataset_id}")
        print(meta.get("name", "(no title)"))
        print("-" * 72)
        for field in field_names(dataset_id):
            print(field)


if __name__ == "__main__":
    main()
