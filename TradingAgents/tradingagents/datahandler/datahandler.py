import pandas as pd
from datetime import datetime

class DataHandler:
    """
    Handles loading, storing, and providing historical market data.
    """
    def __init__(self, symbols: list[str], start_date: str, end_date: str,
                 data_source: str = "csv", csv_dir: str = "data/"):
        """
        Initializes the DataHandler.

        Args:
            symbols: A list of symbols (e.g., stock tickers) to manage.
            start_date: The start date for the historical data (YYYY-MM-DD).
            end_date: The end date for the historical data (YYYY-MM-DD).
            data_source: The source of the data (default: "csv").
            csv_dir: The directory where CSV files are stored (default: "data/").
        """
        self.symbols = symbols
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.data_source = data_source
        self.csv_dir = csv_dir
        self.data = {}  # To store DataFrames for each symbol

        if self.data_source == "csv":
            self._load_csv_data()
        else:
            print(f"Warning: Data source '{self.data_source}' is not yet supported.")

    def _load_csv_data(self):
        """
        Loads historical data from CSV files for the specified symbols and date range.
        Assumes CSV files are named <symbol>.csv (e.g., AAPL.csv).
        Assumes CSVs have a 'Date' column and other relevant price columns (Open, High, Low, Close, Volume, Adj Close).
        """
        for symbol in self.symbols:
            try:
                file_path = f"{self.csv_dir}/{symbol}.csv"
                df = pd.read_csv(file_path, parse_dates=['Date'])

                # Filter by date range
                df = df[(df['Date'] >= self.start_date) & (df['Date'] <= self.end_date)]

                if df.empty:
                    print(f"Warning: No data found for {symbol} in the specified date range {self.start_date.date()} to {self.end_date.date()} in {file_path}.")
                    self.data[symbol] = pd.DataFrame() # Store empty dataframe
                else:
                    df.set_index('Date', inplace=True)
                    self.data[symbol] = df
                    print(f"Successfully loaded data for {symbol} from {file_path}")
            except FileNotFoundError:
                print(f"Warning: CSV file not found for symbol {symbol} at {file_path}. Storing empty DataFrame.")
                self.data[symbol] = pd.DataFrame() # Store empty dataframe if file not found
            except Exception as e:
                print(f"Error loading data for symbol {symbol}: {e}. Storing empty DataFrame.")
                self.data[symbol] = pd.DataFrame() # Store empty dataframe on other errors

    def get_latest_data(self, symbol: str) -> pd.Series | None:
        """
        Gets the latest available data point (row) for a given symbol.

        Args:
            symbol: The symbol for which to retrieve data.

        Returns:
            A pandas Series if data is available, otherwise None.
        """
        if symbol in self.data and not self.data[symbol].empty:
            return self.data[symbol].iloc[-1]
        print(f"No data available for {symbol} to get the latest data point.")
        return None

    def get_data_at_date(self, symbol: str, date: str) -> pd.DataFrame | None:
        """
        Gets all data points for a specific symbol and date.

        Args:
            symbol: The symbol for which to retrieve data.
            date: The specific date for which to retrieve data (YYYY-MM-DD).

        Returns:
            A pandas DataFrame if data is available for that date, otherwise None or an empty DataFrame.
        """
        target_date = pd.to_datetime(date)
        if symbol in self.data and not self.data[symbol].empty:
            # Ensure the index is DatetimeIndex for exact date matching
            if isinstance(self.data[symbol].index, pd.DatetimeIndex):
                data_on_date = self.data[symbol][self.data[symbol].index == target_date]
                if not data_on_date.empty:
                    return data_on_date
                else:
                    print(f"No data found for {symbol} on {date}.")
                    return pd.DataFrame()
            else:
                print(f"Data for {symbol} does not have a DatetimeIndex.")
                return pd.DataFrame()
        print(f"No data loaded for {symbol} to retrieve data at {date}.")
        return None

    def get_data_window(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame | None:
        """
        Gets a window of data for a specific symbol and date range.

        Args:
            symbol: The symbol for which to retrieve data.
            start_date: The start date of the window (YYYY-MM-DD).
            end_date: The end date of the window (YYYY-MM-DD).

        Returns:
            A pandas DataFrame if data is available for that range, otherwise None or an empty DataFrame.
        """
        window_start = pd.to_datetime(start_date)
        window_end = pd.to_datetime(end_date)

        if symbol in self.data and not self.data[symbol].empty:
            # Ensure the index is DatetimeIndex for date range slicing
            if isinstance(self.data[symbol].index, pd.DatetimeIndex):
                data_window = self.data[symbol][(self.data[symbol].index >= window_start) &
                                                (self.data[symbol].index <= window_end)]
                if not data_window.empty:
                    return data_window
                else:
                    print(f"No data found for {symbol} in window {start_date} to {end_date}.")
                    return pd.DataFrame()
            else:
                print(f"Data for {symbol} does not have a DatetimeIndex for windowing.")
                return pd.DataFrame()
        print(f"No data loaded for {symbol} to retrieve window from {start_date} to {end_date}.")
        return None

if __name__ == '__main__':
    # Example Usage (assuming you have some CSV data in a 'data' folder)
    # Create dummy CSV files for testing
    import os
    if not os.path.exists("data"):
        os.makedirs("data")

    # Dummy AAPL.csv
    aapl_data = {
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']),
        'Open': [150, 151, 152, 153, 154],
        'High': [152, 153, 154, 155, 156],
        'Low': [149, 150, 151, 152, 153],
        'Close': [151, 152, 153, 154, 155],
        'Volume': [1000, 1100, 1200, 1300, 1400]
    }
    aapl_df = pd.DataFrame(aapl_data)
    aapl_df.to_csv("data/AAPL.csv", index=False)

    # Dummy GOOG.csv
    goog_data = {
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05']),
        'Open': [2700, 2710, 2720, 2730, 2740],
        'High': [2720, 2730, 2740, 2750, 2760],
        'Low': [2690, 2700, 2710, 2720, 2730],
        'Close': [2710, 2720, 2730, 2740, 2750],
        'Volume': [2000, 2100, 2200, 2300, 2400]
    }
    goog_df = pd.DataFrame(goog_data)
    goog_df.to_csv("data/GOOG.csv", index=False)

    print("Dummy CSV files created in 'data/' directory for AAPL and GOOG.")

    # Initialize DataHandler
    symbols_list = ["AAPL", "GOOG", "MSFT"] # MSFT.csv won't be found
    dh = DataHandler(symbols=symbols_list, start_date="2023-01-01", end_date="2023-01-31", csv_dir="data")

    print("\n--- Testing DataHandler ---")

    # Test loading
    print("\nLoaded data for AAPL:")
    print(dh.data.get("AAPL", pd.DataFrame()).head())

    print("\nLoaded data for GOOG:")
    print(dh.data.get("GOOG", pd.DataFrame()).head())

    print("\nLoaded data for MSFT (should be empty or warning printed):")
    print(dh.data.get("MSFT", pd.DataFrame()).head())


    # Test get_latest_data
    print("\nLatest AAPL data:")
    latest_aapl = dh.get_latest_data("AAPL")
    if latest_aapl is not None:
        print(latest_aapl)

    # Test get_data_at_date
    print("\nAAPL data on 2023-01-03:")
    aapl_on_date = dh.get_data_at_date("AAPL", "2023-01-03")
    if aapl_on_date is not None:
        print(aapl_on_date)

    print("\nMSFT data on 2023-01-03 (should be empty or warning):")
    msft_on_date = dh.get_data_at_date("MSFT", "2023-01-03")
    if msft_on_date is not None:
        print(msft_on_date)

    # Test get_data_window
    print("\nAAPL data from 2023-01-02 to 2023-01-04:")
    aapl_window = dh.get_data_window("AAPL", "2023-01-02", "2023-01-04")
    if aapl_window is not None:
        print(aapl_window)

    # Test with a symbol that has no data
    print("\nLatest MSFT data (should be None or warning):")
    latest_msft = dh.get_latest_data("MSFT")
    if latest_msft is not None:
        print(latest_msft)
    else:
        print("No latest data for MSFT as expected.")

    # Test getting data for a date outside the loaded range
    print("\nAAPL data on 2022-12-31 (before start_date):")
    aapl_outside_date = dh.get_data_at_date("AAPL", "2022-12-31")
    if aapl_outside_date is not None:
        print(aapl_outside_date) # Should be empty

    # Test getting a window where part is outside the loaded range
    print("\nAAPL data from 2023-01-04 to 2023-01-06 (end_date is outside initial dummy data):")
    aapl_partial_window = dh.get_data_window("AAPL", "2023-01-04", "2023-01-06")
    if aapl_partial_window is not None:
        print(aapl_partial_window) # Should show data for 04 and 05

    print("\n--- End of Test ---")
