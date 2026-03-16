#!/usr/bin/env python3
"""
עדכון יומי — דירות להשכרה ברמת גן
מקורות: קבוצות פייסבוק (Playwright + cookies), מדלן, הומלס
יד2 — קישור ידני בלבד

הרצה ראשונה (שמירת cookies לפייסבוק):
    python generate_digest.py --setup

הרצה רגילה:
    python generate_digest.py
"""

import json
import os
import re
import sys
import smtplib
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("❌ playwright לא מותקן. הרץ:")
    print("   pip install playwright")
    print("   playwright install chromium")
    sys.exit(1)

try:
    from playwright_stealth import stealth_sync as _stealth
    STEALTH_AVAILABLE = True
except ImportError:
    STEALTH_AVAILABLE = False

def apply_stealth(page):
    if STEALTH_AVAILABLE:
        _stealth(page)

# ── הגדרות ──────────────────────────────────────────────────────────────────
RECIPIENT_EMAIL = "mirit.tc@gmail.com"
SENDER_EMAIL    = "miritronicohen@gmail.com"
SITE_URL        = "https://mirittc-prog.github.io/rent-ramat-gan"
DIGEST_TITLE    = "דירות להשכרה ברמת גן"
COOKIES_FILE    = Path(__file__).parent / "fb_cookies.json"
MAX_DAYS        = 30

FB_GROUPS = [
    ("1870209196564360", "קבוצת דירות להשכרה ברמת גן"),
    ("1424244737803677", "קבוצת דירות רמת גן"),
    ("647901439404148",  "קבוצת שכירות רמת גן"),
    ("253957624766723",  "קבוצת דירות להשכרה גוש דן"),
    ("1774413905909921", "קבוצת דירות רמת גן והסביבה"),
]

YAD2_URL = "https://www.yad2.co.il/realestate/rent?city=8600"
# ────────────────────────────────────────────────────────────────────────────

HEBREW_MONTHS = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני",
                 "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]
MONTHS_EN = ["january","february","march","april","may","june",
             "july","august","september","october","november","december"]
MONTHS_HE = ["ינואר","פברואר","מרץ","אפריל","מאי","יוני",
             "יולי","אוגוסט","ספטמבר","אוקטובר","נובמבר","דצמבר"]


def get_date_str():
    now = datetime.now()
    return f"{now.day} ב{HEBREW_MONTHS[now.month-1]} {now.year}"


def get_issue_number():
    now = datetime.now()
    return max(1, (now - datetime(2026, 3, 15)).days + 1)


# ── Setup: שמירת cookies פייסבוק ─────────────────────────────────────────────

def setup_facebook_cookies():
    """פותח דפדפן נראה לעין. המשתמש מתחבר לפייסבוק, ואז cookies נשמרים."""
    print("🔑 מצב הגדרה — ייפתח דפדפן Chrome.")
    print("   התחבר לפייסבוק, וכשתסיים לחץ Enter כאן בטרמינל.")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=50)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="he-IL",
        )
        page = ctx.new_page()
        page.goto("https://www.facebook.com/login", timeout=30000)
        input("\n✋ התחבר לפייסבוק בדפדפן שנפתח, ואז לחץ Enter כאן...")
        cookies = ctx.cookies()
        COOKIES_FILE.write_text(json.dumps(cookies, ensure_ascii=False, indent=2))
        print(f"✅ Cookies נשמרו ב: {COOKIES_FILE}")
        browser.close()


# ── פרסור תאריכים ─────────────────────────────────────────────────────────────

