#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
שני שלבים: 1) חיפוש מודעות  2) ייצור HTML + שליחת מייל
"""

import anthropic
import json
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
DIGEST_TITLE    = "דירות להשכרה ברמת גן"

FB_GROUPS = [
    ("1870209196564360", "קבוצת דירות להשכרה ברמת גן"),
    ("1424244737803677", "קבוצת דירות רמת גן"),
    ("647901439404148",  "קבוצת שכירות רמת גן"),
    ("253957624766723",  "קבוצת דירות להשכרה גוש דן"),
    ("1774413905909921", "קבוצת דירות רמת גן והסביבה"),
]
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


def search_listings(client):
    """שלב 1: חיפוש מודעות, מחזיר רשימת JSON."""
    print("🔍 מחפש מודעות (30 הימים האחרונים)...")

    searches = "\n".join(
        f"{i+1}. site:facebook.com/groups/{gid} דירה חדרים שקל"
        for i, (gid, _) in enumerate(FB_GROUPS)
    )
    searches += "\n6. madlan.co.il רמת גן דירה להשכרה"
    searches += "\n7. homeless.co.il דירה להשכרה רמת גן"

    prompt = (
        "You have access to web search. Find rental apartment listings in Ramat Gan, Israel "
        "published in the last 30 days only.\n\n"
        f"Run ALL these searches:\n{searches}\n\n"
        "Rules:\n"
        "- Only listings from the last 30 days.\n"
        "- Only include listings with a DIRECT URL to the specific post/listing page.\n"
        "- Do NOT fabricate URLs. Only use URLs from search results.\n"
        "- Extract: title, price (number in ILS), rooms (number), address, date (YYYY-MM-DD), "
        "source (facebook/madlan/homeless), link.\n\n"
        "Return ONLY a valid JSON array. No explanations. Example:\n"
        '[{"title":"3 חדרים ברמת גן","price":6500,"rooms":3,"address":"רח\' ביאליק 5",'
        '"date":"2026-03-10","source":"facebook","link":"https://www.facebook.com/groups/.../posts/..."}]'
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": prompt}]
    )

    for block in response.content:
        if hasattr(block, "text") and block.text:
            text = block.text.strip()
            start = text.find("[")
            end   = text.rfind("]") + 1
            if start >= 0 and end > start:
                try:
                    listings = json.loads(text[start:end])
                    print(f"  נמצאו {len(listings)} מודעות")
                    return listings
                except Exception:
                    pass

    print("  נמצאו 0 מודעות")
    return []


def generate_html(client, listings, date_str, issue):
    """שלב 2: ייצור HTML מהמודעות שנמצאו."""
    print("🎨 מייצר דף HTML...")

    # קבוצות פייסבוק — קבועות
    fb_cards_html = "".join(
        f'<div class="card fb-card" data-source="facebook">'
        f'<div class="badges"><span class="badge src-fb">🔵 פייסבוק</span></div>'
        f'<div class="card-title">{name}</div>'
        f'<a href="https://www.facebook.com/groups/{gid}/?sorting_setting=RECENT_ACTIVITY" '
        f'target="_blank" class="btn">לפוסטים החדשים ←</a>'
        f'</div>'
        for gid, name in FB_GROUPS
    )

    yad2_html = (
        '<div class="card yad2-card">'
        '<div class="badges"><span class="badge src-yad2">יד2</span></div>'
        '<div class="card-title">חיפוש דירות ביד2 — רמת גן</div>'
        '<div class="card-sub">יד2 חוסמת גישה אוטומטית. לחצו לחיפוש ישיר.</div>'
        '<a href="https://www.yad2.co.il/realestate/rent?city=8600" target="_blank" class="btn">'
        'לחיפוש ביד2 ←</a>'
        '</div>'
    )

    prompt = (
        f"Create a complete Hebrew RTL HTML page for rental apartments in Ramat Gan.\n\n"
        f"Date: {date_str} | Update #{issue}\n"
        f"Listings (JSON): {json.dumps(listings, ensure_ascii=False)}\n\n"
        "Design requirements:\n"
        "- dir='rtl' lang='he', complete HTML from <!DOCTYPE html> to </html>\n"
        "- Dark theme: bg=#0d0d14, cards=#1e1e2e, border=#2a2a3e, primary=#4a9eff, accent=#e94560\n"
        f"- Sticky navbar: '{DIGEST_TITLE}' + {date_str}\n"
        f"- Hero: title, update #{issue}, 3 stat boxes (listing count / price range / avg price)\n"
        "- Filter tabs: הכל / 1-2 חדרים / 3-4 חדרים / 5+ חדרים / 30 יום אחרונים\n"
        "  (JS: '30 יום אחרונים' hides cards where data-date is older than 30 days)\n"
        "- Mobile responsive, all CSS+JS inline\n\n"
        "For each listing in the JSON, create a card with:\n"
        "- data-rooms attribute for room filtering\n"
        "- data-date='YYYY-MM-DD' for date filtering\n"
        "- Title + address\n"
        "- Tags: price (₪), rooms, date\n"
        "- Source badge: פייסבוק=blue (#4a9eff), מדלן=green (#27ae60), homeless=orange (#e67e22)\n"
        "- Button 'לצפייה במודעה ←' with the direct link\n\n"
        "After all listing cards, insert these exact HTML sections:\n"
        "<section style='margin:40px 0'><h2 style='color:#4a9eff;text-align:center;margin-bottom:20px'>"
        "🔵 קבוצות פייסבוק</h2>"
        "<div class='cards-grid'>" + fb_cards_html + "</div></section>\n"
        "<section style='margin:40px 0;text-align:center'><div class='cards-grid'>"
        + yad2_html + "</div></section>\n\n"
        f"Footer: 'מקור: פייסבוק · מדלן · יד2 · נוצר אוטומטית על ידי Claude · {date_str}'\n\n"
        "Return ONLY complete HTML from <!DOCTYPE html> to </html>. Nothing else."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )

    for block in response.content:
        if hasattr(block, "text") and block.text:
            text = block.text
            if "<!DOCTYPE" in text:
                start = text.find("<!DOCTYPE")
                end   = text.rfind("</html>") + 7
                if end > start:
                    return text[start:end]

    print("❌ לא נוצר HTML תקין")
    sys.exit(1)


def send_notification_email(date_str, issue, listing_count, app_password):
    print("📧 שולח מייל...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {listing_count} דירות להשכרה ברמת גן · {date_str}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    html_body = (
        '<!DOCTYPE html><html dir="rtl" lang="he"><head><meta charset="UTF-8"></head>'
        '<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;direction:rtl;">'
        '<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;'
        'overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
        '<div style="background:linear-gradient(135deg,#0d0d14,#0f3460);padding:32px;text-align:center;">'
        '<div style="font-size:36px;margin-bottom:8px;">🏠</div>'
        f'<h1 style="color:#4a9eff;margin:0;font-size:20px;">דירות להשכרה ברמת גן</h1>'
        f'<p style="color:#aaa;margin:6px 0 0;font-size:13px;">עדכון יומי · {date_str}</p>'
        '</div><div style="padding:28px 32px;">'
        '<p style="font-size:16px;color:#333;line-height:1.6;">היי מירית! 👋</p>'
        f'<p style="font-size:15px;color:#555;line-height:1.7;">נמצאו '
        f'<strong style="color:#4a9eff;">{listing_count} מודעות</strong> חדשות להשכרה ברמת גן.</p>'
        '<div style="text-align:center;margin:28px 0;">'
        f'<a href="{SITE_URL}" style="background:#4a9eff;color:white;text-decoration:none;'
        'padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;">'
        'לצפייה בכל המודעות ←</a></div>'
        '<p style="font-size:13px;color:#999;border-top:1px solid #eee;padding-top:16px;margin-top:8px;">'
        f'מקור: פייסבוק · מדלן · יד2 · נשלח אוטומטית על ידי Claude · {date_str}<br>'
        f'<a href="{SITE_URL}" style="color:#4a9eff;">{SITE_URL}</a>'
        '</p></div></div></body></html>'
    )

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

    # שלב 1: חיפוש
    listings = search_listings(client)

    # שלב 2: HTML
    html = generate_html(client, listings, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    listing_count = html.count('לצפייה במודעה')
    print(f"✅ index.html נשמר ({len(html):,} תווים, ~{listing_count} מודעות)")

    # שלב 3: מייל
    send_notification_email(date_str, issue, listing_count, app_password)


if __name__ == "__main__":
    main()
