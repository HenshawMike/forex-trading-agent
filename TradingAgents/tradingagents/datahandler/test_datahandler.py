import unittest
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal
import os
import shutil
from datetime import datetime

# Assuming DataHandler is in a sibling directory or installed
from TradingAgents.tradingagents.datahandler.datahandler import DataHandler

class TestDataHandler(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Create a temporary directory for test CSV files."""
        cls.temp_csv_dir = "temp_test_data_dir"
        os.makedirs(cls.temp_csv_dir, exist_ok=True)

        # Sample data for testing
        cls.symbol1 = "TEST1"
        cls.symbol1_data = {
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']),
            'Open': [10, 11, 12, 13, 14],
            'High': [10.5, 11.5, 12.5, 13.5, 14.5],
            'Low': [9.5, 10.5, 11.5, 12.5, 13.5],
            'Close': [10.2, 11.2, 12.2, 13.2, 14.2],
            'Volume': [100, 110, 120, 130, 140]
        }
        cls.symbol1_df = pd.DataFrame(cls.symbol1_data)
        cls.symbol1_df.to_csv(os.path.join(cls.temp_csv_dir, f"{cls.symbol1}.csv"), index=False)

        cls.symbol2 = "TEST2_EMPTY" # Will represent a symbol with a CSV but no data in range
        cls.symbol2_data = {
            'Date': pd.to_datetime(['2022-12-01', '2022-12-02']),
            'Open': [1, 2], 'High': [1, 2], 'Low': [1, 2], 'Close': [1, 2], 'Volume': [10, 20]
        }
        cls.symbol2_df = pd.DataFrame(cls.symbol2_data)
        cls.symbol2_df.to_csv(os.path.join(cls.temp_csv_dir, f"{cls.symbol2}.csv"), index=False)

        cls.start_date_str = "2023-01-01"
        cls.end_date_str = "2023-01-05"

    @classmethod
    def tearDownClass(cls):
        """Remove the temporary directory after all tests."""
        shutil.rmtree(cls.temp_csv_dir)

    def setUp(self):
        """Initialize DataHandler for each test."""
        self.symbols_list = [self.symbol1, self.symbol2, "NONEXISTENT"]
        self.dh = DataHandler(symbols=self.symbols_list,
                              start_date=self.start_date_str,
                              end_date=self.end_date_str,
                              csv_dir=self.temp_csv_dir)

        # Expected loaded DF for TEST1
        self.expected_symbol1_loaded_df = self.symbol1_df.copy()
        self.expected_symbol1_loaded_df['Date'] = pd.to_datetime(self.expected_symbol1_loaded_df['Date'])
        self.expected_symbol1_loaded_df = self.expected_symbol1_loaded_df[
            (self.expected_symbol1_loaded_df['Date'] >= pd.to_datetime(self.start_date_str)) &
            (self.expected_symbol1_loaded_df['Date'] <= pd.to_datetime(self.end_date_str))
        ].set_index('Date')


    def test_initialization_and_loading(self):
        """Test if DataHandler initializes and loads data correctly."""
        self.assertIn(self.symbol1, self.dh.data)
        self.assertFalse(self.dh.data[self.symbol1].empty)
        assert_frame_equal(self.dh.data[self.symbol1], self.expected_symbol1_loaded_df)

        # Test for symbol with CSV but data outside range (TEST2_EMPTY)
        self.assertIn(self.symbol2, self.dh.data)
        self.assertTrue(self.dh.data[self.symbol2].empty, f"Data for {self.symbol2} should be empty due to date range filter.")

        # Test for symbol with no CSV file (NONEXISTENT)
        self.assertIn("NONEXISTENT", self.dh.data)
        self.assertTrue(self.dh.data["NONEXISTENT"].empty)

        self.assertEqual(self.dh.start_date, pd.to_datetime(self.start_date_str))
        self.assertEqual(self.dh.end_date, pd.to_datetime(self.end_date_str))

    def test_get_latest_data(self):
        """Test retrieving the latest data point."""
        latest_data = self.dh.get_latest_data(self.symbol1)
        self.assertIsNotNone(latest_data)

        expected_latest = self.expected_symbol1_loaded_df.iloc[-1]
        assert_series_equal(latest_data, expected_latest, check_names=False) # Pandas can sometimes mismatch names for iloc series

        # Test for symbol with no data loaded
        latest_nonexistent = self.dh.get_latest_data("NONEXISTENT")
        self.assertIsNone(latest_nonexistent)

        latest_empty_range = self.dh.get_latest_data(self.symbol2)
        self.assertIsNone(latest_empty_range)


    def test_get_data_at_date(self):
        """Test retrieving data for a specific date."""
        date_str = "2023-01-03"
        data_at_date = self.dh.get_data_at_date(self.symbol1, date_str)
        self.assertIsNotNone(data_at_date)

        expected_data = self.expected_symbol1_loaded_df[self.expected_symbol1_loaded_df.index == pd.to_datetime(date_str)]
        assert_frame_equal(data_at_date, expected_data)

        # Test for a date with no data
        data_no_date = self.dh.get_data_at_date(self.symbol1, "2023-01-10") # Outside range
        self.assertTrue(data_no_date.empty if data_no_date is not None else True)


        # Test for symbol with no data loaded
        data_nonexistent = self.dh.get_data_at_date("NONEXISTENT", date_str)
        self.assertIsNone(data_nonexistent) # Current implementation returns None

    def test_get_data_window(self):
        """Test retrieving a window of data."""
        window_start_str = "2023-01-02"
        window_end_str = "2023-01-04"

        data_window = self.dh.get_data_window(self.symbol1, window_start_str, window_end_str)
        self.assertIsNotNone(data_window)

        expected_window_df = self.expected_symbol1_loaded_df[
            (self.expected_symbol1_loaded_df.index >= pd.to_datetime(window_start_str)) &
            (self.expected_symbol1_loaded_df.index <= pd.to_datetime(window_end_str))
        ]
        assert_frame_equal(data_window, expected_window_df)

        # Test window outside actual data range but within object's overall date range
        window_outside_data = self.dh.get_data_window(self.symbol1, "2023-01-06", "2023-01-10")
        self.assertTrue(window_outside_data.empty if window_outside_data is not None else True)

        # Test for symbol with no data loaded
        window_nonexistent = self.dh.get_data_window("NONEXISTENT", window_start_str, window_end_str)
        self.assertIsNone(window_nonexistent) # Current implementation returns None

    def test_edge_case_empty_csv_file(self):
        """Test loading an empty CSV file (or one that becomes empty after date filtering)."""
        empty_symbol = "EMPTY_CSV"
        empty_df = pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        empty_df.to_csv(os.path.join(self.temp_csv_dir, f"{empty_symbol}.csv"), index=False)

        dh_empty_test = DataHandler(symbols=[empty_symbol],
                                    start_date=self.start_date_str,
                                    end_date=self.end_date_str,
                                    csv_dir=self.temp_csv_dir)

        self.assertIn(empty_symbol, dh_empty_test.data)
        self.assertTrue(dh_empty_test.data[empty_symbol].empty)
        self.assertIsNone(dh_empty_test.get_latest_data(empty_symbol))

    def test_data_type_consistency(self):
        """Test that data types are consistent after loading."""
        data_df = self.dh.data[self.symbol1]
        self.assertTrue(isinstance(data_df.index, pd.DatetimeIndex))
        for col in ['Open', 'High', 'Low', 'Close']: # Assuming these should be float/int
            self.assertTrue(pd.api.types.is_numeric_dtype(data_df[col]))
        self.assertTrue(pd.api.types.is_integer_dtype(data_df['Volume']))


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
