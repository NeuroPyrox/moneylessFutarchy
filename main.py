
import csv
from datetime import date as calendarDate
import math
import random
import sqlite3
from io import StringIO


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


def _today():
    return calendarDate.today()


def _validateDate(date):
    if not isinstance(date, str) or not date:
        raise InvalidPrediction("date must use YYYY-MM-DD format")
    try:
        parsedDate = calendarDate.fromisoformat(date)
    except ValueError as error:
        raise InvalidPrediction(
            "date must use YYYY-MM-DD format"
        ) from error
    if parsedDate.isoformat() != date:
        raise InvalidPrediction("date must use YYYY-MM-DD format")
    if parsedDate > _today():
        raise InvalidPrediction("date cannot be later than today")


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
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS decisions (
                market TEXT PRIMARY KEY,
                chosen_option TEXT NOT NULL,
                decision_date TEXT NOT NULL
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
        _validateDate(date)
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

    def submitPredictions(self, copiedTable):
        rows = csv.reader(StringIO(copiedTable), delimiter="\t")
        header = next(rows, None)
        expectedHeader = [
            "Market",
            "Forecaster",
            "Option",
            "Percentile5",
            "Percentile95",
            "Date",
        ]
        if header != expectedHeader:
            raise ValueError("table must have the expected prediction columns")

        predictions = []
        for row in rows:
            if not row or not any(row):
                continue
            if len(row) != len(expectedHeader):
                raise ValueError("each prediction row must have six columns")
            percentile5 = float(row[3])
            percentile95 = float(row[4])
            if self._isMarketResolved(row[0]):
                raise MarketAlreadyResolved(
                    f"market {row[0]!r} is already resolved"
                )
            _validatePrediction(row[2], percentile5, percentile95)
            _validateDate(row[5])
            predictions.append(
                (
                    row[0],
                    row[1],
                    row[2],
                    percentile5,
                    percentile95,
                    row[5],
                )
            )

        self.connection.executemany(
            """
            INSERT INTO predictions
                (market, forecaster, option, percentile5, percentile95, date)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(market, forecaster, option) DO UPDATE SET
                percentile5=excluded.percentile5,
                percentile95=excluded.percentile95,
                date=excluded.date
            """,
            predictions,
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
            SELECT market, forecaster, option, percentile5, percentile95, date
            FROM predictions
            ORDER BY forecaster, market, option
            """
        ).fetchall()
        predictions = []
        for row in rows:
            prediction = {
                "market": row[0],
                "forecaster": row[1],
                "option": row[2],
                "percentile5": row[3],
                "percentile95": row[4],
            }
            if row[5] is not None:
                prediction["date"] = row[5]
            predictions.append(prediction)
        return predictions

    def readRecommendedDecisions(self):
        rows = self.connection.execute(
            """
            SELECT market, option, percentile5, percentile95
            FROM predictions
            ORDER BY market, option, forecaster
            """
        ).fetchall()
        predictionsByMarket = {}
        for market, option, percentile5, percentile95 in rows:
            predictionsByMarket.setdefault(market, {}).setdefault(
                option, []
            ).append((percentile5, percentile95))

        results = []
        for market, predictionsByOption in predictionsByMarket.items():
            recommendationCounts = {
                option: 0 for option in predictionsByOption
            }
            for _ in range(100):
                sampledScores = {}
                for option, predictions in predictionsByOption.items():
                    percentile5, percentile95 = random.choice(predictions)
                    mean = (percentile5 + percentile95) / 2
                    standardDeviation = (
                        mean - percentile5
                    ) / 1.64485
                    sampledScores[option] = random.gauss(
                        mean, standardDeviation
                    )
                highestScore = max(sampledScores.values())
                highestOptions = [
                    option
                    for option, score in sampledScores.items()
                    if score == highestScore
                ]
                recommendationCounts[random.choice(highestOptions)] += 1

            recommendedOptions = [
                {
                    "option": option,
                    "probability": count / 100,
                }
                for option, count in recommendationCounts.items()
            ]
            randomValue = random.random()
            cumulativeProbability = 0
            recommendedOption = recommendedOptions[-1]["option"]
            for recommendation in recommendedOptions:
                cumulativeProbability += recommendation["probability"]
                if randomValue < cumulativeProbability:
                    recommendedOption = recommendation["option"]
                    break
            results.append(
                {
                    "market": market,
                    "recommendedOption": recommendedOption,
                    "recommendedOptions": recommendedOptions,
                }
            )
        return results

    def decideMarket(self, market):
        recommendation = next(
            result
            for result in self.readRecommendedDecisions()
            if result["market"] == market
        )
        self.connection.execute(
            """
            INSERT INTO decisions (market, chosen_option, decision_date)
            VALUES (?, ?, ?)
            """,
            (
                market,
                recommendation["recommendedOption"],
                _today().isoformat(),
            ),
        )
        self.connection.commit()

    def readDecisions(self):
        rows = self.connection.execute(
            """
            SELECT market, chosen_option, decision_date
            FROM decisions
            ORDER BY rowid
            """
        ).fetchall()
        return [
            {
                "market": market,
                "chosenOption": chosenOption,
                "decisionDate": decisionDate,
            }
            for market, chosenOption, decisionDate in rows
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
