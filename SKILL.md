---
name: fundamental-analysis
description: Produce a structured fundamental-analysis report on a US-listed stock (or side-by-side comparison of several tickers) using a five-layer KPI framework — Profitability, Valuation, Cash Flow, Financial Health, Forward Signals. Trigger on requests like "analyze NVDA", "fundamentals on X", "value $Y", "is $Z overpriced", "compare AMD vs NVDA on fundamentals", "run a stock screen on my watchlist", "give me a fundamental take on <ticker>", or Hebrew equivalents ("נתח את NVDA", "ניתוח פנדמנטלי ל-X"). Uses yfinance for the raw numbers; every ratio is reported next to its peer-median, because the rule is "never absolute, always relative". English and Hebrew (RTL) output via `--lang en|he`. Outputs a markdown report plus a three-signal bottom line (FCF, revenue growth, ROIC vs WACC). Not for pure technical analysis, options, crypto, or news-sentiment questions.
---

# Fundamental Analysis (5-Layer KPI Framework)

## What this skill does

Runs a fundamental analysis on one or more US-listed stocks and produces a
markdown report grouped by the five-layer KPI framework. Every ratio is
compared to a peer median (curated peer set per ticker, or user-supplied).

The output includes:

- **Layer 0** — company-familiarity checklist (human-only, the one thing AI
  cannot do)
- **Layer 1** — Profitability (revenue growth, gross/operating/net margins,
  EPS, EBITDA)
- **Layer 2** — Valuation (P/E trailing + forward, P/S, EV/EBITDA, PEG, P/B)
- **Layer 3** — Cash Flow (OCF, FCF, FCF margin, FCF yield, quarterly trend)
- **Layer 4** — Financial Health (Debt/Equity, Net Cash, Current Ratio, ROE,
  ROIC-proxy, payout)
- **Layer 5** — Forward Signals (analyst targets, recommendation, insider %,
  institutional %, short interest)
- **Three-signal bottom line** — FCF present? revenue growth direction? ROIC
  vs a 10% WACC hurdle?
- **Prompt-engineering templates** — the three questions the user should ask
  a downstream LLM about this ticker (never "is X good?" — always structured
  KPI-referencing questions)

## When to trigger

Fire on any of:

- "analyze <TICKER>", "fundamental analysis of X", "run fundamentals on X"
- "value $X", "is $Y a buy", "is $Z overpriced"
- "compare $A vs $B on fundamentals"
- "run a stock screen on my watchlist" (implies multiple tickers → `--compare`)
- "give me a fundamental take on <ticker>"
- Any question that references profitability, margins, P/E, FCF, ROIC, PEG,
  or the KPI framework and names one or more US-listed stocks

**Don't fire on**:

- Pure technical-analysis / chart-pattern questions (moving averages, support
  levels, RSI, candlestick patterns) — this skill is fundamentals only.
- Options / greeks / strategies.
- Crypto (yfinance data is unreliable there and the framework was built for
  equity earnings).
- News-sentiment or "why did $X move today?" questions.
- Non-US listings — yfinance coverage of foreign tickers is spotty.

## Setup

