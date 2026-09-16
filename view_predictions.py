import argparse

from main import PredictionStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", help="SQLite database file")
    args = parser.parse_args()

    store = PredictionStore(args.database)
    try:
        print("Forecaster\tMarket\tOption\tPercentile5\tPercentile95\tDate")
        for prediction in store.readAllPredictions():
            print(
                "\t".join(
                    str(prediction.get(column, ""))
                    for column in (
                        "forecaster",
                        "market",
                        "option",
                        "percentile5",
                        "percentile95",
                        "date",
                    )
                )
            )
    finally:
        store.close()


if __name__ == "__main__":
    main()
