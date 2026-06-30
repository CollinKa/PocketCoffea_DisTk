# DisTk Muon Pveto Coffee For OSUNano

This directory contains the DisTkCoffee copy of the muon Pveto Coffee analysis script adapted for OSUNano custom NanoAOD.

The important schema decision is intentional:

- PCAS reads central NanoAOD kinematics such as `Muon_pt`, `Muon_eta`, `Jet_pt`,
  and `Jet_eta`.
- PCAS reads custom OSUNano extras only where central NanoAOD does not already
  provide the needed definition, such as `muon_isTrigMatched`,
  `jet_isTightLepVeto`, `metNoMu_pt`, `metNoMu_phi`, and `trk_*`.
- PCAS does not require old lowercase duplicate kinematic branches.

## Files

```text
disTkMuonPveto_core.py
disTkMuonPveto_cuts.py
disTkMuonPveto_native_workflow.py
disTkMuonPveto_processor.py
disTkMuonPveto_config_native.py
run_disTkMuonPveto.py
export_pveto_json.py
make_dataset_json.py
run_options_local.yaml
datasets/disTkMuonPveto_smoke.json
```

The direct wrapper is useful for schema validation and simple local checks:

```text
run_disTkMuonPveto.py
```

The native PocketCoffea entry point is:

```text
disTkMuonPveto_config_native.py
```

## Environment On LPC

Use the official PocketCoffea Apptainer image:

```bash
apptainer exec \
  -B /cvmfs:/cvmfs \
  -B /uscms:/uscms \
  -B /uscms_data:/uscms_data \
  /cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-el9-stable \
  bash
```

Inside the container, use the real `/uscms_data` path for the checkout:

```bash
cd /uscms_data/d3/czheng/CMSSW_15_0_10/src/DisplacedLeptonsSupplement
```

## Direct Smoke Test

Run on a small OSUNano smoke file:

```bash
python3 DisTkCoffee/run_disTkMuonPveto.py \
  --single-muon test_outputs/distkcoffee_run2024C_muon0_20260624_eventfilters_proxy/osunano_distkcoffee_noskim_10.root \
  --tree Events \
  --layers all \
  --json-output CustomNanoAOD/validation/results/disTkMuonPveto_smoke.json \
  --output CustomNanoAOD/validation/results/disTkMuonPveto_smoke.root
```

The current smoke file was built with reduced standard Electron content. If
`Electron_eta` or `Electron_phi` is missing, the direct wrapper fails early with
a message explaining that the OSUNano NanoAOD must preserve central Electron
coordinates or add a minimal non-duplicate electron-coordinate solution. That
failure is expected for reduced validation files and should not be hidden.

## Native PocketCoffea Smoke Test

```bash
DISAPPTRKS_PVETO_DATASET_JSON=CustomNanoAOD/pocketcoffea_pveto/datasets/disTkMuonPveto_smoke.json \
pocket-coffea run \
  --cfg CustomNanoAOD/pocketcoffea_pveto/disTkMuonPveto_config_native.py \
  -o CustomNanoAOD/validation/results/disTkMuonPveto_native_smoke \
  --test \
  --custom-run-options CustomNanoAOD/pocketcoffea_pveto/run_options_local.yaml
```

Export the compact Pveto JSON:

```bash
python3 CustomNanoAOD/pocketcoffea_pveto/export_pveto_json.py \
  CustomNanoAOD/validation/results/disTkMuonPveto_native_smoke/output_all.coffea \
  --output CustomNanoAOD/validation/results/disTkMuonPveto_native_smoke/pveto_summary.json
```

## Trigger-Skim Interpretation

Trigger-trimmed Muon files are acceptable for Pveto counting because the input
file is already restricted to the SingleMuon trigger skim. They are not
acceptable for measuring trigger efficiency denominators; those studies require
unskimmed validation/control output.

The first cutflow label is therefore:

```text
input event kept by SingleMuon trigger skim
```

When `HLT_IsoMu24` is present, PCAS uses it as a diagnostic event mask.
