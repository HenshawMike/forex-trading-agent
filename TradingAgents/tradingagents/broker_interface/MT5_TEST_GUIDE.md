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

### Testing Mock Implementations of Other Broker Methods

The `MT5Broker.py` script now includes mock/placeholder implementations for the following methods:

*   `get_account_info()`
*   `get_current_price(pair)`
*   `place_order(order_details)`
*   `modify_order(order_id, new_params)`
*   `close_order(order_id, size_to_close)`
*   `get_open_positions()`
*   `get_pending_orders()`

When you run the test script provided below (or your own test script) *without uncommenting the actual MetaTrader 5 API calls within these methods*, they will return predefined mock data or simulate actions (like adding to an in-memory list of open positions for `place_order` and `get_open_positions`).

You can extend the test script to call these methods and observe their mock behavior. For example, after a successful connection:

```python
# Example additions to the test script:
# ... (after successful connection, but ensure MT5 live calls in broker methods are commented out for pure mock testing) ...

# Test get_account_info (mocked)
print("\nFetching mock account info...")
# Ensure connect was called with some credentials for mock to use them
if not broker._connected: # If previous connection failed, try a mock connect
    print("Attempting mock connect for further tests...")
    broker.connect({"login": 12345, "password": "password", "server": "TestServer"})

mock_acc_info = broker.get_account_info()
if mock_acc_info:
    print(f"Mock Account Info: Login: {mock_acc_info.get('login')}, Balance: {mock_acc_info.get('balance')}")

# Test get_current_price (mocked)
print("\nFetching mock current price for GBPUSD...")
mock_gbpusd_price = broker.get_current_price("GBPUSD")
if mock_gbpusd_price:
    print(f"Mock GBPUSD: Bid: {mock_gbpusd_price.get('bid')}, Ask: {mock_gbpusd_price.get('ask')}")

# Test place_order (simulated - adds to internal list)
print("\nSimulating placing a market order for EURCAD...")
order_details_eurcad = {
    "pair": "EUR/CAD", "type": "market", "side": "buy",
    "size": 0.02, "sl": 1.4500, "tp": 1.4600,
    "comment": "Test mock EURCAD buy"
}
sim_order_result = broker.place_order(order_details_eurcad)
if sim_order_result and sim_order_result.get("success"):
    print(f"Simulated order placement success: ID {sim_order_result.get('order_id')}")

    # Test get_open_positions (simulated - should show the EURCAD order)
    print("\nFetching simulated open positions...")
    sim_positions = broker.get_open_positions()
    if sim_positions is not None:
        print(f"Simulated Open Positions ({len(sim_positions)}):")
        for pos in sim_positions:
            print(f"  ID: {pos.get('id')}, Pair: {pos.get('pair')}, Size: {pos.get('size')}, Open Price: {pos.get('open_price')}")

    # Test modify_order (simulated)
    if sim_positions:
        pos_to_modify_id = sim_positions[0].get("id")
        print(f"\nSimulating modifying position {pos_to_modify_id}...")
        modify_result = broker.modify_order(pos_to_modify_id, {"sl": 1.4450, "tp": 1.4650})
        if modify_result and modify_result.get("success"):
            print(f"Simulated modification success for {pos_to_modify_id}.")
            # Optionally re-fetch and print to see changes if your mock updates the list by reference
            # updated_pos = broker.get_open_positions() ... print ...

    # Test close_order (simulated - should remove from internal list)
    if sim_positions: # Re-check as it might have been cleared by other tests if run multiple times
        pos_to_close_id = sim_positions[0].get("id") # Could be the modified one or original
        print(f"\nSimulating closing position {pos_to_close_id}...")
        close_result = broker.close_order(pos_to_close_id)
        if close_result and close_result.get("success"):
            print(f"Simulated close success for {pos_to_close_id}.")

            print("\nFetching simulated open positions (after close)...")
            sim_positions_after_close = broker.get_open_positions()
            if sim_positions_after_close is not None:
                 print(f"Simulated Open Positions ({len(sim_positions_after_close)}): {sim_positions_after_close}")

else:
    print("Simulated order placement failed or no order ID returned, skipping further mock tests.")

# ... (rest of the original test script, like disconnect) ...
```

This allows you to verify the mocked behavior before you attempt to connect to a live MT5 terminal and test the actual API calls (by uncommenting the relevant sections in `mt5_broker.py`). The primary purpose of this guide remains to assist with testing the *actual* MT5 connection and API calls.

## Running the Test

1.  Ensure your MetaTrader 5 terminal is running and logged into the account specified by your environment variables.
2.  Open a terminal or command prompt where your Python environment is active and your environment variables are set.
3.  Navigate to the directory containing the script (e.g., `TradingAgents/tradingagents/broker_interface/`).
4.  Run the script: `python mt5_broker.py` (if the test code is in its `if __name__ == "__main__":` block) or `python your_test_script_name.py`.
5.  Observe the output for connection status, account information, price data, historical data, and disconnection messages. Check for any error messages.

This guide should help you verify the functionality of the `MT5Broker` class in your own environment.
```
