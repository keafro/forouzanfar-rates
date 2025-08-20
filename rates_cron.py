# -*- coding: utf-8 -*-
"""
کانال صرافی فروزانفر — سه حالت:
- MODE=rates : ارسال نرخ‌ها (۱ تماس به Navasan)
- MODE=greet : پیام صبح‌بخیر با تاریخ میلادی/شمسی/قمری
- MODE=close : پیام پایان معاملات شب

ویژگی‌ها:
- ایموجی سبز/قرمز (🟢🔺 / 🔴🔻) برای جهت تغییر
- دسته‌بندی منظم: اسکناس، حواله، صرافی ملی، سکه/طلا (کریپتو حذف)
- خلاصه «بیشترین تغییرها» (Top Movers) مثبت/منفی
- محدودکننده تعداد خطوط هر دسته (TOP_N_PER_CATEGORY)
- عددهای خیلی بزرگ: نمایش فشرده (میلیون/میلیارد)
- آستانه حداقل تغییر (MIN_CHANGE_TOMAN) روی دلار فروش تهران
"""

import os
import requests
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
try:
    import jdatetime
except Exception:
    jdatetime = None
try:
    from hijri_converter import convert
except Exception:
    convert = None

from requests.adapters import HTTPAdapter, Retry

# ---------- تنظیمات از ENV ----------
MODE             = os.getenv("MODE", "rates").strip().lower()
BOT_TOKEN        = os.getenv("TELEGRAM_BOT_TOKEN")
NAVASAN_KEY      = os.getenv("NAVASAN_API_KEY")
CHANNEL          = os.getenv("TELEGRAM_CHANNEL", "@Foorouzanfar")
TIMEZONE         = os.getenv("TIMEZONE", "Asia/Tehran")
MESSAGE_HEADER   = os.getenv("MESSAGE_HEADER", "📣 صرافی فروزانفر — بروزرسانی نرخ‌ها")
SOURCE_LABEL     = os.getenv("SOURCE_LABEL", "نوسان")
HASHTAGS         = os.getenv("HASHTAGS", "#دلار #یورو #سکه #طلا #حواله #صرافی_فروزانفر")
CHANNEL_HANDLE   = os.getenv("CHANNEL_HANDLE", "@Foorouzanfar")
MIN_CHANGE_TOMAN = float(os.getenv("MIN_CHANGE_TOMAN", "0"))
INCLUDE_CATEGORIES = set(s.strip().lower() for s in os.getenv(
    "INCLUDE_CATEGORIES", "cash,remittance,melli,goldcoin"
).split(",") if s.strip())
TOP_N_PER_CATEGORY = int(os.getenv("TOP_N_PER_CATEGORY", "3"))

# ---------- ابزارها ----------
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

def fmt_compact_tmn(n):
    try:
        v = float(n)
    except Exception:
        return fmt(n) + " تومان"
    if abs(v) >= 1_000_000_000:
        return f"{v/1_000_000_000:.2f} میلیارد تومان"
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.2f} میلیون تومان"
    return f"{fmt(v)} تومان"

def now_dt():
    try:
        tz = ZoneInfo(TIMEZONE) if ZoneInfo else None
    except Exception:
        tz = None
    return datetime.now(tz) if tz else datetime.utcnow()

def now_text():
    dt = now_dt()
    suffix = f" ({TIMEZONE})" if ZoneInfo else " (UTC)"
    return dt.strftime("تاریخ و ساعت: %Y/%m/%d — %H:%M") + suffix

def today_multi_calendars():
    dt = now_dt()
    g = dt.strftime("%Y-%m-%d")
    if jdatetime:
        jd = jdatetime.datetime.fromgregorian(datetime=dt)
        sh = jd.strftime("%Y/%m/%d")
    else:
        sh = "—"
    if convert:
        h = convert.Gregorian(dt.year, dt.month, dt.day).to_hijri()
        gh = f"{h.year}/{h.month:02d}/{h.day:02d}"
    else:
        gh = "—"
    weekdays_fa = ["دوشنبه","سه‌شنبه","چهارشنبه","پنجشنبه","جمعه","شنبه","یکشنبه"]
    wd = weekdays_fa[dt.weekday()] if 0 <= dt.weekday() < 7 else ""
    return wd, g, sh, gh

