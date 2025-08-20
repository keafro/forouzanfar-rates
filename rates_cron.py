# -*- coding: utf-8 -*-
"""
صرافی فروزانفر — ارسال خودکار نرخ دلار آزاد با GitHub Actions (بدون سرور)
منبع: Navasan (۱۲۰ درخواست/ماه → امن: ۳ بار در روز)
"""
import os
import requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
from requests.adapters import HTTPAdapter, Retry

BOT_TOKEN      = os.getenv("TELEGRAM_BOT_TOKEN")            # از GitHub Secrets
NAVASAN_KEY    = os.getenv("NAVASAN_API_KEY")               # از GitHub Secrets
CHANNEL        = os.getenv("TELEGRAM_CHANNEL", "@Foorouzanfar")
TIMEZONE       = os.getenv("TIMEZONE", "Asia/Tehran")
MESSAGE_HEADER = os.getenv("MESSAGE_HEADER", "📣 صرافی فروزانفر — بروزرسانی دلار آزاد")
SOURCE_LABEL   = os.getenv("SOURCE_LABEL", "نوسان")

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
    val = float(usd.get("value") or 0)
    chg = usd.get("change")
    ts  = usd.get("date") or ""
    if val <= 0:
        raise RuntimeError("مقدار دلار معتبر نیست.")
    return val, chg, ts

def send_to_telegram(session, text):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = session.post(url, data=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"ارسال تلگرام ناموفق بود: {r.status_code} {r.text}")

def build_message(usd_value, usd_change, provider_ts):
    line = f"💵 دلار آزاد: <b>{fmt(usd_value)}</b> تومان"
    if usd_change not in (None, "", 0, "0"):
        try:
            sign = "🔺" if float(usd_change) > 0 else "🔻"
            line += f" ({sign}{fmt(usd_change)})"
        except Exception:
            pass
    footer = f"منبع: {SOURCE_LABEL}"
    if provider_ts:
        footer += f" — به‌روزرسانی منبع: {provider_ts}"
    return f"{MESSAGE_HEADER}\n{line}\n{now_text()}\n{footer}"

def main():
    s = _session()
    usd_value, usd_change, provider_ts = fetch_usd_from_navasan(s)
    msg = build_message(usd_value, usd_change, provider_ts)
    send_to_telegram(s, msg)
    print({"ok": True, "posted": True, "usd_value": usd_value})

if __name__ == "__main__":
    main()
