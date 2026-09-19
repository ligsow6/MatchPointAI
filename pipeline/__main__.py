import argparse


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="pipeline", description="MatchPoint data pipeline")
    parser.add_argument("--offline", action="store_true", help="reuse cached raw files")
    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()
    print(f"pipeline ready (offline={arguments.offline})")


if __name__ == "__main__":
    main()
