"""
Spending Change Optimizer for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md §Allowed values, §Choosing Between Safe Plans
"""

from decimal import Decimal
from itertools import combinations
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime, timedelta

from financial_state import FinancialState
from recurrence_detector import RecurringDebitSpec, SalaryCommitment
from simulator import Simulator

class SpendingOptimizer:
    """
    Finds valid spending changes (stop or reduce_to) on flexible recurring events
    when zero-change plans cannot safely complete the request by desired_completion_date.
    """

    @staticmethod
    def get_candidate_interventions(
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
    ) -> List[Dict[str, Any]]:
        interventions = []

        for rd in recurring_debits:
            cat = rd.category
            # Rule: Protected categories must NEVER be modified
            if cat in state.expense_categories_to_protect:
                continue

            ev_id = rd.latest_event_id

            # Can stop?
            if cat in state.expense_categories_user_is_willing_to_stop and rd.flexibility in ("stoppable", "reducible_or_stoppable"):
                interventions.append({
                    "type": "stop",
                    "event_id": ev_id,
                    "category": cat,
                    "action_str": f"stop:{ev_id}",
                    "savings": rd.amount,
                    "target_amount": Decimal("0"),
                })

            # Can reduce?
            if cat in state.expense_categories_user_is_willing_to_reduce and rd.flexibility in ("reducible", "reducible_or_stoppable"):
                if rd.minimum_allowed_amount is not None and rd.minimum_allowed_amount < rd.amount:
                    min_amt = rd.minimum_allowed_amount
                    savings = rd.amount - min_amt
                    # Format amount cleanly
                    amt_str = str(int(min_amt)) if min_amt == min_amt.to_integral() else f"{min_amt:.2f}".rstrip("0").rstrip(".")
                    interventions.append({
                        "type": "reduce_to",
                        "event_id": ev_id,
                        "category": cat,
                        "action_str": f"reduce_to:{ev_id}:{amt_str}",
                        "savings": savings,
                        "target_amount": min_amt,
                    })

        return interventions

    @classmethod
    def optimize(
        cls,
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
        salary_commitment: Optional[SalaryCommitment],
        requested_amount: Decimal,
        desired_completion_date: str,
        eligible_payment_methods: Set[str],
        eligible_options: List[Dict[str, Any]],
        candidate_plan_class: Any,
    ) -> List[Any]:
        candidate_plans = []
        interventions = cls.get_candidate_interventions(state, recurring_debits)
        if not interventions:
            return []

        # Try 1, 2, then 3 spending changes
        for k in (1, 2, 3):
            for combo in combinations(interventions, k):
                # Ensure no event_id is referenced more than once (stopping and reducing same event is mutually exclusive)
                event_ids = [act["event_id"] for act in combo]
                if len(set(event_ids)) != len(event_ids):
                    continue

                stop_ids = {act["event_id"] for act in combo if act["type"] == "stop"}
                reduce_map = {act["event_id"]: act["target_amount"] for act in combo if act["type"] == "reduce_to"}
                spending_changes_dict = {"stop": stop_ids, "reduce_to": reduce_map}
                changes_list = [act["action_str"] for act in combo]

                # 1. Test Full Payment today with these spending changes
                if "full_payment" in eligible_payment_methods:
                    full_res = Simulator.simulate(
                        state=state,
                        recurring_debits=recurring_debits,
                        salary_commitment=salary_commitment,
                        spending_changes=spending_changes_dict,
                        plan_payments=[(state.request_date, requested_amount)],
                    )
                    if full_res.is_safe:
                        completes_by_deadline = (state.request_date <= desired_completion_date)
                        plan = candidate_plan_class(
                            method="full_payment",
                            affordability_status="affordable_with_plan",
                            plan_str=f"{state.request_date}:{cls._fmt_amt(requested_amount)}",
                            payments=[(state.request_date, requested_amount)],
                            start_date=state.request_date,
                            completion_date=state.request_date,
                            total_amount_paid=requested_amount,
                            num_payments=1,
                            payment_option_id="",
                            spending_changes=changes_list,
                            is_safe=True,
                            completes_by_deadline=completes_by_deadline,
                            min_headroom=full_res.min_headroom,
                        )
                        candidate_plans.append(plan)

                # 2. Test Installment Options with these spending changes
                if "installments" in eligible_payment_methods:
                    for opt in eligible_options:
                        opt_payments, opt_total, opt_start, opt_end = cls._build_installment_schedule(opt)
                        inst_horizon = (datetime.strptime(opt_end, "%Y-%m-%d") - datetime.strptime(state.request_date, "%Y-%m-%d")).days
                        deadline_days = (datetime.strptime(desired_completion_date, "%Y-%m-%d") - datetime.strptime(state.request_date, "%Y-%m-%d")).days
                        opt_res = Simulator.simulate(
                            state=state,
                            recurring_debits=recurring_debits,
                            salary_commitment=salary_commitment,
                            spending_changes=spending_changes_dict,
                            plan_payments=opt_payments,
                            days=max(inst_horizon, min(90, deadline_days)),
                        )
                        if opt_res.is_safe:
                            completes_by_deadline = (opt_end <= desired_completion_date)
                            plan_str = "|".join(f"{d}:{cls._fmt_amt(a)}" for d, a in opt_payments)
                            plan = candidate_plan_class(
                                method="installments",
                                affordability_status="affordable_with_plan",
                                plan_str=plan_str,
                                payments=opt_payments,
                                start_date=opt_start,
                                completion_date=opt_end,
                                total_amount_paid=opt_total,
                                num_payments=len(opt_payments),
                                payment_option_id=opt["payment_option_id"],
                                spending_changes=changes_list,
                                is_safe=True,
                                completes_by_deadline=completes_by_deadline,
                                min_headroom=opt_res.min_headroom,
                            )
                            candidate_plans.append(plan)

            # If we found safe plans with k changes, don't unnecessarily generate k+1 changes
            if candidate_plans:
                break

        return candidate_plans

    @staticmethod
    def _build_installment_schedule(opt: Dict[str, Any]) -> Tuple[List[Tuple[str, Decimal]], Decimal, str, str]:
        first_date = datetime.strptime(opt["first_payment_date"], "%Y-%m-%d")
        freq = opt.get("payment_frequency_days") or 30
        n = opt["number_of_payments"]
        amt = opt["payment_amount"]

        payments = []
        for i in range(n):
            d = first_date + timedelta(days=i * freq)
            payments.append((d.strftime("%Y-%m-%d"), amt))

        total_paid = opt["total_payable_amount"]
        start_date = payments[0][0]
        end_date = payments[-1][0]
        return payments, total_paid, start_date, end_date

    @staticmethod
    def _fmt_amt(d: Decimal) -> str:
        if d == d.to_integral():
            return str(int(d))
        return f"{d:.2f}"