Only requirement: [`uv`](https://docs.astral.sh/uv/) on `PATH`. The yfinance
dep is pulled per-invocation, no persistent venv, no system-Python touch.

- macOS: `brew install uv`
- Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`

No API keys. `<skill-dir>` in every command below is the directory this
`SKILL.md` sits in — resolve it however your platform names paths (e.g.
`~/.claude/skills/fundamental-analysis` on macOS/Linux under Claude Code,
`%USERPROFILE%\.claude\skills\fundamental-analysis` on Windows).

## Usage patterns

### Single-ticker deep dive

```bash
uv run --quiet --with yfinance \
  python <skill-dir>/scripts/analyze.py NVDA --peers auto
```

`--peers auto` pulls a curated 4-name peer set for the common mega-caps
(NVDA → AMD/AVGO/INTC/QCOM, AAPL → MSFT/GOOGL/META/AMZN, etc). If the
ticker isn't in the curated table, pass `--peers TICK1,TICK2,TICK3` yourself.
If no peers are given at all, the report still generates but all the
comparison cells collapse — worth flagging that to the user.

### Side-by-side comparison

```bash
uv run --quiet --with yfinance \
  python <skill-dir>/scripts/analyze.py \
  NVDA AMD AVGO --compare
```

Emits one wide markdown table with every KPI as a row and each ticker as a
column. Skips the Layer-0 human-checklist and prompt templates — the
compare view is for numeric side-by-side, not for a deep dive.

### Hebrew (RTL) output

```bash
uv run --quiet --with yfinance \
  python <skill-dir>/scripts/analyze.py \
  NVDA --peers auto --lang he
```

Sections, table headers, disclaimer, and prose are Hebrew and render RTL
in any Markdown viewer that respects the language of a document. Financial
terms (Revenue, EBITDA, Free Cash Flow, PEG, EV/EBITDA, Buy Back, Insider,
etc.) stay in Latin because that is how the market documents them and how
Israeli traders read them in practice. The three prompt-templates at
the end of the report stay in English so they can be pasted straight into
Perplexity Finance / Claude / GPT without re-translation.

The report file is UTF-8; when writing to `--md` the file will render RTL
correctly in any editor that honours the Hebrew characters (VS Code,
Obsidian, GitHub's preview, etc.).

### Write to a file

Add `--md report.md` to also write the markdown to disk (still printed
to stdout).

Add `--json out.json` to dump the raw snapshot objects — useful when the
user asks for follow-up analysis on specific fields.

## Framework rules (apply to how you present output)

1. **Never absolute, always relative.** Any metric quoted without a peer
   median is nearly useless. If the user asks about a single ticker,
   default to `--peers auto` unless they explicitly said "no peers".
2. **Forward > trailing.** Forward P/E and forward EPS are what price is
   really tracking. When both are shown, lead with the forward number.
3. **Cash flow beats accounting earnings.** Net income can be dressed up.
   FCF cannot easily be. When there's a large gap between net margin and
   FCF margin, flag it.
4. **Growth stocks earn a PEG.** For a company growing revenue >20% YoY,
   report the PEG prominently. PEG < 1 = potentially undervalued for its
   growth; > 2 = expensive even for growth.
5. **The three-signal summary is what the reader will actually remember.**
   Always end with FCF status, revenue growth direction, and ROIC vs a 10%
   cost-of-capital hurdle. The rest is context.
6. **Never issue a buy/sell recommendation.** The disclaimer is not
   decoration. Even if the peer-median comparison is overwhelmingly
   favourable, do not say "buy X" — say "the numbers profile as [rich cash,
   growing, capital-efficient, expensive on price/book]" and let the user
   decide.

## Prompt-engineering handoff

The framework's core teaching is that AI is a bad general-purpose oracle
but a very good structured-KPI answerer. The report ends with three
template questions the user can hand to any AI (Perplexity Finance, Claude,
GPT) to get a follow-on answer. If the user asks you to run those follow-ons
directly, use WebFetch or a similar tool — do not re-run the yfinance script
for them, since the follow-up needs sector data yfinance doesn't have.

## Known gaps to tell the user about

- **yfinance data is often stale by 15-30 minutes for the price and up to a
  full trading day for the fundamentals.** Any report timestamped inside
  Yahoo's overnight window may pick up yesterday's close as "current price".
  For actionable decisions, tell the user to verify at
  https://finance.yahoo.com/quote/<TICKER>.
- **`Ticker.info` sometimes returns partial payloads on rate-limit or
  weekend runs.** Cells that come back as `n/a` are missing data, not
  meaningful zeros. Never make a claim about a missing field.
- **ROIC is a proxy.** True ROIC uses NOPAT (net operating profit after
  tax). This script uses net income / (debt + equity) — close enough to
  compare a stock to its sector, but the absolute value drifts a few
  hundred bps from a rigorous calc. Flag that if the user is doing
  precision work.
- **Peer sets are curated for ~10 mega-caps.** For anything else, the user
  must supply `--peers TICK1,TICK2,TICK3`. When you ask them for peers,
  suggest sector ETF constituents (XLK top-10, XLF top-10, etc) rather
  than asking cold.
- **Cash flow signs** — a negative FCF isn't a bug; it means the company is
  investing more than it earns (Tesla for years, AMZN early days). Frame
  it neutrally.

## What NOT to do

- **Don't hallucinate peer medians.** If the `--peers` set fails to load or
  is empty, the comparison cells collapse — do not fill them in from memory.
- **Don't quote a target price as a fact.** Analyst targets are consensus
  guesses; report them as "analyst consensus target = $X" not "the stock
  is worth $X".
- **Don't extrapolate the quarterly FCF trend into a prediction.** Show the
  6 quarters, note the direction, stop.
- **Don't answer questions this skill isn't scoped for.** If the user
  pivots to "should I sell now?" or "what's the technical picture?", say
  the skill can't answer that and offer to hand it back to a human or a
  different tool.

## File layout

```
<skill-dir>/
├── SKILL.md              # this file
└── scripts/
    └── analyze.py        # yfinance loader + markdown renderer
```

