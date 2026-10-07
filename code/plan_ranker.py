"""
Plan Ranking Engine for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md §Choosing Between Safe Plans
"""

from decimal import Decimal
from typing import List, Any

class PlanRanker:
    """
    Ranks safe and eligible plans according to the 6 mandatory criteria:
    1. Complete the full request by desired_completion_date.
    2. Require no spending changes (and fewer spending changes).
    3. Minimize the total amount paid.
    4. Start payment earlier.
    5. Use fewer payments.
    6. Use the lowest payment_option_id as the final tie-breaker.
    """

    @staticmethod
    def sort_key(plan: Any) -> tuple:
        # Criterion 1: Complete by desired_completion_date (1 for True, 0 for False)
        completes_by_deadline = 1 if plan.completes_by_deadline else 0

        # Criterion 2: Spending changes needed (0 changes is best, then fewer changes)
        num_changes = len(plan.spending_changes) if plan.spending_changes else 0

        # Criterion 3: Total amount paid (lower is better)
        total_paid = plan.total_amount_paid

        # Criterion 4: Start date earlier (earlier date string is lexicographically smaller)
        start_date = plan.start_date or "9999-99-99"

        # Criterion 5: Fewer payments
        num_payments = plan.num_payments

        # Criterion 6: Lowest payment_option_id as final tie-breaker
        # Empty string for non-option plans gets sorted after or consistently
        opt_id = plan.payment_option_id or "zzzzzz"

        return (
            -completes_by_deadline, # Descending (True first)
            num_changes,            # Ascending (0 changes first)
            total_paid,             # Ascending (minimize total paid)
            start_date,             # Ascending (earliest date first)
            num_payments,           # Ascending (fewer payments first)
            opt_id,                 # Ascending (lowest option ID first)
        )

    @classmethod
    def rank_plans(cls, plans: List[Any]) -> List[Any]:
        return sorted(plans, key=cls.sort_key)
