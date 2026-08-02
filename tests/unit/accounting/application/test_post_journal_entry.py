"""Unit tests for PostJournalEntry use case."""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from educonnect_engine.accounting.application.post_journal_entry import (
    AccountingPeriodClosedError,
    ConcurrencyConflictError,
    InvalidIdempotencyKeyError,
    JournalEntryAlreadyPostedError,
    JournalEntryNotFoundError,
    PostJournalEntry,
    PostJournalEntryCommand,
    PostJournalEntryResult,
)
from educonnect_engine.accounting.domain.account_number import AccountNumber
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
    UnitOfWork,
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
    save_calls: list[tuple[JournalEntry, int]]

    def add(self, entry: JournalEntry) -> None:
        self.entries[entry.id] = entry

    def get_by_id(self, entry_id: JournalEntryId) -> JournalEntry | None:
        return self.entries.get(entry_id)

    def save_posted(self, entry: JournalEntry, expected_version: int) -> None:
        self.save_calls.append((entry, expected_version))
        self.entries[entry.id] = entry


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
class _FakeIdempotencyRepository(IdempotencyRepository[PostJournalEntryResult]):
    values: dict[IdempotencyKey, PostJournalEntryResult]

    def get(self, key: IdempotencyKey) -> PostJournalEntryResult | None:
        return self.values.get(key)

    def save(self, key: IdempotencyKey, result: PostJournalEntryResult) -> None:
        self.values[key] = result


@dataclass
class _FakeUnitOfWork(UnitOfWork):
    entered: int = 0

    @contextmanager
    def transaction(self):
        self.entered += 1
        yield


@dataclass(frozen=True, slots=True)
class _FixedClock(Clock):
    fixed_now: datetime = datetime(2026, 1, 31, 12, 0, tzinfo=UTC)

    def now_utc(self) -> datetime:
        return self.fixed_now


def _recorded_entry(entry_id: str = "JE-001", version: int = 0) -> JournalEntry:
    entry = JournalEntry.from_recorded(
        id=JournalEntryId(value=entry_id),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        journal_code=JournalCode(value="GEN"),
        reference=JournalReference(value="REF-001"),
        posting_date=date(2026, 1, 31),
        lines=(
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.DEBIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="debit",
            ),
            JournalLine(
                account_number=AccountNumber(value="1000"),
                side=DebitCreditSide.CREDIT,
                amount=Money(amount=Decimal("10.00"), currency=Currency(code="CHF")),
                description="credit",
            ),
        ),
    )
    return replace(entry, version=version)


def test_post_journal_entry_first_processing_returns_canonical_result() -> None:
    entry = _recorded_entry()
    repository = _FakeJournalEntryRepository(entries={entry.id: entry}, save_calls=[])
    period_repository = _FakeAccountingPeriodRepository(open_flag=True)
    idempotency_repository = _FakeIdempotencyRepository(values={})
    uow = _FakeUnitOfWork()
    use_case = PostJournalEntry(
        repository=repository,
        period_repository=period_repository,
        idempotency_repository=idempotency_repository,
        uow=uow,
        clock=_FixedClock(),
    )

    command = PostJournalEntryCommand(
        journal_entry_id=entry.id,
        expected_version=0,
        idempotency_key=IdempotencyKey(value="post-je-001"),
    )

    result = use_case.execute(command)

    assert result.entry_id == entry.id
    assert result.status is JournalEntryStatus.POSTED
    assert result.posted_at == datetime(2026, 1, 31, 12, 0, tzinfo=UTC)
    assert result.version == 1
    assert result.idempotent_replay is False
    assert len(repository.save_calls) == 1
    assert repository.save_calls[0][1] == 0
    assert idempotency_repository.get(command.idempotency_key) == result
    assert uow.entered == 1


