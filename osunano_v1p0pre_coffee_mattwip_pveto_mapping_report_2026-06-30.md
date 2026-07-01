# OSUNano v1.0.0-pre / Coffee Replication Of DisappTrks_v2 MattWIP Muon Pveto

Date: 2026-06-30

This report explains how OSUNano custom NanoAOD plus the Coffee/PocketCoffea
analysis reproduces the `DisappTrks_v2` MattWIP muon Pveto workflow, especially
the cutflow in:

```text
DisappTrks_v2/BkgdEstimation/scripts/MuonBackground_v2_table16_pveto_json_pairfix_taujet.py
```

The intended audience is someone familiar with the original `DisappTrks_v2`
MiniAOD ntuplizer. The main point is that Coffee does not need to duplicate all
old lowercase ntuple branches. It reads central NanoAOD branches directly when
the physics quantity is already present, and uses OSUNano custom branches only
for quantities that central NanoAOD cannot recover exactly from the flat file.

## Repositories And Versions Inspected

### OSUNano

Primary local checkout:

```text
/Users/haoliangzheng/Desktop/CERN/OSUNano
```

Local Git state:

```text
branch: main
HEAD: 0f3ef818e2c9198dd1d7ea422c3e05bd982f9146
describe: v1.0.0-pre-9-g0f3ef81
HEAD subject: Update README to include common workflow section
```

Important interpretation:

```text
HEAD is not exactly on the tag v1.0.0-pre.
It is 9 commits after v1.0.0-pre.
```

The tag itself points to:

```text
tag: v1.0.0-pre
commit: 0a1e48ad0c6175307ddf415f68698f59f33dc795
tag message: Initial format for preproduction testing
commit subject: Fix default EOS path
```

For this report, the schema-relevant OSUNano source is effectively the same at
`main@0f3ef81` and `v1.0.0-pre@0a1e48a`. The diff from the tag to HEAD touched:

```text
CustomNanoAOD/data/datasets.yaml
CustomNanoAOD/scripts/hadd_and_transfer.py
CustomNanoAOD/scripts/make_configs.py
CustomNanoAOD/scripts/verify_transfer.py
README.md
```

It did not change the relevant `CustomNanoAOD/python/custom_osu_cff.py`,
`CustomNanoAOD/python/isoTracks_cff.py`, or custom producer plugins.

How to check this tag relationship yourself:

```bash
cd /Users/haoliangzheng/Desktop/CERN/OSUNano
git status --short --branch
git describe --tags --always --dirty --long
git tag --points-at HEAD
git log --oneline --decorate -n 20
git diff --name-status v1.0.0-pre..HEAD
```

### PocketCoffea_DisTk

Local shallow clone for this report:

```text
/Users/haoliangzheng/Documents/disTkOld/tmp/repo_audit_20260630/PocketCoffea_DisTk
```

Inspected commit:

```text
8c3b6f30b83f2662552a1c1d1c743ada7263b7ed
branch: main
subject: comments about muonTriggerFilterName
```

Main file:

```text
DisTkCoffee/disTkMuonPveto_core.py
```

### DisappTrks_v2 MattWIP

Local shallow clone for this report:

```text
/Users/haoliangzheng/Documents/disTkOld/tmp/repo_audit_20260630/DisappTrks_v2
```

Inspected commit:

```text
e6ca887c64142f2e102fb4f1139686cfbd683af4
branch: MattWIP
subject: fixing multiple directory bug
```

Main files:

```text
BkgdEstimation/test/ntuplizer_cfg.py
BkgdEstimation/plugins/Ntuplizer.cc
BkgdEstimation/scripts/MuonBackground_v2_table16_pveto_json_pairfix_taujet.py
```

## Executive Summary

The replication is a three-part translation:

1. `DisappTrks_v2` MattWIP makes a MiniAOD-derived flat ntuple.
2. OSUNano v1.0.0-pre makes a NanoAOD file that preserves central NanoAOD
   branches and adds disappearing-track-specific extras.
3. Coffee maps the old MattWIP branch names to NanoAOD branch names and computes
   a few derived decisions from central branches.

The clean rule is:

```text
Use central NanoAOD branches for standard object kinematics and IDs.
Use OSUNano custom branches for MiniAOD/object-method quantities absent from
central NanoAOD.
Use Coffee-side derived quantities only when the needed inputs are already in
NanoAOD and the definition is simple enough to reproduce exactly or nearly so.
```

Examples:

