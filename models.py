
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Player(db.Model):
    __tablename__ = "players"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(50), nullable=False, unique=True
    )
    balance = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=5000
    )


class Holding(db.Model):
    __tablename__ = "holdings"

    id = db.Column(db.Integer, primary_key=True)

    player_id = db.Column(
        db.Integer,
        db.ForeignKey("players.id"),
        nullable=False
    )

    stock_id = db.Column(
        db.String(10), nullable=False
    )

    quantity = db.Column(
        db.Integer, nullable=False, default=0
    )

    total_cost = db.Column(
        db.Numeric(12, 2),
        nullable=False,
        default=0
    )

    __table_args__ = (
        db.UniqueConstraint(
            "player_id", "stock_id",
            name="unique_player_stock"
        ),
    )


class Transaction(db.Model):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)

    player_id = db.Column(
        db.Integer,
        db.ForeignKey("players.id"),
        nullable=False
    )

    stock_id = db.Column(
        db.String(10), nullable=False
    )

    action = db.Column(
        db.String(10), nullable=False
    )

    quantity = db.Column(
        db.Integer, nullable=False
    )

    price = db.Column(
        db.Numeric(12, 2), nullable=False
    )

    total = db.Column(
        db.Numeric(12, 2), nullable=False
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: __import__(
            "datetime"
        ).datetime.now(
            __import__("datetime").timezone.utc
        )
    )
