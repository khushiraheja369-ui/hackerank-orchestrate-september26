import sys
from pathlib import Path

# Add code dir to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data_loader import DataLoader
from event_resolver import EventResolver

def test_event_resolver():
    loader = DataLoader()
    print(f"Loaded {len(loader.profiles)} profiles and {len(loader.requests)} requests.")
    
    total_resolved_historical = 0
    total_resolved_pending_debits = 0
    
    for req in loader.requests:
        uid = req["user_id"]
        req_date = req["request_date"]
        user_events = loader.events_by_user.get(uid, [])
        user_messages = loader.messages_by_user.get(uid, [])
        
        # Extract message facts
        facts = EventResolver.extract_message_facts(uid, user_messages)
        
        # Resolve events
        hist, pend_debits, conf_credits = EventResolver.resolve_financial_events(uid, user_events, facts, req_date)
        
        total_resolved_historical += len(hist)
        total_resolved_pending_debits += len(pend_debits)
        
        assert isinstance(hist, list)
        assert isinstance(pend_debits, list)
        assert isinstance(conf_credits, list)
        for ev in pend_debits:
            assert ev["direction"] == "debit"
            assert ev["status"] in ("pending", "scheduled", "settled")
            
    print(f"Successfully resolved all {len(loader.requests)} evaluation requests!")
    print(f"Total resolved historical events: {total_resolved_historical}")
    print(f"Total resolved pending/scheduled debits: {total_resolved_pending_debits}")

if __name__ == "__main__":
    test_event_resolver()
