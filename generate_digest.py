#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
מחפש מודעות מפייסבוק ופלטפורמות נוספות, מייצר דף HTML, שולח מייל.
"""

import anthropic
import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── הגדרות ──────────────────────────────────────────────────────────────────
RECIPIENT_EMAIL = "mirit.tc@gmail.com"
SENDER_EMAIL    = "miritronicohen@gmail.com"
SITE_URL        = "https://mirittc-prog.github.io/rent-ramat-gan"

SEARCH_QUERIES = [
    '"דירה להשכרה רמת גן" site:facebook.com',
    '"דירות להשכרה ברמת גן" facebook',
    '"להשכרה רמת גן" facebook קבוצה שכירות',
    '"שכירות רמת גן" facebook 2025 OR 2026',
    'rent apartment "Ramat Gan" facebook group',
    '"דירה" OR "חדר" "רמת גן" "להשכרה" facebook',
]

DIGEST_TITLE = "🏠 דירות להשכרה ברמת גן"
# ────────────────────────────────────────────────────────────────────────────

HEBREW_MONTHS = [
    "ינואר","פברואר","מרץ","אפריל","מאי","יוני",
    "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"
]

def get_date_str():
    now = datetime.now()
    return f"{now.day} ב{HEBREW_MONTHS[now.month-1]} {now.year}"

def get_issue_number():
    now = datetime.now()
    base = datetime(2026, 3, 15)
    return max(1, (now - base).days + 1)


def generate_html(client, date_str, issue):
    print("🔍 מחפש מודעות...")

    queries_formatted = "\n".join(f'{i+1}. {q}' for i, q in enumerate(SEARCH_QUERIES))

    prompt = f"""חפש ברשת מודעות להשכרת דירות ברמת גן מפייסבוק ופלטפורמות נוספות.
הרץ את החיפושים הבאים:
{queries_formatted}

לאחר החיפוש, צור עמוד HTML מלא ומושלם בעברית עם כל המודעות שמצאת.

דרישות עיצוב:
- כיוון RTL, dir="rtl" lang="he", כל הטקסט בעברית
- רקע כהה: #0d0d14, כרטיסים: #1e1e2e עם גבול #2a2a3e
- צבע ראשי: #4a9eff (כחול), משני: #e94560 (אדום)
- Navbar דביק עם הכותרת "{DIGEST_TITLE}" + {date_str}
- Hero section עם סטטיסטיקות (מספר מודעות, טווח מחירים)
- טאבים לפילטור: הכל / חדרים 1-2 / 3-4 חדרים / 5+ חדרים
- כרטיסים מגיבים למובייל
- כל CSS ו-JS מוטמעים בקובץ אחד

לכל מודעה שמצאת, צור כרטיס עם:
- כותרת (קישור ישיר למודעה המקורית — חובה!)
- תגיות: מחיר בש"ח, מספר חדרים, שכונה ברמת גן (אם ידוע)
- תיאור קצר 1-2 משפטים
- כפתור "לצפייה במודעה ←" המקשר ישירות לפוסט/מודעה
- תגית "🆕 חדש!" אם המודעה מהשבוע האחרון

אם לא נמצאו מודעות ספציפיות, הצג הסבר ידידותי + קישורים ישירים לקבוצות הפייסבוק הרלוונטיות ולחיפוש ביד2/מדלן.

מבנה הדף:
1. Navbar: "{DIGEST_TITLE}" + {date_str} (sticky)
2. Hero: כותרת, עדכון #{issue}, סטטיסטיקות
3. טאבים לפילטור לפי מספר חדרים
4. כרטיסי מודעות
5. Footer: "נוצר אוטומטית על ידי Claude · {date_str}"

החזר אך ורק HTML מלא מ-<!DOCTYPE html> עד </html>, ללא שום טקסט אחר."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}]
    )

    html = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            html += block.text

    if "<!DOCTYPE" in html:
        start = html.find("<!DOCTYPE")
        end = html.rfind("</html>") + 7
        if end > start:
            html = html[start:end]

    if "<!DOCTYPE" not in html or "</html>" not in html:
        print(f"❌ לא נוצר HTML תקין\nתצוגה מקדימה: {html[:300]}")
        sys.exit(1)

    return html


def send_notification_email(date_str, issue, app_password):
    print("📧 שולח מייל...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 עדכון #{issue} — דירות להשכרה ברמת גן · {date_str}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    html_body = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;direction:rtl;">
  <div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">
    <div style="background:linear-gradient(135deg,#0d0d14,#0f3460);padding:32px;text-align:center;">
      <div style="font-size:36px;margin-bottom:8px;">🏠</div>
      <h1 style="color:#4a9eff;margin:0;font-size:20px;">דירות להשכרה ברמת גן</h1>
      <p style="color:#aaa;margin:6px 0 0;font-size:13px;">עדכון יומי · {date_str}</p>
    </div>
    <div style="padding:28px 32px;">
      <p style="font-size:16px;color:#333;line-height:1.6;">היי מירית! 👋</p>
      <p style="font-size:15px;color:#555;line-height:1.7;">
        עדכון המודעות היומי שלך מוכן —<br>
        דירות להשכרה ברמת גן מפייסבוק ומפלטפורמות נוספות.
      </p>
      <div style="text-align:center;margin:28px 0;">
        <a href="{SITE_URL}" style="background:#4a9eff;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;">
          לצפייה במודעות ←
        </a>
      </div>
      <p style="font-size:13px;color:#999;border-top:1px solid #eee;padding-top:16px;margin-top:8px;">
        נשלח אוטומטית על ידי Claude · {date_str}<br>
        <a href="{SITE_URL}" style="color:#4a9eff;">{SITE_URL}</a>
      </p>
    </div>
  </div>
</body>
</html>"""

    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(SENDER_EMAIL, app_password)
        server.send_message(msg)

    print(f"✅ מייל נשלח אל {RECIPIENT_EMAIL}")


def main():
    api_key      = os.environ.get("ANTHROPIC_API_KEY")
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace('\xa0', '').replace(' ', '').strip()

    if not api_key:
        print("❌ ANTHROPIC_API_KEY לא מוגדר")
        sys.exit(1)
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD לא מוגדר")
        sys.exit(1)

    client   = anthropic.Anthropic(api_key=api_key)
    date_str = get_date_str()
    issue    = get_issue_number()

    print(f"📅 מייצר עדכון — {date_str} (עדכון #{issue})")

    html = generate_html(client, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים)")

    send_notification_email(date_str, issue, app_password)


if __name__ == "__main__":
    main()
