"""
HackerRank Orchestrate — Buy or Wait? AI Financial Decision Agent
Interactive Web Frontend & API Server.
Zero external dependencies (uses standard library http.server).
"""

import sys
import os
import json
import csv
import mimetypes
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# Set up paths
REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT / "code"))

import config
from data_loader import DataLoader, VERIFIED_IMAGE_CACHE
from financial_state import FinancialState
from recurrence_detector import RecurrenceEngine
from plan_generator import PlanGenerator
from explanation_generator import ExplanationGenerator
from verifier import PlanVerifier
from simulator import Simulator

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, set):
            return list(o)
        if isinstance(o, (datetime,)):
            return o.isoformat()
        return super().default(o)

class FinancialServerContext:
    def __init__(self):
        print("[Init] Loading datasets and financial profiles...")
        self.loader = DataLoader(dataset_dir=REPO_ROOT / "dataset")
        
        # Build event descriptions mapping
        self.event_descriptions: Dict[str, str] = {}
        for ev in self.loader.events:
            self.event_descriptions[ev["event_id"]] = ev.get("description", "")
            
        # Build image links lookup: request_id -> list of image_ids
        self.request_images: Dict[str, List[Dict[str, Any]]] = {}
        images_csv_path = REPO_ROOT / "dataset" / "images.csv"
        if images_csv_path.exists():
            with open(images_csv_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    r_id = r.get("request_id", "").strip()
                    img_id = r.get("image_id", "").strip()
                    ev_id = r.get("related_event_id", "").strip()
                    u_id = r.get("user_id", "").strip()
                    cached_info = VERIFIED_IMAGE_CACHE.get(img_id, {})
                    entry = {
                        "image_id": img_id,
                        "request_id": r_id,
                        "related_event_id": ev_id,
                        "user_id": u_id,
                        "amount": float(cached_info["amount"]) if "amount" in cached_info else None,
                        "currency": cached_info.get("currency", ""),
                        "doc_type": cached_info.get("doc", "receipt"),
                        "image_url": f"/media/images/{img_id}.png"
                    }
                    if r_id:
                        self.request_images.setdefault(r_id, []).append(entry)

        # Preload output.csv and output_sample.csv predictions
        self.predictions: Dict[str, Dict[str, str]] = {}
        for path in [REPO_ROOT / "output_sample.csv", REPO_ROOT / "output.csv"]:
            if path.exists():
                with open(path, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for r in reader:
                        self.predictions[r["request_id"]] = r

        # Index requests by ID
        self.all_requests_map: Dict[str, Dict[str, Any]] = {}
        for req in self.loader.requests:
            req_copy = dict(req)
            req_copy["is_sample"] = False
            self.all_requests_map[req["request_id"]] = req_copy
            
        for req in self.loader.sample_requests:
            req_copy = dict(req)
            req_copy["is_sample"] = True
            # Don't overwrite if present in main requests
            if req["request_id"] not in self.all_requests_map:
                self.all_requests_map[req["request_id"]] = req_copy

        # Precompute overview stats
        self._compute_overview_stats()
        print(f"[Init] Ready: {len(self.all_requests_map)} requests loaded, {len(self.loader.profiles)} profiles.")

    def _compute_overview_stats(self):
        status_counts = {"affordable_now": 0, "affordable_with_plan": 0, "affordable_later": 0, "not_affordable": 0}
        method_counts = {"full_payment": 0, "partial_payment": 0, "installments": 0, "wait": 0, "not_recommended": 0}
        category_counts: Dict[str, int] = {}
        currency_totals: Dict[str, Dict[str, float]] = {}

        for req_id, req in self.all_requests_map.items():
            pred = self.predictions.get(req_id, {})
            status = pred.get("affordability_status", "unknown")
            method = pred.get("recommended_payment_method", "unknown")
            if status in status_counts:
                status_counts[status] += 1
            if method in method_counts:
                method_counts[method] += 1
                
            cat = req.get("request_type", "other")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            
            u_id = req["user_id"]
            prof = self.loader.profiles.get(u_id, {})
            curr = prof.get("home_currency", "USD")
            if curr not in currency_totals:
                currency_totals[curr] = {"requested": 0.0, "safe": 0.0}
            try:
                currency_totals[curr]["requested"] += float(req.get("requested_amount", 0))
                currency_totals[curr]["safe"] += float(pred.get("amount_safe_to_pay", 0))
            except Exception:
                pass

        self.overview_stats = {
            "total_requests": len(self.all_requests_map),
            "status_counts": status_counts,
            "method_counts": method_counts,
            "category_counts": category_counts,
            "currency_totals": currency_totals,
            "safety_rate": 100.0,
        }

    def simulate_request_detail(self, req: Dict[str, Any]) -> Dict[str, Any]:
        uid = req["user_id"]
        req_id = req["request_id"]
        req_date = req["request_date"]
        
        # 1. Financial state reconstruction
        state = FinancialState.reconstruct(uid, req_date, self.loader)
        
        # 2. Recurrence detection
        commitments = RecurrenceEngine.detect_commitments(state)
        r_debits = commitments["recurring_debits"]
        sal = commitments["salary_commitment"]
        
        # 3. Payment options
        opts = self.loader.payment_options.get(req_id, [])
        
        # 4. Plan generation
        winning_plan, amount_safe_to_pay, earliest_date, candidates = PlanGenerator.generate_and_select_plan(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            request=req,
            payment_options=opts,
        )
        
        # 5. Explanation
        explanation = ExplanationGenerator.generate_explanation(
            currency=state.home_currency,
            requested_amount=req["requested_amount"],
            amount_safe_to_pay=amount_safe_to_pay,
            minimum_balance_to_keep=state.minimum_balance_to_keep,
            desired_completion_date=req["desired_completion_date"],
            winning_plan=winning_plan,
            earliest_date_for_full_payment=earliest_date,
            event_descriptions=self.event_descriptions,
        )
        
        # 6. Verification
        val_res = PlanVerifier.verify_prediction(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            request=req,
            winning_plan=winning_plan,
            amount_safe_to_pay=amount_safe_to_pay,
            earliest_date_for_full_payment=earliest_date,
            candidates=candidates,
        )
        
        # 7. 90-Day Trajectory simulations
        # Baseline (no purchase)
        sim_baseline = Simulator.simulate(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            spending_changes=None,
            plan_payments=None,
            days=90,
        )
        
        # Winning plan
        spending_changes_dict = None
        if winning_plan.spending_changes:
            spending_changes_dict = {"stop": set(), "reduce_to": {}}
            for sc in winning_plan.spending_changes:
                parts = sc.split(":")
                if parts[0] == "stop":
                    spending_changes_dict["stop"].add(parts[1])
                elif parts[0] == "reduce_to":
                    spending_changes_dict["reduce_to"][parts[1]] = Decimal(parts[2])
                    
        sim_winning = Simulator.simulate(
            state=state,
            recurring_debits=r_debits,
            salary_commitment=sal,
            spending_changes=spending_changes_dict,
            plan_payments=winning_plan.payments,
            days=90,
        )

        # Build trajectory timeline
        start_d = datetime.strptime(req_date, "%Y-%m-%d")
        timeline = []
        for i in range(91):
            date_str = (start_d + timedelta(days=i)).strftime("%Y-%m-%d")
            base_bal = float(sim_baseline.daily_balances[i][1])
            win_bal = float(sim_winning.daily_balances[i][1])
            timeline.append({
                "day_index": i,
                "date": date_str,
                "baseline_balance": base_bal,
                "projected_balance": win_bal,
                "min_keep": float(state.minimum_balance_to_keep),
                "is_breach": win_bal < float(state.minimum_balance_to_keep)
            })

        # Format candidate plans
        formatted_candidates = []
        for cand in candidates:
            is_winner = (cand == winning_plan)
            formatted_candidates.append({
                "method": cand.method,
                "affordability_status": cand.affordability_status,
                "plan_str": cand.plan_str,
                "payments": [{"date": p[0], "amount": float(p[1])} for p in cand.payments],
                "start_date": cand.start_date,
                "completion_date": cand.completion_date,
                "total_amount_paid": float(cand.total_amount_paid),
                "num_payments": cand.num_payments,
                "payment_option_id": cand.payment_option_id,
                "spending_changes": cand.spending_changes,
                "is_safe": cand.is_safe,
                "completes_by_deadline": cand.completes_by_deadline,
                "min_headroom": float(cand.min_headroom),
                "is_winner": is_winner
            })

        # Format recurring debits
        formatted_recurring = []
        for rd in r_debits:
            formatted_recurring.append({
                "category": rd.category,
                "amount": float(rd.amount),
                "cadence": rd.cadence,
                "day_of_month": rd.day_of_month,
                "period_days": rd.period_days,
                "description": self.event_descriptions.get(rd.latest_event_id, rd.category),
                "latest_event_id": rd.latest_event_id
            })

        # User profile
        prof = self.loader.profiles.get(uid, {})

        # Multimodal images
        images = self.request_images.get(req_id, [])

        # User messages
        messages = [
            {
                "message_id": m.get("message_id", ""),
                "timestamp": m.get("timestamp", ""),
                "sender": m.get("sender", ""),
                "content": m.get("content", ""),
                "related_event_id": m.get("related_event_id", "")
            }
            for m in self.loader.messages_by_user.get(uid, [])
        ]

        return {
            "request": {
                "request_id": req_id,
                "user_id": uid,
                "request_date": req_date,
                "request_type": req.get("request_type", ""),
                "requested_amount": float(req["requested_amount"]),
                "desired_completion_date": req.get("desired_completion_date", ""),
                "allows_partial_payment": str(req.get("allows_partial_payment", "")).lower() == "true",
                "request_text": req.get("request_text", ""),
                "is_sample": req.get("is_sample", False)
            },
            "profile": {
                "user_id": uid,
                "home_currency": state.home_currency,
                "current_available_balance": float(state.current_available_balance),
                "minimum_balance_to_keep": float(state.minimum_balance_to_keep),
                "protected_categories": list(state.expense_categories_to_protect),
                "reducible_categories": list(state.expense_categories_user_is_willing_to_reduce),
                "stoppable_categories": list(state.expense_categories_user_is_willing_to_stop),
                "payment_methods_allowed": list(state.payment_methods_user_will_consider),
                "max_installment_months": state.max_installment_months,
                "priorities": state.financial_priorities,
            },
            "verdict": {
                "amount_safe_to_pay": float(amount_safe_to_pay),
                "affordability_status": winning_plan.affordability_status,
                "recommended_payment_method": winning_plan.method,
                "payment_plan": winning_plan.plan_str,
                "earliest_date_for_full_payment": earliest_date,
                "spending_changes_needed": winning_plan.spending_changes_str,
                "decision_explanation": explanation,
                "is_valid": val_res.is_valid,
                "validation_errors": val_res.errors if not val_res.is_valid else []
            },
            "timeline": timeline,
            "candidates": formatted_candidates,
            "recurring_commitments": formatted_recurring,
            "salary_commitment": {
                "amount": float(sal.amount),
                "day_of_month": sal.day_of_month,
                "effective_date": sal.effective_date
            } if sal else None,
            "images": images,
            "messages": messages,
            "payment_options": [
                {
                    "payment_option_id": o["payment_option_id"],
                    "payment_method": o["payment_method"],
                    "payment_amount": float(o["payment_amount"]),
                    "number_of_payments": int(o["number_of_payments"]),
                    "first_payment_date": o["first_payment_date"],
                    "payment_frequency_days": int(o["payment_frequency_days"]) if o["payment_frequency_days"] else None,
                    "financing_fee": float(o["financing_fee"]) if o["financing_fee"] else 0.0,
                    "total_payable_amount": float(o["total_payable_amount"]) if o["total_payable_amount"] else float(o["payment_amount"])
                }
                for o in opts
            ]
        }

# Global context
SERVER_CONTEXT: Optional[FinancialServerContext] = None

class FinancialRequestHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, cls=DecimalEncoder).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # API: Overview
        if path == "/api/overview":
            self.send_json(SERVER_CONTEXT.overview_stats)
            return

        # API: List Requests
        if path == "/api/requests":
            search_query = query.get("q", [""])[0].lower().strip()
            status_filter = query.get("status", ["all"])[0].strip()
            method_filter = query.get("method", ["all"])[0].strip()
            category_filter = query.get("category", ["all"])[0].strip()
            currency_filter = query.get("currency", ["all"])[0].strip()
            page = int(query.get("page", [1])[0])
            page_size = int(query.get("page_size", [50])[0])

            items = []
            for req_id, req in SERVER_CONTEXT.all_requests_map.items():
                pred = SERVER_CONTEXT.predictions.get(req_id, {})
                status = pred.get("affordability_status", "unknown")
                method = pred.get("recommended_payment_method", "unknown")
                cat = req.get("request_type", "")
                uid = req.get("user_id", "")
                prof = SERVER_CONTEXT.loader.profiles.get(uid, {})
                curr = prof.get("home_currency", "")
                has_imgs = req_id in SERVER_CONTEXT.request_images

                # Filter checks
                if status_filter != "all" and status != status_filter:
                    continue
                if method_filter != "all" and method != method_filter:
                    continue
                if category_filter != "all" and cat != category_filter:
                    continue
                if currency_filter != "all" and curr != currency_filter:
                    continue
                if search_query:
                    match_str = f"{req_id} {uid} {cat} {req.get('request_text', '')}".lower()
                    if search_query not in match_str:
                        continue

                items.append({
                    "request_id": req_id,
                    "user_id": uid,
                    "request_date": req.get("request_date", ""),
                    "request_type": cat,
                    "requested_amount": float(req.get("requested_amount", 0)),
                    "desired_completion_date": req.get("desired_completion_date", ""),
                    "allows_partial_payment": str(req.get("allows_partial_payment", "")).lower() == "true",
                    "home_currency": curr,
                    "affordability_status": status,
                    "recommended_payment_method": method,
                    "amount_safe_to_pay": float(pred.get("amount_safe_to_pay", 0)),
                    "earliest_date_for_full_payment": pred.get("earliest_date_for_full_payment", ""),
                    "has_images": has_imgs,
                    "is_sample": req.get("is_sample", False),
                })

            # Sort items by request_id number
            def sort_key(x):
                try:
                    return int(x["request_id"].split("_")[-1])
                except Exception:
                    return x["request_id"]
            items.sort(key=sort_key)

            total_items = len(items)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paged_items = items[start_idx:end_idx]

            self.send_json({
                "total": total_items,
                "page": page,
                "page_size": page_size,
                "total_pages": (total_items + page_size - 1) // page_size if page_size else 1,
                "items": paged_items
            })
            return

        # API: Request Detail
        if path.startswith("/api/request/"):
            req_id = path.replace("/api/request/", "").strip()
            if req_id not in SERVER_CONTEXT.all_requests_map:
                self.send_json({"error": f"Request {req_id} not found"}, status=404)
                return
            req = SERVER_CONTEXT.all_requests_map[req_id]
            try:
                detail = SERVER_CONTEXT.simulate_request_detail(req)
                self.send_json(detail)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({"error": str(e)}, status=500)
            return

        # API: User Profiles List (for Sandbox)
        if path == "/api/profiles":
            profiles = []
            def _clean_list(val):
                if isinstance(val, (set, list)):
                    return list(val)
                if isinstance(val, str):
                    return [c.strip() for c in val.split("|") if c.strip()]
                return []

            for uid, p in SERVER_CONTEXT.loader.profiles.items():
                profiles.append({
                    "user_id": uid,
                    "home_currency": p.get("home_currency", ""),
                    "current_available_balance": float(p.get("current_available_balance", 0)),
                    "minimum_balance_to_keep": float(p.get("minimum_balance_to_keep", 0)),
                    "protected_categories": _clean_list(p.get("expense_categories_to_protect")),
                    "reducible_categories": _clean_list(p.get("expense_categories_user_is_willing_to_reduce")),
                    "stoppable_categories": _clean_list(p.get("expense_categories_user_is_willing_to_stop")),
                    "payment_methods_allowed": _clean_list(p.get("payment_methods_user_will_consider")),
                    "max_installment_months": int(p["max_installment_months"]) if p.get("max_installment_months") else None,
                    "priorities": _clean_list(p.get("financial_priorities"))
                })
            profiles.sort(key=lambda x: int(x["user_id"].split("_")[-1]) if "_" in x["user_id"] else x["user_id"])
            self.send_json({"profiles": profiles})
            return

        # Serve media images
        if path.startswith("/media/images/"):
            img_filename = path.replace("/media/images/", "")
            img_path = REPO_ROOT / "dataset" / "media" / "images" / img_filename
            if img_path.exists() and img_path.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Content-Length", str(img_path.stat().st_size))
                self.send_header("Cache-Control", "public, max-age=86400")
                self.end_headers()
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
                return
            else:
                self.send_response(404)
                self.end_headers()
                return

        # Serve static frontend files
        static_dir = REPO_ROOT / "frontend"
        if path == "/" or path == "/index.html":
            file_path = static_dir / "index.html"
        else:
            rel_path = path.lstrip("/")
            file_path = static_dir / rel_path

        if file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            if not mime_type:
                mime_type = "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", f"{mime_type}; charset=utf-8" if "text" in mime_type or "javascript" in mime_type else mime_type)
            self.send_header("Content-Length", str(file_path.stat().st_size))
            self.end_headers()
            with open(file_path, "rb") as f:
                self.wfile.write(f.read())
            return

        # 404 fallback
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/simulate":
            content_length = int(self.headers.get("Content-Length", 0))
            post_body = self.rfile.read(content_length)
            try:
                data = json.loads(post_body.decode("utf-8"))
                uid = data.get("user_id")
                if not uid or uid not in SERVER_CONTEXT.loader.profiles:
                    uid = "user_01"

                req_id = data.get("request_id", "sim_custom_01")
                custom_req = {
                    "request_id": req_id,
                    "user_id": uid,
                    "request_date": data.get("request_date", "2025-06-01"),
                    "request_type": data.get("request_type", "purchase"),
                    "requested_amount": Decimal(str(data.get("requested_amount", 1000))),
                    "desired_completion_date": data.get("desired_completion_date", "2025-08-01"),
                    "allows_partial_payment": bool(data.get("allows_partial_payment", False)),
                    "request_text": data.get("request_text", "Custom simulation request"),
                    "is_sample": False
                }

                # Custom payment options if provided
                custom_opts = []
                for idx, opt in enumerate(data.get("payment_options", [])):
                    custom_opts.append({
                        "payment_option_id": opt.get("payment_option_id", f"opt_{idx+1}"),
                        "request_id": req_id,
                        "payment_method": opt.get("payment_method", "installments"),
                        "payment_amount": Decimal(str(opt.get("payment_amount", 0))),
                        "number_of_payments": int(opt.get("number_of_payments", 1)),
                        "first_payment_date": opt.get("first_payment_date", custom_req["request_date"]),
                        "payment_frequency_days": int(opt.get("payment_frequency_days", 30)) if opt.get("payment_frequency_days") else None,
                        "financing_fee": Decimal(str(opt.get("financing_fee", 0))),
                        "total_payable_amount": Decimal(str(opt.get("total_payable_amount", opt.get("payment_amount", 0)))),
                    })
                SERVER_CONTEXT.loader.payment_options[req_id] = custom_opts

                res = SERVER_CONTEXT.simulate_request_detail(custom_req)
                self.send_json(res)
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_json({"error": str(e)}, status=500)
            return

        self.send_response(404)
        self.end_headers()

def run_server(host="127.0.0.1", port=8000):
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass
    global SERVER_CONTEXT
    SERVER_CONTEXT = FinancialServerContext()
    server = ThreadingHTTPServer((host, port), FinancialRequestHandler)
    print("\n=======================================================")
    print("[SERVER] BUY OR WAIT? AI FINANCIAL AGENT DASHBOARD")
    print(f"[SERVER] Running at: http://{host}:{port}/")
    print("=======================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
    run_server(port=port)
