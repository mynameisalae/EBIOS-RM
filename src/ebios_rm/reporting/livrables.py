"""The EBIOS RM deliverables of a mission, drawn straight from the approved data — no model involved.

The method's final products are not prose: the risk map (« cartographie des risques »), the attack
paths that carry each risk, and the security improvement plan (PACS). They are rendered here from
the approved atelier 4 and 5 outputs, so they are exact and need no verification gate.
"""

from __future__ import annotations

from io import BytesIO

GRAVITY = ["Minimale", "Significative", "Grave", "Critique"]
LEVEL_COLORS = {"Faible": "#B8BFC9", "Moyen": "#E3A83A", "Élevé": "#D26B3A", "Critique": "#BE1E2D"}
_DARK_TEXT = {"Faible", "Moyen"}
NAVY, GREY = "#0E1729", "#5B6573"

PHASE_COLORS = {"Connaître": "E6D8A8", "Rentrer": "E3A83A", "Trouver": "D26B3A", "Exploiter": "BE1E2D"}
AXES = ["gouvernance", "protection", "defense", "resilience"]
AXIS_LABELS = {"gouvernance": "Gouvernance", "protection": "Protection", "defense": "Défense", "resilience": "Résilience"}


def _v_index(value: str | None) -> int | None:
    if value and len(value) == 2 and value[0] == "V" and value[1] in "1234":
        return int(value[1])
    return None


def _plot_map(ax, risks: list[dict], *, residual: bool, title: str) -> None:
    ax.set_xlim(0, 4)
    ax.set_ylim(0, 4)
    for g in range(4):
        for v in range(4):  # v = 0 is V1 at the bottom
            shade = 0.93 - 0.035 * (g + v)
            ax.add_patch(_rect(g, v, (shade, shade + 0.01, shade + 0.03)))
    ax.set_xticks([i + 0.5 for i in range(4)], GRAVITY, fontsize=7.5, color=GREY)
    ax.set_yticks([i + 0.5 for i in range(4)], ["V1", "V2", "V3", "V4"], fontsize=8, color=GREY)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_title(title, fontsize=10, fontweight="bold", color=NAVY, pad=8)
    ax.set_xlabel("Gravité", fontsize=8, color=GREY)
    ax.set_ylabel("Vraisemblance", fontsize=8, color=GREY)
    cells: dict[tuple[int, int], list[dict]] = {}
    for risk in risks:
        g = GRAVITY.index(risk["gravite"]) if risk.get("gravite") in GRAVITY else None
        v = _v_index(risk.get("vraisemblance_residuelle" if residual else "vraisemblance"))
        if g is not None and v is not None:
            cells.setdefault((g, v - 1), []).append(risk)
    for (g, v), group in cells.items():
        for k, risk in enumerate(group):
            level = risk.get("niveau_risque_residuel" if residual else "niveau_risque") or "Faible"
            x = g + (k + 1) / (len(group) + 1)
            ax.scatter([x], [v + 0.5], s=620, color=LEVEL_COLORS.get(level, "#B8BFC9"), edgecolors="white", linewidths=1.5, zorder=3)
            ax.text(x, v + 0.5, risk["id"], ha="center", va="center", fontsize=8, fontweight="bold", zorder=4,
                    color=NAVY if level in _DARK_TEXT else "white")


def _rect(g: int, v: int, color):
    from matplotlib.patches import Rectangle  # noqa: PLC0415

    return Rectangle((g, v), 1, 1, facecolor=color, edgecolor="white", linewidth=2)


def risk_map_png(risks: list[dict]) -> bytes | None:
    """The risk map before and after treatment, side by side. None when there is nothing to draw."""
    if not risks:
        return None
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    fig, (left, right) = plt.subplots(1, 2, figsize=(7.4, 3.7), dpi=200)
    _plot_map(left, risks, residual=False, title="Avant traitement")
    _plot_map(right, risks, residual=True, title="Après traitement (risque résiduel)")
    handles = [plt.Line2D([0], [0], marker="o", linestyle="", markersize=8, markerfacecolor=c, markeredgecolor="white", label=name)
               for name, c in LEVEL_COLORS.items()]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=8, labelcolor=GREY)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    buffer = BytesIO()
    fig.savefig(buffer, format="png", facecolor="white")
    plt.close(fig)
    return buffer.getvalue()


def risk_rows(risks: list[dict]) -> list[list[str]]:
    return [[r["id"], r.get("gravite", ""), f'{r.get("niveau_risque", "")} ({r.get("vraisemblance", "")})',
             f'{r.get("niveau_risque_residuel", "")} ({r.get("vraisemblance_residuelle", "")})',
             str(r.get("option_traitement", "")).capitalize(), r.get("acceptabilite_residuelle", "")] for r in risks]


def _plain(text: str) -> str:
    return " ".join(str(text).lower().split())


def distinct_measures(measures: list[dict]) -> list[dict]:
    """The same wording under two ids is one measure: shown once, with its other ids."""
    seen: dict[str, dict] = {}
    for m in measures:
        key = _plain(m.get("libelle") or m.get("id", ""))
        if key in seen:
            seen[key]["_ids"].append(m["id"])
            seen[key]["risques_ids"] = sorted(set(seen[key].get("risques_ids", [])) | set(m.get("risques_ids", [])))
        else:
            seen[key] = {**m, "_ids": [m["id"]]}
    return list(seen.values())


def pacs_rows(measures: list[dict]) -> list[list[str]]:
    """The improvement plan, by axis then priority: what, who, by when, for which risks."""
    ordered = sorted(distinct_measures(measures), key=lambda m: (
        AXES.index(m.get("axe")) if m.get("axe") in AXES else 9, str(m.get("priorite", "P9")), m["id"]))
    rows = []
    for m in ordered:
        rows.append([
            " / ".join(m["_ids"]),
            m.get("libelle", ""),
            AXIS_LABELS.get(m.get("axe"), str(m.get("axe", ""))),
            str(m.get("priorite", "")),
            str(m.get("echeance", "")),
            str(m.get("responsable", "")),
            ", ".join(m.get("risques_ids", [])),
        ])
    return rows


def attack_path_blocks(w4: dict) -> list[dict]:
    """For each strategic scenario, the operational mode that carries the risk and its steps."""
    blocks = []
    for scenario in w4.get("scenarios", []):
        if not scenario.get("retenu"):
            continue
        steps = [[str(i), s.get("phase", ""), f'{s.get("technique_id") or "—"} {s.get("technique_name", "")}'.strip(),
                  s.get("description", "")] for i, s in enumerate(scenario.get("attack_path", []), 1)]
        blocks.append({
            "title": f'{scenario.get("scenario_strategique_id", "")} — mode retenu {scenario["id"]} '
                     f'({scenario.get("revised_risk_level", "")})',
            "summary": scenario.get("resume", ""),
            "phases": [s.get("phase", "") for s in scenario.get("attack_path", [])],
            "steps": steps,
        })
    return blocks


def follow_up_rows(w5: dict) -> list[list[str]]:
    return [[i["id"], i.get("libelle", ""), str(i.get("cible", "")), str(i.get("frequence", ""))]
            for i in (w5.get("cadre_suivi") or {}).get("indicateurs", [])]
