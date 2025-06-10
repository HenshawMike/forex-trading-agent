from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from .base import BrokerInterface
import pandas as pd
import numpy as np
import uuid

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
    print("MT5Broker INFO: MetaTrader5 package found and imported.")
except ImportError:
    print("MT5Broker INFO: MetaTrader5 package not found. MT5 functionality will be disabled and mocked.")
    MT5_AVAILABLE = False
    class DummyMT5:
        TIMEFRAME_M1, TIMEFRAME_M2, TIMEFRAME_M3, TIMEFRAME_M4, TIMEFRAME_M5 = 1, 2, 3, 4, 5
        TIMEFRAME_M6, TIMEFRAME_M10, TIMEFRAME_M12, TIMEFRAME_M15, TIMEFRAME_M20, TIMEFRAME_M30 = 6, 10, 12, 15, 20, 30
        TIMEFRAME_H1, TIMEFRAME_H2, TIMEFRAME_H3, TIMEFRAME_H4, TIMEFRAME_H6, TIMEFRAME_H8, TIMEFRAME_H12 = 101, 102, 103, 104, 106, 108, 112
        TIMEFRAME_D1, TIMEFRAME_W1, TIMEFRAME_MN1 = 201, 301, 401
        ORDER_TYPE_BUY, ORDER_TYPE_SELL = 0, 1
        ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT = 2, 3
        ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP = 4, 5
        TRADE_ACTION_DEAL, TRADE_ACTION_PENDING, TRADE_ACTION_SLTP, TRADE_ACTION_MODIFY = 1, 2, 3, 4
        TRADE_RETCODE_DONE, TRADE_RETCODE_PLACED = 10009, 10008
        ORDER_TIME_GTC = 0
        ORDER_FILLING_IOC, ORDER_FILLING_FOK = 1, 2
        ACCOUNT_TRADE_MODE_DEMO, ACCOUNT_TRADE_MODE_REAL = 0, 1
        _last_error = (0, "No error (DummyMT5)")
        def __getattr__(self, name):
            def dummy_method(*args, **kwargs):
                if name == "account_info": return None
                if name == "symbol_info_tick": return None
                if name == "copy_rates_range": return None
                if name == "copy_rates_from": return None
                if name == "copy_rates_from_pos": return None
                if name == "order_send": return None
                if name == "positions_get": return None
                if name == "orders_get": return None
                if name == "last_error": return DummyMT5._last_error
                return None
            return dummy_method
    if not MT5_AVAILABLE:
        mt5 = DummyMT5()