def test_post_journal_entry_replay_returns_copy_with_replay_flag() -> None:
    entry_id = JournalEntryId(value="JE-001")
    canonical = PostJournalEntryResult(
        entry_id=entry_id,
        status=JournalEntryStatus.POSTED,
        posted_at=datetime(2026, 1, 31, 12, 0, tzinfo=UTC),
        version=1,
        idempotent_replay=False,
    )
    repository = _FakeJournalEntryRepository(entries={}, save_calls=[])
    period_repository = _FakeAccountingPeriodRepository(open_flag=True)
    idempotency_repository = _FakeIdempotencyRepository(
        values={IdempotencyKey(value="post-je-001"): canonical},
    )
    use_case = PostJournalEntry(
        repository=repository,
        period_repository=period_repository,
        idempotency_repository=idempotency_repository,
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    result = use_case.execute(
        PostJournalEntryCommand(
            journal_entry_id=entry_id,
            expected_version=1,
            idempotency_key=IdempotencyKey(value="post-je-001"),
        ),
    )

    assert result.entry_id == canonical.entry_id
    assert result.status is canonical.status
    assert result.posted_at == canonical.posted_at
    assert result.version == canonical.version
    assert result.idempotent_replay is True
    assert repository.save_calls == []


def test_post_journal_entry_raises_not_found() -> None:
    use_case = PostJournalEntry(
        repository=_FakeJournalEntryRepository(entries={}, save_calls=[]),
        period_repository=_FakeAccountingPeriodRepository(open_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(JournalEntryNotFoundError):
        use_case.execute(
            PostJournalEntryCommand(
                journal_entry_id=JournalEntryId(value="JE-404"),
                expected_version=0,
                idempotency_key=IdempotencyKey(value="post-je-404"),
            ),
        )


def test_post_journal_entry_raises_concurrency_conflict() -> None:
    entry = _recorded_entry(version=2)
    use_case = PostJournalEntry(
        repository=_FakeJournalEntryRepository(entries={entry.id: entry}, save_calls=[]),
        period_repository=_FakeAccountingPeriodRepository(open_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(ConcurrencyConflictError):
        use_case.execute(
            PostJournalEntryCommand(
                journal_entry_id=entry.id,
                expected_version=1,
                idempotency_key=IdempotencyKey(value="post-je-001"),
            ),
        )


def test_post_journal_entry_raises_period_closed() -> None:
    entry = _recorded_entry(version=0)
    use_case = PostJournalEntry(
        repository=_FakeJournalEntryRepository(entries={entry.id: entry}, save_calls=[]),
        period_repository=_FakeAccountingPeriodRepository(open_flag=False),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(AccountingPeriodClosedError):
        use_case.execute(
            PostJournalEntryCommand(
                journal_entry_id=entry.id,
                expected_version=0,
                idempotency_key=IdempotencyKey(value="post-je-001"),
            ),
        )


def test_post_journal_entry_raises_already_posted() -> None:
    recorded = _recorded_entry(version=0)
    posted = recorded.post(posted_at=datetime(2026, 1, 31, 12, 0, tzinfo=UTC))
    use_case = PostJournalEntry(
        repository=_FakeJournalEntryRepository(entries={posted.id: posted}, save_calls=[]),
        period_repository=_FakeAccountingPeriodRepository(open_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(JournalEntryAlreadyPostedError):
        use_case.execute(
            PostJournalEntryCommand(
                journal_entry_id=posted.id,
                expected_version=1,
                idempotency_key=IdempotencyKey(value="post-je-001"),
            ),
        )


def test_post_journal_entry_raises_invalid_idempotency_key() -> None:
    entry = _recorded_entry()
    use_case = PostJournalEntry(
        repository=_FakeJournalEntryRepository(entries={entry.id: entry}, save_calls=[]),
        period_repository=_FakeAccountingPeriodRepository(open_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(InvalidIdempotencyKeyError):
        use_case.execute(
            PostJournalEntryCommand(
                journal_entry_id=entry.id,
                expected_version=0,
                idempotency_key="post-je-001",  # type: ignore[arg-type]
            ),
        )


def test_post_journal_entry_raises_runtime_error_when_post_result_is_inconsistent() -> None:
    @dataclass(frozen=True, slots=True)
    class _BrokenPostedEntry:
        id: JournalEntryId
        status: JournalEntryStatus
        posted_at: datetime | None
        version: int

    @dataclass(frozen=True, slots=True)
    class _BrokenEntry:
        id: JournalEntryId
        legal_entity_id: LegalEntityId
        fiscal_year: FiscalYear
        posting_date: date
        status: JournalEntryStatus
        version: int

        def post(self, posted_at: datetime) -> _BrokenPostedEntry:
            _ = posted_at
            return _BrokenPostedEntry(
                id=self.id,
                status=JournalEntryStatus.POSTED,
                posted_at=None,
                version=self.version + 1,
            )

    broken_entry = _BrokenEntry(
        id=JournalEntryId(value="JE-001"),
        legal_entity_id=LegalEntityId(value="entity-01"),
        fiscal_year=FiscalYear(value=2026),
        posting_date=date(2026, 1, 31),
        status=JournalEntryStatus.RECORDED,
        version=0,
    )
    repository = _FakeJournalEntryRepository(
        entries={broken_entry.id: broken_entry},  # type: ignore[dict-item]
        save_calls=[],
    )
    use_case = PostJournalEntry(
        repository=repository,
        period_repository=_FakeAccountingPeriodRepository(open_flag=True),
        idempotency_repository=_FakeIdempotencyRepository(values={}),
        uow=_FakeUnitOfWork(),
        clock=_FixedClock(),
    )

    with pytest.raises(RuntimeError, match="posted_at"):
        use_case.execute(
            PostJournalEntryCommand(
                journal_entry_id=broken_entry.id,
                expected_version=0,
                idempotency_key=IdempotencyKey(value="post-je-001"),
            ),
        )
