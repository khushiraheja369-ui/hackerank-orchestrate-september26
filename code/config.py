"""
Configuration and Schema Definitions for Buy or Wait? Financial Decision Agent.
Authoritative Reference: problem_statement.md
"""

from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP

# Root and Data Directories
REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
MEDIA_DIR = DATASET_DIR / "media" / "images"
EVALUATION_DIR = REPO_ROOT / "code" / "evaluation"
ROOT_OUTPUT_CSV = REPO_ROOT / "output.csv"

# Dataset Files
REQUESTS_CSV = DATASET_DIR / "requests.csv"
SAMPLE_REQUESTS_CSV = DATASET_DIR / "sample_requests.csv"
FINANCIAL_PROFILES_CSV = DATASET_DIR / "financial_profiles.csv"
FINANCIAL_EVENTS_CSV = DATASET_DIR / "financial_events.csv"
EXCHANGE_RATES_CSV = DATASET_DIR / "exchange_rates.csv"
REQUEST_PAYMENT_OPTIONS_CSV = DATASET_DIR / "request_payment_options.csv"
MESSAGES_CSV = DATASET_DIR / "messages.csv"
IMAGES_CSV = DATASET_DIR / "images.csv"
TEMPLATE_OUTPUT_CSV = DATASET_DIR / "output.csv"

# Evaluation Artifacts
USAGE_REPORT_MD = EVALUATION_DIR / "usage_report.md"
SAMPLE_BENCHMARK_RESULTS_MD = EVALUATION_DIR / "sample_benchmark_results.md"
HIGH_RISK_CASES_MD = EVALUATION_DIR / "high_risk_cases.md"
VALIDATION_REPORT_MD = EVALUATION_DIR / "validation_report.md"

# Output Contract: Required Columns in Exact Order
REQUIRED_OUTPUT_COLUMNS = [
    "request_id",
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]

# Allowed Enumeration Values
ALLOWED_AFFORDABILITY_STATUS = {
    "affordable_now",
    "affordable_with_plan",
    "affordable_later",
    "not_affordable",
}

ALLOWED_RECOMMENDED_PAYMENT_METHOD = {
    "full_payment",
    "partial_payment",
    "installments",
    "wait",
    "not_recommended",
}

ALLOWED_REQUEST_TYPES = {
    "purchase",
    "travel",
    "education",
    "family_transfer",
    "debt_repayment",
    "investment",
    "housing",
    "emergency_expense",
    "other",
}

# Simulation Parameters
FORECAST_DAYS = 90

# Pricing configuration (per 1,000,000 tokens for Gemini 1.5/2.0 Flash / Pro)
MODEL_PRICING = {
    "gemini-2.0-flash": {
        "input_per_million": Decimal("0.10"),
        "output_per_million": Decimal("0.40"),
    },
    "gemini-1.5-flash": {
        "input_per_million": Decimal("0.075"),
        "output_per_million": Decimal("0.30"),
    },
    "gemini-1.5-pro": {
        "input_per_million": Decimal("1.25"),
        "output_per_million": Decimal("5.00"),
    },
}

def to_decimal(val) -> Decimal:
    """Safely convert any numeric / string value to Decimal without float contamination."""
    if val is None:
        return Decimal("0")
    if isinstance(val, Decimal):
        return val
    s = str(val).strip().replace(",", "")
    if not s:
        return Decimal("0")
    return Decimal(s)

def format_currency_decimal(d: Decimal) -> str:
    """
    Format monetary amounts according to benchmark representation:
    - If exact integer: format without decimals (e.g. 25256, 873000)
    - If has fractional part: quantize to 2 decimals, trimming trailing zeros (e.g. 17229139.2, 603.3, 87170.56)
    """
    if d is None:
        return ""
    d = Decimal(d)
    if d == d.to_integral():
        return str(int(d))
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if q == q.to_integral():
        return str(int(q))
    return f"{q:.2f}".rstrip("0").rstrip(".")

def format_display_amount(d: Decimal) -> str:
    """Format decimal with commas for readable decision explanations (e.g. 25,256 or 15,952,906.67)."""
    d = Decimal(d)
    if d == d.to_integral():
        return f"{int(d):,}"
    q = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{q:,.2f}".rstrip("0").rstrip(".") if q != q.to_integral() else f"{int(q):,}"
