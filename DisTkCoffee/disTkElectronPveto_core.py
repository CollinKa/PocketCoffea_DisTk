from __future__ import annotations

import math
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable

import awkward as ak
import numpy as np
import vector

vector.register_awkward()

ELECTRON_MASS = 0.000511
Z_MASS = 91.1876
LAYERS = ("NLayers4", "NLayers5", "NLayers6plus", "combinedBins")
ELECTRON_TRIGGER_MATCHING_DR = 0.3
ELECTRON_TRIGOBJ_ID = 11
ELECTRON_WPTIGHT_TRACKISO_FILTER_BIT = 1

BRANCH_ALIASES = {
    "passMETFilters": ("Flag_METFilters",),
    "ele_pt": ("Electron_pt",),
    "ele_eta": ("Electron_eta",),
    "ele_phi": ("Electron_phi",),
    "ele_charge": ("Electron_charge",),
    "ele_dxy": ("Electron_dxy",),
    "ele_dz": ("Electron_dz",),
    "ele_deltaEtaSC": ("Electron_deltaEtaSC",),
    "ele_isTrigMatched": ("Electron_isTrigMatched",),
    "ele_isTight": ("Electron_isTight",),
    "muon_eta": ("Muon_eta",),
    "muon_phi": ("Muon_phi",),
    "tau_eta": ("Tau_eta",),
    "tau_phi": ("Tau_phi",),
    "tau_isTight": ("Tau_isTight",),
    "jet_pt": ("Jet_pt",),
    "jet_eta": ("Jet_eta",),
    "jet_phi": ("Jet_phi",),
    "jet_isTightLepVeto": ("Jet_isTightLepVeto",),
    "trk_caloTotNoPU": ("IsoTrack_caloTotNoPU",),
    "trk_pt": ("IsoTrack_pt",),
    "trk_eta": ("IsoTrack_eta",),
    "trk_phi": ("IsoTrack_phi",),
    "trk_theta": ("IsoTrack_theta",),
    "trk_charge": ("IsoTrack_charge",),
    "trk_dxy": ("IsoTrack_dxy",),
    "trk_dz": ("IsoTrack_dz",),
    "trk_missingInnerHits": ("IsoTrack_missingInnerHits",),
    "trk_hitDrop_missingMiddleHits": ("IsoTrack_missingMiddleHits",),
    "trk_missingOuterHits": ("IsoTrack_missingOuterHits",),
    "trk_isFiducialECALTrack": ("IsoTrack_isFiducialECALTrack",),
    "trk_relativePFIso": ("IsoTrack_pfRelIso03_chg", "IsoTrack_pfRelIso03_all"),
    "trk_hp_numberOfValidPixelHits": ("IsoTrack_hp_nValidPixelHits",),
    "trk_hp_trackerLayersWithMeasurement": ("IsoTrack_hp_trackerLayersWithMeasurement",),
}

COMPUTED_BRANCH_REQUIREMENTS = {
    "ele_isTight": ("Electron_cutBased",),
    "tau_isTight": (
        "Tau_idDecayModeNewDMs",
        "Tau_idDeepTau2018v2p5VSjet",
        "Tau_idDeepTau2018v2p5VSe",
        "Tau_idDeepTau2018v2p5VSmu",
    ),
    "trk_caloTotNoPU": (
        "IsoTrack_caloEm",
        "IsoTrack_caloHad",
        "Rho_fixedGridRhoFastjetCentralCalo",
    ),
    "trk_isFiducialECALTrack": ("IsoTrack_minDRToMaskedEcal",),
    "jet_isTightLepVeto": (
        "Jet_neHEF",
        "Jet_neEmEF",
        "Jet_chHEF",
        "Jet_chEmEF",
        "Jet_muEF",
        "Jet_chMultiplicity",
        "Jet_neMultiplicity",
        "Jet_eta",
    ),
}

CENTRAL_FALLBACK_BRANCH_REQUIREMENTS = {
    "jet_isTightLepVeto": ("Jet_jetId",),
}

# FIXME(2026-07-02): Current v1.0.0-pre Run2022 EGamma customized NanoAOD
# lacks the saved jet-veto-map event decision (passJvmFilter/jetVeto2022).
# Treat it as all-true only for temporary validation; strict Run 3 replication
# needs this branch saved during NanoAOD production or an explicitly documented
# approximate JVM recomputation from Jet_* branches.
TEMPORARY_TRUE_IF_MISSING = {"passJvmFilter"}

