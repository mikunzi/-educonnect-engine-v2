"""Unit tests for ReverseJournalEntry use case."""

from __future__ import annotations

import inspect
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.application import (
    reverse_journal_entry as reverse_journal_entry_module,
)
from educonnect_engine.accounting.application.reverse_journal_entry import (
    AccountingPeriodClosedError,
    ConcurrencyConflictError,
    InvalidIdempotencyKeyError,
    JournalEntryNotFoundError,
    JournalEntryNotPostedError,
    ReverseJournalEntryCommand,
    ReverseJournalEntryHandler,
    ReverseJournalEntryResult,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
from educonnect_engine.accounting.domain.correction_reason import CorrectionReason
from educonnect_engine.accounting.domain.debit_credit_side import DebitCreditSide
from educonnect_engine.accounting.domain.idempotency_key import IdempotencyKey
from educonnect_engine.accounting.domain.journal_entry import JournalEntry
from educonnect_engine.accounting.domain.journal_entry_id import JournalEntryId
from educonnect_engine.accounting.domain.journal_entry_status import JournalEntryStatus
from educonnect_engine.accounting.domain.journal_line import JournalLine
from educonnect_engine.accounting.domain.repositories import (
    AccountingPeriodRepository,
    IdempotencyRepository,
    JournalEntryRepository,
)
from educonnect_engine.shared.clock import Clock
from educonnect_engine.shared.value_objects.currency import Currency
from educonnect_engine.shared.value_objects.fiscal_year import FiscalYear
from educonnect_engine.shared.value_objects.journal_code import JournalCode
from educonnect_engine.shared.value_objects.journal_reference import JournalReference
from educonnect_engine.shared.value_objects.legal_entity_id import LegalEntityId
from educonnect_engine.shared.value_objects.money import Money


@dataclass
class _FakeJournalEntryRepository(JournalEntryRepository):
    entries: dict[JournalEntryId, JournalEntry]
    save_calls: list[tuple[JournalEntry, JournalEntryId, int]]
    raise_on_get: Exception | None = None
    raise_on_save: Exception | None = None

    def add(self, entry: JournalEntry) -> None:
        self.entries[entry.id] = entry

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        if self.raise_on_get is not None:
            raise self.raise_on_get
        return self.entries.get(entry_id)

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        _ = (entry, expected_version)

    def save_reversal(
        self,
        reversal_entry: JournalEntry,
        original_entry_id: JournalEntryId,
        expected_original_version: int,
    ) -> None:
        if self.raise_on_save is not None:
            raise self.raise_on_save
        self.save_calls.append((reversal_entry, original_entry_id, expected_original_version))
        self.entries[reversal_entry.id] = reversal_entry


@dataclass
class _FakeAccountingPeriodRepository(AccountingPeriodRepository):
    open_flag: bool

    def is_open(
        self,
        legal_entity_id: LegalEntityId,
        fiscal_year: FiscalYear,
        posting_date: date,
    ) -> bool:
        _ = (legal_entity_id, fiscal_year, posting_date)
        return self.open_flag


@dataclass
class _FakeReverseIdempotencyRepository(IdempotencyRepository[ReverseJournalEntryResult]):
    values: dict[IdempotencyKey, ReverseJournalEntryResult]

    def get(self, key: IdempotencyKey) -> ReverseJournalEntryResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: ReverseJournalEntryResult) -> None:
        self.values[key] = result


@dataclass
class _FakeReverseJournalEntryUnitOfWork:
    journal_entry_repository: _FakeJournalEntryRepository
    accounting_period_repository: _FakeAccountingPeriodRepository
    idempotency_repository: _FakeReverseIdempotencyRepository
    fail_commit: bool = False
    entered: int = 0
    commit_calls: int = 0
    rollback_calls: int = 0
    close_calls: int = 0
    active: bool = False

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self.active:
            raise RuntimeError("transaction already active")

        self.active = True
        self.entered += 1
        try:
            yield
            self.commit()
        except Exception:
            self.rollback()
            raise
        finally:
            self.close()

    def commit(self) -> None:
        if not self.active:
            raise RuntimeError("transaction is not active")
        self.commit_calls += 1
        if self.fail_commit:
            raise RuntimeError("commit failed")

    def rollback(self) -> None:
        if not self.active:
            raise RuntimeError("transaction is not active")
        self.rollback_calls += 1

    def close(self) -> None:
        self.close_calls += 1
        self.active = False


@dataclass(frozen=True, slots=True)
class _FixedClock(Clock):
    fixed_now: datetime = datetime(2026, 3, 1, 10, 0, tzinfo=UTC)

    def now_utc(self) -> datetime:
        return self.fixed_now


