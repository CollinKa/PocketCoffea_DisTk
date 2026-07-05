#!/usr/bin/env python3
from __future__ import annotations

import argparse
import glob
import json
import math
import subprocess
import sys
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path
from typing import Iterable

import awkward as ak
import numpy as np
import uproot

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

RUN3_MET_AND_ISOTRK_TRIGGERS = (
    "HLT_MET105_IsoTrk50",
    "HLT_MET120_IsoTrk50",
    "HLT_PFMET105_IsoTrk50",
)

RUN3_MET_INCLUSIVE_TRIGGERS = (
    "HLT_PFMET120_PFMHT120_IDTight",
    "HLT_PFMET130_PFMHT130_IDTight",
    "HLT_PFMET140_PFMHT140_IDTight",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60",
    "HLT_PFMETNoMu110_PFMHTNoMu110_IDTight_FilterHF",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight_FilterHF",
    "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight_FilterHF",
    "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight_FilterHF",
    "HLT_PFMETNoMu120_PFMHTNoMu120_IDTight",
    "HLT_PFMETNoMu130_PFMHTNoMu130_IDTight",
    "HLT_PFMETNoMu140_PFMHTNoMu140_IDTight",
    "HLT_PFMET120_PFMHT120_IDTight_PFHT60",
)

RUN3_MET_FILTERS = (
    "Flag_goodVertices",
    "Flag_EcalDeadCellTriggerPrimitiveFilter",
    "Flag_BadPFMuonFilter",
    "Flag_BadPFMuonDzFilter",
    "Flag_globalSuperTightHalo2016Filter",
    "Flag_hfNoisyHitsFilter",
    "Flag_eeBadScFilter",
)

JET_VETO_CONFIGS = {
    "2022_preEE": {
        "file": "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/JME/2022_Summer22/jetvetomaps.json.gz",
        "name": "Summer22_23Sep2023_RunCD_V1",
        "nano_version": 12,
    },
    "2022_postEE": {
        "file": "/cvmfs/cms.cern.ch/rsync/cms-nanoAOD/jsonpog-integration/POG/JME/2022_Summer22EE/jetvetomaps.json.gz",
        "name": "Summer22EE_23Sep2023_RunEFG_V1",
        "nano_version": 12,
    },
}

JER_CONFIGS = {
    "2022_preEE": {
        "file": "/cvmfs/cms-griddata.cern.ch/cat/metadata/JME/Run3-22CDSep23-Summer22-NanoAODv12/2026-04-13/jet_jerc.json.gz",
        "resolution": "Summer22_22Sep2023_JRV1_MC_PtResolution_AK4PFPuppi",
        "scale_factor": "Summer22_22Sep2023_JRV1_MC_ScaleFactor_AK4PFPuppi",
    },
    "2022_postEE": {
        "file": "/cvmfs/cms-griddata.cern.ch/cat/metadata/JME/Run3-22EFGSep23-Summer22EE-NanoAODv12/2026-04-13/jet_jerc.json.gz",
        "resolution": "Summer22EE_22Sep2023_JRV1_MC_PtResolution_AK4PFPuppi",
        "scale_factor": "Summer22EE_22Sep2023_JRV1_MC_ScaleFactor_AK4PFPuppi",
    },
}

ERA_TO_JET_VETO_YEAR = {
    "C": "2022_preEE",
    "D": "2022_preEE",
    "E": "2022_postEE",
    "F": "2022_postEE",
    "G": "2022_postEE",
}

ERA_TO_MISSING_HITS_PERIOD = {
    "C": "2022CD",
    "D": "2022CD",
    "E": "2022EFG",
    "F": "2022EFG",
    "G": "2022EFG",
}

MISSING_HITS_CORRECTIONS = {
    "2022CD": {
        "dropTOBProbability": 0.000424052,
        "preTOBDropHitInefficiency": 3.230738793e-10,
        "postTOBDropHitInefficiency": 0.786001157,
        "hitInefficiency": 0.003203431,
    },
    "2022EFG": {
        "dropTOBProbability": 0.000665108,
        "preTOBDropHitInefficiency": 0.003683874,
        "postTOBDropHitInefficiency": 0.779060071,
        "hitInefficiency": 0.005060125,
    },
}

BASE_BRANCHES = (
    "event",
    "genWeight",
    "PV_npvsGood",
    "MET_pt",
    "MET_phi",
    "Flag_ecalBadCalibFilter",
    "Flag_METFilters",
    "Jet_pt",
    "Jet_eta",
    "Jet_phi",
    "Jet_genJetIdx",
    "Jet_jetId",
    "Jet_neEmEF",
    "Jet_neHEF",
    "Jet_chEmEF",
    "Jet_muEF",
    "GenJet_pt",
    "GenJet_eta",
    "GenJet_phi",
    "Rho_fixedGridRhoFastjetAll",
    "Muon_pt",
    "Muon_eta",
    "Muon_phi",
    "Electron_eta",
    "Electron_phi",
    "Tau_eta",
    "Tau_phi",
    "Tau_idDecayModeNewDMs",
    "Tau_idDeepTau2018v2p5VSe",
    "Tau_idDeepTau2018v2p5VSjet",
    "Tau_idDeepTau2018v2p5VSmu",
    "IsoTrack_pt",
    "IsoTrack_eta",
    "IsoTrack_phi",
    "IsoTrack_theta",
    "IsoTrack_dxy",
    "IsoTrack_dz",
    "IsoTrack_missingInnerHits",
    "IsoTrack_missingMiddleHits",
    "IsoTrack_missingOuterHits",
    "IsoTrack_pfIso03_chg",
    "IsoTrack_pfRelIso03_chg",
    "IsoTrack_hp_nValidPixelHits",
    "IsoTrack_hp_nValidHits",
    "IsoTrack_hp_trackerLayersWithMeasurement",
    "IsoTrack_hp_stripLayersWithMeasurement",
    "IsoTrack_hp_stripTOBLayersWithMeasurement",
    "IsoTrack_isFiducialECALTrack",
    "IsoTrack_minDRToMaskedEcal",
    "IsoTrack_caloEm",
    "IsoTrack_caloHad",
)