TRIGGER_MATCH_BRANCH_REQUIREMENTS = {
    "ele_isTrigMatched": ("TrigObj_id", "TrigObj_filterBits", "TrigObj_eta", "TrigObj_phi"),
}

OPTIONAL_BRANCHES = (
    "HLT_Ele32_WPTight_Gsf",
    "HLT_Ele32_WPTight_Gsf_L1DoubleEG",
    "Flag_METFilters",
    "passMETFilters",
    "passJvmFilter",
    "ele_isTrigMatched",
    "jet_isTightLepVeto",
    "TrigObj_id",
    "TrigObj_filterBits",
    "TrigObj_eta",
    "TrigObj_phi",
)

PVETO_BRANCHES = [
    "HLT_Ele32_WPTight_Gsf",
    "passMETFilters",
    "passJvmFilter",
    "ele_pt",
    "ele_eta",
    "ele_phi",
    "ele_charge",
    "ele_dxy",
    "ele_dz",
    "ele_deltaEtaSC",
    "ele_isTrigMatched",
    "ele_isTight",
    "muon_eta",
    "muon_phi",
    "tau_eta",
    "tau_phi",
    "tau_isTight",
    "jet_eta",
    "jet_phi",
    "jet_pt",
    "jet_isTightLepVeto",
    "trk_pt",
    "trk_eta",
    "trk_phi",
    "trk_theta",
    "trk_charge",
    "trk_dxy",
    "trk_dz",
    "trk_missingInnerHits",
    "trk_hitDrop_missingMiddleHits",
    "trk_missingOuterHits",
    "trk_isFiducialECALTrack",
    "trk_relativePFIso",
    "trk_caloTotNoPU",
    "trk_hp_numberOfValidPixelHits",
    "trk_hp_trackerLayersWithMeasurement",
]

BRANCH_NOTES = {
    "ele_isTrigMatched": (
        "The electron Pveto tag selection needs the MattWIP trigger-object match. "
        "For OSUNano inputs this is read from Electron_isTrigMatched when present, "
        "otherwise computed from NanoAOD TrigObj electron WPTight TrackIso bits."
    ),
    "ele_isTight": (
        "For OSUNano inputs this is read from Electron_isTight if present, "
        "otherwise computed as Electron_cutBased >= 4. The explicit EB/EE dxy/dz "
        "requirements are applied as separate tag rows to match V1 Run 3 code."
    ),
    "passJvmFilter": (
        "FIXME(2026-07-02): current v1.0.0-pre Run2022 EGamma customized NanoAOD "
        "does not contain the saved jet-veto-map event branch. Coffee temporarily "
        "treats missing passJvmFilter as all true so validation can proceed; strict "
        "Run 3 replication requires remaking NanoAOD with passJvmFilter/jetVeto2022 "
        "or using an explicitly documented approximate JVM recomputation."
    ),
    "tau_isTight": (
        "For OSUNano inputs this is read from Tau_isTight if present, otherwise "
        "computed from decayModeNewDMs plus Run 3 DeepTau Tight VSjet, VVVLoose VSe, "
        "and VLoose VSmu working points."
    ),
    "trk_isFiducialECALTrack": (
        "For OSUNano inputs this is read from IsoTrack_isFiducialECALTrack if present, "
        "otherwise computed as IsoTrack_minDRToMaskedEcal < 0 or > 0.05."
    ),
    "trk_caloTotNoPU": (
        "For OSUNano inputs this is reconstructed from IsoTrack_caloEm, "
        "IsoTrack_caloHad, and Rho_fixedGridRhoFastjetCentralCalo."
    ),
}


@dataclass
class Count:
    value: float = 0.0
    variance: float = 0.0

    @property
    def error(self) -> float:
        return math.sqrt(max(self.variance, 0.0))

    def add_poisson(self, n: float) -> None:
        self.value += float(n)
        self.variance += float(n)

    def as_json(self) -> dict[str, float]:
        return {"value": self.value, "variance": self.variance, "error": self.error}


def normalize_layers(layer: str) -> list[str]:
    return list(LAYERS) if layer == "all" else [layer]


def branch_options(name: str) -> tuple[str, ...]:
    return (name,) + BRANCH_ALIASES.get(name, ())


