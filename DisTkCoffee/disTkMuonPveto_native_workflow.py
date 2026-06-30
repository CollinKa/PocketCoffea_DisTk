from __future__ import annotations

from coffea import processor
from pocket_coffea.workflows.base import BaseProcessorABC

from disTkMuonPveto_core import LAYERS, process_arrays


class DisappTrksPvetoNativeWorkflow(BaseProcessorABC):
    """PocketCoffea-native Pveto workflow for custom NanoAOD validation.

    This keeps PocketCoffea's normal skim, preselection, category, and cutflow
    machinery, while adding a compact custom accumulator for the old Pveto
    numerator/denominator counts.
    """

    def __init__(self, cfg):
        super().__init__(cfg)
        layers = self.workflow_options.get("layers", LAYERS)
        self.layers = tuple(LAYERS if layers == "all" else layers)
        self.output_format["pveto"] = {
            layer: {
                "cutflow": {},
                "counts": {
                    "p_veto_num_os": processor.value_accumulator(float, 0.0),
                    "p_veto_num_ss": processor.value_accumulator(float, 0.0),
                    "p_veto_den_os": processor.value_accumulator(float, 0.0),
                    "p_veto_den_ss": processor.value_accumulator(float, 0.0),
                },
            }
            for layer in self.layers
        }

    def initialize_calibrators(self):
        self.calibrators_manager = None

    def loop_over_variations(self):
        yield "nominal"

    def define_weights(self):
        self.weights_manager = None

    def compute_weights(self, variation):
        return None

    def define_histograms(self):
        self.hists_manager = None

    def fill_histograms(self, variation):
        return None

    def save_processing_metadata(self):
        return None

    def apply_object_preselection(self, variation):
        return None

    def count_objects(self, variation):
        return None

    def fill_histograms_extra(self, variation):
        if variation != "nominal":
            return
        for layer in self.layers:
            result = process_arrays(self.events, layer)
            target = self.output["pveto"][layer]
            for name, value in result["cutflow"].items():
                target["cutflow"][name] = target["cutflow"].get(name, 0) + int(value)
            for name, value in result["counts"].items():
                target["counts"][name] += float(value)
