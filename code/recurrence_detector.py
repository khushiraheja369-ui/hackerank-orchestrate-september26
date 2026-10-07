"""
Recurrence Detection Layer for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md, AGENTS.md §6.1-§6.3
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from collections import defaultdict, Counter
from financial_state import FinancialState

class RecurringDebitSpec:
    def __init__(
        self,
        category: str,
        cadence: str, # 'monthly' or 'periodic'
        amount: Decimal,
        is_fixed: bool,
        flexibility: str, # 'fixed', 'reducible', 'stoppable', 'reducible_or_stoppable'
        latest_event_id: str,
        minimum_allowed_amount: Optional[Decimal],
        description: str,
        day_of_month: Optional[int] = None,
        period_days: Optional[int] = None,
        latest_date: Optional[datetime] = None,
    ):
        self.category = category
        self.cadence = cadence
        self.amount = amount
        self.is_fixed = is_fixed
        self.flexibility = flexibility
        self.latest_event_id = latest_event_id
        self.minimum_allowed_amount = minimum_allowed_amount
        self.description = description
        self.day_of_month = day_of_month
        self.period_days = period_days
        self.latest_date = latest_date

class SalaryCommitment:
    def __init__(
        self,
        amount: Decimal,
        day_of_month: int,
        effective_date: Optional[str] = None,
    ):
        self.amount = amount
        self.day_of_month = day_of_month
        self.effective_date = effective_date

class RecurrenceDetector:
    """
    Data-driven recurrence detector that distinguishes:
    1. Explicit recurring events
    2. Recurring historical patterns (monthly calendar anchors, periodic day cadences)
    3. One-time / unusual / irregular events (excluded from future projections)
    """

    @staticmethod
    def detect(state: FinancialState) -> Tuple_Commitments: # type: ignore
        pass

# Implementing detection
class RecurrenceEngine:
    @staticmethod
    def detect_commitments(state: FinancialState) -> Dict[str, Any]:
        req_date = state.request_date
        debits = [
            e for e in state.settled_historical
            if e.get("direction") == "debit" and (e.get("settlement_date") or e.get("event_date")) <= req_date
        ]
        
        by_cat = defaultdict(list)
        for e in debits:
            by_cat[e["category"]].append(e)
            
        recurring_debits: List[RecurringDebitSpec] = []
        
        for cat, evs in by_cat.items():
            if len(evs) < 3:
                # Insufficient history to distinguish from one-time events
                continue
                
            evs.sort(key=lambda x: (x.get("settlement_date") or x.get("event_date")))
            dates = [
                datetime.strptime(x.get("settlement_date") or x.get("event_date"), "%Y-%m-%d")
                for x in evs
            ]
            diffs = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
            if not diffs:
                continue
                
            # 1. Monthly cadence check: intervals in [27, 32] days
            monthly_diffs = [d for d in diffs if 27 <= d <= 32]
            if len(monthly_diffs) >= len(diffs) * 0.7:
                latest_ev = evs[-1]
                amts = [Decimal(str(x["amount"])) for x in evs if x.get("amount") is not None]
                is_fixed = len(set(amts)) == 1 or latest_ev.get("flexibility") == "fixed"
                amt = Decimal(str(latest_ev["amount"])) if is_fixed else max(amts)
                
                # Apply rent increase from verified message facts if applicable
                if cat in ("rent", "housing") and state.message_facts.rent_increase_pct is not None:
                    amt = amt * (Decimal("1") + state.message_facts.rent_increase_pct / Decimal("100"))
                    
                min_allowed = latest_ev.get("minimum_allowed_amount")
                min_allowed_dec = Decimal(str(min_allowed)) if min_allowed is not None else None
                
                recurring_debits.append(RecurringDebitSpec(
                    category=cat,
                    cadence="monthly",
                    day_of_month=dates[-1].day,
                    amount=amt,
                    is_fixed=is_fixed,
                    flexibility=latest_ev.get("flexibility", "fixed"),
                    latest_event_id=latest_ev["event_id"],
                    minimum_allowed_amount=min_allowed_dec,
                    description=latest_ev.get("description", ""),
                    latest_date=dates[-1]
                ))
                continue
                
            # 2. Periodic day cadence check: median delta in {7, 10, 14, 21} with tight clustering
            median_diff = sorted(diffs)[len(diffs)//2]
            close_diffs = [d for d in diffs if abs(d - median_diff) <= 2]
            if len(close_diffs) >= len(diffs) * 0.7 and median_diff in (7, 10, 14, 21):
                latest_ev = evs[-1]
                amts = [Decimal(str(x["amount"])) for x in evs if x.get("amount") is not None]
                is_fixed = (len(set(amts)) == 1) or (latest_ev.get("flexibility") == "fixed")
                sorted_amts = sorted(amts)
                med_amt = sorted_amts[len(sorted_amts) // 2]
                # Exclude unusual one-off spikes (> 2.5x median) from regular cadence
                regular_amts = [a for a in amts if a <= med_amt * Decimal("2.5")]
                if len(set(amts)) == 1:
                    amt = Decimal(str(latest_ev["amount"]))
                else:
                    # Use empirically supported median of regular series for periodic recurring expenses
                    reg_sorted = sorted(regular_amts) if regular_amts else sorted_amts
                    amt = reg_sorted[len(reg_sorted) // 2]
                
                min_allowed = latest_ev.get("minimum_allowed_amount")
                min_allowed_dec = Decimal(str(min_allowed)) if min_allowed is not None else None
                
                recurring_debits.append(RecurringDebitSpec(
                    category=cat,
                    cadence="periodic",
                    period_days=median_diff,
                    amount=amt,
                    is_fixed=is_fixed,
                    flexibility=latest_ev.get("flexibility", "fixed"),
                    latest_event_id=latest_ev["event_id"],
                    minimum_allowed_amount=min_allowed_dec,
                    description=latest_ev.get("description", ""),
                    latest_date=dates[-1]
                ))
                continue
                
            # Otherwise: category is irregular / one-off (e.g. shopping, unusual purchase)
            # Not classified as recurring.
            
        # 3. Salary detection
        salary_commitment: Optional[SalaryCommitment] = None
        if not state.message_facts.salary_ended:
            salary_evs = [
                e for e in state.settled_historical
                if e.get("category") == "salary" and e.get("direction") == "credit"
            ]
            if salary_evs:
                sal_days = [int((x.get("settlement_date") or x.get("event_date")).split("-")[2]) for x in salary_evs]
                sal_day = Counter(sal_days).most_common(1)[0][0]
                evs_on_sal_day = [e for e in salary_evs if int((e.get("settlement_date") or e.get("event_date")).split("-")[2]) == sal_day]
                latest_sal = evs_on_sal_day[-1] if evs_on_sal_day else salary_evs[-1]
                sal_amt = Decimal(str(latest_sal["amount"]))
                
                # If there is a confirmed scheduled salary credit, that is the active upcoming regular salary
                for cc in state.confirmed_scheduled_credits:
                    if cc.get("category") == "salary":
                        c_date = cc.get("settlement_date") or cc.get("event_date")
                        if c_date > (latest_sal.get("settlement_date") or latest_sal.get("event_date")):
                            sal_amt = Decimal(str(cc["amount"]))
                            sal_day = int(c_date.split("-")[2])
                            break
                
                if state.message_facts.salary_amount is not None:
                    sal_amt = state.message_facts.salary_amount
                if state.message_facts.salary_day_of_month is not None:
                    sal_day = state.message_facts.salary_day_of_month
                    
                salary_commitment = SalaryCommitment(
                    amount=sal_amt,
                    day_of_month=sal_day,
                    effective_date=state.message_facts.salary_effective_date
                )
            elif state.message_facts.salary_amount is not None:
                sal_day = state.message_facts.salary_day_of_month or 15
                salary_commitment = SalaryCommitment(
                    amount=state.message_facts.salary_amount,
                    day_of_month=sal_day,
                    effective_date=state.message_facts.salary_effective_date
                )
            elif state.confirmed_scheduled_credits:
                # Use scheduled salary credit if present
                for cc in state.confirmed_scheduled_credits:
                    if cc.get("category") == "salary":
                        c_date = cc.get("settlement_date") or cc.get("event_date")
                        sal_day = int(c_date.split("-")[2])
                        sal_amt = Decimal(str(cc["amount"]))
                        salary_commitment = SalaryCommitment(amount=sal_amt, day_of_month=sal_day)
                        break
                        
        return {
            "recurring_debits": recurring_debits,
            "salary_commitment": salary_commitment,
        }
