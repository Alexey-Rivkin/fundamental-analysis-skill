<div dir="rtl">

# fundamental-analysis-skill

[English](README.md) · **עברית**

בקשו מהסוכן ה-AI שלכם לנתח מניה, וקבלו דו״ח ניתוח פנדמנטלי מלא.

- **שכבה 1 — רווחיות (Profitability):** קצב גידול הכנסות, שולי רווח גולמיים/אופרטיביים/נקיים, EPS, EBITDA
- **שכבה 2 — הערכת שווי (Valuation):** P/E, Forward P/E, P/S, EV/EBITDA, PEG, P/B
- **שכבה 3 — תזרים מזומנים (Cash Flow):** OCF, FCF, FCF Margin, FCF Yield, מגמה רבעונית
- **שכבה 4 — איתנות פיננסית:** Debt/Equity, Net Cash, Current Ratio, ROE, ROIC
- **שכבה 5 — סימני עתיד:** יעדי אנליסטים, המלצה, אחזקות אינסיידרים, שורט

כל יחס מוצג לצד חציון קבוצת ההשוואה. סיכום שלושת הסימנים בסוף (FCF, קצב גידול הכנסות, ROIC מול WACC). פלט באנגלית או בעברית (RTL). בחינם — נתונים מ-Yahoo Finance, בלי מפתחות API.

עובד עם **Claude Code**, **Codex CLI**, וכל סוכן AI שקורא קבצי הוראות.

**אינו ייעוץ פיננסי.**

---

## התקנה

מעתיקים שורה אחת ולוחצים Enter.

<div dir="ltr">

**macOS או Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/Alexey-Rivkin/fundamental-analysis-skill/main/install.sh | bash
```

**Windows** (PowerShell)
```powershell
irm https://raw.githubusercontent.com/Alexey-Rivkin/fundamental-analysis-skill/main/install.ps1 | iex
```

</div>

זהו. המתקין דואג לכל השאר:

- מתקין את `uv` (מריץ ה-Python) אם אין לכם.
- מזהה אילו סוכני AI מותקנים אצלכם (Claude Code, Codex CLI) ומתקין עבור כל אחד.
- אם אין לכם עדיין אף אחד — מתקין במיקום של Claude Code, כדי שיהיה מוכן כשתתקינו.
- בטוח להריץ שוב — מעדכן במקום במקום להתחיל מחדש.

צריך שיהיה `git` על המחשב. את השאר המתקין מטפל.

---

## שימוש

פתחו את סוכן ה-AI שלכם ושאלו בשפה חופשית:

- **"analyze NVDA"**
- **"is AAPL overpriced"**
- **"compare NVDA and AMD on fundamentals"**
- **"ניתוח פנדמנטלי לאפל"**

הסוכן מריץ את הסקיל ומחזיר לכם את הדו״ח.

אם הסוכן לא מזהה את הסקיל אוטומטית, כתבו לו פעם אחת:

> השתמש בסקיל שנמצא ב-`~/.claude/skills/fundamental-analysis` (או ב-`~/.codex/skills/fundamental-analysis` ל-Codex) כדי לענות.

---

## מה מקבלים

דו״ח Markdown עם כל חמש השכבות, כשכל מספר מושווה לחציון קבוצת ההשוואה, ובסוף — סיכום בעברית פשוטה:

<div dir="ltr">

> 1. **Free Cash Flow** — חיובי, $46.34B.
> 2. **קצב גידול הכנסות** — 85.2% YoY. גדל.
> 3. **ROIC מול WACC** — 76.6%. מעל רף עלות הון של 10% — יוצר ערך.

</div>

מיד אחרי הסיכום — שלוש תבניות פרומפט מוכנות להעתקה שאפשר להעביר לכל AI לניתוח מעמיק.

---

## מה הסקיל לא עושה

- ניתוח טכני (תבניות גרפים, ממוצעים נעים, RSI וכו׳)
- אופציות, יוונים, אסטרטגיות
- קריפטו
- ניתוח סנטימנט / חדשות / "למה $X עלה היום?"
- מניות שלא רשומות בארה״ב (הכיסוי של Yahoo מחוץ לארה״ב חלש)
- לא ייתן המלצת קנייה או מכירה

---

## רישיון

MIT. ראו את קובץ `LICENSE`.

</div>
