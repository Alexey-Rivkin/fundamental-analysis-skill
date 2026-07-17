"""Fundamental analysis of a US-listed stock using yfinance.

Implements a 5-layer KPI framework:

  Layer 0 : company familiarity        (human-only, listed for the reader)
  Layer 1 : Profitability   (6 params) revenue growth, GM, OM, NM, EPS, EBITDA
  Layer 2 : Valuation       (7 params) P/E, Fwd P/E, P/S, EV/EBITDA, PEG, P/B, P/E vs sector
  Layer 3 : Cash Flow       (4 params) OCF, FCF, FCF margin, FCF yield
  Layer 4 : Financial Health(5 params) Debt/Equity, Net Cash/Debt, Current Ratio, ROE, ROIC (proxy)
  Layer 5 : Forward Signals (5 params) analyst target, revision, guidance implied, buyback, insider holding

Core rule: never absolute, always compared. When --peers is given, every
Layer 1-4 ratio is reported alongside the peer median so the reader sees whether
the number is above or below its sector.

Usage:
    python analyze.py NVDA
    python analyze.py NVDA --peers AMD,AVGO,INTC
    python analyze.py NVDA --peers auto           # auto-pick 4 sector peers
    python analyze.py NVDA AMD --compare          # side-by-side comparison
    python analyze.py NVDA --lang he              # Hebrew (RTL) report
    python analyze.py NVDA --json out.json        # machine-readable output
    python analyze.py NVDA --md out.md            # markdown report file

Output is a markdown report to stdout by default (also written to --md path).
The report is not financial advice.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


# --- yfinance import guarded so the caller gets a clear message ---
try:
    import yfinance as yf
except ModuleNotFoundError:
    sys.stderr.write(
        "ERROR: yfinance is not installed. Run via `uv run --with yfinance python3 analyze.py …`\n"
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_pct(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x * 100:.1f}%"


def _fmt_num(x: float | None, unit: str = "") -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    if abs(x) >= 1e12:
        return f"${x / 1e12:.2f}T"
    if abs(x) >= 1e9:
        return f"${x / 1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"${x / 1e6:.2f}M"
    return f"{x:.2f}{unit}"


def _fmt_ratio(x: float | None) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/a"
    return f"{x:.2f}"


def _delta(value: float | None, peer_median: float | None,
           higher_is_better: bool = True, lang: str = "en") -> str:
    """Return a compact ' _(peers X, ↑/↓ Y%)_ ' string, or '' if unavailable.

    The arrow reflects direction vs peer (↑ = above peers, ↓ = below).
    The tick (✓/✗) reflects whether that direction is good for this metric.
    """
    if value is None or peer_median is None:
        return ""
    if peer_median == 0:
        return ""
    diff = (value - peer_median) / abs(peer_median)
    arrow = "↑" if diff >= 0 else "↓"
    is_favorable = (diff > 0) == higher_is_better
    tick = "✓" if is_favorable else "✗"
    label = LOCALES[lang]["peers_note_prefix"]
    return f"  _({label} {_fmt_ratio(peer_median)}, {arrow}{diff * 100:+.0f}% {tick})_"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    ticker: str
    name: str = ""
    sector: str = ""
    industry: str = ""
    price: float | None = None
    market_cap: float | None = None
    ev: float | None = None
    currency: str = "USD"

    # Layer 1 — Profitability
    revenue_ttm: float | None = None
    revenue_growth_yoy: float | None = None
    gross_margin: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    eps_ttm: float | None = None
    eps_forward: float | None = None
    ebitda_ttm: float | None = None

    # Layer 2 — Valuation
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_sales: float | None = None
    ev_to_ebitda: float | None = None
    peg_ratio: float | None = None
    price_to_book: float | None = None

    # Layer 3 — Cash flow
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    fcf_margin: float | None = None
    fcf_yield: float | None = None

    # Layer 4 — Financial health
    total_debt: float | None = None
    total_cash: float | None = None
    debt_to_equity: float | None = None
    net_cash: float | None = None
    current_ratio: float | None = None
    quick_ratio: float | None = None
    roe: float | None = None
    roic_proxy: float | None = None
    payout_ratio: float | None = None

    # Layer 5 — Forward signals
    target_mean: float | None = None
    target_median: float | None = None
    recommendation_mean: float | None = None
    recommendation_key: str = ""
    insider_pct: float | None = None
    institution_pct: float | None = None
    shares_short_pct: float | None = None

    # Series (quarterly, most-recent-first)
    q_revenue: list[float] = field(default_factory=list)
    q_ocf: list[float] = field(default_factory=list)
    q_fcf: list[float] = field(default_factory=list)
    q_dates: list[str] = field(default_factory=list)


def load_snapshot(ticker: str) -> Snapshot:
    t = yf.Ticker(ticker)
    info = t.info or {}

    snap = Snapshot(
        ticker=ticker.upper(),
        name=info.get("shortName") or info.get("longName") or ticker.upper(),
        sector=info.get("sector") or "",
        industry=info.get("industry") or "",
        price=info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose"),
        market_cap=info.get("marketCap"),
        ev=info.get("enterpriseValue"),
        currency=info.get("currency", "USD"),

        revenue_ttm=info.get("totalRevenue"),
        revenue_growth_yoy=info.get("revenueGrowth"),
        gross_margin=info.get("grossMargins"),
        operating_margin=info.get("operatingMargins"),
        net_margin=info.get("profitMargins"),
        eps_ttm=info.get("trailingEps"),
        eps_forward=info.get("forwardEps"),

        trailing_pe=info.get("trailingPE"),
        forward_pe=info.get("forwardPE"),
        price_to_sales=info.get("priceToSalesTrailing12Months"),
        peg_ratio=info.get("pegRatio") or info.get("trailingPegRatio"),
        price_to_book=info.get("priceToBook"),

        operating_cash_flow=info.get("operatingCashflow"),
        free_cash_flow=info.get("freeCashflow"),

        total_debt=info.get("totalDebt"),
        total_cash=info.get("totalCash"),
        debt_to_equity=(info.get("debtToEquity") / 100 if info.get("debtToEquity") else None),
        current_ratio=info.get("currentRatio"),
        quick_ratio=info.get("quickRatio"),
        roe=info.get("returnOnEquity"),
        payout_ratio=info.get("payoutRatio"),

        target_mean=info.get("targetMeanPrice"),
        target_median=info.get("targetMedianPrice"),
        recommendation_mean=info.get("recommendationMean"),
        recommendation_key=info.get("recommendationKey", ""),
        insider_pct=info.get("heldPercentInsiders"),
        institution_pct=info.get("heldPercentInstitutions"),
        shares_short_pct=info.get("shortPercentOfFloat"),
    )

    # Derived
    if snap.free_cash_flow and snap.revenue_ttm:
        snap.fcf_margin = snap.free_cash_flow / snap.revenue_ttm
    if snap.free_cash_flow and snap.market_cap:
        snap.fcf_yield = snap.free_cash_flow / snap.market_cap
    if snap.total_cash is not None and snap.total_debt is not None:
        snap.net_cash = snap.total_cash - snap.total_debt

    # EBITDA + EV/EBITDA from quarterly income statement (info.ebitda isn't reliable)
    try:
        qis = t.quarterly_income_stmt
        if qis is not None and not qis.empty and "EBITDA" in qis.index:
            row = qis.loc["EBITDA"]
            ebitda_ttm = float(row.dropna().head(4).sum())
            snap.ebitda_ttm = ebitda_ttm
            if snap.ev and ebitda_ttm:
                snap.ev_to_ebitda = snap.ev / ebitda_ttm
        if qis is not None and not qis.empty and "Total Revenue" in qis.index:
            rev_row = qis.loc["Total Revenue"].dropna()
            snap.q_revenue = [float(v) for v in rev_row.head(8)]
            snap.q_dates = [d.strftime("%Y-%m-%d") for d in rev_row.head(8).index]
    except Exception:
        pass

    # ROIC proxy: NetIncome / (TotalDebt + StockholdersEquity)
    try:
        bs = t.quarterly_balance_sheet
        if bs is not None and not bs.empty and "Stockholders Equity" in bs.index:
            equity = float(bs.loc["Stockholders Equity"].dropna().iloc[0])
            debt = snap.total_debt or 0
            ni = info.get("netIncomeToCommon")
            if ni and (equity + debt):
                snap.roic_proxy = ni / (equity + debt)
    except Exception:
        pass

    # Quarterly OCF/FCF
    try:
        qcf = t.quarterly_cash_flow
        if qcf is not None and not qcf.empty:
            if "Operating Cash Flow" in qcf.index:
                snap.q_ocf = [float(v) for v in qcf.loc["Operating Cash Flow"].dropna().head(8)]
            if "Free Cash Flow" in qcf.index:
                snap.q_fcf = [float(v) for v in qcf.loc["Free Cash Flow"].dropna().head(8)]
    except Exception:
        pass

    return snap


# ---------------------------------------------------------------------------
# Peer sourcing
# ---------------------------------------------------------------------------

# Curated fallback peer sets for the common sectors — yfinance no longer exposes
# reliable industry-peer lists via `Ticker.recommendations`, so a small hand
# table beats network lookups for the most-asked names.
_HARDCODED_PEERS = {
    "NVDA": ["AMD", "AVGO", "INTC", "QCOM"],
    "AMD":  ["NVDA", "INTC", "AVGO", "QCOM"],
    "INTC": ["NVDA", "AMD", "AVGO", "QCOM"],
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "META", "AMZN"],
    "GOOGL":["MSFT", "AAPL", "META", "AMZN"],
    "META": ["GOOGL", "MSFT", "AAPL", "AMZN"],
    "AMZN": ["MSFT", "GOOGL", "AAPL", "META"],
    "TSLA": ["F",    "GM",    "STLA",  "TM"],
    "NFLX": ["DIS",  "WBD",   "PARA",  "CMCSA"],
}


def resolve_peers(ticker: str, spec: str | None) -> list[str]:
    if not spec:
        return []
    if spec.lower() != "auto":
        return [p.strip().upper() for p in spec.split(",") if p.strip()]
    return _HARDCODED_PEERS.get(ticker.upper(), [])


def peer_median(snaps: list[Snapshot], attr: str) -> float | None:
    vals = [getattr(s, attr) for s in snaps if getattr(s, attr) is not None]
    return statistics.median(vals) if vals else None


# ---------------------------------------------------------------------------
# Localisation
# ---------------------------------------------------------------------------

# English is the source-of-truth. Hebrew layer names and section titles mirror
# how Israeli traders read them in practice; English financial terms stay in
# Latin (Revenue, EBITDA, Free Cash Flow, PEG, Buy Back, etc.) because that's
# how the market documents them.
LOCALES = {
    "en": {
        "dir": "ltr",
        "title_suffix": "— Fundamental Analysis",
        "sector_line": "_Sector: {sector} · Industry: {industry} · Currency: {currency}_",
        "generated": "_Generated: {ts}_",
        "peer_set": "_Peer set: {peers}_",
        "peers_note_prefix": "peers",
        "disclaimer": (
            "> **Not financial advice. Not a recommendation to buy or sell.** "
            "Data via yfinance (Yahoo Finance) at the time shown below; may be stale, "
            "adjusted, or wrong. Always verify against the company's own filings."
        ),
        "price_line": "**Price:** {price}  · **Market Cap:** {mcap}  · **EV:** {ev}",
        "layer0_title": "Layer 0 — Company familiarity",
        "layer0_body": (
            "This layer isn't AI-fillable. Before trusting any number below,\n"
            "visit https://finance.yahoo.com/quote/{ticker} and the company's own site,\n"
            "read the latest earnings call, and watch a recent CEO interview. Understand\n"
            "the product, the customers, the moat. Otherwise the ratios are noise."
        ),
        "layer1_title": "Layer 1 — Profitability",
        "layer2_title": "Layer 2 — Valuation",
        "layer3_title": "Layer 3 — Cash Flow",
        "layer4_title": "Layer 4 — Financial Health",
        "layer5_title": "Layer 5 — Forward Signals",
        "col_metric": "Metric",
        "col_value": "Value",
        "col_notes": "Notes",
        "col_multiple": "Multiple",
        "col_signal": "Signal",
        "rows": {
            "revenue_ttm": ("Revenue TTM", "Total sales over the trailing 12 months."),
            "revenue_growth_yoy": ("Revenue growth YoY", "Momentum. Rising cadence > declining cadence."),
            "gross_margin": ("Gross margin", "Revenue − COGS as %. Product-level leverage."),
            "operating_margin": ("Operating margin", "After opex. \"Is the business lean?\""),
            "net_margin": ("Net margin", "True bottom line."),
            "eps_ttm": ("EPS trailing", "Net income / shares outstanding. Buy-backs lift this."),
            "eps_forward": ("EPS forward", "Analyst consensus for next 12m."),
            "ebitda_ttm": ("EBITDA TTM", "Pre-D&A / interest / tax operating earnings."),
            "trailing_pe": ("P/E trailing", "Price per $1 of last-year earnings."),
            "forward_pe": ("P/E forward", "Vs. next-year consensus. **Prefer this over trailing** — future cash flows are what you're buying."),
            "price_to_sales": ("Price / Sales", "Market cap ÷ revenue. Critical when earnings are noisy."),
            "ev_to_ebitda": ("EV / EBITDA", "Capital-structure neutral."),
            "peg_ratio": ("PEG ratio", "P/E ÷ growth. <1 = potentially undervalued for growth stocks."),
            "price_to_book": ("Price / Book", "Useful for asset-heavy businesses. Less so for tech."),
            "operating_cash_flow": ("Operating cash flow", "Cash generated by the actual business."),
            "free_cash_flow": ("Free cash flow", "OCF − CapEx. What's left after keeping the lights on."),
            "fcf_margin": ("FCF margin", "FCF as % of revenue. Quality of earnings."),
            "fcf_yield": ("FCF yield", "FCF / Market Cap. Reciprocal of a cash-based P/E."),
            "q_fcf": ("Quarterly FCF (oldest → newest)", "Trend, not level, is the signal."),
            "total_debt": ("Total debt", ""),
            "total_cash": ("Total cash", ""),
            "net_cash": ("Net cash / (debt)", "Positive = net-cash balance sheet."),
            "debt_to_equity": ("Debt / Equity", "Leverage."),
            "current_ratio": ("Current ratio", "Assets ÷ liabilities (short term). >1 = can meet 12m obligations."),
            "roe": ("ROE", "Return on shareholder equity."),
            "roic_proxy": ("ROIC (proxy)", "Net income ÷ (debt + equity). True ROIC needs the tax rate; this is close enough for a filter."),
            "payout_ratio": ("Dividend payout", "Fraction of earnings paid out."),
            "target_median": ("Analyst target (median)", "Consensus 12-month target."),
            "recommendation": ("Analyst recommendation", "1 = strong buy, 5 = strong sell."),
            "insider_pct": ("Insider ownership", "Do managers hold their own stock?"),
            "institution_pct": ("Institutional ownership", "High = crowded; low = under-followed."),
            "shares_short_pct": ("Short interest (% float)", "High = market is betting against."),
        },
        "vs_price": "vs price",
        "three_signal_title": "Three-signal bottom line",
        "three_signal_intro": "If you remember nothing else, look at three things:",
        "signal1": "**Free cash flow** — is the company actually generating cash, or is it a treadmill? FCF is {status}.",
        "fcf_positive": "positive at {v}",
        "fcf_negative": "**negative** at {v}",
        "fcf_unknown": "unavailable",
        "signal2": "**Revenue growth** — direction and pace: {msg}",
        "growth_grow": "{p} YoY. Growing.",
        "growth_flat": "{p} YoY. Stagnant.",
        "growth_shrink": "{p} YoY. Shrinking.",
        "signal3": "**ROIC vs WACC** — true value creation. ROIC (proxy) is {msg}",
        "roic_good": "{p}. Above a 10% cost-of-capital hurdle — value creator.",
        "roic_bad": "{p}. Below a 10% cost-of-capital hurdle — value destroyer or thin margin of safety.",
        "signal_outro": "Ask AI for the sector median on each of these three and compare — never trust the absolute number, always the relative one.",
        "prompts_title": "Prompt-engineering reminders",
        "prompts_intro": "Don't ask AI \"is X a good stock?\". Ask questions that reference the KPIs you just read. Templates:",
        "prompt_1": "`What is {ticker}'s free cash flow margin trend over the last 8 quarters versus the sector median?`",
        "prompt_2": "`Compare {ticker}'s forward P/E and PEG to its 3 closest peers, and explain the spread.`",
        "prompt_3": "`Given {ticker}'s ROIC ({roic}), is it earning above its cost of capital? Use a 10% WACC assumption unless a better figure is public.`",
        "compare_title": "Comparison — {tickers}",
        "compare_metric": "Metric",
        "compare_rows": [
            ("Sector", "sector", "str"),
            ("Price", "price", "num"),
            ("Market Cap", "market_cap", "num"),
            ("Revenue TTM", "revenue_ttm", "num"),
            ("Rev growth YoY", "revenue_growth_yoy", "pct"),
            ("Gross margin", "gross_margin", "pct"),
            ("Op margin", "operating_margin", "pct"),
            ("Net margin", "net_margin", "pct"),
            ("P/E fwd", "forward_pe", "ratio"),
            ("P/S", "price_to_sales", "ratio"),
            ("EV/EBITDA", "ev_to_ebitda", "ratio"),
            ("PEG", "peg_ratio", "ratio"),
            ("P/B", "price_to_book", "ratio"),
            ("FCF", "free_cash_flow", "num"),
            ("FCF margin", "fcf_margin", "pct"),
            ("FCF yield", "fcf_yield", "pct"),
            ("Debt/Equity", "debt_to_equity", "ratio"),
            ("Net cash", "net_cash", "num"),
            ("ROE", "roe", "pct"),
            ("ROIC (proxy)", "roic_proxy", "pct"),
            ("Target median", "target_median", "num"),
            ("Rec (1=SB)", "recommendation_mean", "ratio"),
        ],
    },
    "he": {
        "dir": "rtl",
        "title_suffix": "— ניתוח פנדמנטלי",
        "sector_line": "_סקטור: {sector} · תעשייה: {industry} · מטבע: {currency}_",
        "generated": "_נוצר: {ts}_",
        "peer_set": "_קבוצת השוואה: {peers}_",
        "peers_note_prefix": "עמיתים",
        "disclaimer": (
            "> **אינו ייעוץ פיננסי. אינו המלצה לקנייה או מכירה.** "
            "הנתונים מבוססים על yfinance (Yahoo Finance) בשעת ההרצה; ייתכן שאינם מעודכנים, "
            "מותאמים או שגויים. יש לאמת מול הדוחות הרשמיים של החברה."
        ),
        "price_line": "**מחיר:** {price}  · **שווי שוק:** {mcap}  · **Enterprise Value:** {ev}",
        "layer0_title": "שכבה 0 — היכרות עם החברה",
        "layer0_body": (
            "השכבה הזאת AI לא יכול למלא בשבילכם. לפני שמסתמכים על נתון כלשהו מטה,\n"
            "היכנסו ל-https://finance.yahoo.com/quote/{ticker} ולאתר של החברה,\n"
            "האזינו לשיחת התוצאות האחרונה וצפו בראיון עדכני עם המנכ״ל. הבינו\n"
            "את המוצר, את הלקוחות, את החפיר. אחרת היחסים הם רעש."
        ),
        "layer1_title": "שכבה 1 — רווחיות (Profitability)",
        "layer2_title": "שכבה 2 — הערכת שווי (Valuation)",
        "layer3_title": "שכבה 3 — תזרים מזומנים (Cash Flow)",
        "layer4_title": "שכבה 4 — איתנות פיננסית",
        "layer5_title": "שכבה 5 — סימני עתיד",
        "col_metric": "מדד",
        "col_value": "ערך",
        "col_notes": "הערות",
        "col_multiple": "מכפיל",
        "col_signal": "סימן",
        "rows": {
            "revenue_ttm": ("Revenue TTM (הכנסות)", "סך המכירות ב-12 החודשים האחרונים."),
            "revenue_growth_yoy": ("קצב גידול הכנסות (YoY)", "מומנטום. קצב עולה עדיף על קצב יורד."),
            "gross_margin": ("Gross Margin (שולי רווח גולמיים)", "הכנסות − COGS באחוזים. יעילות ברמת המוצר."),
            "operating_margin": ("Operating Margin (שולי רווח אופרטיביים)", "אחרי הוצאות אופרטיביות. \"האם העסק רזה?\""),
            "net_margin": ("Net Margin (שולי רווח נקי)", "השורה התחתונה האמיתית."),
            "eps_ttm": ("EPS (רווח למניה) trailing", "רווח נקי חלקי כמות המניות. Buy Back מעלה את זה."),
            "eps_forward": ("EPS forward", "תחזית אנליסטים ל-12 החודשים הבאים."),
            "ebitda_ttm": ("EBITDA TTM", "רווח לפני פחת/הפחתות/ריבית/מס."),
            "trailing_pe": ("P/E trailing", "מחיר לכל $1 של רווחיות בשנה האחרונה."),
            "forward_pe": ("P/E forward", "מול תחזית שנה קדימה. **עדיף על trailing** — מה שקונים זה תזרימים עתידיים."),
            "price_to_sales": ("Price / Sales", "שווי שוק חלקי הכנסות. קריטי כשהרווחיות רועשת."),
            "ev_to_ebitda": ("EV / EBITDA", "נייטרלי למבנה הון."),
            "peg_ratio": ("PEG ratio", "P/E חלקי קצב הצמיחה. <1 = פוטנציאל תמחור-חסר לחברת צמיחה."),
            "price_to_book": ("Price / Book", "שימושי לעסקים עתירי נכסים. פחות לטק."),
            "operating_cash_flow": ("Operating Cash Flow", "מזומן שנוצר מהאופרציה בפועל."),
            "free_cash_flow": ("Free Cash Flow", "OCF פחות CapEx. מה שנשאר אחרי אחזקת העסק."),
            "fcf_margin": ("FCF Margin", "FCF כאחוז מההכנסות. איכות רווחים."),
            "fcf_yield": ("FCF Yield", "FCF חלקי שווי שוק. הפוך ל-P/E מבוסס-מזומן."),
            "q_fcf": ("FCF רבעוני (ישן → חדש)", "המגמה חשובה, לא הרמה."),
            "total_debt": ("סך חוב", ""),
            "total_cash": ("סך מזומן", ""),
            "net_cash": ("Net Cash / (Debt)", "חיובי = מאזן במזומן נטו."),
            "debt_to_equity": ("Debt / Equity", "מינוף."),
            "current_ratio": ("Current Ratio", "נכסים חלקי התחייבויות (טווח קצר). >1 = יכולת עמידה ב-12 חודש."),
            "roe": ("ROE", "תשואה על ההון העצמי."),
            "roic_proxy": ("ROIC (קירוב)", "רווח נקי חלקי (חוב + הון). ROIC אמיתי דורש שיעור מס; הקירוב מספיק לסינון."),
            "payout_ratio": ("שיעור חלוקת דיבידנד", "אחוז הרווחים המחולק כדיבידנד."),
            "target_median": ("יעד אנליסטים (חציון)", "יעד קונצנזוס ל-12 חודשים."),
            "recommendation": ("המלצת אנליסטים", "1 = strong buy, 5 = strong sell."),
            "insider_pct": ("אחזקת אינסיידרים", "האם המנהלים מחזיקים במניה?"),
            "institution_pct": ("אחזקה מוסדית", "גבוה = צפוף; נמוך = חסר סיקור."),
            "shares_short_pct": ("Short Interest (% float)", "גבוה = השוק בפוזיציה שורט."),
        },
        "vs_price": "מול המחיר",
        "three_signal_title": "שלושת הסימנים המרכזיים",
        "three_signal_intro": "אם תזכרו רק שלושה דברים — הסתכלו על אלה:",
        "signal1": "**Free Cash Flow** — האם החברה באמת מייצרת מזומן, או מכונה על הליכון? FCF הוא {status}.",
        "fcf_positive": "חיובי, {v}",
        "fcf_negative": "**שלילי**, {v}",
        "fcf_unknown": "לא זמין",
        "signal2": "**קצב גידול הכנסות** — כיוון וקצב: {msg}",
        "growth_grow": "{p} YoY. גדל.",
        "growth_flat": "{p} YoY. סטגנטי.",
        "growth_shrink": "{p} YoY. מתכווץ.",
        "signal3": "**ROIC מול WACC** — יצירת ערך אמיתית. ROIC (קירוב) הוא {msg}",
        "roic_good": "{p}. מעל רף עלות הון של 10% — יוצר ערך.",
        "roic_bad": "{p}. מתחת לרף עלות הון של 10% — משמיד ערך או ביטחון דק.",
        "signal_outro": "שאלו את ה-AI מה חציון הסקטור בכל אחד משלושת הפרמטרים והשוו — לעולם אל תסתמכו על הערך המוחלט, רק על היחסי.",
        "prompts_title": "תזכורות לפרומפט-אנגינירינג",
        "prompts_intro": "אל תשאלו את ה-AI \"האם X היא מניה טובה?\". שאלו שאלות שמפנות ל-KPIs שקראתם עכשיו. תבניות:",
        "prompt_1": "`What is {ticker}'s free cash flow margin trend over the last 8 quarters versus the sector median?`",
        "prompt_2": "`Compare {ticker}'s forward P/E and PEG to its 3 closest peers, and explain the spread.`",
        "prompt_3": "`Given {ticker}'s ROIC ({roic}), is it earning above its cost of capital? Use a 10% WACC assumption unless a better figure is public.`",
        "compare_title": "השוואה — {tickers}",
        "compare_metric": "מדד",
        "compare_rows": [
            ("סקטור", "sector", "str"),
            ("מחיר", "price", "num"),
            ("שווי שוק", "market_cap", "num"),
            ("Revenue TTM", "revenue_ttm", "num"),
            ("קצב גידול הכנסות YoY", "revenue_growth_yoy", "pct"),
            ("Gross Margin", "gross_margin", "pct"),
            ("Op Margin", "operating_margin", "pct"),
            ("Net Margin", "net_margin", "pct"),
            ("P/E fwd", "forward_pe", "ratio"),
            ("P/S", "price_to_sales", "ratio"),
            ("EV/EBITDA", "ev_to_ebitda", "ratio"),
            ("PEG", "peg_ratio", "ratio"),
            ("P/B", "price_to_book", "ratio"),
            ("FCF", "free_cash_flow", "num"),
            ("FCF Margin", "fcf_margin", "pct"),
            ("FCF Yield", "fcf_yield", "pct"),
            ("Debt/Equity", "debt_to_equity", "ratio"),
            ("Net Cash", "net_cash", "num"),
            ("ROE", "roe", "pct"),
            ("ROIC (קירוב)", "roic_proxy", "pct"),
            ("יעד חציוני", "target_median", "num"),
            ("המלצה (1=SB)", "recommendation_mean", "ratio"),
        ],
    },
}

_DISCLAIMER = LOCALES["en"]["disclaimer"]  # retained for back-compat, unused in renderers now


def _row(loc: dict, key: str, value_str: str, delta: str = "") -> str:
    """One markdown table row using the localised (label, note) pair."""
    label, note = loc["rows"][key]
    return f"| {label} | {value_str}{delta} | {note} |"


def render_markdown(subject: Snapshot, peers: list[Snapshot], lang: str = "en") -> str:
    loc = LOCALES[lang]

    def dm(attr: str, higher_is_better: bool = True) -> str:
        return _delta(getattr(subject, attr), peer_median(peers, attr),
                      higher_is_better, lang=lang)

    lines: list[str] = []
    lines.append(f"# {subject.name} ({subject.ticker}) {loc['title_suffix']}")
    lines.append("")
    lines.append(loc["sector_line"].format(
        sector=subject.sector or "n/a",
        industry=subject.industry or "n/a",
        currency=subject.currency,
    ))
    lines.append(loc["generated"].format(ts=datetime.now().strftime("%Y-%m-%d %H:%M")))
    if peers:
        lines.append(loc["peer_set"].format(peers=", ".join(s.ticker for s in peers)))
    lines.append("")
    lines.append(loc["disclaimer"])
    lines.append("")
    lines.append(loc["price_line"].format(
        price=_fmt_num(subject.price),
        mcap=_fmt_num(subject.market_cap),
        ev=_fmt_num(subject.ev),
    ))
    lines.append("")

    # Layer 0
    lines.append(f"## {loc['layer0_title']}")
    lines.append("")
    lines.append(loc["layer0_body"].format(ticker=subject.ticker))
    lines.append("")

    def _table_header(first_col: str) -> None:
        lines.append(f"| {first_col} | {loc['col_value']} | {loc['col_notes']} |")
        lines.append("|---|---|---|")

    # Layer 1
    lines.append(f"## {loc['layer1_title']}")
    lines.append("")
    _table_header(loc["col_metric"])
    lines.append(_row(loc, "revenue_ttm", _fmt_num(subject.revenue_ttm)))
    lines.append(_row(loc, "revenue_growth_yoy", _fmt_pct(subject.revenue_growth_yoy), dm("revenue_growth_yoy")))
    lines.append(_row(loc, "gross_margin", _fmt_pct(subject.gross_margin), dm("gross_margin")))
    lines.append(_row(loc, "operating_margin", _fmt_pct(subject.operating_margin), dm("operating_margin")))
    lines.append(_row(loc, "net_margin", _fmt_pct(subject.net_margin), dm("net_margin")))
    lines.append(_row(loc, "eps_ttm", _fmt_ratio(subject.eps_ttm)))
    lines.append(_row(loc, "eps_forward", _fmt_ratio(subject.eps_forward)))
    lines.append(_row(loc, "ebitda_ttm", _fmt_num(subject.ebitda_ttm)))
    lines.append("")

    # Layer 2
    lines.append(f"## {loc['layer2_title']}")
    lines.append("")
    _table_header(loc["col_multiple"])
    lines.append(_row(loc, "trailing_pe", _fmt_ratio(subject.trailing_pe), dm("trailing_pe", higher_is_better=False)))
    lines.append(_row(loc, "forward_pe", _fmt_ratio(subject.forward_pe), dm("forward_pe", higher_is_better=False)))
    lines.append(_row(loc, "price_to_sales", _fmt_ratio(subject.price_to_sales), dm("price_to_sales", higher_is_better=False)))
    lines.append(_row(loc, "ev_to_ebitda", _fmt_ratio(subject.ev_to_ebitda), dm("ev_to_ebitda", higher_is_better=False)))
    lines.append(_row(loc, "peg_ratio", _fmt_ratio(subject.peg_ratio), dm("peg_ratio", higher_is_better=False)))
    lines.append(_row(loc, "price_to_book", _fmt_ratio(subject.price_to_book), dm("price_to_book", higher_is_better=False)))
    lines.append("")

    # Layer 3
    lines.append(f"## {loc['layer3_title']}")
    lines.append("")
    _table_header(loc["col_metric"])
    lines.append(_row(loc, "operating_cash_flow", _fmt_num(subject.operating_cash_flow)))
    lines.append(_row(loc, "free_cash_flow", _fmt_num(subject.free_cash_flow)))
    lines.append(_row(loc, "fcf_margin", _fmt_pct(subject.fcf_margin), dm("fcf_margin")))
    lines.append(_row(loc, "fcf_yield", _fmt_pct(subject.fcf_yield), dm("fcf_yield")))
    if subject.q_fcf:
        recent = " → ".join(_fmt_num(v) for v in reversed(subject.q_fcf[:6]))
        lines.append(_row(loc, "q_fcf", recent))
    lines.append("")

    # Layer 4
    lines.append(f"## {loc['layer4_title']}")
    lines.append("")
    _table_header(loc["col_metric"])
    lines.append(_row(loc, "total_debt", _fmt_num(subject.total_debt)))
    lines.append(_row(loc, "total_cash", _fmt_num(subject.total_cash)))
    lines.append(_row(loc, "net_cash", _fmt_num(subject.net_cash)))
    lines.append(_row(loc, "debt_to_equity", _fmt_ratio(subject.debt_to_equity), dm("debt_to_equity", higher_is_better=False)))
    lines.append(_row(loc, "current_ratio", _fmt_ratio(subject.current_ratio), dm("current_ratio")))
    lines.append(_row(loc, "roe", _fmt_pct(subject.roe), dm("roe")))
    lines.append(_row(loc, "roic_proxy", _fmt_pct(subject.roic_proxy), dm("roic_proxy")))
    lines.append(_row(loc, "payout_ratio", _fmt_pct(subject.payout_ratio)))
    lines.append("")

    # Layer 5
    lines.append(f"## {loc['layer5_title']}")
    lines.append("")
    _table_header(loc["col_signal"])
    upside = None
    if subject.price and subject.target_median:
        upside = (subject.target_median - subject.price) / subject.price
    target_val = _fmt_num(subject.target_median)
    if upside is not None:
        target_val += f"  ({_fmt_pct(upside)} {loc['vs_price']})"
    lines.append(_row(loc, "target_median", target_val))
    rec_val = f"{subject.recommendation_key or 'n/a'} ({_fmt_ratio(subject.recommendation_mean)})"
    lines.append(_row(loc, "recommendation", rec_val))
    lines.append(_row(loc, "insider_pct", _fmt_pct(subject.insider_pct)))
    lines.append(_row(loc, "institution_pct", _fmt_pct(subject.institution_pct)))
    lines.append(_row(loc, "shares_short_pct", _fmt_pct(subject.shares_short_pct)))
    lines.append("")

    # Three-signal bottom line
    lines.append(f"## {loc['three_signal_title']}")
    lines.append("")
    lines.append(loc["three_signal_intro"])
    lines.append("")

    fcf = subject.free_cash_flow
    if fcf is None:
        fcf_status = loc["fcf_unknown"]
    elif fcf > 0:
        fcf_status = loc["fcf_positive"].format(v=_fmt_num(fcf))
    else:
        fcf_status = loc["fcf_negative"].format(v=_fmt_num(fcf))
    lines.append(f"1. {loc['signal1'].format(status=fcf_status)}")

    growth = subject.revenue_growth_yoy
    if growth is None:
        growth_msg = ""
    elif growth > 0.05:
        growth_msg = loc["growth_grow"].format(p=_fmt_pct(growth))
    elif growth > -0.02:
        growth_msg = loc["growth_flat"].format(p=_fmt_pct(growth))
    else:
        growth_msg = loc["growth_shrink"].format(p=_fmt_pct(growth))
    lines.append(f"2. {loc['signal2'].format(msg=growth_msg)}")

    roic = subject.roic_proxy
    if roic is None:
        roic_msg = ""
    elif roic > 0.10:
        roic_msg = loc["roic_good"].format(p=_fmt_pct(roic))
    else:
        roic_msg = loc["roic_bad"].format(p=_fmt_pct(roic))
    lines.append(f"3. {loc['signal3'].format(msg=roic_msg)}")
    lines.append("")
    lines.append(loc["signal_outro"])
    lines.append("")

    # Prompt templates
    lines.append(f"## {loc['prompts_title']}")
    lines.append("")
    lines.append(loc["prompts_intro"])
    lines.append("")
    lines.append(f"- {loc['prompt_1'].format(ticker=subject.ticker)}")
    lines.append(f"- {loc['prompt_2'].format(ticker=subject.ticker)}")
    lines.append(f"- {loc['prompt_3'].format(ticker=subject.ticker, roic=_fmt_pct(subject.roic_proxy))}")
    lines.append("")

    return "\n".join(lines) + "\n"


_FMTS = {
    "num": _fmt_num,
    "pct": _fmt_pct,
    "ratio": _fmt_ratio,
    "str": lambda x: (x if isinstance(x, str) and x else "n/a"),
}


def render_compare(snaps: list[Snapshot], lang: str = "en") -> str:
    if len(snaps) < 2:
        return render_markdown(snaps[0], peers=[], lang=lang)

    loc = LOCALES[lang]

    tickers = " | ".join(f"**{s.ticker}**" for s in snaps)
    sep = " | ".join("---" for _ in snaps)

    L: list[str] = []
    L.append(f"# {loc['compare_title'].format(tickers=', '.join(s.ticker for s in snaps))}")
    L.append("")
    L.append(loc["generated"].format(ts=datetime.now().strftime("%Y-%m-%d %H:%M")))
    L.append("")
    L.append(loc["disclaimer"])
    L.append("")
    L.append(f"| {loc['compare_metric']} | {tickers} |")
    L.append(f"|---|{sep}|")

    for label, attr, kind in loc["compare_rows"]:
        fmt = _FMTS[kind]
        cells = " | ".join(fmt(getattr(s, attr)) for s in snaps)
        L.append(f"| {label} | {cells} |")
    L.append("")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tickers", nargs="+", help="Ticker(s), e.g. NVDA AMD")
    ap.add_argument("--peers", help="Comma-separated peer tickers, or 'auto' for a curated set")
    ap.add_argument("--compare", action="store_true", help="Side-by-side comparison of all positional tickers")
    ap.add_argument("--lang", choices=sorted(LOCALES.keys()), default="en",
                    help="Report language (en, he). Hebrew renders RTL and keeps English financial terms in Latin.")
    ap.add_argument("--md", help="Write markdown report to this path (also printed to stdout)")
    ap.add_argument("--json", help="Write raw snapshot(s) as JSON to this path")
    args = ap.parse_args()

    snaps = [load_snapshot(t) for t in args.tickers]

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump([asdict(s) for s in snaps], f, indent=2, default=str)

    if args.compare and len(snaps) > 1:
        out = render_compare(snaps, lang=args.lang)
    else:
        subject = snaps[0]
        peer_syms = resolve_peers(subject.ticker, args.peers)
        peers = [load_snapshot(p) for p in peer_syms] if peer_syms else []
        out = render_markdown(subject, peers, lang=args.lang)

    if args.md:
        with open(args.md, "w", encoding="utf-8") as f:
            f.write(out)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
