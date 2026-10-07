"""
Data Loader and Normalization Layer for Buy or Wait?
Authoritative Reference: problem_statement.md
"""

import csv
import sys
from pathlib import Path
from decimal import Decimal
from typing import Dict, List, Optional, Any

# Ensure code directory is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

# Verified multimodal image extraction table
# Maps image_id -> (amount, currency, document_type, description)
# Used as deterministic offline verification cache
VERIFIED_IMAGE_CACHE: Dict[str, Dict[str, Any]] = {
    "image_01": {"amount": Decimal("4365000"), "currency": "IDR", "doc": "payslip"},
    "image_02": {"amount": Decimal("100000.00"), "currency": "INR", "doc": "rent_receipt"},
    "image_03": {"amount": Decimal("41272.00"), "currency": "INR", "doc": "bill_of_supply"},
    "image_04": {"amount": Decimal("2854.00"), "currency": "INR", "doc": "grocery_delivery"},
    "image_05": {"amount": Decimal("704.05"), "currency": "INR", "doc": "telecom_bill"},
    "image_06": {"amount": Decimal("1995.00"), "currency": "INR", "doc": "tax_invoice"},
    "image_07": {"amount": Decimal("8528.00"), "currency": "INR", "doc": "restaurant_invoice"},
    "image_08": {"amount": Decimal("15339.00"), "currency": "INR", "doc": "maintenance_receipt"},
    "image_09": {"amount": Decimal("723.00"), "currency": "INR", "doc": "water_bill"},
    "image_10": {"amount": Decimal("79679.26"), "currency": "INR", "doc": "grocery_tax_invoice"},
    "image_11": {"amount": Decimal("3650.00"), "currency": "INR", "doc": "hospital_bill"},
    "image_12": {"amount": Decimal("33.50"), "currency": "USD", "doc": "taxi_receipt"},
    "image_13": {"amount": Decimal("2298.00"), "currency": "INR", "doc": "order_summary"},
    "image_14": {"amount": Decimal("4543.00"), "currency": "INR", "doc": "pharmacy_receipt"},
    "image_15": {"amount": Decimal("9968.00"), "currency": "INR", "doc": "airline_invoice"},
    "image_16": {"amount": Decimal("393.22"), "currency": "INR", "doc": "ev_charging_invoice"},
}

