"""Priority matrix — what gets asked, and what never does (conception §7, §11.1)."""

from ebios_rm.domain.enums import PriorityLevel
from ebios_rm.mission_context.priority_matrix import blocking_questions, follow_up_questions


def test_empty_important_field_is_asked(example_form):
    names = {q.field_name for q in follow_up_questions(example_form)}
    assert "edr_av_deploye" in names       # empty Important -> asked
    assert "sauvegarde_strategie" in names


def test_answered_field_is_never_asked(example_form):
    names = {q.field_name for q in follow_up_questions(example_form)}
    assert "organisation_nom" not in names      # answered in the form
    assert "acces_distant_moyens" not in names


def test_documents_field_is_never_asked(example_form):
    # Genuinely optional (askable=False) — never raised even though empty.
    names = {q.field_name for q in follow_up_questions(example_form)}
    assert "documents_fournis" not in names


def test_conditional_field_not_asked_when_trigger_false(example_form):
    form = example_form.model_copy(update={
        "donnees_personnelles_traitees": False,
        "categories_donnees_personnelles": None,
    })
    names = {q.field_name for q in follow_up_questions(form)}
    assert "categories_donnees_personnelles" not in names


def test_critical_questions_are_blocking_and_come_first():
    from ebios_rm.mission_context.intake_form import OrgContextForm

    # An almost-empty form: organisation identity fields are Critical and missing.
    form = OrgContextForm(
        organisation_nom="", secteur_activite="", taille_effectif=0,
        systeme_information_resume="", hebergement="cloud",
        teletravail_autorise=False, donnees_personnelles_traitees=False,
    )
    questions = follow_up_questions(form)
    blocking = blocking_questions(form)
    assert blocking, "critical empty fields must produce blocking questions"
    assert all(q.priority is PriorityLevel.CRITICAL for q in blocking)
    # Critical sort before Important.
    priorities = [q.priority for q in questions]
    assert priorities == sorted(priorities, key=lambda p: 0 if p is PriorityLevel.CRITICAL else 1)
