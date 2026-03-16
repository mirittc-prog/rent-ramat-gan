#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
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


def build_fb_section():
    """בונה את קטע קבוצות הפייסבוק כ-HTML קבוע."""
    cards = "".join(
        f'''<div class="card" style="background:#1e1e2e;border:1px solid #2a2a3e;border-radius:12px;padding:20px;">
  <div style="margin-bottom:10px;"><span style="background:#1877f2;color:#fff;padding:3px 10px;border-radius:20px;font-size:12px;">🔵 פייסבוק</span></div>
  <div style="font-size:16px;font-weight:bold;color:#fff;margin-bottom:16px;">{name}</div>
  <a href="https://www.facebook.com/groups/{gid}/?sorting_setting=RECENT_ACTIVITY" target="_blank"
     style="display:block;text-align:center;background:#4a9eff;color:#fff;padding:12px;border-radius:8px;text-decoration:none;font-weight:bold;">
    לפוסטים החדשים ←</a>
</div>'''
        for gid, name in FB_GROUPS
    )
    return (
        '<section style="max-width:1200px;margin:40px auto;padding:0 20px;">'
        '<h2 style="color:#4a9eff;text-align:center;font-size:24px;margin-bottom:24px;">🔵 קבוצות פייסבוק</h2>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px;">{cards}</div>'
        '</section>'
    )


def build_yad2_section():
    return (
        '<section style="max-width:400px;margin:20px auto 40px;padding:0 20px;">'
        '<div class="card" style="background:#1e1e2e;border:1px solid #2a2a3e;border-radius:12px;padding:20px;text-align:center;">'
        '<div style="margin-bottom:10px;"><span style="background:#e94560;color:#fff;padding:3px 10px;border-radius:20px;font-size:12px;">יד2</span></div>'
        '<div style="font-size:16px;font-weight:bold;color:#fff;margin-bottom:8px;">חיפוש דירות ביד2 — רמת גן</div>'
        '<div style="font-size:13px;color:#aaa;margin-bottom:16px;">יד2 חוסמת גישה אוטומטית. לחצו לחיפוש ישיר.</div>'
        '<a href="https://www.yad2.co.il/realestate/rent?city=8600" target="_blank"'
        ' style="display:block;background:#e94560;color:#fff;padding:12px;border-radius:8px;text-decoration:none;font-weight:bold;">'
        'לחיפוש ביד2 ←</a>'
        '</div></section>'
    )


def generate_html_with_search(client, date_str, issue):
    """קריאה אחת: חיפוש + HTML ביחד."""
    print("🔍 מחפש מודעות ומייצר דף HTML...")

    prompt = (
        "You have access to web search. Find rental apartments in Ramat Gan, Israel "
        "from the last 30 days, then build a complete HTML page.\n\n"
        "Run these searches:\n"
        "1. madlan.co.il רמת גן דירה להשכרה\n"
        "2. homeless.co.il דירה להשכרה רמת גן\n"
        "3. winwin.co.il דירה להשכרה רמת גן\n"
        "4. komo.co.il דירה להשכרה רמת גן\n"
        "5. דירות להשכרה רמת גן 2026 חדרים שקל\n"
        "6. madlan.co.il/listing רמת גן\n\n"
        "Include ALL listings found — the more the better. "
        "Skip listings older than 30 days if date is known.\n\n"
        "Build a complete Hebrew RTL HTML page:\n"
        "- dir='rtl' lang='he', all CSS+JS inline\n"
        "- Dark theme: bg=#0d0d14, cards=#1e1e2e, border=#2a2a3e, primary=#4a9eff, accent=#e94560\n"
        f"- Sticky navbar: '{DIGEST_TITLE}' + {date_str}\n"
        f"- Hero: title, update #{issue}, stats (count / price range / avg)\n"
        "- Filter tabs: הכל / 1-2 חדרים / 3-4 חדרים / 5+ חדרים\n"
        "  (JS: filter cards by data-rooms attribute)\n"
        "- Mobile responsive grid of cards\n\n"
        "Each listing card:\n"
        "- data-rooms='N' attribute\n"
        "- Title + address\n"
        "- Tags: price (₪), rooms, date (if known)\n"
        "- Source badge: מדלן=green, homeless=orange, other=gray\n"
        "- Button 'לצפייה במודעה ←' with the listing link\n\n"
        "End the page with a <!-- INJECT_FB --> comment before </body>.\n\n"
        f"Footer before that: 'מקור: פייסבוק · מדלן · יד2 · Claude · {date_str}'\n\n"
        "Return ONLY complete HTML from <!DOCTYPE html> to </html>."
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

    if not html:
        print("❌ לא נוצר HTML תקין")
        sys.exit(1)

    # הזרקת קטעי פייסבוק ויד2 לפני </body>
    fb_html  = build_fb_section()
    yad2_html = build_yad2_section()
    inject = fb_html + yad2_html

    if "<!-- INJECT_FB -->" in html:
        html = html.replace("<!-- INJECT_FB -->", inject)
    else:
        html = html.replace("</body>", inject + "</body>")

    listing_count = html.count("לצפייה במודעה")
    print(f"✅ HTML נוצר עם ~{listing_count} מודעות")
    return html, listing_count


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
        f'<h1 style="color:#4a9eff;margin:0;font-size:20px;">{DIGEST_TITLE}</h1>'
        f'<p style="color:#aaa;margin:6px 0 0;font-size:13px;">עדכון יומי · {date_str}</p>'
        '</div><div style="padding:28px 32px;">'
        '<p style="font-size:16px;color:#333;">היי מירית! 👋</p>'
        f'<p style="font-size:15px;color:#555;">נמצאו '
        f'<strong style="color:#4a9eff;">{listing_count} מודעות</strong> חדשות להשכרה ברמת גן.</p>'
        '<div style="text-align:center;margin:28px 0;">'
        f'<a href="{SITE_URL}" style="background:#4a9eff;color:white;text-decoration:none;'
        'padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;display:inline-block;">'
        'לצפייה בכל המודעות ←</a></div>'
        '<p style="font-size:13px;color:#999;border-top:1px solid #eee;padding-top:16px;">'
        f'מקור: פייסבוק · מדלן · יד2 · Claude · {date_str}<br>'
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
        print("❌ ANTHROPIC_API_KEY לא מוגדר"); sys.exit(1)
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD לא מוגדר"); sys.exit(1)

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
