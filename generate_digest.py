#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
מחפש מודעות בפייסבוק ומדלן דרך Claude web search, מייצר דף HTML, שולח מייל.
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
DIGEST_TITLE    = "דירות להשכרה ברמת גן"
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


def generate_html_with_search(client, date_str, issue):
    """מחפש מודעות ומייצר HTML בקריאה אחת עם web_search."""
    print("🔍 מחפש מודעות ומייצר דף HTML...")

    prompt = (
        "You have access to web search. Your task: find REAL rental apartment listings "
        "in Ramat Gan, Israel, with DIRECT LINKS to specific posts/listings.\n\n"

        "=== SEARCH STRATEGY (run ALL of these) ===\n"
        '1. facebook.com "רמת גן" "להשכרה" דירה חדרים\n'
        '2. facebook.com/groups דירות להשכרה רמת גן\n'
        '3. madlan.co.il/listing רמת גן להשכרה\n'
        '4. homeless.co.il דירה להשכרה רמת גן\n'
        '5. "רמת גן" "להשכרה" דירה חדרים ש"ח 2026\n\n'

        "=== CRITICAL RULES ===\n"
        "- For EACH listing, you MUST have a direct URL to that specific post or listing page.\n"
        "- Facebook posts: use the actual facebook.com/groups/xxx/posts/yyy URL from search results.\n"
        "- Madlan listings: use the actual madlan.co.il/listing/xxx URL from search results.\n"
        "- Homeless listings: use the actual homeless.co.il URL from search results.\n"
        "- Do NOT invent or fabricate URLs. Only use URLs that appeared in your search results.\n"
        "- Do NOT link to search pages or category pages.\n"
        "- Extract: title, price (in ILS), rooms, address, source (facebook/madlan/homeless), direct URL.\n"
        "- Include as many listings as you can find. More = better.\n\n"

        "=== NOW BUILD THE HTML PAGE ===\n"
        "Create a complete Hebrew RTL HTML page with these sections:\n\n"

        "SECTION 1: מודעות שנמצאו (all listings with direct links)\n"
        "SECTION 2: חיפוש ביד2 (ONE card linking to: "
        "https://www.yad2.co.il/realestate/rent?city=8600 "
        "with text: 'יד2 חוסמת גישה אוטומטית. לחצו כאן לחיפוש ישיר באתר יד2')\n\n"

        "Design:\n"
        "- dir='rtl' lang='he'\n"
        "- Dark theme: background #0d0d14, cards #1e1e2e, border #2a2a3e\n"
        "- Primary: #4a9eff, accent: #e94560\n"
        f"- Sticky navbar with '{DIGEST_TITLE}' and date {date_str}\n"
        f"- Hero: title, update #{issue}, stats (listing count, price range, avg)\n"
        "- Filter tabs: הכל / 1-2 חדרים / 3-4 חדרים / 5+ חדרים\n"
        "- Mobile responsive, all CSS+JS inline\n\n"

        "Each listing card:\n"
        "- Title + address\n"
        "- Tags: price, rooms, source (פייסבוק/מדלן/homeless)\n"
        "- Source badge with color: Facebook=blue, Madlan=green, Homeless=orange\n"
        "- Button 'לצפייה במודעה ←' with href to the DIRECT listing URL\n\n"

        f"Footer: 'מקור: פייסבוק · מדלן · יד2 · נוצר אוטומטית על ידי Claude · {date_str}'\n\n"

        "Return ONLY the HTML from <!DOCTYPE html> to </html>. Nothing else."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": prompt}]
    )

    html = ""
    for block in response.content:
        if hasattr(block, "text") and block.text:
            text = block.text
            if "<!DOCTYPE" in text:
                start = text.find("<!DOCTYPE")
                end   = text.rfind("</html>") + 7
                if end > start:
                    html = text[start:end]

    if not html or "<!DOCTYPE" not in html:
        print("❌ לא נוצר HTML תקין")
        sys.exit(1)

    listing_count = html.count('לצפייה במודעה')
    print(f"✅ HTML נוצר עם ~{listing_count} מודעות")
    return html, listing_count


def send_notification_email(date_str, issue, listing_count, app_password):
    print("📧 שולח מייל...")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {listing_count} דירות להשכרה ברמת גן · {date_str}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    html_body = (
        '<!DOCTYPE html>'
        '<html dir="rtl" lang="he">'
        '<head><meta charset="UTF-8"></head>'
        '<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;direction:rtl;">'
        '<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);">'
        '<div style="background:linear-gradient(135deg,#0d0d14,#0f3460);padding:32px;text-align:center;">'
        '<div style="font-size:36px;margin-bottom:8px;">🏠</div>'
        f'<h1 style="color:#4a9eff;margin:0;font-size:20px;">דירות להשכרה ברמת גן</h1>'
        f'<p style="color:#aaa;margin:6px 0 0;font-size:13px;">עדכון יומי · {date_str}</p>'
        '</div>'
        '<div style="padding:28px 32px;">'
        '<p style="font-size:16px;color:#333;line-height:1.6;">היי מירית! 👋</p>'
        '<p style="font-size:15px;color:#555;line-height:1.7;">'
        f'נמצאו <strong style="color:#4a9eff;">{listing_count} מודעות</strong> חדשות להשכרה ברמת גן.'
        '</p>'
        '<div style="text-align:center;margin:28px 0;">'
        f'<a href="{SITE_URL}" style="background:#4a9eff;color:white;text-decoration:none;padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;">'
        'לצפייה בכל המודעות ←'
        '</a>'
        '</div>'
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

    html, listing_count = generate_html_with_search(client, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים)")

    send_notification_email(date_str, issue, listing_count, app_password)


if __name__ == "__main__":
    main()
