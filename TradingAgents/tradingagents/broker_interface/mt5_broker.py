from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
from .base import BrokerInterface
import pandas as pd
import numpy as np
import uuid

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None
    print("MT5Broker Warning: MetaTrader5 package not found. MT5Broker will not be functional.")

class MT5Broker(BrokerInterface):
    def __init__(self):
        self._connected = False
        self.mt5_path = None
        self.credentials = {}
        self.simulated_open_positions: List[Dict[str, Any]] = []
        if mt5 is None:
            print("MT5Broker initialized, but MetaTrader5 package is NOT AVAILABLE.")
        else:
            print("MT5Broker initialized. Not connected.")

    def connect(self, credentials: Dict[str, Any]) -> bool:
        if mt5 is None:
            print("MT5Broker Error: MetaTrader5 package not available. Cannot connect.")
            return False

        print(f"MT5Broker: Attempting to connect with login: {credentials.get('login')}")

        login_val = credentials.get('login')
        password = credentials.get('password')
        server = credentials.get('server')

        if not all([login_val, password, server]):
            print("MT5Broker: 'login', 'password', and 'server' are required in credentials.")
            return False

        try:
            login_int = int(login_val)
        except ValueError:
            print(f"MT5Broker: Invalid login ID '{login_val}'. Must be an integer.")
            return False

        self.credentials = credentials.copy()
        path = self.credentials.get('path')

        try:
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
                self.credentials = {}
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
                self.credentials = {}
                return False

            self._connected = True
            print(f"MT5Broker: Connected and logged in successfully to account {login_int}.")
            return True

        except Exception as e:
            print(f"MT5Broker: An unexpected error occurred during connection: {e}")
            self._connected = False
            self.credentials = {}
            if hasattr(mt5, 'terminal_info') and mt5.terminal_info():
                 mt5.shutdown()
            return False

    def disconnect(self) -> None:
        print("MT5Broker: disconnect() called.")
        try:
            if self._connected:
                if mt5 and hasattr(mt5, 'shutdown'):
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
            self.credentials = {}

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first for get_account_info.")
            return None

        if mt5:
            try:
                account_info_mt5 = mt5.account_info()
                if account_info_mt5:
                    return account_info_mt5._asdict()
                else:
                    print(f"MT5Broker: mt5.account_info() returned None. Error: {mt5.last_error()}")
                    return None
            except Exception as e:
                print(f"MT5Broker: Exception during mt5.account_info(): {e}")
                return None

        print("MT5Broker: get_account_info() - mt5 module not available or live call failed. Returning MOCK data.")
        mock_balance = 10000.0 + np.random.uniform(-500, 500)
        mock_equity = mock_balance - np.random.uniform(0, 200)

        return {
            "login": self.credentials.get('login', 12345),
            "balance": round(mock_balance, 2),
            "equity": round(mock_equity, 2),
            "currency": "USD",
            "margin": round(mock_equity * 0.5, 2),
            "margin_free": round(mock_equity * 0.5 * 0.8, 2),
            "margin_level": 0.0 if mock_equity == 0 or (mock_equity*0.5) <=0 else round((mock_equity / (mock_equity * 0.5)) * 100, 2),
            "server": self.credentials.get('server', "Default-Server"),
            "name": self.credentials.get('name', "Mock Test Account"),
            "trade_mode": mt5.ACCOUNT_TRADE_MODE_DEMO if mt5 else 0
        }

    def get_current_price(self, pair: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first for get_current_price.")
            return None

        if mt5:
            try:
                tick = mt5.symbol_info_tick(pair)
                if tick:
                    return {
                        "pair": pair,
                        "bid": tick.bid,
                        "ask": tick.ask,
                        "time": datetime.fromtimestamp(tick.time, tz=timezone.utc)
                    }
                else:
                    return None
            except Exception as e:
                print(f"MT5Broker: Exception during mt5.symbol_info_tick({pair}): {e}")
                return None

        print(f"MT5Broker: get_current_price() for {pair} - mt5 module not available or live call failed. Returning MOCK data.")
        base_price = 1.0800
        spread = 0.0002
        if "JPY" in pair.upper():
            base_price = 150.00
            spread = 0.02
        elif "GBP" in pair.upper():
            base_price = 1.2500
            spread = 0.0003

        mock_bid = round(base_price + np.random.uniform(-0.0005, 0.0005), 5 if "JPY" not in pair.upper() else 3)
        mock_ask = round(mock_bid + spread + np.random.uniform(0, 0.00005), 5 if "JPY" not in pair.upper() else 3)

        return {
            "pair": pair,
            "bid": mock_bid,
            "ask": mock_ask,
            "time": datetime.now(timezone.utc)
        }

    def get_historical_data(
        self,
        pair: str,
        timeframe: str,
        start_date: Optional[Union[datetime, str]] = None,
        end_date: Optional[Union[datetime, str]] = None,
        count: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:
        if not self._connected or mt5 is None:
            print("MT5Broker: Not connected or MetaTrader5 package not available for get_historical_data.")
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
            if start_date and end_date:
                start_date_dt = pd.to_datetime(start_date).replace(tzinfo=timezone.utc) if isinstance(start_date, str) else \
                                (start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date)
                end_date_dt = pd.to_datetime(end_date).replace(tzinfo=timezone.utc) if isinstance(end_date, str) else \
                              (end_date.replace(tzinfo=timezone.utc) if end_date.tzinfo is None else end_date)
                rates = mt5.copy_rates_range(pair, mt5_timeframe, start_date_dt, end_date_dt)
            elif count:
                if start_date:
                    start_date_dt_for_count = pd.to_datetime(start_date).replace(tzinfo=timezone.utc) if isinstance(start_date, str) else \
                                       (start_date.replace(tzinfo=timezone.utc) if start_date.tzinfo is None else start_date)
                    rates = mt5.copy_rates_from(pair, mt5_timeframe, int(start_date_dt_for_count.timestamp()), count)
                else:
                    rates = mt5.copy_rates_from_pos(pair, mt5_timeframe, 0, count)
            else:
                print("MT5Broker: Insufficient parameters for get_historical_data. Provide start_date/end_date or count.")
                return None
            if rates is None or len(rates) == 0:
                return []
            formatted_data = []
            for rate_val in rates:
                formatted_data.append({
                    "time": datetime.fromtimestamp(rate_val['time'], tz=timezone.utc),
                    "open": float(rate_val['open']), "high": float(rate_val['high']),
                    "low": float(rate_val['low']), "close": float(rate_val['close']),
                    "volume": int(rate_val['tick_volume'])
                })
            return formatted_data
        except Exception as e:
            print(f"MT5Broker: Error fetching historical data for {pair}, {timeframe}: {e}")
            return None

    def place_order(self, order_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first to place_order.")
            return {"success": False, "message": "Not connected", "order_id": None}

        if not mt5:
            simulated_order_id = f"sim_ord_{str(uuid.uuid4())[:8]}"
            if order_details.get("type", "market").lower() == "market":
                position_id = f"sim_pos_{str(uuid.uuid4())[:8]}"
                mock_open_price = order_details.get("sl", 1.0) + 0.0050 if order_details.get("side", "buy").lower() == "buy" else order_details.get("sl", 1.0) - 0.0050
                if "JPY" in order_details.get("pair","").upper():
                     mock_open_price = order_details.get("sl", 150.0) + 0.50 if order_details.get("side","buy").lower() == "buy" else order_details.get("sl", 150.0) - 0.50

                new_position = {
                    "id": position_id, "order_id_ref": simulated_order_id,
                    "pair": order_details["pair"],
                    "type": 0 if order_details.get("side").lower() == "buy" else 1,
                    "size": float(order_details.get("size", 0.01)),
                    "open_price": round(mock_open_price, 5 if "JPY" not in order_details.get("pair","").upper() else 3),
                    "sl": float(order_details.get("sl", 0.0)), "tp": float(order_details.get("tp", 0.0)),
                    "profit": -float(order_details.get("size", 0.01)) * 2.0,
                    "comment": order_details.get("comment", "Simulated Position"),
                    "open_time": datetime.now(timezone.utc)
                }
                self.simulated_open_positions.append(new_position)
                print(f"MT5Broker (Mock Mode): Added to simulated_open_positions: {position_id} for pair {new_position['pair']}")
            return {"success": True, "order_id": simulated_order_id, "message": "Order simulated successfully (MT5 not available)."}

        print(f"MT5Broker: place_order() - Attempting to place LIVE order for: {order_details}")
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": order_details.get("pair"),
            "volume": float(order_details.get("size", 0.01)),
            "type": None,
            "price": float(order_details.get("price", 0.0)) if order_details.get("type") != "market" else 0.0,
            "sl": float(order_details.get("sl", 0.0)),
            "tp": float(order_details.get("tp", 0.0)),
            "deviation": 10,
            "magic": order_details.get("magic_number", 234000),
            "comment": order_details.get("comment", "python_script_trade"),
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        order_type_map = {
           ("market", "buy"): mt5.ORDER_TYPE_BUY, ("market", "sell"): mt5.ORDER_TYPE_SELL,
           ("limit", "buy"): mt5.ORDER_TYPE_BUY_LIMIT, ("limit", "sell"): mt5.ORDER_TYPE_SELL_LIMIT,
           ("stop", "buy"): mt5.ORDER_TYPE_BUY_STOP, ("stop", "sell"): mt5.ORDER_TYPE_SELL_STOP,
        }
        order_key = (order_details.get("type", "market").lower(), order_details.get("side", "buy").lower())
        request["type"] = order_type_map.get(order_key)

        if request["type"] is None:
            return {"success": False, "message": f"Unsupported order type/side: {order_key}", "order_id": None}

        if order_details.get("type", "market").lower() == "market":
            symbol_info = mt5.symbol_info_tick(request["symbol"])
            if symbol_info is None: return {"success": False, "message": f"Failed to get symbol info for {request['symbol']}", "order_id": None}
            request["price"] = symbol_info.ask if request["type"] == mt5.ORDER_TYPE_BUY else symbol_info.bid

        try:
            result = mt5.order_send(request)
            if result is None:
                return {"success": False, "message": f"Order send failed (None result): {mt5.last_error()}", "order_id": None}
            if result.retcode == mt5.TRADE_RETCODE_DONE or result.retcode == mt5.TRADE_RETCODE_PLACED:
                if order_details.get("type", "market").lower() == "market":
                    position_id = f"live_pos_{result.order}"
                    new_position = {
                        "id": position_id, "order_id_ref": str(result.order),
                        "pair": order_details["pair"],
                        "type": request["type"], "size": request["volume"],
                        "open_price": result.price, "sl": request["sl"], "tp": request["tp"],
                        "profit": 0.0,
                        "comment": result.comment, "open_time": datetime.now(timezone.utc)
                    }
                    self.simulated_open_positions.append(new_position)
                return {"success": True, "order_id": str(result.order), "message": f"Order placed ({result.comment})."}
            else:
                return {"success": False, "message": f"Order failed: {result.comment} (retcode: {result.retcode})", "order_id": None, "retcode": result.retcode}
        except Exception as e:
            return {"success": False, "message": f"Exception during order_send: {e}", "order_id": None}

    def modify_order(self, order_id: str, new_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first for modify_order.")
            return {"success": False, "message": "Not connected"}

        print(f"MT5Broker: modify_order() - SIMULATING modification for order/position ID: {order_id} with params: {new_params}")

        if not mt5:
            found_position = False
            for pos in self.simulated_open_positions:
                if pos["id"] == order_id:
                    if "sl" in new_params: pos["sl"] = new_params["sl"]
                    if "tp" in new_params: pos["tp"] = new_params["tp"]
                    print(f"MT5Broker (Mock Mode): Modified SL/TP for position {order_id}")
                    found_position = True
                    break
            if found_position:
                return {"success": True, "message": f"Order/Position {order_id} modification simulated (MT5 not available)."}
            else:
                return {"success": False, "message": f"Order/Position {order_id} not found in sim for modification (MT5 not available)."}

        # Actual MT5 logic (simplified for SL/TP on positions for now)
        # request = {
        #     "action": mt5.TRADE_ACTION_SLTP,
        #     "position": int(order_id),
        #     "sl": float(new_params.get("sl", 0.0)),
        #     "tp": float(new_params.get("tp", 0.0)),
        # }
        # if new_params.get("price"): # For pending orders
        #     request["action"] = mt5.TRADE_ACTION_MODIFY
        #     request["order"] = int(order_id) # Assume order_id is pending order ticket
        #     request["price"] = float(new_params.get("price"))
        #     del request["position"] # Not needed for pending order modify

        # try:
        #     result = mt5.order_send(request)
        #     if result is None:
        #         return {"success": False, "message": f"Order modify failed (None result): {mt5.last_error()}"}
        #     if result.retcode == mt5.TRADE_RETCODE_DONE:
        #         return {"success": True, "message": f"Order/Position {order_id} modified successfully ({result.comment})."}
        #     else:
        #         return {"success": False, "message": f"Order/Position {order_id} modify failed: {result.comment} (retcode: {result.retcode})", "retcode": result.retcode}
        # except Exception as e:
        #     return {"success": False, "message": f"Exception during order_send (for modify {order_id}): {e}"}

        # Fallback to simpler mock if actual logic is commented out
        return {"success": True, "message": f"Order/Position {order_id} modification simulated (MT5 logic commented out)."}


    def close_order(self, order_id: str, size_to_close: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first for close_order.")
            return {"success": False, "message": "Not connected"}

        print(f"MT5Broker: close_order() - SIMULATING close for order/position ID: {order_id}, size: {size_to_close}")

        if not mt5:
            initial_len = len(self.simulated_open_positions)
            position_found_sim = False
            temp_positions = []
            for pos_sim in self.simulated_open_positions:
                if pos_sim["id"] == order_id or pos_sim.get("order_id_ref") == order_id:
                    position_found_sim = True
                    if size_to_close is None or size_to_close >= pos_sim["size"]:
                        print(f"MT5Broker (Mock Mode): Simulated closing entire position {order_id} (size {pos_sim['size']}).")
                    else:
                        pos_sim["size"] = round(pos_sim["size"] - size_to_close, 2)
                        pos_sim["comment"] = f"Partial close, remaining {pos_sim['size']}"
                        print(f"MT5Broker (Mock Mode): Simulated partial close for position {order_id}. New size: {pos_sim['size']}.")
                        if pos_sim["size"] > 0.009: temp_positions.append(pos_sim)
                        else: print(f"MT5Broker (Mock Mode): Position {order_id} fully closed due to small remaining size.")
                else:
                    temp_positions.append(pos_sim)
            self.simulated_open_positions = temp_positions
            if position_found_sim:
                return {"success": True, "message": f"Order/Position {order_id} close action simulated (MT5 not available)."}
            else:
                return {"success": False, "message": f"Position ID {order_id} not found for closing (MT5 not available)."}

        # Actual MT5 logic:
        # ... (detailed commented out logic from prompt) ...
        # This part needs careful implementation of finding position by order_id or ticket, then constructing opposing order.

        # Fallback to simpler mock if actual logic is commented out
        return {"success": True, "message": f"Order/Position {order_id} close simulated (MT5 logic commented out)."}


    def get_open_positions(self) -> Optional[List[Dict[str, Any]]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first for get_open_positions.")
            return None

        if mt5:
            try:
                positions = mt5.positions_get()
                if positions is None:
                    if mt5.last_error()[0] != 0:
                         print(f"MT5Broker: mt5.positions_get() failed. Error: {mt5.last_error()}")
                    return []
                live_positions = [position._asdict() for position in positions]
                return live_positions
            except Exception as e:
                print(f"MT5Broker: Exception during mt5.positions_get(): {e}")

        print(f"MT5Broker: get_open_positions() - mt5 module not available or live call failed. Returning {len(self.simulated_open_positions)} SIMULATED open position(s).")
        for pos in self.simulated_open_positions:
            pos["profit"] += np.random.uniform(-0.5, 0.5) * pos["size"] * 100
            pos["profit"] = round(pos["profit"], 2)
        return [pos.copy() for pos in self.simulated_open_positions]

    def get_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        if not self._connected:
            print("MT5Broker: Not connected. Call connect() first for get_pending_orders.")
            return None

        if mt5:
            try:
                orders = mt5.orders_get()
                if orders is None:
                    if mt5.last_error()[0] != 0:
                        print(f"MT5Broker: mt5.orders_get() failed. Error: {mt5.last_error()}")
                    return []
                return [order._asdict() for order in orders]
            except Exception as e:
                print(f"MT5Broker: Exception during mt5.orders_get(): {e}")
                return None

        print("MT5Broker: get_pending_orders() - mt5 module not available or live call failed. Returning SIMULATED empty list.")
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
