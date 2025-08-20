# -*- coding: utf-8 -*-
"""
صرافی صلاح‌الدین — ربات ساده و پایدار
حالت‌ها با ENV تعیین می‌شود:
- MODE=greet : پیام صبح بخیر + نام روز + تاریخ شمسی/میلادی
- MODE=rates : نرخ‌های کلیدی ارز/طلا/سکه از API «نوسان»
- MODE=close : پیام شب بخیر/پایان روز

تنظیمات لازم (ENV):
- TELEGRAM_BOT_TOKEN  (توکن بات)
- TELEGRAM_CHANNEL    (مثل @Saladinir یا chat_id عددی)
- NAVASAN_API_KEY     (کلید نوسان؛ فقط برای MODE=rates لازم است)
- TIMEZONE            (پیش‌فرض Asia/Tehran)

کتابخانه‌ها: requests, jdatetime, hijri-converter (اختیاری برای قمری، ولی اینجا استفاده نمی‌کنیم)
"""

import os
import requests
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

try:
    import jdatetime  # فقط برای تاریخ شمسی در پیام صبح/شب
except Exception:
    jdatetime = None

# ------------------ ENV ------------------
MODE       = os.getenv("MODE", "rates").strip().lower()
BOT_TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL    = os.getenv("TELEGRAM_CHANNEL", "@Saladinir")
TIMEZONE   = os.getenv("TIMEZONE", "Asia/Tehran")
API_KEY    = os.getenv("NAVASAN_API_KEY")  # فقط برای rates

BRAND      = "📣 صرافی صلاح‌الدین"
HASHTAGS   = "#دلار #یورو #سکه #طلا #صرافی_صلاح_الدین"
HANDLE     = "@Saladinir"

# ------------------ Time helpers ------------------
def now_dt():
    try:
        tz = ZoneInfo(TIMEZONE) if ZoneInfo else None
    except Exception:
        tz = None
    return datetime.now(tz) if tz else datetime.utcnow()

def today_fa_and_en():
    """نام روز و تاریخ‌های شمسی/میلادی برمی‌گرداند."""
    dt = now_dt()
    greg = dt.strftime("%Y-%m-%d")
    weekday_fa = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"][dt.weekday()]
    if jdatetime:
        jdt = jdatetime.datetime.fromgregorian(datetime=dt)
        jalali = jdt.strftime("%Y/%m/%d")
    else:
        jalali = "—"
    return weekday_fa, jalali, greg

def now_line():
    dt = now_dt()
    return dt.strftime("تاریخ و ساعت: %Y/%m/%d — %H:%M") + f" ({TIMEZONE})"

# ------------------ Telegram ------------------
def send_message(text: str):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"ارسال تلگرام ناموفق بود: {r.status_code} {r.text}")

# ------------------ Rates (Navasan) ------------------
NICE = {
    "usd_sell": "دلار تهران (فروش)",
    "usd_buy":  "دلار تهران (خرید)",
    "eur_sell": "یورو (فروش)",
    "aed_sell": "درهم (فروش)",
    "mex_usd_sell": "دلار صرافی ملی (فروش)",
    "mex_eur_sell": "یورو صرافی ملی (فروش)",
    "sekke":    "سکه امامی",
    "18ayar":   "طلا ۱۸ عیار/گرم",
}

SELECTION = [
    "usd_sell", "usd_buy", "eur_sell", "aed_sell",
    "mex_usd_sell", "mex_eur_sell",
    "sekke", "18ayar",
]

def fmt(n):
    try:
        return f"{int(float(n)):,}".replace(",", "،")
    except Exception:
        return str(n)

def arrow(change):
    try:
        c = float(change)
        return "🟢🔺" if c > 0 else "🔴🔻" if c < 0 else "•"
    except Exception:
        return "•"

def fetch_latest():
    if not API_KEY:
        raise RuntimeError("NAVASAN_API_KEY تنظیم نشده است.")
    url = "http://api.navasan.tech/latest/"
    r = requests.get(url, params={"api_key": API_KEY}, timeout=20)
    r.raise_for_status()
    return r.json()

