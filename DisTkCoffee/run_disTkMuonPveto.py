#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import uproot

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from disTkMuonPveto_core import (
    empty_counts,
    input_branches_for_available,
    missing_branch_message,
    missing_required_for_available,
    make_payload,
    configure_jet_veto,
    configure_fiducial_maps,
    configure_missing_hits,
    default_fiducial_map_paths,
    JET_VETO_CONFIGS,
    normalize_layers,
    ERA_TO_MISSING_HITS_PERIOD,
    MISSING_HITS_CORRECTIONS,
    process_arrays,
)


def parse_inputs(items: Iterable[str]) -> list[str]:
    files = []
    for item in items:
        if any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    return files


def run_file_set(files: list[str], tree: str, layers: list[str], chunk_size: str):
    all_results = {
        layer: {"cutflow": {}, "counts": empty_counts()}
        for layer in layers
    }

    for filename in files:
        with uproot.open(f"{filename}:{tree}") as root_tree:
            read_branches = input_branches_for_available(set(root_tree.keys()))
        for arrays in uproot.iterate(
            f"{filename}:{tree}",
            read_branches,
            step_size=chunk_size,
            library="ak",
        ):
            for layer in layers:
                result = process_arrays(arrays, layer)
                for name, value in result["cutflow"].items():
                    all_results[layer]["cutflow"][name] = (
                        all_results[layer]["cutflow"].get(name, 0) + int(value)
                    )
                for name, value in result["counts"].items():
                    all_results[layer]["counts"][name].add_poisson(value)

    return all_results


def validate_file_schema(files: list[str], tree: str) -> None:
    missing_by_file = {}
    for filename in files:
        with uproot.open(f"{filename}:{tree}") as root_tree:
            branches = set(root_tree.keys())
        missing = missing_required_for_available(branches)
        if missing:
            missing_by_file[filename] = missing

    if not missing_by_file:
        return

    lines = ["Input file is not compatible with the DisTkCoffee NanoAOD Pveto schema."]
    for filename, missing in missing_by_file.items():
        lines.append(f"{filename}:")
        for name in missing:
            lines.append(f"  - {missing_branch_message(name)}")
    raise RuntimeError("\n".join(lines))


def print_summary(results):
    for layer, result in results.items():
        print()
        print("=" * 100)
        print(layer)
        print("=" * 100)
        for name, value in result["cutflow"].items():
            print(f"{name:65s} {value:12d}")
        print("\nPveto counts")
        for name, count in result["counts"].items():
            print(f"{name:20s} {count.value:12.6g} +/- {count.error:.6g}")


def write_root(path: Path, results) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with uproot.recreate(path) as fout:
        for layer, result in results.items():
            for name, count in result["counts"].items():
                fout[f"{layer}/{name}"] = np.histogram(
                    [0.5],
                    bins=1,
                    range=(0, 1),
                    weights=[count.value],
                )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the OSUNano custom NanoAOD muon Pveto analysis."
    )
    parser.add_argument("--single-muon", nargs="+", required=True)
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--era", choices=("C", "D", "E", "F", "G"), default="C")
    parser.add_argument(
        "--layers",
        default="all",
        choices=["NLayers4", "NLayers5", "NLayers6plus", "combinedBins", "all"],
    )
    parser.add_argument("--chunk-size", default="100 MB")
    parser.add_argument(
        "--jet-veto-year",
        choices=sorted(JET_VETO_CONFIGS),
        help=(
            "Run 3 JERC jet-veto-map campaign to use when a saved "
            "passJvmFilter/jetVeto2022 branch is absent."
        ),
    )
    parser.add_argument(
        "--jet-veto-map-file",
        default=None,
        help="Optional override for the correctionlib jetvetomaps.json.gz file.",
    )
    parser.add_argument(
        "--jet-veto-map-name",
        default=None,
        help="Optional override for the correction name inside the jet veto map file.",
    )
    parser.add_argument(
        "--disable-jet-veto-map",
        action="store_true",
        help="Debug-only bypass: treat the jet-veto-map row as all true.",
    )
    parser.add_argument("--electron-fiducial-map", help="Override electron fiducial ROOT map.")
    parser.add_argument("--muon-fiducial-map", help="Override muon fiducial ROOT map.")
    parser.add_argument("--fiducial-threshold", type=float, default=0.0)
    parser.add_argument("--disable-fiducial-maps", action="store_true", help="Debug-only bypass: treat electron/muon fiducial maps as all true.")
    parser.add_argument("--missing-hits-mode", choices=("saved", "stochastic"), default="saved")
    parser.add_argument("--missing-hits-period", choices=tuple(MISSING_HITS_CORRECTIONS), help="Override era-derived missing-hit correction period.")
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    configure_jet_veto(
        "none" if args.disable_jet_veto_map else "pocketcoffea",
        args.jet_veto_year,
        args.jet_veto_map_file,
        args.jet_veto_map_name,
    )
    if args.disable_fiducial_maps:
        electron_map = None
        muon_map = None
    else:
        default_electron_map, default_muon_map = default_fiducial_map_paths(args.era)
        electron_map = args.electron_fiducial_map or str(default_electron_map)
        muon_map = args.muon_fiducial_map or str(default_muon_map)
    configure_fiducial_maps(electron_map, muon_map, args.fiducial_threshold)
    configure_missing_hits(
        args.missing_hits_mode,
        args.missing_hits_period or ERA_TO_MISSING_HITS_PERIOD[args.era],
    )

    files = parse_inputs(args.single_muon)
    if not files:
        raise RuntimeError("No input files found.")

    validate_file_schema(files, args.tree)
    layers = normalize_layers(args.layers)
    results = run_file_set(files, args.tree, layers, args.chunk_size)
    print_summary(results)

    payload = make_payload(files, args.tree, results)
    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w") as fout:
        json.dump(payload, fout, indent=2, sort_keys=True)
    print(f"\nWrote {json_path}")

    if args.output:
        write_root(Path(args.output), results)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