class MT5Broker(BrokerInterface):
    def __init__(self, agent_id: Optional[str] = "MT5BrokerInstance"): # NEW
        self._connected = False
        self.credentials = {}
        self.simulated_open_positions: List[Dict[str, Any]] = []
        self.mt5_path = None
        self.mt5_available = MT5_AVAILABLE
        self._mock_price_cache: Dict[str, float] = {} # For get_current_price mock
        self.agent_id = agent_id # Store agent_id
        if not self.mt5_available:
            print(f"MT5Broker INFO (Agent: {self.agent_id}): MetaTrader5 package not found at init. Live MT5 calls will be skipped; mock logic will be used.")
        else:
            print(f"MT5Broker (Agent: {self.agent_id}) initialized. Not connected.")

    def connect(self, credentials: Dict[str, Any]) -> bool:
        if not self.mt5_available:
            print("MT5Broker Error: MetaTrader5 package not available. Cannot connect.")
            self._connected = False
            return False
        print(f"MT5Broker: Attempting to connect with login: {credentials.get('login')}")
        login_val = credentials.get('login')
        password = credentials.get('password')
        server = credentials.get('server')
        if not all([login_val, password, server]):
            print("MT5Broker: 'login', 'password', and 'server' are required in credentials.")
            return False
        try: login_int = int(login_val)
        except ValueError: print(f"MT5Broker: Invalid login ID '{login_val}'. Must be an integer."); return False
        self.credentials = credentials.copy()
        path = self.credentials.get('path')
        try:
            if path: self.mt5_path = path; initialized = mt5.initialize(path=self.mt5_path, login=login_int, password=password, server=server)
            else: initialized = mt5.initialize(login=login_int, password=password, server=server)
            if not initialized: print(f"MT5Broker: initialize() failed, error code = {mt5.last_error()}"); self._connected = False; self.credentials = {}; return False
            loggedIn = mt5.login(login=login_int, password=password, server=server)
            if not loggedIn:
                error_code = mt5.last_error(); print(f"MT5Broker: login() failed, error code = {error_code}")
                mt5.shutdown(); self._connected = False; self.credentials = {}; return False
            self._connected = True; print(f"MT5Broker: Connected and logged in to account {login_int}."); return True
        except Exception as e:
            print(f"MT5Broker: Unexpected error during connection: {e}"); self._connected = False; self.credentials = {}
            if hasattr(mt5, 'terminal_info') and mt5.terminal_info(): mt5.shutdown()
            return False

    def disconnect(self) -> None:
        print("MT5Broker: disconnect() called.")
        try:
            if self._connected and self.mt5_available and hasattr(mt5, 'shutdown'): mt5.shutdown(); print("MT5Broker: Disconnected from MetaTrader 5.")
            elif self._connected: print("MT5Broker: Conceptually connected, but MT5 lib not available for shutdown.")
            else: print("MT5Broker: Was not connected.")
        except Exception as e: print(f"MT5Broker: Error during disconnection: {e}")
        finally: self._connected = False; self.credentials = {}

    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self._connected: print("MT5Broker: Not connected for get_account_info."); return None
        if self.mt5_available:
            print("MT5Broker: Attempting to fetch LIVE account info...")
            try:
                account_info_mt5 = mt5.account_info()
                if account_info_mt5 is not None:
                    live_info = account_info_mt5._asdict(); live_info["data_source"] = "live"
                    print(f"MT5Broker: Live account info: Login {live_info.get('login')}"); return live_info
                else: print(f"MT5Broker: mt5.account_info() returned None. Error: {mt5.last_error()}");
            except Exception as e: print(f"MT5Broker: Exc in LIVE mt5.account_info(): {e}.")
        reason = "(MT5 N/A)" if not self.mt5_available else "(Not connected)" if not self._connected else "(Live call failed)"
        print(f"MT5Broker: get_account_info() - MOCK data {reason}.")
        bal = 10000.0 + np.random.uniform(-500,500); eq = bal - np.random.uniform(0,200); mu = eq*0.5
        return {"login": self.credentials.get('login',12345), "balance":round(bal,2), "equity":round(eq,2), "currency":"USD",
                "margin":round(mu,2), "margin_free":round(eq-mu,2), "margin_level":0.0 if mu==0 else round((eq/mu)*100,2),
                "server":self.credentials.get('server',"Default"), "name":self.credentials.get('name',"Mock"),
                "trade_mode":mt5.ACCOUNT_TRADE_MODE_DEMO if self.mt5_available and hasattr(mt5,'ACCOUNT_TRADE_MODE_DEMO') else 0, "data_source":"mock"}

    def _get_mock_current_price(self, pair: str, reason: str = "Fallback") -> Dict[str, Any]:
        print(f"MT5Broker: _get_mock_current_price() for {pair}. Reason: {reason}.")
        base_price = 1.0800; spread = 0.0002
        if "JPY" in pair.upper(): base_price = 150.00; spread = 0.02
        elif "GBP" in pair.upper(): base_price = 1.2500; spread = 0.0003

        if pair not in self._mock_price_cache: self._mock_price_cache[pair] = base_price
        self._mock_price_cache[pair] += np.random.uniform(-0.00005, 0.00005) * (100 if "JPY" in pair.upper() else 1)
        self._mock_price_cache[pair] = round(self._mock_price_cache[pair], 5 if "JPY" not in pair.upper() else 3)

        current_base_price = self._mock_price_cache[pair]
        mock_bid = round(current_base_price - (spread/2.0) + np.random.uniform(-0.00001,0.00001)*(100 if "JPY" in pair else 1), 5 if "JPY" not in pair else 3)
        mock_ask = round(current_base_price + (spread/2.0) + np.random.uniform(-0.00001,0.00001)*(100 if "JPY" in pair else 1), 5 if "JPY" not in pair else 3)
        return {"pair": pair, "bid": mock_bid, "ask": mock_ask, "time": datetime.now(timezone.utc), "data_source": "mock"}

    def get_current_price(self, pair: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print("MT5Broker: Not connected. Using mock for get_current_price.")
            return self._get_mock_current_price(pair, reason="Not connected")
        if self.mt5_available:
            # print(f"MT5Broker: Attempting to fetch LIVE current price for {pair}...") # Verbose
            try:
                tick = mt5.symbol_info_tick(pair)
                if tick:
                    tick_time = datetime.fromtimestamp(tick.time, tz=timezone.utc) if hasattr(tick, 'time') and tick.time else datetime.now(timezone.utc)
                    return {"pair": pair, "bid": tick.bid, "ask": tick.ask, "time": tick_time, "data_source": "live"}
                else:
                    error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                    print(f"MT5Broker: mt5.symbol_info_tick({pair}) returned None. Error: {error_code} - {error_message}")
            except Exception as e: print(f"MT5Broker: Exc in LIVE mt5.symbol_info_tick({pair}): {e}.")
        return self._get_mock_current_price(pair, reason="Fallback (MT5 unavailable or live call failed)")

    # ... (other methods like get_current_price remain) ...

    def _get_mock_historical_data(self, pair: str, timeframe: str, count: int) -> List[Dict[str, Any]]:
        print(f"MT5Broker: _get_mock_historical_data() for {pair}, TF={timeframe}, Count={count}")
        bars = []
        current_time = datetime.now(timezone.utc)
        # Determine frequency for mock data based on timeframe string (simplified)
        if 'M' in timeframe.upper() and 'MN' not in timeframe.upper() : # M1, M5, M15, M30
            delta = timedelta(minutes=int(timeframe[1:] if len(timeframe)>1 else 1))
        elif 'H' in timeframe.upper(): # H1, H4
            delta = timedelta(hours=int(timeframe[1:] if len(timeframe)>1 else 1))
        elif 'D' in timeframe.upper(): # D1
            delta = timedelta(days=1)
        elif 'W' in timeframe.upper(): # W1
            delta = timedelta(weeks=1)
        elif 'MN' in timeframe.upper(): # MN1
            delta = timedelta(days=30) # Approximation
        else:
            delta = timedelta(minutes=15) # Default mock delta

        # Generate mock bars backwards from current_time
        # Simulate some price action
        price = 1.0800
        if "JPY" in pair.upper(): price = 150.00
        elif "GBP" in pair.upper(): price = 1.2500

        for i in range(count):
            timestamp = current_time - (delta * (count - 1 - i))
            o = round(price + np.random.uniform(-0.001, 0.001) * (100 if "JPY" in pair.upper() else 1), 5 if "JPY" not in pair.upper() else 3)
            c = round(o + np.random.uniform(-0.001, 0.001) * (100 if "JPY" in pair.upper() else 1), 5 if "JPY" not in pair.upper() else 3)
            h = round(max(o, c) + np.random.uniform(0, 0.0005) * (100 if "JPY" in pair.upper() else 1), 5 if "JPY" not in pair.upper() else 3)
            l = round(min(o, c) - np.random.uniform(0, 0.0005) * (100 if "JPY" in pair.upper() else 1), 5 if "JPY" not in pair.upper() else 3)
            vol = np.random.randint(100,1000)
            bars.append({"time": timestamp, "open":o, "high":h, "low":l, "close":c, "volume":vol})
            price = c # Next bar opens near current close

        for bar in bars: # Add data_source to each bar
            bar["data_source"] = "mock"
        return bars

    def get_historical_data(
        self,
        pair: str,
        timeframe: str,
        start_date: Optional[Union[datetime, str]] = None,
        end_date: Optional[Union[datetime, str]] = None,
        count: Optional[int] = None
    ) -> Optional[List[Dict[str, Any]]]:

        effective_count = count if count else 100 # Default count for mock if not specified

        if not self._connected:
            print("MT5Broker: Not connected for get_historical_data.")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

        if not self.mt5_available:
            print("MT5Broker: MT5 library not available for get_historical_data.")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

        print(f"MT5Broker: Attempting to fetch LIVE historical data for {pair}, TF={timeframe}, Count={count}, Start={start_date}, End={end_date}...")

        timeframe_map = {
            "M1": mt5.TIMEFRAME_M1, "M2": mt5.TIMEFRAME_M2, "M3": mt5.TIMEFRAME_M3, "M4": mt5.TIMEFRAME_M4, "M5": mt5.TIMEFRAME_M5,
            "M6": mt5.TIMEFRAME_M6, "M10": mt5.TIMEFRAME_M10, "M12": mt5.TIMEFRAME_M12, "M15": mt5.TIMEFRAME_M15,
            "M20": mt5.TIMEFRAME_M20, "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1, "H2": mt5.TIMEFRAME_H2, "H3": mt5.TIMEFRAME_H3, "H4": mt5.TIMEFRAME_H4,
            "H6": mt5.TIMEFRAME_H6, "H8": mt5.TIMEFRAME_H8, "H12": mt5.TIMEFRAME_H12,
            "D1": mt5.TIMEFRAME_D1, "W1": mt5.TIMEFRAME_W1, "MN1": mt5.TIMEFRAME_MN1
        }
        mt5_timeframe = timeframe_map.get(timeframe.upper())
        if mt5_timeframe is None:
            print(f"MT5Broker: Invalid timeframe string '{timeframe}'. Falling back to mock.")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

        rates = None
        try:
            if start_date and end_date:
                s_date_dt = pd.to_datetime(start_date).replace(tzinfo=timezone.utc) if isinstance(start_date, str) else \
                            (start_date.astimezone(timezone.utc) if start_date.tzinfo is None else start_date)
                e_date_dt = pd.to_datetime(end_date).replace(tzinfo=timezone.utc) if isinstance(end_date, str) else \
                            (end_date.astimezone(timezone.utc) if end_date.tzinfo is None else end_date)
                rates = mt5.copy_rates_range(pair, mt5_timeframe, s_date_dt, e_date_dt)
            elif count:
                if start_date:
                    s_date_dt = pd.to_datetime(start_date).replace(tzinfo=timezone.utc) if isinstance(start_date, str) else \
                                (start_date.astimezone(timezone.utc) if start_date.tzinfo is None else start_date)
                    rates = mt5.copy_rates_from(pair, mt5_timeframe, s_date_dt, count)
                else:
                    rates = mt5.copy_rates_from_pos(pair, mt5_timeframe, 0, count)
            else: # Default to last 'effective_count' bars if no range or count specified for live data
                print(f"MT5Broker: Insufficient parameters for live get_historical_data (need range or count). Defaulting to last {effective_count} bars.")
                rates = mt5.copy_rates_from_pos(pair, mt5_timeframe, 0, effective_count)


            if rates is None or len(rates) == 0:
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error or no data")
                print(f"MT5Broker: No data returned from MT5 for {pair}, TF={timeframe}. Error: {error_code} - {error_message}. Falling back to mock.")
                return self._get_mock_historical_data(pair, timeframe, effective_count)

            formatted_data = []
            for rate in rates:
                formatted_data.append({
                    "time": datetime.fromtimestamp(rate['time'], tz=timezone.utc),
                    "open": float(rate['open']), "high": float(rate['high']),
                    "low": float(rate['low']), "close": float(rate['close']),
                    "volume": int(rate['tick_volume']),
                    "data_source": "live"
                })
            print(f"MT5Broker: Live historical data fetched for {pair}, {len(formatted_data)} bars.")
            return formatted_data

        except Exception as e:
            print(f"MT5Broker: Exception during LIVE get_historical_data for {pair}, TF={timeframe}: {e}. Falling back to mock.")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

    def _simulate_place_order(self, order_details: Dict[str, Any], fail_reason: Optional[str] = None) -> Dict[str, Any]:
        reason_prefix = f"Simulated order ({fail_reason if fail_reason else 'MT5 unavailable/disconnected'})."
        print(f"MT5Broker ({self.agent_id}): {reason_prefix} Details: {order_details}")

        simulated_order_id = f"sim_ord_{str(uuid.uuid4())[:8]}"

        # Only add to simulated_open_positions if it's a market order in simulation
        if order_details.get("type", "market").lower() == "market":
            position_id = f"sim_pos_{str(uuid.uuid4())[:8]}"

            mock_open_price_default = 1.0825 # A generic price
            pair_upper = order_details.get("pair", "").upper()
            if "JPY" in pair_upper: mock_open_price_default = 150.25

            sl_val = order_details.get("sl")
            mock_open_price = mock_open_price_default # Default to generic price

            if sl_val is not None:
                try:
                    sl_float = float(sl_val)
                    price_offset = 0.50 if "JPY" in pair_upper else 0.0050
                    if order_details.get("side","buy").lower() == "buy":
                        mock_open_price = sl_float + price_offset
                    else:
                        mock_open_price = sl_float - price_offset
                except ValueError:
                    print(f"MT5Broker ({self.agent_id}): Invalid SL value '{sl_val}' for simulation, using default price {mock_open_price_default}.")
                    mock_open_price = mock_open_price_default # Fallback to default if SL is invalid

            new_position = {
                "id": position_id, "order_id_ref": simulated_order_id,
                "pair": order_details["pair"],
                "type": mt5.ORDER_TYPE_BUY if order_details.get("side", "buy").lower() == "buy" else mt5.ORDER_TYPE_SELL,
                "size": float(order_details.get("size", 0.01)),
                "open_price": round(mock_open_price, 5 if "JPY" not in pair_upper else 3),
                "sl": float(order_details.get("sl", 0.0)), "tp": float(order_details.get("tp", 0.0)),
                "profit": -float(order_details.get("size", 0.01)) * 2.0, # Simulate spread cost
                "comment": order_details.get("comment", f"SimPos_{self.agent_id}"),
                "open_time": datetime.now(timezone.utc),
                "data_source": "simulated"
            }
            self.simulated_open_positions.append(new_position)
            print(f"MT5Broker ({self.agent_id}): Added to simulated_open_positions: {position_id} for pair {new_position['pair']}")

        return {"success": True, "order_id": simulated_order_id, "message": f"Order simulated successfully. {reason_prefix}", "data_source": "simulated"}


    def place_order(self, order_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Initial connectivity checks
        if not self._connected:
            print(f"MT5Broker ({self.agent_id}): Not connected for place_order.")
            return self._simulate_place_order(order_details, "Not connected")
        if not self.mt5_available:
            print(f"MT5Broker ({self.agent_id}): MT5 library not available for place_order.")
            return self._simulate_place_order(order_details, "MT5 library N/A")

        print(f"MT5Broker ({self.agent_id}): Attempting to place LIVE order for: {order_details}")

        order_type_map = {
            ("market", "buy"): mt5.ORDER_TYPE_BUY,
            ("market", "sell"): mt5.ORDER_TYPE_SELL,
            ("limit", "buy"): mt5.ORDER_TYPE_BUY_LIMIT,
            ("limit", "sell"): mt5.ORDER_TYPE_SELL_LIMIT,
            ("stop", "buy"): mt5.ORDER_TYPE_BUY_STOP,
            ("stop", "sell"): mt5.ORDER_TYPE_SELL_STOP,
        }

        order_key_type = order_details.get("type", "market").lower()
        order_key_side = order_details.get("side", "buy").lower()
        mt5_order_type = order_type_map.get((order_key_type, order_key_side))

        if mt5_order_type is None:
            print(f"MT5Broker ({self.agent_id}): Unsupported order type/side combination: {order_key_type}/{order_key_side}")
            return {"success": False, "message": f"Unsupported order type/side: {order_key_type}/{order_key_side}", "order_id": None, "data_source": "live_attempt_failed"}

        pair_symbol = order_details.get("pair")
        if not pair_symbol:
            return {"success": False, "message": "Pair must be specified for placing an order.", "order_id": None, "data_source": "input_error"}


        try:
            symbol_info = mt5.symbol_info(pair_symbol)
            if symbol_info is None:
                print(f"MT5Broker ({self.agent_id}): Symbol {pair_symbol} not found by MT5. Attempting to select.")
                if not mt5.symbol_select(pair_symbol, True):
                    print(f"MT5Broker ({self.agent_id}): Failed to select symbol {pair_symbol} in MarketWatch. Error: {mt5.last_error()}")
                    return {"success": False, "message": f"Failed to select symbol {pair_symbol}", "order_id": None, "data_source": "live_attempt_failed"}
                mt5.sleep(100) # ms, wait for symbol to be ready in MarketWatch
                symbol_info = mt5.symbol_info(pair_symbol)
                if symbol_info is None:
                     print(f"MT5Broker ({self.agent_id}): Symbol {pair_symbol} still not found after select.")
                     return {"success": False, "message": f"Symbol {pair_symbol} not found", "order_id": None, "data_source": "live_attempt_failed"}
        except Exception as e_sym:
            print(f"MT5Broker ({self.agent_id}): Exception getting symbol info for {pair_symbol}: {e_sym}. Cannot place order.")
            return {"success": False, "message": f"Exception getting symbol info: {e_sym}", "order_id": None, "data_source": "live_attempt_failed"}

        current_price_for_market = 0.0
        if order_key_type == "market":
            tick = mt5.symbol_info_tick(pair_symbol)
            if not tick:
                print(f"MT5Broker ({self.agent_id}): Could not get tick for {pair_symbol} for market order. Error: {mt5.last_error()}")
                return {"success": False, "message": f"Could not get tick for {pair_symbol}", "order_id": None, "data_source": "live_attempt_failed"}
            current_price_for_market = tick.ask if order_key_side == "buy" else tick.bid

        request_price = float(order_details.get("price", 0.0)) if order_key_type != "market" else current_price_for_market

        if order_key_type != "market" and request_price == 0.0: # Price must be set for pending orders
            return {"success": False, "message": "Price must be set for pending orders and cannot be zero.", "order_id": None, "data_source": "input_error"}

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_key_type == "market" else mt5.TRADE_ACTION_PENDING,
            "symbol": pair_symbol,
            "volume": float(order_details.get("size", 0.01)),
            "type": mt5_order_type,
            "price": request_price,
            "sl": float(order_details.get("sl", 0.0)),
            "tp": float(order_details.get("tp", 0.0)),
            "deviation": 20,
            "magic": order_details.get("magic_number", 234000),
            "comment": order_details.get("comment", self.agent_id),
            "type_time": order_details.get("type_time", mt5.ORDER_TIME_GTC),
            "type_filling": order_details.get("type_filling", mt5.ORDER_FILLING_FOK),
        }

        try:
            print(f"MT5Broker ({self.agent_id}): Sending LIVE order request: {request}")
            result = mt5.order_send(request)

            if result is None: # Should not happen if API is responsive, but good to check
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error (result is None)")
                print(f"MT5Broker ({self.agent_id}): order_send failed, returned None. Error: {error_code} - {error_message}")
                return self._simulate_place_order(order_details, f"Order send None result: {error_message} (Code: {error_code})")

            # Check retcode for success
            if result.retcode in [mt5.TRADE_RETCODE_DONE, mt5.TRADE_RETCODE_PLACED]:
                print(f"MT5Broker ({self.agent_id}): LIVE Order placed/sent successfully. Order ID: {result.order}, Comment: {result.comment}")
                return {"success": True, "order_id": str(result.order), "message": f"Order placed successfully ({result.comment}).", "data_source": "live"}
            else:
                print(f"MT5Broker ({self.agent_id}): LIVE Order failed. Retcode: {result.retcode}, Comment: {result.comment}, Request: {result.request._asdict() if result.request else 'N/A'}")
                return {"success": False, "message": f"Order failed: {result.comment} (retcode: {result.retcode})", "order_id": None, "retcode": result.retcode, "data_source": "live_attempt_failed"}

        except Exception as e:
            print(f"MT5Broker ({self.agent_id}): Exception during LIVE mt5.order_send(): {e}. Falling back to simulation.")
            return self._simulate_place_order(order_details, f"Exception: {str(e)}")


    def _simulate_modify_order(self, order_id: str, new_params: Dict[str, Any], reason: Optional[str] = None) -> Dict[str, Any]:
        reason_prefix = f"Simulated modify ({reason if reason else 'MT5 unavailable/disconnected'})."
        print(f"MT5Broker ({self.agent_id}): {reason_prefix} Order/Pos ID: {order_id}, Params: {new_params}")

        found_position = False
        # Attempt to modify in simulated_open_positions (covers market orders that became positions)
        for pos in self.simulated_open_positions:
            if pos.get("id") == order_id or pos.get("order_id_ref") == order_id:
                if "sl" in new_params and new_params["sl"] is not None:
                    pos["sl"] = float(new_params["sl"])
                    print(f"MT5Broker ({self.agent_id}): Simulated SL update for position {order_id} to {new_params['sl']}")
                if "tp" in new_params and new_params["tp"] is not None:
                    pos["tp"] = float(new_params["tp"])
                    print(f"MT5Broker ({self.agent_id}): Simulated TP update for position {order_id} to {new_params['tp']}")
                # Price modification for open positions is not typical via 'modify_order' (usually SL/TP)
                # If 'price' is in new_params, it might imply a pending order, which we are not separately tracking in simulation yet.
                if "price" in new_params and new_params["price"] is not None:
                     print(f"MT5Broker ({self.agent_id}): Simulated price modification for {order_id} to {new_params['price']} (Note: Typically for pending orders).")
                found_position = True
                break

        # In a more complex simulation, we might have a self.simulated_pending_orders list
        # and check/modify it here if 'price' in new_params indicates a pending order mod.

        if found_position:
            return {"success": True, "message": f"Order/Position {order_id} modification simulated successfully.", "data_source": "simulated"}
        else:
            print(f"MT5Broker ({self.agent_id}): Order/Position ID {order_id} not found in simulated open positions for modification.")
            return {"success": False, "message": f"Order/Position ID {order_id} not found for simulated modification.", "data_source": "simulated_failed_not_found"}

    def modify_order(self, order_id: str, new_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print(f"MT5Broker ({self.agent_id}): Not connected for modify_order. Simulating.")
            return self._simulate_modify_order(order_id, new_params, reason="Not connected")
        if not self.mt5_available:
            print(f"MT5Broker ({self.agent_id}): MT5 library not available for modify_order. Simulating.")
            return self._simulate_modify_order(order_id, new_params, reason="MT5 library unavailable")

        print(f"MT5Broker ({self.agent_id}): Attempting to LIVE modify order/position ID: {order_id} with params: {new_params}")

        request = {}
        try:
            ticket_to_modify = int(order_id)
        except ValueError:
            print(f"MT5Broker ({self.agent_id}): Invalid order_id format '{order_id}'. Must be an integer string.")
            return {"success": False, "message": f"Invalid order_id format '{order_id}'.", "data_source": "input_error"}


        # Try to determine if it's a position or a pending order
        # First, check if it's an open position
        target_symbol = None
        is_position_modification = False
        position_info_list = mt5.positions_get(ticket=ticket_to_modify)

        if position_info_list and len(position_info_list) > 0:
            is_position_modification = True
            target_symbol = position_info_list[0].symbol
            print(f"MT5Broker ({self.agent_id}): Modifying open position {ticket_to_modify} for symbol {target_symbol}.")
            request["action"] = mt5.TRADE_ACTION_SLTP
            request["position"] = ticket_to_modify
            request["symbol"] = target_symbol
            if "sl" in new_params and new_params["sl"] is not None: request["sl"] = float(new_params["sl"])
            if "tp" in new_params and new_params["tp"] is not None: request["tp"] = float(new_params["tp"])
        else:
            # If not an open position, check if it's a pending order
            order_info_list = mt5.orders_get(ticket=ticket_to_modify)
            if order_info_list and len(order_info_list) > 0:
                pending_order_info = order_info_list[0]
                target_symbol = pending_order_info.symbol
                print(f"MT5Broker ({self.agent_id}): Modifying pending order {ticket_to_modify} for symbol {target_symbol}.")
                request["action"] = mt5.TRADE_ACTION_MODIFY
                request["order"] = ticket_to_modify
                request["symbol"] = target_symbol

                # For pending order modification, MT5 often requires resending all relevant parameters
                request["price"] = float(new_params.get("price", pending_order_info.price_open))
                request["sl"] = float(new_params.get("sl", pending_order_info.sl))
                request["tp"] = float(new_params.get("tp", pending_order_info.tp))
                request["volume"] = pending_order_info.volume_current # Volume usually cannot be changed by modify, but good to include
                request["type"] = pending_order_info.type # Order type cannot be changed
                request["type_time"] = pending_order_info.type_time
                request["type_filling"] = pending_order_info.type_filling
                # Potentially other fields like 'deviation' if applicable to the original order type.
            else:
                print(f"MT5Broker ({self.agent_id}): Order/Position {ticket_to_modify} not found.")
                return {"success": False, "message": f"Order/Position {ticket_to_modify} not found.", "data_source": "live_attempt_failed_not_found"}

        # Check if any modifiable parameter is actually being changed
        no_change = True
        if is_position_modification:
            if "sl" in request or "tp" in request: no_change = False
        else: # Pending order
            if pending_order_info: # Ensure pending_order_info is defined
                if request.get("price") != pending_order_info.price_open: no_change = False
                if request.get("sl") != pending_order_info.sl: no_change = False
                if request.get("tp") != pending_order_info.tp: no_change = False
            else: # Should not happen if logic flows correctly
                 return {"success": False, "message": "Internal error: pending_order_info not available.", "data_source": "internal_error"}


        if no_change and not ("sl" in new_params or "tp" in new_params or "price" in new_params): # Check new_params directly
             print(f"MT5Broker ({self.agent_id}): No new SL, TP, or Price provided in new_params for modification of {order_id}.")
             return {"success": False, "message": "No new SL, TP, or Price provided for modification.", "data_source": "input_error"}
        elif no_change and ("sl" not in request and "tp" not in request and "price" not in request): # Check request after filling from existing
             print(f"MT5Broker ({self.agent_id}): No actual change in SL, TP, or Price for modification of {order_id}.")
             # This could be debatable. If user provides same SL/TP, is it success or failure? MT5 might return success.
             # For now, let's consider it a case where no modification is sent if values are identical to current.
             return {"success": True, "message": "No actual change in SL, TP, or Price values; modification not sent.", "data_source": "no_change_needed"}


        try:
            print(f"MT5Broker ({self.agent_id}): Sending LIVE modify request: {request}")
            result = mt5.order_send(request)

            if result is None:
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                print(f"MT5Broker ({self.agent_id}): order_send (for modify) failed, returned None. Error: {error_code} - {error_message}")
                # Consider simulating if result is None, as it implies a connection/terminal issue
                return self._simulate_modify_order(order_id, new_params, reason=f"Live modify returned None: {error_message}")

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"MT5Broker ({self.agent_id}): LIVE Order/Position {order_id} modified successfully. Comment: {result.comment}")
                return {"success": True, "message": f"Order/Position {order_id} modified successfully ({result.comment}).", "data_source": "live"}
            else:
                print(f"MT5Broker ({self.agent_id}): LIVE Order/Position {order_id} modify failed. Retcode: {result.retcode}, Comment: {result.comment}, Request: {result.request._asdict() if result.request else 'N/A'}")
                return {"success": False, "message": f"Order/Position {order_id} modify failed: {result.comment} (retcode: {result.retcode})", "retcode": result.retcode, "data_source": "live_attempt_failed"}

        except Exception as e:
            print(f"MT5Broker ({self.agent_id}): Exception during LIVE mt5.order_send (for modify {order_id}): {e}. Simulating.")
            return self._simulate_modify_order(order_id, new_params, reason=f"Exception during live modify: {e}")

    def _simulate_close_order(self, order_id_or_ticket: str, size_to_close: Optional[float] = None, reason: Optional[str] = None) -> Dict[str, Any]:
        reason_prefix = f"Simulated close ({reason if reason else 'MT5 unavailable/disconnected'})."
        print(f"MT5Broker ({self.agent_id}): {reason_prefix} Order/Pos ID: {order_id_or_ticket}, Size: {size_to_close}")

        position_found_and_acted_on = False
        temp_positions = []
        for pos in self.simulated_open_positions:
            # Assuming order_id_or_ticket for mock is the 'id' field we assigned or 'order_id_ref'
            if str(pos.get("id")) == str(order_id_or_ticket) or str(pos.get("order_id_ref")) == str(order_id_or_ticket):
                position_found_and_acted_on = True
                current_pos_size = float(pos.get("size", 0.01))
                effective_size_to_close = size_to_close if size_to_close is not None and size_to_close > 0 else current_pos_size

                if effective_size_to_close >= current_pos_size - 0.00001: # Account for float precision
                    print(f"MT5Broker ({self.agent_id}): Simulated closing entire position {pos['id']} (size {current_pos_size}).")
                    # Don't add to temp_positions to remove it
                else:
                    new_size = round(current_pos_size - effective_size_to_close, 2) # Standard lot sizes are 2 decimal places
                    if new_size >= 0.01:
                        pos["size"] = new_size
                        pos["comment"] = f"Partial close, remaining {pos['size']}"
                        print(f"MT5Broker ({self.agent_id}): Simulated partial close for position {pos['id']}. New size: {pos['size']}.")
                        temp_positions.append(pos)
                    else:
                        print(f"MT5Broker ({self.agent_id}): Position {pos['id']} fully closed due to small remaining size ({new_size}) after partial close.")
            else:
                temp_positions.append(pos)

        self.simulated_open_positions = temp_positions

        if position_found_and_acted_on:
            return {"success": True, "message": f"Order/Position {order_id_or_ticket} close action simulated.", "data_source": "simulated"}
        else:
            print(f"MT5Broker ({self.agent_id}): Position ID {order_id_or_ticket} not found in simulated open positions for closing.")
            return {"success": False, "message": f"Position ID {order_id_or_ticket} not found for simulated closing.", "data_source": "simulated_failed_not_found"}

    def close_order(self, order_id_or_ticket: str, size_to_close: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self._connected:
            print(f"MT5Broker ({self.agent_id}): Not connected for close_order. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="Not connected")
        if not self.mt5_available:
            print(f"MT5Broker ({self.agent_id}): MT5 library not available for close_order. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="MT5 library unavailable")

        print(f"MT5Broker ({self.agent_id}): Attempting to LIVE close order/position ID/Ticket: {order_id_or_ticket}, Size: {size_to_close}")

        try:
            ticket_to_close = int(order_id_or_ticket)
        except ValueError:
            print(f"MT5Broker ({self.agent_id}): Invalid order_id_or_ticket format: {order_id_or_ticket}. Must be convertible to int.")
            return {"success": False, "message": "Invalid ticket format for close_order.", "data_source": "input_error"}

        position_to_close = None
        try:
            positions = mt5.positions_get(ticket=ticket_to_close)
            if positions and len(positions) > 0:
                position_to_close = positions[0]
            else:
                print(f"MT5Broker ({self.agent_id}): Position ticket {ticket_to_close} not found among open positions.")
                return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="Live position not found by ticket")

        except Exception as e_pos_get:
            print(f"MT5Broker ({self.agent_id}): Exception fetching position for ticket {ticket_to_close}: {e_pos_get}. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason=f"Exception fetching position: {e_pos_get}")

        if not position_to_close:
             print(f"MT5Broker ({self.agent_id}): Position {ticket_to_close} could not be identified (safeguard). Simulating.")
             return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="Position not identified (safeguard)")

        symbol = position_to_close.symbol
        volume_to_close = float(round(size_to_close,8)) if size_to_close is not None and size_to_close > 0 else position_to_close.volume

        if volume_to_close > position_to_close.volume + 0.00000001: # Add tolerance for float precision
            msg = f"Cannot close {volume_to_close} lots; only {position_to_close.volume} available for position {ticket_to_close}."
            print(f"MT5Broker ({self.agent_id}): {msg}")
            return {"success": False, "message": msg, "data_source": "live_attempt_failed_insufficient_volume"}

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            msg = f"Could not get current price for {symbol} to close position {ticket_to_close}."
            print(f"MT5Broker ({self.agent_id}): {msg} Error: {mt5.last_error()}")
            return {"success": False, "message": msg, "data_source": "live_attempt_failed_no_price"}

        price = tick.bid if position_to_close.type == mt5.ORDER_TYPE_BUY else tick.ask

        close_request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol, "volume": volume_to_close,
            "type": mt5.ORDER_TYPE_SELL if position_to_close.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY,
            "position": position_to_close.ticket, "price": price, "deviation": 20,
            "magic": self.credentials.get("magic_number", 234000),
            "comment": f"Close pos {position_to_close.ticket} by {self.agent_id}",
            "type_time": mt5.ORDER_TIME_GTC, "type_filling": mt5.ORDER_FILLING_FOK,
        }

        try:
            print(f"MT5Broker ({self.agent_id}): Sending LIVE close request: {close_request}")
            result = mt5.order_send(close_request)

            if result is None:
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                print(f"MT5Broker ({self.agent_id}): order_send (for close) failed, returned None. Error: {error_code} - {error_message}")
                # Fallback to simulation if MT5 call itself fails critically
                return self._simulate_close_order(order_id_or_ticket, size_to_close, reason=f"Live close returned None: {error_message}")

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"MT5Broker ({self.agent_id}): LIVE Position {ticket_to_close} closed/partially closed successfully. Comment: {result.comment}, OrderID: {result.order}")
                return {"success": True, "message": f"Position {ticket_to_close} closed/partially closed successfully ({result.comment}).", "order_id": str(result.order), "deal_id": str(result.deal), "data_source": "live"}
            else:
                print(f"MT5Broker ({self.agent_id}): LIVE Position {ticket_to_close} close failed. Retcode: {result.retcode}, Comment: {result.comment}, Request: {result.request._asdict() if result.request else 'N/A'}")
                return {"success": False, "message": f"Position {ticket_to_close} close failed: {result.comment} (retcode: {result.retcode})", "retcode": result.retcode, "data_source": "live_attempt_failed"}

        except Exception as e:
            print(f"MT5Broker ({self.agent_id}): Exception during LIVE mt5.order_send (for close {ticket_to_close}): {e}. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason=f"Exception during live close: {e}")

    def get_open_positions(self) -> Optional[List[Dict[str, Any]]]:
        # Initial connectivity checks (already implicitly handled by self._connected check for live path)

        if self.mt5_available and self._connected:
            print(f"MT5Broker ({self.agent_id}): Attempting to fetch LIVE open positions...")
            try:
                positions = mt5.positions_get() # Can filter by symbol or ticket if needed, e.g., mt5.positions_get(symbol="EURUSD")
                if positions is None:
                    error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                    print(f"MT5Broker ({self.agent_id}): mt5.positions_get() returned None. Error: {error_code} - {error_message}. Falling back to simulated.")
                    # Fall through to simulated if live call returns None
                else:
                    live_positions = []
                    for position in positions:
                        pos_dict = position._asdict() # Convert named tuple to dict
                        pos_dict["data_source"] = "live"
                        # MT5 position times are usually int timestamps (seconds)
                        if 'time' in pos_dict and isinstance(pos_dict['time'], (int, float)):
                            pos_dict['time'] = datetime.fromtimestamp(pos_dict['time'], tz=timezone.utc)
                        if 'time_msc' in pos_dict and isinstance(pos_dict['time_msc'], (int, float)): # Milliseconds timestamp
                            pos_dict['time_msc'] = datetime.fromtimestamp(pos_dict['time_msc'] / 1000.0, tz=timezone.utc)
                        if 'time_update' in pos_dict and isinstance(pos_dict['time_update'], (int, float)):
                             pos_dict['time_update'] = datetime.fromtimestamp(pos_dict['time_update'], tz=timezone.utc)
                        if 'time_update_msc' in pos_dict and isinstance(pos_dict['time_update_msc'], (int, float)):
                             pos_dict['time_update_msc'] = datetime.fromtimestamp(pos_dict['time_update_msc'] / 1000.0, tz=timezone.utc)

                        if pos_dict.get('type') == mt5.ORDER_TYPE_BUY:
                            pos_dict['type_str'] = "buy"
                        elif pos_dict.get('type') == mt5.ORDER_TYPE_SELL:
                            pos_dict['type_str'] = "sell"
                        else:
                            pos_dict['type_str'] = "unknown"

                        live_positions.append(pos_dict)

                    print(f"MT5Broker ({self.agent_id}): Fetched {len(live_positions)} LIVE open position(s).")
                    return live_positions
            except Exception as e:
                print(f"MT5Broker ({self.agent_id}): Exception during LIVE mt5.positions_get(): {e}. Falling back to simulated.")
                # Fall through to simulated

        # Fallback to simulated data
        status_reason = ""
        if not self.mt5_available:
            status_reason = "(MT5 library not available)"
        elif not self._connected:
            status_reason = "(Not connected to MT5)"
        else: # mt5 available and connected, but live call failed or returned None
            status_reason = "(Live call failed or returned no data)"

        print(f"MT5Broker ({self.agent_id}): get_open_positions() - returning {len(self.simulated_open_positions)} SIMULATED open position(s). Reason: {status_reason}.")

        updated_simulated_positions = []
        for pos_data in self.simulated_open_positions:
            sim_pos_copy = pos_data.copy()
            sim_pos_copy["data_source"] = "simulated"
            sim_pos_copy["profit"] = round(sim_pos_copy.get("profit", 0.0) + np.random.uniform(-0.5, 0.5) * sim_pos_copy.get("size", 0.01) * 100, 2)
            updated_simulated_positions.append(sim_pos_copy)

        return updated_simulated_positions

    def get_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        if not self._connected:
            print(f"MT5Broker ({self.agent_id}): Not connected for get_pending_orders. Returning empty list (simulated).")
            return [] # No simulated pending orders for now
        if not self.mt5_available:
            print(f"MT5Broker ({self.agent_id}): MT5 library not available for get_pending_orders. Returning empty list (simulated).")
            return [] # No simulated pending orders

        print(f"MT5Broker ({self.agent_id}): Attempting to fetch LIVE pending orders...")
        try:
            orders = mt5.orders_get() # Can filter by symbol or group if needed
            if orders is None:
                # This typically means an error, not just "no orders"
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                print(f"MT5Broker ({self.agent_id}): mt5.orders_get() returned None. Error: {error_code} - {error_message}. Returning empty list.")
                return []

            live_pending_orders = []
            for order in orders:
                order_dict = order._asdict() # Convert named tuple to dict
                order_dict["data_source"] = "live"

                # Convert timestamps
                if 'time_setup' in order_dict and isinstance(order_dict['time_setup'], (int, float)):
                    order_dict['time_setup'] = datetime.fromtimestamp(order_dict['time_setup'], tz=timezone.utc)
                if 'time_setup_msc' in order_dict and isinstance(order_dict['time_setup_msc'], (int, float)):
                    order_dict['time_setup_msc'] = datetime.fromtimestamp(order_dict['time_setup_msc'] / 1000.0, tz=timezone.utc)
                if 'time_expiration' in order_dict and isinstance(order_dict['time_expiration'], (int, float)) and order_dict['time_expiration'] > 0:
                    order_dict['time_expiration'] = datetime.fromtimestamp(order_dict['time_expiration'], tz=timezone.utc)
                else:
                    order_dict['time_expiration'] = None # Or some indicator for no expiration

                # Add user-friendly type string
                # Ensure mt5 constants are available or use integer values if mt5 is DummyMT5
                _ORDER_TYPE_BUY_LIMIT = getattr(mt5, 'ORDER_TYPE_BUY_LIMIT', 2)
                _ORDER_TYPE_SELL_LIMIT = getattr(mt5, 'ORDER_TYPE_SELL_LIMIT', 3)
                _ORDER_TYPE_BUY_STOP = getattr(mt5, 'ORDER_TYPE_BUY_STOP', 4)
                _ORDER_TYPE_SELL_STOP = getattr(mt5, 'ORDER_TYPE_SELL_STOP', 5)
                _ORDER_TYPE_BUY_STOP_LIMIT = getattr(mt5, 'ORDER_TYPE_BUY_STOP_LIMIT', 6)
                _ORDER_TYPE_SELL_STOP_LIMIT = getattr(mt5, 'ORDER_TYPE_SELL_STOP_LIMIT', 7)

                if order_dict.get('type') == _ORDER_TYPE_BUY_LIMIT:
                    order_dict['type_str'] = "buy_limit"
                elif order_dict.get('type') == _ORDER_TYPE_SELL_LIMIT:
                    order_dict['type_str'] = "sell_limit"
                elif order_dict.get('type') == _ORDER_TYPE_BUY_STOP:
                    order_dict['type_str'] = "buy_stop"
                elif order_dict.get('type') == _ORDER_TYPE_SELL_STOP:
                    order_dict['type_str'] = "sell_stop"
                elif order_dict.get('type') == _ORDER_TYPE_BUY_STOP_LIMIT:
                    order_dict['type_str'] = "buy_stop_limit"
                elif order_dict.get('type') == _ORDER_TYPE_SELL_STOP_LIMIT:
                    order_dict['type_str'] = "sell_stop_limit"
                else:
                    order_dict['type_str'] = "unknown_pending"

                live_pending_orders.append(order_dict)

            print(f"MT5Broker ({self.agent_id}): Fetched {len(live_pending_orders)} LIVE pending order(s).")
            return live_pending_orders

        except Exception as e:
            print(f"MT5Broker ({self.agent_id}): Exception during LIVE mt5.orders_get(): {e}. Returning empty list (simulated).")
            return [] # Fallback to empty list for simulated path

if __name__ == "__main__":
    print("This script contains the MT5Broker class implementation.")
    print("To test this class, please refer to the instructions and test script")
    print("provided in 'MT5_TEST_GUIDE.md' located in the same directory.")
    # ... (rest of __main__ block remains) ...
