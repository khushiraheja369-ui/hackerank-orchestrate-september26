"""
Grounded Decision Explanation Generator for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md, AGENTS.md §6.2
"""

from decimal import Decimal
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime

class ExplanationGenerator:
    """
    Generates concise, factual, grounded explanations supporting recommendations.
    Adheres strictly to problem_statement.md explanation requirements and dataset style.
    """

    @staticmethod
    def _fmt_money(amt: Decimal) -> str:
        """Formats Decimal amount with thousands separator and proper decimal places."""
        if amt == amt.to_integral():
            return f"{int(amt):,}"
        else:
            # Round to 2 decimal places
            return f"{amt:,.2f}"

    @staticmethod
    def _fmt_date(d_str: str) -> str:
        """Formats 'YYYY-MM-DD' as '15 June 2024' (day without leading zero)."""
        dt = datetime.strptime(d_str, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%B %Y')}"

    @classmethod
    def generate_explanation(
        cls,
        currency: str,
        requested_amount: Decimal,
        amount_safe_to_pay: Decimal,
        minimum_balance_to_keep: Decimal,
        desired_completion_date: str,
        winning_plan: Any,
        earliest_date_for_full_payment: str,
        event_descriptions: Dict[str, str], # event_id -> description
    ) -> str:
        method = winning_plan.method
        status = winning_plan.affordability_status
        changes = winning_plan.spending_changes
        curr = currency

        fmt_req = cls._fmt_money(requested_amount)
        fmt_min = cls._fmt_money(minimum_balance_to_keep)
        fmt_safe = cls._fmt_money(amount_safe_to_pay)
        fmt_deadline = cls._fmt_date(desired_completion_date)

        # 1. Affordable Now / Full Payment without spending changes
        if status == "affordable_now" or (method == "full_payment" and not changes):
            return f"Pay {curr} {fmt_req} today. This leaves at least {curr} {fmt_min} available over the next 90 days."

        # 2. Full Payment with spending changes
        if method == "full_payment" and changes:
            clause_parts = []
            for chg in changes:
                parts = chg.split(":")
                act_type = parts[0]
                ev_id = parts[1]
                desc = event_descriptions.get(ev_id, "flexible expense").lower()
                # Clean up description prefix if needed
                if act_type == "stop":
                    clause_parts.append(f"Stop the {desc}")
                elif act_type == "reduce_to":
                    new_amt = cls._fmt_money(Decimal(parts[2]))
                    clause_parts.append(f"Reduce the {desc} to {curr} {new_amt}")

            if len(clause_parts) == 1:
                action_text = clause_parts[0]
            elif len(clause_parts) == 2:
                # Capitalize first, lowercase second
                p2 = clause_parts[1]
                p2 = p2[0].lower() + p2[1:]
                action_text = f"{clause_parts[0]} and {p2}"
            else:
                p_last = clause_parts[-1]
                p_last = p_last[0].lower() + p_last[1:]
                action_text = f"{', '.join(clause_parts[:-1])}, and {p_last}"

            return f"{action_text}, then pay {curr} {fmt_req} today. This leaves at least {curr} {fmt_min} available."

        # 3. Installments
        if method == "installments":
            payments = winning_plan.payments
            n = len(payments)
            inst_amt = cls._fmt_money(payments[0][1])
            start_date_fmt = cls._fmt_date(payments[0][0])

            if changes:
                clause_parts = []
                for chg in changes:
                    parts = chg.split(":")
                    ev_id = parts[1]
                    desc = event_descriptions.get(ev_id, "flexible expense").lower()
                    if parts[0] == "stop":
                        clause_parts.append(f"Stop the {desc}")
                    elif parts[0] == "reduce_to":
                        clause_parts.append(f"Reduce the {desc} to {curr} {cls._fmt_money(Decimal(parts[2]))}")
                change_prefix = f"{', '.join(clause_parts)}, then use "
                return f"{change_prefix}{n} installments of {curr} {inst_amt}, starting {start_date_fmt}. This leaves at least {curr} {fmt_min} available."
            else:
                return f"Use {n} installments of {curr} {inst_amt}, starting {start_date_fmt}. This leaves at least {curr} {fmt_min} available."

        # 4. Partial Payment
        if method == "partial_payment":
            p1_amt = cls._fmt_money(winning_plan.payments[0][1])
            p2_amt = cls._fmt_money(winning_plan.payments[1][1])
            p2_date_fmt = cls._fmt_date(winning_plan.payments[1][0])
            return f"Pay {curr} {p1_amt} today and the remaining {curr} {p2_amt} on {p2_date_fmt}. This completes the full request and keeps the {curr} {fmt_min} minimum protected."

        # 5. Wait
        if method == "wait":
            earliest_fmt = cls._fmt_date(earliest_date_for_full_payment)
            return f"Pay {curr} {fmt_req} in full on {earliest_fmt}. Paying earlier would take the balance below the {curr} {fmt_min} minimum."

        # 6. Not Recommended
        if method == "not_recommended":
            if amount_safe_to_pay > Decimal("0") and amount_safe_to_pay < requested_amount:
                return f"Do not proceed with the {curr} {fmt_req} request. Although {curr} {fmt_safe} is available today, the full amount cannot be completed safely within 90 days."
            else:
                return f"Do not make this payment by {fmt_deadline}. None of the available options keeps the {curr} {fmt_min} minimum protected."

        return f"Recommendation for {curr} {fmt_req}: {method} under status {status}."