def has_exact_branch(arrays, name: str) -> bool:
    if name in arrays.fields:
        return True
    if "_" not in name:
        return False
    collection, field = name.split("_", 1)
    return collection in arrays.fields and field in arrays[collection].fields


def available_has_branch(available: set[str], name: str) -> bool:
    if name in TEMPORARY_TRUE_IF_MISSING:
        return True
    if any(option in available for option in branch_options(name)):
        return True
    if name in TRIGGER_MATCH_BRANCH_REQUIREMENTS:
        return all(req in available for req in TRIGGER_MATCH_BRANCH_REQUIREMENTS[name])
    if name in COMPUTED_BRANCH_REQUIREMENTS and all(
        req in available for req in COMPUTED_BRANCH_REQUIREMENTS[name]
    ):
        return True
    if name in CENTRAL_FALLBACK_BRANCH_REQUIREMENTS and all(
        req in available for req in CENTRAL_FALLBACK_BRANCH_REQUIREMENTS[name]
    ):
        return True
    return False


def has_branch(arrays, name: str) -> bool:
    if name in TEMPORARY_TRUE_IF_MISSING:
        return True
    if any(has_exact_branch(arrays, option) for option in branch_options(name)):
        return True
    if name in TRIGGER_MATCH_BRANCH_REQUIREMENTS:
        return all(has_exact_branch(arrays, req) for req in TRIGGER_MATCH_BRANCH_REQUIREMENTS[name])
    if name in COMPUTED_BRANCH_REQUIREMENTS and all(
        has_exact_branch(arrays, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name]
    ):
        return True
    if name in CENTRAL_FALLBACK_BRANCH_REQUIREMENTS and all(
        has_exact_branch(arrays, req) for req in CENTRAL_FALLBACK_BRANCH_REQUIREMENTS[name]
    ):
        return True
    return False


def input_branches_for_available(available: set[str]) -> list[str]:
    needed = []
    for name in PVETO_BRANCHES:
        for option in branch_options(name):
            if option in available:
                needed.append(option)
                break
        else:
            if name in TRIGGER_MATCH_BRANCH_REQUIREMENTS and all(
                req in available for req in TRIGGER_MATCH_BRANCH_REQUIREMENTS[name]
            ):
                needed.extend(TRIGGER_MATCH_BRANCH_REQUIREMENTS[name])
            elif name in COMPUTED_BRANCH_REQUIREMENTS and all(
                req in available for req in COMPUTED_BRANCH_REQUIREMENTS[name]
            ):
                needed.extend(COMPUTED_BRANCH_REQUIREMENTS[name])
            elif name in CENTRAL_FALLBACK_BRANCH_REQUIREMENTS and all(
                req in available for req in CENTRAL_FALLBACK_BRANCH_REQUIREMENTS[name]
            ):
                needed.extend(CENTRAL_FALLBACK_BRANCH_REQUIREMENTS[name])
    needed.extend(option for option in OPTIONAL_BRANCHES if option in available)
    return sorted(set(needed))


def missing_required_for_available(available: set[str]) -> list[str]:
    return [name for name in PVETO_BRANCHES if not available_has_branch(available, name)]


def missing_branch_message(name: str) -> str:
    note = BRANCH_NOTES.get(name)
    if note:
        return f"Required branch {name} not found. {note}"
    return f"Required branch {name} not found in DisTkCoffee/OSUNano electron Pveto input."


def exact_branch(arrays, name: str):
    if name in arrays.fields:
        return arrays[name]
    if "_" in name:
        collection, field = name.split("_", 1)
        if collection in arrays.fields:
            return arrays[collection][field]
    raise KeyError(name)


