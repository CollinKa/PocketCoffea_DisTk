# Muon Pveto PocketCoffea Beginner Note and Cut Replication Status

Date: 2026-07-02

Repo:

```text
/uscms/home/czheng/nobackup/CMSSW_15_0_10/src/PocketCoffea_DisTk
```

Current checkout while writing this note:

```text
HEAD: d929590 Update electron Pveto Coffee cutflow
Muon cutflow commit in history: 1e5f0f0 Update muon Pveto Coffee cutflow
Branch: main
```

This note explains how to run the PocketCoffea-style muon Pveto analysis and how the current Coffee script maps the Run 3 muon tag-and-probe cuts onto branches in the customized NanoAOD. It also separates cuts that are fully reproduced, partially reproduced, and not reproducible from the current v1.0.0-pre NanoAOD.

## Scope

The relevant Run 3 analysis-note table for muon Pveto is Table 16, the muon tag-and-probe cutflow.

Do not use Table 23 as the muon Pveto cutflow. Table 23 is a tau tag-and-probe selection with a muon tag. It contains cuts such as `MT < 40 GeV` that should not be copied into the muon Pveto Table 16 workflow.

The current Coffee code counts all passing tag-probe pairs. It does not randomly choose one muon or one track. In `DisTkCoffee/disTkMuonPveto_core.py`, the pair counting is done with `ak.cartesian([tracks, muons], nested=True)` and the final `p_veto_*` values are sums over all OS and SS pairs.

## Main Files

| File | Purpose |
| --- | --- |
| `DisTkCoffee/disTkMuonPveto_core.py` | Main branch mapping, tag/probe masks, cutflow, pair counting. |
| `DisTkCoffee/run_disTkMuonPveto.py` | Direct runner over one or more NanoAOD ROOT files. It validates schema, reads branches with uproot, writes JSON/ROOT. |
| `DisTkCoffee/disTkMuonPveto_cuts.py` | Native PocketCoffea `Cut` wrappers around the same core functions. |
| `DisTkCoffee/submit_condor_pveto.py` | Helper to split filelists and prepare Condor jobs. |
| `validation/scripts/make_pveto_summary_tables.py` | Makes TeX/PDF tables from a merged `pveto_summary.json`. |

Current Jul2 output products:

```text
validation/Jul2_22MuonValidation/Run2022C/merged_Run2022C_pveto_summary.json
validation/Jul2_22MuonValidation/Run2022D/merged_Run2022D_pveto_summary.json
validation/Jul2_22MuonValidation/merged_Run2022CD_pveto_summary.json

validation/Jul2_22MuonValidation/Run2022C/pdf/Run2022C_muon_pveto_summary.pdf
validation/Jul2_22MuonValidation/Run2022D/pdf/Run2022D_muon_pveto_summary.pdf
validation/Jul2_22MuonValidation/pdf/Run2022CD_muon_pveto_summary.pdf
```

## Beginner Run Recipe

### 1. Log into LPC and enter the repo

Use the real backing path when running Apptainer/Condor, because binding the logical `/uscms/home/.../nobackup` path can fail inside the container.

```bash
ssh cmslpc-el9.fnal.gov
REAL=$(realpath /uscms/home/czheng/nobackup/CMSSW_15_0_10/src/PocketCoffea_DisTk)
cd "$REAL"
```

Check proxy:

```bash
voms-proxy-info -file /uscms/home/czheng/x509up_u3691 -timeleft
```

If this returns `0` or errors, renew the proxy before submitting jobs.

### 2. Set up and check the runtime environment

The Coffee analysis script is a Python/uproot/coffea-style analysis over
NanoAOD ROOT files. It is not a `cmsRun` job. For this validation workflow,
the important runtime is the PocketCoffea Apptainer image, not a local CMSSW
Python environment.

Use this image:

```bash
IMAGE="/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-el9-stable"
```

Check that the image is visible:

```bash
ls -ld "$IMAGE"
```

Check that Python inside the image can import the needed packages:

```bash
apptainer exec \
  -B /cvmfs:/cvmfs \
  -B "$PWD:$PWD" \
  "$IMAGE" \
  python3 - <<'PY'
import awkward
import coffea
import uproot
print("awkward", awkward.__version__)
print("coffea", coffea.__version__)
print("uproot", uproot.__version__)
PY
```

Check that the analysis runner is reachable and prints its options:

```bash
apptainer exec \
  -B /cvmfs:/cvmfs \
  -B "$PWD:$PWD" \
  "$IMAGE" \
  python3 DisTkCoffee/run_disTkMuonPveto.py --help
```

Check that the input NanoAOD directory exists and count files. For EOS paths,
use `xrdfs`; do not assume the directory is complete because the path exists.

```bash
xrdfs root://cmseos.fnal.gov ls /store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022C_customNanoAOD/260626_183424/0000 | grep '\.root$' | wc -l
xrdfs root://cmseos.fnal.gov ls /store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022D_customNanoAOD/260626_183436/0000 | grep '\.root$' | wc -l
```

For Condor submission, also check that HTCondor commands work on the LPC login
node:

```bash
condor_q -totals
condor_status -schedd | head
```

The proxy file is used by XRootD/EOS access from workers. The common file for
this setup is:

```text
/uscms/home/czheng/x509up_u3691
```

If the proxy is missing or expired, renew it before running a smoke test or
submitting Condor jobs.

### 3. Smoke-test one file before Condor

Use one input file and the PocketCoffea Apptainer image. Example for Run2022C:

```bash
mkdir -p validation/Jul2_22MuonValidation/Run2022C/smoke

INPUT="root://cmseos.fnal.gov//store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022C_customNanoAOD/260626_183424/0000/nano_1.root"
IMAGE="/cvmfs/unpacked.cern.ch/gitlab-registry.cern.ch/cms-analysis/general/pocketcoffea:lxplus-el9-stable"

apptainer exec \
  -B /cvmfs:/cvmfs \
  -B "$PWD:$PWD" \
  "$IMAGE" \
  python3 DisTkCoffee/run_disTkMuonPveto.py \
    --single-muon "$INPUT" \
    --tree Events \
    --layers all \
    --json-output validation/Jul2_22MuonValidation/Run2022C/smoke/pveto_summary.json \
    --output validation/Jul2_22MuonValidation/Run2022C/smoke/pveto_summary.root \
    > validation/Jul2_22MuonValidation/Run2022C/smoke/pcas.log 2>&1
```

Check the log:

```bash
sed -n '1,220p' validation/Jul2_22MuonValidation/Run2022C/smoke/pcas.log
```

Do not submit Condor if the smoke test fails schema validation.

### 4. Prepare and submit Condor jobs

Inputs used for Jul2:

```text
Run2022C: /store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022C_customNanoAOD/260626_183424/0000
Run2022D: /store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022D_customNanoAOD/260626_183436/0000
```

Prepare C:

```bash
python3 DisTkCoffee/submit_condor_pveto.py \
  --input-dir /store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022C_customNanoAOD/260626_183424/0000 \
  --run-label Run2022C \
  --result-base validation/Jul2_22MuonValidation \
  --files-per-job 25
```

Submit C:

```bash
cd "$REAL/validation/Jul2_22MuonValidation/Run2022C/condor"
condor_submit disTkMuonPveto.submit
```

Prepare D:

```bash
cd "$REAL"
python3 DisTkCoffee/submit_condor_pveto.py \
  --input-dir /store/group/lpcdisapptrks/nano/dev/Muon/Muon_Run2022D_customNanoAOD/260626_183436/0000 \
  --run-label Run2022D \
  --result-base validation/Jul2_22MuonValidation \
  --files-per-job 25
```

Submit D:

```bash
cd "$REAL/validation/Jul2_22MuonValidation/Run2022D/condor"
condor_submit disTkMuonPveto.submit
```

Practical note: `submit_condor_pveto.py --submit` can hit `OSError: Exec format error: 'condor_submit'` on LPC because `/usr/local/bin/condor_submit` is a shell-wrapper style file without a standard shebang. Preparing with the helper and then running `condor_submit` from the shell works.

