# MetaTrader 5 (MT5) Broker Integration Test Guide

**Important Update:** The `MT5Broker.py` class has now been enhanced to prioritize **live MetaTrader 5 API calls** for all its main methods if the MT5 package is available and a connection is active. This includes methods for fetching account info, prices, historical data, placing orders, modifying orders, closing orders, and getting open/pending orders.

Mock data or simulated actions are now primarily used as a **fallback** if:
*   The MetaTrader 5 Python package is not installed.
*   Connection to the MT5 terminal fails.
*   A live API call encounters an error.

Always check the `"data_source"` field in the returned data to understand if you are seeing live or fallback (mock/simulated) data.

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

### **CRITICAL: Test Exclusively on a Demo Account First!**

Now that `MT5Broker.py` includes logic for live order placement, modification, and closure, it is **absolutely critical** that you conduct all your initial testing using a **DEMO MetaTrader 5 ACCOUNT**.

*   **Never test directly on a live trading account with real funds until you are completely confident in the system's behavior and have thoroughly tested all functionalities in a demo environment.**
*   Be aware of the risks involved in algorithmic trading.
*   Double-check order sizes, stop-loss, and take-profit parameters.
*   Monitor the MT5 terminal directly to confirm actions taken by the script.

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

        # Instantiate with an agent_id for better logging context
        broker = MT5Broker(agent_id="TestScriptAgent")

        print("CRITICAL: Ensure you are connected to a DEMO MT5 account for this test!")
        print(f"Attempting to connect to MT5 with Login ID: {credentials['login']} on Server: {credentials['server']}...")
        if broker.connect(credentials):
            print("Successfully connected to MT5.")

            print("\nFetching account info...")
            account_info = broker.get_account_info()
            if account_info:
                print(f"Account Info: Login: {account_info.get('login')}, Balance: {account_info.get('balance')}, Equity: {account_info.get('equity')}, Currency: {account_info.get('currency')}, Data Source: {account_info.get('data_source')}")
            else:
                print("Failed to fetch account info.")

            print("\nFetching current price for EURUSD...")
            eurusd_price = broker.get_current_price("EURUSD")
            if eurusd_price:
                print(f"EURUSD: Bid: {eurusd_price.get('bid')}, Ask: {eurusd_price.get('ask')}, Time: {eurusd_price.get('time')}, Data Source: {eurusd_price.get('data_source')}")
            else:
                print("Failed to fetch current price for EURUSD.")

            print("\nFetching historical data for EURUSD M1 (last 10 bars)...")
            eurusd_m1_data = broker.get_historical_data(pair="EURUSD", timeframe="M1", count=10)
            if eurusd_m1_data:
                print(f"Fetched {len(eurusd_m1_data)} M1 bars for EURUSD (Data Source: {eurusd_m1_data[0].get('data_source') if eurusd_m1_data else 'N/A'}):")
                for bar in eurusd_m1_data[:3]: # Print first 3 bars
                    print(f"  Time: {bar['time']}, O: {bar['open']}, H: {bar['high']}, L: {bar['low']}, C: {bar['close']}, V: {bar['volume']}")
            else:
                print("Failed to fetch M1 historical data for EURUSD.")

            print("\nFetching historical data for GBPUSD H1 (specific range)...")
            try:
                end_dt = datetime.now(timezone.utc)
                start_dt = end_dt - timedelta(days=1)
                gbpusd_h1_data = broker.get_historical_data(pair="GBPUSD", timeframe="H1", start_date=start_dt, end_date=end_dt)
                if gbpusd_h1_data:
                    print(f"Fetched {len(gbpusd_h1_data)} H1 bars for GBPUSD (Data Source: {gbpusd_h1_data[0].get('data_source') if gbpusd_h1_data else 'N/A'}):")
                    for bar in gbpusd_h1_data[:3]: # Print first 3 bars
                        print(f"  Time: {bar['time']}, O: {bar['open']}, H: {bar['high']}, L: {bar['low']}, C: {bar['close']}, V: {bar['volume']}")
                else:
                    print("Failed to fetch H1 historical data for GBPUSD.")
            except Exception as e:
                print(f"Error fetching ranged data: {e}")

            # --- Live Trading Action Tests (Use with extreme caution on a Demo Account!) ---
            # print("\n--- Live Action Tests (DEMO ACCOUNT ONLY) ---")

            # Example: Placing a market order (ensure parameters are safe for demo)
            # order_details_live = {
            #     "pair": "USDJPY", "type": "market", "side": "buy",
            #     "size": 0.01, "sl": 140.00, "tp": 160.00,
            #     "comment": "Live Test Order"
            # }
            # print(f"\nAttempting to place live order: {order_details_live}")
            # live_order_result = broker.place_order(order_details_live)
            # print(f"Place Order Result: {live_order_result}")
            # live_order_id = None
            # if live_order_result and live_order_result.get("success"):
            #     live_order_id = live_order_result.get("order_id")
            #     print(f"Live order placed successfully. Order ID: {live_order_id}")

            #     # Example: Getting open positions
            #     print("\nFetching open positions...")
            #     open_positions = broker.get_open_positions()
            #     if open_positions is not None:
            #         print(f"Open Positions ({len(open_positions)}):")
            #         for pos in open_positions:
            #             print(f"  Ticket: {pos.get('ticket')}, Pair: {pos.get('symbol')}, Size: {pos.get('volume')}, Type: {pos.get('type_str')}, Price: {pos.get('price_open')}, SL: {pos.get('sl')}, TP: {pos.get('tp')}, P/L: {pos.get('profit')}, Source: {pos.get('data_source')}")

            #     # Example: Modifying the SL/TP of the placed order (assuming it's a position now)
            #     # MT5 modifies positions by their ticket. The order ID from place_order might be the ticket, or a deal associated with it.
            #     # For simplicity, we'll assume live_order_id is the position ticket if the order resulted in a position.
            #     # This might need adjustment based on how your broker handles order IDs vs position tickets.
            #     position_ticket_to_modify = live_order_id
            #     if position_ticket_to_modify: # Check if we have a ticket
            #         print(f"\nAttempting to modify SL/TP for position ticket: {position_ticket_to_modify}")
            #         modify_params = {"sl": 139.50, "tp": 161.00} # New SL/TP
            #         modify_result = broker.modify_order(position_ticket_to_modify, modify_params)
            #         print(f"Modify Order Result: {modify_result}")

            #     # Example: Closing the position
            #     position_ticket_to_close = live_order_id
            #     if position_ticket_to_close:
            #         print(f"\nAttempting to close position ticket: {position_ticket_to_close}")
            #         close_result = broker.close_order(position_ticket_to_close) # Close full position
            #         print(f"Close Order Result: {close_result}")

            # else:
            #     print("Live order placement failed or no order ID returned, skipping further live action tests.")

            print("\nDisconnecting from MT5...")
            broker.disconnect()
            print("Disconnected.")
        else:
            print("Failed to connect to MT5. Check credentials, server name, MT5 terminal status, and path if provided.")
            print("Ensure the MetaTrader 5 terminal is running and logged into the correct account.")
            print("Also, check 'Allow algorithmic trading' in MT5 options (Tools -> Options -> Expert Advisors).")

    print("\nMT5Broker Test Script Finished.")

