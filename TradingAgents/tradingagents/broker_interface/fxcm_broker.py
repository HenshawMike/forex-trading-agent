import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Union
import random # For mock data
import uuid # For mock data

try:
    import fxcmpy
    FXCMPY_AVAILABLE = True
except ImportError:
    FXCMPY_AVAILABLE = False
    # Define a dummy class if fxcmpy is not available for type hinting and structure
    class fxcmpy:
        def __init__(self, *args, **kwargs): pass
        def is_connected(self): return False
        def close(self): pass
        # Add other methods that might be called if needed for parsing structure
        def get_summary(self): return {}
        def get_prices(self, symbol): return None
        def get_candles(self, symbol, period, number, start, end): return []
        def open_trade(self, symbol, is_buy, amount, time_in_force, order_type, limit, stop, trailing_step): return None
        def change_trade_stop_limit(self, trade_id, is_stop, rate): return None
        def close_trade(self, trade_id, amount): return None
        def get_open_positions(self, kind='list'): return []
        def get_orders(self, kind='list'): return []


from tradingagents.broker_interface.base import BrokerInterface
from tradingagents.forex_utils.forex_states import (
    OrderType, OrderSide, TimeInForce, FillPolicy,
    OrderResponse, FillDetails, Position, AccountInfo, PriceTick, Candlestick
)
from tradingagents.broker_interface.rate_limiter import RateLimiter