### 5. Monitor and check outputs

Example clusters from Jul2:

```text
Run2022C: cluster 59516239 on lpcschedd5.fnal.gov, 11 jobs
Run2022D: cluster 59516240 on lpcschedd5.fnal.gov, 6 jobs
```

Monitor:

```bash
condor_q -name lpcschedd5.fnal.gov 59516239 -totals
condor_q -name lpcschedd5.fnal.gov 59516240 -totals
```

Check outputs after jobs leave the queue:

```bash
cd "$REAL"
for r in Run2022C Run2022D; do
  d=validation/Jul2_22MuonValidation/$r/condor
  echo "== $r =="
  echo "JSON:" $(find "$d" -path '*/pveto_summary.json' | wc -l)
  echo "ROOT:" $(find "$d" -path '*/pveto_summary.root' | wc -l)
  find "$d/logs" -name '*.err' -size +0c -print | sort | head
done
```

The usual nonfatal stderr line is:

```text
WARNING: While bind mounting '/cvmfs:/cvmfs': destination is already in the mount point list
```

### 6. Merge split JSON files

The split jobs write one `analysis_output_*/pveto_summary.json` per Condor job. The merged JSON is what should be used for final tables.

The Jul2 merged files already exist. To regenerate them, use this short merger:

```bash
cd "$REAL"
python3 - <<'PY'
import json, math
from pathlib import Path

def merge(inputs, output):
    merged = {"tree": None, "input_files": [], "layers": {}, "source": [], "merge_info": {}}
    for item in inputs:
        path = Path(item)
        data = json.loads(path.read_text())
        merged["source"].append(str(path))
        if merged["tree"] is None:
            merged["tree"] = data.get("tree")
        merged["input_files"].extend(data.get("input_files", []))
        for layer, payload in data.get("layers", {}).items():
            out = merged["layers"].setdefault(layer, {"cutflow": {}, "counts": {}})
            for name, value in payload.get("cutflow", {}).items():
                out["cutflow"][name] = out["cutflow"].get(name, 0) + value
            for name, count in payload.get("counts", {}).items():
                target = out["counts"].setdefault(name, {"value": 0.0, "variance": 0.0, "error": 0.0})
                target["value"] += float(count.get("value", 0.0))
                target["variance"] += float(count.get("variance", 0.0))
                target["error"] = math.sqrt(target["variance"])
    merged["merge_info"] = {"n_split_jsons": len(inputs), "n_input_files": len(merged["input_files"])}
    output = Path(output)
    output.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {output}")

base = Path("validation/Jul2_22MuonValidation")
c = sorted((base / "Run2022C/condor").glob("analysis_output_*/pveto_summary.json"))
d = sorted((base / "Run2022D/condor").glob("analysis_output_*/pveto_summary.json"))
merge(c, base / "Run2022C/merged_Run2022C_pveto_summary.json")
merge(d, base / "Run2022D/merged_Run2022D_pveto_summary.json")
merge(c + d, base / "merged_Run2022CD_pveto_summary.json")
PY
```

### 7. Make PDF tables

Example for combined C+D:

```bash
cd "$REAL"
python3 validation/scripts/make_pveto_summary_tables.py \
  --input validation/Jul2_22MuonValidation/merged_Run2022CD_pveto_summary.json \
  --output-dir validation/Jul2_22MuonValidation/pdf \
  --output-stem Run2022CD_muon_pveto_summary \
  --run-label "Run 2022C+D" \
  --sample-label "Run2022C+D Muon custom NanoAOD v1.0.0-pre; passJvmFilter temporarily treated as true"
```

The PDF path is:

```text
validation/Jul2_22MuonValidation/pdf/Run2022CD_muon_pveto_summary.pdf
```

## How the Analysis Maps Branches to Cuts

The code keeps canonical names that look like the old ntuple/MattWIP branches. `BRANCH_ALIASES` maps those names onto current customized NanoAOD branches.

Important examples:

| Canonical name in Coffee | Current NanoAOD branch or computation | Status |
| --- | --- | --- |
| `metNoMu_pt`, `metNoMu_phi` | `MetNoMu_pt`, `MetNoMu_phi` | Direct alias. |
| `passMETFilters` | `Flag_METFilters` | Direct alias for current files. |
| `passJvmFilter` | missing in current v1.0.0-pre C/D NanoAOD | Temporarily all true. Not strict. |
| `muon_pfRelIso04_dBeta` | `Muon_pfRelIso04_all` | Direct alias; NanoAOD definition is PF relative isolation dR=0.4 with delta-beta correction. |
| `muon_isTrigMatched` | `Muon_isTrigMatched` if present, otherwise recompute from `TrigObj_*` | Exact only if saved branch is present; otherwise approximate. |
| `tau_isTight` | `Tau_idDecayModeNewDMs`, `Tau_idDeepTau2018v2p5VSjet`, `Tau_idDeepTau2018v2p5VSe`, `Tau_idDeepTau2018v2p5VSmu` | Approximate hadronic tau mask. |
| `jet_isTightLepVeto` | full jet energy-fraction formula if multiplicity branches exist; otherwise `Jet_jetId` bit 4 | Current C/D files use the central fallback. |
| `trk_isFiducialECALTrack` | `IsoTrack_isFiducialECALTrack`, or fallback from `IsoTrack_minDRToMaskedEcal` | Direct if saved. |
| `trk_relativePFIso` | `IsoTrack_pfRelIso03_chg` first, then `IsoTrack_pfRelIso03_all` | Direct alias. |
| `trk_caloTotNoPU` | `IsoTrack_caloTotNoPU`, or computed from `IsoTrack_caloEm`, `IsoTrack_caloHad`, and `Rho_fixedGridRhoFastjetCentralCalo` | Formula fallback is available. |

## Current Muon Cutflow Order in Coffee

The main cumulative cutflow is in `make_tp_cutflow()` in `DisTkCoffee/disTkMuonPveto_core.py`.

Current order:

1. `HLT_IsoMu24` event bit.
2. `passMETFilters` / `Flag_METFilters`.
3. Muon tag:
   - `Muon_pt > 26`
   - `abs(Muon_eta) < 2.1`
   - `Muon_tightId`
   - `Muon_pfRelIso04_all < 0.15`
   - object trigger match from `Muon_isTrigMatched` or `TrigObj_*`
4. Probe track:
   - `IsoTrack_pt > 30`
   - `abs(IsoTrack_eta) < 2.1`
   - three eta gap cuts
   - `IsoTrack_isFiducialECALTrack` or masked-ECAL distance fallback
   - `abs(dz) > 0.5 OR abs(lambda) > 1e-3` row
   - pixel hits >= 4
   - missing inner hits == 0
   - missing middle hits == 0
   - relative PF isolation < 0.05
   - `abs(dxy) < 0.02`
   - `abs(dz) < 0.5`
   - `DeltaR(track, jet) > 0.5`
   - `passJvmFilter` row, currently all true if missing
   - track-muon mass > 10 GeV
   - `DeltaR(track, loose electron) > 0.15`
   - `DeltaR(track, hadronic tau) > 0.15`
   - calo energy < 10 GeV
   - layer bin selection
   - Z mass window
   - OS or SS charge split

The final `P_veto` counts are:

```text
p_veto_den_os = OS tag-probe pairs in Z window
p_veto_den_ss = SS tag-probe pairs in Z window
p_veto_num_os = OS denominator pairs where the probe passes muon veto and missing outer hits >= 3
p_veto_num_ss = SS denominator pairs where the probe passes muon veto and missing outer hits >= 3
```

The same-sign-subtracted probability is:

```text
P_veto = (p_veto_num_os - p_veto_num_ss) / (p_veto_den_os - p_veto_den_ss)
```

## Fully Replicated with Current Customized NanoAOD

These are reproduced directly enough for the current Coffee workflow, assuming the saved NanoAOD branches have the standard meanings.

