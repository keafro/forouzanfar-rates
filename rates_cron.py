# -*- coding: utf-8 -*-
"""
صرافی فروزانفر — پست خودکار همهٔ نرخ‌های مهم از نوسان (در یک پیام)
- فقط یک درخواست به /latest می‌زنیم؛ رایگان می‌ماند.
- پوشش: اسکناس نقدی (خرید/فروش)، حواله، صرافی ملی، سکه/طلا، رمزارز.
- هر نمادی که در پاسخ نبود، خودکار حذف می‌شود (Safe).
- قابلیت تنظیم با ENV بدون تغییر کد (برچسب‌ها، هشتگ‌ها، حداقل تغییر، دسته‌ها).
"""

import os
import requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from requests.adapters import HTTPAdapter, Retry

# --------- تنظیمات از ENV (Secrets و Variables) ---------
BOT_TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN")              # Secret
NAVASAN_KEY     = os.getenv("NAVASAN_API_KEY")                 # Secret
CHANNEL         = os.getenv("TELEGRAM_CHANNEL", "@Foorouzanfar")
TIMEZONE        = os.getenv("TIMEZONE", "Asia/Tehran")
MESSAGE_HEADER  = os.getenv("MESSAGE_HEADER", "📣 صرافی فروزانفر — بروزرسانی نرخ‌ها")
SOURCE_LABEL    = os.getenv("SOURCE_LABEL", "نوسان")
HASHTAGS        = os.getenv("HASHTAGS", "#دلار #یورو #سکه #طلا #حواله #صرافی_فروزانفر")
CHANNEL_HANDLE  = os.getenv("CHANNEL_HANDLE", "@Foorouzanfar")
MIN_CHANGE_TOMAN = float(os.getenv("MIN_CHANGE_TOMAN", "0"))   # آستانه تغییر برای «دلار فروش تهران»
# دسته‌هایی که می‌خواهیم نمایش بدهیم (با کاما جدا): cash, remittance, melli, goldcoin, crypto
INCLUDE_CATEGORIES = set(s.strip().lower() for s in os.getenv(
    "INCLUDE_CATEGORIES",
    "cash,remittance,melli,goldcoin,crypto"
).split(",") if s.strip())

# --------- کمک‌تابع‌ها ---------
def _session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6,
                    status_forcelist=(429, 500, 502, 503, 504),
                    allowed_methods=frozenset(["GET", "POST"]))
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def fmt(n):
    try:
        return f"{int(float(n)):,}".replace(",", "،")
    except Exception:
        return str(n)

def now_text():
    try:
        tz = ZoneInfo(TIMEZONE) if ZoneInfo else None
    except Exception:
        tz = None
    dt = datetime.now(tz) if tz else datetime.utcnow()
    suffix = f" ({TIMEZONE})" if tz else " (UTC)"
    return dt.strftime("تاریخ و ساعت: %Y/%m/%d — %H:%M") + suffix

# برچسب‌های فارسی برای نمادها (برگرفته از راهنمای نمادهای نوسان)
NICE = {
    # اسکناس نقدی (بازار آزاد)
    "usd_sell": "دلار تهران (فروش)", "usd_buy": "دلار تهران (خرید)",
    "eur_sell": "یورو (فروش)", "eur_buy": "یورو (خرید)",
    "aed_sell": "درهم (فروش)", "dirham_dubai": "درهم دبی",
    "harat_naghdi_sell": "دلار هرات (فروش)", "harat_naghdi_buy": "دلار هرات (خرید)",
    "dolar_harat_sell": "دلار هرات (فروش نقد)",
    "dolar_soleimanie_sell": "دلار سلیمانیه (فروش)",
    "dolar_kordestan_sell": "دلار کردستان (فروش)",
    "dolar_mashad_sell": "دلار مشهد (فروش)",

    # حواله‌ها
    "usd_shakhs": "دلار حواله (شخص)",
    "usd_sherkat": "دلار حواله (شرکت)",
    "eur_hav": "یورو حواله", "gbp_hav": "پوند حواله", "try_hav": "لیر حواله",
    "jpy_hav": "ین حواله", "cny_hav": "یوان حواله", "aud_hav": "دلار استرالیا حواله",
    "cad_hav": "دلار کانادا حواله",

    # صرافی ملی (Melli-Ex)
    "mex_usd_buy": "دلار صرافی ملی (خرید)", "mex_usd_sell": "دلار صرافی ملی (فروش)",
    "mex_eur_buy": "یورو صرافی ملی (خرید)", "mex_eur_sell": "یورو صرافی ملی (فروش)",

    # سکه و طلا
    "sekke": "سکه امامی", "sekkeh": "سکه امامی", "bahar": "سکه بهار",
    "nim": "نیم سکه", "rob": "ربع سکه", "gerami": "سکه گرمی",
    "18ayar": "طلا ۱۸ عیار/گرم", "abshodeh": "مثقال طلا (آبشده)",
    "xau": "اونس جهانی طلا", "usd_xau": "طلا (XAU/USD)",
    "bub_sekkeh": "حباب سکه امامی", "bub_bahar": "حباب سکه بهار",
    "bub_nim": "حباب نیم‌سکه", "bub_rob": "حباب ربع‌سکه", "bub_gerami": "حباب گرمی", "bub_18ayar": "حباب طلا ۱۸",

    # رمزارزها (اگر در خروجی بود)
    "btc": "بیت‌کوین", "eth": "اتریوم", "ltc": "لایت‌کوین", "xrp": "ریپل",
    "bch": "بیت‌کوین‌کش", "bnb": "بایننس‌کوین", "dash": "دش", "eos": "ایاس", "usdt": "تتر",
}