def branch(arrays, name: str):
    if name in TEMPORARY_TRUE_IF_MISSING and not any(has_exact_branch(arrays, option) for option in branch_options(name)):
        return np.ones(len(arrays), dtype=bool)

    if name == "ele_isTrigMatched":
        saved_match = aligned_saved_branch(arrays, "ele_isTrigMatched", "ele_pt")
        if saved_match is not None:
            return saved_match
        return electron_trigger_match_mask(arrays)

    if name == "ele_isTight" and not any(has_exact_branch(arrays, option) for option in branch_options(name)):
        return exact_branch(arrays, "Electron_cutBased") >= 4

    if name == "tau_isTight" and not any(has_exact_branch(arrays, option) for option in branch_options(name)):
        decay = exact_branch(arrays, "Tau_idDecayModeNewDMs") != 0
        vsjet = exact_branch(arrays, "Tau_idDeepTau2018v2p5VSjet") >= 6
        vse = exact_branch(arrays, "Tau_idDeepTau2018v2p5VSe") >= 1
        vsmu = exact_branch(arrays, "Tau_idDeepTau2018v2p5VSmu") >= 1
        return decay & vsjet & vse & vsmu

    if name == "trk_isFiducialECALTrack" and not any(has_exact_branch(arrays, option) for option in branch_options(name)):
        min_dr = exact_branch(arrays, "IsoTrack_minDRToMaskedEcal")
        return (min_dr < 0.0) | (min_dr > 0.05)

    if name == "trk_caloTotNoPU" and not any(has_exact_branch(arrays, option) for option in branch_options(name)):
        calo_total = exact_branch(arrays, "IsoTrack_caloEm") + exact_branch(arrays, "IsoTrack_caloHad")
        rho = exact_branch(arrays, "Rho_fixedGridRhoFastjetCentralCalo")
        return np.maximum(0.0, calo_total - rho * np.pi * 0.4 * 0.4)

    if name == "jet_isTightLepVeto" and not any(has_exact_branch(arrays, option) for option in branch_options(name)):
        if all(has_exact_branch(arrays, req) for req in COMPUTED_BRANCH_REQUIREMENTS[name]):
            eta = np.abs(exact_branch(arrays, "Jet_eta"))
            nehef = exact_branch(arrays, "Jet_neHEF")
            neemef = exact_branch(arrays, "Jet_neEmEF")
            chef = exact_branch(arrays, "Jet_chHEF")
            chemef = exact_branch(arrays, "Jet_chEmEF")
            muef = exact_branch(arrays, "Jet_muEF")
            chmult = exact_branch(arrays, "Jet_chMultiplicity")
            nemult = exact_branch(arrays, "Jet_neMultiplicity")
            return (
                ((nehef < 0.99) & (neemef < 0.90) & ((chmult + nemult) > 1) & (muef < 0.8) & (chef > 0.01) & (chmult > 0) & (chemef < 0.80) & (eta <= 2.6))
                | ((nehef < 0.90) & (neemef < 0.99) & (muef < 0.8) & (chmult > 0) & (chemef < 0.80) & (eta > 2.6) & (eta <= 2.7))
                | ((nehef < 0.99) & (neemef < 0.99) & (nemult > 1) & (eta > 2.7) & (eta <= 3.0))
                | ((neemef < 0.4) & (nemult > 10) & (eta > 3.0) & (eta <= 5.0))
            )
        if has_exact_branch(arrays, "Jet_jetId"):
            return np.bitwise_and(exact_branch(arrays, "Jet_jetId"), 4) != 0  # Jet tight lepton veto bit

    for option in branch_options(name):
        try:
            return exact_branch(arrays, option)
        except KeyError:
            continue
    raise KeyError(missing_branch_message(name))


def aligned_saved_branch(arrays, name: str, reference_name: str):
    for option in branch_options(name):
        try:
            value = exact_branch(arrays, option)
        except KeyError:
            continue
        try:
            value_counts = ak.num(value, axis=1)
            reference_counts = ak.num(branch(arrays, reference_name), axis=1)
        except Exception:
            return None
        try:
            if bool(ak.all(value_counts == reference_counts)):
                return value
        except Exception:
            return None
    return None


def event_trigger_mask(arrays):
    masks = []
    for name in ("HLT_Ele32_WPTight_Gsf", "HLT_Ele32_WPTight_Gsf_L1DoubleEG"):
        if has_branch(arrays, name):
            masks.append(branch(arrays, name))
    if not masks:
        raise KeyError("Required EGamma trigger branch HLT_Ele32_WPTight_Gsf not found.")
    out = masks[0]
    for mask in masks[1:]:
        out = out | mask
    return out


def event_filter_mask(arrays, name: str):
    return branch(arrays, name)


def event_preselection_mask(arrays):
    return event_trigger_mask(arrays) & branch(arrays, "passMETFilters") & branch(arrays, "passJvmFilter")


def delta_phi(phi1, phi2):
    return np.arctan2(np.sin(phi1 - phi2), np.cos(phi1 - phi2))