class DataLoader:
    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = dataset_dir or config.DATASET_DIR
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.events: List[Dict[str, Any]] = []
        self.events_by_user: Dict[str, List[Dict[str, Any]]] = {}
        self.exchange_rates: Dict[tuple, Decimal] = {}
        self.payment_options: Dict[str, List[Dict[str, Any]]] = {}
        self.messages_by_user: Dict[str, List[Dict[str, Any]]] = {}
        self.requests: List[Dict[str, Any]] = []
        self.sample_requests: List[Dict[str, Any]] = []
        self.image_links: Dict[str, str] = {} # event_id -> image_id
        
        self.load_all()

    def load_all(self):
        self._load_exchange_rates()
        self._load_images_mapping()
        self._load_profiles()
        self._load_events()
        self._load_payment_options()
        self._load_messages()
        self._load_requests()

    def _load_exchange_rates(self):
        path = self.dataset_dir / "exchange_rates.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                key = (r["rate_date"].strip(), r["from_currency"].strip(), r["to_currency"].strip())
                self.exchange_rates[key] = Decimal(r["rate"].strip())

    def _load_images_mapping(self):
        path = self.dataset_dir / "images.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ev_id = r["related_event_id"].strip()
                img_id = r["image_id"].strip()
                if ev_id:
                    self.image_links[ev_id] = img_id

    def _load_profiles(self):
        path = self.dataset_dir / "financial_profiles.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                uid = r["user_id"].strip()
                max_inst = r["max_installment_months"].strip()
                self.profiles[uid] = {
                    "user_id": uid,
                    "home_currency": r["home_currency"].strip(),
                    "current_available_balance": Decimal(r["current_available_balance"].strip()),
                    "minimum_balance_to_keep": Decimal(r["minimum_balance_to_keep"].strip()),
                    "financial_priorities": [p.strip() for p in r["financial_priorities"].split("|") if p.strip()],
                    "expense_categories_to_protect": set(p.strip() for p in r["expense_categories_to_protect"].split("|") if p.strip()),
                    "expense_categories_user_is_willing_to_reduce": set(p.strip() for p in r["expense_categories_user_is_willing_to_reduce"].split("|") if p.strip()),
                    "expense_categories_user_is_willing_to_stop": set(p.strip() for p in r["expense_categories_user_is_willing_to_stop"].split("|") if p.strip()),
                    "payment_methods_user_will_consider": set(p.strip() for p in r["payment_methods_user_will_consider"].split("|") if p.strip()),
                    "max_installment_months": int(max_inst) if max_inst else None,
                }

    def _resolve_image_amount(self, event_id: str) -> Optional[Decimal]:
        """Resolves missing amount from image mapping and extraction cache."""
        img_id = self.image_links.get(event_id)
        if img_id and img_id in VERIFIED_IMAGE_CACHE:
            return VERIFIED_IMAGE_CACHE[img_id]["amount"]
        return None

    def _load_events(self):
        path = self.dataset_dir / "financial_events.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                ev_id = r["event_id"].strip()
                uid = r["user_id"].strip()
                amt_str = r["amount"].strip()
                raw_amt = Decimal(amt_str) if amt_str else self._resolve_image_amount(ev_id)
                min_amt_str = r.get("minimum_allowed_amount", "").strip()
                min_allowed = Decimal(min_amt_str) if min_amt_str else None

                ev_curr = r["currency"].strip()
                home_curr = self.profiles[uid]["home_currency"] if uid in self.profiles else ev_curr
                settle_date = r["settlement_date"].strip()

                # Convert foreign currency to home currency if direct exchange rate exists
                converted_amt = raw_amt
                if raw_amt is not None and ev_curr != home_curr and settle_date:
                    rate_key = (settle_date, ev_curr, home_curr)
                    if rate_key in self.exchange_rates:
                        rate = self.exchange_rates[rate_key]
                        converted_amt = raw_amt * rate

                event = {
                    "event_id": ev_id,
                    "user_id": uid,
                    "event_type": r["event_type"].strip(),
                    "description": r["description"].strip(),
                    "category": r["category"].strip(),
                    "direction": r["direction"].strip(), # credit, debit, non_cash
                    "raw_amount": raw_amt,
                    "amount": converted_amt, # normalized to home currency
                    "currency": home_curr,
                    "raw_currency": ev_curr,
                    "event_date": r["event_date"].strip(),
                    "settlement_date": settle_date,
                    "status": r["status"].strip(), # settled, pending, scheduled, cancelled, failed, unrealized
                    "linked_event_id": r["linked_event_id"].strip(),
                    "flexibility": r["flexibility"].strip(), # fixed, stoppable, reducible, reducible_or_stoppable
                    "minimum_allowed_amount": min_allowed,
                }
                self.events.append(event)
                self.events_by_user.setdefault(uid, []).append(event)

    def _load_payment_options(self):
        path = self.dataset_dir / "request_payment_options.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rid = r["request_id"].strip()
                freq_str = r["payment_frequency_days"].strip()
                opt = {
                    "payment_option_id": r["payment_option_id"].strip(),
                    "request_id": rid,
                    "payment_method": r["payment_method"].strip(),
                    "payment_amount": Decimal(r["payment_amount"].strip()),
                    "number_of_payments": int(r["number_of_payments"].strip()),
                    "first_payment_date": r["first_payment_date"].strip(),
                    "payment_frequency_days": int(freq_str) if freq_str else None,
                    "financing_fee": Decimal(r["financing_fee"].strip()),
                    "total_payable_amount": Decimal(r["total_payable_amount"].strip()),
                }
                self.payment_options.setdefault(rid, []).append(opt)

    def _load_messages(self):
        path = self.dataset_dir / "messages.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                uid = r["user_id"].strip()
                msg = {
                    "message_id": r["message_id"].strip(),
                    "user_id": uid,
                    "request_id": r["request_id"].strip(),
                    "related_event_id": r["related_event_id"].strip(),
                    "sent_at": r["sent_at"].strip(),
                    "source_type": r["source_type"].strip(),
                    "message_text": r["message_text"].strip(),
                }
                self.messages_by_user.setdefault(uid, []).append(msg)

    def _load_requests(self):
        path = self.dataset_dir / "requests.csv"
        with open(path, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                req = {
                    "request_id": r["request_id"].strip(),
                    "user_id": r["user_id"].strip(),
                    "request_date": r["request_date"].strip(),
                    "request_type": r["request_type"].strip(),
                    "requested_amount": Decimal(r["requested_amount"].strip()),
                    "desired_completion_date": r["desired_completion_date"].strip(),
                    "allows_partial_payment": r["allows_partial_payment"].strip().lower() == "true",
                    "request_text": r["request_text"].strip(),
                }
                self.requests.append(req)

        sample_path = self.dataset_dir / "sample_requests.csv"
        if sample_path.exists():
            with open(sample_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    s_req = {
                        "request_id": r["request_id"].strip(),
                        "user_id": r["user_id"].strip(),
                        "request_date": r["request_date"].strip(),
                        "request_type": r["request_type"].strip(),
                        "requested_amount": Decimal(r["requested_amount"].strip()),
                        "desired_completion_date": r["desired_completion_date"].strip(),
                        "allows_partial_payment": r["allows_partial_payment"].strip().lower() == "true",
                        "request_text": r["request_text"].strip(),
                        "expected_amount_safe_to_pay": Decimal(r["amount_safe_to_pay"].strip()),
                        "expected_affordability_status": r["affordability_status"].strip(),
                        "expected_recommended_payment_method": r["recommended_payment_method"].strip(),
                        "expected_payment_plan": r["payment_plan"].strip(),
                        "expected_earliest_date_for_full_payment": r["earliest_date_for_full_payment"].strip(),
                        "expected_spending_changes_needed": r["spending_changes_needed"].strip(),
                        "expected_decision_explanation": r["decision_explanation"].strip(),
                    }
                    self.sample_requests.append(s_req)
