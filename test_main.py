"""
- I want to submit a prediction
    - As a forecaster, I want to submit a probability distribution for a prediction using a 5th and 95th percentile.
    - As a forecaster, I want to revise my prediction before the market resolves.
    - As a forecaster, I want the system to reject invalid predictions.
    - I want the predictions to persist between program runs.
        - As a forecaster, I want a submitted prediction saved to durable storage so it survives program shutdown.
        - As a forecaster, I want predictions from different markets, options, and forecasters kept separate.
    - I want to submit a date with my predictions
        - As a forecaster, I want to submit a date with a prediction.
        - As a forecaster, I want the submitted date saved with the prediction.
        - As a forecaster, I want the saved date loaded when the program starts.
        - As a forecaster, I want the date associated with the correct market, option, and forecaster.
    - I want to submit in bulk from a copied Google sheets table

User stories above here have been implemented, and user stories below here haven’t been implemented yet.

        - As a forecaster, I want to revise the date when revising a prediction.
        - As an administrator, I want invalid dates rejected with a clear error.
        - As an administrator, I want dates stored in a consistent timezone and format.
        - As an administrator, I want historical dates preserved exactly when prediction values are revised.
        - Using another method, automatically record the current submission time instead of accepting a caller-provided date.
- I want to read the recommended decision of the market
    - As a decision-maker, I want to see the market's recommended option.
    - As a decision-maker, I want to see a probability distribution over the available options.
- I want to resolve a prediction market
    - As a market administrator, I want to resolve a prediction market so that submitted predictions can be scored.
    - As a market administrator, I want to resolve a market using a single numerical outcome.
    - As a market administrator, I want to resolve a market using the outcome of another prediction market.
    - As a market administrator, I want the system to prevent a market from being resolved more than once.
    - As a participant, I want to see the resolved outcome of a market.
    - As a participant, I want my prediction to receive a score after the market resolves.
- The futarchy must be moneyless
    - As a participant, I want to submit predictions without using real money.
    - As a participant, I want my ability to influence the market to depend on my prediction performance rather than my financial wealth.
    - As an administrator, I want the market to operate without deposits, withdrawals, or monetary payments.
- Future wishlist
    - As an administrator, I want persistence failures reported rather than silently losing predictions.
    - As an administrator, I want existing saved prediction data preserved when the program is upgraded.
"""

import unittest
import subprocess
import sys
from math import isclose
from datetime import date
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from main import (
    InvalidPrediction,
    MarketAlreadyResolved,
    PredictionStore,
)

class ImportPredictionsCommandTests(unittest.TestCase):
    def test_importPredictions_readsTableFromStdin(self):
        copiedTable = (
            "Market\tForecaster\tOption\tPercentile5\tPercentile95\tDate\n"
            "market-1\tforecaster-1\toption-a\t10\t30\t2020-09-11\n"
        )
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("import_predictions.py")),
                    filename,
                ],
                input=copiedTable,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            store = PredictionStore(filename)
            self.assertEqual(
                store.readPrediction("market-1", "forecaster-1", "option-a"),
                {
                    "percentile5": 10.0,
                    "percentile95": 30.0,
                    "date": "2020-09-11",
                },
            )
            store.close()

    def test_importPredictions_rejectsMalformedTable(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("import_predictions.py")),
                    filename,
                ],
                input="not a prediction table\n",
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)


class ViewPredictionsCommandTests(unittest.TestCase):
    def test_viewPredictions_printsSortedTable(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            store = PredictionStore(filename)
            store.submitPrediction(
                "market-z", "Olivia", "option-a", 3, 15, date="2020-09-11"
            )
            store.submitPrediction(
                "market-b", "Danny", "option-a", 10, 35, date="2020-09-11"
            )
            store.close()

            result = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("view_predictions.py")),
                    filename,
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                result.stdout,
                (
                    "Forecaster\tMarket\tOption\tPercentile5\tPercentile95\tDate\n"
                    "Danny\tmarket-b\toption-a\t10.0\t35.0\t2020-09-11\n"
                    "Olivia\tmarket-z\toption-a\t3.0\t15.0\t2020-09-11\n"
                ),
            )