def parse_fb_date(s: str):
    """ממיר מחרוזת תאריך של פייסבוק ל-datetime."""
    now = datetime.now()
    s = s.strip().lower()

    if any(x in s for x in ["just now", "עכשיו", "כרגע"]):
        return now

    m = re.search(r"(\d+)\s*(minute|min|דקה|דקות)", s)
    if m:
        return now - timedelta(minutes=int(m.group(1)))

    m = re.search(r"(\d+)\s*(hour|hr|שעה|שעות)", s)
    if m:
        return now - timedelta(hours=int(m.group(1)))

    if any(x in s for x in ["yesterday", "אתמול"]):
        return now - timedelta(days=1)

    m = re.search(r"(\d+)\s*(day|יום|ימים)", s)
    if m:
        return now - timedelta(days=int(m.group(1)))

    m = re.search(r"(\d+)\s*(week|שבוע|שבועות)", s)
    if m:
        return now - timedelta(weeks=int(m.group(1)))

    for i, month in enumerate(MONTHS_EN + MONTHS_HE):
        if month in s:
            month_num = (i % 12) + 1
            day_m = re.search(r"\d+", s)
            if day_m:
                try:
                    dt = datetime(now.year, month_num, int(day_m.group()))
                    if dt > now:
                        dt = dt.replace(year=now.year - 1)
                    return dt
                except ValueError:
                    pass

    m = re.search(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass

    return None


def parse_date_generic(s: str):
    """פרסור תאריכים כלליים: ISO, timestamp, עברי/אנגלי יחסי, DD/MM/YYYY."""
    if not s:
        return None
    s = s.strip()

    # ISO 8601: 2026-03-15 or 2026-03-15T10:30:00
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass

    # Unix timestamp (10 or 13 digits)
    if re.match(r"^\d{10,13}$", s):
        try:
            ts = int(s[:10])
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError):
            pass

    # Hebrew/English relative & DD/MM/YYYY
    return parse_fb_date(s)


# ── Facebook Scraping ──────────────────────────────────────────────────────────

def scrape_fb_group(page, group_id: str, group_name: str) -> list[dict]:
    url = f"https://www.facebook.com/groups/{group_id}/?sorting_setting=RECENT_ACTIVITY"
    print(f"  📋 {group_name}...")
    cutoff = datetime.now() - timedelta(days=MAX_DAYS)

    try:
        page.goto(url, timeout=40000, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        for _ in range(6):
            page.keyboard.press("End")
            page.wait_for_timeout(1800)

        raw_items = page.evaluate("""
            () => {
                const results = [];
                const seen = new Set();

                document.querySelectorAll('a[href*="/posts/"], a[href*="/permalink/"]').forEach(a => {
                    const href = a.href.split('?')[0];
                    if (seen.has(href) || !href.includes('facebook.com')) return;
                    seen.add(href);

                    const article = a.closest('[role="article"]');
                    let dateText = '';
                    let postText = '';

                    if (article) {
                        article.querySelectorAll('a[aria-label], span[aria-label]').forEach(el => {
                            const label = el.getAttribute('aria-label') || '';
                            if (!dateText && label.match(/\\d/)) dateText = label;
                        });

                        const msgEl =
                            article.querySelector('[data-ad-comet-preview="message"]') ||
                            article.querySelector('[data-ad-preview="message"]') ||
                            article.querySelector('[dir="auto"]');
                        if (msgEl) postText = msgEl.innerText.trim().slice(0, 200);
                    }

                    results.push({ url: href, dateText, postText });
                });
                return results;
            }
        """)

    except Exception as e:
        print(f"    ⚠️  שגיאה: {e}")
        return []

    listings = []
    for item in raw_items:
        post_url = item["url"]
        if not re.search(r"/(posts|permalink)/", post_url):
            continue

        raw_date = item.get("dateText", "")
        dt = parse_fb_date(raw_date) if raw_date else None
        if dt and dt < cutoff:
            continue

        text = item.get("postText", "").strip() or "פוסט בקבוצה"
        if not is_rental(post_url, text):
            continue
        listings.append({
            "source":      "facebook",
            "source_name": "פייסבוק",
            "group_name":  group_name,
            "group_id":    group_id,
            "url":         post_url,
            "text":        text[:180],
            "price":       "",
            "rooms":       "",
            "address":     "",
            "date":        dt.strftime("%d/%m/%Y") if dt else "לאחרונה",
            "date_obj":    dt or datetime.now(),
        })

    print(f"    ✅ {len(listings)} פוסטים")
    return listings


# ── פילטר השכרה בלבד ─────────────────────────────────────────────────────────

# מילות מפתח שמעידות על מכירה / עסקי / שותפות — לסינון
EXCLUDE_URL_PATTERNS = re.compile(
    r"/(for-sale|sale|iski|shortterm|sold|forsale|buy|mekhar|mate|roommate)(/|$)",
    re.IGNORECASE,
)
EXCLUDE_TEXT_PATTERNS = re.compile(
    r"(למכירה|מכירה|עסקי|משרד|מחסן|חנות|גרז'|גראז'|שותף|שותפ)",
    re.IGNORECASE,
)

def is_rental(url: str, text: str = "") -> bool:
    """מחזיר True אם המודעה היא להשכרה למגורים."""
    if EXCLUDE_URL_PATTERNS.search(url):
        return False
    if text and EXCLUDE_TEXT_PATTERNS.search(text):
        return False
    return True


# ── Madlan popup dismissal ───────────────────────────────────────────────────

def _close_madlan_popups(page):
    """סוגר פופאפים של מדלן (cookies, התראות, הרשמה)."""
    # ESC — סוגר מודאלים רבים
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)

    # סלקטורים נפוצים לכפתורי סגירה
    close_selectors = [
        # כפתורי X / סגור
        'button[aria-label="סגור"]',
        'button[aria-label="Close"]',
        'button[aria-label="close"]',
        '[class*="close" i][role="button"]',
        '[class*="Close"][role="button"]',
        '[class*="dismiss" i]',
        '[data-testid*="close" i]',
        '[data-testid*="dismiss" i]',
        # cookies / GDPR
        '[class*="cookie" i] button',
        '[id*="cookie" i] button',
        'button[class*="accept" i]',
        'button[class*="agree" i]',
        # אלמנטים ספציפיים למדלן
        '[class*="Modal"] button[class*="close" i]',
        '[class*="modal"] button[class*="close" i]',
        '[class*="Popup"] button[class*="close" i]',
        '[class*="popup"] button[class*="close" i]',
        '[class*="overlay" i] button',
        '[class*="Overlay"] button',
    ]

    for sel in close_selectors:
        try:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                btn.click()
                print(f"    🔕 סגרתי פופאפ: {sel}")
                page.wait_for_timeout(400)
        except Exception:
            pass

    # ESC פעם נוספת לבטחה
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)


