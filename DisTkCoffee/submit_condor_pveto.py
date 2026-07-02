#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

DEFAULT_IMAGE = "/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-el9-stable"
DEFAULT_PROXY = "/uscms/home/czheng/x509up_u3691"
DEFAULT_XROOTD_PREFIX = "root://cmseos.fnal.gov/"

CHANNEL_CONFIGS = {
    "muon": {
        "runner": "DisTkCoffee/run_disTkMuonPveto.py",
        "single_arg": "--single-muon",
        "wrapper": "run_disTkMuonPveto_split.sh",
        "submit": "disTkMuonPveto.submit",
        "default_label_prefix": "distk_muon_pveto",
    },
    "electron": {
        "runner": "DisTkCoffee/run_disTkElectronPveto.py",
        "single_arg": "--single-electron",
        "wrapper": "run_disTkElectronPveto_split.sh",
        "submit": "disTkElectronPveto.submit",
        "default_label_prefix": "distk_electron_pveto",
    },
}


def channel_config(args: argparse.Namespace) -> dict[str, str]:
    return CHANNEL_CONFIGS[args.channel]


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    print("+ " + " ".join(shlex.quote(part) for part in command))
    return subprocess.run(
        command,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def read_input_filelist(path: Path) -> list[str]:
    files = []
    for line in path.read_text().splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            files.append(normalize_input(item))
    return files


def list_eos_root_files(input_dir: str) -> list[str]:
    directory = input_dir.rstrip("/")
    listing_path = directory
    if directory.startswith(DEFAULT_XROOTD_PREFIX):
        listing_path = directory.removeprefix(DEFAULT_XROOTD_PREFIX).lstrip("/")
    proc = run(["eos", "root://cmseos.fnal.gov", "ls", listing_path])
    files = []
    for name in proc.stdout.splitlines():
        name = name.strip()
        if name.endswith(".root"):
            files.append(normalize_input(f"{listing_path}/{name}"))
    return sorted(files)


def normalize_input(item: str) -> str:
    if item.startswith("root://") or item.startswith("file:"):
        return item
    if item.startswith("/store/"):
        return DEFAULT_XROOTD_PREFIX + "/" + item.lstrip("/")
    return item


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def ensure_new_dir(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise SystemExit(
            f"Refusing to reuse non-empty directory: {path}\n"
            "Pass --overwrite only for a deliberate retry."
        )
    path.mkdir(parents=True, exist_ok=True)


def write_wrapper(path: Path, args: argparse.Namespace) -> None:
    config = channel_config(args)
    extra_runner_args = ""
    if args.channel == "muon":
        if args.jet_veto_year:
            extra_runner_args += f" \\\n    --jet-veto-year {shlex.quote(args.jet_veto_year)}"
        if args.jet_veto_map_file:
            extra_runner_args += f" \\\n    --jet-veto-map-file {shlex.quote(args.jet_veto_map_file)}"
        if args.jet_veto_map_name:
            extra_runner_args += f" \\\n    --jet-veto-map-name {shlex.quote(args.jet_veto_map_name)}"
        if args.disable_jet_veto_map:
            extra_runner_args += " \\\n    --disable-jet-veto-map"
    path.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

IDX="${{1:?missing split index}}"
TREE="${{2:-Events}}"
LAYERS="${{3:-all}}"
CHUNK_SIZE="${{4:-100 MB}}"
LIST="split_filelists/files_${{IDX}}.txt"
OUT="analysis_output_${{IDX}}"
IMAGE={shlex.quote(args.image)}

if [[ ! -s "${{LIST}}" ]]; then
  echo "Missing or empty split filelist: ${{LIST}}" >&2
  exit 2
fi

mkdir -p "${{OUT}}"
mapfile -t FILES < "${{LIST}}"

apptainer exec \\
  -B /cvmfs:/cvmfs \\
  -B "${{PWD}}:${{PWD}}" \\
  "${{IMAGE}}" \\
  python3 {config["runner"]} \\
    {config["single_arg"]} "${{FILES[@]}}" \\
    --tree "${{TREE}}" \\
    --layers "${{LAYERS}}" \\
    --chunk-size "${{CHUNK_SIZE}}"{extra_runner_args} \\
    --json-output "${{OUT}}/pveto_summary.json" \\
    --output "${{OUT}}/pveto_summary.root"
"""
    )
    path.chmod(0o755)


def write_submit_file(path: Path, repo_root: Path, args: argparse.Namespace) -> None:
    config = channel_config(args)
    distkcoffee_dir = repo_root / "DisTkCoffee"
    chunk_size = args.chunk_size.replace(" ", "")
    path.write_text(
        f"""universe = vanilla
executable = {config["wrapper"]}
arguments = $(IDX) {args.tree} {args.layers} {chunk_size}
transfer_input_files = {distkcoffee_dir},split_filelists
transfer_output_files = analysis_output_$(IDX)
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
x509userproxy = {args.proxy}
request_cpus = {args.request_cpus}
request_memory = {args.request_memory}
request_disk = {args.request_disk}
output = logs/job_$(Cluster)_$(Process).out
error = logs/job_$(Cluster)_$(Process).err
log = logs/job_$(Cluster).log
queue IDX from split_indices.txt
"""
    )


def write_manifest(path: Path, args: argparse.Namespace, files: list[str], splits: list[list[str]]) -> None:
    config = channel_config(args)
    input_source = args.input_dir if args.input_dir else str(args.input_filelist)
    path.write_text(
        f"""# DisTkCoffee Condor Run Manifest

channel: {args.channel}
run_label: {args.run_label}
created: {datetime.now().isoformat(timespec="seconds")}
input_source: {input_source}
input_files: {len(files)}
files_per_job: {args.files_per_job}
jobs: {len(splits)}
tree: {args.tree}
layers: {args.layers}
chunk_size: {args.chunk_size}
jet_veto_year: {args.jet_veto_year}
jet_veto_map_file: {args.jet_veto_map_file}
jet_veto_map_name: {args.jet_veto_map_name}
disable_jet_veto_map: {args.disable_jet_veto_map}
proxy: {args.proxy}
image: {args.image}
runner: {config["runner"]}
submit_file: {config["submit"]}

Submit from this directory with:

```bash
condor_submit {config["submit"]}
```

After completion, expect one JSON and ROOT output in each `analysis_output_*` directory.
"""
    )


def check_proxy(proxy: str) -> None:
    proc = subprocess.run(
        ["voms-proxy-info", "-file", proxy, "-timeleft"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode != 0:
        raise SystemExit(f"Could not read proxy {proxy}:\n{proc.stderr.strip()}")
    seconds = int(proc.stdout.strip() or "0")
    if seconds <= 0:
        raise SystemExit(f"Proxy is expired: {proxy}")
    print(f"Proxy time left: {seconds} seconds")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally submit LPC Condor jobs for OSUNano DisTkCoffee Pveto."
    )
    parser.add_argument(
        "--channel",
        default="muon",
        choices=sorted(CHANNEL_CONFIGS),
        help="Pveto channel to run. Muon remains the default for backward compatibility.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--input-dir",
        help="EOS /store directory or root://cmseos.fnal.gov//store directory containing NanoAOD ROOT files.",
    )
    source.add_argument(
        "--input-filelist",
        type=Path,
        help="Text file with one NanoAOD ROOT file or XRootD URL per line.",
    )
    parser.add_argument("--run-label")
    parser.add_argument("--result-base", type=Path, default=Path("validation/results"))
    parser.add_argument("--files-per-job", type=int, default=25)
    parser.add_argument("--max-files", type=int, help="Limit input file count for a smoke-scale Condor test.")
    parser.add_argument("--tree", default="Events")
    parser.add_argument(
        "--layers",
        default="all",
        choices=["NLayers4", "NLayers5", "NLayers6plus", "combinedBins", "all"],
    )
    parser.add_argument("--chunk-size", default="100MB")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--request-cpus", default="1")
    parser.add_argument("--request-memory", default="4 GB")
    parser.add_argument("--request-disk", default="5 GB")
    parser.add_argument(
        "--jet-veto-year",
        choices=["2022_preEE", "2022_postEE", "2023_preBPix", "2023_postBPix", "2024"],
        help=(
            "Run 3 JERC jet-veto-map campaign passed to the muon runner when "
            "a saved passJvmFilter/jetVeto2022 branch is absent."
        ),
    )
    parser.add_argument(
        "--jet-veto-map-file",
        default=None,
        help="Optional correctionlib jetvetomaps.json.gz override passed to the muon runner.",
    )
    parser.add_argument(
        "--jet-veto-map-name",
        default=None,
        help="Optional correction name override passed to the muon runner.",
    )
    parser.add_argument(
        "--disable-jet-veto-map",
        action="store_true",
        help="Debug-only bypass: tell the muon runner to treat the jet-veto-map row as all true.",
    )
    parser.add_argument("--submit", action="store_true", help="Run condor_submit after preparing the directory.")
    parser.add_argument("--overwrite", action="store_true", help="Allow reusing a non-empty condor directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.files_per_job <= 0:
        raise SystemExit("--files-per-job must be positive")
    if args.run_label is None:
        prefix = channel_config(args)["default_label_prefix"]
        args.run_label = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    script_path = Path(__file__)
    if script_path.is_absolute():
        repo_root = script_path.parent.parent
    else:
        repo_root = (Path(os.environ.get("PWD", ".")).joinpath(script_path)).parent.parent
    result_base = args.result_base if args.result_base.is_absolute() else repo_root / args.result_base
    run_dir = result_base / args.run_label
    condor_dir = run_dir / "condor"
    split_dir = condor_dir / "split_filelists"
    logs_dir = condor_dir / "logs"

    if args.input_dir:
        files = list_eos_root_files(args.input_dir)
    else:
        files = read_input_filelist(args.input_filelist)
    if args.max_files:
        files = files[: args.max_files]
    if not files:
        raise SystemExit("No input ROOT files found.")

    splits = chunked(files, args.files_per_job)
    ensure_new_dir(condor_dir, args.overwrite)
    split_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    config = channel_config(args)
    for index, split in enumerate(splits):
        (split_dir / f"files_{index}.txt").write_text("\n".join(split) + "\n")
    (condor_dir / "split_indices.txt").write_text("\n".join(str(i) for i in range(len(splits))) + "\n")
    write_wrapper(condor_dir / config["wrapper"], args)
    write_submit_file(condor_dir / config["submit"], repo_root, args)
    write_manifest(condor_dir / "MANIFEST.md", args, files, splits)

    print(f"Prepared {len(splits)} Condor jobs from {len(files)} input files")
    print(f"Condor directory: {condor_dir}")
    print(f"Submit file: {condor_dir / config['submit']}")

    if args.submit:
        check_proxy(args.proxy)
        submit_cmd = f"condor_submit {shlex.quote(config['submit'])}"
        proc = subprocess.run(["/bin/bash", "-lc", submit_cmd], cwd=condor_dir, text=True)
        raise SystemExit(proc.returncode)

    print("Not submitted. Inspect the directory, then run:")
    print(f"  cd {condor_dir}")
    print(f"  condor_submit {config['submit']}")


if __name__ == "__main__":
    main()