def electron_trigger_match_mask(arrays):
    trig_fields = ("TrigObj_id", "TrigObj_filterBits", "TrigObj_eta", "TrigObj_phi")
    if not all(has_branch(arrays, name) for name in trig_fields):
        raise KeyError(missing_branch_message("ele_isTrigMatched"))

    trig_mask = (np.abs(branch(arrays, "TrigObj_id")) == ELECTRON_TRIGOBJ_ID) & (
        np.bitwise_and(branch(arrays, "TrigObj_filterBits"), 1 << ELECTRON_WPTIGHT_TRACKISO_FILTER_BIT) != 0
    )
    electrons = ak.zip({"eta": branch(arrays, "ele_eta"), "phi": branch(arrays, "ele_phi")})
    trig_objs = ak.zip({"eta": branch(arrays, "TrigObj_eta"), "phi": branch(arrays, "TrigObj_phi")})[
        trig_mask
    ]
    ele, obj = ak.unzip(ak.cartesian([electrons, trig_objs], nested=True))
    dr = np.sqrt((ele.eta - obj.eta) ** 2 + delta_phi(ele.phi, obj.phi) ** 2)
    return ak.fill_none(ak.any(dr < ELECTRON_TRIGGER_MATCHING_DR, axis=2), False)  # electron is trigger matched.


def min_delta_r_mask(arrays, prefix: str, min_dr: float, obj_mask=None):
    tracks = ak.zip({"eta": branch(arrays, "trk_eta"), "phi": branch(arrays, "trk_phi")})
    objs = ak.zip({"eta": branch(arrays, f"{prefix}_eta"), "phi": branch(arrays, f"{prefix}_phi")})

    if obj_mask is not None:
        objs = objs[obj_mask]

    trk, obj = ak.unzip(ak.cartesian([tracks, objs], nested=True))
    dr = np.sqrt((trk.eta - obj.eta) ** 2 + delta_phi(trk.phi, obj.phi) ** 2)
    return ak.fill_none(ak.all(dr > min_dr, axis=2), True)


def any_pair_per_event(pair_mask):
    return ak.any(ak.flatten(pair_mask, axis=2), axis=1)


def layer_mask(arrays, layer: str):
    n_layers = branch(arrays, "trk_hp_trackerLayersWithMeasurement")
    if layer == "NLayers4":
        return n_layers == 4
    if layer == "NLayers5":
        return n_layers == 5
    if layer == "NLayers6plus":
        return n_layers >= 6
    if layer == "combinedBins":
        return n_layers >= 4
    raise ValueError(f"Unknown layer bin: {layer}")


def fiducial_eta_mask(arrays):
    trk_eta = branch(arrays, "trk_eta")
    return (
        ((np.abs(trk_eta) < 0.15) | (np.abs(trk_eta) > 0.35))
        & ((np.abs(trk_eta) < 1.42) | (np.abs(trk_eta) > 1.65))
        & ((np.abs(trk_eta) < 1.55) | (np.abs(trk_eta) > 1.85))
    )


def water_leak_mask(arrays):
    trk_eta = branch(arrays, "trk_eta")
    return (trk_eta < 0.0) | (trk_eta > 1.42) | (branch(arrays, "trk_phi") < 2.7)


def good_jet_mask(arrays, jet_pt_min: float, jet_eta_max: float):
    return (
        (branch(arrays, "jet_pt") > jet_pt_min)
        & (np.abs(branch(arrays, "jet_eta")) < jet_eta_max)
        & branch(arrays, "jet_isTightLepVeto")
    )


def good_tau_mask(arrays):
    tau_id_branches = (
        "Tau_idDecayModeNewDMs",
        "Tau_idDeepTau2018v2p5VSjet",
        "Tau_idDeepTau2018v2p5VSe",
        "Tau_idDeepTau2018v2p5VSmu",
    )
    if all(has_exact_branch(arrays, name) for name in tau_id_branches):
        return (
            (exact_branch(arrays, "Tau_idDecayModeNewDMs") != 0)
            & (exact_branch(arrays, "Tau_idDeepTau2018v2p5VSjet") >= 6)
            & (exact_branch(arrays, "Tau_idDeepTau2018v2p5VSe") >= 1)
            & (exact_branch(arrays, "Tau_idDeepTau2018v2p5VSmu") >= 1)
        )
    return branch(arrays, "tau_isTight")


def electron_sc_eta(arrays):
    return branch(arrays, "ele_eta") + branch(arrays, "ele_deltaEtaSC")