| Cut or quantity | Branches used | Why this is considered reproduced |
| --- | --- | --- |
| Event-level `HLT_IsoMu24` | `HLT_IsoMu24` | Central event trigger bit exists. This is not object matching. |
| MET filters | `Flag_METFilters` | Current Coffee maps `passMETFilters` to this aggregate branch. |
| Muon pT and eta | `Muon_pt`, `Muon_eta` | Direct central NanoAOD quantities. |
| Tight muon ID | `Muon_tightId` | Direct central NanoAOD tight ID. |
| Muon PF isolation < 0.15 | `Muon_pfRelIso04_all` | Alias for delta-beta corrected dR=0.4 relative PF isolation. |
| Track pT and eta | `IsoTrack_pt`, `IsoTrack_eta` | Direct customized NanoAOD isotrack quantities. |
| Three eta gap cuts | `IsoTrack_eta` | Direct formula cuts. |
| ECAL noisy/dead-channel veto branch | `IsoTrack_isFiducialECALTrack`, or `IsoTrack_minDRToMaskedEcal` fallback | Current customized NanoAOD has the needed information. |
| Pixel hits >= 4 | `IsoTrack_hp_nValidPixelHits` | Direct hit-pattern branch. |
| Missing inner hits == 0 | `IsoTrack_missingInnerHits` | Direct branch. |
| Missing middle hits == 0 | `IsoTrack_missingMiddleHits` via `trk_hitDrop_missingMiddleHits` alias | Direct for data-style usage; strict hit-drop simulation may need a dedicated saved branch. |
| Track relative PF isolation < 0.05 | `IsoTrack_pfRelIso03_chg` | Direct charged isolation over track pT. |
| dxy and dz cuts | `IsoTrack_dxy`, `IsoTrack_dz` | Direct branches. |
| Track calo energy < 10 GeV | `IsoTrack_caloTotNoPU`, or computed from calo/rho branches | Current fallback matches the intended formula structure. |
| Layer bins | `IsoTrack_hp_trackerLayersWithMeasurement` | Direct branch for `Nlayers = 4`, `5`, `>= 6`, and combined `>= 4`. |
| Probe charge and missing outer hits | `IsoTrack_charge`, `IsoTrack_missingOuterHits` | Direct branches used in OS/SS counting and numerator. |

## Partially Replicated or Approximate

These are implemented, but they are not exact replicas of the old MiniAOD/V1 path.

| Cut or quantity | Current implementation | Why it is partial |
| --- | --- | --- |
| Muon object trigger matching | Uses saved `Muon_isTrigMatched` if present; otherwise recomputes from `TrigObj_id`, `TrigObj_filterBits`, `TrigObj_eta`, `TrigObj_phi`, with `DeltaR < 0.3` and IsoMu24 filter bit. | Exact only if the saved custom `Muon_isTrigMatched` branch was made with the same MiniAOD filter label. `TrigObj_*` fallback is a central NanoAOD approximation. |
| Jet tight-lepton-veto ID | Uses full energy-fraction and multiplicity formula if all jet branches exist; otherwise uses central `Jet_jetId` bit 4. | Current v1.0.0-pre files lack `Jet_chMultiplicity` and `Jet_neMultiplicity`, so the central bit fallback is used. |
| `DeltaR(track, jet) > 0.5` | Recomputed from `IsoTrack_eta/phi` and `Jet_eta/phi` after `good_jet_mask`. | Strict V1 uses track-level nearest-jet information from OSUT3/MiniAOD. Recomputing from central NanoAOD jets is not guaranteed identical. |
| Loose-electron veto | `Electron_cutBased >= 2`, then `DeltaR(track, electron) > 0.15`. | This is a reasonable Table 16-style object mask, but exact V1 parity depends on the exact electron collection and fiducial definitions used upstream. |
| Hadronic tau veto | Uses `Tau_idDecayModeNewDMs != 0`, `Tau_idDeepTau2018v2p5VSjet >= 6`, `Tau_idDeepTau2018v2p5VSe >= 1`, `Tau_idDeepTau2018v2p5VSmu >= 1`, then `DeltaR(track, tau) > 0.15`. | This follows the available Run 3 DeepTau branches, but `tau_isTight` in the old ntuplizer is a repo-local helper, not a Tau POG standard branch. Exact parity needs the same tau ID logic saved or reproduced. |
| `trk_caloTotNoPU` fallback | Computes `max(0, caloEm + caloHad - rho * pi * 0.4^2)` when no direct branch exists. | Good approximation when inputs match, but exact parity requires the producer-level value if the upstream implementation uses more detailed calo-jet logic. |
| `abs(dz) > 0.5 OR abs(lambda) > 1e-3` row | Implemented from `IsoTrack_dz` and `IsoTrack_theta`. | This row appears in the current Coffee/V1 comparison artifact but should be checked against the exact Run 3 note/code context before treating it as a physics requirement. |

