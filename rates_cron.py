# -*- coding: utf-8 -*-
"""
صرافی فروزانفر — پست خودکار نرخ دلار آزاد (GitHub Actions)
بهبودها:
- هشتگ‌ها و آیدی کانال (اختیاری با ENV)
- درصد تغییر (اگر قابل محاسبه باشد)
- آستانه‌ی حداقل تغییر برای ارسال (MIN_CHANGE_TOMAN)
"""

import os
import requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from requests.adapters import HTTPAdapter, Retry

# ---------- تنظیمات ----------
BOT_TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN")                # GitHub Secret
NAVASAN_KEY     = os.getenv("NAVASAN_API_KEY")                   # GitHub Secret
CHANNEL         = os.getenv("TELEGRAM_CHANNEL", "@Foorouzanfar")
TIMEZONE        = os.getenv("TIMEZONE", "Asia/Tehran")
MESSAGE_HEADER  = os.getenv("MESSAGE_HEADER", "📣 صرافی فروزانفر — بروزرسانی دلار آزاد")
SOURCE_LABEL    = os.getenv("SOURCE_LABEL", "نوسان")
HASHTAGS        = os.getenv("HASHTAGS", "#دلار #نرخ_دلار #صرافی_فروزانفر")
CHANNEL_HANDLE  = os.getenv("CHANNEL_HANDLE", "@Foorouzanfar")   # انتهای پیام
# اگر تغییر کمتر از این مقدار (تومان) بود، پیام ارسال نشود (۰ = همیشه ارسال شود)
MIN_CHANGE_TOMAN = float(os.getenv("MIN_CHANGE_TOMAN", "0"))

def _session():
    s = requests.Session()
    retries = Retry(
        total=3, backoff_factor=0.6,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "POST"])
    )
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

def fetch_usd_from_navasan(session):
    if not NAVASAN_KEY:
        raise RuntimeError("NAVASAN_API_KEY تنظیم نشده است.")
    r = session.get("http://api.navasan.tech/latest/", params={"api_key": NAVASAN_KEY}, timeout=20)
    r.raise_for_status()
    data = r.json()
    usd = data.get("usd_sell") or data.get("usd") or {}
    if not usd:
        raise RuntimeError("پاسخ Navasan فاقد usd/usd_sell است.")
    val = float(usd.get("value") or 0)        # تومان
    chg = usd.get("change")                   # تغییر (تومان) - ممکن است None باشد
    ts  = usd.get("date") or ""               # زمان منبع (رشته)
    if val <= 0:
        raise RuntimeError("مقدار دلار معتبر نیست.")
    # محاسبه درصد تغییر اگر ممکن بود:
    pct = None
    try:
        if chg not in (None, "", 0, "0"):
            pct = (float(chg) / (val - float(chg))) * 100.0
    except Exception:
        pct = None
    return val, chg, pct, ts

def send_to_telegram(session, text):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = session.post(url, data=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"ارسال تلگرام ناموفق بود: {r.status_code} {r.text}")

def build_message(usd_value, usd_change, usd_pct, provider_ts):
    # خط عنوان
    header = MESSAGE_HEADER

    # خط قیمت + تغییر
    price = f"💵 دلار آزاد: <b>{fmt(usd_value)}</b> تومان"
    if usd_change not in (None, "", 0, "0"):
        try:
            chg_val = float(usd_change)
            sign = "🔺" if chg_val > 0 else "🔻"
            price += f" ({sign}{fmt(chg_val)})"
            if usd_pct is not None:
                # درصد را با دو رقم اعشار نشان بده
                price += f" ~ {sign}{abs(usd_pct):.2f}%"
        except Exception:
            pass

    # زمان فعلی
    when = now_text()

    # منبع
    footer = f"منبع: {SOURCE_LABEL}"
    if provider_ts:
        footer += f" — به‌روزرسانی منبع: {provider_ts}"

    # هشتگ‌ها + آیدی کانال
    tags = HASHTAGS.strip()
    ch = CHANNEL_HANDLE.strip()
    tail = " ".join(x for x in [tags, ch] if x)

    # جداکننده ظریف
    sep = "—" * 12

    lines = [header, price, when, footer, sep, tail]
    return "\n".join([l for l in lines if l.strip()])

def main():
    s = _session()
    usd_value, usd_change, usd_pct, provider_ts = fetch_usd_from_navasan(s)

    # اگر آستانه‌ی حداقل تغییر تعریف شده و تغییر کوچک‌تر از آن بود: ارسال نکن
    try:
        if MIN_CHANGE_TOMAN > 0 and usd_change not in (None, "", "0", 0):
            if abs(float(usd_change)) < MIN_CHANGE_TOMAN:
                print({"ok": True, "posted": False, "reason": "small_change", "usd_value": usd_value, "usd_change": usd_change})
                return
    except Exception:
        pass

    msg = build_message(usd_value, usd_change, usd_pct, provider_ts)
    send_to_telegram(s, msg)
    print({"ok": True, "posted": True, "usd_value": usd_value})

if __name__ == "__main__":
    main()
