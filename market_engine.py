
import json
import random
import hashlib
from pathlib import Path
from datetime import date, timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
TAIPEI = ZoneInfo("Asia/Taipei")
START_DATE = date(2026, 1, 1)
CENT = Decimal("0.01")


# 每種蔬果所屬的市場分類
GROUPS = {
    "leafy": [
        "V01", "V02", "V03", "V04", "V05", "V06"
    ],
    "flower": ["V07", "V08"],
    "root": ["V09", "V10", "V11", "V12", "V13"],
    "warm_veg": [
        "V14", "V15", "V16", "V17",
        "V18", "V19", "V20"
    ],
    "tropical": [
        "F02", "F03", "F04", "F05", "F12",
        "F13", "F14", "F15", "F19", "F20"
    ],
    "imported": [
        "F01", "F07", "F11", "F16", "F18"
    ],
    "citrus": ["F08", "F09", "F10"],
    "cool_fruit": ["F06", "F17"]
}


# 新聞資料庫：所有內容均為遊戲虛構事件
EVENTS = [
    {
        "title": "連日豪雨影響葉菜採收",
        "content": (
            "中部農業產區連日降雨，"
            "部分葉菜採收與運輸受到影響，"
            "市場預期短期供應可能減少。"
        ),
        "effects": {"leafy": 2.2}
    },
    {
        "title": "葉菜產區迎來良好收成",
        "content": (
            "近期天氣穩定，葉菜類產量增加，"
            "批發市場供貨充足，"
            "部分品項面臨價格調整壓力。"
        ),
        "effects": {"leafy": -1.8}
    },
    {
        "title": "國際物流成本上升",
        "content": (
            "國際運輸與冷藏成本上升，"
            "市場擔憂進口水果成本增加，"
            "部分進口品項可能受到影響。"
        ),
        "effects": {"imported": 1.7}
    },
    {
        "title": "進口水果集中到貨",
        "content": (
            "大型進口商增加水果到貨量，"
            "市場供給比原先預期充裕，"
            "進口水果價格面臨下行壓力。"
        ),
        "effects": {"imported": -2.0}
    },
    {
        "title": "夏季水果飲品掀起熱潮",
        "content": (
            "多家飲料品牌推出熱帶水果新品，"
            "帶動相關水果的採購需求，"
            "市場關注後續補貨情況。"
        ),
        "effects": {"tropical": 1.8}
    },
    {
        "title": "熱帶水果進入盛產期",
        "content": (
            "農友陸續進入採收高峰，"
            "熱帶水果供應量增加，"
            "市場預期短期價格承壓。"
        ),
        "effects": {"tropical": -1.7}
    },
    {
        "title": "寒流影響部分蔬果供應",
        "content": (
            "低溫影響部分果菜生長與採收，"
            "市場開始關注溫度敏感作物的供貨。"
        ),
        "effects": {
            "warm_veg": 1.5,
            "tropical": 0.8
        }
    },
    {
        "title": "根莖蔬菜庫存充足",
        "content": (
            "市場盤點顯示根莖類蔬菜"
            "庫存維持充足，短期供應穩定，"
            "部分品項價格可能走弱。"
        ),
        "effects": {"root": -1.2}
    },
    {
        "title": "健康餐飲需求增加",
        "content": (
            "健康餐盒銷售增加，"
            "帶動青花菜與花椰菜採購量，"
            "餐飲業者開始增加備貨。"
        ),
        "effects": {"flower": 1.5}
    },
    {
        "title": "柑橘類水果需求升溫",
        "content": (
            "果汁與柑橘類飲品需求增加，"
            "部分通路提高採購數量，"
            "市場關注柑橘供需變化。"
        ),
        "effects": {"citrus": 1.4}
    },
    {
        "title": "冷季水果品質提升",
        "content": (
            "產區氣候條件改善，"
            "部分冷季水果品質與供應提升，"
            "市場預期價格可能受到供給影響。"
        ),
        "effects": {"cool_fruit": -1.3}
    }
]


def stable_random(*parts):
    """相同輸入永遠產生相同亂數序列。"""
    value = "|".join(str(p) for p in parts)
    digest = hashlib.sha256(value.encode()).digest()
    seed = int.from_bytes(digest[:8], "big")
    return random.Random(seed)


def load_stocks():
    stocks = []

    for filename in ["vegetables.json", "fruits.json"]:
        path = BASE_DIR / "data" / filename

        with open(path, "r", encoding="utf-8") as f:
            stocks.extend(json.load(f))

    return stocks