## Not Strictly Replicated at Current Stage

These are the important gaps.

| Missing or non-strict item | Current state | What would be needed for strict replication |
| --- | --- | --- |
| Jet veto map event filter, `passJvmFilter` / `jetVeto2022` | Missing from current v1.0.0-pre C/D NanoAOD. Coffee currently treats it as all true with a FIXME. | Save `passJvmFilter` or `jetVeto2022` during NanoAOD production, using the correct year/era JVM config. An offline `Jet_*` recomputation can be useful but should be labeled approximate. |
| `!inTOBCrack` | No current Coffee cut and no direct current branch in the checked mapping. | Save `trk_inTOBCrack` or implement and validate the exact geometry logic. |
| `isFiducialElectronTrack` | No current Coffee cut. The V1 comparison marks this row as no NanoAOD equivalent. | Save `trk_isFiducialElectronTrack` or reproduce the exact map/mask logic. |
| `isFiducialMuonTrack` | No current Coffee cut. The V1 comparison marks this row as no NanoAOD equivalent. | Save `trk_isFiducialMuonTrack` or reproduce the exact map/mask logic. |
| `hitPattern.numberOfValidHits >= 4` | Current Coffee does not apply this row. Current branch inventory shows `IsoTrack_hp_nValidHits` exists, so this is likely fixable in analysis only. | Add `trk_hp_numberOfValidHits` mapping and a cutflow row using `IsoTrack_hp_nValidHits >= 4`. |
| Exact V1 `dRMinJet` | Current Coffee recomputes from `Jet_*`. | Save a strict track-level nearest-jet branch, such as `trk_dRMinJet`, at NanoAOD production. |
| Exact hit-drop missing outer hits | Current numerator uses `IsoTrack_missingOuterHits >= 3`. | Strict V1-style numerator wants the hit-drop/TOB-drop corrected missing outer hit quantity if available. Save that branch explicitly. |
| Optional 2017/2018 low-efficiency eta-phi veto | Intentionally ignored for 2022 C/D. | Only needed for the eras where the note/code says to apply it. |

## Why `passJvmFilter` Cannot Be Recovered Exactly Now

Corrected central NanoAOD jets are not the same thing as the JVM event decision.

The JVM event filter asks: does any selected jet land in a bad eta-phi region in the JetMET veto map? If yes, reject the event.

For 2022 C/D the relevant map configuration is the 2022Pre one:

```text
jvmFilePath: /cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/JME/2022_Summer22/jetvetomaps.json.gz
jvmTagName: Summer22_23Sep2023_RunCD_V1
jvmKeyName: jetvetomap
```

An approximate offline recomputation would use `Jet_pt`, `Jet_eta`, `Jet_phi`, `Jet_chEmEF`, `Jet_neEmEF`, and a correctionlib lookup of the veto map. That is useful for studies, but it is not the same as a saved MiniAOD/custom-NanoAOD production-time decision. The Jul2 muon validation explicitly bypasses this by setting missing `passJvmFilter` to true.

## Current Jul2 Result Summary

Inputs:

```text
Run2022C: 256 ROOT files
Run2022D: 149 ROOT files
Combined: 405 ROOT files
```

Combined-bin same-sign-subtracted values from the Jul2 merged outputs:

| Sample | N_T&P OS | N_veto OS | N_T&P SS | N_veto SS | P_veto |
| --- | ---: | ---: | ---: | ---: | ---: |
| Run2022C | 1,404,911 | 21 | 72 | 14 | 4.98e-6 |
| Run2022D | 920,152 | 17 | 47 | 13 | 4.35e-6 |
| Run2022C+D | 2,325,063 | 38 | 119 | 27 | 4.73e-6 |

Important: these numbers are with `passJvmFilter` temporarily treated as true.

## V1 MiniAOD vs OSUNano Two-File Comparison

There is now a direct V1 MiniAOD versus OSUNano/PocketCoffea comparison for two
Run2022C MiniAOD files:

```text
/store/data/Run2022C/Muon/MINIAOD/22Sep2023-v1/2520000/21e3c4bc-4477-46d8-ae3d-fc11cea5730a.root
/store/data/Run2022C/Muon/MINIAOD/22Sep2023-v1/2520000/30ab498b-216d-45e2-8e41-4d141b883cb2.root
```

The handoff is:

```text
validation/Jul2_22MuonValidation/v1_vs_osunano_comparison/HANDOFF_v1_vs_osunano_current_mismatches.md
```

Main artifacts:

```text
validation/Jul2_22MuonValidation/v1_vs_osunano_comparison/run2022C_v1_vs_osunano_cutflow_complete_comparison.pdf
validation/Jul2_22MuonValidation/v1_vs_osunano_comparison/run2022C_v1_vs_osunano_cutflow_complete_comparison.tex
```

The important result is that V1 and OSUNano/PocketCoffea agree exactly through
the muon-tag endpoint.

| Row | V1 merged | NanoAOD merged |
| --- | ---: | ---: |
| trigger / SingleMuon skim | 43,088 | 43,088 |
| MET filters | 43,022 | 43,022 |
| muon pt > 26 | 38,320 | 38,320 |
| muon abs(eta) < 2.1 | 34,756 | 34,756 |
| tight muon ID | 33,202 | 33,202 |
| muon PF rel iso < 0.15 | 30,447 | 30,447 |
| final T&P muon tag endpoint | 30,404 | 30,404 |

This means the current disagreement is not caused by the input files, event
trigger, MET filters, basic muon quantities, muon PF isolation, or final muon
tag construction.

The first direct mismatch is the first probe-track row:

| Row | V1 merged | NanoAOD merged | Nano - V1 |
| --- | ---: | ---: | ---: |
| track pt > 30 | 25,652 | 25,249 | -403 |

This is the next debugging boundary. Later rows inherit this difference and
also include row-order or definition differences, so they should not be treated
as independent evidence until the first track-row mismatch is understood.

The comparison also shows a useful diagnostic rule:

- If V1 and NanoAOD disagree before `track pt > 30`, the problem is in input
  files, trigger/MET handling, or muon tag logic.
- In the current two-file test, they do not disagree there.
- Therefore the first place to debug is the probe-track object itself:
  `IsoTrack` source, pt definition, eta definition, quality/high-purity
  requirement, and any cleaning applied before the first track row.

The handoff also warns that some rows are intentionally asymmetric. Keep them
visible in comparisons instead of forcing a fake one-to-one mapping.

V1-only or not yet represented as an explicit NanoAOD cumulative row:

```text
total
>= 1 mets with passecalBadCalibFilterUpdate
>= 1 tracks with !inTOBCrack
>= 1 tracks with isFiducialElectronTrack
>= 1 tracks with isFiducialMuonTrack
>= 1 tracks with hitPattern_.numberOfValidHits >= 4
```

NanoAOD-only or not explicitly present as a V1 text-cutflow row:

```text
>= 1 passing muon tag
>= 1 tracks |dz| > 0.5 cm OR |lambda| > 1e-3
>= 1 track-muon pairs Mtrack,muon > 10 GeV
>= 1 passing probe track before layer selection
= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV
= 1 track-muon pairs qtrack * qmuon < 0
>= 1 track nlayers >= 4 (combinedBins)
```

