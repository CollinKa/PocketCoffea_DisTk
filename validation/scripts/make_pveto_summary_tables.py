#!/usr/bin/env python3

from __future__ import annotations

import argparse
import ast
import json
import math
import re
import shutil
import subprocess
from pathlib import Path


LAYERS = ("NLayers4", "NLayers5", "NLayers6plus", "combinedBins")

DISPLAY_LAYER = {
    "NLayers4": r"$N_{\mathrm{layers}}=4$",
    "NLayers5": r"$N_{\mathrm{layers}}=5$",
    "NLayers6plus": r"$N_{\mathrm{layers}}\geq 6$",
    "combinedBins": "combined",
}

LATEX_LABELS = {
    "input event kept by SingleMuon trigger skim": r"Input event kept by SingleMuon trigger skim",
    "event passes MET filters": r"Event passes MET filters",
    "event passes jet veto map filter": r"Event passes jet-veto-map filter",
    "event passes SingleMuon triggers": r"Event passes SingleMuon triggers",
    ">= 1 muons pT > 26 GeV": r"$\geq 1$ muon with $p_{\mathrm{T}}>26~\mathrm{GeV}$",
    ">= 1 muons |eta| < 2.1": r"$\geq 1$ muon with $|\eta|<2.1$",
    ">= 1 muons passing tight muon ID": r"$\geq 1$ muon passing tight muon ID",
    ">= 1 passing muon tag": r"$\geq 1$ passing muon tag",
    ">= 1 muons MT(pTmiss, muon) < 40 GeV": (
        r"$\geq 1$ muon with $M_{\mathrm{T}}(p_{\mathrm{T}}^{\mathrm{miss}},\mu)<40~\mathrm{GeV}$"
    ),
    "exactly one passing muon chosen randomly": r"Exactly one passing muon chosen randomly",
    ">= 1 tracks pT > 30 GeV": r"$\geq 1$ track with $p_{\mathrm{T}}>30~\mathrm{GeV}$",
    ">= 1 tracks |eta| < 2.1": r"$\geq 1$ track with $|\eta|<2.1$",
    ">= 1 tracks |eta| < 0.15 OR |eta| > 0.35": (
        r"$\geq 1$ track with $|\eta|<0.15$ or $|\eta|>0.35$"
    ),
    ">= 1 tracks |eta| < 1.42 OR |eta| > 1.65": (
        r"$\geq 1$ track with $|\eta|<1.42$ or $|\eta|>1.65$"
    ),
    ">= 1 tracks |eta| < 1.55 OR |eta| > 1.85": (
        r"$\geq 1$ track with $|\eta|<1.55$ or $|\eta|>1.85$"
    ),
    ">= 1 tracks min DeltaRtrack,noisy/dead ECAL channel > 0.05": (
        r"$\geq 1$ track with $\min\Delta R(\mathrm{track},\mathrm{noisy/dead~ECAL~channel})>0.05$"
    ),
    ">= 1 tracks |dz| > 0.5 cm OR |lambda| > 1e-3": (
        r"$\geq 1$ track with $|d_{z}|>0.5~\mathrm{cm}$ or $|\lambda|>10^{-3}$"
    ),
    ">= 1 tracks number of pixel hits >= 4": r"$\geq 1$ track with $\geq 4$ pixel hits",
    ">= 1 tracks missing inner hits = 0": r"$\geq 1$ track with missing inner hits $=0$",
    ">= 1 tracks missing middle hits = 0": r"$\geq 1$ track with missing middle hits $=0$",
    ">= 1 tracks rel. PF-based iso. < 0.05": (
        r"$\geq 1$ track with relative PF-based isolation $<0.05$"
    ),
    ">= 1 tracks |dxy| < 0.02 cm": r"$\geq 1$ track with $|d_{xy}|<0.02~\mathrm{cm}$",
    ">= 1 tracks |dz| < 0.5 cm": r"$\geq 1$ track with $|d_{z}|<0.5~\mathrm{cm}$",
    ">= 1 track-jet pairs DeltaRtrack,jet > 0.5": (
        r"$\geq 1$ track--jet pair with $\Delta R(\mathrm{track},\mathrm{jet})>0.5$"
    ),
    ">= 1 track-muon pairs Mtrack,muon > 10 GeV": (
        r"$\geq 1$ track--muon pair with $M_{\mathrm{track},\mu}>10~\mathrm{GeV}$"
    ),
    ">= 1 tracks min DeltaRtrack,electron > 0.15": (
        r"$\geq 1$ track with $\min\Delta R(\mathrm{track},e)>0.15$"
    ),
    ">= 1 tracks min DeltaRtrack,had. tau > 0.15": (
        r"$\geq 1$ track with $\min\Delta R(\mathrm{track},\tau_{\mathrm{h}})>0.15$"
    ),
    ">= 1 tracks Ecalo < 10 GeV": r"$\geq 1$ track with $E_{\mathrm{calo}}<10~\mathrm{GeV}$",
    "exactly one passing track chosen randomly": r"Exactly one passing track chosen randomly",
    ">= 1 passing probe track before layer selection": (
        r"$\geq 1$ passing probe track before layer selection"
    ),
    "= 1 track-muon pairs |Mtrack,muon - MZ| < 10 GeV": (
        r"$\geq 1$ track--muon pair with $|M_{\mathrm{track},\mu}-M_{Z}|<10~\mathrm{GeV}$"
    ),
    "= 1 track-muon pairs qtrack * qmuon < 0": (
        r"$\geq 1$ track--muon pair with $q_{\mathrm{track}}q_{\mu}<0$"
    ),
}


