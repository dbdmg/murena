import unittest

import pandas as pd

from app.data.processors import calculate_travel_times_df


class CalculateTravelTimesTests(unittest.TestCase):
    def test_accepts_inventory_english_coordinate_columns(self):
        properties = pd.DataFrame(
            [{"id": "estate-1", "latitude": 45.0, "longitude": 7.0}]
        )
        poi = [["reference", 45.0, 7.0]]

        result = calculate_travel_times_df(properties, poi)

        self.assertEqual(result.loc[0, "distanza_km"], 0.0)
        self.assertEqual(result.loc[0, "poi_riferimento"], "reference")
        self.assertEqual(result.loc[0, "latitude"], 45.0)
        self.assertEqual(result.loc[0, "longitude"], 7.0)

    def test_preserves_support_for_italian_coordinate_columns(self):
        properties = pd.DataFrame(
            [{"id": "estate-1", "latitudine": 45.0, "longitudine": 7.0}]
        )
        poi = [["reference", 45.0, 7.0]]

        result = calculate_travel_times_df(properties, poi)

        self.assertEqual(result.loc[0, "distanza_km"], 0.0)
        self.assertEqual(result.loc[0, "poi_riferimento"], "reference")
