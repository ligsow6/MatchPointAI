from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
OUTPUT_DIR = ROOT_DIR / "web" / "public" / "data"

FIRST_SEASON = 1968
PROBE_FILENAME = "atp_matches_2024.csv"
TRAIN_START = date(1991, 1, 1)
VALIDATION_START = date(2024, 1, 1)
TEST_START = date(2025, 1, 1)

RANDOM_SEED = 20260919