def latex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def latex_cut_label(cut: str) -> str:
    if cut.startswith(">= 1 track nlayers >= 4"):
        return r"$\geq 1$ track with $N_{\mathrm{layers}}\geq 4$"
    return LATEX_LABELS.get(cut, latex_escape(cut))


def fmt_count(value: float) -> str:
    return f"{int(round(float(value))):,}"


def fmt_eff(numerator: float, denominator: float | None) -> str:
    if denominator is None or denominator <= 0:
        return "-"
    return f"{float(numerator) / float(denominator):.4f}"


def fmt_pveto(central: float, err_down: float, err_up: float) -> str:
    if central == 0 and err_down == 0 and err_up == 0:
        return r"$0$"
    max_abs = max(abs(central), abs(err_down), abs(err_up))
    if max_abs > 0 and (max_abs < 1.0e-3 or max_abs >= 1.0e4):
        exponent = math.floor(math.log10(max_abs))
        scale = 10.0**exponent
        return (
            rf"$({central / scale:.3g}^{{+{err_up / scale:.2g}}}"
            rf"_{{-{err_down / scale:.2g}}})\times 10^{{{exponent}}}$"
        )
    return rf"${central:.4g}^{{+{err_up:.2g}}}_{{-{err_down:.2g}}}$"


def label_from_add_arg(arg: ast.AST) -> str | None:
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value
    if isinstance(arg, ast.JoinedStr):
        text = ""
        for value in arg.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                text += value.value
            else:
                text += "{layer}"
        return re.sub(r"\s*\(\{layer\}\)", "", text)
    return None


def load_cut_order(core_path: Path) -> list[str]:
    tree = ast.parse(core_path.read_text())
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != "make_tp_cutflow":
            continue
        labels: list[str] = []
        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue
            if not isinstance(child.func, ast.Name) or child.func.id != "add":
                continue
            if not child.args:
                continue
            label = label_from_add_arg(child.args[0])
            if label:
                labels.append(label)
        if labels:
            return labels
    raise RuntimeError(f"Could not find make_tp_cutflow add(...) labels in {core_path}")