def trading_days(start, end):
    """第一版僅排除週六與週日。"""
    current = start

    while current <= end:
        if current.weekday() < 5:
            yield current

        current += timedelta(days=1)


def get_news(day):
    """產生同一日期固定的市場新聞。"""
    rng = stable_random("news", day.isoformat())
    selected = rng.sample(EVENTS, 2)

    return [
        {
            "date": day.isoformat(),
            "title": event["title"],
            "content": event["content"],
            "effects": event["effects"]
        }
        for event in selected
    ]


def seasonal_effect(stock, day):
    """第一版季節供需模型。"""
    stock_id = stock["id"]
    month = day.month

    if stock_id in GROUPS["tropical"]:
        if month in [5, 6, 7, 8]:
            return -0.35  # 盛產供應增加
        if month in [12, 1, 2]:
            return 0.25

    if stock_id in GROUPS["leafy"]:
        if month in [6, 7, 8]:
            return 0.25  # 高溫增加供應風險
        if month in [11, 12, 1, 2]:
            return -0.20

    if stock_id in GROUPS["cool_fruit"]:
        if month in [12, 1, 2]:
            return -0.35

    return 0.0


def news_effect(stock_id, news):
    """加總當日新聞對特定股票的影響。"""
    total = 0.0

    for event in news:
        for group, effect in event["effects"].items():
            if stock_id in GROUPS.get(group, []):
                total += effect

    return total


def calculate_daily_change(
    stock, day, previous_change, news
):
    """計算單日漲跌幅，最高限制 ±5%。"""
    rng = stable_random(
        "price", day.isoformat(), stock["id"]
    )

    risk = {
        "低": 0.45,
        "中": 0.75,
        "高": 1.0
    }.get(stock["risk"], 0.75)

    event = news_effect(stock["id"], news)
    seasonal = seasonal_effect(stock, day)

    # 前一天的輕微延續趨勢
    momentum = previous_change * 0.15

    # 不確定性較小，讓供需新聞具有意義
    noise = rng.uniform(-0.55, 0.55) * risk

    change = (
        (event + seasonal + momentum) * risk
        + noise
    )

    return round(max(-5.0, min(5.0, change)), 4)


def build_market_history(end_date=None):
    """
    從固定起點計算歷史價格。
    相同日期、相同資料會得到相同結果。
    """
    if end_date is None:
        end_date = datetime.now(TAIPEI).date()

    # 只呈現已完成的交易日，不洩漏今天收盤價
    last_date = end_date - timedelta(days=1)

    stocks = load_stocks()

    prices = {
        s["id"]: Decimal(str(s["price"]))
        for s in stocks
    }

    previous_changes = {
        s["id"]: 0.0 for s in stocks
    }

    history = {
        s["id"]: [] for s in stocks
    }

    news_history = []

    if last_date < START_DATE:
        return {
            "stocks": stocks,
            "history": history,
            "news": []
        }

    for day in trading_days(START_DATE, last_date):
        daily_news = get_news(day)
        news_history.append({
            "date": day.isoformat(),
            "articles": daily_news
        })

        for stock in stocks:
            sid = stock["id"]
            old_price = prices[sid]

            change = calculate_daily_change(
                stock,
                day,
                previous_changes[sid],
                daily_news
            )

            # 依前一收盤價計算隔日收盤價
            candidate = old_price * (
                Decimal("1") + Decimal(str(change)) / 100
            )

            # 限制到合法的分位價格範圍
            upper = (
                old_price * Decimal("1.05")
            ).quantize(
                CENT, rounding="ROUND_FLOOR"
            )

            lower = (
                old_price * Decimal("0.95")
            ).quantize(
                CENT, rounding="ROUND_CEILING"
            )

            new_price = candidate.quantize(
                CENT, rounding=ROUND_HALF_UP
            )

            new_price = max(lower, min(upper, new_price))

            actual_change = (
                (new_price - old_price)
                / old_price * 100
            )

            prices[sid] = new_price
            previous_changes[sid] = float(actual_change)

            history[sid].append({
                "date": day.isoformat(),
                "price": float(new_price),
                "change": round(float(actual_change), 2)
            })

    # 只保留最近七個已完成的交易日
    history = {
        sid: records[-7:]
        for sid, records in history.items()
    }

    return {
        "stocks": stocks,
        "history": history,
        "news": news_history[-7:][::-1]
    }
