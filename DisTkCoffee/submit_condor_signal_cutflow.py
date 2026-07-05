#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

DEFAULT_IMAGE = "/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-el9-stable"
DEFAULT_PROXY = "/uscms/home/czheng/x509up_u3691"
DEFAULT_XROOTD_PREFIX = "root://cmseos.fnal.gov/"
DEFAULT_RUNNER = "DisTkCoffee/run_disTkSignalCutflow.py"
DEFAULT_WRAPPER = "run_disTkSignalCutflow_transfer.sh"
DEFAULT_SUBMIT = "disTkSignalCutflow.submit"
DEFAULT_PAYLOAD = "signal_runner_payload.tgz"
SAMPLE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


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


def normalize_input(item: str) -> str:
    item = item.strip()
    if item.startswith("/eos/uscms/"):
        item = item.removeprefix("/eos/uscms")
    if item.startswith("root://") or item.startswith("file:"):
        return item
    if item.startswith("/store/"):
        return DEFAULT_XROOTD_PREFIX + "/" + item.lstrip("/")
    return item


def eos_listing_path(source: str) -> str:
    path = source.rstrip("/")
    if path.startswith(DEFAULT_XROOTD_PREFIX):
        path = path.removeprefix(DEFAULT_XROOTD_PREFIX)
    if path.startswith("/eos/uscms/"):
        path = path.removeprefix("/eos/uscms")
    path = "/" + path.lstrip("/")
    return path


def read_input_filelist(path: Path) -> list[str]:
    files = []
    for line in path.read_text().splitlines():
        item = line.strip()
        if item and not item.startswith("#"):
            files.append(normalize_input(item))
    return files


def list_eos_root_files(source: str) -> list[str]:
    listing_path = eos_listing_path(source)
    proc = run(["eos", "root://cmseos.fnal.gov", "find", "-f", listing_path])
    files = []
    for item in proc.stdout.splitlines():
        item = item.strip()
        if item.endswith(".root"):
            files.append(normalize_input(item))
    return sorted(files)


def expand_local_glob(source: str) -> list[str]:
    return sorted(str(path) for path in Path().glob(source) if path.is_file() and path.suffix == ".root")


def source_to_files(source: str) -> list[str]:
    if source.startswith("root://") and source.endswith(".root"):
        return [source]
    if source.startswith("/store/") and source.endswith(".root"):
        return [normalize_input(source)]

    path = Path(source)
    if path.exists() and path.is_file():
        if path.suffix == ".root":
            return [normalize_input(str(path))]
        return read_input_filelist(path)

    if any(char in source for char in "*?["):
        files = expand_local_glob(source)
        if files:
            return [normalize_input(item) for item in files]

    return list_eos_root_files(source)


def parse_sample(item: str) -> tuple[str, str]:
    if "=" not in item:
        raise argparse.ArgumentTypeError("Use NAME=SOURCE, for example ctau100=/store/...")
    name, source = item.split("=", 1)
    name = name.strip()
    source = source.strip()
    if not name or not source:
        raise argparse.ArgumentTypeError("Sample name and source must be non-empty")
    if not SAMPLE_RE.match(name):
        raise argparse.ArgumentTypeError(
            f"Sample name {name!r} is not safe for Condor file names. Use letters, numbers, _, ., or -."
        )
    return name, source


def chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def ensure_new_dir(path: Path, overwrite: bool) -> None:
    if path.exists() and any(path.iterdir()) and not overwrite:
        raise SystemExit(
            f"Refusing to reuse non-empty directory: {path}\n"
            "Pass --overwrite only for a deliberate retry."
        )
    path.mkdir(parents=True, exist_ok=True)


def repo_root_from_script() -> Path:
    script_path = Path(__file__)
    if script_path.is_absolute():
        return script_path.parent.parent
    return (Path(os.environ.get("PWD", ".")).joinpath(script_path)).resolve().parent.parent


