"""
Independent Verification and Traceability Layer for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md, AGENTS.md §6.2-§6.3
"""

from decimal import Decimal
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime

from financial_state import FinancialState
from recurrence_detector import RecurringDebitSpec, SalaryCommitment
from simulator import Simulator

class ValidationResult:
    def __init__(
        self,
        is_valid: bool,
        errors: List[str],
        trace: Dict[str, Any],
    ):
        self.is_valid = is_valid
        self.errors = errors
        self.trace = trace

class PlanVerifier:
    """
    Independent verification pass that re-simulates the selected plan and validates
    all business constraints, invariants, formatting rules, and safety conditions.
    """

    @classmethod
    def verify_prediction(
        cls,
        state: FinancialState,
        recurring_debits: List[RecurringDebitSpec],
        salary_commitment: Optional[SalaryCommitment],
        request: Dict[str, Any],
        winning_plan: Any,
        amount_safe_to_pay: Decimal,
        earliest_date_for_full_payment: str,
        candidates: List[Any],
    ) -> ValidationResult:
        errors: List[str] = []
        trace: Dict[str, Any] = {
            "user_id": state.user_id,
            "request_id": request["request_id"],
            "request_date": state.request_date,
            "starting_balance": str(state.current_available_balance),
            "minimum_balance": str(state.minimum_balance_to_keep),
            "requested_amount": str(request["requested_amount"]),
            "desired_completion_date": request["desired_completion_date"],
            "amount_safe_to_pay": str(amount_safe_to_pay),
            "earliest_date_for_full_payment": earliest_date_for_full_payment,
            "candidate_count": len(candidates),
            "winning_method": winning_plan.method,
            "winning_status": winning_plan.affordability_status,
            "winning_plan": winning_plan.plan_str,
            "winning_changes": winning_plan.spending_changes_str,
        }

        req_amt = request["requested_amount"]
        req_date = state.request_date
        deadline = request["desired_completion_date"]
        allows_partial = request.get("allows_partial_payment", False)
        allowed_methods = state.payment_methods_user_will_consider

        # 1. Check bounds: 0 <= amount_safe_to_pay <= requested_amount
        if not (Decimal("0") <= amount_safe_to_pay <= req_amt):
            errors.append(f"amount_safe_to_pay {amount_safe_to_pay} out of bounds [0, {req_amt}]")

        # 2. Check affordability_status allowed values
        valid_statuses = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
        if winning_plan.affordability_status not in valid_statuses:
            errors.append(f"Invalid affordability_status: {winning_plan.affordability_status}")

        # 3. Check recommended_payment_method allowed values
        valid_methods = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
        if winning_plan.method not in valid_methods:
            errors.append(f"Invalid recommended_payment_method: {winning_plan.method}")

        # 4. Check user payment method eligibility
        if winning_plan.method in ("full_payment", "partial_payment", "installments"):
            if winning_plan.method not in allowed_methods:
                errors.append(f"Method {winning_plan.method} not in user allowed methods: {allowed_methods}")
        elif winning_plan.method == "wait":
            if "full_payment" not in allowed_methods:
                errors.append("wait requires user to consider full_payment")

        # 5. Check affordable_now relationship
        if winning_plan.affordability_status == "affordable_now":
            if winning_plan.method != "full_payment":
                errors.append(f"affordable_now must use full_payment, got {winning_plan.method}")
            if earliest_date_for_full_payment != req_date:
                errors.append(f"affordable_now must have earliest_date == request_date ({req_date}), got '{earliest_date_for_full_payment}'")
            if winning_plan.spending_changes_str != "none":
                errors.append(f"affordable_now cannot require spending changes: {winning_plan.spending_changes_str}")

        # 6. Check partial_payment rules
        if winning_plan.method == "partial_payment":
            if winning_plan.affordability_status != "affordable_with_plan":
                errors.append(f"partial_payment must have status affordable_with_plan, got {winning_plan.affordability_status}")
            if not allows_partial:
                errors.append("partial_payment recommended but request does not allow partial payment")
            if not (Decimal("0") < amount_safe_to_pay < req_amt):
                errors.append(f"partial_payment requires 0 < amount_safe_to_pay < requested_amount: {amount_safe_to_pay}")
            if not earliest_date_for_full_payment or earliest_date_for_full_payment > deadline:
                errors.append(f"partial_payment second payment date {earliest_date_for_full_payment} > deadline {deadline}")
            if len(winning_plan.payments) != 2:
                errors.append(f"partial_payment must have exactly 2 payments, got {len(winning_plan.payments)}")
            else:
                p1_date, p1_amt = winning_plan.payments[0]
                p2_date, p2_amt = winning_plan.payments[1]
                if p1_date != req_date:
                    errors.append(f"partial_payment first date {p1_date} != req_date {req_date}")
                if p1_amt != amount_safe_to_pay:
                    errors.append(f"partial_payment first amount {p1_amt} != amount_safe_to_pay {amount_safe_to_pay}")
                if p2_amt != req_amt - amount_safe_to_pay:
                    errors.append(f"partial_payment second amount {p2_amt} != req_amt - safe ({req_amt - amount_safe_to_pay})")
                if p1_amt + p2_amt != req_amt:
                    errors.append(f"partial_payment sum {p1_amt + p2_amt} != req_amt {req_amt}")

        # 7. Check spending changes validity
        if winning_plan.spending_changes:
            if len(winning_plan.spending_changes) > 3:
                errors.append(f"Maximum 3 spending changes allowed, got {len(winning_plan.spending_changes)}")
            seen_events = set()
            for chg in winning_plan.spending_changes:
                parts = chg.split(":")
                act_type = parts[0]
                ev_id = parts[1]
                if ev_id in seen_events:
                    errors.append(f"Event {ev_id} referenced multiple times in spending changes")
                seen_events.add(ev_id)
                # Verify event is in non-protected category
                matching_rds = [r for r in recurring_debits if r.latest_event_id == ev_id]
                if matching_rds:
                    rd = matching_rds[0]
                    if rd.category in state.expense_categories_to_protect:
                        errors.append(f"Intervention targets protected category: {rd.category}")

        # 8. Re-simulate the winning plan independently over its completion horizon
        if winning_plan.method != "not_recommended":
            # Reconstruct spending changes dict
            stop_ids = set()
            reduce_map = {}
            for chg in winning_plan.spending_changes:
                parts = chg.split(":")
                if parts[0] == "stop":
                    stop_ids.add(parts[1])
                elif parts[0] == "reduce_to":
                    reduce_map[parts[1]] = Decimal(parts[2])

            deadline_days = (datetime.strptime(deadline, "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days
            plan_horizon = 0
            if winning_plan.payments:
                plan_horizon = max((datetime.strptime(p[0], "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days for p in winning_plan.payments) + 1
            eval_days = max(plan_horizon, min(90, deadline_days))
            if winning_plan.method == "wait" and earliest_date_for_full_payment:
                e_days = (datetime.strptime(earliest_date_for_full_payment, "%Y-%m-%d") - datetime.strptime(req_date, "%Y-%m-%d")).days + 1
                eval_days = max(e_days, min(90, deadline_days))

            sim_result = Simulator.simulate(
                state=state,
                recurring_debits=recurring_debits,
                salary_commitment=salary_commitment,
                spending_changes={"stop": stop_ids, "reduce_to": reduce_map},
                plan_payments=winning_plan.payments,
                days=eval_days,
            )

            trace["re_sim_min_balance"] = str(sim_result.min_balance)
            trace["re_sim_min_headroom"] = str(sim_result.min_headroom)

            # Small negative tolerance for minor penny rounding differences (0.05 currency units)
            if sim_result.min_headroom < Decimal("-0.05"):
                errors.append(f"Re-simulation failed: min_balance {sim_result.min_balance} < minimum_balance_to_keep {state.minimum_balance_to_keep} (headroom: {sim_result.min_headroom})")

        is_valid = (len(errors) == 0)
        trace["is_valid"] = is_valid
        trace["errors"] = errors
        return ValidationResult(is_valid=is_valid, errors=errors, trace=trace)