def ordered_cut_names(cutflow: dict[str, int], cut_order: list[str], layer: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for label in cut_order:
        candidates = [label]
        if label == ">= 1 track nlayers >= 4":
            candidates = [f">= 1 track nlayers >= 4 ({layer})", label]
        for candidate in candidates:
            if candidate in cutflow and candidate not in seen:
                names.append(candidate)
                seen.add(candidate)
                break

    for label in cutflow:
        if label not in seen:
            names.append(label)
            seen.add(label)
    return names


def pveto_with_uncertainty(counts: dict[str, dict[str, float]]) -> tuple[float, float, float]:
    num_os = counts.get("p_veto_num_os", {})
    num_ss = counts.get("p_veto_num_ss", {})
    den_os = counts.get("p_veto_den_os", {})
    den_ss = counts.get("p_veto_den_ss", {})

    n_os = float(num_os.get("value", 0.0))
    n_ss = float(num_ss.get("value", 0.0))
    d_os = float(den_os.get("value", 0.0))
    d_ss = float(den_ss.get("value", 0.0))

    n_var = float(num_os.get("variance", n_os)) + float(num_ss.get("variance", n_ss))
    d_var = float(den_os.get("variance", d_os)) + float(den_ss.get("variance", d_ss))

    num = n_os - n_ss
    den = d_os - d_ss
    if den <= 0:
        return 0.0, 0.0, 0.0

    sigma_num = math.sqrt(max(n_var, 0.0))
    sigma_den = math.sqrt(max(d_var, 0.0))
    if num < 0:
        return 0.0, 0.0, sigma_num / den

    central = num / den
    rel2 = 0.0
    if num > 0:
        rel2 += (sigma_num / num) ** 2
    if den > 0:
        rel2 += (sigma_den / den) ** 2
    err = abs(central) * math.sqrt(rel2)
    return central, err, err


def count_value(counts: dict[str, dict[str, float]], key: str) -> float:
    return float(counts.get(key, {}).get("value", 0.0))


def write_pveto_table(data: dict, path: Path, caption: str | None = None) -> None:
    lines: list[str] = []
    if caption:
        lines.extend(
            [
                r"\begin{table}[htbp]",
                r"\centering",
                rf"\caption{{{latex_escape(caption)}}}",
                r"\label{tab:muon_pveto_counts}",
            ]
        )
    lines.extend(
        [
            r"\begin{tabular}{lrrrrr}",
            r"\hline",
            (
                r"Layer & $N_{T\&P}$ & $N^{\mathrm{veto}}_{T\&P}$ & "
                r"$N_{SS,T\&P}$ & $N^{\mathrm{veto}}_{SS,T\&P}$ & "
                r"$P_{\mathrm{veto}}$ \\"
            ),
            r"\hline",
        ]
    )
    for layer in LAYERS:
        counts = data["layers"][layer]["counts"]
        central, err_down, err_up = pveto_with_uncertainty(counts)
        lines.append(
            f"{DISPLAY_LAYER[layer]} & "
            f"{fmt_count(count_value(counts, 'p_veto_den_os'))} & "
            f"{fmt_count(count_value(counts, 'p_veto_num_os'))} & "
            f"{fmt_count(count_value(counts, 'p_veto_den_ss'))} & "
            f"{fmt_count(count_value(counts, 'p_veto_num_ss'))} & "
            f"{fmt_pveto(central, err_down, err_up)} \\\\"
        )
    lines.extend([r"\hline", r"\end{tabular}"])
    if caption:
        lines.append(r"\end{table}")
    path.write_text("\n".join(lines) + "\n")


def cutflow_rows(data: dict, layer: str, cut_order: list[str]) -> list[list[str]]:
    cutflow = data["layers"][layer]["cutflow"]
    names = ordered_cut_names(cutflow, cut_order, layer)
    rows: list[list[str]] = []
    first_value: int | None = None
    previous_value: int | None = None

    for name in names:
        value = int(cutflow[name])
        if first_value is None:
            first_value = value
        rows.append(
            [
                latex_cut_label(name),
                fmt_count(value),
                fmt_eff(value, previous_value),
                fmt_eff(value, first_value),
            ]
        )
        previous_value = value
    return rows


def write_cutflow_table(
    data: dict,
    path: Path,
    layer: str,
    cut_order: list[str],
    caption: str | None = None,
) -> None:
    lines: list[str] = []
    if caption:
        lines.extend(
            [
                r"\begin{center}",
                rf"\captionof{{table}}{{{latex_escape(caption)}}}",
                rf"\label{{tab:muon_pveto_cutflow_{layer}}}",
            ]
        )
    lines.extend(
        [
            r"\begin{longtable}{p{0.57\textwidth}rrr}",
            r"\hline",
            r"Selection & Events & $\epsilon_{\mathrm{rel}}$ & $\epsilon_{\mathrm{tot}}$ \\",
            r"\hline",
            r"\endfirsthead",
            r"\hline",
            r"Selection & Events & $\epsilon_{\mathrm{rel}}$ & $\epsilon_{\mathrm{tot}}$ \\",
            r"\hline",
            r"\endhead",
        ]
    )
    for label, count, rel_eff, total_eff in cutflow_rows(data, layer, cut_order):
        lines.append(f"{label} & {count} & {rel_eff} & {total_eff} \\\\")
    lines.extend([r"\hline", r"\end{longtable}"])
    if caption:
        lines.append(r"\end{center}")
    path.write_text("\n".join(lines) + "\n")


def write_document(
    data: dict,
    path: Path,
    run_label: str,
    sample_label: str,
    cut_order: list[str],
    table_files: dict[str, str],
) -> None:
    meta = data.get("merge_info", {})
    n_files = meta.get("n_input_files", len(data.get("input_files", [])))
    n_split = meta.get("n_split_jsons", 0)

    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[margin=0.65in]{geometry}",
        r"\usepackage{caption}",
        r"\usepackage{longtable}",
        r"\usepackage{array}",
        r"\usepackage{booktabs}",
        r"\usepackage{amsmath}",
        r"\usepackage{graphicx}",
        r"\usepackage{fancyhdr}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        r"\lhead{\textbf{CMS} \textit{Preliminary}}",
        rf"\rhead{{{latex_escape(run_label)}}}",
        r"\cfoot{\thepage}",
        r"\setlength{\parindent}{0pt}",
        r"\renewcommand{\arraystretch}{1.12}",
        r"\begin{document}",
        rf"\begin{{center}}\Large\textbf{{Muon Pveto Summary}}\\[2mm]\normalsize {latex_escape(sample_label)}\end{{center}}",
        r"\vspace{2mm}",
        rf"\textbf{{Input files:}} {fmt_count(n_files)}\qquad "
        rf"\textbf{{Split JSON files merged:}} {fmt_count(n_split)}\qquad "
        rf"\textbf{{Tree:}} {latex_escape(str(data.get('tree', 'Events')))}",
        r"\vspace{3mm}",
        rf"\input{{{table_files['pveto']}}}",
        r"\clearpage",
    ]
    for layer in LAYERS:
        lines.extend(
            [
                rf"\section*{{Cutflow: {DISPLAY_LAYER[layer]}}}",
                rf"\input{{{table_files[layer]}}}",
                r"\clearpage",
            ]
        )
    lines.append(r"\end{document}")
    path.write_text("\n".join(lines) + "\n")


