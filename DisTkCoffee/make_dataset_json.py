#!/usr/bin/env python3
"""Create a PocketCoffea dataset JSON from custom NanoAOD ROOT files."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def list_root_files(path: str, redirector: str) -> list[str]:
    if path.startswith("root://"):
        return [path]
    if path.endswith(".root"):
        return [f"{redirector}/{path}" if path.startswith("/store/") else path]

    if path.startswith("/store/"):
        cmd = ["xrdfs", redirector.replace("root://", "").split("/")[0], "ls", "-R", path]
        result = subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE)
        return [
            f"{redirector}/{line.strip()}"
            for line in result.stdout.splitlines()
            if line.strip().endswith(".root")
        ]

    root_files = sorted(str(p) for p in Path(path).rglob("*.root"))
    return root_files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="ROOT file, local directory, or /store directory")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--dataset-name", default="DATA_Muon_Run2022F_CustomNanoAOD")
    parser.add_argument("--sample", default="DATA_Muon")
    parser.add_argument("--year", default="2022")
    parser.add_argument("--era", default="F")
    parser.add_argument("--primary-dataset", default="Muon")
    parser.add_argument("--redirector", default="root://cms-xrd-global.cern.ch/")
    parser.add_argument("--nevents", type=int, default=0)
    args = parser.parse_args()

    files = list_root_files(args.input, args.redirector.rstrip("/"))
    if not files:
        sys.exit(f"No ROOT files found under {args.input}")

    payload = {
        args.dataset_name: {
            "files": files,
            "metadata": {
                "sample": args.sample,
                "year": args.year,
                "isMC": "False",
                "era": args.era,
                "primaryDataset": args.primary_dataset,
                "nano_version": 15,
                "nevents": args.nevents,
                "source": args.input,
            },
        }
    }

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"Wrote {out} with {len(files)} files")


if __name__ == "__main__":
    main()