class SubmitPredictionTests(unittest.TestCase):
    def test_submitPrediction_rejectsDateAfterToday(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with patch("main._today", return_value=date(2030, 1, 15)):
                with self.assertRaises(InvalidPrediction):
                    store.submitPrediction(
                        "market-date", "forecaster-1", "option-a", 10, 30,
                        date="2030-01-16",
                    )

            self.assertIsNone(
                store.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                )
            )
            store.close()

    def test_submitPrediction_acceptsToday(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with patch("main._today", return_value=date(2030, 1, 15)):
                store.submitPrediction(
                    "market-date", "forecaster-1", "option-a", 10, 30,
                    date="2030-01-15",
                )

            self.assertIsNotNone(
                store.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                )
            )
            store.close()

    def test_submitPrediction_acceptsDateBeforeToday(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with patch("main._today", return_value=date(2030, 1, 15)):
                store.submitPrediction(
                    "market-date", "forecaster-1", "option-a", 10, 30,
                    date="2030-01-14",
                )

            self.assertIsNotNone(
                store.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                )
            )
            store.close()

    def test_submitPrediction_acceptsValidDate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )

            self.assertEqual(
                store.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                )["date"],
                "2020-01-15",
            )
            store.close()

    def test_submitPrediction_rejectsMissingDate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                    "market-date", "forecaster-1", "option-a", 10, 30,
                    date="",
                )

            store.close()

    def test_submitPrediction_rejectsInvalidDateFormat(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                    "market-date", "forecaster-1", "option-a", 10, 30,
                    date="9/11/26",
                )

            store.close()

    def test_submitPrediction_invalidDate_isNotPersisted(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                    "market-date", "forecaster-1", "option-a", 10, 30,
                    date="2020-02-30",
                )

            self.assertIsNone(
                store.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                )
            )
            store.close()

    def test_submitPrediction_requiresDate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                    "market-1", "forecaster-1", "option-a", 10, 30
                )

            store.close()

    def test_submitPredictions_requiresDateForEveryRow(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            copiedTable = (
                "Market\tForecaster\tOption\tPercentile5\tPercentile95\tDate\n"
                "market-1\tforecaster-1\toption-a\t10\t30\t\n"
            )

            with self.assertRaises(InvalidPrediction):
                store.submitPredictions(copiedTable)

            self.assertIsNone(
                store.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                )
            )
            store.close()

    def test_submitPredictions_invalidDate_doesNotPersistAnyRows(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            copiedTable = (
                "Market\tForecaster\tOption\tPercentile5\tPercentile95\tDate\n"
                "market-1\tforecaster-1\toption-a\t10\t30\t2020-01-15\n"
                "market-1\tforecaster-2\toption-b\t20\t40\t2020-02-30\n"
            )

            with self.assertRaises(InvalidPrediction):
                store.submitPredictions(copiedTable)

            self.assertEqual(store.readAllPredictions(), [])
            store.close()

    def test_submitPredictions_acceptsCopiedGoogleSheetsTable(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            copiedTable = (
                "Market\tForecaster\tOption\tPercentile5\tPercentile95\tDate\n"
                "market-1\tforecaster-1\toption-a\t10\t30\t2020-09-11\n"
                "market-1\tforecaster-2\toption-b\t20\t40\t2020-09-11\n"
            )

            store.submitPredictions(copiedTable)

            self.assertEqual(
                store.readPrediction("market-1", "forecaster-1", "option-a"),
                {
                    "percentile5": 10.0,
                    "percentile95": 30.0,
                    "date": "2020-09-11",
                },
            )
            self.assertEqual(
                store.readPrediction("market-1", "forecaster-2", "option-b"),
                {
                    "percentile5": 20.0,
                    "percentile95": 40.0,
                    "date": "2020-09-11",
                },
            )
            store.close()

    def test_submit_prediction_stores_one_options_score_distribution(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self.assertIsNone(store.submitPrediction(
                market="market-1",
                forecaster="forecaster-1",
                option="option-a",
                percentile5=10,
                percentile95=30,
                date="2020-01-15",
            ))
            store.close()

    def test_submitPrediction_acceptsDateWithPrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")

            store.submitPrediction(
                market="market-1",
                forecaster="forecaster-1",
                option="option-a",
                percentile5=10,
                percentile95=30,
                date="2020-01-15",
            )

            self.assertEqual(
                store.readPrediction("market-1", "forecaster-1", "option-a"),
                {
                    "percentile5": 10,
                    "percentile95": 30,
                    "date": "2020-01-15",
                },
            )
            store.close()


class SubmitPredictionRevisionTests(unittest.TestCase):
    def test_submitPrediction_revisionOverwritesPreviousDate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 20, 40,
                date="2020-02-15",
            )

            self.assertEqual(
                store.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                )["date"],
                "2020-02-15",
            )
            store.close()

    def test_submitPrediction_revisionReplacesPreviousDate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 20, 40,
                date="2020-02-15",
            )

            self.assertEqual(
                store.readPrediction("market-date", "forecaster-1", "option-a"),
                {
                    "percentile5": 20.0,
                    "percentile95": 40.0,
                    "date": "2020-02-15",
                },
            )
            store.close()

    def test_submitPrediction_revisionPreservesOtherPredictionDates(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )
            store.submitPrediction(
                "market-date", "forecaster-1", "option-b", 50, 70,
                date="2020-03-15",
            )
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 20, 40,
                date="2020-02-15",
            )

            self.assertEqual(
                store.readPrediction("market-date", "forecaster-1", "option-b"),
                {
                    "percentile5": 50.0,
                    "percentile95": 70.0,
                    "date": "2020-03-15",
                },
            )
            store.close()

    def test_submitPrediction_revisedDatePersistsAfterRestart(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            store = PredictionStore(filename)
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )
            store.submitPrediction(
                "market-date", "forecaster-1", "option-a", 20, 40,
                date="2020-02-15",
            )
            store.close()

            restartedStore = PredictionStore(filename)

            self.assertEqual(
                restartedStore.readPrediction(
                    "market-date", "forecaster-1", "option-a"
                ),
                {
                    "percentile5": 20.0,
                    "percentile95": 40.0,
                    "date": "2020-02-15",
                },
            )
            restartedStore.close()

    def test_submitPrediction_beforeMarketResolves_replacesPreviousPrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-replace", "forecaster-1", "option-a", 10, 30, date="2020-01-15")
            store.submitPrediction("market-replace", "forecaster-1", "option-a", 20, 40, date="2020-01-15")
            store.close()

    def test_submitPrediction_beforeMarketResolves_keepsOnePrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-one", "forecaster-1", "option-a", 10, 30, date="2020-01-15")
            store.submitPrediction("market-one", "forecaster-1", "option-a", 20, 40, date="2020-01-15")
            self.assertEqual(store.readPrediction("market-one", "forecaster-1", "option-a"),
                             {"percentile5": 20, "percentile95": 40, "date": "2020-01-15"})
            store.close()

    def test_submitPrediction_doesNotChangeOtherPredictions(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-isolated", "forecaster-1", "option-a", 10, 30, date="2020-01-15")
            store.submitPrediction("market-isolated", "forecaster-1", "option-b", 50, 70, date="2020-01-15")
            store.submitPrediction("market-isolated", "forecaster-1", "option-a", 20, 40, date="2020-01-15")
            self.assertEqual(store.readPrediction("market-isolated", "forecaster-1", "option-b"),
                             {"percentile5": 50, "percentile95": 70, "date": "2020-01-15"})
            store.close()

    def test_submitPrediction_afterMarketResolves_isRejected(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-resolved", "forecaster-1", "option-a", 10, 30, date="2020-01-15")
            store.resolveMarket("market-resolved", 20)
            with self.assertRaises(MarketAlreadyResolved):
                store.submitPrediction("market-resolved", "forecaster-1", "option-a", 20, 40, date="2020-01-15")
            store.close()


class InvalidPredictionTests(unittest.TestCase):
    def test_submitPrediction_rejectsReversedPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-invalid-order", "forecaster-1", "option-a", 40, 20, date="2020-01-15")
            store.close()

    def test_submitPrediction_acceptsEqualPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-equal", "forecaster-1", "option-a", 25, 25, date="2020-01-15")
            self.assertEqual(store.readPrediction("market-equal", "forecaster-1", "option-a"),
                             {"percentile5": 25, "percentile95": 25, "date": "2020-01-15"})
            store.close()

    def test_submitPrediction_rejectsNonNumericPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-invalid-type", "forecaster-1", "option-a", "low", 30, date="2020-01-15")
            store.close()

    def test_submitPrediction_rejectsNonFinitePercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                "market-invalid-finite", "forecaster-1", "option-a",
                float("nan"), 30,
                date="2020-01-15",
                )
            store.close()

    def test_submitPrediction_rejectsBooleanPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-invalid-bool", "forecaster-1", "option-a", True, 30, date="2020-01-15")
            store.close()

    def test_submitPrediction_rejectsMissingOption(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-missing-option", "forecaster-1", "", 10, 30, date="2020-01-15")
            store.close()

    def test_submitPrediction_invalidRevision_preservesPreviousPrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-preserved", "forecaster-1", "option-a", 10, 30, date="2020-01-15")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-preserved", "forecaster-1", "option-a", 40, 20, date="2020-01-15")
            self.assertEqual(store.readPrediction("market-preserved", "forecaster-1", "option-a"),
                             {"percentile5": 10, "percentile95": 30, "date": "2020-01-15"})
            store.close()


class PredictionPersistenceTests(unittest.TestCase):
    def test_newStore_loadsSavedPrediction(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            firstStore = PredictionStore(filename)
            firstStore.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )
            firstStore.close()

            startedStore = PredictionStore(filename)

            self.assertEqual(
                startedStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {
                    "percentile5": 10,
                    "percentile95": 30,
                    "date": "2020-01-15",
                },
            )
            startedStore.close()

    def test_newPredictionStore_createsStorage(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/new-predictions.db"
            store = PredictionStore(filename)
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            store.close()

            reopenedStore = PredictionStore(filename)

            self.assertEqual(
                reopenedStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30, "date": "2020-01-15"},
            )
            reopenedStore.close()

    def test_newStore_loadsAllSavedPredictions(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            firstStore = PredictionStore(filename)
            firstStore.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30,
                date="2020-09-11",
            )
            firstStore.submitPrediction(
                "market-1", "forecaster-2", "option-b", 20, 40,
                date="2020-09-11",
            )
            firstStore.close()

            startedStore = PredictionStore(filename)

            self.assertEqual(
                startedStore.readAllPredictions(),
                [
                    {
                        "market": "market-1",
                        "forecaster": "forecaster-1",
                        "option": "option-a",
                        "percentile5": 10,
                        "percentile95": 30,
                        "date": "2020-01-15",
                        "date": "2020-09-11",
                    },
                    {
                        "market": "market-1",
                        "forecaster": "forecaster-2",
                        "option": "option-b",
                        "percentile5": 20,
                        "percentile95": 40,
                        "date": "2020-01-15",
                        "date": "2020-09-11",
                    },
                ],
            )
            startedStore.close()

    def test_newStore_withNoSavedData_returnsNoPredictions(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/empty.db")

            self.assertEqual(store.readAllPredictions(), [])

            store.close()

    def test_newStore_loadsLatestSavedRevision(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            store = PredictionStore(filename)
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 20, 40
            , date="2020-01-15")
            store.close()

            restartedStore = PredictionStore(filename)

            self.assertEqual(
                restartedStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 20, "percentile95": 40, "date": "2020-01-15"},
            )
            restartedStore.close()


class PredictionSeparationTests(unittest.TestCase):
    def test_predictionDate_isAssociatedWithCorrectIdentifiers(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-a", "forecaster-1", "option-a", 10, 30,
                date="2020-01-15",
            )
            store.submitPrediction(
                "market-b", "forecaster-2", "option-b", 20, 40,
                date="2020-02-15",
            )

            self.assertEqual(
                store.readPrediction(
                    "market-a", "forecaster-1", "option-a"
                )["date"],
                "2020-01-15",
            )
            self.assertEqual(
                store.readPrediction(
                    "market-b", "forecaster-2", "option-b"
                )["date"],
                "2020-02-15",
            )
            store.close()


class RecommendedDecisionTests(unittest.TestCase):
    def _submitPrediction(self, store, option, percentile5, percentile95,
                          forecaster="forecaster-1"):
        store.submitPrediction(
            "market-1",
            forecaster,
            option,
            percentile5,
            percentile95,
            date="2020-01-15",
        )

    def _readMarketResult(self, store):
        results = store.readRecommendedDecisions()
        self.assertEqual(len(results), 1)
        return results[0]

    def test_readRecommendedDecisions_recommendsClearlyHighestOption(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(store, "option-a", 99, 101)
            self._submitPrediction(store, "option-b", 0, 1)

            result = self._readMarketResult(store)

            self.assertEqual(result["market"], "market-1")
            self.assertEqual(result["recommendedOption"], "option-a")
            self.assertGreaterEqual(
                dict(
                    (item["option"], item["probability"])
                    for item in result["recommendedOptions"]
                )["option-a"],
                0.99,
            )
            store.close()

    def test_readRecommendedDecisions_clearlyLowestOptionRarelyWins(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(store, "option-a", 0, 1)
            self._submitPrediction(store, "option-b", 99, 101)

            result = self._readMarketResult(store)

            self.assertLessEqual(
                dict(
                    (item["option"], item["probability"])
                    for item in result["recommendedOptions"]
                )["option-a"],
                0.01,
            )
            store.close()

    def test_readRecommendedDecisions_equalOptionsHaveSimilarChance(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(store, "option-a", 0, 10)
            self._submitPrediction(store, "option-b", 0, 10)

            result = self._readMarketResult(store)
            probabilities = {
                item["option"]: item["probability"]
                for item in result["recommendedOptions"]
            }

            self.assertGreaterEqual(probabilities["option-a"], 0.35)
            self.assertLessEqual(probabilities["option-a"], 0.65)
            self.assertGreaterEqual(probabilities["option-b"], 0.35)
            self.assertLessEqual(probabilities["option-b"], 0.65)
            store.close()

    def test_readRecommendedDecisions_closeOptionsHaveSimilarChance(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(store, "option-a", 0, 10)
            self._submitPrediction(store, "option-b", 0, 10.1)

            result = self._readMarketResult(store)
            probabilities = {
                item["option"]: item["probability"]
                for item in result["recommendedOptions"]
            }

            self.assertLess(abs(
                probabilities["option-a"] - probabilities["option-b"]
            ), 0.15)
            store.close()

    def test_readRecommendedDecisions_returnsNormalizedProbabilities(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(store, "option-a", 0, 10)
            self._submitPrediction(store, "option-b", 0, 10)

            result = self._readMarketResult(store)
            probabilities = [
                item["probability"] for item in result["recommendedOptions"]
            ]

            self.assertTrue(all(0 <= probability <= 1 for probability in probabilities))
            self.assertTrue(isclose(sum(probabilities), 1.0))
            store.close()

    def test_readRecommendedDecisions_choosesRecommendedOptionFromProbabilityDistribution(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(store, "option-a", 0, 10)
            self._submitPrediction(store, "option-b", -1, 9)

            recommendations = [
                self._readMarketResult(store)["recommendedOption"]
                for _ in range(100)
            ]

            optionACount = recommendations.count("option-a")
            optionBCount = recommendations.count("option-b")
            self.assertGreater(optionACount, 20)
            self.assertGreater(optionBCount, 20)
            self.assertLess(optionACount, 80)
            self.assertLess(optionBCount, 80)
            store.close()

    def test_readRecommendedDecisions_usesUniformForecasterMixture(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            self._submitPrediction(
                store, "option-a", 99, 101, forecaster="forecaster-a"
            )
            self._submitPrediction(
                store, "option-b", 99, 101, forecaster="forecaster-b"
            )
            self._submitPrediction(
                store, "option-a", 0, 1, forecaster="forecaster-b"
            )
            self._submitPrediction(
                store, "option-b", 0, 1, forecaster="forecaster-a"
            )

            result = self._readMarketResult(store)
            probabilities = {
                item["option"]: item["probability"]
                for item in result["recommendedOptions"]
            }

            self.assertGreaterEqual(probabilities["option-a"], 0.35)
            self.assertLessEqual(probabilities["option-a"], 0.65)
            self.assertGreaterEqual(probabilities["option-b"], 0.35)
            self.assertLessEqual(probabilities["option-b"], 0.65)
            store.close()

    def test_readRecommendedDecisions_omitsMarketsWithoutPredictions(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            result = store.readRecommendedDecisions()
            self.assertEqual(result, [])
            store.close()

    def test_predictionsFromDifferentMarkets_areKeptSeparate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-a", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            store.submitPrediction(
                "market-b", "forecaster-1", "option-a", 20, 40
            , date="2020-01-15")

            self.assertEqual(
                store.readPrediction(
                    "market-a", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30, "date": "2020-01-15"},
            )
            store.close()

    def test_predictionsForDifferentOptions_areKeptSeparate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            store.submitPrediction(
                "market-1", "forecaster-1", "option-b", 20, 40
            , date="2020-01-15")

            self.assertEqual(
                store.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30, "date": "2020-01-15"},
            )
            store.close()

    def test_predictionsFromDifferentForecasters_areKeptSeparate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            store.submitPrediction(
                "market-1", "forecaster-2", "option-a", 20, 40
            , date="2020-01-15")

            self.assertEqual(
                store.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30, "date": "2020-01-15"},
            )
            store.close()

    def test_predictionsDifferingInAllIdentifiers_canCoexist(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-a", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            store.submitPrediction(
                "market-b", "forecaster-2", "option-b", 20, 40
            , date="2020-01-15")

            self.assertEqual(
                store.readAllPredictions(),
                [
                    {
                        "market": "market-a",
                        "forecaster": "forecaster-1",
                        "option": "option-a",
                        "percentile5": 10,
                        "percentile95": 30,
                        "date": "2020-01-15",
                    },
                    {
                        "market": "market-b",
                        "forecaster": "forecaster-2",
                        "option": "option-b",
                        "percentile5": 20,
                        "percentile95": 40,
                        "date": "2020-01-15",
                    },
                ],
            )
            store.close()

    def test_invalidPrediction_isNotPersisted(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            store = PredictionStore(filename)

            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                    "market-1", "forecaster-1", "option-a", 40, 20
                , date="2020-01-15")

            store.close()
            reopenedStore = PredictionStore(filename)

            self.assertIsNone(
                reopenedStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                )
            )
            reopenedStore.close()

    def test_reopenedStore_readsDataWrittenByOriginalStore(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            firstStore = PredictionStore(filename)
            firstStore.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            , date="2020-01-15")
            firstStore.close()

            secondStore = PredictionStore(filename)

            self.assertEqual(
                secondStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30, "date": "2020-01-15"},
            )
            secondStore.close()


if __name__ == "__main__":
    unittest.main()
