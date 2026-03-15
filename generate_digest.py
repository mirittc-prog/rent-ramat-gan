#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
שולף מודעות ישירות מ-API של יד2, מייצר דף HTML, שולח מייל.
"""

import anthropic
import os
import sys
import json
import smtplib
import requests
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


def _try_fetch_url(url, params, timeout):
    """מבצע בקשה ומחזיר JSON, או None אם נכשל."""
    try:
        resp = requests.get(url, params=params, headers=YAD2_HEADERS, timeout=timeout)
        resp.raise_for_status()
        text = resp.text.strip()
        if not text:
            print(f"  ↳ נכשל: תשובה ריקה מהשרת")
            return None
        if not text.startswith("{") and not text.startswith("["):
            print(f"  ↳ תשובה לא-JSON (ראשית): {text[:200]}")
            return None
        return resp.json()
    except requests.RequestException as e:
        print(f"  ↳ נכשל: {e}")
        return None
    except ValueError as e:
        print(f"  ↳ נכשל לפרסר JSON: {e}")
        return None


def fetch_yad2_listings():
    """שולף מודעות להשכרה ברמת גן — מנסה מספר נתיבי API ו-ScraperAPI."""
    scraper_key = os.environ.get("SCRAPER_API_KEY", "").strip()
    print(f"🏠 שולף מודעות מיד2... (ScraperAPI: {'כן' if scraper_key else 'לא'})")

    # רשימת נתיבי API לניסיון — מהחדש לישן
    candidate_paths = [
        f"https://gw.yad2.co.il/realestate-3/search?propertyGroup=apartments&dealType=2&city={CITY_CODE}",
        f"https://gw.yad2.co.il/realestate-3/feed?propertyGroup=apartments&dealType=2&city={CITY_CODE}",
        f"https://gw.yad2.co.il/feed-search-legacy/realestate/rent?city={CITY_CODE}&propertyGroup=apartments&dealType=2",
        f"https://gw.yad2.co.il/feed-search-legacy/realestate/rent?city={CITY_CODE}",
        f"https://gw.yad2.co.il/realestate/rent?city={CITY_CODE}&propertyGroup=apartments",
    ]

    data = None
    for yad2_url in candidate_paths:
        for render_mode in (["false", "true"] if scraper_key else [None]):
            print(f"  ⤷ מנסה: {yad2_url} (render={render_mode})")
            if scraper_key:
                url = "http://api.scraperapi.com"
                params = {"api_key": scraper_key, "url": yad2_url, "render": render_mode}
                timeout = 60
            else:
                url, params, timeout = yad2_url, {}, 20

            data = _try_fetch_url(url, params, timeout)
            if data:
                print(f"  ✅ הצליח!")
                break
        if data:
            break

    if not data:
        print("⚠️ כל נתיבי יד2 נכשלו. מחזיר רשימה ריקה.")
        return []

    # — debug: הדפסת מבנה ה-JSON (3 רמות ראשונות) —
    def _preview(obj, depth=0):
        if depth > 2:
            return "..."
        if isinstance(obj, dict):
            return {k: _preview(v, depth+1) for k, v in list(obj.items())[:5]}
        if isinstance(obj, list):
            return [_preview(obj[0], depth+1)] if obj else []
        return obj
    print(f"  📦 מבנה JSON: {json.dumps(_preview(data), ensure_ascii=False)}")

    listings = []

    # נסה נתיבים שונים לרשימת המודעות
    feed_items = (
        data.get("data", {}).get("feed", {}).get("feed_items")
        or data.get("data", {}).get("feed_items")
        or data.get("feed_items")
        or data.get("data", {}).get("items")
        or data.get("items")
        or []
    )

    print(f"  🔢 סה\"כ פריטים ב-feed: {len(feed_items)}")

    for item in feed_items:
        if item.get("type") not in ("ad", "listing", None):
            continue

        item_id = item.get("id", "") or item.get("token", "")
        price   = item.get("price", "")
        rooms   = item.get("rooms", "")
        street  = item.get("street", "")
        hood    = item.get("neighborhood", "")
        floor   = item.get("floor", "")
        sqm     = item.get("square_meters", "") or item.get("squareMeter", "")
        date    = item.get("date", "") or item.get("updated_at", "")
        title   = item.get("title", "")
        row2    = item.get("row2", "")

        address = " ".join(filter(None, [street, hood]))
        link    = f"https://www.yad2.co.il/item/{item_id}" if item_id else ""

        listings.append({
            "id":      item_id,
            "title":   title or row2 or address or "דירה להשכרה",
            "price":   f"₪{price:,}" if isinstance(price, int) else (f"₪{price}" if price else "מחיר לא צוין"),
            "rooms":   str(rooms) if rooms else "לא צוין",
            "address": address or "רמת גן",
            "floor":   str(floor) if floor else "",
            "sqm":     str(sqm) if sqm else "",
            "date":    date,
            "link":    link,
        })

        if len(listings) >= MAX_LISTINGS:
            break

    print(f"✅ נמצאו {len(listings)} מודעות ביד2")
    return listings


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
    listings = fetch_yad2_listings()

    # 2. יצירת HTML עם Claude
    html = generate_html(client, listings, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים)")

    # 3. שליחת מייל
    send_notification_email(date_str, issue, len(listings), app_password)


if __name__ == "__main__":
    main()