```text
muon_pt         -> Muon_pt                         central NanoAOD
muon_isTight    -> Muon_tightId                    central NanoAOD
jet_pt          -> Jet_pt                          central NanoAOD
jet_isTightLepVeto -> computed from central Jet_*   Coffee derived
metNoMu_pt      -> MetNoMu_pt                      OSUNano custom
trk_missingOuterHits -> IsoTrack_missingOuterHits  OSUNano custom
trk_caloTotNoPU -> computed/saved from IsoTrack calo + central-calo rho
muon_isTrigMatched -> saved branch if present, otherwise TrigObj fallback
```

The important caveat is trigger matching. MattWIP's `muon_isTrigMatched` is a
MiniAOD trigger-object filter-label match using:

```text
hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered
DeltaR(muon, trigger object) < 0.3
```

The inspected OSUNano v1.0.0-pre source does not define a custom
`Muon_isTrigMatched` producer. Current Coffee therefore uses central NanoAOD
`TrigObj_*` as the fallback. That is the intended NanoAOD-only replacement, but
it should be described as a central-NanoAOD trigger-object approximation unless
the `TrigObj_filterBits` mapping has been validated for the exact era.

## What MattWIP Does Upstream

### Trigger Skim

In `ntuplizer_cfg.py`, MattWIP defines a `SingleMuon` trigger set containing:

```text
HLT_IsoMu24_v*
```

and applies an `HLTHighLevel` filter in `process.hltFilter`.

Relevant source:

```text
BkgdEstimation/test/ntuplizer_cfg.py:89-112
BkgdEstimation/test/ntuplizer_cfg.py:214-220
```

The path then includes:

```text
process.hltFilter *
process.metFilters *
process.TrackEcalDeadChannelFilter *
process.jecAppliedJetProducer *
process.jecAppliedMetProducer *
process.ntuplizer
```

Relevant source:

```text
BkgdEstimation/test/ntuplizer_cfg.py:322-331
```

### MET Filters

MattWIP applies a second `HLTHighLevel` filter named `process.metFilters`.
For the inspected branch it uses the `met_filter_process` process name and
requires these `Flag_*` paths:

```text
Flag_goodVertices
Flag_globalSuperTightHalo2016Filter
Flag_EcalDeadCellTriggerPrimitiveFilter
Flag_BadPFMuonFilter
Flag_BadPFMuonDzFilter
Flag_hfNoisyHitsFilter
Flag_eeBadScFilter
Flag_ecalBadCalibFilter
```

Relevant source:

```text
BkgdEstimation/test/ntuplizer_cfg.py:225-239
```

### Ntuplizer Inputs

MattWIP's `process.ntuplizer = cms.EDAnalyzer("Ntuplizer", ...)` consumes:

```text
tracks       = isolatedTracks
met          = jecAppliedMetProducer:CorrectedMet
muons        = slimmedMuons
electrons    = slimmedElectrons
taus         = slimmedTaus
vertices     = offlineSlimmedPrimaryVertices
jets         = jecAppliedJetProducer:CorrectedAK4
triggerResults = TriggerResults::HLT
triggerObjects = slimmedPatTrigger
rhoAll          = fixedGridRhoFastjetAll
rhoAllCalo      = fixedGridRhoFastjetAllCalo
rhoCentralCalo  = fixedGridRhoFastjetCentralCalo
```

It also passes:

```text
muonTriggerFilterName     = hltL3crIsoL1sSingleMu22L1f0L2f10QL3f24QL3trkIsoFiltered
electronTriggerFilterName = hltEle32WPTightGsfTrackIsoFilter
triggerMatchingDR         = 0.3
tauVsEleLabel             = byVVLooseDeepTau2018v2p5VSe
tauVsMuLabel              = byLooseDeepTau2018v2p5VSmu
maskedEcalChannelStatusThreshold = 3
```

Relevant source:

```text
BkgdEstimation/test/ntuplizer_cfg.py:297-319
```

### Trigger-Object Matching In Ntuplizer.cc

The C++ ntuplizer reads `slimmedPatTrigger`, calls:

```text
obj.unpackNamesAndLabels(iEvent, *triggerResults)
obj.hasFilterLabel(muonTriggerFilterName_)
```

then stores `muon_isTrigMatched` using a `DeltaR < triggerMatchingDR_` check.

Relevant source:

```text
BkgdEstimation/plugins/Ntuplizer.cc:1008-1018
BkgdEstimation/plugins/Ntuplizer.cc:1052
```

For OSUNano/Coffee, this becomes:

```text
If Muon_isTrigMatched exists:
    read it.
Else:
    use central TrigObj_id, TrigObj_filterBits, TrigObj_eta, TrigObj_phi
    select muon trigger objects and require DeltaR < 0.3.
```

Coffee source:

```text
DisTkCoffee/disTkMuonPveto_core.py:19
DisTkCoffee/disTkMuonPveto_core.py:323-340
```

### Tau ID Labels

MattWIP does not just store tau kinematics. It uses the configured DeepTau
labels when it computes `tau_isTight`:

```text
byVVLooseDeepTau2018v2p5VSe
byLooseDeepTau2018v2p5VSmu
```

Relevant source:

```text
BkgdEstimation/test/ntuplizer_cfg.py:314-315
BkgdEstimation/plugins/Ntuplizer.cc:1091-1114
```

For current muon Pveto, the tau veto row is commented out in the MattWIP
Python script and also not active in the current Coffee muon script. If the tau
veto is re-enabled, the NanoAOD replacement is to use central:

```text
Tau_idDecayModeNewDMs
Tau_idDeepTau2018v2p5VSjet
Tau_idDeepTau2018v2p5VSe
Tau_idDeepTau2018v2p5VSmu
```

and compute the same tight-tau boolean in Coffee, or save a custom `Tau_isTight`
branch during OSUNano production.

## What OSUNano Saves

OSUNano keeps the standard central NanoAOD tables and adds custom extension
tables. The relevant source files are:

```text
/Users/haoliangzheng/Desktop/CERN/OSUNano/CustomNanoAOD/python/custom_osu_cff.py
/Users/haoliangzheng/Desktop/CERN/OSUNano/CustomNanoAOD/python/isoTracks_cff.py
/Users/haoliangzheng/Desktop/CERN/OSUNano/CustomNanoAOD/plugins/*.cc
```

### Trigger Skim Modes

OSUNano has two relevant production modes:

```text
customize_osu_Muon:
    applies a NanoAOD output skim using MUON_TRIGGERS, including HLT_IsoMu24_v*

customize_osu_NoSkim:
    does not apply an event skim; Coffee must apply HLT_IsoMu24 from the
    central NanoAOD trigger branch.
```

Relevant source:

```text
CustomNanoAOD/python/custom_osu_cff.py:7-13
CustomNanoAOD/python/custom_osu_cff.py:133-150
CustomNanoAOD/python/custom_osu_cff.py:157-160
CustomNanoAOD/python/custom_osu_cff.py:193-195
```

For Pveto reporting, this means:

```text
If OSUNano was made with customize_osu_Muon:
    the file is already SingleMuon-trigger skimmed.
If OSUNano was made with customize_osu_NoSkim:
    Coffee applies HLT_IsoMu24 as the first cutflow row.
```

### Muon Extras

OSUNano adds extra muon PF isolation and timing fields:

```text
Muon_pfIso04_sumChargedHardonPt
Muon_pfIso04_sumPUPt
Muon_pfIso04_sumNeutralEt
Muon_timeNdof
Muon_timeAtIpInOut
```

Relevant source:

```text
CustomNanoAOD/python/custom_osu_cff.py:52-60
```

For current Coffee muon Pveto, the tag-muon rows use central NanoAOD:

```text
Muon_pt
Muon_eta
Muon_phi
Muon_charge
Muon_tightId
```

The MattWIP Python script does not currently apply the muon PF isolation row
even though `Ntuplizer.cc` stores `muon_pfRelIso04_dBeta`. If that row is
restored, OSUNano has the needed components to compute it.

### MetNoMu

MattWIP stores:

```text
metNoMu_pt
metNoMu_phi
```

OSUNano saves the corresponding NanoAOD scalar table:

```text
MetNoMu_pt
MetNoMu_phi
```

using `slimmedMETs` plus `slimmedMuonsWithUserData`.

Relevant source:

```text
CustomNanoAOD/python/custom_osu_cff.py:89-95
CustomNanoAOD/plugins/MetNoMuTableProducer.cc:29-48
```

This is a custom branch, not central NanoAOD.

### IsoTrack Extras

OSUNano extends the central `IsoTrack` table with the branches needed by
MattWIP Table 16:

```text
IsoTrack_theta
IsoTrack_dxyErr
IsoTrack_dzErr
IsoTrack_deltaEta
IsoTrack_deltaPhi
IsoTrack_caloEm
IsoTrack_caloHad
IsoTrack_missingInnerHits
IsoTrack_missingMiddleHits
IsoTrack_missingOuterHits
IsoTrack_hp_nValidPixelHits
IsoTrack_hp_trackerLayersWithMeasurement
many additional hitPattern counters
IsoTrack_minDRToMaskedEcal
IsoTrack_isFiducialECALTrack
IsoTrackCrossedEcalStatus_*
IsoTrackCrossedHcalStatus_*
```

Relevant source:

```text
CustomNanoAOD/python/isoTracks_cff.py:6-28
CustomNanoAOD/python/isoTracks_cff.py:30-113
CustomNanoAOD/python/isoTracks_cff.py:119-133
CustomNanoAOD/plugins/IsoTrackExtraTableProducer.cc:37-71
CustomNanoAOD/plugins/IsoTrackMaskedEcalTableProducer.cc:99-123
CustomNanoAOD/plugins/IsoTrackCrossedStatusTableProducer.cc:23-61
```

OSUNano also calls:

```text
process.finalIsolatedTracks.finalLeptons = cms.VInputTag()
```

Relevant source:

```text
CustomNanoAOD/python/isoTracks_cff.py:138-139
```

That matters because the Pveto probe track is not supposed to disappear merely
because it is close to the tag lepton; the lepton-veto logic belongs in the
analysis cutflow/numerator split.

### ECAL Masked-Channel Distance

MattWIP has an upstream `TrackEcalDeadChannelFilter` and stores per-track
masked ECAL information in the old ntuple. OSUNano reproduces this as
per-IsoTrack branches:

```text
IsoTrack_minDRToMaskedEcal
IsoTrack_isFiducialECALTrack
```

using ECAL channel status from EventSetup and the same threshold value 3.

Relevant source:

```text
BkgdEstimation/test/ntuplizer_cfg.py:243-248
BkgdEstimation/plugins/Ntuplizer.cc:1365-1373
CustomNanoAOD/plugins/IsoTrackMaskedEcalTableProducer.cc:25-34
CustomNanoAOD/plugins/IsoTrackMaskedEcalTableProducer.cc:39-84
CustomNanoAOD/plugins/IsoTrackMaskedEcalTableProducer.cc:99-123
```

In the current MattWIP Python script, the ECAL dead-channel row is described as
already applied upstream; Coffee can either preserve that interpretation or add
an explicit row using `IsoTrack_isFiducialECALTrack`.

## What Coffee Does

Coffee keeps canonical MattWIP-like names internally and maps them to NanoAOD
branches via aliases. This keeps the cutflow readable while avoiding duplicate
old lowercase branches in the NanoAOD.

Relevant source:

```text
DisTkCoffee/disTkMuonPveto_core.py:21-43
```

The key alias examples:

```text
metNoMu_pt                  -> MetNoMu_pt
metNoMu_phi                 -> MetNoMu_phi
muon_isTrigMatched          -> Muon_isTrigMatched, if present
trk_pt                      -> IsoTrack_pt
trk_eta                     -> IsoTrack_eta
trk_phi                     -> IsoTrack_phi
trk_theta                   -> IsoTrack_theta
trk_missingInnerHits        -> IsoTrack_missingInnerHits
trk_hitDrop_missingMiddleHits -> IsoTrack_missingMiddleHits
trk_missingOuterHits        -> IsoTrack_missingOuterHits
trk_relativePFIso           -> IsoTrack_pfRelIso03_chg or IsoTrack_pfRelIso03_all
trk_hp_numberOfValidPixelHits -> IsoTrack_hp_nValidPixelHits
trk_hp_trackerLayersWithMeasurement -> IsoTrack_hp_trackerLayersWithMeasurement
```

Coffee computes these if the direct branch is absent but the component branches
are present:

```text
trk_caloTotNoPU:
    max(0, IsoTrack_caloEm + IsoTrack_caloHad
           - Rho_fixedGridRhoFastjetCentralCalo * pi * 0.4^2)

jet_isTightLepVeto:
    central Jet energy fractions and multiplicities
    or, as fallback, Jet_jetId bit 4
```

Relevant source:

```text
DisTkCoffee/disTkMuonPveto_core.py:47-65
DisTkCoffee/disTkMuonPveto_core.py:244-274
```

Coffee's current required branch list is:

```text
metNoMu_pt
metNoMu_phi
HLT_IsoMu24
passMETFilters
passJvmFilter
Muon_pt
Muon_eta
Muon_phi
Muon_charge
Muon_tightId
Electron_eta
Electron_phi
Jet_eta
Jet_phi
Jet_pt
jet_isTightLepVeto
trk_pt
trk_eta
trk_phi
trk_theta
trk_charge
trk_dxy
trk_dz
trk_missingInnerHits
trk_hitDrop_missingMiddleHits
trk_missingOuterHits
trk_relativePFIso
trk_caloTotNoPU
trk_hp_numberOfValidPixelHits
trk_hp_trackerLayersWithMeasurement
```

Relevant source:

```text
DisTkCoffee/disTkMuonPveto_core.py:80-109
```

## Branch Mapping From MattWIP To NanoAOD/Coffee

| MattWIP branch | Coffee source | Source type | Comment |
| --- | --- | --- | --- |
| `metNoMu_pt` | `MetNoMu_pt` | OSUNano custom | Built from MET plus muons. |
| `metNoMu_phi` | `MetNoMu_phi` | OSUNano custom | Built from MET plus muons. |
| `muon_pt` | `Muon_pt` | central NanoAOD | Direct read. |
| `muon_eta` | `Muon_eta` | central NanoAOD | Direct read. |
| `muon_phi` | `Muon_phi` | central NanoAOD | Direct read. |
| `muon_charge` | `Muon_charge` | central NanoAOD | Direct read. |
| `muon_isTight` | `Muon_tightId` | central NanoAOD | MattWIP uses `mu.isTightMuon(*pv)`. |
| `muon_isTrigMatched` | `Muon_isTrigMatched` if saved, else `TrigObj_*` | custom if saved, central fallback if not | Exact MiniAOD filter-label matching needs saved branch or era validation of `TrigObj_filterBits`. |
| `ele_pt` | `Electron_pt` | central NanoAOD | Not required in current Coffee muon branch list, but present centrally. |
| `ele_eta` | `Electron_eta` | central NanoAOD | Used for track-electron veto. |
| `ele_phi` | `Electron_phi` | central NanoAOD | Used for track-electron veto. |
| `ele_isTight` | `Electron_cutBased` tight WP | central NanoAOD | More relevant to electron Pveto. |
| `tau_eta` | `Tau_eta` | central NanoAOD | Tau veto is currently commented in muon Pveto. |
| `tau_phi` | `Tau_phi` | central NanoAOD | Tau veto is currently commented in muon Pveto. |
| `tau_isTight` | compute from central `Tau_id*` | central-derived or custom | Needed only if tau veto is re-enabled. |
| `jet_pt` | `Jet_pt` | central NanoAOD | Direct read. |
| `jet_eta` | `Jet_eta` | central NanoAOD | Direct read. |
| `jet_phi` | `Jet_phi` | central NanoAOD | Direct read. |
| `jet_isTightLepVeto` | computed from `Jet_neHEF`, `Jet_neEmEF`, `Jet_chHEF`, `Jet_chEmEF`, `Jet_muEF`, `Jet_chMultiplicity`, `Jet_neMultiplicity`, `Jet_eta`; fallback `Jet_jetId & 4` | central-derived | This is the example where Coffee reproduces MattWIP's tight lepton veto without adding a custom duplicate branch. |
| `trk_pt` | `IsoTrack_pt` | central NanoAOD table, OSUNano-modified selection | Direct read. |
| `trk_eta` | `IsoTrack_eta` | central NanoAOD table, OSUNano-modified selection | Direct read. |
| `trk_phi` | `IsoTrack_phi` | central NanoAOD table, OSUNano-modified selection | Direct read. |
| `trk_theta` | `IsoTrack_theta` | OSUNano custom | Saved by OSUNano. Could be derived from eta, but saved for parity. |
| `trk_charge` | `IsoTrack_charge` | central NanoAOD | Direct read. |
| `trk_dxy` | `IsoTrack_dxy` | central NanoAOD | Direct read. |
| `trk_dz` | `IsoTrack_dz` | central NanoAOD | Direct read. |
| `trk_missingInnerHits` | `IsoTrack_missingInnerHits` | OSUNano custom | HitPattern method, not central enough for strict parity. |
| `trk_hitDrop_missingMiddleHits` | `IsoTrack_missingMiddleHits` | OSUNano custom / Coffee alias | For data, hit inefficiency is zero, so this is equivalent. For nonzero hit-drop simulation, a dedicated branch would be more exact. |
| `trk_missingOuterHits` | `IsoTrack_missingOuterHits` | OSUNano custom | Used in Pveto numerator. |
| `trk_relativePFIso` | `IsoTrack_pfRelIso03_chg` or `IsoTrack_pfRelIso03_all` | central/custom depending output | MattWIP C++ defines this from charged DR03 isolation over track pt. |
| `trk_caloTotNoPU` | `IsoTrack_caloTotNoPU` if saved, else compute from `IsoTrack_caloEm`, `IsoTrack_caloHad`, `Rho_fixedGridRhoFastjetCentralCalo` | custom or central/custom-derived | Formula matches MattWIP C++. |
| `trk_hp_numberOfValidPixelHits` | `IsoTrack_hp_nValidPixelHits` | OSUNano custom | HitPattern branch. |
| `trk_hp_trackerLayersWithMeasurement` | `IsoTrack_hp_trackerLayersWithMeasurement` | OSUNano custom | Layer-bin branch. |
| `passMETFilters` | `Flag_METFilters` in current Coffee, or AND of central `Flag_*` bits | central-derived / custom aggregate | If output lacks `Flag_METFilters`, Coffee needs adapter logic or OSUNano must save aggregate. |
| `passJvmFilter` | saved `passJvmFilter` if present; otherwise Coffee defaults to true | custom or approximation | Central NanoAOD has no JVM branch. Exact MattWIP JVM parity requires saving/applying it. |

