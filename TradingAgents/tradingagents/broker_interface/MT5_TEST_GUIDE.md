# MetaTrader 5 (MT5) Broker Integration Test Guide

This guide provides instructions on how to test the `MT5Broker` class, which interfaces with the MetaTrader 5 trading terminal.

## Prerequisites

1.  **MetaTrader 5 Terminal Installed:** You must have the MetaTrader 5 terminal installed on a Windows machine. The Python script will connect to this running terminal.
2.  **Python Environment:** Ensure you have a Python environment (ideally matching the architecture of your MT5 terminal, i.e., 32-bit or 64-bit).
3.  **`MetaTrader5` Python Package:** Install the package:
    ```bash
    pip install MetaTrader5
    ```
    Ensure this package is also listed in your project's `requirements.txt`.
4.  **Allow Algo Trading in MT5 Terminal:**
    *   In your MT5 terminal, go to `Tools -> Options`.
    *   Navigate to the `Expert Advisors` tab.
    *   Check the box for `Allow algorithmic trading`.
    *   (Optional, but might be needed for some functions) You might also need to add specific URLs to the list of allowed URLs if your scripts access external resources, though this is not directly required for the Python-MT5 connection itself.

## Securely Providing Credentials

It is strongly recommended to use environment variables to store your MT5 account credentials and terminal path rather than hardcoding them into scripts.

Set the following environment variables on your system:

*   `MT5_LOGIN`: Your MT5 account number (integer).
*   `MT5_PASSWORD`: Your MT5 account password (string).
*   `MT5_SERVER`: Your MT5 account server name (string, as shown in the MT5 login dialog).
*   `MT5_PATH`: The full path to your `terminal64.exe` or `terminal.exe` file (e.g., `C:\Program Files\MetaTrader 5\terminal64.exe`). This is optional if the `MetaTrader5` Python library can find your terminal automatically, but providing it can resolve connection issues.

**Example (setting environment variables in Windows PowerShell):**
```powershell
$env:MT5_LOGIN = "your_account_number"
$env:MT5_PASSWORD = "your_password"
$env:MT5_SERVER = "your_server_name"
$env:MT5_PATH = "C:\Program Files\MetaTrader 5\terminal64.exe"
```
Remember to replace placeholder values with your actual credentials. For Linux/macOS (if running MT5 via Wine, though direct Python integration is primarily for Windows), you'd use `export VAR_NAME="value"`.

## Test Script

You can use the following Python code snippet to test your `MT5Broker` implementation. You can place this in the `if __name__ == "__main__":` block of your `TradingAgents/tradingagents/broker_interface/mt5_broker.py` file or run it as a separate test script (ensure imports are correct if run separately).

```python
import os
from datetime import datetime, timedelta, timezone # Added timezone
# Ensure this import path is correct based on where you run the script from.
# If mt5_broker.py is in the same directory and you run it directly, it's:
# from mt5_broker import MT5Broker
# If you run from project root (e.g., TradingAgents/):
from tradingagents.broker_interface.mt5_broker import MT5Broker


if __name__ == "__main__":
    print("Starting MT5Broker Test Script...")

    # Load credentials from environment variables
    mt5_login_str = os.getenv("MT5_LOGIN")
    mt5_password = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")
    mt5_path = os.getenv("MT5_PATH") # Optional, can be None

    if not all([mt5_login_str, mt5_password, mt5_server]):
        print("Error: MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER environment variables must be set.")
    else:
        try:
            mt5_login = int(mt5_login_str) # Convert login to int
        except ValueError:
            print(f"Error: MT5_LOGIN environment variable ('{mt5_login_str}') must be an integer account number.")
            exit()

        credentials = {
            "login": mt5_login,
            "password": mt5_password,
            "server": mt5_server,
            "path": mt5_path # Pass the path if set
        }

        broker = MT5Broker()

        print(f"Attempting to connect to MT5 with Login ID: {credentials['login']} on Server: {credentials['server']}...")
        if broker.connect(credentials):
            print("Successfully connected to MT5.")

            print("\nFetching account info...")
            account_info = broker.get_account_info()
            if account_info:
                print(f"Account Info: Balance: {account_info.get('balance')}, Equity: {account_info.get('equity')}, Currency: {account_info.get('currency')}")
            else:
                print("Failed to fetch account info.")

            print("\nFetching current price for EURUSD...")
            eurusd_price = broker.get_current_price("EURUSD")
            if eurusd_price:
                print(f"EURUSD: Bid: {eurusd_price.get('bid')}, Ask: {eurusd_price.get('ask')}, Time: {eurusd_price.get('time')}")
            else:
                print("Failed to fetch current price for EURUSD.")

            print("\nFetching historical data for EURUSD M1 (last 10 bars)...")
            eurusd_m1_data = broker.get_historical_data(pair="EURUSD", timeframe="M1", count=10)
            if eurusd_m1_data:
                print(f"Fetched {len(eurusd_m1_data)} M1 bars for EURUSD:")
                for bar in eurusd_m1_data[:3]: # Print first 3 bars
                    print(f"  Time: {bar['time']}, O: {bar['open']}, H: {bar['high']}, L: {bar['low']}, C: {bar['close']}, V: {bar['volume']}")
            else:
                print("Failed to fetch M1 historical data for EURUSD.")

            print("\nFetching historical data for GBPUSD H1 (specific range)...")
            try:
                # Ensure end_dt and start_dt are timezone-aware (UTC for MT5)
                end_dt = datetime.now(timezone.utc)
                start_dt = end_dt - timedelta(days=1)
                gbpusd_h1_data = broker.get_historical_data(pair="GBPUSD", timeframe="H1", start_date=start_dt, end_date=end_dt)
                if gbpusd_h1_data:
                    print(f"Fetched {len(gbpusd_h1_data)} H1 bars for GBPUSD:")
                    for bar in gbpusd_h1_data[:3]: # Print first 3 bars
                        print(f"  Time: {bar['time']}, O: {bar['open']}, H: {bar['high']}, L: {bar['low']}, C: {bar['close']}, V: {bar['volume']}")
                else:
                    print("Failed to fetch H1 historical data for GBPUSD.")
            except Exception as e:
                print(f"Error fetching ranged data: {e}")


            print("\nDisconnecting from MT5...")
            broker.disconnect()
            print("Disconnected.")
        else:
            print("Failed to connect to MT5. Check credentials, server name, MT5 terminal status, and path if provided.")
            print("Ensure the MetaTrader 5 terminal is running and logged into the correct account.")
            print("Also, check 'Allow algorithmic trading' in MT5 options (Tools -> Options -> Expert Advisors).")

    print("\nMT5Broker Test Script Finished.")

```

## Running the Test

1.  Ensure your MetaTrader 5 terminal is running and logged into the account specified by your environment variables.
2.  Open a terminal or command prompt where your Python environment is active and your environment variables are set.
3.  Navigate to the directory containing the script (e.g., `TradingAgents/tradingagents/broker_interface/`).
4.  Run the script: `python mt5_broker.py` (if the test code is in its `if __name__ == "__main__":` block) or `python your_test_script_name.py`.
5.  Observe the output for connection status, account information, price data, historical data, and disconnection messages. Check for any error messages.

This guide should help you verify the functionality of the `MT5Broker` class in your own environment.
```
