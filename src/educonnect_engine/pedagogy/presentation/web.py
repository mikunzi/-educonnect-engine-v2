"""AMO-001 web presentation: one server-rendered FastAPI + Jinja practice flow.

This is a single vertical slice — start, accounting attempts, close the
accounting phase, comparison, finish, correction — for AMO-001 only. It is
not a general EduConnect UI, has no authentication, and has no persistence.

This module never computes accounting truth, diagnoses attempts, decides an
attempt number, or builds a correction/comparison itself. It only calls the
existing `DepreciationPracticeSession` (application layer) and renders
whatever that returns.

Session state: no persistence, no database. Each browser is handed an
opaque, HTTP-only cookie identifying one in-memory `DepreciationPracticeSession`
held in a module-level dict for the process's lifetime. There is no identity
beyond "the browser holding this cookie" — this is not a user-account system.
"""

from __future__ import annotations

import random
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from educonnect_engine.pedagogy.application.depreciation_practice import (
    AccountingPhaseClosedError,
    ComparisonNotAttemptedError,
    ComparisonPhaseNotUnlockedError,
    DepreciationPracticeSession,
)
from educonnect_engine.pedagogy.domain.diagnostics import LearnerAttempt
from educonnect_engine.pedagogy.domain.method_comparison import ComparisonAttempt
from educonnect_engine.pedagogy.presentation.formatting import (
    format_amount,
    format_chf,
    format_rate_percent,
)

app = FastAPI(title="AMO-001 — Amortissements")

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.filters["amount"] = format_amount
templates.env.filters["chf"] = format_chf
templates.env.filters["rate_percent"] = format_rate_percent

_SESSION_COOKIE = "amo001_session_id"
_sessions: dict[str, DepreciationPracticeSession] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _new_seed() -> int:
    """Pick a seed for a brand-new practice. Overridable in tests for determinism."""
    return random.randint(0, 2**31 - 1)


def get_session(
    request: Request, seed: Annotated[int, Depends(_new_seed)]
) -> DepreciationPracticeSession:
    """Fetch this browser's practice session, starting a new one if needed.

    A session, once started, is never regenerated: subsequent requests with
    the same cookie always return the same in-memory session object.
    """
    session_id = request.cookies.get(_SESSION_COOKIE)
    if session_id is None or session_id not in _sessions:
        session_id = str(uuid.uuid4())
        _sessions[session_id] = DepreciationPracticeSession.start(seed=seed)
    request.state.session_id = session_id
    return _sessions[session_id]


def _with_session_cookie(request: Request, response: Response) -> Response:
    response.set_cookie(_SESSION_COOKIE, request.state.session_id, httponly=True, samesite="lax")
    return response


def _parse_decimal(raw: str) -> Decimal:
    try:
        return Decimal(raw.strip())
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount: {raw!r}") from exc


@app.get("/practice/depreciation")
def show_practice(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
) -> Response:
    response = templates.TemplateResponse(
        request=request,
        name="practice.html",
        context={
            "learner_view": session.learner_view,
            "phase": session.phase,
            "result": None,
            "submitted": None,
            "error": None,
        },
    )
    return _with_session_cookie(request, response)


@app.post("/practice/depreciation/new")
def start_new_practice(
    request: Request,
    seed: Annotated[int, Depends(_new_seed)],
) -> Response:
    """Replace this browser's session with a genuinely new practice.

    Reuses the existing cookie when present (no new browser identity is
    created) and starts the new session in `PracticePhase.ACCOUNTING` —
    `DepreciationPracticeSession.start()` always does.
    """
    session_id = request.cookies.get(_SESSION_COOKIE) or str(uuid.uuid4())
    _sessions[session_id] = DepreciationPracticeSession.start(seed=seed)
    request.state.session_id = session_id

    response = RedirectResponse(url="/practice/depreciation", status_code=303)
    return _with_session_cookie(request, response)


