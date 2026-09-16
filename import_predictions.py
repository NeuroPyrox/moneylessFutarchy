import argparse
import sys

from main import PredictionStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("database", help="SQLite database file")
    args = parser.parse_args()

    store = PredictionStore(args.database)
    try:
        store.submitPredictions(sys.stdin.read())
    finally:
        store.close()


if __name__ == "__main__":
    main()
