from datetime import datetime, timezone # Added timezone
from typing import Any, Dict, List, Optional, Union
from .base import BrokerInterface
# import MetaTrader5 as mt5 # Original import
import pandas as pd # Added pandas
import numpy as np # Added numpy

# Try to import MetaTrader5 and set it to None if it fails
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
    print("MT5Broker Warning: MetaTrader5 package not found. MT5Broker will not be functional.")

class MT5Broker(BrokerInterface):
    def __init__(self):
        self._connected = False
        self.mt5_path = None
        if mt5 is None:
            print("MT5Broker initialized, but MetaTrader5 package is NOT AVAILABLE.")
        else:
            print("MT5Broker initialized. Not connected.")

    def connect(self, credentials: Dict[str, Any]) -> bool:
        if mt5 is None:
            print("MT5Broker Error: MetaTrader5 package not available. Cannot connect.")
            return False

        print(f"MT5Broker: Attempting to connect with login: {credentials.get('login')}")
        try:
            login_val = credentials.get('login')
            if login_val is None:
                print("MT5Broker: Login credential is required.")
                return False

            try:
                login_int = int(login_val)
            except ValueError:
                print(f"MT5Broker: Invalid login ID '{login_val}'. Must be an integer.")
                return False

            password = credentials.get('password')
            server = credentials.get('server')
            path = credentials.get('path')

            if path:
                self.mt5_path = path
                initialized = mt5.initialize(path=self.mt5_path,
                                             login=login_int,
                                             password=password,
                                             server=server)
            else:
                initialized = mt5.initialize(login=login_int,
                                             password=password,
                                             server=server)

            if not initialized:
                print(f"MT5Broker: initialize() failed, error code = {mt5.last_error()}")
                self._connected = False
                return False

            loggedIn = mt5.login(login=login_int,
                                 password=password,
                                 server=server)

            if not loggedIn:
                error_code = mt5.last_error()
                print(f"MT5Broker: login() failed after initialize, error code = {error_code}")
                account_info = mt5.account_info()
                if account_info:
                    print(f"MT5Broker: Account info after failed login: {account_info}")
                else:
                    print(f"MT5Broker: Could not retrieve account info after failed login.")
                mt5.shutdown()
                self._connected = False
                return False

            self._connected = True
            print(f"MT5Broker: Connected and logged in successfully to account {login_int}.")
            return True

        except Exception as e: # Catch other potential errors during the process
            print(f"MT5Broker: An unexpected error occurred during connection: {e}")
            self._connected = False
            # Ensure shutdown if mt5 was partially initialized and an error occurred later
            if hasattr(mt5, 'terminal_info') and mt5.terminal_info(): # Check if mt5 was initialized enough to have terminal_info
                 mt5.shutdown()
            return False

    def disconnect(self) -> None:
        print("MT5Broker: disconnect() called.")
        try:
            if self._connected:
                if mt5 and hasattr(mt5, 'shutdown'): # Check if mt5 is available and has shutdown
                    mt5.shutdown()
                    print("MT5Broker: Disconnected from MetaTrader 5.")
                else:
                    print("MT5Broker: MetaTrader5 module not available or not initialized for shutdown.")
            else:
                print("MT5Broker: Was not connected.")
        except Exception as e:
            print(f"MT5Broker: Error during disconnection: {e}")
        finally:
            self._connected = False

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return None
        print("MT5Broker: get_account_info() called.")
        try:
            account_info = mt5.account_info()
            if account_info:
                return account_info._asdict()
            else:
                print(f"MT5Broker: Failed to retrieve account info, error: {mt5.last_error()}")
                return None
        except Exception as e:
            print(f"MT5Broker: Error in get_account_info: {e}")
            return None

    def get_current_price(self, pair: str) -> Optional[Dict[str, float]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return None
        print(f"MT5Broker: get_current_price() called for {pair}.")
        try:
            tick = mt5.symbol_info_tick(pair)
            if tick:
                return {"bid": tick.bid, "ask": tick.ask, "time": datetime.fromtimestamp(tick.time, tz=timezone.utc)}
            else:
                print(f"MT5Broker: Failed to get tick for {pair}, error: {mt5.last_error()}")
                return None
        except Exception as e:
            print(f"MT5Broker: Error in get_current_price for {pair}: {e}")
            return None

    def get_historical_data(
        self,
        pair: str,
        timeframe: str,
        start_date: Optional[Union[datetime, str]] = None,
        end_date: Optional[Union[datetime, str]] = None,
        count: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return None

        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1, "M2": mt5.TIMEFRAME_M2, "M3": mt5.TIMEFRAME_M3,
            "M4": mt5.TIMEFRAME_M4, "M5": mt5.TIMEFRAME_M5, "M6": mt5.TIMEFRAME_M6,
            "M10": mt5.TIMEFRAME_M10, "M12": mt5.TIMEFRAME_M12, "M15": mt5.TIMEFRAME_M15,
            "M20": mt5.TIMEFRAME_M20, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H2": mt5.TIMEFRAME_H2, "H3": mt5.TIMEFRAME_H3,
            "H4": mt5.TIMEFRAME_H4, "H6": mt5.TIMEFRAME_H6, "H8": mt5.TIMEFRAME_H8,
            "H12": mt5.TIMEFRAME_H12,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
        }

        mt5_timeframe = timeframe_map.get(timeframe.upper())
        if mt5_timeframe is None:
            print(f"MT5Broker: Invalid timeframe provided: {timeframe}")
            return None

        rates = None
        try:
            print(f"MT5Broker: Fetching historical data for {pair}, Timeframe: {timeframe}")
            if start_date and end_date:
                start_date_dt = pd.to_datetime(start_date).replace(tzinfo=timezone.utc) if isinstance(start_date, str) else \
                                (start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date)
                end_date_dt = pd.to_datetime(end_date).replace(tzinfo=timezone.utc) if isinstance(end_date, str) else \
                              (end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date)

                print(f"MT5Broker: Using date range: {start_date_dt} to {end_date_dt}")
                rates = mt5.copy_rates_range(pair, mt5_timeframe, start_date_dt, end_date_dt)
            elif count:
                if start_date:
                    start_date_dt_for_count = pd.to_datetime(start_date).replace(tzinfo=timezone.utc) if isinstance(start_date, str) else \
                                       (start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date)
                    print(f"MT5Broker: Using count {count} ending around {start_date_dt_for_count}")
                    rates = mt5.copy_rates_from(pair, mt5_timeframe, int(start_date_dt_for_count.timestamp()), count)
                else:
                    print(f"MT5Broker: Using count {count} from current position.")
                    rates = mt5.copy_rates_from_pos(pair, mt5_timeframe, 0, count)
            else:
                print("MT5Broker: Insufficient parameters. Provide start_date/end_date or count.")
                return None

            if rates is None or len(rates) == 0:
                print(f"MT5Broker: No data returned from MT5 for {pair}, {timeframe}. Error: {mt5.last_error()}")
                return []

            formatted_data = []
            for rate in rates:
                formatted_data.append({
                    "time": datetime.fromtimestamp(rate['time'], tz=timezone.utc),
                    "open": float(rate['open']),
                    "high": float(rate['high']),
                    "low": float(rate['low']),
                    "close": float(rate['close']),
                    "volume": int(rate['tick_volume'])
                })
            print(f"MT5Broker: Successfully retrieved {len(formatted_data)} bars for {pair} {timeframe}.")
            return formatted_data

        except Exception as e: # Catch other potential errors during MT5 calls
            print(f"MT5Broker: Error fetching historical data for {pair}, {timeframe}: {e}")
            return None


    def place_order(self, order_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return {"success": False, "message": "Not connected or MT5 not available"}
        print(f"MT5Broker: place_order() called with {order_details}.")
        # Actual implementation will follow in a later step
        return {"success": True, "order_id": "12345", "message": "Order placed (simulated)."}

    def modify_order(self, order_id: str, new_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return {"success": False, "message": "Not connected or MT5 not available"}
        print(f"MT5Broker: modify_order() called for order {order_id} with {new_params}.")
        return {"success": True, "message": "Order modified (simulated)."}

    def close_order(self, order_id: str, size_to_close: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return {"success": False, "message": "Not connected or MT5 not available"}
        print(f"MT5Broker: close_order() called for order {order_id}, size {size_to_close}.")
        return {"success": True, "message": "Order closed (simulated)."}

    def get_open_positions(self) -> Optional[List[Dict[str, Any]]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return None
        print("MT5Broker: get_open_positions() called.")
        return [{"id": "123", "pair": "EUR/USD", "type": "buy", "side": "buy", "size": 0.01, "open_price": 1.0800, "sl": 1.0750, "tp": 1.0900, "profit": 5.20}]

    def get_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available.")
            return None
        print("MT5Broker: get_pending_orders() called.")
        return []

if __name__ == "__main__":
    print("This script contains the MT5Broker class implementation.")
    print("To test this class, please refer to the instructions and test script")
    print("provided in 'MT5_TEST_GUIDE.md' located in the same directory.")
    print("\nExample of how to use the test guide:")
    print("1. Set up your MT5 terminal and environment variables as per the guide.")
    print("2. You can copy the test script from the guide into a new Python file (e.g., test_mt5.py)")
    print("   in this directory, or temporarily paste it into the if __name__ == '__main__': block")
    print("   of this file (mt5_broker.py) for quick testing.")
    print("3. Run the script (e.g., `python test_mt5.py` or `python mt5_broker.py`).")