## Cutflow Mapping

Below is the row-by-row mapping of the current Coffee cutflow to MattWIP.

| Cutflow row | MattWIP implementation | Coffee/OSUNano mapping | Exactness |
| --- | --- | --- | --- |
| SingleMuon trigger skim | Upstream `process.hltFilter`, `HLT_IsoMu24_v*` | `HLT_IsoMu24` first row for NoSkim; pre-applied for skimmed `customize_osu_Muon` outputs | Exact event-level trigger bit, but object-level trigger match is separate. |
| MET filters | Upstream `process.metFilters` requiring `Flag_*` names | `passMETFilters` maps to `Flag_METFilters` or should be AND of central `Flag_*` | Exact if aggregate matches same flags/process. |
| Jet veto map filter | Upstream JVM/JEC path in MattWIP | `passJvmFilter` if saved; Coffee defaults to true if missing | Approx unless saved/applied upstream. |
| Muon `pt > 26` | `muon_pt` | `Muon_pt` | Direct central. |
| Muon `abs(eta) < 2.1` | `muon_eta` | `Muon_eta` | Direct central. |
| Tight muon ID | `muon_isTight` | `Muon_tightId` | Direct central equivalent. |
| Muon trigger matched | `muon_isTrigMatched` from MiniAOD filter label | `Muon_isTrigMatched` if saved; else `TrigObj_*` fallback | Exact only if saved or `TrigObj_filterBits` mapping is validated. |
| Muon `MT(metNoMu, muon) < 40` | `metNoMu_pt/phi`, `muon_pt/phi` | `MetNoMu_pt/phi`, `Muon_pt/phi` | Exact if `MetNoMu` definition matches. |
| Track `pt > 30` | `trk_pt` | `IsoTrack_pt` | Direct. |
| Track `abs(eta) < 2.1` | `trk_eta` | `IsoTrack_eta` | Direct. |
| Eta gaps | `trk_eta` | `IsoTrack_eta` | Direct. |
| Lepton fiducial maps | Optional MattWIP fiducial-map tools | Coffee supports fiducial-map JSON inputs | Exact if same maps/thresholds used. |
| `abs(dz) > 0.5 OR abs(lambda) > 1e-3` | `trk_dz`, `trk_theta` | `IsoTrack_dz`, `IsoTrack_theta` | Direct/custom. |
| Pixel hits `>= 4` | `trk_hp_numberOfValidPixelHits` | `IsoTrack_hp_nValidPixelHits` | OSUNano custom hitPattern. |
| Missing inner hits `= 0` | `trk_missingInnerHits` | `IsoTrack_missingInnerHits` | OSUNano custom hitPattern. |
| Missing middle hits `= 0` | `trk_hitDrop_missingMiddleHits` | `IsoTrack_missingMiddleHits` | Exact for data hit inefficiency zero; otherwise needs dedicated hit-drop branch. |
| Relative PF isolation `< 0.05` | `trk_relativePFIso` | `IsoTrack_pfRelIso03_chg` or equivalent | Needs definition check: MattWIP uses charged DR03 over pt. |
| `abs(dxy) < 0.02` | `trk_dxy` | `IsoTrack_dxy` | Direct. |
| `abs(dz) < 0.5` | `trk_dz` | `IsoTrack_dz` | Direct. |
| Track-jet `DeltaR > 0.5` | MattWIP recomputes from `jet_*` and `jet_isTightLepVeto` | Coffee recomputes from `Jet_*` and central-derived tight-lepton-veto | Same method as MattWIP script; strict V1 parity would prefer a saved per-track `dRMinJet`. |
| Pair mass `M(track,muon) > 10` | vector pair calculation | Coffee vector pair calculation | Same algorithm shape. |
| Track-electron `DeltaR > 0.15` | `ele_eta/phi` | `Electron_eta/phi` | Direct central. |
| Track-tau `DeltaR > 0.15` | commented out in current MattWIP muon script | not active in current Coffee muon script | Aligned by omission. |
| `Ecalo < 10` | `trk_caloTotNoPU` | saved/computed from calo components and central-calo rho | Exact if formula and rho match. |
| Layer bin | `trk_hp_trackerLayersWithMeasurement` | `IsoTrack_hp_trackerLayersWithMeasurement` | OSUNano custom. |
| Z mass window | vector pair mass around Z | Coffee vector pair mass around Z | Same algorithm shape. |
| OS/SS split | charge product | `IsoTrack_charge`, `Muon_charge` | Direct central/custom. |
| Pveto numerator | `DeltaR(track,muon)>0.15`, missing outer hits `>=3`, fiducial maps | Coffee applies `passesMuonVeto`, missing outer hits, fiducial maps | Same logic as MattWIP script. |

