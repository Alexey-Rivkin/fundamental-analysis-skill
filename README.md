# fundamental-analysis-skill

Ask your AI agent to analyze a stock, get a full fundamental report back.

- **Layer 1 — Profitability:** revenue growth, gross/operating/net margin, EPS, EBITDA
- **Layer 2 — Valuation:** P/E, Forward P/E, P/S, EV/EBITDA, PEG, P/B
- **Layer 3 — Cash Flow:** OCF, FCF, FCF margin, FCF yield, quarterly trend
- **Layer 4 — Financial Health:** Debt/Equity, Net Cash, Current Ratio, ROE, ROIC
- **Layer 5 — Forward Signals:** analyst target, recommendation, insider %, short interest

Every ratio next to its peer-median. Three-signal bottom line (FCF, revenue
growth, ROIC vs WACC). English or Hebrew (RTL) output. Free — uses public
Yahoo Finance data, no API keys.

Works with **Claude Code**, **Codex CLI**, or any AI agent that reads
instruction files.

**Not financial advice.**

---

## Install

Copy-paste one line, hit Enter.

**macOS or Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/Alexey-Rivkin/fundamental-analysis-skill/main/install.sh | bash
```

**Windows** (PowerShell)
```powershell
irm https://raw.githubusercontent.com/Alexey-Rivkin/fundamental-analysis-skill/main/install.ps1 | iex
```

That's it. The installer figures out the rest:

- Installs `uv` (the Python runner) if you don't have it.
- Detects which AI agents you have (Claude Code, Codex CLI) and installs
  the skill for each.
- If you don't have either yet, installs into the Claude Code location so
  it's ready when you install Claude Code.
- Safe to re-run — updates the skill in place instead of re-cloning.

You need `git` on your machine. Everything else the installer handles.

---

## Use it

Open your AI agent and ask in plain language:

- **"analyze NVDA"**
- **"is AAPL overpriced"**
- **"compare NVDA and AMD on fundamentals"**
- **"ניתוח פנדמנטלי לאפל"** (Hebrew)

The agent runs the skill and hands you back the report.

If your agent doesn't pick it up automatically, tell it once:

> Use the skill at `~/.claude/skills/fundamental-analysis` (or
> `~/.codex/skills/fundamental-analysis` for Codex) to answer this.

---

## What you get

A markdown report with all five layers filled in, every number compared to
its peer-median, and a plain-English bottom line at the end:

> 1. **Free cash flow** — positive at $46.34B.
> 2. **Revenue growth** — 85.2% YoY. Growing.
> 3. **ROIC vs WACC** — 76.6%. Above a 10% cost-of-capital hurdle — value creator.

Followed by three ready-to-paste prompts you can hand to any other AI for
deeper follow-up questions.

---

## What it won't do

- Technical analysis (chart patterns, moving averages, RSI, etc.)
- Options, greeks, strategies
- Crypto
- News sentiment or "why did $X move today?"
- Non-US-listed stocks (data coverage is poor outside the US)
- Recommend buying or selling anything

---

## License

MIT. See `LICENSE`.
