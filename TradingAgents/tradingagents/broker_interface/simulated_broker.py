from typing import List, Dict, Optional, Any, Tuple
from tradingagents.broker_interface.base import BrokerInterface
from tradingagents.forex_utils.forex_states import (
    PriceTick, Candlestick, AccountInfo, OrderResponse, Position,
    OrderType, OrderSide, TimeInForce
)
import datetime
import time
import random
import uuid

class SimulatedBroker(BrokerInterface):
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.balance = initial_capital
        self.equity = initial_capital
        self._connected = True
        self.current_simulated_time_unix = time.time()

        self.open_positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, Dict[str, Any]] = {} # Storing as dict for flexibility with SL/TP
        self.trade_history: List[Dict] = []

        self.order_fill_logic: str = "CURRENT_BAR_CLOSE"
        self.fixed_slippage_pips: float = 0.2

        self.current_market_data: Dict[str, Candlestick] = {}

        self.default_spread_pips: Dict[str, float] = {
            "EURUSD": 0.5, "GBPUSD": 0.6, "USDJPY": 0.5, "AUDUSD": 0.7, "USDCAD": 0.7, "XAUUSD": 2.0
        }
        self.commission_per_lot: Dict[str, float] = {
            "EURUSD": 7.0, "GBPUSD": 7.0, "USDJPY": 7.0, "AUDUSD": 7.0, "USDCAD": 7.0, "XAUUSD": 7.0
        }
        self.leverage: int = 100
        self.margin_used: float = 0.0
        self.account_currency = "USD"
        self.margin_call_warning_level_pct = 100.0 # e.g., 100%
        self.stop_out_level_pct = 50.0          # e.g., 50%
        self.test_data_store: Dict[str, List[Dict]] = {} # Added for test data

        print(f"SimulatedBroker initialized. Capital: {initial_capital}, Slippage: {self.fixed_slippage_pips} pips, Leverage: {self.leverage}:1, Account Currency: {self.account_currency}, Margin Warning: {self.margin_call_warning_level_pct}%, Stop Out: {self.stop_out_level_pct}%")

    def load_test_data(self, symbol: str, data_sequence: List[Dict]):
        # data_sequence should be a list of Candlestick-like dictionaries
        # already sorted chronologically
        print(f"SimBroker: Loading {len(data_sequence)} bars of test data for {symbol}.")
        self.test_data_store[symbol.upper()] = data_sequence

    def _generate_unique_id(self) -> str:
        return str(uuid.uuid4())

    def _get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        symbol_upper = symbol.upper()
        if len(symbol_upper) == 6 and symbol_upper.isalnum():
            base = symbol_upper[:3]
            quote = symbol_upper[3:]
            if "JPY" == quote:
                return {"base_currency": base, "quote_currency": quote, "price_precision": 3, "point_size": 0.001, "pip_unit_value": 0.01}
            else:
                return {"base_currency": base, "quote_currency": quote, "price_precision": 5, "point_size": 0.00001, "pip_unit_value": 0.0001}
        elif symbol_upper in ["XAUUSD", "GOLD"]:
            return {"base_currency": "XAU", "quote_currency": "USD", "price_precision": 2, "point_size": 0.01, "pip_unit_value": 0.1}
        print(f"SimBroker._get_symbol_info: Symbol info not configured for {symbol}")
        return None

    def _get_point_size(self, symbol: str) -> float:
        info = self._get_symbol_info(symbol)
        return info["point_size"] if info else 0.00001

    def _get_price_precision(self, symbol: str) -> int:
        info = self._get_symbol_info(symbol)
        return info["price_precision"] if info else 5

    def _get_pip_value_for_sl_tp(self, symbol: str) -> float: # This is the price change for 1 pip
        info = self._get_symbol_info(symbol)
        return info["pip_unit_value"] if info else 0.0001

    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        if from_currency == to_currency: return 1.0
        direct_pair = f"{from_currency}{to_currency}".upper()
        inverse_pair = f"{to_currency}{from_currency}".upper()

        current_market_direct = self.current_market_data.get(direct_pair)
        if current_market_direct: return current_market_direct['close']

        current_market_inverse = self.current_market_data.get(inverse_pair)
        if current_market_inverse and current_market_inverse['close'] != 0:
            return 1.0 / current_market_inverse['close']

        # Simplified USD cross for non-USD account currency (more complex logic needed for full support)
        if self.account_currency != "USD": # Only attempt USD cross if account is not USD
             # Try from_currency -> USD -> to_currency
            from_usd_rate = self._get_exchange_rate(from_currency, "USD")
            usd_to_rate = self._get_exchange_rate("USD", to_currency)
            if from_usd_rate and usd_to_rate:
                return from_usd_rate * usd_to_rate

        print(f"SimBroker._get_exchange_rate: Exchange rate for {from_currency}/{to_currency} not found. Current time: {self.current_simulated_time_unix}")
        return None

    def calculate_pip_value_in_account_currency(self, symbol: str, volume_lots: float) -> Optional[float]:
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info: return None
        pip_unit_val = symbol_info['pip_unit_value']
        quote_currency = symbol_info['quote_currency']
        contract_size = 100000
        value_of_one_pip_in_quote_currency = pip_unit_val * contract_size * volume_lots
        if quote_currency == self.account_currency:
            return value_of_one_pip_in_quote_currency
        exchange_rate = self._get_exchange_rate(quote_currency, self.account_currency)
        if exchange_rate is None:
            print(f"SimBroker.calculate_pip_value: Failed to get exchange rate for {quote_currency} to {self.account_currency} for symbol {symbol}")
            return None
        return value_of_one_pip_in_quote_currency * exchange_rate

    def calculate_pnl_in_account_currency(self, symbol: str, side: OrderSide, volume_lots: float, entry_price: float, close_price: float) -> Optional[float]:
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info: return None
        price_difference = (close_price - entry_price) if side == OrderSide.BUY else (entry_price - close_price)
        if symbol_info['pip_unit_value'] == 0: return None
        pips_moved = price_difference / symbol_info['pip_unit_value']
        value_of_one_pip_for_one_lot = self.calculate_pip_value_in_account_currency(symbol, 1.0)
        if value_of_one_pip_for_one_lot is None: return None
        return pips_moved * value_of_one_pip_for_one_lot * volume_lots

    def _get_spread_in_price_terms(self, symbol: str) -> float:
        pips = self.default_spread_pips.get(symbol.upper(), 1.0)
        pip_price_unit = self._get_pip_value_for_sl_tp(symbol)
        return pips * pip_price_unit

    def _calculate_commission(self, symbol: str, volume_lots: float) -> float:
        return self.commission_per_lot.get(symbol.upper(), 0.0) * volume_lots

    def _calculate_margin_required(self, symbol: str, volume_lots: float, entry_price: float) -> float:
        contract_size = 100000
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info:
            print(f"SimBroker._calculate_margin_required: Symbol info for {symbol} not found. Margin might be inaccurate.")
            return (volume_lots * contract_size * entry_price) / self.leverage # Fallback

        base_currency = symbol_info['base_currency']
        quote_currency = symbol_info['quote_currency']

        # Notional value in base currency units * entry_price (base/quote) = notional value in quote currency
        notional_value_in_quote_currency = volume_lots * contract_size * entry_price

        margin_in_base_currency = (volume_lots * contract_size) / self.leverage # Standard formula: LotSize / Leverage

        if base_currency == self.account_currency:
            return margin_in_base_currency * entry_price # if base is USD, entry is XXX/USD, gives USD margin. This seems more standard.
                                                        # Or rather, (Vol * CS * Price) / Lev for quote currency margin, then convert.
                                                        # Let's use (Vol * CS * Price) / Lev for quote currency margin, then convert to Account Currency

        # Standard: (Market Price * Volume in Base Currency) / Leverage = Margin in Quote Currency
        # Then convert Margin in Quote Currency to Account Currency.
        # Notional Value in Quote Currency = volume_lots * contract_size * entry_price

        # Margin required in terms of the base currency of the pair, converted to account currency
        # Example: EURUSD, 1 lot (100k EUR). Margin req = 1000 EUR (at 100:1). Convert 1000 EUR to USD.
        # If trading 1 lot EURUSD (100,000 EUR) at 1.0800, with 100:1 leverage:
        # Margin needed = (100,000 EUR / 100) = 1,000 EUR.
        # Convert 1,000 EUR to USD: 1,000 * EURUSD_rate (if account is USD).

        margin_in_base_currency_units = (volume_lots * contract_size) / self.leverage

        if base_currency == self.account_currency:
            return margin_in_base_currency_units # e.g. for USD/JPY on USD account, margin is in USD

        # Base currency needs to be converted to account currency
        exchange_rate_base_to_account = self._get_exchange_rate(base_currency, self.account_currency)
        if exchange_rate_base_to_account is None:
            print(f"SimBroker._calculate_margin_required: Could not get exchange rate {base_currency}{self.account_currency} for margin calc of {symbol}. Using simplified margin.")
            # Fallback to quote currency calculation if base conversion fails (less accurate but better than nothing)
            if quote_currency == self.account_currency: return notional_value_in_quote_currency / self.leverage
            rate_quote_to_acc = self._get_exchange_rate(quote_currency, self.account_currency)
            return (notional_value_in_quote_currency / self.leverage) * rate_quote_to_acc if rate_quote_to_acc else (notional_value_in_quote_currency / self.leverage)

        return margin_in_base_currency_units * exchange_rate_base_to_account

    def update_current_time(self, simulated_time_unix: float):
        self.current_simulated_time_unix = simulated_time_unix

    def update_market_data(self, market_data: Dict[str, Candlestick]):
        self.current_market_data = market_data
        self._update_equity_and_margin()

    def connect(self, credentials: Dict[str, Any]) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_current_price(self, symbol: str) -> Optional[PriceTick]:
        current_bar = self.current_market_data.get(symbol)
        if not current_bar:
            if symbol == "EURUSD": base_bid = 1.08500
            elif symbol == "GBPUSD": base_bid = 1.27100
            else: print(f"SimBroker: No current bar data or fallback static price for {symbol}"); return None
            spread = self._get_spread_in_price_terms(symbol)
            precision = self._get_price_precision(symbol)
            return PriceTick(symbol=symbol, timestamp=self.current_simulated_time_unix,
                             bid=round(base_bid, precision), ask=round(base_bid + spread, precision),
                             last=round(base_bid + (spread/2), precision))
        spread_amount = self._get_spread_in_price_terms(symbol)
        precision = self._get_price_precision(symbol)
        bid_price = round(current_bar['close'] - (spread_amount / 2.0), precision)
        ask_price = round(current_bar['close'] + (spread_amount / 2.0), precision)
        return PriceTick(symbol=symbol, timestamp=self.current_simulated_time_unix, bid=bid_price, ask=ask_price, last=current_bar['close'])

    def get_historical_data(self, symbol: str, timeframe_str: str,
                              start_time_unix: float, end_time_unix: Optional[float] = None,
                              count: Optional[int] = None) -> List[Dict]: # Candlestick

            symbol_upper = symbol.upper()
            # Use current_simulated_time_unix as the absolute end point for any historical data request
            # to prevent look-ahead bias.
            effective_end_time_unix = min(end_time_unix if end_time_unix is not None else self.current_simulated_time_unix,
                                          self.current_simulated_time_unix)

            print(f"SimBroker: get_historical_data({symbol_upper}, TF:{timeframe_str}) requested range: "
                  f"{datetime.datetime.fromtimestamp(start_time_unix, tz=datetime.timezone.utc).isoformat()} to "
                  f"{datetime.datetime.fromtimestamp(effective_end_time_unix, tz=datetime.timezone.utc).isoformat()}. Current sim time: {datetime.datetime.fromtimestamp(self.current_simulated_time_unix, tz=datetime.timezone.utc).isoformat()}")

            if symbol_upper in self.test_data_store:
                all_bars_for_symbol = self.test_data_store[symbol_upper]
                # Filter bars within the requested range [start_time_unix, effective_end_time_unix]

                relevant_bars = [
                    Candlestick(**bar) for bar in all_bars_for_symbol # Ensure cast to TypedDict if stored as raw dicts
                    if bar['timestamp'] >= start_time_unix and bar['timestamp'] <= effective_end_time_unix
                ]

                # If count is specified, take the last 'count' bars from the filtered list
                if count is not None and len(relevant_bars) > count:
                    relevant_bars = relevant_bars[-count:]

                print(f"SimBroker: Returning {len(relevant_bars)} bars from test_data_store for {symbol_upper}.")
                return relevant_bars
            else: # Fallback to dummy generation if no test data loaded for this symbol
                print(f"SimBroker: No test_data_store for {symbol_upper}. Generating dummy historical data.")
                # ... (keep existing dummy generation logic here, but ensure it also respects effective_end_time_unix)
                # For simplicity, this subtask can omit reimplementing the full dummy generation here
                # if the focus is on using test_data_store. Just return empty list if not in store.
                # For this subtask, let's make it return empty if not in test_data_store to force test data usage.
                # Reinstating dummy generation for completeness, but ensuring it respects effective_end_time_unix
                dummy_bars_generated: List[Candlestick] = []
                time_step_seconds = self._get_timeframe_seconds_approx(timeframe_str)

                # Determine num_bars_to_generate for dummy data
                if count is not None:
                    num_to_gen = count
                    # Start generating backwards from effective_end_time_unix
                    current_bar_open_time_for_dummy = effective_end_time_unix - time_step_seconds
                else:
                    if effective_end_time_unix < start_time_unix: return []
                    num_to_gen = int((effective_end_time_unix - start_time_unix) / time_step_seconds)
                    current_bar_open_time_for_dummy = effective_end_time_unix - time_step_seconds

                for i in range(num_to_gen):
                    bar_open_timestamp = current_bar_open_time_for_dummy - (i * time_step_seconds)
                    if bar_open_timestamp < start_time_unix: continue # Ensure not earlier than requested start

                    idx_from_oldest = num_to_gen - 1 - i # To make prices somewhat trend
                    base_price = 1.0700 + (idx_from_oldest * 0.0001)
                    if "JPY" in symbol_upper: base_price = 150.00 + (idx_from_oldest * 0.01)
                    elif "XAU" in symbol_upper: base_price = 2300.00 + (idx_from_oldest * 0.1)
                    precision = self._get_price_precision(symbol_upper)
                    point = self._get_point_size(symbol_upper) * 10
                    open_val = round(base_price + random.uniform(-point, point), precision)
                    close_val = round(base_price + random.uniform(-point, point), precision)
                    high_val = round(max(open_val, close_val) + random.uniform(0, point*2), precision)
                    low_val = round(min(open_val, close_val) - random.uniform(0, point*2), precision)
                    dummy_bars_generated.append(Candlestick(timestamp=bar_open_timestamp, open=open_val, high=high_val, low=low_val, close=close_val, volume=float(random.randint(500,2000) + idx_from_oldest)))

                dummy_bars_generated.sort(key=lambda x: x['timestamp']) # Ensure chronological
                # Final filter for exactness, though loop condition should mostly handle start_time_unix
                final_dummy_bars = [b for b in dummy_bars_generated if b['timestamp'] >= start_time_unix and b['timestamp'] < effective_end_time_unix]
                print(f"SimBroker: Generated and returning {len(final_dummy_bars)} dummy bars for {symbol_upper}.")
                return final_dummy_bars

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60;  # ... (rest of timeframes)
        if "M5" == timeframe_str: return 5 * 60;
        if "M15" == timeframe_str: return 15 * 60;
        if "M30" == timeframe_str: return 30 * 60;
        if "H1" == timeframe_str: return 60 * 60;
        if "H4" == timeframe_str: return 4 * 60 * 60;
        if "D1" == timeframe_str: return 24 * 60 * 60;
        if "W1" == timeframe_str: return 7 * 24 * 60 * 60;
        if "MN1" == timeframe_str: return 30 * 24 * 60 * 60;
        return 60 * 60

    def get_account_info(self) -> Optional[AccountInfo]:
        if not self.is_connected(): return None
        # _update_equity_and_margin() # Called by update_market_data, or before critical checks
        free_margin = self.equity - self.margin_used
        margin_level = (self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')
        return AccountInfo(account_id=self._generate_unique_id()[:8], balance=round(self.balance, 2), equity=round(self.equity, 2), margin=round(self.margin_used, 2), free_margin=round(free_margin, 2), margin_level=round(margin_level, 2) if margin_level != float('inf') else float('inf'), currency=self.account_currency)

    def place_order(self, symbol: str, order_type: OrderType, side: OrderSide, volume: float,
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None, time_in_force: TimeInForce = TimeInForce.GTC,
                      magic_number: Optional[int] = 0, comment: Optional[str] = "") -> OrderResponse:
        order_id = self._generate_unique_id()
        timestamp_unix = self.current_simulated_time_unix
        if not self.is_connected(): return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Broker not connected.")
        current_bar = self.current_market_data.get(symbol)
        if not current_bar: return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message=f"Market data not available for {symbol} at {datetime.datetime.fromtimestamp(timestamp_unix, tz=datetime.timezone.utc).isoformat()}.")

        price_precision = self._get_price_precision(symbol)

        if order_type == OrderType.MARKET:
            fill_price_base = current_bar['close']
            spread_amount = self._get_spread_in_price_terms(symbol)
            point_size = self._get_point_size(symbol)
            slippage_in_price = self.fixed_slippage_pips * point_size
            entry_price_final: float
            if side == OrderSide.BUY: entry_price_final = round(fill_price_base + (spread_amount / 2) + random.uniform(0, slippage_in_price), price_precision)
            elif side == OrderSide.SELL: entry_price_final = round(fill_price_base - (spread_amount / 2) - random.uniform(0, slippage_in_price), price_precision)
            else: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Invalid order side.")

            margin_for_this_trade = self._calculate_margin_required(symbol, volume, entry_price_final)
            # Ensure equity/margin is current before checking free margin
            self._update_equity_and_margin() # Call here to ensure fresh values before check
            free_margin = self.equity - self.margin_used
            if free_margin < margin_for_this_trade:
                 return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=entry_price_final, timestamp=timestamp_unix, error_message=f"Insufficient free margin. Need: {margin_for_this_trade:.2f}, Have: {free_margin:.2f}")

            commission_cost = self._calculate_commission(symbol, volume)
            position_id = self._generate_unique_id()
            new_position = Position(position_id=position_id, symbol=symbol, side=side, volume=volume, entry_price=entry_price_final, current_price=entry_price_final, profit_loss= -commission_cost, stop_loss=stop_loss, take_profit=take_profit, open_time=timestamp_unix, magic_number=magic_number, comment=comment)
            self.open_positions[position_id] = new_position
            self.balance -= commission_cost
            self.margin_used += margin_for_this_trade
            self._update_equity_and_margin()
            self.trade_history.append({"event_type": "MARKET_ORDER_FILLED", "timestamp": timestamp_unix, "order_id": order_id, "position_id": position_id, "symbol": symbol, "side": side.value, "volume": volume, "fill_price": entry_price_final, "sl": stop_loss, "tp": take_profit, "commission": commission_cost, "comment": comment})
            print(f"SimBroker: {side.value} {volume} {symbol} @ {entry_price_final} (spread/slip incl). PosID: {position_id}. Comm: {commission_cost:.2f}")
            return OrderResponse(order_id=order_id, status="FILLED", symbol=symbol, side=side, type=order_type, volume=volume, price=entry_price_final, timestamp=timestamp_unix, error_message=None, position_id=position_id)

        elif order_type in [OrderType.LIMIT, OrderType.STOP]:
            if price is None: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Price required for pending orders.")
            self.pending_orders[order_id] = {"order_id": order_id, "status": "PENDING", "symbol": symbol, "side": side, "type": order_type, "volume": volume, "price": price, "timestamp": timestamp_unix, "stop_loss": stop_loss, "take_profit": take_profit, "magic_number": magic_number, "comment": comment}
            self.trade_history.append({"event_type": "PENDING_ORDER_PLACED", "timestamp": timestamp_unix, "order_id": order_id, "symbol": symbol, "side": side.value, "type": order_type.value, "volume": volume, "price": price, "sl": stop_loss, "tp": take_profit, "comment": comment})
            print(f"SimBroker: Pending {side.value} {order_type.value} for {volume} {symbol} @ {price} SL:{stop_loss} TP:{take_profit} placed. OrderID: {order_id}")
            return OrderResponse(order_id=order_id, status="PENDING", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message=None)
        return OrderResponse(order_id=order_id, status="REJECTED", error_message="Unsupported order type.")

    def process_pending_orders(self):
        if not self.current_market_data or not self.current_simulated_time_unix: return
        orders_to_remove_after_processing = []
        for order_id, po_details in list(self.pending_orders.items()):
            symbol, bar, order_price, order_type, order_side, order_volume = po_details['symbol'], self.current_market_data.get(po_details['symbol']), po_details['price'], po_details['type'], po_details['side'], po_details['volume']
            if not bar: continue
            sl_pos, tp_pos, magic_pos, comment_pos = po_details.get('stop_loss'), po_details.get('take_profit'), po_details.get('magic_number'), po_details.get('comment', f"Filled from pending {order_id}")
            fill_price_sim: Optional[float] = None; precision = self._get_price_precision(symbol)
            if order_type == OrderType.LIMIT:
                if order_side == OrderSide.BUY and bar['low'] <= order_price: fill_price_sim = min(order_price, bar['open'])
                elif order_side == OrderSide.SELL and bar['high'] >= order_price: fill_price_sim = max(order_price, bar['open'])
            elif order_type == OrderType.STOP:
                if order_side == OrderSide.BUY and bar['high'] >= order_price: fill_price_sim = max(order_price, bar['open'])
                elif order_side == OrderSide.SELL and bar['low'] <= order_price: fill_price_sim = min(order_price, bar['open'])
            if fill_price_sim is not None:
                fill_price_sim = round(fill_price_sim, precision); print(f"SimBroker: Pending order {order_id} TRIGGERED @ {fill_price_sim}.")
                ts_unix = self.current_simulated_time_unix; actual_fill = fill_price_sim
                slip_amt = self.fixed_slippage_pips * self._get_point_size(symbol)
                if order_type == OrderType.STOP: actual_fill += random.uniform(0, slip_amt) if order_side == OrderSide.BUY else -random.uniform(0, slip_amt)
                actual_fill = round(actual_fill, precision)
                margin_req = self._calculate_margin_required(symbol, order_volume, actual_fill)
                self._update_equity_and_margin() # Ensure fresh equity/margin for check
                free_margin = self.equity - self.margin_used
                if free_margin < margin_req:
                    print(f"SimBroker: Insufficient margin for pending {order_id}. Need: {margin_req:.2f}, Have: {free_margin:.2f}. Removed.")
                    self.trade_history.append({"event_type": "PENDING_ORDER_FAIL_MARGIN", "timestamp": ts_unix, "order_id": order_id, "symbol": symbol, "side": order_side.value, "volume": order_volume, "trigger_price": fill_price_sim, "reason": "Insufficient margin"})
                    orders_to_remove_after_processing.append(order_id); continue
                commission = self._calculate_commission(symbol, order_volume); pos_id = self._generate_unique_id()
                new_pos = Position(position_id=pos_id, symbol=symbol, side=order_side, volume=order_volume, entry_price=actual_fill, current_price=actual_fill, profit_loss= -commission, stop_loss=sl_pos, take_profit=tp_pos, open_time=ts_unix, magic_number=magic_pos, comment=comment_pos)
                self.open_positions[pos_id] = new_pos; self.balance -= commission; self.margin_used += margin_req
                self._update_equity_and_margin()
                self.trade_history.append({"event_type": "PENDING_ORDER_FILLED", "timestamp": ts_unix, "original_order_id": order_id, "position_id": pos_id, "symbol": symbol, "side": order_side.value, "type": order_type.value, "volume": order_volume, "requested_price": order_price, "fill_price": actual_fill, "sl": sl_pos, "tp": tp_pos, "commission": commission, "comment": comment_pos})
                print(f"SimBroker: Pending order {order_id} FILLED. New PosID: {pos_id} for {symbol} {order_side.value} {order_volume} @ {actual_fill}. Comm: {commission:.2f}")
                orders_to_remove_after_processing.append(order_id)
        for oid in orders_to_remove_after_processing:
            if oid in self.pending_orders: del self.pending_orders[oid]

    def _update_equity_and_margin(self):
        current_total_unrealized_pnl = 0.0
        current_total_margin_used = 0.0
        # contract_size = 100000 # Already part of calculate_pnl_in_account_currency

        for pos_id, pos_dict_or_obj in list(self.open_positions.items()): # Iterate on list copy if modifications happen
            # Ensure we're working with a consistent object type, prefer dict for direct updates here
            # If Position objects are stored, they need to be mutable or replaced.
            # Assuming self.open_positions stores dictionaries that conform to Position TypedDict.
            current_pos_data = pos_dict_or_obj

            symbol_info = self._get_symbol_info(current_pos_data['symbol'])
            if not symbol_info:
                print(f"SimBroker._update_equity_and_margin: Missing symbol info for {current_pos_data['symbol']}, cannot update P/L accurately.")
                # Add existing P/L if available, otherwise 0 for this position.
                current_total_unrealized_pnl += current_pos_data.get('profit_loss', 0.0)
                # Recalculate margin based on entry price, even if P/L cannot be updated.
                current_total_margin_used += self._calculate_margin_required(current_pos_data['symbol'], current_pos_data['volume'], current_pos_data['entry_price'])
                continue

            current_bar = self.current_market_data.get(current_pos_data['symbol'])
            if not current_bar:
                # print(f"SimBroker._update_equity_and_margin: No current market data for {current_pos_data['symbol']}. P/L for pos {pos_id} not updated this tick.")
                # Add existing P/L as it couldn't be updated
                current_total_unrealized_pnl += current_pos_data.get('profit_loss', 0.0)
                current_total_margin_used += self._calculate_margin_required(current_pos_data['symbol'], current_pos_data['volume'], current_pos_data['entry_price'])
                continue

            market_close_price = current_bar['close']
            spread_amount_for_symbol = self._get_spread_in_price_terms(current_pos_data['symbol'])
            price_precision = symbol_info['price_precision']

            valuation_price: float
            if current_pos_data['side'] == OrderSide.BUY: # Long position, valued at current Bid
                valuation_price = round(market_close_price - (spread_amount_for_symbol / 2), price_precision)
            else: # SELL position, valued at current Ask
                valuation_price = round(market_close_price + (spread_amount_for_symbol / 2), price_precision)

            unrealized_pnl_for_pos = self.calculate_pnl_in_account_currency(
                current_pos_data['symbol'],
                current_pos_data['side'],
                current_pos_data['volume'],
                current_pos_data['entry_price'],
                valuation_price
            )

            if unrealized_pnl_for_pos is not None:
                self.open_positions[pos_id]['profit_loss'] = unrealized_pnl_for_pos
                self.open_positions[pos_id]['current_price'] = valuation_price
                current_total_unrealized_pnl += unrealized_pnl_for_pos
            else:
                # If PNL calculation failed (e.g. missing exchange rate), add last known PNL
                print(f"SimBroker._update_equity_and_margin: PNL calculation failed for {current_pos_data['symbol']} pos {pos_id}. Using last known PNL.")
                current_total_unrealized_pnl += current_pos_data.get('profit_loss', 0.0)

            # Margin is based on entry price, not current price
            margin_for_pos = self._calculate_margin_required(current_pos_data['symbol'], current_pos_data['volume'], current_pos_data['entry_price'])
            current_total_margin_used += margin_for_pos

        self.equity = self.balance + current_total_unrealized_pnl
        self.margin_used = current_total_margin_used
        # print(f"SimBroker: Equity updated. Balance: {self.balance:.2f}, Total Unrealized P/L: {current_total_unrealized_pnl:.2f}, Equity: {self.equity:.2f}, Margin Used: {self.margin_used:.2f}")

    def modify_order(self, order_id: str, new_price: Optional[float] = None, new_stop_loss: Optional[float] = None, new_take_profit: Optional[float] = None) -> OrderResponse:
        ts = self.current_simulated_time_unix
        if order_id in self.open_positions:
            pos = self.open_positions[order_id]
            if new_stop_loss is not None: pos['stop_loss'] = new_stop_loss
            if new_take_profit is not None: pos['take_profit'] = new_take_profit
            return OrderResponse(order_id=order_id, status="MODIFIED", symbol=pos['symbol'], side=pos['side'], type=OrderType.MARKET, volume=pos['volume'], price=pos['entry_price'], timestamp=ts, position_id=order_id)
        elif order_id in self.pending_orders:
            po = self.pending_orders[order_id]
            if new_price is not None: po['price'] = new_price
            if new_stop_loss is not None: po['stop_loss'] = new_stop_loss
            if new_take_profit is not None: po['take_profit'] = new_take_profit
            return OrderResponse(order_id=order_id, status="MODIFIED_PENDING", symbol=po['symbol'], side=po['side'], type=po['type'], volume=po['volume'], price=po['price'], timestamp=ts)
        return OrderResponse(order_id=order_id, status="REJECTED", error_message="Order/Position not found.", timestamp=ts)

    def _close_position_at_price(self, position: Position, close_price: float, reason: str):
        current_position_id = position.position_id
        if current_position_id not in self.open_positions:
            print(f"SimBroker: Position {current_position_id} already actioned or does not exist. Cannot close for reason: {reason}.")
            return

        realized_pnl = self.calculate_pnl_in_account_currency(position.symbol, position.side, position.volume, position.entry_price, close_price)

        if realized_pnl is None:
            print(f"SimBroker: PNL calculation failed for closing pos {current_position_id} ({position.symbol}). Realized PNL recorded as 0.0. Position will still be closed.")
            realized_pnl = 0.0 # Set PNL to 0.0 for accounting if calculation failed, but still close position

        self.balance += realized_pnl
        margin_freed = self._calculate_margin_required(position.symbol, position.volume, position.entry_price)
        self.margin_used -= margin_freed
        if self.margin_used < 0: self.margin_used = 0

        open_time_log = position.get('open_time', self.current_simulated_time_unix)
        comment_log = position.get('comment', "")
        magic_log = position.get('magic_number', 0)

        self.trade_history.append({"event_type": "POSITION_CLOSED", "timestamp": self.current_simulated_time_unix, "position_id": current_position_id, "symbol": position.symbol, "side": position.side.value, "volume": position.volume, "entry_price": position.entry_price, "open_time": open_time_log, "close_price": close_price, "realized_pnl": realized_pnl, "reason_for_close": reason, "magic_number": magic_log, "comment": comment_log})

        del self.open_positions[current_position_id]
        print(f"SimBroker: Position {current_position_id} ({position.symbol} {position.side.value} {position.volume} lot(s)) CLOSED at {close_price} by {reason}. P/L: {realized_pnl:.2f}. Margin Freed: {margin_freed:.2f}")
        self._update_equity_and_margin()

    def check_for_sl_tp_triggers(self):
        if not self.current_market_data or not self.current_simulated_time_unix: return
        positions_to_action = []
        for pos_id, pos_data in list(self.open_positions.items()):
            pos = Position(**pos_data) if isinstance(pos_data, dict) else pos_data
            if pos.symbol not in self.current_market_data: continue
            bar = self.current_market_data[pos.symbol]
            trigger_price = None; reason = None
            if pos.side == OrderSide.BUY:
                if pos.stop_loss is not None and bar['low'] <= pos.stop_loss: trigger_price, reason = pos.stop_loss, "STOP_LOSS_HIT"
                elif pos.take_profit is not None and bar['high'] >= pos.take_profit: trigger_price, reason = pos.take_profit, "TAKE_PROFIT_HIT"
            elif pos.side == OrderSide.SELL:
                if pos.stop_loss is not None and bar['high'] >= pos.stop_loss: trigger_price, reason = pos.stop_loss, "STOP_LOSS_HIT"
                elif pos.take_profit is not None and bar['low'] <= pos.take_profit: trigger_price, reason = pos.take_profit, "TAKE_PROFIT_HIT"
            if trigger_price is not None: positions_to_action.append({"position_to_close": pos, "close_price": trigger_price, "reason": reason})
        for item in positions_to_action: self._close_position_at_price(item["position_to_close"], item["close_price"], item["reason"])

    def close_order(self, order_id: str, volume: Optional[float] = None, price: Optional[float] = None) -> OrderResponse: # order_id here is position_id
        if order_id not in self.open_positions: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Position not found.")
        pos_to_close = Position(**self.open_positions[order_id]) if isinstance(self.open_positions[order_id], dict) else self.open_positions[order_id]
        current_bar = self.current_market_data.get(pos_to_close.symbol)
        if not current_bar: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Market data unavailable.")

        close_price_to_use = price
        if close_price_to_use is None: # Market close
            spread_amount = self._get_spread_in_price_terms(pos_to_close.symbol)
            close_price_base = current_bar['close']
            close_price_to_use = (close_price_base - spread_amount / 2) if pos_to_close.side == OrderSide.BUY else (close_price_base + spread_amount / 2)
            close_price_to_use = round(close_price_to_use, self._get_price_precision(pos_to_close.symbol))

        # Volume check not implemented for partial close, assuming full close
        self._close_position_at_price(pos_to_close, close_price_to_use, "CLOSED_BY_REQUEST")
        return OrderResponse(order_id=order_id, status="CLOSED", symbol=pos_to_close.symbol, side=pos_to_close.side, type=OrderType.MARKET, volume=pos_to_close.volume, price=close_price_to_use, timestamp=self.current_simulated_time_unix, position_id=order_id)

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        self._update_equity_and_margin()
        return [Position(**pos_data) if isinstance(pos_data, dict) else pos_data for pos_data in self.open_positions.values() if symbol is None or pos_data['symbol'] == symbol]

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        return [OrderResponse(**order_data) for order_data in self.pending_orders.values() if symbol is None or order_data['symbol'] == symbol]

    def check_for_margin_call(self):
        # This method checks if the account's margin level has fallen below critical thresholds.
        # If below stop-out level, it force-liquidates positions.
        # It should be called by the backtester event loop AFTER all P/L for open positions
        # has been updated for the current bar (i.e., after _update_equity_and_margin).

        if self.margin_used == 0: # No margin used, so no margin call possible
            return

        # _update_equity_and_margin should have been called before this to ensure self.equity is current.
        margin_level_pct = (self.equity / self.margin_used) * 100 if self.margin_used > 0 else float('inf')

        timestamp_unix = self.current_simulated_time_unix
        log_event_common = {
            "timestamp": timestamp_unix,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "margin_level_pct": margin_level_pct,
        }

        if margin_level_pct <= self.stop_out_level_pct:
            print(f"SimBroker: MARGIN CALL (STOP OUT)! Margin Level: {margin_level_pct:.2f}% <= Stop Out Level: {self.stop_out_level_pct:.2f}%. Force liquidating positions.")
            self.trade_history.append({
                **log_event_common,
                "event_type": "MARGIN_CALL_STOP_OUT_TRIGGERED",
            })

            # Liquidate positions starting with the one with the largest loss
            while self.margin_used > 0 and ((self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')) <= self.stop_out_level_pct:
                if not self.open_positions:
                    break # No positions left to liquidate

                worst_pos_id = None
                largest_loss = float('inf') # Using float('inf') ensures any loss is smaller

                for pos_id, pos_data in self.open_positions.items():
                    # Ensure pos_data is treated as a dict for .get, or use Position attributes
                    current_pos_pnl = pos_data.get('profit_loss', 0.0)
                    if current_pos_pnl < largest_loss:
                        largest_loss = current_pos_pnl
                        worst_pos_id = pos_id

                if worst_pos_id:
                    # Retrieve the full Position object/dict to pass to _close_position_at_price
                    position_to_liquidate_data = self.open_positions[worst_pos_id]
                    # Assuming Position TypedDict is used for type hints but underlying storage is dict
                    # or that Position object itself is stored. For _close_position_at_price, it expects Position object.
                    # If self.open_positions stores dicts, we need to cast it
                    position_obj_to_liquidate = Position(**position_to_liquidate_data) if isinstance(position_to_liquidate_data, dict) else position_to_liquidate_data

                    symbol_to_liquidate = position_obj_to_liquidate.symbol # Use attribute access

                    print(f"SimBroker: Liquidating position {worst_pos_id} ({symbol_to_liquidate}) due to margin call. Current P/L: {largest_loss:.2f}")

                    close_price_for_liquidation = None
                    if symbol_to_liquidate in self.current_market_data and self.current_market_data[symbol_to_liquidate]:
                        bar = self.current_market_data[symbol_to_liquidate]
                        spread_amount = self._get_spread_in_price_terms(symbol_to_liquidate)
                        price_precision = self._get_price_precision(symbol_to_liquidate)
                        if position_obj_to_liquidate.side == OrderSide.BUY: # Closing a BUY by SELLING
                            close_price_for_liquidation = round(bar['close'] - (spread_amount / 2), price_precision) # at Bid
                        else: # Closing a SELL by BUYING
                            close_price_for_liquidation = round(bar['close'] + (spread_amount / 2), price_precision) # at Ask

                        self._close_position_at_price(position_obj_to_liquidate, close_price_for_liquidation, "MARGIN_CALL_LIQUIDATION")
                    else:
                        print(f"SimBroker ERROR: Market data unavailable for {symbol_to_liquidate} to liquidate {worst_pos_id}! Position remains for now (potential issue).")
                        self.trade_history.append({
                            "event_type": "MARGIN_CALL_LIQUIDATION_ERROR",
                            "timestamp": timestamp_unix, "position_id": worst_pos_id,
                            "reason": "Market data unavailable for liquidation price."})
                        break
                else:
                    if not self.open_positions: break
                    print("SimBroker: Margin call, but no clear 'worst loss' position or all profitable. Consider alternative liquidation order. Halting this cycle.")
                    # Fallback: close the first available position if no "worst loss" is found among multiple positions
                    if self.open_positions: # Check again if any positions are left
                        first_pos_id = list(self.open_positions.keys())[0]
                        position_to_liquidate_data = self.open_positions[first_pos_id]
                        position_obj_to_liquidate = Position(**position_to_liquidate_data) if isinstance(position_to_liquidate_data, dict) else position_to_liquidate_data
                        print(f"SimBroker: Fallback liquidation of position {first_pos_id} due to margin call.")
                        symbol_to_liquidate = position_obj_to_liquidate.symbol
                        if symbol_to_liquidate in self.current_market_data and self.current_market_data[symbol_to_liquidate]:
                            bar = self.current_market_data[symbol_to_liquidate]
                            spread_amount = self._get_spread_in_price_terms(symbol_to_liquidate)
                            price_precision = self._get_price_precision(symbol_to_liquidate)
                            if position_obj_to_liquidate.side == OrderSide.BUY:
                                close_price_for_liquidation = round(bar['close'] - (spread_amount / 2), price_precision)
                            else:
                                close_price_for_liquidation = round(bar['close'] + (spread_amount / 2), price_precision)
                            self._close_position_at_price(position_obj_to_liquidate, close_price_for_liquidation, "MARGIN_CALL_LIQUIDATION_FALLBACK")
                        else:
                            print(f"SimBroker ERROR: Market data also unavailable for fallback liquidation {first_pos_id}. Halting liquidation cycle.")
                            break
                    else: # Should be caught by the outer if not self.open_positions: break
                        break

                if self.margin_used == 0: break # All positions liquidated or margin freed sufficiently

            current_margin_level_after_liquidation = (self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')
            if current_margin_level_after_liquidation > self.stop_out_level_pct:
                 print(f"SimBroker: Margin level restored to {current_margin_level_after_liquidation:.2f}% after liquidations.")
                 self.trade_history.append({
                    "event_type": "MARGIN_CALL_RESOLVED", "timestamp": timestamp_unix,
                    "final_margin_level_pct": current_margin_level_after_liquidation })
            else:
                 print(f"SimBroker: Margin level at {current_margin_level_after_liquidation:.2f}% after liquidation attempts. Stop out may not be fully resolved if margin_used is still high.")


        elif margin_level_pct <= self.margin_call_warning_level_pct:
            print(f"SimBroker: MARGIN WARNING! Margin Level: {margin_level_pct:.2f}% (Warning Level: {self.margin_call_warning_level_pct:.2f}%)")
            self.trade_history.append({
                **log_event_common,
                "event_type": "MARGIN_WARNING_TRIGGERED",
            })

```
