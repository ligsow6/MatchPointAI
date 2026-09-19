from datetime import date

import numpy as np
import pandas as pd

from pipeline import config

HISTORY = "history"
TRAIN = "train"
VALIDATION = "validation"
TEST = "test"


def assign_periods(
    tourney_dates: pd.Series,
    train_start: date = config.TRAIN_START,
    validation_start: date = config.VALIDATION_START,
    test_start: date = config.TEST_START,
) -> pd.Series:
    if not train_start < validation_start < test_start:
        raise ValueError("Les bornes du découpage temporel doivent être strictement croissantes")
    conditions = [
        tourney_dates >= pd.Timestamp(test_start),
        tourney_dates >= pd.Timestamp(validation_start),
        tourney_dates >= pd.Timestamp(train_start),
    ]
    labels = np.select(conditions, [TEST, VALIDATION, TRAIN], default=HISTORY)
    return pd.Series(labels, index=tourney_dates.index, name="period")