def _posted_entry() -> JournalEntry:
    recorded = JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-ORIG"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-ORIG"),
        posting_date=date(2026, 2, 1),
        lines=(
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.DEBIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="debit",
            ),
            JournalLine(
                account_number=AccountNumber(value="2000"),
                side=DebitCreditSide.CREDIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="credit",
            ),
        ),
    )
    return recorded.post(posted_at=datetime(2026, 2, 1, 12, 0, tzinfo=UTC))


def _command() -> ReverseJournalEntryCommand:
    return ReverseJournalEntryCommand(
        original_entry_id=JournalEntryId(value="JE-ORIG"),
        expected_version=1,
        idempotency_key=IdempotencyKey(value="rev-001"),
        reversal_entry_id=JournalEntryId(value="JE-REV"),
        reversal_fiscal_year=FiscalYear(value=2026),
        reversal_journal_code=JournalCode(value="ADJ"),
        reversal_reference=JournalReference(value="REV-001"),
        reversal_date=date(2026, 3, 1),
        correction_reason=CorrectionReason(value="Source entry posted with wrong document"),
    )


def _new_uow(
    *,
    original: JournalEntry | None,
    period_open: bool,
    fail_commit: bool = False,
    stored_result: ReverseJournalEntryResult | None = None,
) -> _FakeReverseJournalEntryUnitOfWork:
    entries: dict[JournalEntryId, JournalEntry] = {}
    if original is not None:
        entries[original.id] = original

    idempotency_values: dict[IdempotencyKey, ReverseJournalEntryResult] = {}
    if stored_result is not None:
        idempotency_values[IdempotencyKey(value="rev-001")] = stored_result

    return _FakeReverseJournalEntryUnitOfWork(
        journal_entry_repository=_FakeJournalEntryRepository(entries=entries, save_calls=[]),
        accounting_period_repository=_FakeAccountingPeriodRepository(open_flag=period_open),
        idempotency_repository=_FakeReverseIdempotencyRepository(values=idempotency_values),
        fail_commit=fail_commit,
    )


def test_reverse_journal_entry_first_processing_returns_canonical_result() -> None:
    original = _posted_entry()
    uow = _new_uow(original=original, period_open=True)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    result = use_case.execute(_command())

    assert result.original_entry_id == JournalEntryId(value="JE-ORIG")
    assert result.reversal_entry_id == JournalEntryId(value="JE-REV")
    assert result.status is JournalEntryStatus.POSTED
    assert result.posted_at == datetime(2026, 3, 1, 10, 0, tzinfo=UTC)
    assert result.version == 1
    assert result.idempotent_replay is False
    assert len(uow.journal_entry_repository.save_calls) == 1
    assert uow.journal_entry_repository.save_calls[0][1] == JournalEntryId(value="JE-ORIG")
    assert uow.journal_entry_repository.save_calls[0][2] == 1
    assert uow.idempotency_repository.get(IdempotencyKey(value="rev-001")) == result
    assert uow.entered == 1
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0
    assert uow.close_calls == 1


def test_reverse_journal_entry_replay_returns_copy_with_replay_flag() -> None:
    canonical = ReverseJournalEntryResult(
        original_entry_id=JournalEntryId(value="JE-ORIG"),
        reversal_entry_id=JournalEntryId(value="JE-REV"),
        status=JournalEntryStatus.POSTED,
        posted_at=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
        version=1,
        idempotent_replay=False,
    )
    uow = _new_uow(original=None, period_open=True, stored_result=canonical)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    replay = use_case.execute(_command())

    assert replay.original_entry_id == canonical.original_entry_id
    assert replay.reversal_entry_id == canonical.reversal_entry_id
    assert replay.status is canonical.status
    assert replay.posted_at == canonical.posted_at
    assert replay.version == canonical.version
    assert replay.idempotent_replay is True
    assert uow.journal_entry_repository.save_calls == []
    assert uow.commit_calls == 1
    assert uow.rollback_calls == 0


def test_reverse_journal_entry_raises_not_found() -> None:
    uow = _new_uow(original=None, period_open=True)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(JournalEntryNotFoundError):
        use_case.execute(_command())
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_reverse_journal_entry_raises_not_posted() -> None:
    recorded = JournalEntry.from_recorded(
        id=JournalEntryId(value="JE-ORIG"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-ORIG"),
        posting_date=date(2026, 2, 1),
        lines=(
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.DEBIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="debit",
            ),
            JournalLine(
                account_number=AccountNumber(value="2000"),
                side=DebitCreditSide.CREDIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="credit",
            ),
        ),
    )
    uow = _new_uow(original=recorded, period_open=True)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(JournalEntryNotPostedError):
        use_case.execute(_command())
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_reverse_journal_entry_raises_version_mismatch() -> None:
    original = _posted_entry()
    uow = _new_uow(original=original, period_open=True)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    command = _command()
    mismatched = ReverseJournalEntryCommand(
        original_entry_id=command.original_entry_id,
        expected_version=command.expected_version + 1,
        idempotency_key=command.idempotency_key,
        reversal_entry_id=command.reversal_entry_id,
        reversal_fiscal_year=command.reversal_fiscal_year,
        reversal_journal_code=command.reversal_journal_code,
        reversal_reference=command.reversal_reference,
        reversal_date=command.reversal_date,
        correction_reason=command.correction_reason,
    )

    with pytest.raises(ConcurrencyConflictError, match="version mismatch"):
        use_case.execute(mismatched)
    assert uow.journal_entry_repository.save_calls == []
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_reverse_journal_entry_raises_period_closed() -> None:
    original = _posted_entry()
    uow = _new_uow(original=original, period_open=False)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(AccountingPeriodClosedError):
        use_case.execute(_command())
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1