Coffee source for the active cutflow:

```text
DisTkCoffee/disTkMuonPveto_core.py:457-558
```

MattWIP source for the active cutflow:

```text
BkgdEstimation/scripts/MuonBackground_v2_table16_pveto_json_pairfix_taujet.py:137-199
BkgdEstimation/scripts/MuonBackground_v2_table16_pveto_json_pairfix_taujet.py:237-380
BkgdEstimation/scripts/MuonBackground_v2_table16_pveto_json_pairfix_taujet.py:380-456
```

## Central Branches Versus Custom Branches

### Central NanoAOD Branches Used Directly

These should not be duplicated in OSUNano:

```text
HLT_IsoMu24
Muon_pt
Muon_eta
Muon_phi
Muon_charge
Muon_tightId
Electron_pt
Electron_eta
Electron_phi
Electron_cutBased
Tau_eta
Tau_phi
Tau_idDecayModeNewDMs
Tau_idDeepTau2018v2p5VSjet
Tau_idDeepTau2018v2p5VSe
Tau_idDeepTau2018v2p5VSmu
Jet_pt
Jet_eta
Jet_phi
Jet_neHEF
Jet_neEmEF
Jet_chHEF
Jet_chEmEF
Jet_muEF
Jet_chMultiplicity
Jet_neMultiplicity
Jet_jetId
IsoTrack_pt
IsoTrack_eta
IsoTrack_phi
IsoTrack_charge
IsoTrack_dxy
IsoTrack_dz
Rho_fixedGridRhoFastjetCentralCalo
TrigObj_id
TrigObj_filterBits
TrigObj_eta
TrigObj_phi
```

### OSUNano Custom Branches Needed For MattWIP-Style Pveto

These are either not in central NanoAOD or are clearer/safer to preserve from
MiniAOD object methods:

```text
MetNoMu_pt
MetNoMu_phi
IsoTrack_theta
IsoTrack_missingInnerHits
IsoTrack_missingMiddleHits
IsoTrack_missingOuterHits
IsoTrack_hp_nValidPixelHits
IsoTrack_hp_trackerLayersWithMeasurement
IsoTrack_caloEm
IsoTrack_caloHad
IsoTrack_minDRToMaskedEcal
IsoTrack_isFiducialECALTrack
IsoTrackCrossedEcalStatus_*
IsoTrackCrossedHcalStatus_*
```

Branches that are useful if exact MattWIP parity is the target:

```text
Muon_isTrigMatched
passMETFilters
passJvmFilter
IsoTrack_caloTotNoPU
IsoTrack_relativePFIso or equivalent charged-DR03-over-pt branch
```

The inspected OSUNano v1.0.0-pre source does not define `Muon_isTrigMatched`,
`passMETFilters`, or `passJvmFilter` producers directly. Some prior validation
outputs in this workspace contained those branches, but that should be treated
as generated-output evidence rather than evidence that the public tag source
currently defines them.

## Notes For The DisappTrks_v2 Author