# ---------- برچسب‌ها و دسته‌ها ----------
NICE = {
    # Cash
    "usd_sell":"دلار تهران (فروش)","usd_buy":"دلار تهران (خرید)",
    "eur_sell":"یورو (فروش)","eur_buy":"یورو (خرید)",
    "aed_sell":"درهم (فروش)","dirham_dubai":"درهم دبی",
    "harat_naghdi_sell":"دلار هرات (فروش)","harat_naghdi_buy":"دلار هرات (خرید)",
    "dolar_harat_sell":"دلار هرات (فروش نقد)","dolar_soleimanie_sell":"دلار سلیمانیه (فروش)",
    "dolar_kordestan_sell":"دلار کردستان (فروش)","dolar_mashad_sell":"دلار مشهد (فروش)",
    # Remittance
    "usd_shakhs":"دلار حواله (شخص)","usd_sherkat":"دلار حواله (شرکت)",
    "eur_hav":"یورو حواله","gbp_hav":"پوند حواله","try_hav":"لیر حواله",
    "jpy_hav":"ین حواله","cny_hav":"یوان حواله","aud_hav":"دلار استرالیا حواله","cad_hav":"دلار کانادا حواله",
    # Melli
    "mex_usd_buy":"دلار صرافی ملی (خرید)","mex_usd_sell":"دلار صرافی ملی (فروش)",
    "mex_eur_buy":"یورو صرافی ملی (خرید)","mex_eur_sell":"یورو صرافی ملی (فروش)",
    # Gold & Coin
    "sekke":"سکه امامی","sekkeh":"سکه امامی","bahar":"سکه بهار",
    "nim":"نیم‌سکه","rob":"ربع‌سکه","gerami":"سکه گرمی",
    "18ayar":"طلا ۱۸ عیار/گرم","abshodeh":"مثقال طلا (آبشده)",
    "xau":"اونس جهانی طلا","usd_xau":"طلا (XAU/USD)",
    "bub_sekkeh":"حباب سکه امامی","bub_bahar":"حباب سکه بهار",
    "bub_nim":"حباب نیم‌سکه","bub_rob":"حباب ربع‌سکه","bub_gerami":"حباب گرمی","bub_18ayar":"حباب طلا ۱۸",
}

CATEGORIES = {
    "cash": {"emoji":"💵","title":"اسکناس (نقدی)","keys":[
        "usd_sell","usd_buy","eur_sell","eur_buy","aed_sell","dirham_dubai",
        "harat_naghdi_sell","harat_naghdi_buy","dolar_harat_sell",
        "dolar_soleimanie_sell","dolar_kordestan_sell","dolar_mashad_sell",
    ]},
    "remittance": {"emoji":"🔁","title":"حواله ارزی","keys":[
        "usd_shakhs","usd_sherkat","eur_hav","gbp_hav","try_hav","jpy_hav","cny_hav","aud_hav","cad_hav",
    ]},
    "melli": {"emoji":"🏦","title":"صرافی ملی","keys":[
        "mex_usd_buy","mex_usd_sell","mex_eur_buy","mex_eur_sell",
    ]},
    "goldcoin": {"emoji":"🪙","title":"سکه و طلا","keys":[
        "sekke","sekkeh","bahar","nim","rob","gerami","18ayar","abshodeh","xau","usd_xau",
        "bub_sekkeh","bub_bahar","bub_nim","bub_rob","bub_gerami","bub_18ayar",
    ]},
}

# ---------- دریافت داده ----------
def fetch_latest(session):
    if MODE == "rates":
        if not NAVASAN_KEY:
            raise RuntimeError("NAVASAN_API_KEY تنظیم نشده است.")
        r = session.get("http://api.navasan.tech/latest/", params={"api_key": NAVASAN_KEY}, timeout=20)
        r.raise_for_status()
        return r.json()
    return {}

# ---------- نمایش تغییر ----------
def _change_emoji(chg):
    try:
        v = float(chg)
        return "🟢🔺" if v > 0 else "🔴🔻" if v < 0 else "•"
    except Exception:
        return "•"

def _line_for_item(key, item):
    if not isinstance(item, dict) or item.get("value") is None:
        return None
    val = float(item.get("value") or 0)
    chg = item.get("change")
    ch_emoji = _change_emoji(chg) if chg not in (None,"",0,"0") else "•"
    value_txt = f"{fmt(val)} تومان"

    line = f"• {NICE.get(key, key)}: <b>{value_txt}</b>"
    try:
        if chg not in (None, "", 0, "0"):
            chg_f = float(chg)
            base = val - chg_f
            pct = (chg_f / base) * 100.0 if base else 0.0
            sign = "🔺" if chg_f > 0 else "🔻"
            chg_text = fmt(abs(chg_f))  # علامت منفی را حذف می‌کنیم
            line += f" ({ch_emoji}{chg_text})"
            if abs(pct) <= 50:
                line += f" ~ {sign}{abs(pct):.2f}%"
    except Exception:
        pass
    return line

def build_sections(latest):
    sections = []
    for cat, meta in CATEGORIES.items():
        if cat not in INCLUDE_CATEGORIES:
            continue
        lines = []
        for k in meta["keys"]:
            ln = _line_for_item(k, latest.get(k))
            if ln:
                lines.append(ln)
        if lines:
            lines = lines[:TOP_N_PER_CATEGORY]
            title = f"{meta['emoji']} <b>{meta['title']}</b>"
            sections.append("\n".join([title, *lines]))
    return sections

