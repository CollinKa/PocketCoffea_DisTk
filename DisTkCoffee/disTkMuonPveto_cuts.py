from __future__ import annotations

import awkward as ak

from pocket_coffea.lib.cut_definition import Cut

from disTkMuonPveto_core import (
    LAYERS,
    build_muon_vectors,
    build_track_vectors,
    event_preselection_mask,
    muon_tag_mask,
    probe_track_denominator_mask,
)


def has_pveto_objects(events, params, **kwargs):
    """Loose event preselection used by the native PocketCoffea workflow."""
    layer = params.get("layer", "combinedBins")
    event_mask = event_preselection_mask(events)
    return event_mask & ak.any(muon_tag_mask(events), axis=1) & ak.any(
        probe_track_denominator_mask(events, layer), axis=1
    )


def pveto_denominator_category(events, params, **kwargs):
    """Event mask for a Pveto denominator track-muon pair in one layer bin."""
    layer = params["layer"]
    event_mask = event_preselection_mask(events)
    muons = build_muon_vectors(events, muon_tag_mask(events))
    tracks = build_track_vectors(events, probe_track_denominator_mask(events, layer))
    trk_obj, mu_obj = ak.unzip(ak.cartesian([tracks, muons], nested=True))
    pair_mask = trk_obj.charge * mu_obj.charge != 0
    return event_mask & ak.any(ak.flatten(pair_mask, axis=2), axis=1)


def get_has_pveto_objects_cut(layer="combinedBins"):
    return Cut(
        name=f"has_pveto_objects_{layer}",
        params={"layer": layer},
        function=has_pveto_objects,
    )


def get_pveto_denominator_cut(layer):
    if layer not in LAYERS:
        raise ValueError(f"Unknown Pveto layer bin: {layer}")
    return Cut(
        name=f"pveto_denominator_{layer}",
        params={"layer": layer},
        function=pveto_denominator_category,
    )
