from __future__ import annotations

from collections import OrderedDict

from coffea import processor

from disTkMuonPveto_core import (
    Count,
    LAYERS,
    empty_counts,
    process_arrays,
)


class DisappTrksPvetoProcessor(processor.ProcessorABC):
    """Coffea/PocketCoffea-ready processor for the custom NanoAOD Pveto study."""

    def __init__(self, layers=LAYERS):
        self.layers = tuple(layers)

    def process(self, events):
        out = {}
        for layer in self.layers:
            result = process_arrays(events, layer)
            out[layer] = {
                "cutflow": OrderedDict((k, int(v)) for k, v in result["cutflow"].items()),
                "counts": {
                    name: Count(value=float(value), variance=float(value))
                    for name, value in result["counts"].items()
                },
            }
        return out

    def postprocess(self, accumulator):
        return accumulator


def merge_outputs(outputs):
    merged = {
        layer: {"cutflow": OrderedDict(), "counts": empty_counts()}
        for layer in LAYERS
    }
    for output in outputs:
        for layer, result in output.items():
            for name, value in result["cutflow"].items():
                merged[layer]["cutflow"][name] = merged[layer]["cutflow"].get(name, 0) + int(value)
            for name, count in result["counts"].items():
                value = getattr(count, "value", count)
                merged[layer]["counts"][name].add_poisson(float(value))
    return merged
