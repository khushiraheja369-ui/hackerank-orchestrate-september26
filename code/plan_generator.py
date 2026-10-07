"""
Candidate Plan Generator for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md §Allowed values, §Choosing Between Safe Plans
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Set, Optional, Any, Tuple

from financial_state import FinancialState
from recurrence_detector import RecurringDebitSpec, SalaryCommitment
from simulator import Simulator, SimulationResult
from plan_ranker import PlanRanker
from spending_optimizer import SpendingOptimizer

class CandidatePlan:
    def __init__(
        self,
        method: str, # 'full_payment', 'partial_payment', 'installments', 'wait', 'not_recommended'
        affordability_status: str, # 'affordable_now', 'affordable_with_plan', 'affordable_later', 'not_affordable'
        plan_str: str,
        payments: List[Tuple[str, Decimal]],
        start_date: str,
        completion_date: str,
        total_amount_paid: Decimal,
        num_payments: int,
        payment_option_id: str = "",
        spending_changes: Optional[List[str]] = None,
        is_safe: bool = True,
        completes_by_deadline: bool = True,
        min_headroom: Decimal = Decimal("0"),
    ):
        self.method = method
        self.affordability_status = affordability_status
        self.plan_str = plan_str
        self.payments = payments
        self.start_date = start_date
        self.completion_date = completion_date
        self.total_amount_paid = total_amount_paid
        self.num_payments = num_payments
        self.payment_option_id = payment_option_id
        self.spending_changes = spending_changes or []
        self.is_safe = is_safe
        self.completes_by_deadline = completes_by_deadline
        self.min_headroom = min_headroom

    @property
    def spending_changes_str(self) -> str:
        return "|".join(self.spending_changes) if self.spending_changes else "none"

class PlanGenerator:
    """
    Generates, evaluates, and selects the winning financial plan.
    """

    @classmethod
    def generate_and_select_plan(
        cls,
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
        salary_commitment: Optional[SalaryCommitment],
        request: Dict[str, Any],
        payment_options: List[Dict[str, Any]],
    ) -> Tuple[CandidatePlan, Decimal, str, List[CandidatePlan]]:
        req_date = state.request_date
        req_amt = request["requested_amount"]
        deadline = request["desired_completion_date"]
        allows_partial = request.get("allows_partial_payment", False)
        allowed_methods = state.payment_methods_user_will_consider

        # 1. Baseline safe amount and earliest safe date
        amount_safe_to_pay = Simulator.calculate_amount_safe_to_pay(
            state=state,
            recurring_debits=recurring_debits,
            salary_commitment=salary_commitment,
            requested_amount=req_amt,
        )

        earliest_date_for_full_payment = Simulator.calculate_earliest_date_for_full_payment(
            state=state,
            recurring_debits=recurring_debits,
            salary_commitment=salary_commitment,
            requested_amount=req_amt,
            amount_safe_to_pay=amount_safe_to_pay,
            deadline=deadline,
        )

        candidate_plans: List[CandidatePlan] = []

        # 2. Candidate: Full Payment
        if "full_payment" in allowed_methods and amount_safe_to_pay == req_amt:
            plan = CandidatePlan(
                method="full_payment",
                affordability_status="affordable_now",
                plan_str=f"{req_date}:{cls._fmt_amt(req_amt)}",
                payments=[(req_date, req_amt)],
                start_date=req_date,
                completion_date=req_date,
                total_amount_paid=req_amt,
                num_payments=1,
                payment_option_id="",
                spending_changes=[],
                is_safe=True,
                completes_by_deadline=(req_date <= deadline),
            )
            candidate_plans.append(plan)

        # 3. Candidate: Partial Payment
        # Mandatory conditions from problem_statement.md:
        # - request allows partial payment
        # - user accepts partial_payment
        # - 0 < amount_safe_to_pay < requested_amount
        # - earliest_date_for_full_payment <= desired_completion_date
        if (
            allows_partial
            and "partial_payment" in allowed_methods
            and Decimal("0") < amount_safe_to_pay < req_amt
            and earliest_date_for_full_payment
            and earliest_date_for_full_payment <= deadline
        ):
            part1 = amount_safe_to_pay
            part2 = req_amt - amount_safe_to_pay
            partial_payments = [
                (req_date, part1),
                (earliest_date_for_full_payment, part2),
            ]
            # Verify safety of partial payment schedule through completion horizon
            part_horizon = (datetime.strptime(earliest_date_for_full_payment, "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days
            deadline_days = (datetime.strptime(deadline, "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days
            part_res = Simulator.simulate(
                state=state,
                recurring_debits=recurring_debits,
                salary_commitment=salary_commitment,
                spending_changes=None,
                plan_payments=partial_payments,
                days=max(part_horizon, min(90, deadline_days)),
            )
            if part_res.is_safe:
                plan_str = f"{req_date}:{cls._fmt_amt(part1)}|{earliest_date_for_full_payment}:{cls._fmt_amt(part2)}"
                plan = CandidatePlan(
                    method="partial_payment",
                    affordability_status="affordable_with_plan",
                    plan_str=plan_str,
                    payments=partial_payments,
                    start_date=req_date,
                    completion_date=earliest_date_for_full_payment,
                    total_amount_paid=req_amt,
                    num_payments=2,
                    payment_option_id="",
                    spending_changes=[],
                    is_safe=True,
                    completes_by_deadline=True,
                    min_headroom=part_res.min_headroom,
                )
                candidate_plans.append(plan)

        # 4. Candidate: Installments (Zero Spending Changes)
        # 4. Candidate: Options from request_payment_options.csv
        eligible_options = []
        for opt in payment_options:
            opt_method = opt["payment_method"]
            if opt_method not in allowed_methods:
                continue
            if opt_method == "installments":
                if state.max_installment_months is None or opt["number_of_payments"] > state.max_installment_months:
                    continue
            eligible_options.append(opt)
            opt_payments, opt_total, opt_start, opt_end = SpendingOptimizer._build_installment_schedule(opt)
            inst_horizon = (datetime.strptime(opt_end, "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days
            deadline_days = (datetime.strptime(deadline, "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days
            opt_res = Simulator.simulate(
                state=state,
                recurring_debits=recurring_debits,
                salary_commitment=salary_commitment,
                spending_changes=None,
                plan_payments=opt_payments,
                days=max(inst_horizon, min(90, deadline_days)),
            )
            if opt_res.is_safe:
                completes_by_deadline = (opt_end <= deadline)
                plan_str = "|".join(f"{d}:{cls._fmt_amt(a)}" for d, a in opt_payments)
                aff_status = "affordable_now" if (opt_method == "full_payment" and opt_start == req_date) else "affordable_with_plan"
                plan = CandidatePlan(
                    method=opt_method,
                    affordability_status=aff_status,
                    plan_str=plan_str,
                    payments=opt_payments,
                    start_date=opt_start,
                    completion_date=opt_end,
                    total_amount_paid=opt_total,
                    num_payments=len(opt_payments),
                    payment_option_id=opt["payment_option_id"],
                    spending_changes=[],
                    is_safe=True,
                    completes_by_deadline=completes_by_deadline,
                    min_headroom=opt_res.min_headroom,
                )
                candidate_plans.append(plan)

        # 5. Candidate: Wait
        if (
            "full_payment" in allowed_methods
            and earliest_date_for_full_payment
            and earliest_date_for_full_payment > req_date
        ):
            completes_by_deadline = (earliest_date_for_full_payment <= deadline)
            plan = CandidatePlan(
                method="wait",
                affordability_status="affordable_later",
                plan_str=f"{earliest_date_for_full_payment}:{cls._fmt_amt(req_amt)}",
                payments=[(earliest_date_for_full_payment, req_amt)],
                start_date=earliest_date_for_full_payment,
                completion_date=earliest_date_for_full_payment,
                total_amount_paid=req_amt,
                num_payments=1,
                payment_option_id="",
                spending_changes=[],
                is_safe=True,
                completes_by_deadline=completes_by_deadline,
            )
            candidate_plans.append(plan)

        # 6. Check if we need spending changes:
        # If no zero-change candidate plan completes by desired_completion_date, explore spending changes
        on_time_zero_change = [p for p in candidate_plans if p.completes_by_deadline]
        if not on_time_zero_change:
            spending_plans = SpendingOptimizer.optimize(
                state=state,
                recurring_debits=recurring_debits,
                salary_commitment=salary_commitment,
                requested_amount=req_amt,
                desired_completion_date=deadline,
                eligible_payment_methods=allowed_methods,
                eligible_options=eligible_options,
                candidate_plan_class=CandidatePlan,
            )
            candidate_plans.extend(spending_plans)

        # 7. Select winning plan via PlanRanker
        if candidate_plans:
            ranked = PlanRanker.rank_plans(candidate_plans)
            winning_plan = ranked[0]
            # If the winning plan does not complete by deadline and wait is possible later, verify status
            return winning_plan, amount_safe_to_pay, earliest_date_for_full_payment, candidate_plans

        # 8. Fallback: Not Recommended
        fallback = CandidatePlan(
            method="not_recommended",
            affordability_status="not_affordable",
            plan_str="none",
            payments=[],
            start_date="",
            completion_date="",
            total_amount_paid=Decimal("0"),
            num_payments=0,
            payment_option_id="",
            spending_changes=[],
            is_safe=True,
            completes_by_deadline=False,
        )
        return fallback, amount_safe_to_pay, earliest_date_for_full_payment, candidate_plans

    @staticmethod
    def _fmt_amt(d: Decimal) -> str:
        if d == d.to_integral():
            return str(int(d))
        return f"{d:.2f}"