def runner_extra_args(args: argparse.Namespace) -> str:
    parts: list[str] = []
    option_values = [
        ("--jet-veto-year", args.jet_veto_year),
        ("--jet-veto-file", args.jet_veto_file),
        ("--jet-veto-name", args.jet_veto_name),
        ("--jer-file", args.jer_file),
        ("--jer-resolution-name", args.jer_resolution_name),
        ("--jer-scale-factor-name", args.jer_scale_factor_name),
        ("--electron-fiducial-map", args.electron_fiducial_map),
        ("--muon-fiducial-map", args.muon_fiducial_map),
        ("--missing-hits-period", args.missing_hits_period),
    ]
    for option, value in option_values:
        if value:
            parts.append(f" \\\n    {option} {shlex.quote(value)}")
    if args.fiducial_threshold != 0.0:
        parts.append(f" \\\n    --fiducial-threshold {args.fiducial_threshold}")
    return "".join(parts)


def write_wrapper(path: Path, args: argparse.Namespace) -> None:
    root_output = ""
    if not args.no_root_output:
        root_output = ' \\\n    --output "$PWD/$OUTDIR/signal_cutflow.root"'

    path.write_text(
        f"""#!/usr/bin/env bash
set -euo pipefail

SAMPLE="${{1:?missing sample}}"
IDX="${{2:?missing split index}}"
TREE="${{3:-Events}}"
ERA="${{4:-C}}"
CHUNK_SIZE="${{5:-100MB}}"
MISSING_HITS_MODE="${{6:-saved}}"
LIST="split_filelists/${{SAMPLE}}_${{IDX}}.txt"
OUTDIR="analysis_output_${{SAMPLE}}_${{IDX}}"
IMAGE={shlex.quote(args.image)}
CONTAINER_WORKDIR="/srv/work"

if [[ ! -s "${{LIST}}" ]]; then
  echo "Missing or empty split filelist: ${{LIST}}" >&2
  exit 2
fi

mkdir -p "${{OUTDIR}}"
mapfile -t FILES < "${{LIST}}"

echo "Host: $(hostname)"
echo "PWD: $PWD"
echo "Sample: ${{SAMPLE}}"
echo "Split: ${{IDX}}"
echo "Files: ${{#FILES[@]}}"
printf "  %s\\n" "${{FILES[@]}}"
echo "Output dir: ${{OUTDIR}}"
echo "X509_USER_PROXY: ${{X509_USER_PROXY:-unset}}"

rm -rf payload
tar -xzf {DEFAULT_PAYLOAD}

apptainer exec \\
  -B "$PWD:${{CONTAINER_WORKDIR}}" \\
  -B /cvmfs:/cvmfs \\
  --pwd "${{CONTAINER_WORKDIR}}" \\
  "$IMAGE" \\
  python3 "${{CONTAINER_WORKDIR}}/payload/run_disTkSignalCutflow.py" \\
    --input "${{FILES[@]}}" \\
    --tree "${{TREE}}" \\
    --era "${{ERA}}" \\
    --missing-hits-mode "${{MISSING_HITS_MODE}}" \\
    --json-output "${{CONTAINER_WORKDIR}}/${{OUTDIR}}/signal_cutflow.json" \\
    --chunk-size "${{CHUNK_SIZE}}"{root_output.replace('$PWD', '${CONTAINER_WORKDIR}')}{runner_extra_args(args)}

ls -lh "${{OUTDIR}}"
"""
    )
    path.chmod(0o755)


def write_submit_file(path: Path, args: argparse.Namespace) -> None:
    chunk_size = args.chunk_size.replace(" ", "")
    path.write_text(
        f"""universe = vanilla
executable = {DEFAULT_WRAPPER}
arguments = $(sample) $(idx) {args.tree} {args.era} {chunk_size} {args.missing_hits_mode}
output = logs/$(sample)_$(idx).out
error = logs/$(sample)_$(idx).err
log = logs/condor.log
request_cpus = {args.request_cpus}
request_memory = {args.request_memory}
request_disk = {args.request_disk}
+JobFlavour = "{args.job_flavour}"
should_transfer_files = YES
when_to_transfer_output = ON_EXIT
transfer_input_files = {DEFAULT_PAYLOAD},split_filelists
transfer_output_files = analysis_output_$(sample)_$(idx)
x509userproxy = {args.proxy}
queue sample, idx from jobs.args
"""
    )


