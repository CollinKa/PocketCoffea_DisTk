#!/usr/bin/env python3
"""Export the DisTkMuonPveto PocketCoffea output to readable JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from coffea.util import load


def to_jsonable(value: Any) -> Any:
    """Convert coffea/awkward/numpy accumulator objects into JSON values."""
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return to_jsonable(value.value)
    if hasattr(value, "tolist"):
        return to_jsonable(value.tolist())
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("coffea_output", help="Path to output_all.coffea")
    parser.add_argument(
        "--output",
        default=None,
        help="JSON output path. Defaults to pveto_summary.json beside the coffea file.",
    )
    args = parser.parse_args()

    coffea_path = Path(args.coffea_output)
    output_path = Path(args.output) if args.output else coffea_path.with_name("pveto_summary.json")

    payload = load(coffea_path)
    summary = {
        "source": str(coffea_path),
        "cutflow": to_jsonable(payload.get("cutflow", {})),
        "pveto": to_jsonable(payload.get("pveto", {})),
        "processing_metadata": to_jsonable(payload.get("processing_metadata", {})),
        "datasets_metadata": to_jsonable(payload.get("datasets_metadata", {})),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
