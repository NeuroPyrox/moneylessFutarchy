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
from tempfile import TemporaryDirectory

from main import (
    InvalidPrediction,
    MarketAlreadyResolved,
    PredictionStore,
)


class SubmitPredictionTests(unittest.TestCase):
    def test_submitPredictions_acceptsCopiedGoogleSheetsTable(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            copiedTable = (
                "Market\tForecaster\tOption\tPercentile5\tPercentile95\tDate\n"
                "market-1\tforecaster-1\toption-a\t10\t30\t9/11/26\n"
                "market-1\tforecaster-2\toption-b\t20\t40\t9/11/26\n"
            )

            store.submitPredictions(copiedTable)

            self.assertEqual(
                store.readPrediction("market-1", "forecaster-1", "option-a"),
                {
                    "percentile5": 10.0,
                    "percentile95": 30.0,
                    "date": "9/11/26",
                },
            )
            self.assertEqual(
                store.readPrediction("market-1", "forecaster-2", "option-b"),
                {
                    "percentile5": 20.0,
                    "percentile95": 40.0,
                    "date": "9/11/26",
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
                date="2030-01-15",
            )

            self.assertEqual(
                store.readPrediction("market-1", "forecaster-1", "option-a"),
                {
                    "percentile5": 10,
                    "percentile95": 30,
                    "date": "2030-01-15",
                },
            )
            store.close()


class SubmitPredictionRevisionTests(unittest.TestCase):
    def test_submitPrediction_beforeMarketResolves_replacesPreviousPrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-replace", "forecaster-1", "option-a", 10, 30)
            store.submitPrediction("market-replace", "forecaster-1", "option-a", 20, 40)
            store.close()

    def test_submitPrediction_beforeMarketResolves_keepsOnePrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-one", "forecaster-1", "option-a", 10, 30)
            store.submitPrediction("market-one", "forecaster-1", "option-a", 20, 40)
            self.assertEqual(store.readPrediction("market-one", "forecaster-1", "option-a"),
                             {"percentile5": 20, "percentile95": 40})
            store.close()

    def test_submitPrediction_doesNotChangeOtherPredictions(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-isolated", "forecaster-1", "option-a", 10, 30)
            store.submitPrediction("market-isolated", "forecaster-1", "option-b", 50, 70)
            store.submitPrediction("market-isolated", "forecaster-1", "option-a", 20, 40)
            self.assertEqual(store.readPrediction("market-isolated", "forecaster-1", "option-b"),
                             {"percentile5": 50, "percentile95": 70})
            store.close()

    def test_submitPrediction_afterMarketResolves_isRejected(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-resolved", "forecaster-1", "option-a", 10, 30)
            store.resolveMarket("market-resolved", 20)
            with self.assertRaises(MarketAlreadyResolved):
                store.submitPrediction("market-resolved", "forecaster-1", "option-a", 20, 40)
            store.close()


class InvalidPredictionTests(unittest.TestCase):
    def test_submitPrediction_rejectsReversedPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-invalid-order", "forecaster-1", "option-a", 40, 20)
            store.close()

    def test_submitPrediction_acceptsEqualPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-equal", "forecaster-1", "option-a", 25, 25)
            self.assertEqual(store.readPrediction("market-equal", "forecaster-1", "option-a"),
                             {"percentile5": 25, "percentile95": 25})
            store.close()

    def test_submitPrediction_rejectsNonNumericPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-invalid-type", "forecaster-1", "option-a", "low", 30)
            store.close()

    def test_submitPrediction_rejectsNonFinitePercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction(
                "market-invalid-finite", "forecaster-1", "option-a",
                float("nan"), 30,
                )
            store.close()

    def test_submitPrediction_rejectsBooleanPercentiles(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-invalid-bool", "forecaster-1", "option-a", True, 30)
            store.close()

    def test_submitPrediction_rejectsMissingOption(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-missing-option", "forecaster-1", "", 10, 30)
            store.close()

    def test_submitPrediction_invalidRevision_preservesPreviousPrediction(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction("market-preserved", "forecaster-1", "option-a", 10, 30)
            with self.assertRaises(InvalidPrediction):
                store.submitPrediction("market-preserved", "forecaster-1", "option-a", 40, 20)
            self.assertEqual(store.readPrediction("market-preserved", "forecaster-1", "option-a"),
                             {"percentile5": 10, "percentile95": 30})
            store.close()


class PredictionPersistenceTests(unittest.TestCase):
    def test_newStore_loadsSavedPrediction(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            firstStore = PredictionStore(filename)
            firstStore.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30,
                date="2030-01-15",
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
                    "date": "2030-01-15",
                },
            )
            startedStore.close()

    def test_newPredictionStore_createsStorage(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/new-predictions.db"
            store = PredictionStore(filename)
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            )
            store.close()

            reopenedStore = PredictionStore(filename)

            self.assertEqual(
                reopenedStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30},
            )
            reopenedStore.close()

    def test_newStore_loadsAllSavedPredictions(self):
        with TemporaryDirectory() as directory:
            filename = f"{directory}/predictions.db"
            firstStore = PredictionStore(filename)
            firstStore.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            )
            firstStore.submitPrediction(
                "market-1", "forecaster-2", "option-b", 20, 40
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
                    },
                    {
                        "market": "market-1",
                        "forecaster": "forecaster-2",
                        "option": "option-b",
                        "percentile5": 20,
                        "percentile95": 40,
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
            )
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 20, 40
            )
            store.close()

            restartedStore = PredictionStore(filename)

            self.assertEqual(
                restartedStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 20, "percentile95": 40},
            )
            restartedStore.close()


class PredictionSeparationTests(unittest.TestCase):
    def test_predictionDate_isAssociatedWithCorrectIdentifiers(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-a", "forecaster-1", "option-a", 10, 30,
                date="2030-01-15",
            )
            store.submitPrediction(
                "market-b", "forecaster-2", "option-b", 20, 40,
                date="2030-02-15",
            )

            self.assertEqual(
                store.readPrediction(
                    "market-a", "forecaster-1", "option-a"
                )["date"],
                "2030-01-15",
            )
            self.assertEqual(
                store.readPrediction(
                    "market-b", "forecaster-2", "option-b"
                )["date"],
                "2030-02-15",
            )
            store.close()

    def test_predictionsFromDifferentMarkets_areKeptSeparate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-a", "forecaster-1", "option-a", 10, 30
            )
            store.submitPrediction(
                "market-b", "forecaster-1", "option-a", 20, 40
            )

            self.assertEqual(
                store.readPrediction(
                    "market-a", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30},
            )
            store.close()

    def test_predictionsForDifferentOptions_areKeptSeparate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            )
            store.submitPrediction(
                "market-1", "forecaster-1", "option-b", 20, 40
            )

            self.assertEqual(
                store.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30},
            )
            store.close()

    def test_predictionsFromDifferentForecasters_areKeptSeparate(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-1", "forecaster-1", "option-a", 10, 30
            )
            store.submitPrediction(
                "market-1", "forecaster-2", "option-a", 20, 40
            )

            self.assertEqual(
                store.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30},
            )
            store.close()

    def test_predictionsDifferingInAllIdentifiers_canCoexist(self):
        with TemporaryDirectory() as directory:
            store = PredictionStore(f"{directory}/predictions.db")
            store.submitPrediction(
                "market-a", "forecaster-1", "option-a", 10, 30
            )
            store.submitPrediction(
                "market-b", "forecaster-2", "option-b", 20, 40
            )

            self.assertEqual(
                store.readAllPredictions(),
                [
                    {
                        "market": "market-a",
                        "forecaster": "forecaster-1",
                        "option": "option-a",
                        "percentile5": 10,
                        "percentile95": 30,
                    },
                    {
                        "market": "market-b",
                        "forecaster": "forecaster-2",
                        "option": "option-b",
                        "percentile5": 20,
                        "percentile95": 40,
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
                )

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
            )
            firstStore.close()

            secondStore = PredictionStore(filename)

            self.assertEqual(
                secondStore.readPrediction(
                    "market-1", "forecaster-1", "option-a"
                ),
                {"percentile5": 10, "percentile95": 30},
            )
            secondStore.close()


if __name__ == "__main__":
    unittest.main()
