#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
מחפש מודעות דרך Claude web search, מייצר דף HTML, שולח מייל.
"""

import anthropic
import os
import sys
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── הגדרות ──────────────────────────────────────────────────────────────────
RECIPIENT_EMAIL = "mirit.tc@gmail.com"
SENDER_EMAIL    = "miritronicohen@gmail.com"
SITE_URL        = "https://mirittc-prog.github.io/rent-ramat-gan"

DIGEST_TITLE    = "🏠 דירות להשכרה ברמת גן"
CITY_CODE       = 8600   # קוד עיר יד2 עבור רמת גן
MAX_LISTINGS    = 50     # מקסימום מודעות לשליפה
# ────────────────────────────────────────────────────────────────────────────

HEBREW_MONTHS = [
    "ינואר","פברואר","מרץ","אפריל","מאי","יוני",
    "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"
]

YAD2_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.yad2.co.il/realestate/rent",
    "Origin": "https://www.yad2.co.il",
    "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "Connection": "keep-alive",
}


def get_date_str():
    now = datetime.now()
    return f"{now.day} ב{HEBREW_MONTHS[now.month-1]} {now.year}"


def get_issue_number():
    now = datetime.now()
    base = datetime(2026, 3, 15)
    return max(1, (now - base).days + 1)


def fetch_yad2_listings(client):
    """שולף מודעות להשכרה ברמת גן דרך חיפוש אינטרנט של Claude."""
    print("🔍 מחפש מודעות ביד2 דרך חיפוש אינטרנט...")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
            messages=[{
                "role": "user",
                "content": (
                    "חפש דירות להשכרה ברמת גן ביד2 שפורסמו לאחרונה.\n"
                    "בצע מספר חיפושים:\n"
                    "1. yad2.co.il דירות להשכרה רמת גן\n"
                    "2. site:yad2.co.il/item להשכרה רמת גן\n\n"
                    "לכל מודעה שתמצא, אסוף את הפרטים הבאים.\n"
                    "בסוף החזר JSON array תקין בלבד (ללא טקסט נוסף) בפורמט:\n"
                    '[{"title":"...","price":5000,"rooms":3,"address":"...","floor":2,'
                    '"sqm":80,"date":"...","link":"https://www.yad2.co.il/item/..."}]'
                )
            }]
        )

        for block in response.content:
            if hasattr(block, "text") and block.text:
                text = block.text.strip()
                start = text.find("[")
                end   = text.rfind("]") + 1
                if start >= 0 and end > start:
                    try:
                        raw = json.loads(text[start:end])
                        listings = []
                        for item in raw:
                            price = item.get("price", "")
                            listings.append({
                                "id":      "",
                                "title":   item.get("title", "דירה להשכרה"),
                                "price":   f"₪{price:,}" if isinstance(price, int) else (f"₪{price}" if price else "מחיר לא צוין"),
                                "rooms":   str(item.get("rooms", "")) or "לא צוין",
                                "address": item.get("address", "רמת גן"),
                                "floor":   str(item.get("floor", "")) if item.get("floor") else "",
                                "sqm":     str(item.get("sqm", "")) if item.get("sqm") else "",
                                "date":    item.get("date", ""),
                                "link":    item.get("link", ""),
                            })
                            if len(listings) >= MAX_LISTINGS:
                                break
                        print(f"✅ נמצאו {len(listings)} מודעות")
                        return listings
                    except json.JSONDecodeError as e:
                        print(f"  ↳ שגיאת JSON: {e} | טקסט: {text[:200]}")

    except Exception as e:
        print(f"⚠️ שגיאה בחיפוש: {e}")

    print("⚠️ לא נמצאו מודעות")
    return []


def generate_html(client, listings, date_str, issue):
    print("🎨 מייצר דף HTML...")

    if listings:
        listings_text = json.dumps(listings, ensure_ascii=False, indent=2)
        data_section = f"נמצאו {len(listings)} מודעות ביד2. הנה הנתונים:\n{listings_text}"
    else:
        data_section = "לא נמצאו מודעות ביד2 כרגע. צור דף עם הסבר ידידותי וקישורים לחיפוש ידני."

    prompt = f"""צור עמוד HTML מלא ומושלם בעברית עבור דירות להשכרה ברמת גן.

{data_section}

דרישות עיצוב:
- כיוון RTL, dir="rtl" lang="he", כל הטקסט בעברית
- רקע כהה: #0d0d14, כרטיסים: #1e1e2e עם גבול #2a2a3e
- צבע ראשי: #4a9eff (כחול), משני: #e94560 (אדום)
- Navbar דביק: "{DIGEST_TITLE}" + {date_str}
- Hero section: כותרת, עדכון #{issue}, סטטיסטיקות (מספר מודעות, טווח מחירים, ממוצע)
- טאבים לפילטור: הכל / 1-2 חדרים / 3-4 חדרים / 5+ חדרים
- כרטיסים מגיבים למובייל
- כל CSS ו-JS מוטמעים בקובץ אחד

לכל מודעה צור כרטיס עם:
- כותרת + כתובת (קישור ישיר לדף המודעה ביד2 — חובה! השתמש ב-link מהנתונים)
- תגיות: מחיר, מספר חדרים, קומה (אם יש), שטח במ"ר (אם יש)
- כפתור "לצפייה במודעה ←" עם href לקישור
- תגית "🆕 חדש!" אם המודעה מהיום או אתמול

מבנה:
1. Navbar (sticky)
2. Hero עם סטטיסטיקות
3. טאבים
4. כרטיסי מודעות ממוינים לפי תאריך (חדש ראשון)
5. Footer: "מקור: יד2 · נוצר אוטומטית על ידי Claude · {date_str}"

החזר אך ורק HTML מלא מ-<!DOCTYPE html> עד </html>, ללא שום טקסט אחר."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )

    html = response.content[0].text if response.content else ""

    if "<!DOCTYPE" in html:
        start = html.find("<!DOCTYPE")
        end   = html.rfind("</html>") + 7
        if end > start:
            html = html[start:end]

    if "<!DOCTYPE" not in html or "</html>" not in html:
        print(f"❌ לא נוצר HTML תקין\nתצוגה מקדימה: {html[:300]}")
        sys.exit(1)

    return html


def send_notification_email(date_str, issue, listing_count, app_password):
    print("📧 שולח מייל...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {listing_count} דירות להשכרה ברמת גן · {date_str}"
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
        נמצאו <strong style="color:#4a9eff;">{listing_count} מודעות</strong> להשכרה ברמת גן ביד2 היום.
      </p>
      <div style="text-align:center;margin:28px 0;">
        <a href="{SITE_URL}" style="background:#4a9eff;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;">
          לצפייה בכל המודעות ←
        </a>
      </div>
      <p style="font-size:13px;color:#999;border-top:1px solid #eee;padding-top:16px;margin-top:8px;">
        מקור: יד2 · נשלח אוטומטית על ידי Claude · {date_str}<br>
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
    api_key      = os.environ.get("ANTHROPIC_API_KEY", "").strip()
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

    # 1. שליפת מודעות מיד2
    listings = fetch_yad2_listings(client)

    # 2. יצירת HTML עם Claude
    html = generate_html(client, listings, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים)")

    # 3. שליחת מייל
    send_notification_email(date_str, issue, len(listings), app_password)


if __name__ == "__main__":
    main()