def compile_pdf(tex_path: Path) -> None:
    if shutil.which("pdflatex") is None:
        print("pdflatex not found; wrote TeX files only")
        return
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", tex_path.name],
            cwd=tex_path.parent,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Make CMS-style TeX/PDF summary tables from a merged muon Pveto JSON."
    )
    parser.add_argument("--input", required=True, type=Path, help="Merged pveto_summary JSON.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directory for TeX/PDF outputs.")
    parser.add_argument("--core", type=Path, default=None, help="Path to DisTkCoffee/disTkMuonPveto_core.py.")
    parser.add_argument("--output-stem", default=None, help="Base name for the standalone TeX/PDF document.")
    parser.add_argument("--run-label", default="Run 2022D", help="Run label printed in the page header.")
    parser.add_argument("--sample-label", default="Custom NanoAOD muon data", help="Sample label printed below the title.")
    parser.add_argument("--no-compile", action="store_true", help="Write TeX files without running pdflatex.")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_dir = (args.output_dir or input_path.parent).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    core_path = (args.core or repo_root / "DisTkCoffee" / "disTkMuonPveto_core.py").resolve()
    output_stem = args.output_stem or input_path.stem.replace("merged_", "").replace("_summary", "_tables")

    data = json.loads(input_path.read_text())
    cut_order = load_cut_order(core_path)

    pveto_table = output_dir / "pveto_table.tex"
    write_pveto_table(data, pveto_table, caption="Muon veto probability counts and same-sign subtraction.")

    table_files = {"pveto": pveto_table.name}
    for layer in LAYERS:
        table_path = output_dir / f"cutflow_table_{layer}.tex"
        write_cutflow_table(
            data,
            table_path,
            layer,
            cut_order,
            caption=f"Muon tag-and-probe cutflow for {layer}.",
        )
        table_files[layer] = table_path.name

    document_path = output_dir / f"{output_stem}.tex"
    write_document(data, document_path, args.run_label, args.sample_label, cut_order, table_files)

    if not args.no_compile:
        compile_pdf(document_path)

    print(f"Wrote {pveto_table}")
    for layer in LAYERS:
        print(f"Wrote {output_dir / f'cutflow_table_{layer}.tex'}")
    print(f"Wrote {document_path}")
    pdf_path = document_path.with_suffix(".pdf")
    if pdf_path.exists():
        print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    main()
