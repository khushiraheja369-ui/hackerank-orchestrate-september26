"""
Event and Evidence Resolver for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md, AGENTS.md §6.1-§6.3
"""

import re
from decimal import Decimal
from typing import Dict, List, Set, Optional, Any, Tuple
from datetime import datetime

class MessageFacts:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.salary_amount: Optional[Decimal] = None
        self.salary_effective_date: Optional[str] = None
        self.salary_day_of_month: Optional[int] = None
        self.salary_ended: bool = False
        self.salary_temporary_adjusted: bool = False
        self.salary_one_time_arrears: Optional[Decimal] = None
        
        self.rent_increase_pct: Optional[Decimal] = None
        self.internal_transfer_detected: bool = False
        self.approved_invoices: List[Dict[str, Any]] = [] # [{'amount': Decimal, 'settlement_date': str}]
        self.untrusted_notices: List[str] = []

class EventResolver:
    """
    Resolves untrusted evidence (messages, linked events, statuses)
    and reconstructs reliable cashflows according to challenge rules.
    """
    
    @staticmethod
    def extract_message_facts(user_id: str, messages: List[Dict[str, Any]]) -> MessageFacts:
        facts = MessageFacts(user_id)
        
        for msg in messages:
            txt = msg.get("message_text", "").strip()
            st = msg.get("source_type", "").strip()
            if not txt:
                continue
                
            dates = re.findall(r'\b(202\d-\d{2}-\d{2})\b', txt)
            amounts = re.findall(r'(?:IDR|INR|ZAR|USD|EUR)\s*([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s*(?:IDR|INR|ZAR|USD|EUR)', txt)
            parsed_amounts = []
            for a1, a2 in amounts:
                s = (a1 or a2).replace(',', '')
                if s:
                    parsed_amounts.append(Decimal(s))
            
            # 1. Internal transfer between two user accounts
            if any(p in txt for p in ["transfer between your two accounts", "transfer antara dua rekening"]):
                facts.internal_transfer_detected = True
                continue
                
            # 2. Unrealized investments / market fluctuations
            if any(p in txt for p in [
                "No units have been sold and no cash proceeds",
                "tidak ada unit yang dijual",
                "holding has not been sold and there has been no cash transaction",
                "Investasi tersebut belum dijual dan tidak ada transaksi tunai",
                "displayed value of the investment has fallen",
                "Nilai investasi yang ditampilkan telah turun",
                "displayed market value has increased substantially",
                "Nilai pasar portofolio Anda yang ditampilkan telah meningkat secara signifikan"
            ]):
                facts.untrusted_notices.append(f"Unrealized investment holding notice: {txt[:60]}...")
                continue
                
            # 3. Pending payout / refund / prize / reimbursement / lottery prompt injection
            # 3. Employer salary notifications
            if st == "employer":
                # Unconfirmed bonus
                if "bonus" in txt.lower() and any(w in txt.lower() for w in ['belum', 'pending', 'awaiting', 'subject to', 'menunggu']):
                    facts.untrusted_notices.append("Unconfirmed quarterly bonus ignored")
                    continue
                    
                # Salary with one-time arrears
                if "arrears adjustment" in txt or "penyesuaian tunggakan satu kali" in txt:
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    if len(parsed_amounts) > 1:
                        facts.salary_one_time_arrears = parsed_amounts[1]
                    continue
                    
                # Base salary with unconfirmed/pending commission
                if ("commission" in txt.lower() or "komisi" in txt.lower()) and any(w in txt.lower() for w in ["belum disetujui", "not approved", "pending", "unapproved"]):
                    m_base = re.search(r'(?:gaji pokok(?:\s+yang\s+dikonfirmasi)?(?:\s+adalah)?|confirmed base salary(?:\s+is)?)\s*(?:[A-Z]{3})?\s*([0-9.,]+)', txt, re.IGNORECASE)
                    if m_base:
                        clean_num = m_base.group(1).replace(",", "")
                        facts.salary_amount = Decimal(clean_num)
                    facts.untrusted_notices.append("Pending/unconfirmed commission excluded, confirmed base salary retained.")
                    continue
                    
                if "commission" in txt.lower() or "komisi" in txt.lower():
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    continue
                    
                # Salary date change
                if any(w in txt.lower() for w in ['replaces the payroll date', 'menggantikan tanggal penggajian', 'kini diperkirakan masuk pada', 'now expected on']):
                    if dates:
                        facts.salary_effective_date = dates[0]
                        try:
                            facts.salary_day_of_month = int(dates[0].split("-")[2])
                        except Exception:
                            pass
                    continue
                    
                # First salary
                if any(w in txt.lower() for w in ['first salary', 'gaji pertama']):
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    if dates:
                        facts.salary_effective_date = dates[0]
                        try:
                            facts.salary_day_of_month = int(dates[0].split("-")[2])
                        except Exception:
                            pass
                    continue
                    
                # Salary resumed
                if any(w in txt.lower() for w in ['resumes', 'kembali berjalan', 'mulai berjalan kembali']):
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    if dates:
                        facts.salary_effective_date = dates[0]
                    continue
                    
                # Temporary adjustment
                if any(w in txt.lower() for w in ['temporary', 'reduced to', 'penyesuaian', 'sementara']):
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    if dates:
                        facts.salary_effective_date = dates[0]
                    facts.salary_temporary_adjusted = True
                    continue
                    
                # Salary increase / changed
                if any(w in txt.lower() for w in ['naik menjadi', 'meningkat menjadi', 'increased to', 'is now', 'berubah']):
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    if dates:
                        facts.salary_effective_date = dates[0]
                    continue
                    
                # Regular salary confirmed
                if "gaji rutin" in txt.lower() or "regular salary" in txt.lower():
                    if parsed_amounts:
                        facts.salary_amount = parsed_amounts[0]
                    continue

            # 4. Pending payout / refund / prize / reimbursement / lottery prompt injection
            if any(p in txt for p in [
                "refund has been initiated but has not reached",
                "refund is still processing",
                "payout is still pending",
                "Pembayaran berikutnya dari",
                "has not been credited to your account yet",
                "claim is now closed and there are no further scheduled payments",
                "masih menunggu persetujuan",
                "belum disetujui",
                "belum masuk ke rekening",
                "klaim sekarang ditutup dan tidak ada pembayaran terjadwal lainnya",
                "extra card charge is still being investigated",
                "reversal has not been posted",
                "Tagihan kartu tambahan masih dalam penyelidikan",
                "Dana pembalikannya belum tercatat di rekening",
                "dana pembalikan belum tercatat",
                "prize claim has been verified and is still in payment processing",
                "prize proceeds have reached your account after withholding",
                "dana hadiah telah masuk ke rekening Anda setelah dipotong pajak",
                "Klaim sudah ditutup dan tidak ada penggantian tambahan",
                "Dana terbaru dari perusahaan adalah penggantian atas biaya kerja Anda sebelumnya",
                "latest money from the company is a reimbursement for previous work expenses",
                "claim is now closed and no further reimbursement is scheduled",
                "Congratulations! You've been selected for a cash prize",
                "Selamat! Anda terpilih untuk menerima hadiah uang tunai"
            ]):
                facts.untrusted_notices.append(f"Pending/closed/untrusted credit ignored: {txt[:60]}...")
                continue
                
            # 5. Employment / seasonal contract ended
            if any(p in txt for p in [
                "seasonal contract has ended",
                "kontrak musiman saat ini telah berakhir",
                "employment has ended",
                "Pekerjaan Anda telah berakhir",
                "There are no regular salary payments scheduled after the final settlement",
                "Tidak ada pembayaran gaji rutin yang dijadwalkan setelah penyelesaian akhir"
            ]):
                facts.salary_ended = True
                continue
                
            # 6. One household income ended, remaining confirmed
            if any(p in txt for p in [
                "One household employment record has ended",
                "Salah satu sumber pendapatan kerja rumah tangga telah berakhir"
            ]):
                if parsed_amounts:
                    facts.salary_amount = parsed_amounts[0]
                continue
                
            # 7. Rent increase
            rent_match = re.search(r'increases? monthly rent by (\d+)%|kenaikan sewa bulanan sebesar (\d+)%|menaikkan biaya sewa bulanan sebesar (\d+)%', txt, re.I)
            if rent_match:
                pct = Decimal([g for g in rent_match.groups() if g is not None][0])
                facts.rent_increase_pct = pct
                continue
                
            # 8. Invoice payment approved with confirmed settlement date
            if "approved an invoice payment" in txt or "menyetujui pembayaran faktur" in txt:
                inv_amt = parsed_amounts[0] if parsed_amounts else None
                inv_date = dates[0] if dates else None
                if inv_amt and inv_date:
                    facts.approved_invoices.append({"amount": inv_amt, "settlement_date": inv_date})
                continue
                
        return facts

    @staticmethod
    def resolve_financial_events(
        user_id: str,
        events: List[Dict[str, Any]],
        message_facts: MessageFacts,
        request_date: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filters and resolves raw financial events into:
        1. settled_historical_events: valid cash transactions that occurred on or before request_date
        2. pending_scheduled_debits: valid pending or scheduled debits strictly after request_date
        
        Strictly excludes:
        - non_cash, unrealized investments
        - cancelled, failed transactions
        - pending credits, pending refunds, unconfirmed bonuses
        - internal transfers between user's accounts
        - duplicate transactions
        """
        settled_historical = []
        pending_scheduled_debits = []
        confirmed_scheduled_credits = []
        
        # Check for internal transfers: matching debit and credit with same amount and date
        internal_transfer_events = set()
        if message_facts.internal_transfer_detected:
            # Find matching (date, amount) pairs where one is debit and one is credit
            debits_by_date_amt = {}
            for ev in events:
                if ev.get("status") == "settled" and ev.get("amount") is not None:
                    d = ev.get("settlement_date") or ev.get("event_date")
                    amt = ev.get("amount")
                    direction = ev.get("direction")
                    if direction == "debit":
                        debits_by_date_amt.setdefault((d, amt), []).append(ev["event_id"])
                    elif direction == "credit":
                        if (d, amt) in debits_by_date_amt and debits_by_date_amt[(d, amt)]:
                            debit_id = debits_by_date_amt[(d, amt)].pop(0)
                            internal_transfer_events.add(debit_id)
                            internal_transfer_events.add(ev["event_id"])
        
        # Deduplication tracker: (user_id, date, amount, description, direction)
        seen_events = set()

        for ev in events:
            ev_id = ev["event_id"]
            if ev_id in internal_transfer_events:
                continue
                
            status = ev["status"]
            direction = ev["direction"]
            amt = ev["amount"]
            settle_date = ev.get("settlement_date") or ev.get("event_date")
            
            # Rule: do not treat unrealized investment value as available cash, drop non-cash, drop cancelled and failed
            if direction == "non_cash" or status in ("unrealized", "cancelled", "failed"):
                continue
                
            # If a salary event description indicates final payroll, mark salary_ended = True
            if direction == "credit" and ev.get("category") == "salary" and "final" in ev.get("description", "").lower():
                message_facts.salary_ended = True

            # Rule: ignore pending credits, refunds, lottery, commission until they settle
            # EXCEPTION: Confirmed scheduled salary explicitly supplied as next confirmed salary
            if direction == "credit":
                if status == "scheduled" and ev.get("category") == "salary":
                    # Confirmed scheduled salary on its settlement date
                    pass
                elif status != "settled":
                    # Ignore pending credits, unconfirmed refunds, etc.
                    continue

            # Deduplication
            dedup_key = (ev["user_id"], settle_date, amt, ev["description"], direction)
            if dedup_key in seen_events:
                continue
            seen_events.add(dedup_key)
            
            # Event date classification
            if status == "settled":
                if settle_date <= request_date:
                    settled_historical.append(ev)
                else:
                    # Settled event with settlement_date > request_date behaves as confirmed upcoming cashflow
                    if direction == "debit":
                        pending_scheduled_debits.append(ev)
                    elif direction == "credit":
                        confirmed_scheduled_credits.append(ev)
            elif status in ("pending", "scheduled"):
                if direction == "debit":
                    # Pending debits must be reserved on their settlement date
                    if settle_date and settle_date > request_date:
                        pending_scheduled_debits.append(ev)
                    elif settle_date and settle_date <= request_date:
                        # Settled or due today
                        pending_scheduled_debits.append(ev)
                    else:
                        # Fallback if settlement date missing: reserve on request_date
                        fallback_ev = dict(ev)
                        fallback_ev["settlement_date"] = request_date
                        pending_scheduled_debits.append(fallback_ev)
                elif direction == "credit" and ev.get("category") == "salary":
                    confirmed_scheduled_credits.append(ev)
                        
        return settled_historical, pending_scheduled_debits, confirmed_scheduled_credits
