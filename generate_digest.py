#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
שלב 1: חיפוש → JSON   |   שלב 2: JSON → HTML   |   שלב 3: מייל
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

HEBREW_MONTHS = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני",
                 "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]


def get_date_str():
    now = datetime.now()
    return f"{now.day} ב{HEBREW_MONTHS[now.month-1]} {now.year}"


def get_issue_number():
    now = datetime.now()
    return max(1, (now - datetime(2026, 3, 15)).days + 1)


# ── שלב 1: חיפוש ────────────────────────────────────────────────────────────

def search_listings(client):
    print("🔍 שלב 1: מחפש מודעות...")

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": (
            "Search for rental apartment listings in Ramat Gan, Israel. "
            "Run these searches:\n"
            "1. madlan.co.il דירה להשכרה רמת גן\n"
            "2. homeless.co.il דירה להשכרה רמת גן\n"
            "3. winwin.co.il דירה להשכרה רמת גן\n"
            "4. komo.co.il דירה להשכרה רמת גן\n"
            "5. דירה להשכרה רמת גן חדרים שקל 2026\n\n"
            "For each listing found, extract: title, price (number), rooms (number), "
            "address, date (YYYY-MM-DD or empty), source (site name), link (URL).\n\n"
            "Return ONLY a JSON array. No text, no markdown. Example:\n"
            '[{"title":"3 חדרים","price":6500,"rooms":3,"address":"ביאליק 5 רמת גן",'
            '"date":"2026-03-10","source":"madlan","link":"https://..."}]\n\n'
            "If nothing found, return: []"
        )}]
    )

    for block in response.content:
        if hasattr(block, "text") and block.text:
            t = block.text.strip()
            s, e = t.find("["), t.rfind("]") + 1
            if s >= 0 and e > s:
                try:
                    listings = json.loads(t[s:e])
                    print(f"  ✅ נמצאו {len(listings)} מודעות")
                    return listings
                except Exception:
                    pass
    print("  ⚠️ 0 מודעות נמצאו")
    return []


# ── שלב 2: HTML ─────────────────────────────────────────────────────────────

def build_static_sections():
    """בונה את קטעי פייסבוק ויד2 ישירות ב-Python — לא דרך Claude."""
    fb_cards = "".join(
        f'<div style="background:#1e1e2e;border:1px solid #2a2a3e;border-radius:12px;padding:20px;">'
        f'<div style="margin-bottom:10px;"><span style="background:#1877f2;color:#fff;'
        f'padding:3px 10px;border-radius:20px;font-size:12px;">🔵 פייסבוק</span></div>'
        f'<div style="font-size:16px;font-weight:bold;color:#e0e0e0;margin-bottom:16px;">{name}</div>'
        f'<a href="https://www.facebook.com/groups/{gid}/?sorting_setting=RECENT_ACTIVITY" '
        f'target="_blank" style="display:block;text-align:center;background:#4a9eff;color:#fff;'
        f'padding:12px;border-radius:8px;text-decoration:none;font-weight:bold;">'
        f'לפוסטים החדשים ←</a></div>'
        for gid, name in FB_GROUPS
    )
    yad2 = (
        '<div style="background:#1e1e2e;border:1px solid #2a2a3e;border-radius:12px;'
        'padding:20px;text-align:center;">'
        '<div style="margin-bottom:10px;"><span style="background:#e94560;color:#fff;'
        'padding:3px 10px;border-radius:20px;font-size:12px;">יד2</span></div>'
        '<div style="font-size:16px;font-weight:bold;color:#e0e0e0;margin-bottom:8px;">'
        'חיפוש דירות ביד2 — רמת גן</div>'
        '<div style="font-size:13px;color:#888;margin-bottom:16px;">'
        'יד2 חוסמת גישה אוטומטית. לחצו לחיפוש ישיר.</div>'
        '<a href="https://www.yad2.co.il/realestate/rent?city=8600" target="_blank" '
        'style="display:block;background:#e94560;color:#fff;padding:12px;border-radius:8px;'
        'text-decoration:none;font-weight:bold;">לחיפוש ביד2 ←</a></div>'
    )
    grid = f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:20px;">'
    return (
        f'<section style="max-width:1200px;margin:48px auto;padding:0 20px;">'
        f'<h2 style="color:#4a9eff;text-align:center;margin-bottom:24px;">🔵 קבוצות פייסבוק</h2>'
        f'{grid}{fb_cards}</div></section>'
        f'<section style="max-width:420px;margin:0 auto 48px;">'
        f'<div style="padding:0 20px;">{yad2}</div></section>'
    )