def electron_dxy_mask(arrays):
    barrel = np.abs(electron_sc_eta(arrays)) <= 1.479
    return (barrel & (np.abs(branch(arrays, "ele_dxy")) < 0.05)) | (~barrel & (np.abs(branch(arrays, "ele_dxy")) < 0.10))


def electron_dz_mask(arrays):
    barrel = np.abs(electron_sc_eta(arrays)) <= 1.479
    return (barrel & (np.abs(branch(arrays, "ele_dz")) < 0.10)) | (~barrel & (np.abs(branch(arrays, "ele_dz")) < 0.20))


def electron_tag_mask(arrays):
    mask = branch(arrays, "ele_pt") > 32.0
    mask = mask & (np.abs(branch(arrays, "ele_eta")) < 2.1)
    mask = mask & branch(arrays, "ele_isTight")
    mask = mask & electron_dxy_mask(arrays)
    mask = mask & electron_dz_mask(arrays)
    mask = mask & branch(arrays, "ele_isTrigMatched")
    return mask


def probe_track_denominator_mask(
    arrays,
    layer: str,
    jet_pt_min: float = 30.0,
    jet_eta_max: float = 4.5,
    apply_water_leak_veto: bool = False,
):
    mask = branch(arrays, "trk_pt") > 30
    mask = mask & (np.abs(branch(arrays, "trk_eta")) < 2.1)
    mask = mask & fiducial_eta_mask(arrays)
    mask = mask & branch(arrays, "trk_isFiducialECALTrack")
    if apply_water_leak_veto:
        mask = mask & water_leak_mask(arrays)
    mask = mask & (
        (np.abs(branch(arrays, "trk_dz")) > 0.5)
        | (np.abs((np.pi / 2.0) - branch(arrays, "trk_theta")) > 1.0e-3)
    )
    mask = mask & (branch(arrays, "trk_hp_numberOfValidPixelHits") >= 4)
    mask = mask & (branch(arrays, "trk_missingInnerHits") == 0)
    mask = mask & (branch(arrays, "trk_hitDrop_missingMiddleHits") == 0)
    mask = mask & (branch(arrays, "trk_relativePFIso") < 0.05)
    mask = mask & (np.abs(branch(arrays, "trk_dxy")) < 0.02)
    mask = mask & (np.abs(branch(arrays, "trk_dz")) < 0.5)
    mask = mask & min_delta_r_mask(
        arrays,
        "jet",
        0.5,
        obj_mask=good_jet_mask(arrays, jet_pt_min, jet_eta_max),
    )
    mask = mask & min_delta_r_mask(arrays, "muon", 0.15)
    mask = mask & min_delta_r_mask(arrays, "tau", 0.15, obj_mask=good_tau_mask(arrays))
    mask = mask & layer_mask(arrays, layer)
    return mask


def build_electron_vectors(arrays, mask):
    return ak.zip(
        {
            "pt": branch(arrays, "ele_pt")[mask],
            "eta": branch(arrays, "ele_eta")[mask],
            "phi": branch(arrays, "ele_phi")[mask],
            "mass": ak.ones_like(branch(arrays, "ele_pt")[mask]) * ELECTRON_MASS,
            "charge": branch(arrays, "ele_charge")[mask],
        },
        with_name="Momentum4D",
    )


def build_track_vectors(arrays, mask):
    electron_veto = min_delta_r_mask(arrays, "ele", 0.15)
    return ak.zip(
        {
            "pt": branch(arrays, "trk_pt")[mask],
            "eta": branch(arrays, "trk_eta")[mask],
            "phi": branch(arrays, "trk_phi")[mask],
            "mass": ak.ones_like(branch(arrays, "trk_pt")[mask]) * ELECTRON_MASS,
            "charge": branch(arrays, "trk_charge")[mask],
            "missingOuterHits": branch(arrays, "trk_missingOuterHits")[mask],
            "calo": branch(arrays, "trk_caloTotNoPU")[mask],
            "passesElectronDR": electron_veto[mask],
        },
        with_name="Momentum4D",
    )


