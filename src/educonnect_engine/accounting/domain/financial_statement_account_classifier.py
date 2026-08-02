"""Domain contract for classifying account numbers for statements."""

from typing import Protocol

from .account_classification import AccountClassification
from .account_number import AccountNumber


class FinancialStatementAccountClassifier(Protocol):
    """Classify accounts without embedding chart rules in projections."""

    def classify(self, account_number: AccountNumber) -> AccountClassification:
        """Return financial statement classification for the given account."""
