import html
import inspect

import pytest
from fastapi.testclient import TestClient

from educonnect_engine.accounting.depreciation import solve
from educonnect_engine.pedagogy.domain.exercise import build_depreciation_exercise
from educonnect_engine.pedagogy.domain.generator import generate_depreciation_problem
from educonnect_engine.pedagogy.domain.method_comparison import build_method_comparison
from educonnect_engine.pedagogy.presentation import web as web_module
from educonnect_engine.pedagogy.presentation.formatting import (
    format_amount,
    format_chf,
    format_rate_percent,
)
from educonnect_engine.pedagogy.presentation.web import _new_seed, app

_SEED = 42


def _accounting_form(solution) -> dict[str, str]:
    return {
        "depreciation_amount": str(solution.depreciation_amount),
        "debit_account": solution.debit_account,
        "credit_account": solution.credit_account,
        "entry_amount": str(solution.entry_amount),
        "carrying_amount": str(solution.carrying_amount),
    }


def _vcn_form(solution) -> dict[str, str]:
    data = _accounting_form(solution)
    data["depreciation_amount"] = str(solution.carrying_amount)
    return data


def _comparison_form(comparison) -> dict[str, str]:
    return {
        "direct_credited_account": comparison.direct.credited_account,
        "indirect_credited_account": comparison.indirect.credited_account,
        "direct_presented_asset_value": str(comparison.direct.asset_value_presented),
        "indirect_acquisition_value_shown": str(comparison.indirect.asset_value_presented),
        "indirect_adjustment_amount": str(comparison.indirect.adjustment_account_balance),
        "direct_carrying_amount": str(comparison.direct.carrying_amount),
        "indirect_carrying_amount": str(comparison.indirect.carrying_amount),
    }


def _finish_practice(client, seed: int) -> None:
    """Drive a session all the way to PracticePhase.COMPLETED."""
    problem = generate_depreciation_problem(seed=seed)
    solution = solve(problem)
    comparison = build_method_comparison(problem)

    client.get("/practice/depreciation")
    client.post("/practice/depreciation/submit", data=_accounting_form(solution))
    client.post("/practice/depreciation/complete-accounting-phase")
    client.post("/practice/depreciation/comparison/submit", data=_comparison_form(comparison))
    client.post("/practice/depreciation/finish")


@pytest.fixture
def client():
    app.dependency_overrides[_new_seed] = lambda: _SEED
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- 1-5: initial GET does not leak, does show the problem ---


def test_initial_get_shows_professional_situation(client):
    response = client.get("/practice/depreciation")

    assert response.status_code == 200
    problem = generate_depreciation_problem(seed=_SEED)
    assert problem.context in response.text
    assert "perte de valeur" in response.text.lower()  # economic rationale


def test_initial_get_shows_acquisition_value_and_rate(client):
    response = client.get("/practice/depreciation")
    text = html.unescape(response.text)

    problem = generate_depreciation_problem(seed=_SEED)
    assert format_chf(problem.acquisition_value) in text
    assert format_rate_percent(problem.rate) in text


def test_initial_get_does_not_leak_expected_depreciation_or_carrying_amount(client):
    response = client.get("/practice/depreciation")

    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)
    assert str(solution.depreciation_amount) not in response.text
    assert str(solution.carrying_amount) not in response.text


def test_initial_get_does_not_leak_expected_debit_or_credit_account(client):
    response = client.get("/practice/depreciation")

    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)
    assert solution.debit_account not in response.text
    assert solution.credit_account not in response.text


# --- 6-8: accounting submission, retry, attempt-number-driven feedback ---


def test_first_accounting_post_displays_score_and_feedback(client):
    client.get("/practice/depreciation")
    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)

    response = client.post("/practice/depreciation/submit", data=_accounting_form(solution))

    assert response.status_code == 200
    assert "10" in response.text
    assert "Bravo, votre réponse est entièrement correcte." in response.text


def test_first_wrong_attempt_shows_hint_not_explanation(client):
    client.get("/practice/depreciation")
    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)

    response = client.post("/practice/depreciation/submit", data=_vcn_form(solution))

    assert "HINT" in response.text
    assert "EXPLANATION" not in response.text
    assert "valeur comptable nette" in response.text.lower()


