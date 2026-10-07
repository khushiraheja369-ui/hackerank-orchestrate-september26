"""
90-Day Financial Simulator and Affordability Calculator for Buy or Wait?
Authoritative Reference: problem_statement.md, AGENTS.md §6.1-§6.3
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Set, Optional, Any, Tuple
from collections import defaultdict

from financial_state import FinancialState
from recurrence_detector import RecurringDebitSpec, SalaryCommitment

class SimulationResult:
    def __init__(
        self,
        is_safe: bool,
        min_balance: Decimal,
        min_headroom: Decimal, # min_balance - minimum_balance_to_keep
        daily_balances: List[Tuple[str, Decimal]],
    ):
        self.is_safe = is_safe
        self.min_balance = min_balance
        self.min_headroom = min_headroom
        self.daily_balances = daily_balances

class Simulator:
    """
    Simulates daily balance over 90 days using Decimal arithmetic.
    Does not round or quantize at intermediate steps.
    """

    @staticmethod
    def simulate(
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
        salary_commitment: Optional[SalaryCommitment],
        spending_changes: Optional[Dict[str, Any]] = None, # {'stop': set of event_ids, 'reduce_to': {event_id: new_amount}}
        plan_payments: Optional[List[Tuple[str, Decimal]]] = None, # [(date_str, amount), ...]
        days: int = 90
    ) -> SimulationResult:
        start_d = datetime.strptime(state.request_date, "%Y-%m-%d")
        daily_credits: Dict[str, Decimal] = defaultdict(Decimal)
        daily_debits: Dict[str, Decimal] = defaultdict(Decimal)

        # 1. Confirmed future credits (e.g. scheduled salary)
        for cc in state.confirmed_scheduled_credits:
            sd = cc.get("settlement_date") or cc.get("event_date") or state.request_date
            daily_credits[sd] += cc["amount"]

        # 2. Approved invoices
        for inv in state.message_facts.approved_invoices:
            daily_credits[inv["settlement_date"]] += inv["amount"]

        # 3. Pending and scheduled debits
        for pd in state.pending_scheduled_debits:
            sd = pd.get("settlement_date") or pd.get("event_date") or state.request_date
            daily_debits[sd] += pd["amount"]

        # Parse spending changes filters
        stop_ids: Set[str] = set()
        reduce_map: Dict[str, Decimal] = {}
        if spending_changes:
            stop_ids = spending_changes.get("stop", set())
            reduce_map = spending_changes.get("reduce_to", {})

        # 4. Project calendar over 90 days
        for day_idx in range(days + 1):
            curr_date = start_d + timedelta(days=day_idx)
            curr_d_str = curr_date.strftime("%Y-%m-%d")

            # Salary projection
            if salary_commitment and not state.message_facts.salary_ended:
                if salary_commitment.effective_date and curr_d_str < salary_commitment.effective_date:
                    pass
                else:
                    if curr_date.day == salary_commitment.day_of_month and day_idx > 0:
                        # Only add if no scheduled credit was already recorded for this exact day
                        if curr_d_str not in daily_credits:
                            daily_credits[curr_d_str] += salary_commitment.amount

            # Recurring debits
            for rd in recurring_debits:
                # Apply spending changes
                if rd.latest_event_id in stop_ids:
                    continue
                amt = rd.amount
                if rd.latest_event_id in reduce_map:
                    amt = reduce_map[rd.latest_event_id]

                if amt <= Decimal("0"):
                    continue

                if rd.cadence == "monthly":
                    if curr_date.day == rd.day_of_month:
                        daily_debits[curr_d_str] += amt
                elif rd.cadence == "periodic":
                    if rd.latest_date is not None:
                        days_since = (curr_date - rd.latest_date).days
                        if days_since > 0 and days_since % rd.period_days == 0:
                            daily_debits[curr_d_str] += amt

        # 5. Add custom plan payments if provided
        if plan_payments:
            for p_date, p_amt in plan_payments:
                daily_debits[p_date] += p_amt

        # 6. Execute daily balance progression
        # Same-day aggregation: deterministic netting of credits and debits
        b = state.current_available_balance
        daily_balances: List[Tuple[str, Decimal]] = []
        min_b = b

        for day_idx in range(days + 1):
            curr_date = start_d + timedelta(days=day_idx)
            curr_d_str = curr_date.strftime("%Y-%m-%d")
            b = b + daily_credits[curr_d_str] - daily_debits[curr_d_str]
            daily_balances.append((curr_d_str, b))
            if b < min_b:
                min_b = b

        is_safe = (min_b >= state.minimum_balance_to_keep)
        min_headroom = min_b - state.minimum_balance_to_keep

        return SimulationResult(
            is_safe=is_safe,
            min_balance=min_b,
            min_headroom=min_headroom,
            daily_balances=daily_balances,
        )

    @staticmethod
    def calculate_amount_safe_to_pay(
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
        salary_commitment: Optional[SalaryCommitment],
        requested_amount: Decimal,
    ) -> Decimal:
        """
        Calculates amount_safe_to_pay:
        The largest amount the user can safely pay on request_date before optional
        spending changes, while covering protected expenses and maintaining their minimum balance.
        Capped at requested_amount, bounded below by 0.
        """
        # Baseline simulation with no optional spending changes and no request payment
        baseline = Simulator.simulate(
            state=state,
            recurring_debits=recurring_debits,
            salary_commitment=salary_commitment,
            spending_changes=None,
            plan_payments=None,
        )

        min_headroom = baseline.min_headroom
        if min_headroom <= Decimal("0"):
            return Decimal("0")

        return min(requested_amount, min_headroom)

    @staticmethod
    def calculate_earliest_date_for_full_payment(
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
        salary_commitment: Optional[SalaryCommitment],
        requested_amount: Decimal,
        amount_safe_to_pay: Decimal,
        days: int = 90,
        deadline: Optional[str] = None,
    ) -> str:
        """
        Calculates earliest_date_for_full_payment:
        Earliest date when the full amount is forecast to be safe as a single payment
        without optional spending changes.
        Equals request_date if amount_safe_to_pay == requested_amount.
        Empty string if not safe within the forecast period.
        """
        if amount_safe_to_pay == requested_amount:
            return state.request_date

        start_d = datetime.strptime(state.request_date, "%Y-%m-%d")
        deadline_days = 90
        if deadline:
            try:
                deadline_days = (datetime.strptime(deadline, "%Y-%m-%d") - start_d).days
            except Exception:
                deadline_days = 90

        # Scan each candidate date from day 1 to day 90
        for day_idx in range(days + 1):
            cand_date_str = (start_d + timedelta(days=day_idx)).strftime("%Y-%m-%d")
            eval_days = max(day_idx, min(days, deadline_days))
            res = Simulator.simulate(
                state=state,
                recurring_debits=recurring_debits,
                salary_commitment=salary_commitment,
                spending_changes=None,
                plan_payments=[(cand_date_str, requested_amount)],
                days=eval_days,
            )
            if res.is_safe:
                return cand_date_str

        return ""
