from market_engine import build_market_history
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.exc import SQLAlchemyError
from models import db, Player, Holding, Transaction
from flask import (
    Flask, render_template,
    request, redirect, url_for, flash
)
from pathlib import Path
from decimal import Decimal
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError
import json
import secrets

from models import db, Player, Holding, Transaction

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///" + str(BASE_DIR / "veggie_market.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# 本機開發用，部署前需改用環境變數中的固定密鑰
app.secret_key = "veggie-market-local-dev-only"

db.init_app(app)


def load_stocks(filename):
    path = BASE_DIR / "data" / filename
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_all_stocks():
    vegetables = load_stocks("vegetables.json")
    fruits = load_stocks("fruits.json")
    return vegetables + fruits


def calculate_realized_pnl(player_id):
    records = (
        Transaction.query
        .filter_by(player_id=player_id)
        .order_by(Transaction.id.asc())
        .all()
    )

    positions = {}
    realized_total = Decimal("0.00")
    cent = Decimal("0.01")

    for record in records:
        key = record.stock_id

        if key not in positions:
            positions[key] = {
                "quantity": 0,
                "cost": Decimal("0.00")
            }

        position = positions[key]

        if record.action == "BUY":
            position["quantity"] += record.quantity
            position["cost"] += record.total

        elif record.action == "SELL":
            old_qty = position["quantity"]

            if old_qty < record.quantity:
                raise ValueError(
                    "交易紀錄持股數量不一致"
                )

            if old_qty == record.quantity:
                sold_cost = position["cost"]
            else:
                sold_cost = (
                    position["cost"]
                    * Decimal(record.quantity)
                    / Decimal(old_qty)
                ).quantize(
                    cent,
                    rounding=ROUND_HALF_UP
                )

            realized_total += record.total - sold_cost
            position["quantity"] -= record.quantity
            position["cost"] -= sold_cost

    return realized_total

# 建立資料庫與初始測試玩家
with app.app_context():
    db.create_all()

    player = db.session.get(Player, 1)

    if player is None:
        player = Player(
            id=1,
            username="Player1",
            balance=Decimal("5000.00")
        )
        db.session.add(player)
        db.session.commit()


@app.route("/")
def index():
    vegetables = load_stocks("vegetables.json")
    fruits = load_stocks("fruits.json")

    player = db.session.get(Player, 1)

    holdings = Holding.query.filter_by(
        player_id=player.id
    ).all()

    all_stocks = get_all_stocks()
    stock_map = {
        stock["id"]: stock
        for stock in all_stocks
    }

    holdings_data = []

    for holding in holdings:
        stock = stock_map.get(holding.stock_id)

        if stock:
            holdings_data.append({
                "name": stock["name"],
                "quantity": holding.quantity,
                "total_cost": holding.total_cost,
                "stock_id": holding.stock_id
            })

    transactions = (
        Transaction.query
        .filter_by(player_id=player.id)
        .order_by(Transaction.id.desc())
        .limit(10)
        .all()
    )

    realized_pnl = calculate_realized_pnl(player.id)

    return render_template(
        "index.html",
        realized_pnl=realized_pnl,
        vegetables=vegetables,
        fruits=fruits,
        balance=player.balance,
        holdings=holdings_data,
        transactions=transactions,
        csrf_token=get_csrf_token()
    )


def get_csrf_token():
    # 下一階段改成登入帳號與正式 CSRF 保護
    return ""


