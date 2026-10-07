import sys
from pathlib import Path
from decimal import Decimal

# Add code dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_loader import DataLoader
from financial_state import FinancialState
from recurrence_detector import RecurrenceEngine
from plan_generator import PlanGenerator

def test_plan_generator():
    loader = DataLoader()
    samples = loader.sample_requests
    print(f"Testing PlanGenerator across {len(samples)} sample requests...")
    
    matches_status = 0
    matches_method = 0
    matches_plan = 0
    matches_changes = 0
    
    for s in samples:
        uid = s["user_id"]
        req_id = s["request_id"]
        req_date = s["request_date"]
        
        state = FinancialState.reconstruct(uid, req_date, loader)
        commitments = RecurrenceEngine.detect_commitments(state)
        r_debits = commitments["recurring_debits"]
        sal = commitments["salary_commitment"]
        
        opts = loader.payment_options.get(req_id, [])
        winning_plan, safe_amt, earliest_date, candidates = PlanGenerator.generate_and_select_plan(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            request=s,
            payment_options=opts,
        )
        
        exp_status = s["expected_affordability_status"]
        exp_method = s["expected_recommended_payment_method"]
        exp_plan = s["expected_payment_plan"]
        exp_changes = s["expected_spending_changes_needed"]
        
        pred_changes = "|".join(winning_plan.spending_changes) if winning_plan.spending_changes else "none"
        
        is_stat_match = (winning_plan.affordability_status == exp_status)
        is_meth_match = (winning_plan.method == exp_method)
        is_plan_match = (winning_plan.plan_str == exp_plan)
        is_chg_match = (pred_changes == exp_changes)
        
        if is_stat_match: matches_status += 1
        if is_meth_match: matches_method += 1
        if is_plan_match: matches_plan += 1
        if is_chg_match: matches_changes += 1
        
        print(f"[{req_id}] method: {winning_plan.method:15} (exp: {exp_method:15}) {'OK' if is_meth_match else 'DIFF'} | status: {winning_plan.affordability_status:20} {'OK' if is_stat_match else 'DIFF'} | changes: {pred_changes}")

    print("\nBenchmark Results Summary on 25 Samples:")
    print(f"Method Matches: {matches_method} / {len(samples)} ({matches_method/len(samples)*100:.1f}%)")
    print(f"Status Matches: {matches_status} / {len(samples)} ({matches_status/len(samples)*100:.1f}%)")
    print(f"Plan Matches:   {matches_plan} / {len(samples)} ({matches_plan/len(samples)*100:.1f}%)")
    print(f"Changes Matches:{matches_changes} / {len(samples)} ({matches_changes/len(samples)*100:.1f}%)")

if __name__ == "__main__":
    test_plan_generator()
