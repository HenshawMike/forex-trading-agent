from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
from .base import BrokerInterface
from .rate_limiter import RateLimiter
from tradingagents.forex_utils.forex_states import OrderType, OrderSide, TimeInForce, FillPolicy, OrderResponse, FillDetails # Added
import pandas as pd
import numpy as np
import uuid
import logging # Added

# Configure basic logging for the module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # Module-level logger

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
    logger.info("MetaTrader5 package found and imported.")
except ImportError:
    logger.info("MetaTrader5 package not found. MT5 functionality will be disabled and mocked.")
    MT5_AVAILABLE = False
    class DummyMT5: # Ensure logger is usable even if MT5 is dummy
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
        self.logger = logging.getLogger(f"{__name__}.{self.agent_id}") # Agent-specific logger
        if not self.mt5_available:
            self.logger.info(f"MetaTrader5 package not found at init. Live MT5 calls will be skipped; mock logic will be used.")
        else:
            self.logger.info(f"MT5Broker initialized. Not connected.")

    def connect(self, credentials: Dict[str, Any]) -> bool:
        if not self.mt5_available:
            self.logger.error("MetaTrader5 package not available. Cannot connect.")
            self._connected = False
            return False
        self.logger.info(f"Attempting to connect with login: {credentials.get('login')}")
        login_val = credentials.get('login')
        password = credentials.get('password')
        server = credentials.get('server')
        if not all([login_val, password, server]):
            self.logger.error("'login', 'password', and 'server' are required in credentials.")
            return False
        try: login_int = int(login_val)
        except ValueError: self.logger.error(f"Invalid login ID '{login_val}'. Must be an integer."); return False
        self.credentials = credentials.copy()
        path = self.credentials.get('path')
        try:
            if path: self.mt5_path = path; initialized = mt5.initialize(path=self.mt5_path, login=login_int, password=password, server=server)
            else: initialized = mt5.initialize(login=login_int, password=password, server=server)
            if not initialized:
                self.logger.error(f"initialize() failed, error code = {mt5.last_error()}")
                self._connected = False; self.credentials = {}; return False
            loggedIn = mt5.login(login=login_int, password=password, server=server)
            if not loggedIn:
                error_code = mt5.last_error()
                self.logger.error(f"login() failed, error code = {error_code}")
                mt5.shutdown(); self._connected = False; self.credentials = {}; return False
            self._connected = True; self.logger.info(f"Connected and logged in to account {login_int}.")
            return True
        except RuntimeError as re: # Specific catch for RuntimeError
            self.logger.critical(f"Critical RuntimeError during connection: {re}. This might be due to MT5 terminal issues or path problems.")
            self._connected = False; self.credentials = {}
            if hasattr(mt5, 'terminal_info') and mt5.terminal_info() and hasattr(mt5, 'shutdown'): mt5.shutdown() # Ensure shutdown if possible
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during connection: {e}")
            self._connected = False; self.credentials = {}
            if hasattr(mt5, 'terminal_info') and mt5.terminal_info() and hasattr(mt5, 'shutdown'): mt5.shutdown() # Ensure shutdown if possible
            return False

    def disconnect(self) -> None:
        self.logger.info("disconnect() called.")
        try:
            if self._connected and self.mt5_available and hasattr(mt5, 'shutdown'): mt5.shutdown(); self.logger.info("Disconnected from MetaTrader 5.")
            elif self._connected: self.logger.info("Conceptually connected, but MT5 lib not available for shutdown.")
            else: self.logger.info("Was not connected.")
        except Exception as e: self.logger.error(f"Error during disconnection: {e}")
        finally: self._connected = False; self.credentials = {}

    @RateLimiter(max_calls=2, period_seconds=1)
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self._connected: self.logger.warning("Not connected for get_account_info."); return None
        if self.mt5_available:
            self.logger.info("Attempting to fetch LIVE account info...")
            try:
                account_info_mt5 = mt5.account_info()
                if account_info_mt5 is not None:
                    live_info = account_info_mt5._asdict(); live_info["data_source"] = "live"
                    self.logger.info(f"Live account info: Login {live_info.get('login')}"); return live_info
                else:
                    err_code, err_msg = mt5.last_error()
                    self.logger.error(f"mt5.account_info() returned None. Error: {err_code} - {err_msg}");
            except Exception as e: self.logger.error(f"Exception in LIVE mt5.account_info(): {e}.")
        reason = "(MT5 N/A)" if not self.mt5_available else "(Not connected)" if not self._connected else "(Live call failed)"
        self.logger.info(f"get_account_info() - MOCK data {reason}.")
        bal = 10000.0 + np.random.uniform(-500,500); eq = bal - np.random.uniform(0,200); mu = eq*0.5
        return {"login": self.credentials.get('login',12345), "balance":round(bal,2), "equity":round(eq,2), "currency":"USD",
                "margin":round(mu,2), "margin_free":round(eq-mu,2), "margin_level":0.0 if mu==0 else round((eq/mu)*100,2),
                "server":self.credentials.get('server',"Default"), "name":self.credentials.get('name',"Mock"),
                "trade_mode":mt5.ACCOUNT_TRADE_MODE_DEMO if self.mt5_available and hasattr(mt5,'ACCOUNT_TRADE_MODE_DEMO') else 0, "data_source":"mock"}

    def _get_mock_current_price(self, pair: str, reason: str = "Fallback") -> Dict[str, Any]:
        self.logger.info(f"_get_mock_current_price() for {pair}. Reason: {reason}.")
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

    @RateLimiter(max_calls=10, period_seconds=1)
    def get_current_price(self, pair: str) -> Optional[Dict[str, Any]]:
        if not self._connected:
            self.logger.warning(f"Not connected. Using mock for get_current_price({pair}).")
            return self._get_mock_current_price(pair, reason="Not connected")
        if self.mt5_available:
            # self.logger.debug(f"Attempting to fetch LIVE current price for {pair}...")
            try:
                tick = mt5.symbol_info_tick(pair)
                if tick:
                    tick_time = datetime.fromtimestamp(tick.time, tz=timezone.utc) if hasattr(tick, 'time') and tick.time else datetime.now(timezone.utc)
                    return {"pair": pair, "bid": tick.bid, "ask": tick.ask, "time": tick_time, "data_source": "live"}
                else:
                    error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                    self.logger.warning(f"mt5.symbol_info_tick({pair}) returned None. Error: {error_code} - {error_message}")
            except Exception as e: self.logger.error(f"Exception in LIVE mt5.symbol_info_tick({pair}): {e}.")
        return self._get_mock_current_price(pair, reason="Fallback (MT5 unavailable or live call failed)")

    # ... (other methods like get_current_price remain) ...

    def _get_mock_historical_data(self, pair: str, timeframe: str, count: int) -> List[Dict[str, Any]]:
        self.logger.info(f"_get_mock_historical_data() for {pair}, TF={timeframe}, Count={count}")
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

    @RateLimiter(max_calls=2, period_seconds=1)
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
            self.logger.warning(f"Not connected for get_historical_data({pair}).")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

        if not self.mt5_available:
            self.logger.warning(f"MT5 library not available for get_historical_data({pair}).")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

        self.logger.info(f"Attempting to fetch LIVE historical data for {pair}, TF={timeframe}, Count={count}, Start={start_date}, End={end_date}...")

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
            self.logger.warning(f"Invalid timeframe string '{timeframe}'. Falling back to mock.")
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
                self.logger.info(f"Insufficient parameters for live get_historical_data (need range or count). Defaulting to last {effective_count} bars.")
                rates = mt5.copy_rates_from_pos(pair, mt5_timeframe, 0, effective_count)


            if rates is None or len(rates) == 0:
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error or no data")
                self.logger.warning(f"No data returned from MT5 for {pair}, TF={timeframe}. Error: {error_code} - {error_message}. Falling back to mock.")
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
            self.logger.info(f"Live historical data fetched for {pair}, {len(formatted_data)} bars.")
            return formatted_data

        except Exception as e:
            self.logger.error(f"Exception during LIVE get_historical_data for {pair}, TF={timeframe}: {e}. Falling back to mock.")
            return self._get_mock_historical_data(pair, timeframe, effective_count)

    def _simulate_place_order(self,
                              symbol: str,
                              order_type: OrderType,
                              side: OrderSide,
                              volume: float,
                              price: Optional[float] = None,
                              stop_loss: Optional[float] = None,
                              take_profit: Optional[float] = None,
                              time_in_force: Optional[TimeInForce] = TimeInForce.GTC,
                              fill_policy: Optional[FillPolicy] = FillPolicy.FOK,
                              magic_number: Optional[int] = 0,
                              comment: Optional[str] = "",
                              client_order_id: Optional[str] = None,
                              fail_reason: Optional[str] = None) -> OrderResponse:

        reason_prefix = f"Simulated order ({fail_reason if fail_reason else 'MT5 unavailable/disconnected'})."
        self.logger.info(f"{reason_prefix} Symbol: {symbol}, Type: {order_type}, Side: {side}, Vol: {volume}")

        simulated_order_id = f"sim_ord_{str(uuid.uuid4())[:8]}"
        now_ts = datetime.now(timezone.utc).timestamp()

        sim_status = "FILLED"
        sim_filled_volume = volume
        sim_avg_fill_price = price
        sim_fills: List[FillDetails] = []

        if order_type == OrderType.MARKET:
            # Simulate market order execution
            mock_open_price_default = 1.0825  # A generic price
            if "JPY" in symbol.upper(): mock_open_price_default = 150.25

            # Use SL as a hint for more realistic mock price if provided, otherwise use default
            if stop_loss is not None:
                price_offset = 0.50 if "JPY" in symbol.upper() else 0.0050
                if side == OrderSide.BUY:
                    sim_avg_fill_price = stop_loss + price_offset
                else: # SELL
                    sim_avg_fill_price = stop_loss - price_offset
            elif price is not None : # Use provided price if SL not set (e.g. for testing)
                 sim_avg_fill_price = price
            else: # Fallback
                sim_avg_fill_price = mock_open_price_default

            sim_avg_fill_price = round(sim_avg_fill_price, 5 if "JPY" not in symbol.upper() else 3)

            sim_fills.append(FillDetails(
                fill_id=f"sim_fill_{str(uuid.uuid4())[:8]}",
                fill_price=sim_avg_fill_price,
                fill_volume=volume,
                fill_timestamp=now_ts,
                commission=0.01 * volume, # mock commission
                fee=0.0
            ))

            # Add to simulated_open_positions for market orders
            position_id = f"sim_pos_{str(uuid.uuid4())[:8]}"
            new_position = {
                "id": position_id, "order_id_ref": simulated_order_id,
                "pair": symbol,
                "type": mt5.ORDER_TYPE_BUY if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL,
                "size": volume,
                "open_price": sim_avg_fill_price,
                "sl": stop_loss, "tp": take_profit,
                "profit": -volume * 2.0, # Simulate spread cost
                "comment": comment if comment else f"SimPos_{self.agent_id}",
                "open_time": datetime.fromtimestamp(now_ts, tz=timezone.utc),
                "data_source": "simulated"
            }
            self.simulated_open_positions.append(new_position)
            self.logger.info(f"Added to simulated_open_positions: {position_id} for pair {symbol}")

        elif order_type in [OrderType.LIMIT, OrderType.STOP]:
            sim_status = "PENDING"
            sim_filled_volume = 0.0
            sim_avg_fill_price = None # Not filled yet
        else: # Should not happen with Enum
            self.logger.error(f"Unsupported order type {order_type} in _simulate_place_order")
            return OrderResponse(
                order_id=simulated_order_id, client_order_id=client_order_id, status="ERROR", symbol=symbol,
                order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0,
                average_fill_price=None, requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit,
                time_in_force=time_in_force or TimeInForce.GTC, fill_policy=fill_policy or FillPolicy.FOK,
                creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                error_message=f"Unsupported order type for simulation: {order_type}",
                broker_native_response={"simulated_reason": fail_reason or "Unsupported order type"},
                position_id=None
            )

        return OrderResponse(
            order_id=simulated_order_id,
            client_order_id=client_order_id,
            status=sim_status,
            symbol=symbol,
            order_type=order_type,
            side=side,
            requested_volume=volume,
            filled_volume=sim_filled_volume,
            average_fill_price=sim_avg_fill_price,
            requested_price=price, # Original price for limit/stop
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            time_in_force=time_in_force or TimeInForce.GTC,
            fill_policy=fill_policy or FillPolicy.FOK,
            creation_timestamp=now_ts,
            last_update_timestamp=now_ts,
            fills=sim_fills,
            error_message=fail_reason,
            broker_native_response={"simulated_reason": fail_reason or "Simulated success"},
            position_id=new_position["id"] if order_type == OrderType.MARKET and 'new_position' in locals() else None
        )

    @RateLimiter(max_calls=5, period_seconds=1)
    def place_order(self,
                      symbol: str,
                      order_type: OrderType,
                      side: OrderSide,
                      volume: float,
                      price: Optional[float] = None,
                      stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None,
                      time_in_force: Optional[TimeInForce] = TimeInForce.GTC,
                      fill_policy: Optional[FillPolicy] = FillPolicy.FOK,
                      magic_number: Optional[int] = 0,
                      comment: Optional[str] = "",
                      client_order_id: Optional[str] = None
                     ) -> OrderResponse:

        now_ts = datetime.now(timezone.utc).timestamp()

        if not self._connected:
            self.logger.warning(f"Not connected for place_order. Simulating.")
            return self._simulate_place_order(symbol, order_type, side, volume, price, stop_loss, take_profit,
                                              time_in_force, fill_policy, magic_number, comment, client_order_id,
                                              fail_reason="Not connected")
        if not self.mt5_available:
            self.logger.warning(f"MT5 library not available for place_order. Simulating.")
            return self._simulate_place_order(symbol, order_type, side, volume, price, stop_loss, take_profit,
                                              time_in_force, fill_policy, magic_number, comment, client_order_id,
                                              fail_reason="MT5 library N/A")

        self.logger.info(f"Attempting to place LIVE order: Symbol:{symbol} Type:{order_type} Side:{side} Vol:{volume} Price:{price} SL:{stop_loss} TP:{take_profit} TIF:{time_in_force} FillPol:{fill_policy}")

        # --- Enum to MT5 Constant Mapping ---
        mt5_order_type_val = None
        if order_type == OrderType.MARKET:
            mt5_order_type_val = mt5.ORDER_TYPE_BUY if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL
        elif order_type == OrderType.LIMIT:
            mt5_order_type_val = mt5.ORDER_TYPE_BUY_LIMIT if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_LIMIT
        elif order_type == OrderType.STOP:
            mt5_order_type_val = mt5.ORDER_TYPE_BUY_STOP if side == OrderSide.BUY else mt5.ORDER_TYPE_SELL_STOP
        else:
            self.logger.error(f"Unsupported OrderType: {order_type}")
            return OrderResponse(
                order_id=f"err_{uuid.uuid4()}", client_order_id=client_order_id, status="ERROR", symbol=symbol,
                order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0, average_fill_price=None,
                requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
                fill_policy=fill_policy, creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                error_message=f"Unsupported OrderType: {order_type}", broker_native_response=None, position_id=None
            )

        mt5_time_in_force_val = mt5.ORDER_TIME_GTC # Default for MT5
        if time_in_force == TimeInForce.IOC:
            mt5_time_in_force_val = mt5.ORDER_TIME_IOC
        elif time_in_force == TimeInForce.FOK:
             # Note: FOK in TIF enum maps to Fill Policy in MT5 for some order types.
             # MT5 uses ORDER_TIME_GTC for most spot FX orders, and fill policy is separate.
             # If TIF.FOK is passed, it implies fill_policy should also be FOK.
             # We will primarily use the fill_policy parameter for this.
            mt5_time_in_force_val = mt5.ORDER_TIME_GTC # Keep GTC, FOK is a fill type
        elif time_in_force == TimeInForce.DAY:
            mt5_time_in_force_val = mt5.ORDER_TIME_DAY
        # GTC is default

        mt5_fill_policy_val = mt5.ORDER_FILLING_FOK # Default
        if fill_policy == FillPolicy.FOK:
            mt5_fill_policy_val = mt5.ORDER_FILLING_FOK
        elif fill_policy == FillPolicy.IOC:
            mt5_fill_policy_val = mt5.ORDER_FILLING_IOC
        elif fill_policy == FillPolicy.NORMAL: # Map 'NORMAL' to FOK as a sensible default for MT5
            mt5_fill_policy_val = mt5.ORDER_FILLING_FOK
            self.logger.info(f"FillPolicy.NORMAL mapped to mt5.ORDER_FILLING_FOK for order on {symbol}")
        elif fill_policy == FillPolicy.RETURN:
            # MT5's ORDER_FILLING_RETURN is for exchange execution mode, not typically for retail spot FX.
            # Defaulting to FOK and logging a warning.
            mt5_fill_policy_val = mt5.ORDER_FILLING_FOK
            self.logger.warning(f"FillPolicy.RETURN is not directly supported for this MT5 order type, defaulting to FOK for {symbol}.")

        # --- Symbol Info and Price ---
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                self.logger.warning(f"Symbol {symbol} not found by MT5. Attempting to select.")
                if not mt5.symbol_select(symbol, True):
                    err_code, err_msg = mt5.last_error()
                    self.logger.error(f"Failed to select symbol {symbol} in MarketWatch. Error: {err_code} - {err_msg}")
                    return OrderResponse(
                        order_id=f"err_{uuid.uuid4()}", client_order_id=client_order_id, status="REJECTED", symbol=symbol,
                        order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0, average_fill_price=None,
                        requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
                        fill_policy=fill_policy, creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                        error_message=f"Failed to select symbol {symbol}: {err_msg} (Code: {err_code})", broker_native_response=None, position_id=None
                    )
                mt5.sleep(100)
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                     err_code, err_msg = mt5.last_error()
                     self.logger.error(f"Symbol {symbol} still not found after select. Error: {err_code} - {err_msg}")
                     return OrderResponse(
                        order_id=f"err_{uuid.uuid4()}", client_order_id=client_order_id, status="REJECTED", symbol=symbol,
                        order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0, average_fill_price=None,
                        requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
                        fill_policy=fill_policy, creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                        error_message=f"Symbol {symbol} not found after select: {err_msg} (Code: {err_code})", broker_native_response=None, position_id=None
                    )
        except Exception as e_sym:
            self.logger.error(f"Exception getting symbol info for {symbol}: {e_sym}")
            return OrderResponse(
                order_id=f"err_{uuid.uuid4()}", client_order_id=client_order_id, status="ERROR", symbol=symbol,
                order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0, average_fill_price=None,
                requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
                fill_policy=fill_policy, creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                error_message=f"Exception getting symbol info: {e_sym}", broker_native_response=None, position_id=None
            )

        request_price_mt5 = 0.0
        if order_type == OrderType.MARKET:
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                err_code, err_msg = mt5.last_error()
                self.logger.error(f"Could not get tick for {symbol} for market order. Error: {err_code} - {err_msg}")
                return OrderResponse(
                    order_id=f"err_{uuid.uuid4()}", client_order_id=client_order_id, status="REJECTED", symbol=symbol,
                    order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0, average_fill_price=None,
                    requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
                    fill_policy=fill_policy, creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                    error_message=f"Could not get tick for {symbol}: {err_msg} (Code: {err_code})", broker_native_response=None, position_id=None
                )
            request_price_mt5 = tick.ask if side == OrderSide.BUY else tick.bid
        elif price is not None : # For Limit/Stop orders
             request_price_mt5 = price
        else: # Price must be set for pending orders
            self.logger.error(f"Price must be set for non-market order type {order_type}")
            return OrderResponse(
                order_id=f"err_{uuid.uuid4()}", client_order_id=client_order_id, status="REJECTED", symbol=symbol,
                order_type=order_type, side=side, requested_volume=volume, filled_volume=0.0, average_fill_price=None,
                requested_price=price, stop_loss_price=stop_loss, take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
                fill_policy=fill_policy, creation_timestamp=now_ts, last_update_timestamp=now_ts, fills=[],
                error_message="Price must be set for pending orders.", broker_native_response=None, position_id=None
            )

        request = {
            "action": mt5.TRADE_ACTION_DEAL if order_type == OrderType.MARKET else mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": volume,
            "type": mt5_order_type_val,
            "price": request_price_mt5,
            "sl": stop_loss if stop_loss is not None else 0.0,
            "tp": take_profit if take_profit is not None else 0.0,
            "deviation": 20, # Standard deviation for market orders
            "magic": magic_number if magic_number is not None else 0,
            "comment": comment if comment is not None else self.agent_id,
            "type_time": mt5_time_in_force_val,
            "type_filling": mt5_fill_policy_val,
        }

        try:
            self.logger.info(f"Sending LIVE order request: {request}")
            result = mt5.order_send(request)

            broker_native_resp_dict = result._asdict() if result and hasattr(result, '_asdict') else None

            if result is None:
                err_code, err_msg = mt5.last_error()
                self.logger.error(f"order_send failed, returned None. Error: {err_code} - {err_msg}")
                # Fallback to simulation on critical failure, though this indicates a deeper issue
                return self._simulate_place_order(symbol, order_type, side, volume, price, stop_loss, take_profit,
                                              time_in_force, fill_policy, magic_number, comment, client_order_id,
                                              fail_reason=f"Order send None result: {err_msg} (Code: {err_code})")

            order_status_str = "ERROR"
            filled_vol = 0.0
            avg_fill_price = None
            fills_list: List[FillDetails] = []
            pos_id = None
            error_msg = result.comment

            if result.retcode == mt5.TRADE_RETCODE_DONE: # Executed
                order_status_str = "FILLED"
                filled_vol = result.volume
                avg_fill_price = result.price
                fills_list.append(FillDetails(
                    fill_id=str(result.deal) if result.deal else None,
                    fill_price=result.price,
                    fill_volume=result.volume,
                    fill_timestamp=datetime.now(timezone.utc).timestamp(), # Approx, MT5 deal time not in direct result
                    commission=result.commission if hasattr(result, 'commission') else None,
                    fee=None # MT5 result doesn't usually have separate 'fee' field like this
                ))
                # Position ID logic: if a new position is typically identified by the order ticket that opened it
                # This might need adjustment based on how MT5 handles position IDs vs order/deal tickets.
                # For simplicity, if it's a new market order that got filled, the order ticket might be used as reference.
                if order_type == OrderType.MARKET: # Assuming market orders create/affect positions directly
                    # Querying positions right after may be needed for accurate pos_id
                    pos_id = str(result.order)


            elif result.retcode == mt5.TRADE_RETCODE_PLACED: # Pending order accepted
                order_status_str = "PENDING"
                error_msg = None # Not an error, order is placed
            elif result.retcode in [mt5.TRADE_RETCODE_REJECT, mt5.TRADE_RETCODE_ERROR, mt5.TRADE_RETCODE_TIMEOUT, mt5.TRADE_RETCODE_INVALID, mt5.TRADE_RETCODE_INVALID_VOLUME, mt5.TRADE_RETCODE_INVALID_PRICE, mt5.TRADE_RETCODE_INVALID_STOPS, mt5.TRADE_RETCODE_NO_MONEY]:
                order_status_str = "REJECTED"
                self.logger.error(f"LIVE Order REJECTED. Retcode: {result.retcode}, Comment: {result.comment}, Full Result: {broker_native_resp_dict}")
            else: # Other non-success codes
                order_status_str = "ERROR" # Generic error for other codes
                self.logger.error(f"LIVE Order failed with unhandled Retcode: {result.retcode}, Comment: {result.comment}, Full Result: {broker_native_resp_dict}")


            return OrderResponse(
                order_id=str(result.order),
                client_order_id=client_order_id,
                status=order_status_str,
                symbol=symbol,
                order_type=order_type,
                side=side,
                requested_volume=volume,
                filled_volume=filled_vol,
                average_fill_price=avg_fill_price,
                requested_price=price, # Original requested price for limit/stop
                stop_loss_price=stop_loss,
                take_profit_price=take_profit,
                time_in_force=time_in_force or TimeInForce.GTC,
                fill_policy=fill_policy or FillPolicy.FOK,
                creation_timestamp=now_ts, # Request creation time
                last_update_timestamp=datetime.now(timezone.utc).timestamp(), # Response processing time
                fills=fills_list,
                error_message=error_msg,
                broker_native_response=broker_native_resp_dict,
                position_id=pos_id
            )

        except Exception as e:
            self.logger.error(f"Exception during LIVE mt5.order_send(): {e}. Simulating with error.")
            return self._simulate_place_order(symbol, order_type, side, volume, price, stop_loss, take_profit,
                                              time_in_force, fill_policy, magic_number, comment, client_order_id,
                                              fail_reason=f"Exception: {str(e)}")


    def _simulate_modify_order(self, order_id: str, new_params: Dict[str, Any], reason: Optional[str] = None) -> Dict[str, Any]:
        reason_prefix = f"Simulated modify ({reason if reason else 'MT5 unavailable/disconnected'})."
        self.logger.info(f"{reason_prefix} Order/Pos ID: {order_id}, Params: {new_params}")

        found_position = False
        # Attempt to modify in simulated_open_positions (covers market orders that became positions)
        for pos in self.simulated_open_positions:
            if pos.get("id") == order_id or pos.get("order_id_ref") == order_id:
                if "sl" in new_params and new_params["sl"] is not None:
                    pos["sl"] = float(new_params["sl"])
                    self.logger.info(f"Simulated SL update for position {order_id} to {new_params['sl']}")
                if "tp" in new_params and new_params["tp"] is not None: # type: ignore
                    pos["tp"] = float(new_params["tp"]) # type: ignore
                    self.logger.info(f"Simulated TP update for position {order_id} to {new_params['tp']}") # type: ignore
                # Price modification for open positions is not typical via 'modify_order' (usually SL/TP)
                # If 'price' is in new_params, it might imply a pending order, which we are not separately tracking in simulation yet.
                if "price" in new_params and new_params["price"] is not None: # type: ignore
                     self.logger.info(f"Simulated price modification for {order_id} to {new_params['price']} (Note: Typically for pending orders).") # type: ignore
                found_position = True
                break

        # In a more complex simulation, we might have a self.simulated_pending_orders list
        # and check/modify it here if 'price' in new_params indicates a pending order mod.

        if found_position:
            return {"success": True, "message": f"Order/Position {order_id} modification simulated successfully.", "data_source": "simulated"}
        else:
            self.logger.warning(f"Order/Position ID {order_id} not found in simulated open positions for modification.")
            return {"success": False, "message": f"Order/Position ID {order_id} not found for simulated modification.", "data_source": "simulated_failed_not_found"}

    @RateLimiter(max_calls=5, period_seconds=1)
    def modify_order(self, order_id: str, new_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._connected:
            self.logger.warning(f"Not connected for modify_order. Simulating.")
            return self._simulate_modify_order(order_id, new_params, reason="Not connected")
        if not self.mt5_available:
            self.logger.warning(f"MT5 library not available for modify_order. Simulating.")
            return self._simulate_modify_order(order_id, new_params, reason="MT5 library unavailable")

        self.logger.info(f"Attempting to LIVE modify order/position ID: {order_id} with params: {new_params}")

        request = {}
        try:
            ticket_to_modify = int(order_id)
        except ValueError:
            self.logger.error(f"Invalid order_id format '{order_id}'. Must be an integer string.")
            return {"success": False, "message": f"Invalid order_id format '{order_id}'.", "data_source": "input_error"}


        # Try to determine if it's a position or a pending order
        # First, check if it's an open position
        target_symbol = None
        is_position_modification = False
        position_info_list = mt5.positions_get(ticket=ticket_to_modify)

        if position_info_list and len(position_info_list) > 0:
            is_position_modification = True
            target_symbol = position_info_list[0].symbol
            self.logger.info(f"Modifying open position {ticket_to_modify} for symbol {target_symbol}.")
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
                self.logger.info(f"Modifying pending order {ticket_to_modify} for symbol {target_symbol}.")
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
                self.logger.warning(f"Order/Position {ticket_to_modify} not found.")
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
             self.logger.info(f"No new SL, TP, or Price provided in new_params for modification of {order_id}.")
             return {"success": False, "message": "No new SL, TP, or Price provided for modification.", "data_source": "input_error"}
        elif no_change and ("sl" not in request and "tp" not in request and "price" not in request): # Check request after filling from existing
             self.logger.info(f"No actual change in SL, TP, or Price for modification of {order_id}.")
             # This could be debatable. If user provides same SL/TP, is it success or failure? MT5 might return success.
             # For now, let's consider it a case where no modification is sent if values are identical to current.
             return {"success": True, "message": "No actual change in SL, TP, or Price values; modification not sent.", "data_source": "no_change_needed"}


        try:
            self.logger.info(f"Sending LIVE modify request: {request}")
            result = mt5.order_send(request)

            if result is None:
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                self.logger.error(f"order_send (for modify) failed, returned None. Error: {error_code} - {error_message}")
                # Consider simulating if result is None, as it implies a connection/terminal issue
                return self._simulate_modify_order(order_id, new_params, reason=f"Live modify returned None: {error_message}")

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"LIVE Order/Position {order_id} modified successfully. Comment: {result.comment}")
                return {"success": True, "message": f"Order/Position {order_id} modified successfully ({result.comment}).", "data_source": "live"}
            else:
                # Log full result object on failure
                self.logger.error(f"LIVE Order/Position {order_id} modify failed. Retcode: {result.retcode}, Comment: {result.comment}, Full Result: {result._asdict() if hasattr(result, '_asdict') else result}")
                return {"success": False, "message": f"Order/Position {order_id} modify failed: {result.comment} (retcode: {result.retcode})", "retcode": result.retcode, "data_source": "live_attempt_failed"}

        except Exception as e:
            self.logger.error(f"Exception during LIVE mt5.order_send (for modify {order_id}): {e}. Simulating.")
            return self._simulate_modify_order(order_id, new_params, reason=f"Exception during live modify: {e}")

    def _simulate_close_order(self, order_id_or_ticket: str, size_to_close: Optional[float] = None, reason: Optional[str] = None) -> Dict[str, Any]:
        reason_prefix = f"Simulated close ({reason if reason else 'MT5 unavailable/disconnected'})."
        self.logger.info(f"{reason_prefix} Order/Pos ID: {order_id_or_ticket}, Size: {size_to_close}")

        position_found_and_acted_on = False
        temp_positions = []
        for pos in self.simulated_open_positions:
            # Assuming order_id_or_ticket for mock is the 'id' field we assigned or 'order_id_ref'
            if str(pos.get("id")) == str(order_id_or_ticket) or str(pos.get("order_id_ref")) == str(order_id_or_ticket):
                position_found_and_acted_on = True
                current_pos_size = float(pos.get("size", 0.01))
                effective_size_to_close = size_to_close if size_to_close is not None and size_to_close > 0 else current_pos_size

                if effective_size_to_close >= current_pos_size - 0.00001: # Account for float precision
                    self.logger.info(f"Simulated closing entire position {pos['id']} (size {current_pos_size}).")
                    # Don't add to temp_positions to remove it
                else:
                    new_size = round(current_pos_size - effective_size_to_close, 2) # Standard lot sizes are 2 decimal places
                    if new_size >= 0.01:
                        pos["size"] = new_size
                        pos["comment"] = f"Partial close, remaining {pos['size']}"
                        self.logger.info(f"Simulated partial close for position {pos['id']}. New size: {pos['size']}.")
                        temp_positions.append(pos)
                    else:
                        self.logger.info(f"Position {pos['id']} fully closed due to small remaining size ({new_size}) after partial close.")
            else:
                temp_positions.append(pos)

        self.simulated_open_positions = temp_positions

        if position_found_and_acted_on:
            return {"success": True, "message": f"Order/Position {order_id_or_ticket} close action simulated.", "data_source": "simulated"}
        else:
            self.logger.warning(f"Position ID {order_id_or_ticket} not found in simulated open positions for closing.")
            return {"success": False, "message": f"Position ID {order_id_or_ticket} not found for simulated closing.", "data_source": "simulated_failed_not_found"}

    @RateLimiter(max_calls=5, period_seconds=1)
    def close_order(self, order_id_or_ticket: str, size_to_close: Optional[float] = None) -> Optional[Dict[str, Any]]:
        if not self._connected:
            self.logger.warning(f"Not connected for close_order. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="Not connected")
        if not self.mt5_available:
            self.logger.warning(f"MT5 library not available for close_order. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="MT5 library unavailable")

        self.logger.info(f"Attempting to LIVE close order/position ID/Ticket: {order_id_or_ticket}, Size: {size_to_close}")

        try:
            ticket_to_close = int(order_id_or_ticket)
        except ValueError:
            self.logger.error(f"Invalid order_id_or_ticket format: {order_id_or_ticket}. Must be convertible to int.")
            return {"success": False, "message": "Invalid ticket format for close_order.", "data_source": "input_error"}

        position_to_close = None
        try:
            positions = mt5.positions_get(ticket=ticket_to_close)
            if positions and len(positions) > 0:
                position_to_close = positions[0]
            else:
                self.logger.warning(f"Position ticket {ticket_to_close} not found among open positions. Error: {mt5.last_error()}")
                return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="Live position not found by ticket")

        except Exception as e_pos_get:
            self.logger.error(f"Exception fetching position for ticket {ticket_to_close}: {e_pos_get}. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason=f"Exception fetching position: {e_pos_get}")

        if not position_to_close:
             self.logger.warning(f"Position {ticket_to_close} could not be identified (safeguard). Simulating.")
             return self._simulate_close_order(order_id_or_ticket, size_to_close, reason="Position not identified (safeguard)")

        symbol = position_to_close.symbol
        volume_to_close = float(round(size_to_close,8)) if size_to_close is not None and size_to_close > 0 else position_to_close.volume

        if volume_to_close > position_to_close.volume + 0.00000001: # Add tolerance for float precision
            msg = f"Cannot close {volume_to_close} lots; only {position_to_close.volume} available for position {ticket_to_close}."
            self.logger.error(msg)
            return {"success": False, "message": msg, "data_source": "live_attempt_failed_insufficient_volume"}

        tick = mt5.symbol_info_tick(symbol)
        if not tick:
            err_code, err_msg = mt5.last_error()
            msg = f"Could not get current price for {symbol} to close position {ticket_to_close}. Error: {err_code} - {err_msg}"
            self.logger.error(msg)
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
            self.logger.info(f"Sending LIVE close request: {close_request}")
            result = mt5.order_send(close_request)

            if result is None:
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                self.logger.error(f"order_send (for close) failed, returned None. Error: {error_code} - {error_message}")
                # Fallback to simulation if MT5 call itself fails critically
                return self._simulate_close_order(order_id_or_ticket, size_to_close, reason=f"Live close returned None: {error_message}")

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"LIVE Position {ticket_to_close} closed/partially closed successfully. Comment: {result.comment}, OrderID: {result.order}")
                return {"success": True, "message": f"Position {ticket_to_close} closed/partially closed successfully ({result.comment}).", "order_id": str(result.order), "deal_id": str(result.deal), "data_source": "live"}
            else:
                # Log full result object on failure
                self.logger.error(f"LIVE Position {ticket_to_close} close failed. Retcode: {result.retcode}, Comment: {result.comment}, Full Result: {result._asdict() if hasattr(result, '_asdict') else result}")
                return {"success": False, "message": f"Position {ticket_to_close} close failed: {result.comment} (retcode: {result.retcode})", "retcode": result.retcode, "data_source": "live_attempt_failed"}

        except Exception as e:
            self.logger.error(f"Exception during LIVE mt5.order_send (for close {ticket_to_close}): {e}. Simulating.")
            return self._simulate_close_order(order_id_or_ticket, size_to_close, reason=f"Exception during live close: {e}")

    @RateLimiter(max_calls=2, period_seconds=1)
    def get_open_positions(self) -> Optional[List[Dict[str, Any]]]:
        # Initial connectivity checks (already implicitly handled by self._connected check for live path)

        if self.mt5_available and self._connected:
            self.logger.info(f"Attempting to fetch LIVE open positions...")
            try:
                positions = mt5.positions_get() # Can filter by symbol or ticket if needed, e.g., mt5.positions_get(symbol="EURUSD")
                if positions is None:
                    error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                    self.logger.warning(f"mt5.positions_get() returned None. Error: {error_code} - {error_message}. Falling back to simulated.")
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

                    self.logger.info(f"Fetched {len(live_positions)} LIVE open position(s).")
                    return live_positions
            except Exception as e:
                self.logger.error(f"Exception during LIVE mt5.positions_get(): {e}. Falling back to simulated.")
                # Fall through to simulated

        # Fallback to simulated data
        status_reason = ""
        if not self.mt5_available:
            status_reason = "(MT5 library not available)"
        elif not self._connected:
            status_reason = "(Not connected to MT5)"
        else: # mt5 available and connected, but live call failed or returned None
            status_reason = "(Live call failed or returned no data)"

        self.logger.info(f"get_open_positions() - returning {len(self.simulated_open_positions)} SIMULATED open position(s). Reason: {status_reason}.")

        updated_simulated_positions = []
        for pos_data in self.simulated_open_positions:
            sim_pos_copy = pos_data.copy()
            sim_pos_copy["data_source"] = "simulated"
            sim_pos_copy["profit"] = round(sim_pos_copy.get("profit", 0.0) + np.random.uniform(-0.5, 0.5) * sim_pos_copy.get("size", 0.01) * 100, 2)
            updated_simulated_positions.append(sim_pos_copy)

        return updated_simulated_positions

    @RateLimiter(max_calls=2, period_seconds=1)
    def get_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        if not self._connected:
            self.logger.warning(f"Not connected for get_pending_orders. Returning empty list (simulated).")
            return [] # No simulated pending orders for now
        if not self.mt5_available:
            self.logger.warning(f"MT5 library not available for get_pending_orders. Returning empty list (simulated).")
            return [] # No simulated pending orders

        self.logger.info(f"Attempting to fetch LIVE pending orders...")
        try:
            orders = mt5.orders_get() # Can filter by symbol or group if needed
            if orders is None:
                # This typically means an error, not just "no orders"
                error_code, error_message = mt5.last_error() if hasattr(mt5, 'last_error') else (-1, "Unknown MT5 error")
                self.logger.warning(f"mt5.orders_get() returned None. Error: {error_code} - {error_message}. Returning empty list.")
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

            self.logger.info(f"Fetched {len(live_pending_orders)} LIVE pending order(s).")
            return live_pending_orders

        except Exception as e:
            self.logger.error(f"Exception during LIVE mt5.orders_get(): {e}. Returning empty list (simulated).")
            return [] # Fallback to empty list for simulated path

if __name__ == "__main__":
    # Basic configuration for when the script is run directly (e.g., for simple tests outside a larger app)
    # This will also be effective if no other logging config is set by an importing module.
    if not logging.getLogger().hasHandlers(): # Avoid adding handlers multiple times if already configured
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("This script contains the MT5Broker class implementation.")
    logger.info("To test this class, please refer to the instructions and test script")
    logger.info("provided in 'MT5_TEST_GUIDE.md' located in the same directory.")
    # ... (rest of __main__ block remains) ...
