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


def generate_html_with_search(client, date_str, issue):
    """מחפש מודעות ומייצר HTML בקריאה אחת עם web_search."""
    print("🔍 מחפש מודעות ומייצר דף HTML...")

    prompt = f"""You have access to web search. Search for rental apartments in Ramat Gan, Israel.

Search for:
1. "דירות להשכרה רמת גן" yad2 OR madlan
2. yad2.co.il apartments rent "רמת גן" 2026
3. madlan.co.il דירות להשכרה רמת גן
4. facebook.com "דירות להשכרה" "רמת גן" 2026
5. "להשכרה רמת גן" פייסבוק קבוצה דירה חדרים

Collect all rental listings you find. Then create a complete Hebrew HTML page.

Page requirements:
- Full RTL HTML page, dir="rtl" lang="he"
- Dark background: #0d0d14, cards: #1e1e2e with border #2a2a3e
- Primary color: #4a9eff (blue), accent: #e94560 (red)
- Sticky navbar: "{DIGEST_TITLE}" + {date_str}
- Hero section: title "דירות להשכרה ברמת גן", issue #{issue}, stats (count, price range, average)
- Filter tabs: הכל / 1-2 חדרים / 3-4 חדרים / 5+ חדרים
- Mobile-responsive cards
- All CSS and JS embedded in one file

For each listing found, create a card with:
- Title + address (direct link to listing — use actual URL from search results)
- Tags: price, rooms, floor (if available), sqm (if available)
- Button "לצפייה במודעה ←" with href to listing
- Badge "🆕 חדש!" if published today or yesterday

Page structure:
1. Navbar (sticky)
2. Hero with stats
3. Filter tabs
4. Listing cards sorted by date (newest first)
5. Footer: "מקור: יד2 · מדלן · פייסבוק · נוצר אוטומטית על ידי Claude · {date_str}"

If you find NO listings, show a friendly message with links to:
- https://www.yad2.co.il/realestate/rent?city=8600
- https://www.madlan.co.il/for-rent/רמת-גן

Return ONLY complete HTML from <!DOCTYPE html> to </html>, no other text."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": prompt}]
    )

    html = ""
    listing_count = 0
    for block in response.content:
        if hasattr(block, "text") and block.text:
            text = block.text
            if "<!DOCTYPE" in text:
                start = text.find("<!DOCTYPE")
                end   = text.rfind("</html>") + 7
                if end > start:
                    html = text[start:end]

    if not html or "<!DOCTYPE" not in html:
        print(f"❌ לא נוצר HTML תקין")
        sys.exit(1)

    # ספור כרטיסים כדי לדווח בנושא המייל
    listing_count = html.count('לצפייה במודעה')
    print(f"✅ HTML נוצר עם ~{listing_count} מודעות")
    return html, listing_count


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

    # 1. חיפוש + ייצור HTML בקריאה אחת
    html, listing_count = generate_html_with_search(client, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים)")

    # 2. שליחת מייל
    send_notification_email(date_str, issue, listing_count, app_password)


if __name__ == "__main__":
    main()