def format_rates(latest: dict):
    # تیتر + زمان بالای پیام
    parts = [f"{BRAND} — بروزرسانی نرخ‌ها", now_line(), ""]
    # بدنه
    lines = []
    for key in SELECTION:
        item = latest.get(key)
        if not isinstance(item, dict) or item.get("value") in (None, "", 0, "0"):
            continue
        val  = fmt(item["value"])
        ch   = item.get("change")
        emj  = arrow(ch) if ch not in (None, "", 0, "0") else "•"
        ln   = f"• {NICE.get(key, key)}: <b>{val} تومان</b>"
        # درصد تغییر اگر معقول بود (<= 50%)
        try:
            chf = float(ch)
            base = float(item["value"]) - chf
            pct = (chf / base) * 100 if base else 0.0
            if abs(pct) <= 50 and ch not in (None, "", 0, "0"):
                sign = "🔺" if chf > 0 else "🔻"
                ln += f" ({emj}{fmt(abs(chf))}) ~ {sign}{abs(pct):.2f}%"
        except Exception:
            if ch not in (None, "", 0, "0"):
                ln += f" ({emj}{fmt(abs(float(ch)))})"
        lines.append(ln)

    if not lines:
        lines = ["(داده‌ای برای نمایش موجود نیست)"]

    # برچسب منبع (از هر آیتم یک تاریخ منبع بگیریم اگر بود)
    provider_ts = ""
    for key in SELECTION:
        item = latest.get(key)
        if isinstance(item, dict) and item.get("date"):
            provider_ts = item["date"]
            break

    parts.append("💵 <b>ارز</b>")
    for k in ["usd_sell", "usd_buy", "eur_sell", "aed_sell", "mex_usd_sell", "mex_eur_sell"]:
        for ln in lines:
            if NICE.get(k, k) in ln:
                parts.append(ln)

    parts.append("")
    parts.append("🪙 <b>سکه و طلا</b>")
    for k in ["sekke", "18ayar"]:
        for ln in lines:
            if NICE.get(k, k) in ln:
                parts.append(ln)

    parts.append("")
    parts.append(f"منبع: نوسان" + (f" — به‌روزرسانی منبع: {provider_ts}" if provider_ts else ""))
    parts.append("—" * 12)
    parts.append(f"{HASHTAGS} {HANDLE}")

    return "\n".join(parts)

# ------------------ Messages ------------------
def do_greet():
    weekday_fa, jalali, greg = today_fa_and_en()
    msg = (
        "━━━━━━━━━━━━━━━\n"
        "🌅 صبح بخیر از صرافی صلاح‌الدین\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"امروز: <b>{weekday_fa}</b>\n"
        f"📅 شمسی: <b>{jalali}</b>\n"
        f"📆 میلادی: <b>{greg}</b>\n\n"
        f"{now_line()}\n"
        + "—"*12 + "\n"
        + f"{HASHTAGS} {HANDLE}"
    )
    send_message(msg)

def do_close():
    weekday_fa, jalali, greg = today_fa_and_en()
    msg = (
        "━━━━━━━━━━━━━━━\n"
        "🌙 شب‌بخیر — پایان معاملات امروز\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"امروز: <b>{weekday_fa}</b>\n"
        f"📅 شمسی: <b>{jalali}</b>\n"
        f"📆 میلادی: <b>{greg}</b>\n\n"
        "تا فردا با بروزرسانی‌های جدید در خدمتیم.\n\n"
        f"{now_line()}\n"
        + "—"*12 + "\n"
        + f"{HASHTAGS} {HANDLE}"
    )
    send_message(msg)

def do_rates():
    latest = fetch_latest()
    text = format_rates(latest)
    send_message(text)

# ------------------ Main ------------------
def main():
    if MODE == "greet":
        do_greet()
    elif MODE == "close":
        do_close()
    else:
        do_rates()

if __name__ == "__main__":
    main()