# ---------- Top Movers ----------
def collect_changes_for_movers(latest):
    items = []
    for cat, meta in CATEGORIES.items():
        if cat not in INCLUDE_CATEGORIES:
            continue
        for k in meta["keys"]:
            d = latest.get(k)
            if not isinstance(d, dict):
                continue
            val = d.get("value"); chg = d.get("change")
            if val in (None,"",0,"0") or chg in (None,"",0,"0"):
                continue
            try:
                val_f = float(val); chg_f = float(chg)
                base = val_f - chg_f
                pct = (chg_f / base) * 100.0 if base else 0.0
                if abs(pct) <= 50:
                    items.append((NICE.get(k, k), pct))
            except Exception:
                continue
    return items

def build_top_movers(latest, top_n=2):
    arr = collect_changes_for_movers(latest)
    if not arr:
        return ""
    ups = sorted([(n,p) for (n,p) in arr if p > 0], key=lambda x: x[1], reverse=True)[:top_n]
    dns = sorted([(n,p) for (n,p) in arr if p < 0], key=lambda x: x[1])[:top_n]
    lines = []
    if ups:
        up_texts = [f"{n} (+{abs(p):.2f}%)" for (n,p) in ups]
        lines.append("🟢 پُررشد: " + " | ".join(up_texts))
    if dns:
        dn_texts = [f"{n} (-{abs(p):.2f}%)" for (n,p) in dns]
        lines.append("🔴 پُرافـت: " + " | ".join(dn_texts))
    return "\n".join(lines)

# ---------- ارسال تلگرام ----------
def send_to_telegram(session, text):
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN تنظیم نشده است.")
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    r = session.post(url, data=payload, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"ارسال تلگرام ناموفق بود: {r.status_code} {r.text}")

# ---------- حالات اجرا ----------
def do_greet(session):
    wd, g, sh, gh = today_multi_calendars()
    msg = (
        "━━━━━━━━━━━━━━━\n"
        "🌅 صبح بخیر\n"
        "━━━━━━━━━━━━━━━\n\n"
        f"امروز: <b>{wd}</b>\n"
        f"📆 میلادی: <b>{g}</b>\n"
        f"📅 شمسی: <b>{sh}</b>\n"
        f"🗓 قمری: <b>{gh}</b>\n\n"
        f"{now_text()}\n"
        + "—"*12 + "\n"
        + f"{HASHTAGS} {CHANNEL_HANDLE}"
    )
    send_to_telegram(session, msg)

def do_close(session):
    msg = (
        "━━━━━━━━━━━━━━━\n"
        "🌙 پایان معاملات امروز\n"
        "━━━━━━━━━━━━━━━\n\n"
        "تا فردا با بروزرسانی‌های جدید همراه شما هستیم.\n"
        "شب آرام 🌟\n\n"
        f"{now_text()}\n"
        + "—"*12 + "\n"
        + f"{HASHTAGS} {CHANNEL_HANDLE}"
    )
    send_to_telegram(session, msg)

def do_rates(session):
    latest = fetch_latest(session)

    # آستانه حداقل تغییر روی دلار فروش تهران
    if MIN_CHANGE_TOMAN > 0:
        base = latest.get("usd_sell") or {}
        chg = base.get("change")
        try:
            if chg not in (None,"","0",0) and abs(float(chg)) < MIN_CHANGE_TOMAN:
                print({"ok": True, "posted": False, "reason": "small_change", "usd_change": chg})
                return
        except Exception:
            pass

    sections = build_sections(latest)
    if not sections:
        raise RuntimeError("هیچ نمادی برای نمایش یافت نشد.")

    # زمان منبع
    provider_ts = ""
    for meta in CATEGORIES.values():
        for k in meta["keys"]:
            if isinstance(latest.get(k), dict):
                provider_ts = latest[k].get("date") or ""
                if provider_ts:
                    break
        if provider_ts:
            break

    movers = build_top_movers(latest, top_n=2)

    header = MESSAGE_HEADER
    when   = now_text()
    footer = f"منبع: {SOURCE_LABEL}" + (f" — به‌روزرسانی منبع: {provider_ts}" if provider_ts else "")
    sep    = "—"*12
    tags   = " ".join(x for x in [HASHTAGS.strip(), CHANNEL_HANDLE.strip()] if x)

    body = (movers + "\n\n" if movers else "") + "\n\n".join(sections)
    msg  = "\n".join([header, when, body, footer, sep, tags])

    if len(msg) > 3950:
        msg = msg[:3950] + "\n…"

    send_to_telegram(_session(), msg)

def main():
    s = _session()
    if MODE == "greet":
        do_greet(s)
    elif MODE == "close":
        do_close(s)
    else:
        do_rates(s)
    print({"ok": True, "mode": MODE})

if __name__ == "__main__":
    main()
