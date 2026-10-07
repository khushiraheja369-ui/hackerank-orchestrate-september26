import sys
from pathlib import Path
from decimal import Decimal

# Add code dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_loader import DataLoader
from financial_state import FinancialState
from recurrence_detector import RecurrenceEngine
from simulator import Simulator

def test_simulator_and_affordability():
    loader = DataLoader()
    samples = loader.sample_requests
    print(f"Testing Simulator across {len(samples)} sample requests...")
    
    for s in samples:
        uid = s["user_id"]
        req_id = s["request_id"]
        req_date = s["request_date"]
        req_amt = s["requested_amount"]
        
        state = FinancialState.reconstruct(uid, req_date, loader)
        commitments = RecurrenceEngine.detect_commitments(state)
        r_debits = commitments["recurring_debits"]
        sal = commitments["salary_commitment"]
        
        safe_amt = Simulator.calculate_amount_safe_to_pay(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            requested_amount=req_amt,
        )
        
        earliest_date = Simulator.calculate_earliest_date_for_full_payment(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            requested_amount=req_amt,
            amount_safe_to_pay=safe_amt,
        )
        
        assert Decimal("0") <= safe_amt <= req_amt
        if safe_amt == req_amt:
            assert earliest_date == req_date
            
        print(f"[{req_id}] safe_amt: {safe_amt} (expected: {s['expected_amount_safe_to_pay']}) | earliest: '{earliest_date}' (expected: '{s['expected_earliest_date_for_full_payment']}')")

    print("\nSimulator unit test passed successfully!")

if __name__ == "__main__":
    test_simulator_and_affordability()
