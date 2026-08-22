"""Generate the complete professional intake questionnaire from the catalog.

Renders src/ebios_rm/mission_context/questionnaire.py (QUESTIONNAIRE) to Markdown,
so the client-facing Word document and the machine-read catalog can never drift.
Each question is rendered with its plain-language explanation (for non-technical
readers), its priority, an expected-answer hint, an example, and a blank answer
area. Convert the Markdown to .docx with pandoc afterwards.

Usage:
    python scripts/generate_intake_questionnaire.py [output.md]
"""

from __future__ import annotations

import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ebios_rm.domain.enums import PriorityLevel  # noqa: E402
from ebios_rm.mission_context.questionnaire import QUESTIONNAIRE  # noqa: E402

_PRIORITY_LABEL = {
    PriorityLevel.CRITICAL: "Critique — indispensable pour démarrer l'étude",
    PriorityLevel.IMPORTANT: "Important — si vous ne pouvez pas répondre, indiquez pourquoi",
}

_HEADER = """\
# Questionnaire de contexte — Audit EBIOS Risk Manager

**À l'attention de la personne qui remplit ce document**

Ce questionnaire recueille les informations nécessaires pour cadrer votre audit de
sécurité selon la méthode EBIOS Risk Manager. Il est **volontairement complet** :
prenez le temps qu'il faut, et n'hésitez pas à répondre « je ne sais pas » quand
c'est le cas — c'est une information utile en soi.

**Vous n'avez pas besoin d'être informaticien pour répondre.** Chaque question est
accompagnée d'une explication en langage simple. Répondez avec vos mots.

Comment lire chaque question :

- 🔹 **Explication** : ce que la question signifie, sans jargon.
- 🔸 **Priorité** : « Critique » = nous ne pouvons pas démarrer sans cette réponse ;
  « Important » = si vous ne savez pas, dites-le et expliquez brièvement pourquoi.
- ✏️ **Votre réponse** : écrivez juste en dessous.

Toute réponse que vous écrivez est considérée comme une **déclaration** de votre
part. Vous pouvez joindre des documents (politique de sécurité, schéma réseau,
inventaire, rapport d'audit précédent…) : c'est facultatif, mais l'agent les lira
et en extraira les informations en citant précisément ses sources. Rien ne sera
supposé ou inventé à votre place — les informations manquantes vous seront
redemandées.

---
"""


def render_markdown() -> str:
    lines: list[str] = [_HEADER]
    for section in QUESTIONNAIRE:
        lines.append(f"## {section.title}\n")
        if section.respondent:
            # Who should answer this section. A long form handed to one person yields
            # confident answers to questions outside their competence, and those read
            # exactly like real ones afterwards.
            lines.append(f"**RÉPOND : {section.respondent}**\n")
        lines.append(f"*{section.intro}*\n")
        for q in section.questions:
            lines.append(f"### {q.question}")
            lines.append(f"🔹 **Explication.** {q.explanation}")
            lines.append("")
            lines.append(f"🔸 *Priorité : {_PRIORITY_LABEL[q.priority]}.*")
            if q.answer_hint:
                lines.append(f"Format attendu : {q.answer_hint}.")
            if q.example:
                lines.append(f"Exemple : _{q.example}_")
            lines.append("")
            lines.append("✏️ **Votre réponse :**")
            lines.append("")
            lines.append("> _______________________________________________________________")
            lines.append("")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/intake/questionnaire.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(), encoding="utf-8")
    print(f"Wrote {out_path} ({len(QUESTIONNAIRE)} sections)")
