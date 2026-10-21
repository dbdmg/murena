"""Plot within-case APE heated-surface variation to support threshold choice."""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "backend/research/civicbench/examples/ape_use_code_changes.csv"
DEFAULT_OUTPUT = ROOT / "backend/research/civicbench/examples/surface_variation_threshold.html"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--threshold", type=float, default=20.0, help="Reference threshold in percent")
    args = parser.parse_args()

    areas: dict[str, list[float]] = defaultdict(list)
    with args.input.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                area = float(row["heated_usable_surface"])
            except (TypeError, ValueError):
                continue
            if area > 0:
                areas[row["case_id"]].append(area)

    # One point per cadastral case: full span, normalized by the larger area.
    variations = np.array([
        100 * (max(values) - min(values)) / max(values)
        for values in areas.values() if len(values) >= 2
    ])
    if not len(variations):
        raise SystemExit("No cases with at least two positive surface values found")

    threshold = args.threshold
    below = int(np.count_nonzero(variations <= threshold))
    above = len(variations) - below
    median, q1, q3 = np.percentile(variations, [50, 25, 75])
    sorted_values = np.sort(variations)
    ecdf = np.arange(1, len(sorted_values) + 1) / len(sorted_values) * 100

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.12,
                        subplot_titles=("Distribuzione delle variazioni", "Quota cumulativa dei casi"))
    edges = np.arange(0, 105, 5)
    centers = (edges[:-1] + edges[1:]) / 2
    counts, _ = np.histogram(variations, bins=edges)
    colors = ["#2878B5" if right <= threshold else "#E39C37"
              for right in edges[1:]]
    fig.add_trace(go.Bar(x=centers, y=counts, width=4.5, marker_color=colors,
                         customdata=np.column_stack((edges[:-1], edges[1:])),
                         hovertemplate="Intervallo %{customdata[0]:.0f}–%{customdata[1]:.0f}%<br>Casi %{y}<extra></extra>",
                         name="Casi per intervallo"), row=1, col=1)
    fig.add_trace(go.Scatter(x=sorted_values, y=ecdf, mode="lines",
                             line={"color": "#334155", "width": 3},
                             hovertemplate="Variazione %{x:.1f}%<br>Casi cumulativi %{y:.1f}%<extra></extra>",
                             name="Cumulativa"), row=2, col=1)
    at_threshold = below / len(variations) * 100
    fig.add_trace(go.Scatter(x=[threshold], y=[at_threshold], mode="markers",
                             marker={"color": "#9A3412", "size": 10},
                             hovertemplate=f"Soglia {threshold:g}%<br>{below} casi entro soglia<extra></extra>",
                             name="Quota alla soglia"), row=2, col=1)
    fig.add_vline(x=threshold, line_dash="dash", line_color="#9A3412", line_width=2,
                  annotation_text=f"Soglia {threshold:g}%", annotation_position="top right")
    fig.add_hline(y=at_threshold, row=2, col=1, line_dash="dot", line_color="#9A3412", opacity=.7)
    fig.update_layout(template="plotly_white", height=800, width=1100,
        title={"text": "Variazione della superficie utile riscaldata tra APE dello stesso case ID",
               "x": .04, "xanchor": "left"},
        bargap=.06, legend={"orientation": "h", "y": 1.02, "x": 1, "xanchor": "right"},
        margin={"l": 75, "r": 45, "t": 120, "b": 120},
        annotations=[*fig.layout.annotations,
            {"text": f"N = {len(variations)} casi · mediana {median:.1f}% · intervallo interquartile {q1:.1f}–{q3:.1f}% · ≤{threshold:g}%: {below} ({below/len(variations):.1%}) · >{threshold:g}%: {above} ({above/len(variations):.1%})",
             "xref": "paper", "yref": "paper", "x": 0, "y": 1.09, "showarrow": False,
             "xanchor": "left", "font": {"size": 12, "color": "#334155"}},
            {"text": "Una osservazione per case ID. La soglia è un riferimento esplorativo, non un limite normativo né una validazione dell’identità fisica.",
             "xref": "paper", "yref": "paper", "x": 0, "y": -0.21, "showarrow": False,
             "xanchor": "left", "font": {"size": 11, "color": "#475569"}}])
    fig.update_yaxes(title_text="Numero di casi", rangemode="tozero", row=1, col=1)
    fig.update_yaxes(title_text="Casi cumulativi (%)", range=[0, 100], row=2, col=1)
    fig.update_xaxes(title_text="Variazione per case ID: (superficie max − superficie min) / superficie max × 100",
                     range=[0, 100], dtick=10, row=2, col=1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(args.output, include_plotlyjs=True, full_html=True)
    print(f"cases={len(variations)} median={median:.2f}% q1={q1:.2f}% q3={q3:.2f}%")
    print(f"at_or_below_{threshold:g}={below} above={above}")
    print(f"html={args.output}")


if __name__ == "__main__":
    main()