@app.route("/buy", methods=["POST"])
def buy_stock():

    stock_id = request.form.get(
        "stock_id", ""
    ).strip()

    quantity_text = request.form.get(
        "quantity", ""
    ).strip()

    # 檢查股數
    try:
        quantity = int(quantity_text)

        if quantity < 1 or quantity > 10000:
            raise ValueError

    except ValueError:
        flash("購買數量必須是 1～10000 的整數。", "error")
        return redirect(url_for("index"))

    # 從伺服器端取得股票資料
    all_stocks = get_all_stocks()

    stock = next(
        (s for s in all_stocks if s["id"] == stock_id),
        None
    )

    if stock is None:
        flash("找不到這支蔬果股票。", "error")
        return redirect(url_for("index"))

    price = Decimal(str(stock["price"]))
    total = price * quantity

    try:
        # 條件式扣款，防止餘額不足仍成功買入
        result = db.session.execute(
            update(Player)
            .where(Player.id == 1)
            .where(Player.balance >= total)
            .values(balance=Player.balance - total)
        )

        if result.rowcount != 1:
            db.session.rollback()
            flash("資金不足，無法完成購買。", "error")
            return redirect(url_for("index"))

        holding = Holding.query.filter_by(
            player_id=1,
            stock_id=stock_id
        ).first()

        if holding is None:
            holding = Holding(
                player_id=1,
                stock_id=stock_id,
                quantity=quantity,
                total_cost=total
            )
            db.session.add(holding)
        else:
            holding.quantity += quantity
            holding.total_cost += total

        transaction = Transaction(
            player_id=1,
            stock_id=stock_id,
            action="BUY",
            quantity=quantity,
            price=price,
            total=total
        )

        db.session.add(transaction)

        # 扣款、持股與交易紀錄一起提交
        db.session.commit()

        flash(
            f"成功買入 {stock['name']} "
            f"{quantity} 股，花費 NT${total:,.2f}",
            "success"
        )

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("買入交易失敗")
        flash("交易失敗，請稍後再試。", "error")

    return redirect(url_for("index"))


@app.route("/sell", methods=["POST"])
def sell_stock():

    stock_id = request.form.get(
        "stock_id", ""
    ).strip()

    quantity_text = request.form.get(
        "quantity", ""
    ).strip()

    # 1. 檢查賣出數量
    try:
        quantity = int(quantity_text)

        if quantity < 1 or quantity > 10000:
            raise ValueError

    except ValueError:
        flash("賣出數量必須是 1～10000 的整數。", "error")
        return redirect(url_for("index"))

    # 2. 檢查股票是否存在
    stocks = get_all_stocks()

    stock = next(
        (s for s in stocks if s["id"] == stock_id),
        None
    )

    if stock is None:
        flash("找不到這支股票。", "error")
        return redirect(url_for("index"))

    # 3. 查詢玩家持股
    holding = Holding.query.filter_by(
        player_id=1,
        stock_id=stock_id
    ).first()

    if holding is None or holding.quantity < quantity:
        flash("持股不足，無法賣出。", "error")
        return redirect(url_for("index"))

    # 4. 計算收入與平均成本
    money = Decimal("0.01")

    sell_price = Decimal(
        str(stock["price"])
    )

    proceeds = (
        sell_price * quantity
    ).quantize(money, rounding=ROUND_HALF_UP)

    original_quantity = holding.quantity

    # 全部賣出時，把剩餘成本完整扣除
    if quantity == original_quantity:
        sold_cost = holding.total_cost
    else:
        sold_cost = (
            holding.total_cost
            * Decimal(quantity)
            / Decimal(original_quantity)
        ).quantize(money, rounding=ROUND_HALF_UP)

    realized_pnl = proceeds - sold_cost

    try:
        # 5. 更新剩餘持股及總成本
        holding.quantity -= quantity
        holding.total_cost -= sold_cost

        if holding.quantity == 0:
            db.session.delete(holding)

        # 6. 賣出收入回到玩家錢包
        player = db.session.get(Player, 1)
        player.balance += proceeds

        # 7. 儲存賣出交易紀錄
        transaction = Transaction(
            player_id=1,
            stock_id=stock_id,
            action="SELL",
            quantity=quantity,
            price=sell_price,
            total=proceeds
        )

        db.session.add(transaction)
        db.session.commit()

        flash(
            f"成功賣出 {stock['name']} {quantity} 股！"
            f"獲得 NT${proceeds:,.2f}，"
            f"本次已實現損益 NT${realized_pnl:+,.2f}",
            "success"
        )

    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("賣出交易失敗")
        flash("交易失敗，請稍後再試。", "error")

    return redirect(url_for("index"))

@app.route("/market-history")
def market_history():

    market_data = build_market_history()

    stocks = market_data["stocks"]
    history = market_data["history"]
    news = market_data["news"]

    stock_rows = []

    for stock in stocks:
        stock_id = stock["id"]
        records = history.get(stock_id, [])

        latest = records[-1] if records else None

        stock_rows.append({
            "id": stock_id,
            "name": stock["name"],
            "risk": stock["risk"],
            "records": records,
            "latest": latest
        })

    return render_template(
        "history.html",
        stocks=stock_rows,
        news=news
    )

if __name__ == "__main__":
    app.run(debug=True)
