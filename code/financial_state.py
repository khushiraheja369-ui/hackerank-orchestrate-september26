"""
Financial State Reconstruction Layer for Buy or Wait?
Authoritative Reference: problem_statement.md, AGENTS.md §6.1-§6.3
"""

from decimal import Decimal
from typing import Dict, List, Set, Optional, Any
from event_resolver import EventResolver, MessageFacts

class FinancialState:
    """
    Encapsulates a user's fully reconstructed financial position on request_date.
    """
    def __init__(
        self,
        user_id: str,
        request_date: str,
        home_currency: str,
        current_available_balance: Decimal,
        minimum_balance_to_keep: Decimal,
        expense_categories_to_protect: Set[str],
        expense_categories_user_is_willing_to_reduce: Set[str],
        expense_categories_user_is_willing_to_stop: Set[str],
        payment_methods_user_will_consider: Set[str],
        max_installment_months: Optional[int],
        financial_priorities: List[str],
        message_facts: MessageFacts,
        settled_historical: List[Dict[str, Any]],
        pending_scheduled_debits: List[Dict[str, Any]],
        confirmed_scheduled_credits: List[Dict[str, Any]],
    ):
        self.user_id = user_id
        self.request_date = request_date
        self.home_currency = home_currency
        self.current_available_balance = current_available_balance
        self.minimum_balance_to_keep = minimum_balance_to_keep
        self.expense_categories_to_protect = expense_categories_to_protect
        self.expense_categories_user_is_willing_to_reduce = expense_categories_user_is_willing_to_reduce
        self.expense_categories_user_is_willing_to_stop = expense_categories_user_is_willing_to_stop
        self.payment_methods_user_will_consider = payment_methods_user_will_consider
        self.max_installment_months = max_installment_months
        self.financial_priorities = financial_priorities
        self.message_facts = message_facts
        self.settled_historical = settled_historical
        self.pending_scheduled_debits = pending_scheduled_debits
        self.confirmed_scheduled_credits = confirmed_scheduled_credits

    @classmethod
    def reconstruct(
        cls,
        user_id: str,
        request_date: str,
        loader: Any
    ) -> "FinancialState":
        """
        Reconstructs the full financial state using data loader and event resolver.
        """
        prof = loader.profiles[user_id]
        messages = loader.messages_by_user.get(user_id, [])
        events = loader.events_by_user.get(user_id, [])
        
        facts = EventResolver.extract_message_facts(user_id, messages)
        hist, pends, creds = EventResolver.resolve_financial_events(user_id, events, facts, request_date)
        
        return cls(
            user_id=user_id,
            request_date=request_date,
            home_currency=prof["home_currency"],
            current_available_balance=prof["current_available_balance"],
            minimum_balance_to_keep=prof["minimum_balance_to_keep"],
            expense_categories_to_protect=prof["expense_categories_to_protect"],
            expense_categories_user_is_willing_to_reduce=prof["expense_categories_user_is_willing_to_reduce"],
            expense_categories_user_is_willing_to_stop=prof["expense_categories_user_is_willing_to_stop"],
            payment_methods_user_will_consider=prof["payment_methods_user_will_consider"],
            max_installment_months=prof["max_installment_months"],
            financial_priorities=prof["financial_priorities"],
            message_facts=facts,
            settled_historical=hist,
            pending_scheduled_debits=pends,
            confirmed_scheduled_credits=creds,
        )