def parse_inputs(items: Iterable[str]) -> list[str]:
    files: list[str] = []
    for item in items:
        path = Path(item)
        if item.endswith(".txt") and path.exists():
            files.extend(
                line.strip()
                for line in path.read_text().splitlines()
                if line.strip() and not line.strip().startswith("#")
            )
        elif item.startswith("/store/") and not item.endswith(".root"):
            files.extend(eos_find_root_files(item))
        elif any(ch in item for ch in "*?["):
            files.extend(sorted(glob.glob(item)))
        else:
            files.append(item)
    return sorted(dict.fromkeys(files))


def eos_find_root_files(path: str) -> list[str]:
    proc = subprocess.run(
        ["eos", "root://cmseos.fnal.gov", "find", "-f", path],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    files = []
    for line in proc.stdout.splitlines():
        if not line.endswith(".root"):
            continue
        if line.startswith("/eos/uscms/store/"):
            line = line.replace("/eos/uscms/store/", "/store/", 1)
        files.append(f"root://cmseos.fnal.gov/{line}")
    return sorted(files)


def has_branch(available: set[str], name: str) -> bool:
    if name in available:
        return True
    if "_" not in name:
        return False
    collection, field = name.split("_", 1)
    return f"{collection}_{field}" in available


def exact_branch(arrays, name: str):
    if name in arrays.fields:
        return arrays[name]
    if "_" in name:
        collection, field = name.split("_", 1)
        if collection in arrays.fields and field in arrays[collection].fields:
            return arrays[collection][field]
    raise KeyError(name)


def optional_branch(arrays, name: str):
    try:
        return exact_branch(arrays, name)
    except KeyError:
        return None


def input_branches_for_available(available: set[str], missing_hits_mode: str) -> list[str]:
    needed = set()
    for name in BASE_BRANCHES:
        if name in available:
            needed.add(name)
    for name in RUN3_MET_AND_ISOTRK_TRIGGERS + RUN3_MET_INCLUSIVE_TRIGGERS + RUN3_MET_FILTERS:
        if name in available:
            needed.add(name)
    if missing_hits_mode != "stochastic":
        needed.discard("event")
        needed.discard("IsoTrack_hp_stripLayersWithMeasurement")
        needed.discard("IsoTrack_hp_stripTOBLayersWithMeasurement")
    return sorted(needed)


def missing_required(available: set[str], missing_hits_mode: str) -> list[str]:
    required = set(BASE_BRANCHES)
    if missing_hits_mode != "stochastic":
        required.discard("event")
        required.discard("IsoTrack_hp_stripLayersWithMeasurement")
        required.discard("IsoTrack_hp_stripTOBLayersWithMeasurement")
    if "IsoTrack_pfIso03_chg" in available:
        required.discard("IsoTrack_pfRelIso03_chg")
    if "IsoTrack_isFiducialECALTrack" in available:
        required.discard("IsoTrack_minDRToMaskedEcal")
    if "IsoTrack_theta" not in available and "IsoTrack_eta" in available:
        required.discard("IsoTrack_theta")
    return sorted(name for name in required if name not in available)


def delta_phi(phi1, phi2):
    return (phi1 - phi2 + math.pi) % (2.0 * math.pi) - math.pi


def delta_r(eta1, phi1, eta2, phi2):
    return np.sqrt((eta1 - eta2) ** 2 + delta_phi(phi1, phi2) ** 2)


def jet_tight_lep_veto(arrays):
    jet_id = exact_branch(arrays, "Jet_jetId")
    return np.bitwise_and(jet_id, 1 << 2) != 0


def valid_event_jets(arrays):
    return (
        (exact_branch(arrays, "Jet_pt") > 30.0)
        & (np.abs(exact_branch(arrays, "Jet_eta")) < 4.5)
        & jet_tight_lep_veto(arrays)
    )


def event_weight(arrays):
    gen_weight = optional_branch(arrays, "genWeight")
    if gen_weight is None:
        return np.ones(len(arrays), dtype=float)
    return np.sign(ak.to_numpy(gen_weight))


def no_mu_met(arrays):
    met_px = exact_branch(arrays, "MET_pt") * np.cos(exact_branch(arrays, "MET_phi"))
    met_py = exact_branch(arrays, "MET_pt") * np.sin(exact_branch(arrays, "MET_phi"))
    mu_px = ak.sum(exact_branch(arrays, "Muon_pt") * np.cos(exact_branch(arrays, "Muon_phi")), axis=1)
    mu_py = ak.sum(exact_branch(arrays, "Muon_pt") * np.sin(exact_branch(arrays, "Muon_phi")), axis=1)
    x = met_px + mu_px
    y = met_py + mu_py
    return np.hypot(x, y), np.arctan2(y, x)


def trigger_mask(arrays):
    masks = []
    for name in RUN3_MET_AND_ISOTRK_TRIGGERS + RUN3_MET_INCLUSIVE_TRIGGERS:
        branch = optional_branch(arrays, name)
        if branch is not None:
            masks.append(branch)
    if not masks:
        return np.zeros(len(arrays), dtype=bool)
    out = masks[0]
    for mask in masks[1:]:
        out = out | mask
    return out


def met_filter_mask(arrays):
    flag_met_filters = optional_branch(arrays, "Flag_METFilters")
    if flag_met_filters is not None:
        return flag_met_filters
    out = np.ones(len(arrays), dtype=bool)
    for name in RUN3_MET_FILTERS:
        branch = optional_branch(arrays, name)
        if branch is not None:
            out = out & branch
    return out


def dijet_max_delta_phi(arrays, jet_mask):
    phis = exact_branch(arrays, "Jet_phi")[jet_mask]
    pairs = ak.combinations(phis, 2, fields=("a", "b"), axis=1)
    values = np.abs(delta_phi(pairs.a, pairs.b))
    return ak.fill_none(ak.max(values, axis=1), -999.0)


def leading_jet_phi(arrays, jet_mask):
    pts = exact_branch(arrays, "Jet_pt")[jet_mask]
    phis = exact_branch(arrays, "Jet_phi")[jet_mask]
    order = ak.argsort(pts, ascending=False, axis=1)
    return ak.firsts(phis[order], axis=1)


def min_delta_r_to_objects(src_eta, src_phi, obj_eta, obj_phi, obj_mask=None):
    if obj_mask is not None:
        obj_eta = obj_eta[obj_mask]
        obj_phi = obj_phi[obj_mask]
    src = ak.zip({"eta": src_eta, "phi": src_phi})
    obj = ak.zip({"eta": obj_eta, "phi": obj_phi})
    pairs = ak.cartesian({"src": src, "obj": obj}, nested=True, axis=1)
    dr = delta_r(pairs.src.eta, pairs.src.phi, pairs.obj.eta, pairs.obj.phi)
    return ak.fill_none(ak.min(dr, axis=2), 999.0)


class Hist2DLookup:
    def __init__(self, values, x_edges, y_edges):
        self.values = np.asarray(values)
        self.x_edges = np.asarray(x_edges)
        self.y_edges = np.asarray(y_edges)

    @classmethod
    def from_root(cls, path: Path, name: str):
        with uproot.open(path) as fin:
            values, x_edges, y_edges = fin[name].to_numpy()
        return cls(values, x_edges, y_edges)

    def lookup(self, eta, phi):
        counts = ak.num(eta, axis=1)
        flat_eta = np.asarray(ak.to_numpy(ak.flatten(eta, axis=1)))
        flat_phi = np.asarray(ak.to_numpy(ak.flatten(phi, axis=1)))
        if len(flat_eta) == 0:
            return ak.unflatten(np.array([], dtype=float), counts)
        ix = np.searchsorted(self.x_edges, flat_eta, side="right") - 1
        iy = np.searchsorted(self.y_edges, flat_phi, side="right") - 1
        ix = np.clip(ix, 0, self.values.shape[0] - 1)
        iy = np.clip(iy, 0, self.values.shape[1] - 1)
        return ak.unflatten(self.values[ix, iy], counts)


class FiducialMap:
    def __init__(self, eta_points, phi_points, min_delta_r):
        self.eta_points = np.asarray(eta_points, dtype=float)
        self.phi_points = np.asarray(phi_points, dtype=float)
        self.min_delta_r = float(min_delta_r)

    @classmethod
    def from_root(cls, path: Path, threshold: float):
        with uproot.open(path) as fin:
            before, x_edges, y_edges = fin["beforeVeto"].to_numpy()
            after, _, _ = fin["afterVeto"].to_numpy()

        occupied = before > 0.0
        if not np.any(occupied):
            return cls([], [], 0.05)

        mean = np.sum(after[occupied]) / np.sum(before[occupied])
        ratio = np.zeros_like(after, dtype=float)
        ratio[occupied] = after[occupied] / before[occupied]
        n_bins = int(np.count_nonzero(occupied))
        std = 0.0
        if n_bins > 1:
            std = math.sqrt(np.sum((ratio[occupied] - mean) ** 2) / (n_bins - 1))

        x_width = np.diff(x_edges)
        y_width = np.diff(y_edges)
        max_bin_radius = float(np.max(np.hypot(0.5 * x_width[:, None], 0.5 * y_width[None, :])))
        min_delta_r = max(0.05, max_bin_radius)

        hot = (ratio != 0.0) & ((ratio - mean) > threshold * std)
        x_centers = 0.5 * (x_edges[:-1] + x_edges[1:])
        y_centers = 0.5 * (y_edges[:-1] + y_edges[1:])
        ix, iy = np.where(hot)
        return cls(x_centers[ix], y_centers[iy], min_delta_r)

    def track_mask(self, trk_eta, trk_phi):
        mask = ak.ones_like(trk_eta, dtype=bool)
        for eta, phi in zip(self.eta_points, self.phi_points):
            mask = mask & (delta_r(trk_eta, trk_phi, eta, phi) >= self.min_delta_r)
        return mask

    def summary(self):
        return {"n_veto_points": int(len(self.eta_points)), "min_delta_r": self.min_delta_r}


@lru_cache(maxsize=16)
def load_correction(path: str, name: str):
    import correctionlib

    return correctionlib.CorrectionSet.from_file(path)[name]


@lru_cache(maxsize=32)
def load_fiducial_map(path: str, threshold: float):
    return FiducialMap.from_root(Path(path), threshold)


def compute_pocketcoffea_jet_id(arrays, config):
    eta = np.abs(exact_branch(arrays, "Jet_eta"))
    if int(config["nano_version"]) >= 15:
        raise RuntimeError("NanoAOD v15 jet ID correction is not configured in this 2022 signal runner.")

    jet_id = exact_branch(arrays, "Jet_jetId")
    pass_tight = ak.where(
        eta <= 2.7,
        np.bitwise_and(jet_id, 1 << 1) != 0,
        ak.where(
            (eta > 2.7) & (eta <= 3.0),
            (np.bitwise_and(jet_id, 1 << 1) != 0) & (exact_branch(arrays, "Jet_neHEF") < 0.99),
            (np.bitwise_and(jet_id, 1 << 1) != 0) & (exact_branch(arrays, "Jet_neEmEF") < 0.4),
        ),
    )
    pass_tight_lep_veto = ak.where(
        eta <= 2.7,
        pass_tight & (exact_branch(arrays, "Jet_muEF") < 0.8) & (exact_branch(arrays, "Jet_chEmEF") < 0.8),
        pass_tight,
    )
    return pass_tight * (1 << 1) | pass_tight_lep_veto * (1 << 2)


def get_correction_input_names(correction):
    return tuple(item.name for item in correction.inputs)


def evaluate_resolution(correction, eta, pt, rho):
    names = get_correction_input_names(correction)
    values = {"JetEta": eta, "JetPt": pt, "Rho": rho}
    return correction.evaluate(*(values[name] for name in names))


def evaluate_jer_scale_factor(correction, eta, pt):
    names = get_correction_input_names(correction)
    values = {
        "JetEta": eta,
        "JetPt": pt,
        "systematic": "nom",
    }
    return correction.evaluate(*(values[name] for name in names))


def stable_normal(seed_value: int):
    rng = np.random.default_rng(int(seed_value))
    return rng.normal()


def hybrid_jer_smeared_pt(arrays, config):
    jet_pt = exact_branch(arrays, "Jet_pt")
    counts = ak.num(jet_pt, axis=1)
    flat_pt = np.asarray(ak.to_numpy(ak.flatten(jet_pt, axis=1)), dtype=float)
    if len(flat_pt) == 0:
        return jet_pt

    flat_eta = np.asarray(ak.to_numpy(ak.flatten(exact_branch(arrays, "Jet_eta"), axis=1)), dtype=float)
    flat_phi = np.asarray(ak.to_numpy(ak.flatten(exact_branch(arrays, "Jet_phi"), axis=1)), dtype=float)
    flat_event = np.repeat(np.asarray(ak.to_numpy(exact_branch(arrays, "event")), dtype=np.int64), np.asarray(ak.to_numpy(counts)))
    flat_jet_index = np.asarray(ak.to_numpy(ak.flatten(ak.local_index(jet_pt, axis=1), axis=1)), dtype=np.int64)

    jet_gen_idx = exact_branch(arrays, "Jet_genJetIdx")
    n_gen = ak.num(exact_branch(arrays, "GenJet_pt"), axis=1)
    valid_gen = (jet_gen_idx >= 0) & (jet_gen_idx < n_gen)
    safe_gen_idx = ak.where(valid_gen, jet_gen_idx, 0)
    gen_pt_padded = ak.pad_none(exact_branch(arrays, "GenJet_pt"), 1, axis=1)
    gen_eta_padded = ak.pad_none(exact_branch(arrays, "GenJet_eta"), 1, axis=1)
    gen_phi_padded = ak.pad_none(exact_branch(arrays, "GenJet_phi"), 1, axis=1)
    matched_gen_pt = ak.fill_none(ak.mask(gen_pt_padded[safe_gen_idx], valid_gen), -999.0)
    matched_gen_eta = ak.fill_none(ak.mask(gen_eta_padded[safe_gen_idx], valid_gen), -999.0)
    matched_gen_phi = ak.fill_none(ak.mask(gen_phi_padded[safe_gen_idx], valid_gen), -999.0)
    flat_gen_pt = np.asarray(ak.to_numpy(ak.flatten(matched_gen_pt, axis=1)), dtype=float)
    flat_gen_eta = np.asarray(ak.to_numpy(ak.flatten(matched_gen_eta, axis=1)), dtype=float)
    flat_gen_phi = np.asarray(ak.to_numpy(ak.flatten(matched_gen_phi, axis=1)), dtype=float)

    rho = np.asarray(ak.to_numpy(exact_branch(arrays, "Rho_fixedGridRhoFastjetAll")), dtype=float)
    flat_rho = np.repeat(rho, np.asarray(ak.to_numpy(counts)))

    resolution = load_correction(str(config["file"]), str(config["resolution"]))
    scale_factor = load_correction(str(config["file"]), str(config["scale_factor"]))
    sigma = np.asarray(evaluate_resolution(resolution, flat_eta, flat_pt, flat_rho), dtype=float)
    sf = np.asarray(evaluate_jer_scale_factor(scale_factor, flat_eta, flat_pt), dtype=float)

    gen_dr = np.sqrt((flat_eta - flat_gen_eta) ** 2 + ((flat_phi - flat_gen_phi + math.pi) % (2.0 * math.pi) - math.pi) ** 2)
    matched = (
        (flat_gen_pt > 0.0)
        & (gen_dr < 0.2)
        & (np.abs(flat_pt - flat_gen_pt) < (3.0 * sigma * flat_pt))
    )

    c_jer = np.ones_like(flat_pt, dtype=float)
    valid_pt = flat_pt > 0.0
    c_jer[matched & valid_pt] = 1.0 + (sf[matched & valid_pt] - 1.0) * (
        flat_pt[matched & valid_pt] - flat_gen_pt[matched & valid_pt]
    ) / flat_pt[matched & valid_pt]

    unmatched = ~matched
    smear_width = sigma * np.sqrt(np.maximum(sf * sf - 1.0, 0.0))
    random_values = np.asarray(
        [stable_normal(stable_seed(int(event), int(index))) for event, index in zip(flat_event, flat_jet_index)],
        dtype=float,
    )
    c_jer[unmatched] = 1.0 + random_values[unmatched] * smear_width[unmatched]
    c_jer = np.maximum(c_jer, 0.0)
    return ak.unflatten(c_jer * flat_pt, counts)


def lookup_pocketcoffea_jet_veto_map(eta, phi, config):
    counts = ak.num(eta, axis=1)
    flat_eta = np.asarray(ak.to_numpy(ak.flatten(eta, axis=1)))
    flat_phi = np.asarray(ak.to_numpy(ak.flatten(phi, axis=1)))
    if len(flat_eta) == 0:
        return ak.unflatten(np.array([], dtype=np.float32), counts)
    corr = load_correction(str(config["file"]), str(config["name"]))
    flat_phi = np.clip(flat_phi, -3.14159, 3.14159)
    values = corr.evaluate("jetvetomap", flat_eta, flat_phi)
    return ak.unflatten(values, counts)


def pass_pocketcoffea_jet_veto(arrays, config):
    jet_id_corrected = compute_pocketcoffea_jet_id(arrays, config)
    mask_for_veto_map = (
        (jet_id_corrected >= 6)
        & (np.abs(exact_branch(arrays, "Jet_eta")) < 5.19)
        & (exact_branch(arrays, "Jet_pt") > 15.0)
        & ((exact_branch(arrays, "Jet_neEmEF") + exact_branch(arrays, "Jet_chEmEF")) < 0.9)
    )
    values = lookup_pocketcoffea_jet_veto_map(
        exact_branch(arrays, "Jet_eta")[mask_for_veto_map],
        exact_branch(arrays, "Jet_phi")[mask_for_veto_map],
        config,
    )
    return ak.sum(values, axis=-1) == 0


def tau_had_mask(arrays):
    decay = exact_branch(arrays, "Tau_idDecayModeNewDMs") > 0
    vsjet = np.bitwise_and(exact_branch(arrays, "Tau_idDeepTau2018v2p5VSjet"), 32) != 0
    vse = np.bitwise_and(exact_branch(arrays, "Tau_idDeepTau2018v2p5VSe"), 1) != 0
    vsmu = np.bitwise_and(exact_branch(arrays, "Tau_idDeepTau2018v2p5VSmu"), 1) != 0
    return decay & vsjet & vse & vsmu


def in_tob_crack(arrays):
    theta = optional_branch(arrays, "IsoTrack_theta")
    if theta is None:
        theta = 2.0 * np.arctan(np.exp(-exact_branch(arrays, "IsoTrack_eta")))
    return (np.abs(exact_branch(arrays, "IsoTrack_dz")) < 0.5) & (
        np.abs((math.pi / 2.0) - theta) < 1.0e-3
    )


def fiducial_ecal_track(arrays):
    saved = optional_branch(arrays, "IsoTrack_isFiducialECALTrack")
    if saved is not None:
        return saved
    min_dr = exact_branch(arrays, "IsoTrack_minDRToMaskedEcal")
    return (min_dr < 0.0) | (min_dr > 0.05)


def track_relative_charged_iso(arrays):
    iso = optional_branch(arrays, "IsoTrack_pfIso03_chg")
    if iso is not None:
        return iso / exact_branch(arrays, "IsoTrack_pt")
    return exact_branch(arrays, "IsoTrack_pfRelIso03_chg")


def stable_seed(event_number: int, track_index: int):
    value = int(event_number) & 0xFFFFFFFFFFFFFFFF
    value ^= (int(track_index) + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
    value ^= (value >> 30)
    value = (value * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
    value ^= (value >> 27)
    value = (value * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
    value ^= (value >> 31)
    return value & 0xFFFFFFFF


def hit_drop_missing_hits(arrays, period: str, mode: str):
    middle = exact_branch(arrays, "IsoTrack_missingMiddleHits")
    outer = exact_branch(arrays, "IsoTrack_missingOuterHits")
    if mode == "saved":
        return middle, outer

    params = MISSING_HITS_CORRECTIONS[period]
    counts = ak.num(middle, axis=1)
    events = np.asarray(ak.to_numpy(exact_branch(arrays, "event")))
    flat_events = np.repeat(events, np.asarray(ak.to_numpy(counts)))
    flat_track_index = np.asarray(ak.to_numpy(ak.flatten(ak.local_index(middle, axis=1), axis=1)))
    flat_middle = np.asarray(ak.to_numpy(ak.flatten(middle, axis=1)))
    flat_outer = np.asarray(ak.to_numpy(ak.flatten(outer, axis=1)))
    strip_layers = np.asarray(ak.to_numpy(ak.flatten(exact_branch(arrays, "IsoTrack_hp_stripLayersWithMeasurement"), axis=1)))
    tob_layers = np.asarray(ak.to_numpy(ak.flatten(exact_branch(arrays, "IsoTrack_hp_stripTOBLayersWithMeasurement"), axis=1)))

    out_middle = np.empty_like(flat_middle, dtype=np.int32)
    out_outer = np.empty_like(flat_outer, dtype=np.int32)
    for i, (event, trk_idx) in enumerate(zip(flat_events, flat_track_index)):
        rng = np.random.default_rng(stable_seed(int(event), int(trk_idx)))
        drop_tob = rng.random() < params["dropTOBProbability"]
        hit_drop_prob = (
            params["postTOBDropHitInefficiency"]
            if drop_tob
            else params["preTOBDropHitInefficiency"]
        )
        drop_hits = rng.random(50) < hit_drop_prob
        drop_middle_hits = rng.random(50) < params["hitInefficiency"]
        n_layers = int(max(0, min(50, strip_layers[i] - (tob_layers[i] if drop_tob else 0))))

        extra_middle = 0
        count_missing_middle = False
        for j in range(n_layers):
            hit = not drop_middle_hits[j]
            if (not hit) and count_missing_middle:
                extra_middle += 1
            elif hit:
                count_missing_middle = True

        extra_outer = 0
        for j in range(n_layers):
            if drop_hits[j]:
                extra_outer += 1
            else:
                break

        out_middle[i] = int(flat_middle[i]) + extra_middle
        out_outer[i] = int(flat_outer[i]) + (int(tob_layers[i]) if drop_tob else 0) + extra_outer

    return ak.unflatten(out_middle, counts), ak.unflatten(out_outer, counts)


def build_cutflow(arrays, config):
    cutflow = OrderedDict()
    event_mask = np.ones(len(arrays), dtype=bool)
    weights = event_weight(arrays)

    def add(label: str, mask) -> None:
        nonlocal event_mask
        event_mask = event_mask & mask
        cutflow[label] = float(ak.sum(weights[event_mask]))

    cutflow["total"] = float(ak.sum(weights))
    add("trigger", trigger_mask(arrays))
    add("MET filter", met_filter_mask(arrays))
    add(">= 1 mets with passEcalBadCalibFilterUpdate", exact_branch(arrays, "Flag_ecalBadCalibFilter"))
    add(">= 1 good primary vertices", exact_branch(arrays, "PV_npvsGood") > 0)

    no_mu_pt, no_mu_phi = no_mu_met(arrays)
    add(">= 1 mets with noMuPt > 120", no_mu_pt > 120.0)

    smeared_pt = hybrid_jer_smeared_pt(arrays, config["jer"])
    jets = smeared_pt > 110.0
    add(">= 1 jets with smearedPt > 110", ak.any(jets, axis=1))
    jets = jets & (np.abs(exact_branch(arrays, "Jet_eta")) < 2.4)
    add(">= 1 jets with fabs(eta) < 2.4", ak.any(jets, axis=1))
    jets = jets & jet_tight_lep_veto(arrays)
    add(">= 1 jet passing TightLepVeto ID", ak.any(jets, axis=1))

    event_jets = valid_event_jets(arrays)
    add("veto pairs of jets with DeltaPhi > 2.5", dijet_max_delta_phi(arrays, event_jets) < 2.5)
    lead_phi = leading_jet_phi(arrays, event_jets)
    lead_dphi_pass = ak.fill_none(np.abs(delta_phi(no_mu_phi, lead_phi)) > 0.5, False)
    add("DeltaPhi(ETmiss, jet) > 0.5", lead_dphi_pass)

    trk_eta = exact_branch(arrays, "IsoTrack_eta")
    trk_phi = exact_branch(arrays, "IsoTrack_phi")
    trk = np.abs(trk_eta) < 2.1
    add(">= 1 tracks with fabs(eta) < 2.1", ak.any(trk, axis=1))
    trk = trk & (exact_branch(arrays, "IsoTrack_pt") > 55.0)
    add(">= 1 tracks with pt > 55", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 1.42) | (np.abs(trk_eta) > 1.65))
    add(">= 1 tracks with fabs(eta) < 1.42 || fabs(eta) > 1.65", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 0.15) | (np.abs(trk_eta) > 0.35))
    add(">= 1 tracks with fabs(eta) < 0.15 || fabs(eta) > 0.35", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 1.55) | (np.abs(trk_eta) > 1.85))
    add(">= 1 tracks with fabs(eta) < 1.55 || fabs(eta) > 1.85", ak.any(trk, axis=1))
    trk = trk & ~in_tob_crack(arrays)
    add(">= 1 tracks with !inTOBCrack", ak.any(trk, axis=1))

    trk = trk & config["electron_fiducial"].track_mask(trk_eta, trk_phi)
    add(">= 1 tracks with isFiducialElectronTrack", ak.any(trk, axis=1))
    trk = trk & config["muon_fiducial"].track_mask(trk_eta, trk_phi)
    add(">= 1 tracks with isFiducialMuonTrack", ak.any(trk, axis=1))
    trk = trk & fiducial_ecal_track(arrays)
    add(">= 1 tracks with isFiducialECALTrack", ak.any(trk, axis=1))

    trk = trk & (exact_branch(arrays, "IsoTrack_hp_nValidPixelHits") >= 4)
    add(">= 1 tracks with hitPattern_.numberOfValidPixelHits >= 4", ak.any(trk, axis=1))
    trk = trk & (exact_branch(arrays, "IsoTrack_hp_nValidHits") >= 4)
    add(">= 1 tracks with hitPattern_.numberOfValidHits >= 4", ak.any(trk, axis=1))
    trk = trk & (exact_branch(arrays, "IsoTrack_missingInnerHits") == 0)
    add(">= 1 tracks with missingInnerHits == 0", ak.any(trk, axis=1))

    hitdrop_middle, hitdrop_outer = hit_drop_missing_hits(
        arrays, config["missing_hits_period"], config["missing_hits_mode"]
    )
    trk = trk & (hitdrop_middle == 0)
    add(">= 1 tracks with hitDrop_missingMiddleHits == 0", ak.any(trk, axis=1))
    trk = trk & (track_relative_charged_iso(arrays) < 0.05)
    add(">= 1 tracks with (pfIsolationDR03_.chargedHadronIso / pt) < 0.05", ak.any(trk, axis=1))
    trk = trk & (np.abs(exact_branch(arrays, "IsoTrack_dxy")) < 0.02)
    add(">= 1 tracks with |d0| < 0.02", ak.any(trk, axis=1))
    trk = trk & (np.abs(exact_branch(arrays, "IsoTrack_dz")) < 0.5)
    add(">= 1 tracks with |dz| < 0.5", ak.any(trk, axis=1))

    d_r_min_jet = min_delta_r_to_objects(
        trk_eta,
        trk_phi,
        exact_branch(arrays, "Jet_eta"),
        exact_branch(arrays, "Jet_phi"),
        event_jets,
    )
    trk = trk & (d_r_min_jet > 0.5)
    add(">= 1 tracks with dRMinJet > 0.5", ak.any(trk, axis=1))
    add("eventvariables jetVeto2022 == 1", pass_pocketcoffea_jet_veto(arrays, config["jet_veto"]))

    trk = trk & (
        min_delta_r_to_objects(
            trk_eta, trk_phi, exact_branch(arrays, "Electron_eta"), exact_branch(arrays, "Electron_phi")
        )
        > 0.15
    )
    add(">= 1 tracks with deltaRToClosestElectron > 0.15", ak.any(trk, axis=1))
    trk = trk & (
        min_delta_r_to_objects(
            trk_eta, trk_phi, exact_branch(arrays, "Muon_eta"), exact_branch(arrays, "Muon_phi")
        )
        > 0.15
    )
    add(">= 1 tracks with deltaRToClosestMuon > 0.15", ak.any(trk, axis=1))
    trk = trk & (
        min_delta_r_to_objects(
            trk_eta,
            trk_phi,
            exact_branch(arrays, "Tau_eta"),
            exact_branch(arrays, "Tau_phi"),
            tau_had_mask(arrays),
        )
        > 0.15
    )
    add(">= 1 tracks with deltaRToClosestTauHad > 0.15", ak.any(trk, axis=1))

    calo = exact_branch(arrays, "IsoTrack_caloEm") + exact_branch(arrays, "IsoTrack_caloHad")
    trk = trk & (calo < 10.0)
    add(">= 1 tracks with matchedCaloJetEmEnergy + matchedCaloJetHadEnergy < 10", ak.any(trk, axis=1))
    trk = trk & (hitdrop_outer >= 3)
    add(">= 1 tracks with hitAndTOBDrop_bestTrackMissingOuterHits >= 3", ak.any(trk, axis=1))
    trk = trk & (exact_branch(arrays, "IsoTrack_hp_trackerLayersWithMeasurement") >= 6)
    add(">= 1 tracks with hitPattern_.trackerLayersWithMeasurement >= 6", ak.any(trk, axis=1))
    return cutflow


def merge_cutflows(target, source):
    for name, value in source.items():
        target[name] = target.get(name, 0.0) + float(value)


def run_files(files: list[str], tree: str, chunk_size: str, config):
    merged = OrderedDict()
    for filename in files:
        with uproot.open(f"{filename}:{tree}") as root_tree:
            available = set(root_tree.keys())
            missing = missing_required(available, config["missing_hits_mode"])
            if missing:
                raise RuntimeError(f"{filename} is missing required branches: {', '.join(missing)}")
            branches = input_branches_for_available(available, config["missing_hits_mode"])
        for arrays in uproot.iterate(f"{filename}:{tree}", branches, step_size=chunk_size, library="ak"):
            merge_cutflows(merged, build_cutflow(arrays, config))
    return merged


def cutflow_payload(files, tree, cutflow, config):
    total = float(cutflow.get("total", 0))
    rows = []
    previous = None
    for name, count in cutflow.items():
        count = float(count)
        rows.append(
            {
                "cut": name,
                "count": count,
                "cumulative_efficiency": (count / total if total > 0 else 0.0),
                "relative_efficiency": (count / previous if previous else 1.0),
            }
        )
        previous = float(count)
    meta = {
        "tree": tree,
        "n_files": len(files),
        "files": files,
        "era": config["era"],
        "jet_veto": {
            "mode": "pocketcoffea_jerc_correctionlib",
            "year": config["jet_veto_year"],
            "file": str(config["jet_veto"]["file"]),
            "name": str(config["jet_veto"]["name"]),
            "nano_version": int(config["jet_veto"]["nano_version"]),
        },
        "jer_smearing": {
            "mode": "hybrid_jerc_correctionlib",
            "year": config["jet_veto_year"],
            "file": str(config["jer"]["file"]),
            "resolution": str(config["jer"]["resolution"]),
            "scale_factor": str(config["jer"]["scale_factor"]),
            "systematic": "nom",
            "random_seed": "stable hash of event number and jet index",
        },
        "electron_fiducial_map": str(config["electron_fiducial_path"]),
        "muon_fiducial_map": str(config["muon_fiducial_path"]),
        "electron_fiducial_summary": config["electron_fiducial"].summary(),
        "muon_fiducial_summary": config["muon_fiducial"].summary(),
        "fiducial_threshold": config["fiducial_threshold"],
        "missing_hits_mode": config["missing_hits_mode"],
        "missing_hits_period": config["missing_hits_period"],
        "cutflow_weight_note": "Cutflow rows are weighted by sign(genWeight), matching V1 CutFlowPlotter behavior for GenEventInfoProduct.",
        "jet_pt_note": "The smearedPt row uses correctionlib hybrid JER smearing from NanoAOD Jet/GenJet/Rho branches.",
        "calo_note": "The calo row uses IsoTrack_caloEm + IsoTrack_caloHad.",
    }
    return {"metadata": meta, "cutflow": rows}


def print_summary(cutflow):
    print()
    print("=" * 110)
    print("Signal cutflow")
    print("=" * 110)
    total = float(cutflow.get("total", 0))
    previous = None
    for name, count in cutflow.items():
        rel = (count / previous) if previous else 1.0
        cum = (count / total) if total > 0 else 0.0
        print(f"{name:82s} {count:12.3f}  rel={rel:9.5f}  cum={cum:9.5f}")
        previous = float(count)


def write_root(path: Path, cutflow) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    values = np.asarray(list(cutflow.values()), dtype=float)
    edges = np.arange(len(values) + 1, dtype=float)
    with uproot.recreate(path) as fout:
        fout["cutflow_counts"] = values, edges


def build_config(args):
    era = args.era.upper()
    jet_veto_year = args.jet_veto_year or ERA_TO_JET_VETO_YEAR[era]
    jet_veto = dict(JET_VETO_CONFIGS[jet_veto_year])
    if args.jet_veto_file:
        jet_veto["file"] = args.jet_veto_file
    if args.jet_veto_name:
        jet_veto["name"] = args.jet_veto_name
    jer = dict(JER_CONFIGS[jet_veto_year])
    if args.jer_file:
        jer["file"] = args.jer_file
    if args.jer_resolution_name:
        jer["resolution"] = args.jer_resolution_name
    if args.jer_scale_factor_name:
        jer["scale_factor"] = args.jer_scale_factor_name
    electron_path = Path(args.electron_fiducial_map or DATA_DIR / f"electronFiducialMap_2022{era}_data.root")
    muon_path = Path(args.muon_fiducial_map or DATA_DIR / f"muonFiducialMap_2022{era}_data.root")
    missing_hits_period = args.missing_hits_period or ERA_TO_MISSING_HITS_PERIOD[era]
    return {
        "era": era,
        "jet_veto_year": jet_veto_year,
        "jet_veto": jet_veto,
        "jer": jer,
        "electron_fiducial_path": electron_path,
        "muon_fiducial_path": muon_path,
        "electron_fiducial": load_fiducial_map(str(electron_path), args.fiducial_threshold),
        "muon_fiducial": load_fiducial_map(str(muon_path), args.fiducial_threshold),
        "fiducial_threshold": args.fiducial_threshold,
        "missing_hits_mode": args.missing_hits_mode,
        "missing_hits_period": missing_hits_period,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Run 3 disappearing-track signal cutflow on OSUNano NanoAOD.")
    parser.add_argument("--input", nargs="+", required=True, help="ROOT files, text file lists, globs, or /store directories.")
    parser.add_argument("--tree", default="Events")
    parser.add_argument("--era", choices=("C", "D", "E", "F", "G"), default="C")
    parser.add_argument("--chunk-size", default="100 MB")
    parser.add_argument("--json-output", required=True)
    parser.add_argument("--output", help="Optional ROOT output file.")
    parser.add_argument("--jet-veto-year", choices=tuple(JET_VETO_CONFIGS), help="Override era-derived JERC jet-veto-map campaign.")
    parser.add_argument("--jet-veto-file", help="Override correctionlib jetvetomaps.json.gz file.")
    parser.add_argument("--jet-veto-name", help="Override correctionlib jet-veto correction name.")
    parser.add_argument("--jer-file", help="Override correctionlib jet_jerc.json.gz file for hybrid JER smearing.")
    parser.add_argument("--jer-resolution-name", help="Override JER pt resolution correction name.")
    parser.add_argument("--jer-scale-factor-name", help="Override JER scale factor correction name.")
    parser.add_argument("--electron-fiducial-map", help="Override electron fiducial ROOT map.")
    parser.add_argument("--muon-fiducial-map", help="Override muon fiducial ROOT map.")
    parser.add_argument("--fiducial-threshold", type=float, default=0.0)
    parser.add_argument("--missing-hits-mode", choices=("saved", "stochastic"), default="saved")
    parser.add_argument("--missing-hits-period", choices=tuple(MISSING_HITS_CORRECTIONS), help="Override era-derived missing-hit correction period.")
    args = parser.parse_args()

    files = parse_inputs(args.input)
    if not files:
        raise RuntimeError("No input files found.")

    config = build_config(args)
    cutflow = run_files(files, args.tree, args.chunk_size, config)
    print_summary(cutflow)

    payload = cutflow_payload(files, args.tree, cutflow, config)
    json_path = Path(args.json_output)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print(f"\nWrote {json_path}")

    if args.output:
        write_root(Path(args.output), cutflow)
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