def generate_html(client, listings, date_str, issue):
    print("🎨 שלב 2: מייצר דף HTML...")

    data = json.dumps(listings, ensure_ascii=False)
    count = len(listings)
    prices = [l["price"] for l in listings if isinstance(l.get("price"), (int, float)) and l["price"] > 0]
    avg_p  = int(sum(prices) / len(prices)) if prices else 0
    min_p  = min(prices) if prices else 0
    max_p  = max(prices) if prices else 0

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": (
            f"Create a complete Hebrew RTL HTML page. Date: {date_str}, Update #{issue}.\n\n"
            f"Listings JSON ({count} items): {data}\n\n"
            "Requirements:\n"
            "- Complete HTML from <!DOCTYPE html> to </html>, dir='rtl' lang='he'\n"
            "- Dark theme: body bg=#0d0d14, cards bg=#1e1e2e, border=#2a2a3e, "
            "  primary=#4a9eff, accent=#e94560, text=#e0e0e0\n"
            f"- Sticky navbar: '{DIGEST_TITLE}' right, '{date_str}' left\n"
            f"- Hero section: big title '{DIGEST_TITLE}', subtitle 'עדכון #{issue}', "
            f"  3 stat boxes: '{count} מודעות' / '₪{min_p:,}–₪{max_p:,}' / 'ממוצע ₪{avg_p:,}'\n"
            "- Filter tabs: הכל / 1-2 חדרים / 3-4 חדרים / 5+ חדרים\n"
            "  JS: clicking tab filters cards by data-rooms attribute\n"
            "- Responsive card grid (minmax 280px)\n"
            "- All CSS and JS embedded inline\n\n"
            "For each listing in the JSON, create a card:\n"
            "- data-rooms='N' (N = rooms number)\n"
            "- Source badge top-right: מדלן=green(#27ae60), homeless=orange(#e67e22), default=gray\n"
            "- Title (bold, white)\n"
            "- Address in gray\n"
            "- Tag pills: price (₪), rooms, date (if not empty)\n"
            "- Button 'לצפייה במודעה ←' linking to listing URL\n\n"
            "After all cards, insert exactly this comment: <!-- STATIC_SECTIONS -->\n"
            f"Footer: 'מקור: פייסבוק · מדלן · יד2 · Claude · {date_str}'\n\n"
            "Return ONLY the HTML. No markdown, no explanation."
        )}]
    )

    html = ""
    for block in response.content:
        if hasattr(block, "text") and block.text and "<!DOCTYPE" in block.text:
            t = block.text
            s = t.find("<!DOCTYPE")
            e = t.rfind("</html>") + 7
            if e > s:
                html = t[s:e]

    if not html:
        print("❌ לא נוצר HTML תקין")
        sys.exit(1)

    # הזרקת קטעי פייסבוק ויד2 ישירות ב-Python
    static = build_static_sections()
    if "<!-- STATIC_SECTIONS -->" in html:
        html = html.replace("<!-- STATIC_SECTIONS -->", static)
    else:
        html = html.replace("</body>", static + "</body>")

    return html


# ── שלב 3: מייל ─────────────────────────────────────────────────────────────

def send_notification_email(date_str, listing_count, app_password):
    print("📧 שלב 3: שולח מייל...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {listing_count} דירות להשכרה ברמת גן · {date_str}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    body = (
        '<!DOCTYPE html><html dir="rtl" lang="he"><head><meta charset="UTF-8"></head>'
        '<body style="font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:20px;">'
        '<div style="max-width:520px;margin:0 auto;background:#fff;border-radius:12px;'
        'overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);">'
        '<div style="background:linear-gradient(135deg,#0d0d14,#0f3460);padding:32px;text-align:center;">'
        '<div style="font-size:36px;">🏠</div>'
        f'<h1 style="color:#4a9eff;margin:8px 0 0;font-size:20px;">{DIGEST_TITLE}</h1>'
        f'<p style="color:#aaa;margin:6px 0 0;font-size:13px;">עדכון יומי · {date_str}</p>'
        '</div><div style="padding:28px 32px;direction:rtl;">'
        '<p style="font-size:16px;color:#333;">היי מירית! 👋</p>'
        f'<p style="font-size:15px;color:#555;">נמצאו '
        f'<strong style="color:#4a9eff;">{listing_count} מודעות</strong> להשכרה ברמת גן.</p>'
        '<div style="text-align:center;margin:28px 0;">'
        f'<a href="{SITE_URL}" style="background:#4a9eff;color:#fff;text-decoration:none;'
        'padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;">לצפייה בכל המודעות ←</a></div>'
        f'<p style="font-size:12px;color:#aaa;border-top:1px solid #eee;padding-top:12px;">'
        f'<a href="{SITE_URL}" style="color:#4a9eff;">{SITE_URL}</a></p>'
        '</div></div></body></html>'
    )
    msg.attach(MIMEText(body, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as s:
        s.starttls()
        s.login(SENDER_EMAIL, app_password)
        s.send_message(msg)
    print(f"✅ מייל נשלח אל {RECIPIENT_EMAIL}")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    api_key      = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace('\xa0','').replace(' ','').strip()
    if not api_key:      print("❌ ANTHROPIC_API_KEY לא מוגדר"); sys.exit(1)
    if not app_password: print("❌ GMAIL_APP_PASSWORD לא מוגדר");  sys.exit(1)

    client   = anthropic.Anthropic(api_key=api_key)
    date_str = get_date_str()
    issue    = get_issue_number()
    print(f"📅 מייצר עדכון — {date_str} (עדכון #{issue})")

    listings      = search_listings(client)
    html          = generate_html(client, listings, date_str, issue)
    listing_count = html.count("לצפייה במודעה")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים, ~{listing_count} מודעות)")

    send_notification_email(date_str, listing_count, app_password)


if __name__ == "__main__":
    main()