def test_second_same_wrong_attempt_shows_explanation(client):
    client.get("/practice/depreciation")
    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)
    data = _vcn_form(solution)

    client.post("/practice/depreciation/submit", data=data)
    response = client.post("/practice/depreciation/submit", data=data)

    assert "EXPLANATION" in response.text
    assert "HINT" not in response.text
    assert str(solution.carrying_amount) in response.text


# --- 9-10: closing accounting phase ---


def test_closing_accounting_phase_does_not_reveal_correction(client):
    client.get("/practice/depreciation")
    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)

    response = client.post("/practice/depreciation/complete-accounting-phase")

    assert str(solution.depreciation_amount) not in response.text
    assert str(solution.carrying_amount) not in response.text
    assert solution.debit_account not in response.text


def test_comparison_page_not_accessible_before_accounting_phase_closed(client):
    client.get("/practice/depreciation")

    response = client.get("/practice/depreciation/comparison")

    assert response.status_code == 409


def test_comparison_page_accessible_after_accounting_phase_closed(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")

    response = client.get("/practice/depreciation/comparison")

    assert response.status_code == 200


# --- 11-12: comparison page ---


def test_comparison_page_does_not_expose_expected_values(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")
    problem = generate_depreciation_problem(seed=_SEED)
    comparison = build_method_comparison(problem)

    response = client.get("/practice/depreciation/comparison")

    assert str(comparison.indirect.adjustment_account_balance) not in response.text
    assert str(comparison.direct.asset_value_presented) not in response.text


def test_comparison_submit_displays_component_correctness(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")
    problem = generate_depreciation_problem(seed=_SEED)
    comparison = build_method_comparison(problem)
    data = _comparison_form(comparison)
    data["indirect_carrying_amount"] = "999"  # deliberately wrong

    response = client.post("/practice/depreciation/comparison/submit", data=data)

    assert response.status_code == 200
    assert "correct" in response.text.lower()
    assert "incorrect" in response.text.lower()


# --- 13-15: finish and correction ---


def test_correction_not_available_before_comparison_attempt(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")

    response = client.get("/practice/depreciation/correction")

    assert response.status_code == 409


def test_finish_displays_expected_answer_after_comparison_attempt(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")
    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)
    comparison = build_method_comparison(problem)
    client.post("/practice/depreciation/comparison/submit", data=_comparison_form(comparison))

    response = client.post("/practice/depreciation/finish")
    text = html.unescape(response.text)

    assert response.status_code == 200
    assert format_chf(solution.depreciation_amount) in text
    assert format_chf(solution.carrying_amount) in text
    assert solution.debit_account in text
    assert solution.credit_account in text


def test_correction_page_displays_calculation_steps_and_method_explanation(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")
    problem = generate_depreciation_problem(seed=_SEED)
    comparison = build_method_comparison(problem)
    client.post("/practice/depreciation/comparison/submit", data=_comparison_form(comparison))

    response = client.post("/practice/depreciation/finish")

    exercise = build_depreciation_exercise(problem)
    unescaped_text = html.unescape(response.text)
    for step in exercise.correction.calculation_steps:
        assert format_amount(step.left_operand) in unescaped_text
        right_formatted = (
            format_rate_percent(step.right_operand)
            if step.right_operand_is_rate
            else format_amount(step.right_operand)
        )
        assert right_formatted in unescaped_text
        assert format_amount(step.result) in unescaped_text
    assert exercise.correction.method_explanation in unescaped_text


# --- 16-17: session stability and phase enforcement ---


def test_same_session_keeps_the_same_problem_even_if_seed_would_differ():
    seeds = iter([1, 2, 3, 4, 5])
    app.dependency_overrides[_new_seed] = lambda: next(seeds)
    try:
        with TestClient(app) as isolated_client:
            first = isolated_client.get("/practice/depreciation")
            second = isolated_client.get("/practice/depreciation")
    finally:
        app.dependency_overrides.clear()

    problem_for_seed_one = generate_depreciation_problem(seed=1)
    assert format_chf(problem_for_seed_one.acquisition_value) in html.unescape(first.text)
    assert format_chf(problem_for_seed_one.acquisition_value) in html.unescape(second.text)


def test_two_browsers_have_isolated_sessions() -> None:
    app.dependency_overrides[_new_seed] = lambda: _SEED
    try:
        with TestClient(app) as browser_a, TestClient(app) as browser_b:
            browser_a.get("/practice/depreciation")
            browser_b.get("/practice/depreciation")

            assert browser_a.cookies.get("amo001_session_id") != browser_b.cookies.get(
                "amo001_session_id"
            )

            browser_a.post("/practice/depreciation/complete-accounting-phase")

            assert browser_a.get("/practice/depreciation/comparison").status_code == 200
            assert browser_b.get("/practice/depreciation/comparison").status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_accounting_submission_rejected_after_phase_closed(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")
    problem = generate_depreciation_problem(seed=_SEED)
    solution = solve(problem)

    response = client.post("/practice/depreciation/submit", data=_accounting_form(solution))

    assert response.status_code == 409


# --- 18-19: no formula duplication, no manual attempt_number ---


def test_web_module_contains_no_depreciation_calculation_formula():
    source = inspect.getsource(web_module)

    assert "acquisition_value *" not in source
    assert "* problem.rate" not in source
    assert "acquisition_value -" not in source


def test_web_module_never_supplies_attempt_number_manually():
    source = inspect.getsource(web_module)

    assert "attempt_number=" not in source
    assert "attempt_number =" not in source


# --- 20: full end-to-end flow ---


def test_full_presentation_flow_end_to_end():
    app.dependency_overrides[_new_seed] = lambda: 99
    try:
        with TestClient(app) as flow_client:
            problem = generate_depreciation_problem(seed=99)
            solution = solve(problem)
            comparison = build_method_comparison(problem)

            response = flow_client.get("/practice/depreciation")
            assert response.status_code == 200

            response = flow_client.post(
                "/practice/depreciation/submit", data=_accounting_form(solution)
            )
            assert response.status_code == 200
            assert "Bravo, votre réponse est entièrement correcte." in response.text

            response = flow_client.post("/practice/depreciation/complete-accounting-phase")
            assert response.status_code == 200

            response = flow_client.post(
                "/practice/depreciation/comparison/submit", data=_comparison_form(comparison)
            )
            assert response.status_code == 200
            assert "correct" in response.text.lower()

            response = flow_client.post("/practice/depreciation/finish")
            assert response.status_code == 200
            assert format_chf(solution.depreciation_amount) in html.unescape(response.text)
    finally:
        app.dependency_overrides.clear()


# --- Pilot readiness FIX 1: completed state + new exercise ---


def test_comparison_phase_page_indicates_accounting_is_complete_with_cta(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")

    response = client.get("/practice/depreciation")

    assert "continuer vers la comparaison" in response.text.lower()
    assert "Exercice terminé" not in response.text


def test_completed_page_never_says_continue_to_comparison(client):
    _finish_practice(client, _SEED)

    response = client.get("/practice/depreciation")

    assert "continuer vers la comparaison" not in response.text.lower()


def test_completed_page_says_exercise_finished(client):
    _finish_practice(client, _SEED)

    response = client.get("/practice/depreciation")

    assert "Exercice terminé" in response.text


def test_completed_page_exposes_new_exercise_cta(client):
    _finish_practice(client, _SEED)

    response = client.get("/practice/depreciation")

    assert "Nouvel exercice" in response.text


def test_post_new_creates_a_fresh_session(client):
    _finish_practice(client, _SEED)

    app.dependency_overrides[_new_seed] = lambda: _SEED + 1
    response = client.post("/practice/depreciation/new")
    new_problem = generate_depreciation_problem(seed=_SEED + 1)

    assert response.status_code == 200  # redirect followed
    assert format_chf(new_problem.acquisition_value) in html.unescape(response.text)


def test_new_practice_starts_in_accounting_phase(client):
    _finish_practice(client, _SEED)

    app.dependency_overrides[_new_seed] = lambda: _SEED + 2
    client.post("/practice/depreciation/new")
    response = client.get("/practice/depreciation")

    assert "Valider ma réponse" in response.text


def test_new_practice_does_not_expose_previous_correction(client):
    _finish_practice(client, _SEED)

    app.dependency_overrides[_new_seed] = lambda: _SEED + 3
    client.post("/practice/depreciation/new")

    response = client.get("/practice/depreciation/correction")

    assert response.status_code == 409


def test_existing_browser_session_now_points_to_the_new_problem(client):
    _finish_practice(client, _SEED)

    app.dependency_overrides[_new_seed] = lambda: _SEED + 4
    client.post("/practice/depreciation/new")
    new_problem = generate_depreciation_problem(seed=_SEED + 4)

    response = client.get("/practice/depreciation")

    assert format_chf(new_problem.acquisition_value) in html.unescape(response.text)


# --- Pilot readiness FIX 3: accounting form reads as a journal entry ---


def test_accounting_form_is_grouped_into_calcul_ecriture_controle_sections(client):
    response = client.get("/practice/depreciation")
    text = response.text

    calcul_index = text.find("Calcul")
    ecriture_index = text.find("Écriture comptable")
    controle_index = text.find("Contrôle")

    assert calcul_index != -1
    assert ecriture_index != -1
    assert controle_index != -1
    assert calcul_index < ecriture_index < controle_index


def test_accounting_form_presents_debit_and_credit_as_a_single_journal_entry(client):
    response = client.get("/practice/depreciation")
    text = response.text

    debit_index = text.find("Débit")
    credit_index = text.find("Crédit")
    assert debit_index != -1
    assert credit_index != -1
    assert debit_index < credit_index

    # A single journal-entry amount field — no second, invented domain amount.
    assert text.count('name="entry_amount"') == 1
    assert 'name="debit_amount"' not in text
    assert 'name="credit_amount"' not in text


# --- Pilot readiness FIX 4: comparison accessibility ---


def test_comparison_inputs_each_have_a_unique_id_and_label(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")

    response = client.get("/practice/depreciation/comparison")
    text = response.text

    field_ids = [
        "direct_credited_account",
        "indirect_credited_account",
        "direct_presented_asset_value",
        "indirect_acquisition_value_shown",
        "indirect_adjustment_amount",
        "direct_carrying_amount",
        "indirect_carrying_amount",
    ]
    for field_id in field_ids:
        assert f'id="{field_id}"' in text
        assert f'for="{field_id}"' in text


def test_comparison_input_accessible_names_communicate_field_and_method(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")

    response = client.get("/practice/depreciation/comparison")
    text = html.unescape(response.text)

    assert "Compte crédité — méthode directe" in text
    assert "Compte crédité — méthode indirecte" in text
    assert "Valeur de l'actif présentée — méthode directe" in text
    assert "Valeur de l'actif présentée — méthode indirecte" in text
    assert "Solde du compte d'ajustement de valeur — méthode indirecte" in text
    assert "Valeur comptable nette — méthode directe" in text
    assert "Valeur comptable nette — méthode indirecte" in text


# --- Pilot readiness FIX 5: conceptual clarification on the comparison page ---


def test_comparison_page_explains_the_direct_indirect_distinction_without_leaking_values(client):
    client.get("/practice/depreciation")
    client.post("/practice/depreciation/complete-accounting-phase")
    problem = generate_depreciation_problem(seed=_SEED)
    comparison = build_method_comparison(problem)

    response = client.get("/practice/depreciation/comparison")
    text = response.text
    text_lower = text.lower()

    assert "réduit directement" in text_lower
    assert "compte d'ajustement de valeur" in text_lower

    # Conceptual scaffolding only — no expected numbers or account numbers.
    assert str(comparison.direct.asset_value_presented) not in text
    assert str(comparison.indirect.asset_value_presented) not in text
    assert str(comparison.indirect.adjustment_account_balance) not in text
    assert comparison.direct.credited_account not in text
    assert comparison.indirect.credited_account not in text


# --- Pilot readiness trivial fix: no duplicate problem-data presentation ---


def test_practice_page_shows_acquisition_value_exactly_once(client):
    response = client.get("/practice/depreciation")
    text = html.unescape(response.text)
    problem = generate_depreciation_problem(seed=_SEED)

    assert text.count(format_chf(problem.acquisition_value)) == 1
