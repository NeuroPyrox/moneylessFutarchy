
import math
import sqlite3


class InvalidPrediction(ValueError):
    """Raised when a prediction cannot represent a valid score distribution."""


class MarketAlreadyResolved(ValueError):
    """Raised when a prediction is changed after its market is resolved."""


def _validatePrediction(option, percentile5, percentile95):
    if not isinstance(option, str) or not option:
        raise InvalidPrediction("option must be a non-empty string")
    for name, value in (
        ("percentile5", percentile5),
        ("percentile95", percentile95),
    ):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise InvalidPrediction(f"{name} must be a finite number")
    if percentile5 > percentile95:
        raise InvalidPrediction(
            "the 5th percentile cannot exceed the 95th"
        )


class PredictionStore:
    def __init__(self, filename):
        self.connection = sqlite3.connect(filename)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                market TEXT NOT NULL,
                forecaster TEXT NOT NULL,
                option TEXT NOT NULL,
                percentile5 REAL NOT NULL,
                percentile95 REAL NOT NULL,
                date TEXT,
                PRIMARY KEY (market, forecaster, option)
            )
            """
        )
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS markets (
                market TEXT PRIMARY KEY,
                outcome TEXT NOT NULL
            )
            """
        )
        self.connection.commit()

    def submitPrediction(
        self, market, forecaster, option, percentile5, percentile95, date=None
    ):
        if self._isMarketResolved(market):
            raise MarketAlreadyResolved(
                f"market {market!r} is already resolved"
            )
        _validatePrediction(option, percentile5, percentile95)
        self.connection.execute(
            """
            INSERT INTO predictions
                (market, forecaster, option, percentile5, percentile95, date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(market, forecaster, option) DO UPDATE SET
                percentile5=excluded.percentile5,
                percentile95=excluded.percentile95,
                date=excluded.date
            """,
            (market, forecaster, option, percentile5, percentile95, date),
        )
        self.connection.commit()

    def readPrediction(self, market, forecaster, option):
        row = self.connection.execute(
            """
            SELECT percentile5, percentile95
                , date
            FROM predictions
            WHERE market = ? AND forecaster = ? AND option = ?
            """,
            (market, forecaster, option),
        ).fetchone()
        if row is None:
            return None
        prediction = {
            "percentile5": row[0],
            "percentile95": row[1],
        }
        if row[2] is not None:
            prediction["date"] = row[2]
        return prediction

    def readAllPredictions(self):
        rows = self.connection.execute(
            """
            SELECT market, forecaster, option, percentile5, percentile95
            FROM predictions
            ORDER BY rowid
            """
        ).fetchall()
        return [
            {
                "market": row[0],
                "forecaster": row[1],
                "option": row[2],
                "percentile5": row[3],
                "percentile95": row[4],
            }
            for row in rows
        ]

    def resolveMarket(self, market, outcome):
        self.connection.execute(
            """
            INSERT INTO markets(market, outcome)
            VALUES (?, ?)
            """,
            (market, str(outcome)),
        )
        self.connection.commit()

    def _isMarketResolved(self, market):
        return self.connection.execute(
            "SELECT 1 FROM markets WHERE market = ?", (market,)
        ).fetchone() is not None

    def close(self):
        self.connection.close()