def test_reverse_journal_entry_rolls_back_on_repository_concurrency_conflict() -> None:
    original = _posted_entry()
    uow = _new_uow(original=original, period_open=True)
    uow.journal_entry_repository.raise_on_save = ConcurrencyConflictError("version mismatch")
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(ConcurrencyConflictError, match="version mismatch"):
        use_case.execute(_command())
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_reverse_journal_entry_raises_invalid_idempotency_key() -> None:
    original = _posted_entry()
    uow = _new_uow(original=original, period_open=True)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            ReverseJournalEntryCommand(
                original_entry_id=JournalEntryId(value="JE-ORIG"),
                expected_version=1,
                idempotency_key="rev-001",  # type: ignore[arg-type]
                reversal_entry_id=JournalEntryId(value="JE-REV"),
                reversal_fiscal_year=FiscalYear(value=2026),
                reversal_journal_code=JournalCode(value="ADJ"),
                reversal_reference=JournalReference(value="REV-001"),
                reversal_date=date(2026, 3, 1),
                correction_reason=CorrectionReason(value="reason"),
            ),
        )
    assert uow.entered == 0
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 0


def test_reverse_journal_entry_raises_runtime_error_when_post_result_is_inconsistent() -> None:
    @dataclass(frozen=True, slots=True)
    class _BrokenPostedEntry:
        id: JournalEntryId
        status: JournalEntryStatus
        posted_at: datetime | None
        version: int

    @dataclass(frozen=True, slots=True)
    class _BrokenReversalEntry:
        id: JournalEntryId

        def post(self, posted_at: datetime) -> _BrokenPostedEntry:
            _ = posted_at
            return _BrokenPostedEntry(
                id=self.id,
                status=JournalEntryStatus.POSTED,
                posted_at=None,
                version=1,
            )

    @dataclass(frozen=True, slots=True)
    class _BrokenOriginal:
        id: JournalEntryId
        legal_entity_id: LegalEntityId
        status: JournalEntryStatus
        version: int

        def build_reversal(
            self,
            *,
            reversal_entry_id: JournalEntryId,
            reversal_fiscal_year: FiscalYear,
            reversal_journal_code: JournalCode,
            reversal_reference: JournalReference,
            reversal_date: date,
            correction_reason: CorrectionReason,
        ) -> _BrokenReversalEntry:
            _ = (
                reversal_fiscal_year,
                reversal_journal_code,
                reversal_reference,
                reversal_date,
                correction_reason,
            )
            return _BrokenReversalEntry(id=reversal_entry_id)

    broken_original = _BrokenOriginal(
        id=JournalEntryId(value="JE-ORIG"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        status=JournalEntryStatus.POSTED,
        version=1,
    )
    uow = _FakeReverseJournalEntryUnitOfWork(
        journal_entry_repository=_FakeJournalEntryRepository(
            entries={broken_original.id: broken_original},  # type: ignore[dict-item]
            save_calls=[],
        ),
        accounting_period_repository=_FakeAccountingPeriodRepository(open_flag=True),
        idempotency_repository=_FakeReverseIdempotencyRepository(values={}),
    )
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(RuntimeError, match="posted_at"):
        use_case.execute(_command())
    assert uow.commit_calls == 0
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_reverse_journal_entry_rolls_back_when_commit_fails() -> None:
    original = _posted_entry()
    uow = _new_uow(original=original, period_open=True, fail_commit=True)
    use_case = ReverseJournalEntryHandler(uow=uow, clock=_FixedClock())

    with pytest.raises(RuntimeError, match="commit failed"):
        use_case.execute(_command())

    assert uow.commit_calls == 1
    assert uow.rollback_calls == 1
    assert uow.close_calls == 1


def test_reverse_journal_entry_module_has_no_sqlite_dependency() -> None:
    source = inspect.getsource(reverse_journal_entry_module)
    assert "sqlite3" not in source
    assert "infrastructure.sqlite" not in source
