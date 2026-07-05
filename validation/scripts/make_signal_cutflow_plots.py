#!/usr/bin/env python3
"""Merge signal cutflow split JSONs and make Figure-17-style plots."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages


SAMPLE_LABELS = {
    "ctau10": "c tau = 10 cm",
    "ctau100": "c tau = 100 cm",
    "ctau1000": "c tau = 1000 cm",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--samples",
        nargs="+",
        default=["ctau10", "ctau100", "ctau1000"],
        help="Sample keys to merge and plot.",
    )
    parser.add_argument("--title", default="AMSB chargino, m = 700 GeV")
    parser.add_argument("--subtitle", default="2022 preEE/C-D settings")
    return parser.parse_args()


def discover_files(input_dir: Path, samples: list[str]) -> dict[str, list[Path]]:
    files_by_sample: dict[str, list[Path]] = {sample: [] for sample in samples}
    pattern = re.compile(r"analysis_output_(ctau\d+)_\d+$")
    for json_path in sorted(input_dir.glob("analysis_output_*_*/signal_cutflow.json")):
        match = pattern.search(json_path.parent.name)
        if not match:
            continue
        sample = match.group(1)
        if sample in files_by_sample:
            files_by_sample[sample].append(json_path)
    return files_by_sample


def read_cutflow(path: Path) -> list[dict[str, float | str]]:
    with path.open() as fin:
        payload = json.load(fin)
    return payload["cutflow"]


def merge_sample(sample: str, paths: list[Path]) -> dict:
    if not paths:
        raise RuntimeError(f"No JSON files found for {sample}")

    cuts: list[str] | None = None
    counts: defaultdict[str, float] = defaultdict(float)

    for path in paths:
        rows = read_cutflow(path)
        row_cuts = [str(row["cut"]) for row in rows]
        if cuts is None:
            cuts = row_cuts
        elif row_cuts != cuts:
            raise RuntimeError(f"Cutflow row mismatch in {path}")
        for row in rows:
            counts[str(row["cut"])] += float(row["count"])

    assert cuts is not None
    total = counts[cuts[0]]
    merged_rows = []
    previous = None
    for cut in cuts:
        count = counts[cut]
        cumulative = count / total if total else math.nan
        relative = count / previous if previous not in (None, 0.0) else cumulative
        merged_rows.append(
            {
                "cut": cut,
                "count": count,
                "cumulative_efficiency": cumulative,
                "relative_efficiency": relative,
            }
        )
        previous = count

    return {
        "sample": sample,
        "n_files": len(paths),
        "source_files": [str(path) for path in paths],
        "cutflow": merged_rows,
    }


def write_outputs(merged: dict[str, dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for sample, payload in merged.items():
        with (output_dir / f"merged_{sample}_signal_cutflow.json").open("w") as fout:
            json.dump(payload, fout, indent=2, sort_keys=True)

    with (output_dir / "merged_signal_cutflow_all.json").open("w") as fout:
        json.dump(merged, fout, indent=2, sort_keys=True)

    rows = next(iter(merged.values()))["cutflow"]
    with (output_dir / "merged_signal_cutflow.csv").open("w", newline="") as fout:
        writer = csv.writer(fout)
        header = ["index", "cut"]
        for sample in merged:
            header.extend(
                [
                    f"{sample}_count",
                    f"{sample}_cumulative_efficiency",
                    f"{sample}_relative_efficiency",
                ]
            )
        writer.writerow(header)
        for index, row in enumerate(rows):
            line = [index, row["cut"]]
            for sample in merged:
                sample_row = merged[sample]["cutflow"][index]
                line.extend(
                    [
                        sample_row["count"],
                        sample_row["cumulative_efficiency"],
                        sample_row["relative_efficiency"],
                    ]
                )
            writer.writerow(line)


def clean_label(label: str) -> str:
    replacements = {
        "passecalBadCalibFilterUpdate": "passEcalBadCalibFilterUpdate",
        "fabs(eta)": "fabs ( eta )",
        "fabs( eta )": "fabs ( eta )",
        "DeltaPhi": "DeltaPhi",
        "eventvariables jetVeto2022 == 1": ">= 1 eventvariables with jetVeto2022 == 1",
        "matchedCaloJetEmEnergy + matchedCaloJetHadEnergy < 10": "(matchedCaloJetEmEnergy + matchedCaloJetHadEnergy) < 10",
    }
    out = label
    for old, new in replacements.items():
        out = out.replace(old, new)
    return out


def style_axis(ax, title: str, subtitle: str) -> None:
    ax.grid(True, axis="x", which="both", linestyle=":", linewidth=0.7, alpha=0.6)
    ax.set_title(f"{title}\n{subtitle}", loc="left", fontsize=12, fontweight="bold", pad=10)
    ax.text(1.0, 1.025, "13.6 TeV", transform=ax.transAxes, fontsize=10, ha="right", va="bottom")


def plot_cumulative(merged: dict[str, dict], output_dir: Path, title: str, subtitle: str) -> plt.Figure:
    first_rows = next(iter(merged.values()))["cutflow"]
    labels = [clean_label(str(row["cut"])) for row in first_rows]
    y = list(range(len(labels)))

    fig_height = max(10.0, len(labels) * 0.32)
    fig, ax = plt.subplots(figsize=(12.0, fig_height))

    for sample, payload in merged.items():
        values = [max(float(row["cumulative_efficiency"]), 1e-8) for row in payload["cutflow"]]
        ax.plot(values, y, marker="o", markersize=4, linewidth=1.8, label=SAMPLE_LABELS.get(sample, sample))

    ax.set_xscale("log")
    ax.set_xlim(1e-4, 1.2)
    ax.set_xlabel("Cumulative efficiency")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.legend(loc="lower left", frameon=False)
    style_axis(ax, title, subtitle)
    fig.tight_layout()
    fig.savefig(output_dir / "signal_cutflow_cumulative_efficiency.pdf")
    fig.savefig(output_dir / "signal_cutflow_cumulative_efficiency.png", dpi=180)
    return fig


def plot_counts(merged: dict[str, dict], output_dir: Path, title: str, subtitle: str) -> plt.Figure:
    first_rows = next(iter(merged.values()))["cutflow"]
    labels = [clean_label(str(row["cut"])) for row in first_rows]
    y = list(range(len(labels)))

    fig_height = max(10.0, len(labels) * 0.32)
    fig, ax = plt.subplots(figsize=(12.0, fig_height))

    for sample, payload in merged.items():
        values = [max(float(row["count"]), 1e-4) for row in payload["cutflow"]]
        ax.plot(values, y, marker="o", markersize=4, linewidth=1.8, label=SAMPLE_LABELS.get(sample, sample))

    ax.set_xscale("log")
    ax.set_xlabel("Signed weighted count")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.legend(loc="lower left", frameon=False)
    style_axis(ax, title, subtitle)
    fig.tight_layout()
    fig.savefig(output_dir / "signal_cutflow_weighted_counts.pdf")
    fig.savefig(output_dir / "signal_cutflow_weighted_counts.png", dpi=180)
    return fig


def plot_relative(merged: dict[str, dict], output_dir: Path, title: str, subtitle: str) -> plt.Figure:
    first_rows = next(iter(merged.values()))["cutflow"]
    labels = [clean_label(str(row["cut"])) for row in first_rows]
    y = list(range(len(labels)))

    fig_height = max(10.0, len(labels) * 0.32)
    fig, ax = plt.subplots(figsize=(12.0, fig_height))

    for sample, payload in merged.items():
        values = [float(row["relative_efficiency"]) for row in payload["cutflow"]]
        values = [min(max(value, 0.0), 1.05) for value in values]
        ax.plot(values, y, marker="o", markersize=4, linewidth=1.8, label=SAMPLE_LABELS.get(sample, sample))

    ax.set_xlim(0.0, 1.05)
    ax.set_xlabel("Efficiency relative to previous row")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    ax.legend(loc="lower left", frameon=False)
    style_axis(ax, title, subtitle)
    fig.tight_layout()
    fig.savefig(output_dir / "signal_cutflow_relative_efficiency.pdf")
    fig.savefig(output_dir / "signal_cutflow_relative_efficiency.png", dpi=180)
    return fig


def make_combined_pdf(figures: list[plt.Figure], output_dir: Path) -> None:
    with PdfPages(output_dir / "signal_cutflow_plots.pdf") as pdf:
        for fig in figures:
            pdf.savefig(fig)


def main() -> None:
    args = parse_args()
    files_by_sample = discover_files(args.input_dir, args.samples)
    merged = {sample: merge_sample(sample, files_by_sample[sample]) for sample in args.samples}

    write_outputs(merged, args.output_dir)
    figures = [
        plot_cumulative(merged, args.output_dir, args.title, args.subtitle),
        plot_counts(merged, args.output_dir, args.title, args.subtitle),
        plot_relative(merged, args.output_dir, args.title, args.subtitle),
    ]
    make_combined_pdf(figures, args.output_dir)

    for fig in figures:
        plt.close(fig)

    print(f"Wrote plots and merged cutflows to {args.output_dir}")
    for sample, payload in merged.items():
        final = payload["cutflow"][-1]
        print(
            f"{sample}: files={payload['n_files']} "
            f"total={payload['cutflow'][0]['count']:.6g} "
            f"final={final['count']:.6g} "
            f"final_eff={final['cumulative_efficiency']:.6g}"
        )


if __name__ == "__main__":
    main()