The Coffee/OSUNano port is not replacing the MattWIP physics selection with a
different selection. It is replacing the data layout:

```text
Old layout:
    MiniAOD -> DisappTrks_v2 Ntuplizer.cc -> lowercase flat ntuple -> uproot script

New layout:
    MiniAOD -> OSUNano custom NanoAOD -> central/custom NanoAOD branches -> Coffee
```

The cutflow mapping is done by keeping the old logical names in Coffee and
mapping each one to the correct NanoAOD branch or computation. The mapping is
explicit in `DisTkCoffee/disTkMuonPveto_core.py`.

For example:

```text
MattWIP:
    good_jet = jet_pt > 30, abs(jet_eta) < 4.5, jet_isTightLepVeto
    track passes if min DeltaR(track, good_jet) > 0.5

Coffee/NanoAOD:
    Jet_pt, Jet_eta, Jet_phi are central NanoAOD
    jet_isTightLepVeto is computed from central Jet fractions/multiplicities
    the same min-DeltaR logic is applied in Coffee
```

This is why OSUNano does not need to write a duplicate `jet_isTightLepVeto`
branch for the current workflow. The central `Jet_*` inputs are sufficient for
Coffee to reproduce that decision.

By contrast, OSUNano does need to save hit-pattern and calo/masked-ECAL
branches because those come from MiniAOD object methods or EventSetup state and
are not fully recoverable from ordinary central NanoAOD after production.

## Exactness Caveats

### 1. Object-level trigger matching

Event-level `HLT_IsoMu24` is not the same as object-level
`muon_isTrigMatched`.

MattWIP object matching uses the literal MiniAOD trigger-object filter label.
Coffee can approximate this from central `TrigObj_*`, but for exact parity one
of these must be true:

```text
1. OSUNano saves Muon_isTrigMatched with the same filter-label logic, or
2. The central TrigObj_filterBits bit used by Coffee is validated against
   the exact MattWIP filter-label match for the data era.
```

### 2. MET filter aggregate

MattWIP applies named `Flag_*` paths upstream. Coffee currently maps
`passMETFilters` to `Flag_METFilters`. If an OSUNano file contains only
individual central `Flag_*` branches, Coffee should either:

```text
1. AND the same individual flags in analysis, or
2. read a saved OSUNano aggregate passMETFilters branch.
```

### 3. Jet veto map filter

Central NanoAOD does not contain MattWIP's JVM event decision. Current Coffee
defaults `passJvmFilter` to true if the branch is missing. That is acceptable
only if the input was already made with the JVM filter upstream or if the report
explicitly states that the JVM row is approximated.

### 4. Track-jet requirement

The current MattWIP Python script recomputes track-jet `DeltaR` from saved jet
arrays. Coffee mirrors that behavior from central `Jet_*`.

For strict historical V1 replication, however, the safest representation is a
saved track-level nearest-good-jet value, not a later recomputation from flat
jet arrays. That distinction should be stated separately:

```text
MattWIP-style script replication:
    recompute from Jet_pt, Jet_eta, Jet_phi, jet_isTightLepVeto.

Strict V1-style replication:
    save and use the V1-equivalent per-track dRMinJet value.
```

### 5. Hit-drop missing middle hits

MattWIP has `trk_hitDrop_missingMiddleHits`. Coffee maps this to
`IsoTrack_missingMiddleHits`. For data this is expected to be equivalent when
hit inefficiency is zero. For MC or any study that turns on hit-drop
inefficiency, OSUNano should save the exact hit-drop branch.

## Bottom Line

OSUNano v1.0.0-pre plus Coffee can reproduce the MattWIP muon Pveto cutflow in
the intended NanoAOD way:

```text
central NanoAOD:
    muon/electron/tau/jet kinematics, muon tight ID, HLT bit, TrigObj fallback,
    jet ID ingredients, standard flags, rho

OSUNano custom:
    MetNoMu, IsoTrack hit-pattern details, IsoTrack calo components, masked ECAL
    distance/status, and optional exact trigger/MET/JVM decisions

Coffee:
    old-branch aliasing, central-derived jet tight lepton veto, caloNoPU formula,
    trigger-object fallback, and MattWIP-style cutflow/counting
```

The explanation to the DisappTrks_v2 author should emphasize that the port is
not a new physics definition. It is a schema translation plus a few explicit
analysis-time computations from central NanoAOD branches. The exactness
boundaries are object-level trigger matching, MET-filter aggregation, JVM
filtering, and strict V1 per-track nearest-jet behavior.
