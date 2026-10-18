"""A measured answer to « how much does the check actually catch? ».

From a mission's approved data, build sentences whose truth is known: faithful ones (a good check must
accept them) and corrupted ones (a good check must refuse them). Run them all through the same
``check_statement`` the report uses, and count. One category is a known limit on purpose — swapping
a value between two fields of the *same* cited object — so the numbers say what the check cannot see.
"""

from __future__ import annotations

from dataclasses import dataclass

from ebios_rm.reporting.mission_report import check_statement
from ebios_rm.reporting.report_agent import Statement

LEVELS = ["faible", "moyen", "élevé", "critique"]


@dataclass(frozen=True)
class Case:
    category: str
    statement: Statement
    should_refuse: bool


@dataclass(frozen=True)
class Row:
    category: str
    description: str
    expectation: str          # "accepter" | "refuser"
    total: int
    correct: int
    known_limit: bool

    @property
    def rate(self) -> float:
        return self.correct / self.total if self.total else 0.0


CATEGORIES = {
    "fidèle": ("Phrase exacte, bien citée", "accepter", False),
    "identifiant inventé": ("Un identifiant qui n'existe pas (R9, SO-99, M-99…)", "refuser", False),
    "identifiant d'un autre objet": ("Un identifiant réel, mais pas celui de l'objet cité", "refuser", False),
    "source inventée": ("Un champ cité qui n'existe pas", "refuser", False),
    "source absente": ("Aucune source", "refuser", False),
    "source trop vague": ("Une citation qui ne prouve rien (« w5 »)", "refuser", False),
    "niveau inventé": ("Un niveau que les données citées ne contiennent jamais", "refuser", False),
    "niveau échangé (champ cité)": ("Avant et après permutés, avec le champ du niveau cité", "refuser", False),
    "niveau échangé (objet cité)": ("Avant et après permutés, avec l'objet entier cité (limite connue)", "refuser", True),
}


def _other_level(present: set[str]) -> str | None:
    return next((level for level in LEVELS if level not in present), None)


def build_cases(state: dict) -> list[Case]:
    cases: list[Case] = []
    w5 = state.get("w5") or {}
    risks = w5.get("risques", [])
    for i, risk in enumerate(risks):
        rid, avant, apres = risk["id"], str(risk.get("niveau_risque", "")).lower(), str(risk.get("niveau_risque_residuel", "")).lower()
        leaf = [f"w5.risques.{i}.niveau_risque"]
        text = f"Le risque {rid} est au niveau {avant} avant traitement."
        cases.append(Case("fidèle", Statement(text=text, sources=leaf), False))
        cases.append(Case("identifiant inventé", Statement(text=text.replace(rid, "R9"), sources=leaf), True))
        other = next((r["id"] for j, r in enumerate(risks) if j != i), None)
        if other:
            cases.append(Case("identifiant d'un autre objet", Statement(text=text.replace(rid, other), sources=leaf), True))
        cases.append(Case("source inventée", Statement(text=text, sources=[f"w5.risques.{len(risks) + 5}.niveau_risque"]), True))
        cases.append(Case("source absente", Statement(text=text, sources=[]), True))
        cases.append(Case("source trop vague", Statement(text=text, sources=["w5"]), True))
        present = {str(v).lower() for v in risk.values() if isinstance(v, str)}
        missing = _other_level(present)
        if missing:
            cases.append(Case("niveau inventé", Statement(text=f"Le risque {rid} est au niveau {missing}.", sources=leaf), True))
        if apres and apres != avant:
            swapped = f"Le risque {rid} est au niveau {apres} avant traitement."
            cases.append(Case("niveau échangé (champ cité)", Statement(text=swapped, sources=leaf), True))
            cases.append(Case("niveau échangé (objet cité)", Statement(text=swapped, sources=[f"w5.risques.{i}"]), True))
    for i, measure in enumerate(w5.get("mesures", [])):
        if measure.get("priorite"):
            text = f"La mesure {measure['id']} est de priorité {measure['priorite']}."
            leaf = [f"w5.mesures.{i}.priorite"]
            cases.append(Case("fidèle", Statement(text=text, sources=leaf), False))
            cases.append(Case("identifiant inventé", Statement(text=text.replace(measure["id"], "M-99"), sources=leaf), True))
    for i, scenario in enumerate((state.get("w4") or {}).get("scenarios", [])):
        if scenario.get("retenu"):
            text = f"Le mode {scenario['id']} porte le risque du scénario {scenario['scenario_strategique_id']}."
            cases.append(Case("fidèle", Statement(text=text, sources=[f"w4.scenarios.{i}.retenu"]), False))
            cases.append(Case("identifiant inventé", Statement(text=text.replace(scenario["id"], "SO-99"),
                                                              sources=[f"w4.scenarios.{i}.retenu"]), True))
    return cases


def run(state: dict) -> list[Row]:
    cases = build_cases(state)
    rows = []
    for category, (description, expectation, known_limit) in CATEGORIES.items():
        mine = [c for c in cases if c.category == category]
        if not mine:
            continue
        correct = sum((check_statement(c.statement, state) is not None) == c.should_refuse for c in mine)
        rows.append(Row(category, description, expectation, len(mine), correct, known_limit))
    return rows


def to_markdown(rows: list[Row]) -> str:
    lines = ["| Catégorie | Ce que le contrôle doit faire | Cas | Bien traités | Taux |", "|---|---|---|---|---|"]
    for r in rows:
        mark = " (limite connue)" if r.known_limit else ""
        lines.append(f"| {r.category}{mark} | {r.expectation} : {r.description} | {r.total} | {r.correct} | {r.rate:.0%} |")
    catchable = [r for r in rows if not r.known_limit]
    total, correct = sum(r.total for r in catchable), sum(r.correct for r in catchable)
    lines.append("")
    lines.append(f"Hors limite connue : {correct} cas bien traités sur {total} ({correct / total:.0%})." if total else "Aucun cas.")
    return "\n".join(lines)