# دسته‌بندی‌ها برای گروه‌بندی خروجی
CATEGORIES = {
    "cash": {
        "emoji": "💵",
        "keys": [
            "usd_sell","usd_buy","eur_sell","eur_buy","aed_sell","dirham_dubai",
            "harat_naghdi_sell","harat_naghdi_buy","dolar_harat_sell",
            "dolar_soleimanie_sell","dolar_kordestan_sell","dolar_mashad_sell",
        ],
        "title": "اسکناس (نقدی)"
    },
    "remittance": {
        "emoji": "🔁",
        "keys": [
            "usd_shakhs","usd_sherkat","eur_hav","gbp_hav","try_hav","jpy_hav","cny_hav","aud_hav","cad_hav",
        ],
        "title": "حواله ارزی"
    },
    "melli": {
        "emoji": "🏦",
        "keys": ["mex_usd_buy","mex_usd_sell","mex_eur_buy","mex_eur_sell"],
        "title": "صرافی ملی"
    },
    "goldcoin": {
        "emoji": "🪙",
        "keys": ["sekke","sekkeh","bahar","nim","rob","gerami","18ayar","abshodeh","xau","usd_xau",
                 "bub_sekkeh","bub_bahar","bub_nim","bub_rob","bub_gerami","bub_18ayar"],
        "title": "سکه و طلا"
    },
    "crypto": {
        "emoji": "₿",
        "keys": ["btc","eth","ltc","xrp","bch","bnb","dash","eos","usdt"],
        "title": "رمزارز"
    },
}

def fetch_latest(session):
    if not NAVASAN_KEY:
        raise RuntimeError("NAVASAN_API_KEY تنظیم نشده است.")
    r = session.get("http://api.navasan.tech/latest/", params={"api_key": NAVASAN_KEY}, timeout=20)
    r.raise_for_status()
    return r.json()

def _line_from_item(key, item):
    """خط یک نماد را می‌سازد: نام، قیمت، تغییر، درصد."""
    if not isinstance(item, dict) or item.get("value") is None:
        return None
    val = float(item.get("value") or 0)
    chg = item.get("change")
    line = f"• {NICE.get(key, key)}: <b>{fmt(val)}</b> تومان"
    try:
        if chg not in (None, "", 0, "0"):
            chg_f = float(chg)
            sign = "🔺" if chg_f > 0 else "🔻"
            line += f" ({sign}{fmt(chg_f)})"
            base = val - chg_f
            if base != 0:
                pct = (chg_f / base) * 100.0
                line += f" ~ {sign}{abs(pct):.2f}%"
    except Exception:
        pass
    return line

def build_sections(latest: dict):
    """بر اساس دسته‌ها، خطوط هر گروه را می‌سازد."""
    sections = []
    for cat_key, meta in CATEGORIES.items():
        if cat_key not in INCLUDE_CATEGORIES:
            continue
        lines = []
        for k in meta["keys"]:
            item = latest.get(k)
            line = _line_from_item(k, item)
            if line:
                lines.append(line)
        if lines:
            title = f"{meta['emoji']} {meta['title']}"
            sections.append("\n".join([title, *lines]))
    return sections

def send_to_telegram(session, text):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = session.post(url, data=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"ارسال تلگرام ناموفق بود: {r.status_code} {r.text}")

def main():
    s = _session()
    latest = fetch_latest(s)

    # اگر آستانه حداقل تغییر تعریف شده: بر اساس دلار فروش تهران بررسی می‌کنیم
    if MIN_CHANGE_TOMAN > 0:
        base = latest.get("usd_sell") or {}
        chg = base.get("change")
        try:
            if chg not in (None, "", 0, "0") and abs(float(chg)) < MIN_CHANGE_TOMAN:
                print({"ok": True, "posted": False, "reason": "small_change", "usd_change": chg})
                return
        except Exception:
            pass

    sections = build_sections(latest)
    if not sections:
        raise RuntimeError("هیچ نمادی برای نمایش یافت نشد. احتمالاً کلیدها/دسته‌ها در پاسخ موجود نبودند.")

    # زمان منبع (از یکی از نمادها)
    provider_ts = ""
    for sec_keys in CATEGORIES.values():
        for k in sec_keys["keys"]:
            if isinstance(latest.get(k), dict):
                provider_ts = latest[k].get("date") or ""
                if provider_ts:
                    break
        if provider_ts:
            break

    header = MESSAGE_HEADER
    when = now_text()
    footer = f"منبع: {SOURCE_LABEL}" + (f" — به‌روزرسانی منبع: {provider_ts}" if provider_ts else "")

    sep = "—" * 12
    tags = " ".join(x for x in [HASHTAGS.strip(), CHANNEL_HANDLE.strip()] if x)

    body = "\n\n".join(sections)
    msg = "\n".join([header, body, when, footer, sep, tags])

    # اگر پیام خیلی بلند شد و از محدودیت تلگرام (4096 کاراکتر) گذشت، کمی خلاصه می‌کنیم
    if len(msg) > 3800:
        # اول رمزارز و حباب‌ها را حذف می‌کنیم
        global INCLUDE_CATEGORIES
        INCLUDE_CATEGORIES = {c for c in INCLUDE_CATEGORIES if c not in {"crypto"}}
        sections = build_sections(latest)
        body = "\n\n".join(sections)
        msg = "\n".join([header, body, when, footer, sep, tags])[:4000]

    send_to_telegram(s, msg)
    print({"ok": True, "posted": True})

if __name__ == "__main__":
    main()
