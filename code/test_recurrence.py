import sys
from pathlib import Path

# Add code dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_loader import DataLoader
from financial_state import FinancialState
from recurrence_detector import RecurrenceEngine

def test_recurrence_engine():
    loader = DataLoader()
    print(f"Loaded {len(loader.profiles)} profiles.")
    
    total_debits_detected = 0
    salaries_detected = 0
    
    for req in loader.requests:
        uid = req["user_id"]
        req_date = req["request_date"]
        
        state = FinancialState.reconstruct(uid, req_date, loader)
        assert state.current_available_balance >= 0
        assert state.minimum_balance_to_keep >= 0
        
        commitments = RecurrenceEngine.detect_commitments(state)
        r_debits = commitments["recurring_debits"]
        sal = commitments["salary_commitment"]
        
        total_debits_detected += len(r_debits)
        if sal is not None:
            salaries_detected += 1
            assert sal.amount > 0
            assert 1 <= sal.day_of_month <= 31
            
        for rd in r_debits:
            assert rd.amount > 0
            assert rd.cadence in ("monthly", "periodic")
            if rd.cadence == "monthly":
                assert 1 <= rd.day_of_month <= 31
            elif rd.cadence == "periodic":
                assert rd.period_days in (7, 10, 14, 21)
                
    print(f"Successfully processed all {len(loader.requests)} requests!")
    print(f"Total recurring debits series detected: {total_debits_detected}")
    print(f"Total active salary commitments detected: {salaries_detected}")

if __name__ == "__main__":
    test_recurrence_engine()