# ── Madlan Scraping ────────────────────────────────────────────────────────────

def _find_listings_in_json(obj, depth=0) -> list:
    """חיפוש רשיות בתוך JSON של __NEXT_DATA__ — מחפש מערך עם שדות price/rooms."""
    if depth > 8 or not isinstance(obj, (dict, list)):
        return []
    if isinstance(obj, list) and len(obj) >= 3:
        # בדוק אם הפריטים נראים כמו מודעות
        sample = obj[0] if obj else {}
        if isinstance(sample, dict):
            keys = set(sample.keys())
            listing_keys = {"price", "rooms", "id", "slug", "address", "publishedAt",
                            "updatedAt", "monthlyRent", "floor", "area"}
            if len(keys & listing_keys) >= 2:
                return obj
    if isinstance(obj, dict):
        for v in obj.values():
            result = _find_listings_in_json(v, depth + 1)
            if result:
                return result
    if isinstance(obj, list):
        for item in obj:
            result = _find_listings_in_json(item, depth + 1)
            if result:
                return result
    return []


def scrape_madlan(page) -> list[dict]:
    """מגרד מודעות ממדלן — מנסה __NEXT_DATA__ ואחר כך DOM."""
    url = "https://www.madlan.co.il/for-rent/%D7%A8%D7%9E%D7%AA-%D7%92%D7%9F"
    print("  🏠 מדלן...")
    cutoff = datetime.now() - timedelta(days=MAX_DAYS)
    listings = []

    try:
        apply_stealth(page)
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # סגירת פופאפים של מדלן
        _close_madlan_popups(page)
        page.wait_for_timeout(2000)

        # גלגול לטעינת מודעות נוספות
        for _ in range(4):
            page.keyboard.press("End")
            page.wait_for_timeout(1500)

        # ניסיון 1: __NEXT_DATA__
        next_data = page.evaluate("""
            () => {
                try {
                    return JSON.parse(document.getElementById('__NEXT_DATA__').textContent);
                } catch(e) { return null; }
            }
        """)

        if next_data:
            raw_items = _find_listings_in_json(next_data)
            print(f"    📦 __NEXT_DATA__: {len(raw_items)} פריטים")
            for item in raw_items:
                if not isinstance(item, dict):
                    continue
                # סינון — רק השכרה למגורים
                deal_type = str(item.get("dealType") or item.get("type") or item.get("listingType") or "").lower()
                if deal_type and deal_type not in ("rent", "for_rent", "rental", "השכרה", ""):
                    continue

                # חילוץ שדות — madlan משתמש בשמות שונים לפי גרסה
                price_val = (item.get("price") or item.get("monthlyRent") or
                             item.get("rentPrice") or "")
                rooms_val = (item.get("rooms") or item.get("roomsCount") or "")
                addr_val  = ""
                addr_obj  = item.get("address") or item.get("location") or {}
                if isinstance(addr_obj, dict):
                    parts = [addr_obj.get("street",""), addr_obj.get("houseNum",""),
                             addr_obj.get("city","")]
                    addr_val = " ".join(str(p) for p in parts if p).strip()
                elif isinstance(addr_obj, str):
                    addr_val = addr_obj

                date_raw = (item.get("publishedAt") or item.get("updatedAt") or
                            item.get("createdAt") or "")
                dt = parse_date_generic(str(date_raw)) if date_raw else None
                if dt and dt < cutoff:
                    continue

                listing_id = item.get("id") or item.get("listingId") or ""
                slug       = item.get("slug") or item.get("url") or ""
                if slug and slug.startswith("http"):
                    listing_url = slug
                elif listing_id:
                    listing_url = f"https://www.madlan.co.il/listing/{listing_id}"
                else:
                    continue  # אין קישור ישיר — מדלג

                price_str = f"₪{price_val:,}" if isinstance(price_val, (int, float)) and price_val else str(price_val)
                rooms_str = str(rooms_val) if rooms_val else ""

                listings.append({
                    "source":      "madlan",
                    "source_name": "מדלן",
                    "group_name":  "מדלן",
                    "group_id":    "madlan",
                    "url":         listing_url,
                    "text":        f"{addr_val}",
                    "price":       price_str,
                    "rooms":       rooms_str,
                    "address":     addr_val,
                    "date":        dt.strftime("%d/%m/%Y") if dt else "לאחרונה",
                    "date_obj":    dt or datetime.now(),
                })

        # ניסיון 2: DOM (גם אם __NEXT_DATA__ הצליח — בונוס)
        if not listings:
            raw_dom = page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();
                    // נסה סלקטורים שונים של מדלן
                    const selectors = [
                        'a[href*="/listing/"]',
                        'a[href*="/nadlan/"]',
                        '[data-listing-id] a',
                    ];
                    for (const sel of selectors) {
                        document.querySelectorAll(sel).forEach(a => {
                            const href = a.href ? a.href.split('?')[0] : '';
                            if (!href || seen.has(href)) return;
                            seen.add(href);
                            const card = a.closest('article') || a.closest('[class*="card"]') ||
                                         a.closest('[class*="Card"]') || a.closest('li') || a.parentElement;
                            const getText = (el, ...cls) => {
                                for (const c of cls) {
                                    const el2 = el && el.querySelector(c);
                                    if (el2) return el2.innerText.trim();
                                }
                                return '';
                            };
                            results.push({
                                url:      href,
                                price:    getText(card, '[class*="price"]','[class*="Price"]','[data-testid*="price"]'),
                                rooms:    getText(card, '[class*="room"]','[class*="Room"]'),
                                address:  getText(card, '[class*="address"]','[class*="Address"]','[class*="street"]'),
                                dateText: getText(card, 'time','[class*="date"]','[class*="Date"]','[class*="time"]'),
                            });
                        });
                        if (results.length > 0) break;
                    }
                    return results;
                }
            """)
            print(f"    🌐 DOM: {len(raw_dom)} קישורים")
            for item in raw_dom:
                href = item.get("url","")
                if not re.search(r"madlan\.co\.il/(listing|nadlan)/", href):
                    continue
                if not is_rental(href, item.get("address","")):
                    continue
                dt = parse_date_generic(item.get("dateText",""))
                if dt and dt < cutoff:
                    continue
                listings.append({
                    "source":      "madlan",
                    "source_name": "מדלן",
                    "group_name":  "מדלן",
                    "group_id":    "madlan",
                    "url":         href,
                    "text":        item.get("address",""),
                    "price":       item.get("price",""),
                    "rooms":       item.get("rooms",""),
                    "address":     item.get("address",""),
                    "date":        dt.strftime("%d/%m/%Y") if dt else "לאחרונה",
                    "date_obj":    dt or datetime.now(),
                })

    except Exception as e:
        print(f"    ⚠️  שגיאה במדלן: {e}")

    # הסרת כפולות לפי URL
    seen = set()
    unique = []
    for item in listings:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    print(f"    ✅ {len(unique)} מודעות ממדלן")
    return unique


# ── Homeless Scraping ──────────────────────────────────────────────────────────

def scrape_homeless(page) -> list[dict]:
    """מגרד מודעות מהומלס — URL נכון, סלקטור viewad."""
    BASE_URL = "https://www.homeless.co.il/rent/city=%D7%A8%D7%9E%D7%AA%20%D7%92%D7%9F"
    print("  🏡 הומלס...")
    cutoff = datetime.now() - timedelta(days=MAX_DAYS)
    listings = []

    try:
        for page_num in range(1, 4):  # עמודים 1–3
            purl = BASE_URL if page_num == 1 else f"{BASE_URL}/{page_num}"
            page.goto(purl, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            raw_dom = page.evaluate("""
                () => {
                    const results = [];
                    const seen = new Set();
                    document.querySelectorAll('a[href*="viewad,"]').forEach(a => {
                        const href = a.href.split('?')[0];
                        if (seen.has(href)) return;
                        seen.add(href);
                        // מצא את כרטיס האב
                        const card = a.closest('tr') || a.closest('li') ||
                                     a.closest('[class*="board"]') || a.parentElement;
                        const cardText = card ? card.innerText.trim() : '';
                        // URL של תמונה לשם חילוץ תאריך
                        const img = card ? card.querySelector('img[src*="uploads.homeless"]') : null;
                        results.push({
                            url:    href,
                            text:   cardText.slice(0, 300),
                            imgSrc: img ? img.src : '',
                        });
                    });
                    return results;
                }
            """)

            if not raw_dom:
                break  # אין יותר עמודים

            print(f"    עמוד {page_num}: {len(raw_dom)} מודעות")

            for item in raw_dom:
                href = item.get("url", "")
                if not href or "homeless.co.il" not in href:
                    continue
                if not is_rental(href):
                    continue

                text = item.get("text", "")

                # חילוץ תאריך מ-URL של תמונה: uploads.homeless.co.il/rent/202602/...
                dt = None
                img_m = re.search(r'/rent/(\d{4})(\d{2})/', item.get("imgSrc", ""))
                if img_m:
                    try:
                        dt = datetime(int(img_m.group(1)), int(img_m.group(2)), 15)
                    except ValueError:
                        pass
                if dt and dt < cutoff:
                    continue

                # חילוץ מחיר, חדרים, כתובת מהטקסט
                price_m = re.search(r'([\d,]+)\s*₪', text)
                price = f"₪{price_m.group(1)}" if price_m else ""

                rooms_m = re.search(r'([\d.]+)\s*חדרים', text)
                rooms = rooms_m.group(1) if rooms_m else ""

                addr_m = re.search(r'ברמת גן\s*[•\-]\s*([^\n•\d]+)', text)
                address = addr_m.group(1).strip() if addr_m else "רמת גן"

                listings.append({
                    "source":      "homeless",
                    "source_name": "הומלס",
                    "group_name":  "הומלס",
                    "group_id":    "homeless",
                    "url":         href,
                    "text":        text[:150].replace('\n', ' '),
                    "price":       price,
                    "rooms":       rooms,
                    "address":     address,
                    "date":        dt.strftime("%m/%Y") if dt else "לאחרונה",
                    "date_obj":    dt or datetime.now(),
                })

    except Exception as e:
        print(f"    ⚠️  שגיאה בהומלס: {e}")

    seen = set()
    unique = []
    for item in listings:
        if item["url"] not in seen:
            seen.add(item["url"])
            unique.append(item)

    print(f"    ✅ {len(unique)} מודעות מהומלס")
    return unique


# ── Main Scraping Orchestration ───────────────────────────────────────────────

def scrape_all() -> list[dict]:
    """מגרד את כל המקורות: פייסבוק (עם cookies), מדלן, הומלס."""
    if not COOKIES_FILE.exists():
        print("❌ אין cookies שמורים לפייסבוק.")
        print("   הרץ תחילה: python generate_digest.py --setup")
        sys.exit(1)

    fb_cookies = json.loads(COOKIES_FILE.read_text())
    all_listings = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # ── פייסבוק (עם cookies) ─────────────────────────────────────────────
        print("🔵 גורד קבוצות פייסבוק...")
        fb_ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="he-IL",
        )
        fb_ctx.add_cookies(fb_cookies)
        fb_page = fb_ctx.new_page()

        for group_id, group_name in FB_GROUPS:
            items = scrape_fb_group(fb_page, group_id, group_name)
            all_listings.extend(items)
            time.sleep(3)

        fb_ctx.close()

        # ── מדלן + הומלס (ללא cookies) ───────────────────────────────────────
        print("\n🔍 גורד מדלן ו-הומלס...")
        other_ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="he-IL",
        )
        other_page = other_ctx.new_page()

        madlan_items   = scrape_madlan(other_page)
        time.sleep(2)
        homeless_items = scrape_homeless(other_page)

        all_listings.extend(madlan_items)
        all_listings.extend(homeless_items)
        other_ctx.close()

        browser.close()

    all_listings.sort(key=lambda x: x["date_obj"], reverse=True)
    return all_listings


# ── HTML ──────────────────────────────────────────────────────────────────────

def _escape(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


SOURCE_COLORS = {
    "facebook": "#1877f2",
    "madlan":   "#00c896",
    "homeless": "#ff6b35",
}
SOURCE_LABELS = {
    "facebook": "פייסבוק",
    "madlan":   "מדלן",
    "homeless": "הומלס",
}


def build_card(item: dict) -> str:
    src       = item["source"]
    color     = SOURCE_COLORS.get(src, "#4a9eff")
    src_label = SOURCE_LABELS.get(src, src)
    group     = _escape(item.get("group_name",""))

    price_tag = f'<span class="tag tag-price">💰 {_escape(item["price"])}</span>' if item.get("price") else ""
    rooms_tag = f'<span class="tag">🛏 {_escape(item["rooms"])} חד\'</span>' if item.get("rooms") else ""
    addr_tag  = f'<span class="tag">📍 {_escape(item["address"])}</span>' if item.get("address") else ""
    btn_text  = "לצפייה בפוסט ←" if src == "facebook" else "לצפייה במודעה ←"

    secondary_badge = (
        f'<span class="badge badge-grp">{group}</span>'
        if src == "facebook" and group
        else ""
    )

    return (
        f'<div class="card" data-source="{src}">'
        f'<div class="badges">'
        f'<span class="badge" style="background:{color}">{src_label}</span>'
        f'{secondary_badge}'
        f'</div>'
        f'<p class="card-text">{_escape(item["text"])}</p>'
        f'<div class="card-meta">'
        f'{price_tag}{rooms_tag}{addr_tag}'
        f'<span class="tag">📅 {item["date"]}</span>'
        f'</div>'
        f'<a href="{item["url"]}" target="_blank" class="btn" style="background:{color}">{btn_text}</a>'
        f'</div>'
    )


def build_html(listings: list[dict], date_str: str, issue: int) -> str:
    cards_html = "".join(build_card(item) for item in listings)

    # סטטיסטיקות לפי מקור
    fb_count       = sum(1 for i in listings if i["source"] == "facebook")
    madlan_count   = sum(1 for i in listings if i["source"] == "madlan")
    homeless_count = sum(1 for i in listings if i["source"] == "homeless")

    # כפתורי פילטר
    filter_btns = (
        '<button class="filter-btn" data-source="facebook" onclick="filterSource(this)" '
        'style="--c:#1877f2">🔵 פייסבוק</button>'
        '<button class="filter-btn" data-source="madlan" onclick="filterSource(this)" '
        'style="--c:#00c896">🏠 מדלן</button>'
        '<button class="filter-btn" data-source="homeless" onclick="filterSource(this)" '
        'style="--c:#ff6b35">🏡 הומלס</button>'
    )

    empty_msg = (
        '<div class="empty"><span>😕</span>'
        '<p>לא נמצאו מודעות. בדקי cookies ונסי שוב.</p></div>'
    )

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{DIGEST_TITLE}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0d0d14;color:#e0e0e0;font-family:'Segoe UI',Arial,sans-serif;direction:rtl}}

.navbar{{position:sticky;top:0;z-index:100;background:#0d0d14dd;backdrop-filter:blur(10px);
  border-bottom:1px solid #2a2a3e;padding:14px 24px;
  display:flex;justify-content:space-between;align-items:center}}
.navbar-title{{color:#4a9eff;font-size:18px;font-weight:bold}}
.navbar-date{{color:#888;font-size:13px}}

.hero{{text-align:center;padding:60px 20px 40px;
  background:radial-gradient(ellipse at top,#0f3460 0%,#0d0d14 70%)}}
.hero h1{{font-size:clamp(22px,5vw,38px);color:#4a9eff;margin-bottom:10px}}
.issue{{color:#888;font-size:14px;margin-bottom:24px}}
.stats{{display:inline-flex;gap:24px;background:#1e1e2e;
  border:1px solid #2a2a3e;border-radius:12px;padding:16px 32px;flex-wrap:wrap;
  justify-content:center}}
.stat{{text-align:center}}
.stat-num{{font-size:28px;font-weight:bold;color:#4a9eff}}
.stat-label{{font-size:12px;color:#888;margin-top:4px}}

.filters{{max-width:1200px;margin:32px auto 0;padding:0 20px;
  display:flex;gap:10px;flex-wrap:wrap;align-items:center}}
.filters-label{{color:#888;font-size:13px;margin-left:8px}}
.filter-btn{{background:#1e1e2e;border:1px solid #2a2a3e;color:#aaa;
  padding:8px 16px;border-radius:20px;cursor:pointer;font-size:13px;transition:all .2s}}
.filter-btn:hover{{background:var(--c,#4a9eff);border-color:var(--c,#4a9eff);color:#fff}}
.filter-btn.active{{background:var(--c,#4a9eff);border-color:var(--c,#4a9eff);color:#fff}}
.filter-btn[data-source="all"]{{--c:#4a9eff;border-color:#4a9eff;color:#4a9eff}}

.section{{max-width:1200px;margin:32px auto;padding:0 20px}}
.section h2{{color:#4a9eff;margin-bottom:20px;font-size:20px}}

.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:20px}}
.card{{background:#1e1e2e;border:1px solid #2a2a3e;border-radius:12px;padding:20px;
  display:flex;flex-direction:column;gap:12px;transition:border-color .2s}}
.card:hover{{border-color:#4a9eff}}

.badges{{display:flex;gap:8px;flex-wrap:wrap}}
.badge{{padding:3px 10px;border-radius:20px;font-size:11px;font-weight:bold;color:#fff}}
.badge-grp{{background:#2a2a3e;color:#aaa}}

.card-text{{color:#ccc;font-size:14px;line-height:1.6;flex:1}}
.card-meta{{display:flex;gap:8px;flex-wrap:wrap}}
.tag{{background:#2a2a3e;color:#888;padding:3px 10px;border-radius:12px;font-size:12px}}
.tag-price{{background:#0f3460;color:#4a9eff;font-weight:bold}}

.btn{{display:block;text-align:center;background:#4a9eff;color:#fff;padding:11px;
  border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px;
  transition:opacity .2s;margin-top:4px}}
.btn:hover{{opacity:.85}}

.yad2-banner{{max-width:1200px;margin:0 auto 32px;padding:0 20px}}
.yad2-box{{background:#1e1e2e;border:1px solid #e94560;border-radius:12px;
  padding:20px 28px;display:flex;justify-content:space-between;align-items:center;gap:16px;
  flex-wrap:wrap}}
.yad2-text{{color:#e0e0e0;font-size:15px}}
.yad2-text strong{{color:#e94560}}

.empty{{text-align:center;padding:60px;color:#555}}
.empty span{{font-size:48px;display:block;margin-bottom:12px}}
.empty p{{font-size:15px}}

footer{{text-align:center;padding:40px;color:#444;font-size:12px;
  border-top:1px solid #2a2a3e;margin-top:40px}}
footer a{{color:#4a9eff;text-decoration:none}}

@media(max-width:600px){{
  .stats{{gap:16px}}
  .filter-btn{{font-size:12px;padding:6px 12px}}
  .yad2-box{{flex-direction:column}}
}}
</style>
</head>
<body>

<nav class="navbar">
  <span class="navbar-title">🏠 {DIGEST_TITLE}</span>
  <span class="navbar-date">{date_str}</span>
</nav>

<div class="hero">
  <h1>🏠 {DIGEST_TITLE}</h1>
  <div class="issue">עדכון #{issue} · {date_str} · {MAX_DAYS} ימים אחרונים</div>
  <div class="stats">
    <div class="stat">
      <div class="stat-num" style="color:#1877f2">{fb_count}</div>
      <div class="stat-label">פייסבוק</div>
    </div>
    <div class="stat">
      <div class="stat-num" style="color:#00c896">{madlan_count}</div>
      <div class="stat-label">מדלן</div>
    </div>
    <div class="stat">
      <div class="stat-num" style="color:#ff6b35">{homeless_count}</div>
      <div class="stat-label">הומלס</div>
    </div>
    <div class="stat">
      <div class="stat-num">{len(listings)}</div>
      <div class="stat-label">סה"כ</div>
    </div>
  </div>
</div>

<div class="filters">
  <span class="filters-label">סנן:</span>
  <button class="filter-btn active" data-source="all" style="--c:#4a9eff" onclick="filterSource(this)">הכל</button>
  {filter_btns}
</div>

<div class="section">
  <h2>📋 מודעות — {MAX_DAYS} ימים אחרונים</h2>
  {'<div class="grid" id="listings-grid">' + cards_html + '</div>' if listings else empty_msg}
</div>

<div class="yad2-banner">
  <div class="yad2-box">
    <div class="yad2-text">🔴 <strong>יד2</strong> — חיפוש ידני (חסום לגרידה אוטומטית)</div>
    <a href="{YAD2_URL}" target="_blank" class="btn" style="background:#e94560;white-space:nowrap">
      לחיפוש ביד2 ←
    </a>
  </div>
</div>

<footer>
  מקור: פייסבוק · מדלן · הומלס · {date_str}<br>
  <a href="{SITE_URL}">{SITE_URL}</a>
</footer>

<script>
function filterSource(btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  const s = btn.dataset.source;
  document.querySelectorAll('.card').forEach(c => {{
    c.style.display = (s === 'all' || c.dataset.source === s) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""


# ── מייל ─────────────────────────────────────────────────────────────────────

def send_notification_email(date_str: str, listings: list[dict], app_password: str):
    print("📧 שולח מייל...")
    total        = len(listings)
    fb_count     = sum(1 for i in listings if i["source"] == "facebook")
    madlan_count = sum(1 for i in listings if i["source"] == "madlan")
    hl_count     = sum(1 for i in listings if i["source"] == "homeless")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🏠 {total} מודעות ברמת גן · {date_str}"
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
        '</div>'
        '<div style="padding:28px 32px;direction:rtl;">'
        '<p style="font-size:16px;color:#333;">היי מירית! 👋</p>'
        f'<p style="font-size:15px;color:#555;">נמצאו '
        f'<strong style="color:#4a9eff;">{total} מודעות</strong> '
        f'ב-{MAX_DAYS} הימים האחרונים:</p>'
        '<ul style="margin:16px 0;padding-right:20px;color:#555;font-size:14px;line-height:2">'
        f'<li>🔵 <strong style="color:#1877f2">פייסבוק:</strong> {fb_count} פוסטים</li>'
        f'<li>🟢 <strong style="color:#00c896">מדלן:</strong> {madlan_count} מודעות</li>'
        f'<li>🟠 <strong style="color:#ff6b35">הומלס:</strong> {hl_count} מודעות</li>'
        '</ul>'
        '<div style="text-align:center;margin:28px 0;">'
        f'<a href="{SITE_URL}" style="background:#4a9eff;color:#fff;text-decoration:none;'
        'padding:14px 36px;border-radius:8px;font-size:16px;font-weight:bold;">לצפייה בכל המודעות ←</a>'
        '</div>'
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


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    if "--setup" in sys.argv:
        setup_facebook_cookies()
        return

    app_password = os.environ.get("GMAIL_APP_PASSWORD", "").replace('\xa0', '').replace(' ', '').strip()
    if not app_password:
        print("❌ GMAIL_APP_PASSWORD לא מוגדר")
        sys.exit(1)

    date_str = get_date_str()
    issue    = get_issue_number()
    print(f"📅 מייצר עדכון — {date_str} (עדכון #{issue})")

    listings = scrape_all()

    fb_n  = sum(1 for i in listings if i["source"] == "facebook")
    md_n  = sum(1 for i in listings if i["source"] == "madlan")
    hl_n  = sum(1 for i in listings if i["source"] == "homeless")
    print(f'\n📊 סה"כ: {len(listings)} מודעות | פייסבוק: {fb_n} | מדלן: {md_n} | הומלס: {hl_n}')

    html = build_html(listings, date_str, issue)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ index.html נשמר ({len(html):,} תווים)")

    send_notification_email(date_str, listings, app_password)


if __name__ == "__main__":
    main()