class FXCMBroker(BrokerInterface):
    def __init__(self, agent_id: Optional[str] = "FXCMBrokerInstance"):
        self.agent_id = agent_id
        self.logger = logging.getLogger(f"{__name__}.{self.agent_id}")
        self._connected: bool = False
        self.api: Optional[fxcmpy.fxcmpy] = None
        self.fxcmpy_available: bool = FXCMPY_AVAILABLE

        if not self.fxcmpy_available:
            self.logger.warning("fxcmpy package not found. FXCM live functionality will be disabled.")
        self.logger.info("FXCMBroker initialized.")

    def connect(self, credentials: Dict[str, Any]) -> bool:
        if not self.fxcmpy_available:
            self.logger.error("Cannot connect: fxcmpy package is not available.")
            return False

        api_key = credentials.get("api_key")
        server_env = credentials.get("server", "demo") # 'demo' or 'real'
        config_file = credentials.get("config_file") # Optional path to fxcm.cfg

        if not api_key:
            self.logger.error("API key (access_token) is required for FXCM connection.")
            return False

        try:
            # For fxcmpy, connection is often established during instantiation or by calling connect()
            # if auto_connect=False was used. Let's assume default auto_connect=True.
            self.api = fxcmpy.fxcmpy(access_token=api_key, server=server_env, config_file=config_file) # type: ignore

            # fxcmpy might connect automatically or might need an explicit call if using certain parameters.
            # The `is_connected()` check after instantiation is crucial.
            # If it has a separate connect method, it might look like:
            # self.api.connect()

            if self.api.is_connected():
                self.logger.info(f"Successfully connected to FXCM server: {server_env}. Account IDs: {self.api.get_account_ids()}")
                self._connected = True
                return True
            else:
                # Attempt to explicitly connect if not already connected by constructor
                try:
                    self.api.connect()
                    if self.api.is_connected():
                        self.logger.info(f"Explicit connect call successful to FXCM server: {server_env}. Account IDs: {self.api.get_account_ids()}")
                        self._connected = True
                        return True
                    else:
                        self.logger.error(f"Failed to connect to FXCM server {server_env} after explicit connect call.")
                        self._connected = False
                        self.api = None
                        return False
                except Exception as connect_e: # Catch specific fxcmpy connection errors if known
                    self.logger.error(f"FXCM explicit connect() call failed: {connect_e}")
                    self._connected = False
                    self.api = None
                    return False
        except RuntimeError as e: # fxcmpy can raise RuntimeError on connection failure
            self.logger.error(f"FXCM API RuntimeError during connection: {e}")
            self._connected = False
            self.api = None
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during FXCM connection: {e}")
            self._connected = False
            self.api = None
            return False

    def disconnect(self) -> None:
        self.logger.info(f"Disconnecting from FXCM. Agent: {self.agent_id}")
        if self.api and self._connected:
            try:
                self.api.close()
                self.logger.info("FXCM connection closed.")
            except Exception as e:
                self.logger.error(f"Error during FXCM disconnect: {e}")
        self.api = None
        self._connected = False

    def is_connected(self) -> bool:
        if self.api and self._connected:
            try:
                # Re-verify with the library's method if possible, as connection might drop
                return self.api.is_connected()
            except Exception: # If is_connected() itself throws error
                self._connected = False # Assume disconnected
                return False
        return False

    # --- Mock/Fallback Methods ---
    def _get_mock_account_info(self) -> Optional[AccountInfo]:
        self.logger.info(f"_get_mock_account_info called for agent {self.agent_id}")
        return AccountInfo(
            account_id="mock_fxcm_acc", balance=10000.0, equity=10000.0,
            margin=0.0, free_margin=10000.0, margin_level=float('inf'), currency="USD"
        )

    def _get_mock_current_price(self, symbol: str, reason: str = "Fallback") -> Optional[PriceTick]:
        self.logger.info(f"_get_mock_current_price for {symbol} called. Reason: {reason}")
        base_price = 1.10000
        if "JPY" in symbol.upper(): base_price = 150.000
        # FXCM prices are typically to 5th decimal for non-JPY, 3rd for JPY. Spread is variable.
        spread = 0.00010 if "JPY" not in symbol.upper() else 0.010

        bid = round(base_price - spread, 5 if "JPY" not in symbol.upper() else 3)
        ask = round(base_price + spread, 5 if "JPY" not in symbol.upper() else 3)

        return PriceTick(
            symbol=symbol, timestamp=datetime.now(timezone.utc).timestamp(),
            bid=bid, ask=ask, last=(bid + ask) / 2
        )

    def _get_mock_historical_data(self, symbol: str, timeframe: str, count: int, reason: str = "Fallback") -> List[Candlestick]:
        self.logger.info(f"_get_mock_historical_data for {symbol}, TF={timeframe}, Count={count}. Reason: {reason}")
        bars: List[Candlestick] = []
        current_time = datetime.now(timezone.utc)
        delta_map = {"m1": 60, "m5": 300, "H1": 3600, "D1": 86400} # FXCM uses 'm1', 'H1', 'D1'
        delta_seconds = delta_map.get(timeframe.lower(), 3600)

        for i in range(count):
            ts = (current_time - timedelta(seconds=delta_seconds * (count - 1 - i))).timestamp()
            price = 1.10000 + (i * 0.0001)
            if "JPY" in symbol.upper(): price = 150.000 + (i*0.01)

            o = round(price + random.uniform(-0.0001, 0.0001) * (100 if "JPY" in symbol.upper() else 1), 5)
            c = round(price + random.uniform(-0.0001, 0.0001) * (100 if "JPY" in symbol.upper() else 1), 5)
            h = round(max(o,c) + random.uniform(0, 0.0005) * (100 if "JPY" in symbol.upper() else 1), 5)
            l = round(min(o,c) - random.uniform(0, 0.0005) * (100 if "JPY" in symbol.upper() else 1), 5)

            bars.append(Candlestick(
                timestamp=ts, open=o, high=h, low=l, close=c,
                volume=float(random.randint(100, 1000)) # FXCM candle volume might be ticks
            ))
        return bars

    def _simulate_place_order(self, symbol: str, order_type: OrderType, side: OrderSide, volume: float,
                               price: Optional[float] = None, stop_loss: Optional[float] = None,
                               take_profit: Optional[float] = None, time_in_force: Optional[TimeInForce] = TimeInForce.GTC,
                               fill_policy: Optional[FillPolicy] = FillPolicy.FOK,
                               magic_number: Optional[int] = 0, comment: Optional[str] = "",
                               client_order_id: Optional[str] = None,
                               fail_reason: Optional[str] = "Simulated Fallback") -> OrderResponse:
        self.logger.info(f"_simulate_place_order for {symbol} {order_type} {side} {volume}. Reason: {fail_reason}")
        now_ts = datetime.now(timezone.utc).timestamp()
        sim_order_id = f"sim_fxcm_ord_{uuid.uuid4()}"

        status = "FILLED" if order_type == OrderType.MARKET else "PENDING"
        filled_vol = volume if status == "FILLED" else 0.0
        avg_fill_price = price
        sim_fills: List[FillDetails] = []

        if status == "FILLED":
            mock_current_price = self._get_mock_current_price(symbol, "Simulated Fill")
            if mock_current_price:
                 avg_fill_price = mock_current_price.ask if side == OrderSide.BUY else mock_current_price.bid
            else: avg_fill_price = 1.10050 if side == OrderSide.BUY else 1.09950

            sim_fills.append(FillDetails(
                fill_id=f"sim_fill_{sim_order_id}", fill_price=avg_fill_price, # type: ignore
                fill_volume=filled_vol, fill_timestamp=now_ts, commission=0.0, fee=0.0
            ))

        return OrderResponse(
            order_id=sim_order_id, client_order_id=client_order_id, status=status, symbol=symbol,
            order_type=order_type, side=side, requested_volume=volume, filled_volume=filled_vol,
            average_fill_price=avg_fill_price, requested_price=price, stop_loss_price=stop_loss,
            take_profit_price=take_profit, time_in_force=time_in_force or TimeInForce.GTC,
            fill_policy=fill_policy or FillPolicy.FOK, creation_timestamp=now_ts,
            last_update_timestamp=now_ts, fills=sim_fills,
            error_message=None if status != "REJECTED" else fail_reason,
            broker_native_response={"simulation_details": fail_reason},
            position_id=f"sim_pos_{sim_order_id}" if status == "FILLED" else None
        )

    def _simulate_modify_order(self, order_id: str, new_price: Optional[float] = None,
                               new_stop_loss: Optional[float] = None, new_take_profit: Optional[float] = None,
                               reason: str = "Simulated Fallback") -> OrderResponse:
        self.logger.info(f"_simulate_modify_order for {order_id}. Reason: {reason}")
        return OrderResponse(
            order_id=order_id, client_order_id=None, status="MODIFIED", symbol="EUR/USD", # FXCM uses /
            order_type=OrderType.LIMIT, side=OrderSide.BUY, requested_volume=0.01, filled_volume=0.0,
            average_fill_price=None, requested_price=new_price, stop_loss_price=new_stop_loss,
            take_profit_price=new_take_profit, time_in_force=TimeInForce.GTC, fill_policy=FillPolicy.FOK,
            creation_timestamp=datetime.now(timezone.utc).timestamp() - 1000,
            last_update_timestamp=datetime.now(timezone.utc).timestamp(), fills=[],
            error_message=None, broker_native_response={"simulation_details": reason}, position_id=None
        )

    def _simulate_close_order(self, order_id: str, volume_to_close: Optional[float] = None,
                              reason: str = "Simulated Fallback") -> OrderResponse:
        self.logger.info(f"_simulate_close_order for {order_id} vol {volume_to_close}. Reason: {reason}")
        now_ts = datetime.now(timezone.utc).timestamp()
        closed_vol = volume_to_close or 0.01
        mock_price = self._get_mock_current_price("EUR/USD", "Simulated Close") # FXCM uses /
        close_fill_price = mock_price.bid if mock_price else 1.10000 # type: ignore

        fills_list = [FillDetails(
            fill_id=f"sim_fill_close_{order_id}", fill_price=close_fill_price, fill_volume=closed_vol,
            fill_timestamp=now_ts, commission=0.0, fee=0.0
        )]
        return OrderResponse(
            order_id=order_id, client_order_id=None, status="CLOSED", symbol="EUR/USD",
            order_type=OrderType.MARKET, side=OrderSide.SELL, # Assuming closing a BUY
            requested_volume=closed_vol, filled_volume=closed_vol, average_fill_price=close_fill_price,
            requested_price=None, stop_loss_price=None, take_profit_price=None,
            time_in_force=TimeInForce.IOC, fill_policy=FillPolicy.IOC, creation_timestamp=now_ts,
            last_update_timestamp=now_ts, fills=fills_list, error_message=None,
            broker_native_response={"simulation_details": reason}, position_id=order_id
        )

    # --- BrokerInterface Methods (Shells) ---
    @RateLimiter(max_calls=10, period_seconds=60) # FXCM limits vary, be conservative
    def get_account_info(self) -> Optional[AccountInfo]:
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning("get_account_info: Not connected or FXCM unavailable. Using mock.")
            return self._get_mock_account_info()
        self.logger.info("get_account_info: Live implementation pending.")
        return self._get_mock_account_info()

    @RateLimiter(max_calls=30, period_seconds=60) # Price updates can be frequent but might have overall limits
    def get_current_price(self, symbol: str) -> Optional[PriceTick]:
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning(f"get_current_price for {symbol}: Not connected or FXCM unavailable. Using mock.")
            return self._get_mock_current_price(symbol, reason="Not connected or FXCM unavailable")
        self.logger.info(f"get_current_price for {symbol}: Live implementation pending.")
        return self._get_mock_current_price(symbol, reason="Live pending")

    @RateLimiter(max_calls=10, period_seconds=60)
    def get_historical_data(self, symbol: str, timeframe_str: str,
                              start_time_unix: float, end_time_unix: Optional[float] = None,
                              count: Optional[int] = None) -> List[Candlestick]:
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning(f"get_historical_data for {symbol}: Not connected or FXCM unavailable. Using mock.")
            return self._get_mock_historical_data(symbol, timeframe_str, count or 100, reason="Not connected or FXCM unavailable")
        self.logger.info(f"get_historical_data for {symbol}: Live implementation pending.")
        return self._get_mock_historical_data(symbol, timeframe_str, count or 100, reason="Live pending")

    @RateLimiter(max_calls=10, period_seconds=60) # Order operations often have stricter limits
    def place_order(self, symbol: str, order_type: OrderType, side: OrderSide, volume: float,
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None, time_in_force: Optional[TimeInForce] = TimeInForce.GTC,
                      fill_policy: Optional[FillPolicy] = FillPolicy.FOK,
                      magic_number: Optional[int] = 0, comment: Optional[str] = "",
                      client_order_id: Optional[str] = None) -> OrderResponse:
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning(f"place_order for {symbol}: Not connected or FXCM unavailable. Simulating.")
            return self._simulate_place_order(symbol, order_type, side, volume, price, stop_loss, take_profit,
                                             time_in_force, fill_policy, magic_number, comment, client_order_id,
                                             fail_reason="Not connected or FXCM unavailable")
        self.logger.info(f"place_order for {symbol}: Live implementation pending.")
        return self._simulate_place_order(symbol, order_type, side, volume, price, stop_loss, take_profit,
                                         time_in_force, fill_policy, magic_number, comment, client_order_id,
                                         fail_reason="Live pending")

    @RateLimiter(max_calls=10, period_seconds=60)
    def modify_order(self, order_id: str, new_price: Optional[float] = None,
                     new_stop_loss: Optional[float] = None, new_take_profit: Optional[float] = None,
                     new_client_order_id: Optional[str] = None) -> OrderResponse: # Added client_order_id for consistency
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning(f"modify_order for {order_id}: Not connected or FXCM unavailable. Simulating.")
            return self._simulate_modify_order(order_id, new_price, new_stop_loss, new_take_profit,
                                              reason="Not connected or FXCM unavailable")
        self.logger.info(f"modify_order for {order_id}: Live implementation pending.")
        return self._simulate_modify_order(order_id, new_price, new_stop_loss, new_take_profit, reason="Live pending")

    @RateLimiter(max_calls=10, period_seconds=60)
    def close_order(self, order_id: str, volume_to_close: Optional[float] = None, client_order_id: Optional[str] = None) -> OrderResponse: # Added client_order_id
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning(f"close_order for {order_id}: Not connected or FXCM unavailable. Simulating.")
            return self._simulate_close_order(order_id, volume_to_close, reason="Not connected or FXCM unavailable")
        self.logger.info(f"close_order for {order_id}: Live implementation pending.")
        return self._simulate_close_order(order_id, volume_to_close, reason="Live pending")

    @RateLimiter(max_calls=10, period_seconds=60)
    def get_open_positions(self) -> List[Position]:
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning("get_open_positions: Not connected or FXCM unavailable. Returning empty list.")
            return []
        self.logger.info("get_open_positions: Live implementation pending.")
        return []

    @RateLimiter(max_calls=10, period_seconds=60)
    def get_pending_orders(self) -> List[OrderResponse]:
        if not self._connected or not self.fxcmpy_available:
            self.logger.warning("get_pending_orders: Not connected or FXCM unavailable. Returning empty list.")
            return []
        self.logger.info("get_pending_orders: Live implementation pending.")
        return []


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    import os
    api_k = os.getenv("FXCM_API_KEY")
    server_env = os.getenv("FXCM_SERVER", "demo") # Default to 'demo' if not set

    if api_k:
        broker = FXCMBroker(agent_id="TestFXCM")
        creds = {"api_key": api_k, "server": server_env}
        if broker.connect(creds):
            print(f"Connection Test: SUCCESSFUL. Connected: {broker.is_connected()}")

            print("Testing mock account info:", broker.get_account_info())
            print("Testing mock EUR/USD price:", broker.get_current_price("EUR/USD")) # FXCM uses /
            print("Testing mock historical data:", broker.get_historical_data("GBP/JPY", "H1", count=3))

            mock_order_resp = broker.place_order("USD/CAD", OrderType.MARKET, OrderSide.SELL, 0.01)
            print("Testing mock place_order:", mock_order_resp)

            if mock_order_resp.order_id and mock_order_resp.status not in ["REJECTED", "ERROR"]:
                sim_ord_id = mock_order_resp.order_id
                # FXCM uses trade_id for modifying SL/TP of open positions.
                # Order ID from place_order might be different from trade_id.
                # For mock, we'll use it as a placeholder.
                trade_id_placeholder = mock_order_resp.position_id or sim_ord_id
                print("Testing mock modify_order (on trade):", broker.modify_order(trade_id_placeholder, new_stop_loss=1.3400))
                print("Testing mock close_order (on trade):", broker.close_order(trade_id_placeholder))

            print("Testing mock open positions:", broker.get_open_positions())
            print("Testing mock pending orders:", broker.get_pending_orders())

            broker.disconnect()
            print(f"Connection Test: DISCONNECTED. Connected: {broker.is_connected()}")
        else:
            print(f"Connection Test: FAILED. Connected: {broker.is_connected()}")
    else:
        print("Skipping FXCM connection test: FXCM_API_KEY not set in environment.")

    if not FXCMPY_AVAILABLE:
        print("\nNote: fxcmpy library was not found. All FXCM operations are mocked.")
        no_lib_broker = FXCMBroker(agent_id="NoLibTestFXCM")
        print("Testing mock account info (no lib):", no_lib_broker.get_account_info())
        no_lib_order = no_lib_broker.place_order("AUD/USD", OrderType.LIMIT, OrderSide.BUY, 0.1, price=0.6500)
        print("Testing mock place_order (no lib):", no_lib_order)