This comparison is useful because it turns the broad question "what is missing
from NanoAOD?" into a smaller question: why does the NanoAOD probe-track
candidate set start 403 merged events lower than V1 at the first track cut?

The recommended next strict diagnostic is to write event-level pass lists for
both workflows at two checkpoints:

```text
1. final muon-tag endpoint
2. first probe-track row, track pt > 30
```

Then compare `run:lumi:event` between V1 and NanoAOD. For events that pass V1
but fail NanoAOD at `track pt > 30`, inspect the candidate tracks and branch
values. That will separate:

- analysis-script differences that can be fixed in Coffee,
- missing branch information that requires a new NanoAOD,
- and genuine MiniAOD-versus-NanoAOD object-definition differences.

## Useful Reference Material Reviewed

Local reports and artifacts used to write this note:

| Reference | What it contributes |
| --- | --- |
| `.porting/porting_docs/osunano_v1p0pre_coffee_mattwip_pveto_mapping_report_2026-06-30.md` | Branch mapping and exactness boundaries for OSUNano v1.0.0-pre plus Coffee. |
| `.porting/porting_docs/v2_strict_pveto_replica_handoff_2026-06-20.md` | Strict V2/V1 guidance: save strict track values and `jetVeto2022`; apply JVM after `dRMinJet > 0.5`. |
| `.porting/logs/v2_strict_pveto_replica_change_log_2026-06-20.log` | Source-of-truth note that strict V2 saves `jetVeto2022` and applies it in the Pveto script. |
| `validation/branch_inventories/run2022C_teammate_nano1_branch_inventory.md` | Current branch inventory evidence, including many available `IsoTrack_*`, `Muon_*`, `Electron_*`, `Tau_*`, and missing `passJvmFilter`. Some older status rows are stale after Coffee alias updates. |
| `validation/Jul2_22MuonValidation/v1_vs_osunano_comparison/HANDOFF_v1_vs_osunano_current_mismatches.md` | Two-file V1 MiniAOD versus OSUNano/PocketCoffea diagnostic handoff; identifies exact muon-tag agreement and first mismatch at track `pt > 30`. |
| `validation/Jul2_22MuonValidation/v1_vs_osunano_comparison/run2022C_v1_vs_osunano_cutflow_complete_comparison.pdf` | Direct V1-vs-NanoAOD comparison; shows missing explicit NanoAOD rows for `!inTOBCrack`, fiducial electron/muon track, and valid hits. |
| `DisTkCoffee/disTkMuonPveto_core.py` | Current implementation source. This is the final authority for what the Coffee script actually applies today. |

Memory-backed reminders used:

- Table 16 is the muon Pveto/tag-and-probe cutflow.
- Table 23 is tau tag-and-probe and should not be used to add `MT < 40 GeV` to the muon Pveto workflow.
- Event-level HLT bits, object trigger matching, `TrigObj_*`, and saved `muon_isTrigMatched` are distinct objects and should not be treated as interchangeable.
- For strict V1 replication, producer-level track quantities such as `dRMinJet`, fiducial masks, TOB crack state, and hit-drop quantities should be saved instead of reconstructed later from generic NanoAOD branches.

## Practical Next Fixes

These are the highest-impact changes if the goal is stricter Table 16 replication.

1. Add `IsoTrack_hp_nValidHits >= 4` to the Coffee cutflow. The branch appears to exist in the current customized NanoAOD, so this is likely analysis-script-only.
2. Decide whether to implement an explicitly labeled approximate JVM recomputation from `Jet_*` and correctionlib maps, or remake NanoAOD with saved `passJvmFilter` / `jetVeto2022`.
3. Add or save direct branches for `trk_inTOBCrack`, `trk_isFiducialElectronTrack`, and `trk_isFiducialMuonTrack` if strict V1/Table 16 parity is required.
4. Save strict `trk_dRMinJet` and hit-drop corrected missing outer hits if the final goal is V1-equivalent counting rather than central-NanoAOD approximation.
5. Keep Table 16 and Table 23 separate in all future discussions. Do not add `MT < 40 GeV` to muon Pveto unless a separate source explicitly requires it for the muon table.