```

### Understanding Live vs. Mock/Simulated Behavior

Methods like `get_account_info()`, `get_current_price(pair)`, `get_historical_data(...)`, `place_order(order_details)`, `modify_order(order_id, new_params)`, `close_order(order_id, size_to_close)`, `get_open_positions()`, and `get_pending_orders()` will now attempt to perform live operations with your MT5 terminal if it's connected and the `MetaTrader5` Python package is available.

When you run tests:
*   If MT5 is connected and the operation is successful, the returned dictionary will often include fields like `"data_source": "live"`.
*   If MT5 is not connected, the MT5 library is unavailable, or a live call fails (e.g., invalid parameters, symbol not found, no data returned, trading disabled for the symbol), these methods will fall back to providing mock data or simulating actions. In such cases, the output will include a relevant `"data_source"` value (e.g., `"mock"`, `"simulated"`, `"live_attempt_failed"`, `"simulated_failed_not_found"`).

The test script snippets provided earlier for these methods can still be used. Pay close attention to the `data_source` field in the output to understand whether the data is live from the terminal or a fallback response from the broker class.

For example, to see the mock behavior for methods that don't have extensive examples in the main test script, you can do the following (assuming `broker` is an `MT5Broker` instance that is *not* successfully connected to MT5, or if you temporarily disable MT5 availability in the code for testing fallbacks):

```python
# Ensure broker is not connected or MT5 is unavailable to see fallback behavior.
# broker.disconnect() # if previously connected
# Or, instantiate broker = MT5Broker(agent_id="MockTestAgent") when MT5_AVAILABLE is False

print("\n--- Testing Fallback/Simulated Behaviors ---")

# Test get_account_info (mock)
mock_acc_info = broker.get_account_info()
if mock_acc_info:
    print(f"Fallback Account Info: Login: {mock_acc_info.get('login')}, Balance: {mock_acc_info.get('balance')}, Source: {mock_acc_info.get('data_source')}")