def make_tp_cutflow(
    arrays,
    layer: str,
    jet_pt_min: float = 30.0,
    jet_eta_max: float = 4.5,
    apply_water_leak_veto: bool = False,
):
    cutflow = OrderedDict()
    event_mask = ak.ones_like(ak.num(branch(arrays, "ele_pt"), axis=1), dtype=bool)

    def add(label: str, mask) -> None:
        nonlocal event_mask
        event_mask = event_mask & mask
        cutflow[label] = int(ak.sum(event_mask))

    add("event passes SingleElectron/EGamma triggers", event_trigger_mask(arrays))
    add("event passes MET filters", event_filter_mask(arrays, "passMETFilters"))
    add("event passes jet veto map filter", event_filter_mask(arrays, "passJvmFilter"))

    ele = branch(arrays, "ele_pt") > 32.0
    add(">= 1 electrons pT > 32 GeV", ak.any(ele, axis=1))
    ele = ele & (np.abs(branch(arrays, "ele_eta")) < 2.1)
    add(">= 1 electrons |eta| < 2.1", ak.any(ele, axis=1))
    ele = ele & branch(arrays, "ele_isTight")
    add(">= 1 electrons passing tight electron ID", ak.any(ele, axis=1))
    ele = ele & electron_dxy_mask(arrays)
    add(">= 1 electrons passing EB/EE dxy requirement", ak.any(ele, axis=1))
    ele = ele & electron_dz_mask(arrays)
    add(">= 1 electrons passing EB/EE dz requirement", ak.any(ele, axis=1))
    ele = ele & branch(arrays, "ele_isTrigMatched")
    add(">= 1 electrons matched to trigger object", ak.any(ele, axis=1))
    add(">= 1 passing electron tag", ak.any(ele, axis=1))

    trk = branch(arrays, "trk_pt") > 30
    add(">= 1 tracks pT > 30 GeV", ak.any(trk, axis=1))
    trk = trk & (np.abs(branch(arrays, "trk_eta")) < 2.1)
    add(">= 1 tracks |eta| < 2.1", ak.any(trk, axis=1))
    trk_eta = branch(arrays, "trk_eta")
    trk = trk & ((np.abs(trk_eta) < 0.15) | (np.abs(trk_eta) > 0.35))
    add(">= 1 tracks |eta| < 0.15 OR |eta| > 0.35", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 1.42) | (np.abs(trk_eta) > 1.65))
    add(">= 1 tracks |eta| < 1.42 OR |eta| > 1.65", ak.any(trk, axis=1))
    trk = trk & ((np.abs(trk_eta) < 1.55) | (np.abs(trk_eta) > 1.85))
    add(">= 1 tracks |eta| < 1.55 OR |eta| > 1.85", ak.any(trk, axis=1))
    trk = trk & branch(arrays, "trk_isFiducialECALTrack")
    add(">= 1 tracks min DeltaRtrack,noisy/dead ECAL channel > 0.05", ak.any(trk, axis=1))
    if apply_water_leak_veto:
        trk = trk & water_leak_mask(arrays)
        add(">= 1 tracks eta < 0 OR eta > 1.42 OR phi < 2.7", ak.any(trk, axis=1))
    trk = trk & (
        (np.abs(branch(arrays, "trk_dz")) > 0.5)
        | (np.abs((np.pi / 2.0) - branch(arrays, "trk_theta")) > 1.0e-3)
    )
    add(">= 1 tracks |dz| > 0.5 cm OR |lambda| > 1e-3", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_hp_numberOfValidPixelHits") >= 4)
    add(">= 1 tracks number of pixel hits >= 4", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_missingInnerHits") == 0)
    add(">= 1 tracks missing inner hits = 0", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_hitDrop_missingMiddleHits") == 0)
    add(">= 1 tracks missing middle hits = 0", ak.any(trk, axis=1))
    trk = trk & (branch(arrays, "trk_relativePFIso") < 0.05)
    add(">= 1 tracks rel. PF-based iso. < 0.05", ak.any(trk, axis=1))
    trk = trk & (np.abs(branch(arrays, "trk_dxy")) < 0.02)
    add(">= 1 tracks |dxy| < 0.02 cm", ak.any(trk, axis=1))
    trk = trk & (np.abs(branch(arrays, "trk_dz")) < 0.5)
    add(">= 1 tracks |dz| < 0.5 cm", ak.any(trk, axis=1))
    trk = trk & min_delta_r_mask(
        arrays,
        "jet",
        0.5,
        obj_mask=good_jet_mask(arrays, jet_pt_min, jet_eta_max),
    )
    add(">= 1 track-jet pairs DeltaRtrack,jet > 0.5", ak.any(trk, axis=1))

    electrons = build_electron_vectors(arrays, ele)
    tracks_pre_veto = build_track_vectors(arrays, trk)
    trk_obj, ele_obj = ak.unzip(ak.cartesian([tracks_pre_veto, electrons], nested=True))
    mass = (trk_obj + ele_obj).mass
    add(">= 1 track-electron pairs Mtrack,electron > 10 GeV", any_pair_per_event(mass > 10))

    trk = trk & min_delta_r_mask(arrays, "muon", 0.15)
    add(">= 1 tracks min DeltaRtrack,muon > 0.15", ak.any(trk, axis=1))
    trk = trk & min_delta_r_mask(arrays, "tau", 0.15, obj_mask=good_tau_mask(arrays))
    add(">= 1 tracks min DeltaRtrack,had. tau > 0.15", ak.any(trk, axis=1))
    add(">= 1 passing probe track before layer selection", ak.any(trk, axis=1))

    trk = trk & layer_mask(arrays, layer)
    electrons = build_electron_vectors(arrays, ele)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, ele_obj = ak.unzip(ak.cartesian([tracks, electrons], nested=True))
    mass = (trk_obj + ele_obj).mass
    z_window = (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    add(">= 1 track-electron pairs |Mtrack,electron - MZ| < 10 GeV", any_pair_per_event(z_window))
    os_pair = z_window & (trk_obj.charge * ele_obj.charge < 0)
    add(">= 1 track-electron pairs qtrack * qelectron < 0", any_pair_per_event(os_pair))
    add(f">= 1 track nlayers >= 4 ({layer})", any_pair_per_event(os_pair))
    return cutflow


def count_pveto_pairs(
    arrays,
    layer: str,
    jet_pt_min: float = 30.0,
    jet_eta_max: float = 4.5,
    apply_water_leak_veto: bool = False,
) -> dict[str, float]:
    arrays = arrays[event_preselection_mask(arrays)]
    ele = electron_tag_mask(arrays)
    trk = probe_track_denominator_mask(
        arrays,
        layer,
        jet_pt_min,
        jet_eta_max,
        apply_water_leak_veto,
    )
    electrons = build_electron_vectors(arrays, ele)
    tracks = build_track_vectors(arrays, trk)
    trk_obj, ele_obj = ak.unzip(ak.cartesian([tracks, electrons], nested=True))
    mass = (trk_obj + ele_obj).mass
    z_window = (mass > 10.0) & (mass > Z_MASS - 10) & (mass < Z_MASS + 10)
    os_pair = trk_obj.charge * ele_obj.charge < 0
    ss_pair = trk_obj.charge * ele_obj.charge > 0
    passes_veto = (
        trk_obj.passesElectronDR
        & (trk_obj.calo < 10.0)
        & (trk_obj.missingOuterHits >= 3)
    )
    return {
        "p_veto_den_os": float(ak.sum(z_window & os_pair)),
        "p_veto_den_ss": float(ak.sum(z_window & ss_pair)),
        "p_veto_num_os": float(ak.sum(z_window & os_pair & passes_veto)),
        "p_veto_num_ss": float(ak.sum(z_window & ss_pair & passes_veto)),
    }


def empty_counts() -> dict[str, Count]:
    return {
        "p_veto_num_os": Count(),
        "p_veto_num_ss": Count(),
        "p_veto_den_os": Count(),
        "p_veto_den_ss": Count(),
    }


def process_arrays(
    arrays,
    layer: str,
    jet_pt_min: float = 30.0,
    jet_eta_max: float = 4.5,
    apply_water_leak_veto: bool = False,
) -> dict:
    return {
        "cutflow": make_tp_cutflow(
            arrays,
            layer,
            jet_pt_min,
            jet_eta_max,
            apply_water_leak_veto,
        ),
        "counts": count_pveto_pairs(
            arrays,
            layer,
            jet_pt_min,
            jet_eta_max,
            apply_water_leak_veto,
        ),
    }


def make_payload(input_files: Iterable[str], tree: str, layer_results: dict, configuration: dict) -> dict:
    payload = {
        "input_files": list(input_files),
        "tree": tree,
        "configuration": dict(configuration),
        "layers": {},
    }
    for layer, result in layer_results.items():
        payload["layers"][layer] = {
            "cutflow": dict(result["cutflow"]),
            "counts": {name: count.as_json() for name, count in result["counts"].items()},
        }
    return payload