def build_payload(path: Path, repo_root: Path) -> None:
    runner = repo_root / DEFAULT_RUNNER
    data_dir = repo_root / "DisTkCoffee" / "data"
    if not runner.exists():
        raise SystemExit(f"Missing signal runner: {runner}")
    if not data_dir.exists():
        raise SystemExit(f"Missing signal data directory: {data_dir}")

    with tarfile.open(path, "w:gz") as tar:
        tar.add(runner, arcname="payload/run_disTkSignalCutflow.py")
        for item in sorted(data_dir.iterdir()):
            if item.is_file() and item.suffix in {".root", ".py"}:
                tar.add(item, arcname=f"payload/data/{item.name}")


def write_manifest(
    path: Path,
    args: argparse.Namespace,
    samples: dict[str, list[str]],
    jobs: list[tuple[str, int, list[str]]],
    condor_dir: Path,
) -> None:
    manifest = {
        "created": datetime.now().isoformat(timespec="seconds"),
        "run_label": args.run_label,
        "condor_dir": str(condor_dir),
        "samples": {name: len(files) for name, files in samples.items()},
        "jobs": len(jobs),
        "files_per_job": args.files_per_job,
        "tree": args.tree,
        "era": args.era,
        "chunk_size": args.chunk_size,
        "missing_hits_mode": args.missing_hits_mode,
        "proxy": args.proxy,
        "image": args.image,
        "runner": DEFAULT_RUNNER,
        "submit_file": DEFAULT_SUBMIT,
        "payload": DEFAULT_PAYLOAD,
        "notes": [
            "Generated by DisTkCoffee/submit_condor_signal_cutflow.py.",
            "Uses Condor file transfer; NanoAOD ROOT inputs remain XRootD paths in split_filelists.",
            "The queue variable is not named input because HTCondor treats input as a reserved stdin transfer field.",
        ],
    }
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    md_path = path.with_suffix(".md")
    md_path.write_text(
        f"""# Signal Cutflow Condor Run

run_label: {args.run_label}
created: {manifest["created"]}
condor_dir: {condor_dir}
jobs: {len(jobs)}
files_per_job: {args.files_per_job}
tree: {args.tree}
era: {args.era}
chunk_size: {args.chunk_size}
missing_hits_mode: {args.missing_hits_mode}
proxy: {args.proxy}
image: {args.image}

Samples:
{chr(10).join(f"- {name}: {len(files)} files" for name, files in samples.items())}

Submit from this directory with:

```bash
condor_submit {DEFAULT_SUBMIT}
```

After completion, expect one JSON and ROOT output in each `analysis_output_<sample>_<idx>` directory.
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
        description="Prepare and optionally submit LPC Condor jobs for the DisTk signal cutflow."
    )
    parser.add_argument(
        "--sample",
        action="append",
        type=parse_sample,
        required=True,
        metavar="NAME=SOURCE",
        help=(
            "Signal sample name and source. SOURCE may be a /store directory, root:// directory, "
            "single ROOT file, or text filelist. Repeat for ctau10, ctau100, etc."
        ),
    )
    parser.add_argument("--run-label")
    parser.add_argument("--result-base", type=Path, default=Path("validation/results"))
    parser.add_argument("--files-per-job", type=int, default=1)
    parser.add_argument("--max-files-per-sample", type=int, help="Limit each sample for smoke-scale tests.")
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--era", choices=("C", "D", "E", "F", "G"), default="C")
    parser.add_argument("--chunk-size", default="100MB")
    parser.add_argument("--missing-hits-mode", choices=("saved", "stochastic"), default="saved")
    parser.add_argument("--missing-hits-period", help="Override era-derived missing-hit correction period.")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--proxy", default=DEFAULT_PROXY)
    parser.add_argument("--request-cpus", default="1")
    parser.add_argument("--request-memory", default="2500MB")
    parser.add_argument("--request-disk", default="2500MB")
    parser.add_argument("--job-flavour", default="workday")
    parser.add_argument("--jet-veto-year", choices=("2022_preEE", "2022_postEE"), help="Override era-derived JERC jet-veto campaign.")
    parser.add_argument("--jet-veto-file", help="Override correctionlib jetvetomaps.json.gz file.")
    parser.add_argument("--jet-veto-name", help="Override correctionlib jet-veto correction name.")
    parser.add_argument("--jer-file", help="Override correctionlib jet_jerc.json.gz file.")
    parser.add_argument("--jer-resolution-name", help="Override JER pt-resolution correction name.")
    parser.add_argument("--jer-scale-factor-name", help="Override JER scale-factor correction name.")
    parser.add_argument("--electron-fiducial-map", help="Override electron fiducial ROOT map.")
    parser.add_argument("--muon-fiducial-map", help="Override muon fiducial ROOT map.")
    parser.add_argument("--fiducial-threshold", type=float, default=0.0)
    parser.add_argument("--no-root-output", action="store_true", help="Only write JSON outputs.")
    parser.add_argument("--submit", action="store_true", help="Run condor_submit after preparing the directory.")
    parser.add_argument("--overwrite", action="store_true", help="Allow reusing a non-empty condor directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.files_per_job <= 0:
        raise SystemExit("--files-per-job must be positive")
    if args.run_label is None:
        args.run_label = f"distk_signal_cutflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    repo_root = repo_root_from_script()
    result_base = args.result_base if args.result_base.is_absolute() else repo_root / args.result_base
    run_dir = result_base / args.run_label
    condor_dir = run_dir / "condor"
    split_dir = condor_dir / "split_filelists"
    logs_dir = condor_dir / "logs"

    samples: dict[str, list[str]] = {}
    for name, source in args.sample:
        if name in samples:
            raise SystemExit(f"Duplicate sample name: {name}")
        files = source_to_files(source)
        if args.max_files_per_sample:
            files = files[: args.max_files_per_sample]
        if not files:
            raise SystemExit(f"No ROOT files found for sample {name}: {source}")
        samples[name] = files

    ensure_new_dir(condor_dir, args.overwrite)
    split_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[tuple[str, int, list[str]]] = []
    for sample, files in samples.items():
        for index, split in enumerate(chunked(files, args.files_per_job)):
            (split_dir / f"{sample}_{index}.txt").write_text("\n".join(split) + "\n")
            jobs.append((sample, index, split))

    (condor_dir / "jobs.args").write_text("\n".join(f"{sample} {index}" for sample, index, _ in jobs) + "\n")
    write_wrapper(condor_dir / DEFAULT_WRAPPER, args)
    write_submit_file(condor_dir / DEFAULT_SUBMIT, args)
    build_payload(condor_dir / DEFAULT_PAYLOAD, repo_root)
    write_manifest(condor_dir / "MANIFEST.json", args, samples, jobs, condor_dir)

    print(f"Prepared {len(jobs)} Condor jobs from {sum(len(files) for files in samples.values())} input files")
    for sample, files in samples.items():
        print(f"  {sample}: {len(files)} files")
    print(f"Condor directory: {condor_dir}")
    print(f"Submit file: {condor_dir / DEFAULT_SUBMIT}")

    if args.submit:
        check_proxy(args.proxy)
        proc = subprocess.run(["condor_submit", DEFAULT_SUBMIT], cwd=condor_dir, text=True)
        raise SystemExit(proc.returncode)

    print("Not submitted. Inspect the directory, then run:")
    print(f"  cd {condor_dir}")
    print(f"  condor_submit {DEFAULT_SUBMIT}")


if __name__ == "__main__":
    main()