# Test get_current_price (mock)
mock_price = broker.get_current_price("AUDNZD")
if mock_price:
    print(f"Fallback AUDNZD Price: Bid: {mock_price.get('bid')}, Ask: {mock_price.get('ask')}, Source: {mock_price.get('data_source')}")

# Test get_historical_data (mock)
mock_hist = broker.get_historical_data("CADJPY", "M5", count=5)
if mock_hist:
    print(f"Fallback CADJPY M5 Data (first bar): Time: {mock_hist[0].get('time')}, Close: {mock_hist[0].get('close')}, Source: {mock_hist[0].get('data_source')}")


# Test place_order (simulated - adds to internal list)
print("\nSimulating placing a market order for XAUUSD...")
order_details_gold = {
    "pair": "XAUUSD", "type": "market", "side": "sell",
    "size": 0.1, "sl": 2000.00, "tp": 1950.00,
    "comment": "Test simulated XAUUSD sell"
}
sim_order_result = broker.place_order(order_details_gold)
if sim_order_result:
    print(f"Simulated order placement: {sim_order_result}")
    sim_order_id = sim_order_result.get("order_id")

    # Test get_open_positions (simulated)
    sim_positions = broker.get_open_positions()
    if sim_positions is not None:
        print(f"Simulated Open Positions ({len(sim_positions)}):")
        for pos in sim_positions:
            print(f"  ID: {pos.get('id')}, Pair: {pos.get('pair')}, Size: {pos.get('size')}, Open Price: {pos.get('open_price')}, Source: {pos.get('data_source')}")

    # Test modify_order (simulated)
    # Use the 'id' of the simulated position, which might be different from sim_order_id
    # For this example, let's assume the first simulated position is the one we want to modify
    if sim_positions and sim_order_result.get("success"): # Check if we have positions and last order was success
        # Find the actual ID from the simulated_open_positions list, as sim_order_id is just an order ref.
        actual_pos_id_to_modify = None
        for p in broker.simulated_open_positions: # Accessing internal list for test clarity
            if p.get("order_id_ref") == sim_order_id:
                actual_pos_id_to_modify = p.get("id")
                break

        if actual_pos_id_to_modify:
            print(f"\nSimulating modifying position {actual_pos_id_to_modify}...")
            modify_result = broker.modify_order(actual_pos_id_to_modify, {"sl": 2010.00, "tp": 1940.00})
            print(f"Simulated modification result: {modify_result}")
        else:
            print("Could not find simulated position by order_id_ref for modification test.")


    # Test close_order (simulated)
    if sim_positions and sim_order_result.get("success"): # Re-check
        actual_pos_id_to_close = None # Find it again, or assume it's the same one if only one
        for p in broker.simulated_open_positions:
             if p.get("order_id_ref") == sim_order_id: # or use actual_pos_id_to_modify if set
                actual_pos_id_to_close = p.get("id")
                break

        if actual_pos_id_to_close:
            print(f"\nSimulating closing position {actual_pos_id_to_close}...")
            close_result = broker.close_order(actual_pos_id_to_close)
            print(f"Simulated close result: {close_result}")

            sim_positions_after_close = broker.get_open_positions()
            if sim_positions_after_close is not None:
                 print(f"Simulated Open Positions after close ({len(sim_positions_after_close)}): {sim_positions_after_close}")
        else:
            print("Could not find simulated position by order_id_ref for close test.")


# Test get_pending_orders (simulated - currently returns empty list)
print("\nFetching simulated pending orders...")
sim_pending = broker.get_pending_orders()
if sim_pending is not None:
    print(f"Simulated Pending Orders ({len(sim_pending)}): {sim_pending}")

```

This allows you to verify the fallback behavior and the structure of the data returned when live MT5 interaction is not occurring.

## Running the Test

1.  Ensure your MetaTrader 5 terminal is running and logged into the DEMO account specified by your environment variables if you intend to test live functionality.
2.  Open a terminal or command prompt where your Python environment is active and your environment variables are set.
3.  Navigate to the directory containing the script (e.g., `TradingAgents/tradingagents/broker_interface/`).
4.  Run the script: `python mt5_broker.py` (if the test code is in its `if __name__ == "__main__":` block) or `python your_test_script_name.py`.
5.  Observe the output for connection status, account information, price data, historical data, and disconnection messages. Pay attention to the `data_source` field. Check for any error messages.

This guide should help you verify the functionality of the `MT5Broker` class in your own environment.