@app.post("/practice/depreciation/submit")
def submit_accounting_attempt(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
    depreciation_amount: Annotated[str, Form()],
    debit_account: Annotated[str, Form()],
    credit_account: Annotated[str, Form()],
    entry_amount: Annotated[str, Form()],
    carrying_amount: Annotated[str, Form()],
) -> Response:
    submitted = {
        "depreciation_amount": depreciation_amount,
        "debit_account": debit_account,
        "credit_account": credit_account,
        "entry_amount": entry_amount,
        "carrying_amount": carrying_amount,
    }
    result = None
    error = None
    try:
        attempt = LearnerAttempt(
            depreciation_amount=_parse_decimal(depreciation_amount),
            debit_account=debit_account.strip(),
            credit_account=credit_account.strip(),
            entry_amount=_parse_decimal(entry_amount),
            carrying_amount=_parse_decimal(carrying_amount),
        )
    except ValueError:
        error = "Merci de saisir des montants valides."
    else:
        try:
            result = session.submit(attempt)
        except AccountingPhaseClosedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    response = templates.TemplateResponse(
        request=request,
        name="practice.html",
        context={
            "learner_view": session.learner_view,
            "phase": session.phase,
            "result": result,
            "submitted": submitted,
            "error": error,
        },
    )
    return _with_session_cookie(request, response)


@app.post("/practice/depreciation/complete-accounting-phase")
def close_accounting_phase(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
) -> Response:
    try:
        session.complete_accounting_phase()
    except AccountingPhaseClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response = RedirectResponse(url="/practice/depreciation/comparison", status_code=303)
    return _with_session_cookie(request, response)


@app.get("/practice/depreciation/comparison")
def show_comparison(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
) -> Response:
    try:
        comparison = session.comparison
    except ComparisonPhaseNotUnlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response = templates.TemplateResponse(
        request=request,
        name="comparison.html",
        context={"comparison": comparison, "result": None, "submitted": None, "error": None},
    )
    return _with_session_cookie(request, response)


@app.post("/practice/depreciation/comparison/submit")
def submit_comparison_attempt(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
    direct_credited_account: Annotated[str, Form()],
    indirect_credited_account: Annotated[str, Form()],
    direct_presented_asset_value: Annotated[str, Form()],
    indirect_acquisition_value_shown: Annotated[str, Form()],
    indirect_adjustment_amount: Annotated[str, Form()],
    direct_carrying_amount: Annotated[str, Form()],
    indirect_carrying_amount: Annotated[str, Form()],
) -> Response:
    submitted = {
        "direct_credited_account": direct_credited_account,
        "indirect_credited_account": indirect_credited_account,
        "direct_presented_asset_value": direct_presented_asset_value,
        "indirect_acquisition_value_shown": indirect_acquisition_value_shown,
        "indirect_adjustment_amount": indirect_adjustment_amount,
        "direct_carrying_amount": direct_carrying_amount,
        "indirect_carrying_amount": indirect_carrying_amount,
    }
    result = None
    error = None
    try:
        attempt = ComparisonAttempt(
            direct_credited_account=direct_credited_account.strip(),
            indirect_credited_account=indirect_credited_account.strip(),
            direct_presented_asset_value=_parse_decimal(direct_presented_asset_value),
            indirect_acquisition_value_shown=_parse_decimal(indirect_acquisition_value_shown),
            indirect_adjustment_amount=_parse_decimal(indirect_adjustment_amount),
            direct_carrying_amount=_parse_decimal(direct_carrying_amount),
            indirect_carrying_amount=_parse_decimal(indirect_carrying_amount),
        )
    except ValueError:
        error = "Merci de saisir des montants valides."
    else:
        try:
            result = session.submit_comparison(attempt)
        except ComparisonPhaseNotUnlockedError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    try:
        comparison = session.comparison
    except ComparisonPhaseNotUnlockedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response = templates.TemplateResponse(
        request=request,
        name="comparison.html",
        context={
            "comparison": comparison,
            "result": result,
            "submitted": submitted,
            "error": error,
        },
    )
    return _with_session_cookie(request, response)


@app.post("/practice/depreciation/finish")
def finish_practice(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
) -> Response:
    try:
        session.finish()
    except ComparisonNotAttemptedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response = RedirectResponse(url="/practice/depreciation/correction", status_code=303)
    return _with_session_cookie(request, response)


@app.get("/practice/depreciation/correction")
def show_correction(
    request: Request,
    session: Annotated[DepreciationPracticeSession, Depends(get_session)],
) -> Response:
    try:
        completed = session.finish()  # idempotent: only copies already-built exercise data
    except ComparisonNotAttemptedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    response = templates.TemplateResponse(
        request=request,
        name="correction.html",
        context={"completed": completed},
    )
    return _with_session_cookie(request, response)
