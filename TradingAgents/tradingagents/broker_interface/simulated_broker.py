from typing import List, Dict, Optional, Any, Tuple
from TradingAgents.tradingagents.broker_interface.base import BrokerInterface
from TradingAgents.tradingagents.forex_utils.forex_states import (
    Tick, Candlestick, AccountInfo, OrderResponse, Position,
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
        self.pending_orders: Dict[str, Dict[str, Any]] = {}
        self.trade_history: List[Dict] = []

        self.order_fill_logic: str = "CURRENT_BAR_CLOSE"
        self.base_slippage_pips: float = 0.2
        self.volume_slippage_factor_pips_per_million: float = 0.1

        self.current_market_data: Dict[str, Candlestick] = {}

        self.default_spread_pips: Dict[str, float] = {
            "EURUSD": 0.5, "GBPUSD": 0.6, "USDJPY": 0.5, "AUDUSD": 0.7, "USDCAD": 0.7, "XAUUSD": 2.0, "default": 1.0
        }
        self.leverage: int = 100
        self.margin_used: float = 0.0
        self.account_currency = "USD"
        self.margin_call_warning_level_pct = 100.0
        self.stop_out_level_pct = 50.0
        self.test_data_store: Dict[str, List[Dict]] = {}

        self.commission_per_lot: Dict[str, float] = {
            "EURUSD": 7.0, "GBPUSD": 7.0, "USDJPY": 7.0, "AUDUSD": 7.0, "USDCAD": 7.0, "XAUUSD": 7.0, "default": 7.0
        }

        print(f"SimulatedBroker initialized. Capital: {initial_capital}, Base Slippage: {self.base_slippage_pips} pips, Volume Slippage Factor: {self.volume_slippage_factor_pips_per_million} pips/million, Leverage: {self.leverage}:1, Account Currency: {self.account_currency}, Margin Warning: {self.margin_call_warning_level_pct}%, Stop Out: {self.stop_out_level_pct}%")

    def load_test_data(self, symbol: str, data_sequence: List[Dict[str, Any]]):
        validated_data_sequence: List[Candlestick] = []
        for idx, bar_data in enumerate(data_sequence):
            is_valid = True
            required_keys = ['timestamp', 'open', 'high', 'low', 'close']
            for key in required_keys:
                if key not in bar_data:
                    print(f"SimBroker WARNING: Bar {idx} for {symbol} missing required key '{key}'. Skipping bar.")
                    is_valid = False
                    break
                if key == 'timestamp' and not bar_data[key] > 0:
                    print(f"SimBroker WARNING: Bar {idx} for {symbol} has invalid timestamp {bar_data[key]}. Must be positive. Skipping bar.")
                    is_valid = False
                    break
                if key in ['open', 'high', 'low', 'close'] and not bar_data[key] > 0:
                    print(f"SimBroker WARNING: Bar {idx} for {symbol} has non-positive OHLC value for '{key}': {bar_data[key]}. Skipping bar.")
                    is_valid = False
                    break

            if not is_valid:
                continue

            candlestick_entry: Candlestick = {
                "timestamp": float(bar_data["timestamp"]),
                "open": float(bar_data["open"]),
                "high": float(bar_data["high"]),
                "low": float(bar_data["low"]),
                "close": float(bar_data["close"]),
                "volume": float(bar_data["volume"]) if bar_data.get("volume") is not None else None,
                "bid_close": float(bar_data["bid_close"]) if bar_data.get("bid_close") is not None else None,
                "ask_close": float(bar_data["ask_close"]) if bar_data.get("ask_close") is not None else None,
            }

            if candlestick_entry["bid_close"] is not None and candlestick_entry["bid_close"] <= 0:
                print(f"SimBroker WARNING: Bar {idx} for {symbol} has non-positive bid_close {candlestick_entry['bid_close']}. Storing as None.")
                candlestick_entry["bid_close"] = None
            if candlestick_entry["ask_close"] is not None and candlestick_entry["ask_close"] <= 0:
                print(f"SimBroker WARNING: Bar {idx} for {symbol} has non-positive ask_close {candlestick_entry['ask_close']}. Storing as None.")
                candlestick_entry["ask_close"] = None

            if candlestick_entry["bid_close"] is not None and candlestick_entry["ask_close"] is not None and candlestick_entry["bid_close"] > candlestick_entry["ask_close"]:
                print(f"SimBroker WARNING: Bar {idx} for {symbol} has bid_close ({candlestick_entry['bid_close']}) > ask_close ({candlestick_entry['ask_close']}). Data might be suspect. Still loading.")

            validated_data_sequence.append(candlestick_entry)

        print(f"SimBroker: Loaded {len(validated_data_sequence)} (out of {len(data_sequence)} provided) bars of test data for {symbol.upper()} after validation.")
        self.test_data_store[symbol.upper()] = validated_data_sequence

    def load_tick_data(self, symbol: str, tick_data: List[Dict]):
        print(f"SimBroker: load_tick_data called for {symbol} with {len(tick_data)} ticks. Tick data loading not yet fully implemented.")

    def _generate_unique_id(self) -> str:
        return str(uuid.uuid4())

    def _get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        symbol_upper = symbol.upper()
        contract_size_units = 100000.0
        info = None
        if len(symbol_upper) == 6 and symbol_upper.isalnum():
            base = symbol_upper[:3]
            quote = symbol_upper[3:]
            if "JPY" == quote:
                info = {"base_currency": base, "quote_currency": quote, "price_precision": 3, "point_size": 0.001, "pip_definition": 0.01, "contract_size_units": contract_size_units}
            else:
                info = {"base_currency": base, "quote_currency": quote, "price_precision": 5, "point_size": 0.00001, "pip_definition": 0.0001, "contract_size_units": contract_size_units}
        elif symbol_upper in ["XAUUSD", "GOLD"]:
            info = {"base_currency": "XAU", "quote_currency": "USD", "price_precision": 2, "point_size": 0.01, "pip_definition": 0.1, "contract_size_units": 100.0}

        if info: return info
        else:
            print(f"SimBroker._get_symbol_info: Symbol info not explicitly configured for '{symbol_upper}'. Attempting generic parsing or default.")
            if len(symbol_upper) == 6 and symbol_upper.isalnum():
                base = symbol_upper[:3]; quote = symbol_upper[3:]
                return {"base_currency": base, "quote_currency": quote, "price_precision": 5, "point_size": 0.00001, "pip_definition": 0.0001, "contract_size_units": contract_size_units}
            print(f"SimBroker._get_symbol_info: Could not determine info for '{symbol_upper}'. Returning None.")
            return None

    def _get_point_size(self, symbol: str) -> float:
        info = self._get_symbol_info(symbol)
        return info["point_size"] if info else 0.00001

    def _get_price_precision(self, symbol: str) -> int:
        info = self._get_symbol_info(symbol)
        return info["price_precision"] if info else 5

    def _get_pip_value_for_sl_tp(self, symbol: str) -> float:
        info = self._get_symbol_info(symbol)
        return info["pip_definition"] if info and "pip_definition" in info else (0.01 if "JPY" in symbol.upper() else 0.0001)

    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        from_curr = from_currency.upper(); to_curr = to_currency.upper()
        if from_curr == to_curr: return 1.0
        if not self.current_market_data:
            print(f"SimBroker._get_exchange_rate: current_market_data is not populated. Cannot get rate for {from_curr}/{to_curr}.")
            return None

        def get_pair_close_price(symbol: str) -> Optional[float]:
            symbol_upper = symbol.upper()
            if symbol_upper in self.current_market_data and self.current_market_data[symbol_upper]:
                close_price = self.current_market_data[symbol_upper].get('close')
                if close_price is not None:
                    try: return float(close_price)
                    except ValueError: print(f"SimBroker._get_exchange_rate: Could not convert close_price '{close_price}' to float for {symbol_upper}."); return None
            return None

        direct_pair_symbol = f"{from_curr}{to_curr}"; rate = get_pair_close_price(direct_pair_symbol)
        if rate is not None: return rate
        inverse_pair_symbol = f"{to_curr}{from_curr}"; inverse_rate = get_pair_close_price(inverse_pair_symbol)
        if inverse_rate is not None:
            if inverse_rate == 0: print(f"SimBroker._get_exchange_rate: Inverse rate for {inverse_pair_symbol} is zero, cannot divide."); return None
            return 1.0 / inverse_rate
        elif inverse_rate == 0: print(f"SimBroker._get_exchange_rate: Inverse rate for {inverse_pair_symbol} is zero (or data error), cannot divide.")

        intermediary_curr = self.account_currency.upper()
        if from_curr != intermediary_curr and to_curr != intermediary_curr:
            from_curr_to_intermediary_rate = self._get_exchange_rate(from_curr, intermediary_curr)
            to_curr_to_intermediary_rate = self._get_exchange_rate(to_curr, intermediary_curr)
            if from_curr_to_intermediary_rate is not None and to_curr_to_intermediary_rate is not None:
                if to_curr_to_intermediary_rate == 0: print(f"SimBroker._get_exchange_rate: Triangulation Path A failed for {from_curr}/{to_curr}. Divisor (TO/{intermediary_curr}) is zero.")
                else: return from_curr_to_intermediary_rate / to_curr_to_intermediary_rate
        print(f"SimBroker._get_exchange_rate: Exchange rate for {from_curr}/{to_curr} could not be determined..."); return None

    def calculate_pip_value_in_account_currency(self, symbol: str, volume_lots: float) -> Optional[float]:
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info: print(f"SimBroker.calculate_pip_value: Could not get symbol info for {symbol}."); return None
        pip_definition_in_price_terms = symbol_info['pip_definition']; quote_currency = symbol_info['quote_currency']; contract_size = symbol_info['contract_size_units']
        value_of_one_pip_in_quote_currency = pip_definition_in_price_terms * contract_size * volume_lots
        if quote_currency == self.account_currency: return value_of_one_pip_in_quote_currency
        else:
            exchange_rate = self._get_exchange_rate(quote_currency, self.account_currency)
            if exchange_rate is None: print(f"SimBroker.calculate_pip_value: Failed to get exchange rate for {quote_currency} to {self.account_currency} for symbol {symbol}..."); return None
            return value_of_one_pip_in_quote_currency * exchange_rate

    def calculate_pnl_in_account_currency(self, symbol: str, side: OrderSide, volume_lots: float, entry_price: float, close_price: float) -> Optional[float]:
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info: print(f"SimBroker.calculate_pnl: Could not get symbol info for {symbol}."); return None
        pip_definition_val = symbol_info['pip_definition']
        if pip_definition_val == 0: print(f"SimBroker.calculate_pnl: Pip definition for {symbol} is zero..."); return None
        price_difference = (close_price - entry_price) if side == OrderSide.BUY else (entry_price - close_price)
        pips_moved = price_difference / pip_definition_val
        value_of_one_pip_for_one_lot_in_acct_curr = self.calculate_pip_value_in_account_currency(symbol, 1.0)
        if value_of_one_pip_for_one_lot_in_acct_curr is None: print(f"SimBroker.calculate_pnl: Could not calculate pip value for {symbol}."); return None
        total_pnl = pips_moved * value_of_one_pip_for_one_lot_in_acct_curr * volume_lots
        return total_pnl

    def _get_spread_in_price_terms(self, symbol: str) -> float:
        symbol_upper = symbol.upper(); current_bar_for_symbol = self.current_market_data.get(symbol_upper)
        if current_bar_for_symbol:
            hist_bid_val = current_bar_for_symbol.get('bid_close'); hist_ask_val = current_bar_for_symbol.get('ask_close')
            hist_bid: Optional[float] = float(hist_bid_val) if hist_bid_val is not None else None
            hist_ask: Optional[float] = float(hist_ask_val) if hist_ask_val is not None else None
            if hist_bid is not None and hist_ask is not None and hist_ask > hist_bid: return hist_ask - hist_bid
        symbol_info = self._get_symbol_info(symbol_upper)
        if not symbol_info: print(f"SimBroker._get_spread_in_price_terms: Could not get symbol info for {symbol_upper}..."); return 0.0
        configured_pips = self.default_spread_pips.get(symbol_upper, self.default_spread_pips.get("default", 1.0))
        pip_definition_for_symbol = symbol_info['pip_definition']
        return configured_pips * pip_definition_for_symbol

    def _calculate_commission(self, symbol: str, volume_lots: float) -> float:
        return self.commission_per_lot.get(symbol.upper(), self.commission_per_lot.get("default", 7.0)) * volume_lots

    def _calculate_margin_required(self, symbol: str, volume_lots: float, entry_price: float) -> float:
        symbol_info = self._get_symbol_info(symbol)
        contract_size = symbol_info['contract_size_units'] if symbol_info and 'contract_size_units' in symbol_info else 100000.0

        notional_value_in_quote_currency = volume_lots * contract_size * entry_price
        base_currency = symbol_info['base_currency'] if symbol_info else ""
        quote_currency = symbol_info['quote_currency'] if symbol_info else ""

        if not symbol_info:
            print(f"SimBroker._calculate_margin_required: Symbol info for {symbol} not found. Margin might be inaccurate.")
            return (volume_lots * contract_size * entry_price) / self.leverage

        margin_in_base_currency_units = (volume_lots * contract_size) / self.leverage
        if base_currency == self.account_currency: return margin_in_base_currency_units

        exchange_rate_base_to_account = self._get_exchange_rate(base_currency, self.account_currency)
        if exchange_rate_base_to_account is None:
            print(f"SimBroker._calculate_margin_required: Could not get exchange rate {base_currency}{self.account_currency} for margin calc of {symbol}. Using simplified margin.")
            if quote_currency == self.account_currency: return notional_value_in_quote_currency / self.leverage
            rate_quote_to_acc = self._get_exchange_rate(quote_currency, self.account_currency)
            return (notional_value_in_quote_currency / self.leverage) * rate_quote_to_acc if rate_quote_to_acc else (notional_value_in_quote_currency / self.leverage)
        return margin_in_base_currency_units * exchange_rate_base_to_account

    def update_current_time(self, simulated_time_unix: float): self.current_simulated_time_unix = simulated_time_unix
    def update_market_data(self, market_data: Dict[str, Candlestick]): self.current_market_data = market_data; self._update_equity_and_margin()
    def connect(self, credentials: Dict[str, Any]) -> bool: self._connected = True; return True
    def disconnect(self) -> None: self._connected = False
    def is_connected(self) -> bool: return self._connected

    def get_current_price(self, symbol: str) -> Optional[Tick]:
        symbol_upper = symbol.upper(); current_bar = self.current_market_data.get(symbol_upper); precision = self._get_price_precision(symbol_upper); timestamp_to_use = self.current_simulated_time_unix
        if not current_bar:
            if symbol_upper == "EURUSD": base_close_for_fallback = 1.08500
            elif symbol_upper == "GBPUSD": base_close_for_fallback = 1.27100
            else: print(f"SimBroker: No current bar data or fallback static price for {symbol_upper}."); return None
            spread_from_default_pips = self.default_spread_pips.get(symbol_upper, self.default_spread_pips.get("default", 1.0))
            pip_definition_val = self._get_pip_value_for_sl_tp(symbol_upper)
            spread_amount_price_terms = spread_from_default_pips * pip_definition_val
            bid_price = round(base_close_for_fallback - (spread_amount_price_terms / 2.0), precision)
            ask_price = round(base_close_for_fallback + (spread_amount_price_terms / 2.0), precision)
            return Tick(symbol=symbol_upper, timestamp=timestamp_to_use, bid=bid_price, ask=ask_price, last=base_close_for_fallback, volume=None)

        hist_bid_close_val = current_bar.get('bid_close'); hist_ask_close_val = current_bar.get('ask_close')
        hist_bid_close: Optional[float] = float(hist_bid_close_val) if hist_bid_close_val is not None else None
        hist_ask_close: Optional[float] = float(hist_ask_close_val) if hist_ask_close_val is not None else None
        bar_close_price = float(current_bar['close'])
        current_volume = current_bar.get('volume')

        if hist_bid_close is not None and hist_ask_close is not None and hist_ask_close > hist_bid_close:
            return Tick(symbol=symbol_upper, timestamp=timestamp_to_use, bid=round(hist_bid_close, precision), ask=round(hist_ask_close, precision), last=bar_close_price, volume=current_volume)
        else:
            spread_amount = self._get_spread_in_price_terms(symbol_upper)
            bid_price = round(bar_close_price - (spread_amount / 2.0), precision)
            ask_price = round(bar_close_price + (spread_amount / 2.0), precision)
            return Tick(symbol=symbol_upper, timestamp=timestamp_to_use, bid=bid_price, ask=ask_price, last=bar_close_price, volume=current_volume)

    def get_historical_data(self, symbol: str, timeframe_str: str, start_time_unix: float, end_time_unix: Optional[float] = None, count: Optional[int] = None) -> List[Dict]:
            symbol_upper = symbol.upper()
            effective_end_time_unix = min(end_time_unix if end_time_unix is not None else self.current_simulated_time_unix, self.current_simulated_time_unix)
            print(f"SimBroker: get_historical_data({symbol_upper}, TF:{timeframe_str}) requested range: {datetime.datetime.fromtimestamp(start_time_unix, tz=datetime.timezone.utc).isoformat()} to {datetime.datetime.fromtimestamp(effective_end_time_unix, tz=datetime.timezone.utc).isoformat()}. Current sim time: {datetime.datetime.fromtimestamp(self.current_simulated_time_unix, tz=datetime.timezone.utc).isoformat()}")
            if symbol_upper in self.test_data_store:
                all_bars_for_symbol = self.test_data_store[symbol_upper]
                relevant_bars = [Candlestick(**bar) for bar in all_bars_for_symbol if bar['timestamp'] >= start_time_unix and bar['timestamp'] <= effective_end_time_unix]
                if count is not None and len(relevant_bars) > count: relevant_bars = relevant_bars[-count:]
                print(f"SimBroker: Returning {len(relevant_bars)} bars from test_data_store for {symbol_upper}."); return relevant_bars
            else:
                print(f"SimBroker: No test_data_store for {symbol_upper}. Generating dummy historical data.")
                dummy_bars_generated: List[Candlestick] = []; time_step_seconds = self._get_timeframe_seconds_approx(timeframe_str)
                if count is not None: num_to_gen = count; current_bar_open_time_for_dummy = effective_end_time_unix - time_step_seconds
                else:
                    if effective_end_time_unix < start_time_unix: return []
                    num_to_gen = int((effective_end_time_unix - start_time_unix) / time_step_seconds); current_bar_open_time_for_dummy = effective_end_time_unix - time_step_seconds
                for i in range(num_to_gen):
                    bar_open_timestamp = current_bar_open_time_for_dummy - (i * time_step_seconds)
                    if bar_open_timestamp < start_time_unix: continue
                    idx_from_oldest = num_to_gen - 1 - i; base_price = 1.0700 + (idx_from_oldest * 0.0001)
                    if "JPY" in symbol_upper: base_price = 150.00 + (idx_from_oldest * 0.01)
                    elif "XAU" in symbol_upper: base_price = 2300.00 + (idx_from_oldest * 0.1)
                    precision = self._get_price_precision(symbol_upper); point = self._get_point_size(symbol_upper) * 10
                    open_val = round(base_price + random.uniform(-point, point), precision); close_val = round(base_price + random.uniform(-point, point), precision)
                    high_val = round(max(open_val, close_val) + random.uniform(0, point*2), precision); low_val = round(min(open_val, close_val) - random.uniform(0, point*2), precision)
                    dummy_bars_generated.append(Candlestick(timestamp=bar_open_timestamp, open=open_val, high=high_val, low=low_val, close=close_val, volume=float(random.randint(500,2000) + idx_from_oldest)))
                dummy_bars_generated.sort(key=lambda x: x['timestamp'])
                final_dummy_bars = [b for b in dummy_bars_generated if b['timestamp'] >= start_time_unix and b['timestamp'] < effective_end_time_unix]
                print(f"SimBroker: Generated and returning {len(final_dummy_bars)} dummy bars for {symbol_upper}."); return final_dummy_bars

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60
        elif "M5" == timeframe_str: return 5 * 60
        elif "M15" == timeframe_str: return 15 * 60
        elif "M30" == timeframe_str: return 30 * 60
        elif "H1" == timeframe_str: return 60 * 60
        elif "H4" == timeframe_str: return 4 * 60 * 60
        elif "D1" == timeframe_str: return 24 * 60 * 60
        elif "W1" == timeframe_str: return 7 * 24 * 60 * 60
        elif "MN1" == timeframe_str: return 30 * 24 * 60 * 60
        return 60 * 60 # Default to 1 hour if not matched

    def get_account_info(self) -> Optional[AccountInfo]:
        if not self.is_connected(): return None
        free_margin = self.equity - self.margin_used
        margin_level = (self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')
        return AccountInfo(account_id=self._generate_unique_id()[:8], balance=round(self.balance, 2), equity=round(self.equity, 2), margin=round(self.margin_used, 2), free_margin=round(free_margin, 2), margin_level=round(margin_level, 2) if margin_level != float('inf') else float('inf'), currency=self.account_currency)

    def place_order(self, symbol: str, order_type: OrderType, side: OrderSide, volume: float, price: Optional[float] = None, stop_loss: Optional[float] = None, take_profit: Optional[float] = None, time_in_force: TimeInForce = TimeInForce.GTC, magic_number: Optional[int] = 0, comment: Optional[str] = "") -> OrderResponse:
        order_id = self._generate_unique_id(); timestamp_unix = self.current_simulated_time_unix
        if not self.is_connected(): return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Broker not connected.")
        current_bar = self.current_market_data.get(symbol)
        if not current_bar: return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message=f"Market data not available for {symbol} at {datetime.datetime.fromtimestamp(timestamp_unix, tz=datetime.timezone.utc).isoformat()}.")
        price_precision = self._get_price_precision(symbol)

        if order_type == OrderType.MARKET:
            hist_bid_close: Optional[float] = current_bar.get('bid_close'); hist_ask_close: Optional[float] = current_bar.get('ask_close')
            fill_price_base_for_slippage: float; market_open_for_trade = False
            if side == OrderSide.BUY:
                if hist_ask_close is not None and hist_ask_close > 0: fill_price_base_for_slippage = hist_ask_close; market_open_for_trade = True
                else: spread_amount = self._get_spread_in_price_terms(symbol); fill_price_base_for_slippage = float(current_bar['close']) + (spread_amount / 2.0); market_open_for_trade = True
            elif side == OrderSide.SELL:
                if hist_bid_close is not None and hist_bid_close > 0: fill_price_base_for_slippage = hist_bid_close; market_open_for_trade = True
                else: spread_amount = self._get_spread_in_price_terms(symbol); fill_price_base_for_slippage = float(current_bar['close']) - (spread_amount / 2.0); market_open_for_trade = True
            else: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Invalid order side.")
            if not market_open_for_trade: return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message=f"Market closed or data issue for {symbol} (no valid fill base price).")

            symbol_info = self._get_symbol_info(symbol)
            contract_size = symbol_info['contract_size_units'] if symbol_info and 'contract_size_units' in symbol_info else 100000.0
            volume_in_base_currency_units = volume * contract_size; volume_in_millions = volume_in_base_currency_units / 1_000_000.0
            dynamic_slippage_pips = volume_in_millions * self.volume_slippage_factor_pips_per_million
            total_slippage_pips = self.base_slippage_pips + dynamic_slippage_pips
            final_slippage_pips = total_slippage_pips * random.uniform(0.8, 1.2); final_slippage_pips = max(0, final_slippage_pips)
            pip_definition_val = self._get_pip_value_for_sl_tp(symbol)
            slippage_amount_in_price_terms = final_slippage_pips * pip_definition_val

            entry_price_final: float
            if side == OrderSide.BUY: entry_price_final = round(fill_price_base_for_slippage + slippage_amount_in_price_terms, price_precision)
            else: entry_price_final = round(fill_price_base_for_slippage - slippage_amount_in_price_terms, price_precision)

            margin_for_this_trade = self._calculate_margin_required(symbol, volume, entry_price_final)
            self._update_equity_and_margin()
            free_margin = self.equity - self.margin_used
            if free_margin < margin_for_this_trade: return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=entry_price_final, timestamp=timestamp_unix, error_message=f"Insufficient free margin. Need: {margin_for_this_trade:.2f}, Have: {free_margin:.2f}")

            commission_cost = self._calculate_commission(symbol, volume); position_id = self._generate_unique_id()
            new_position = Position(position_id=position_id, symbol=symbol, side=side, volume=volume, entry_price=entry_price_final, current_price=entry_price_final, profit_loss= -commission_cost, stop_loss=stop_loss, take_profit=take_profit, open_time=timestamp_unix, magic_number=magic_number, comment=comment)
            self.open_positions[position_id] = new_position; self.balance -= commission_cost; self.margin_used += margin_for_this_trade
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
                hist_bid_close: Optional[float] = bar.get('bid_close'); hist_ask_close: Optional[float] = bar.get('ask_close')
                pip_definition_val = self._get_pip_value_for_sl_tp(symbol)
                slippage_for_stop_order_price_terms = 0.0
                if order_type == OrderType.STOP:
                    symbol_info = self._get_symbol_info(symbol)
                    contract_size = symbol_info['contract_size_units'] if symbol_info and 'contract_size_units' in symbol_info else 100000.0
                    volume_in_base_currency_units = order_volume * contract_size
                    volume_in_millions = volume_in_base_currency_units / 1_000_000.0
                    dynamic_slippage_pips = volume_in_millions * self.volume_slippage_factor_pips_per_million
                    total_slippage_pips = self.base_slippage_pips + dynamic_slippage_pips
                    final_slippage_pips = total_slippage_pips * random.uniform(0.8, 1.2); final_slippage_pips = max(0, final_slippage_pips)
                    slippage_for_stop_order_price_terms = final_slippage_pips * pip_definition_val

                base_price_for_execution: float; actual_fill_price: float
                if order_side == OrderSide.BUY:
                    if hist_ask_close is not None and hist_ask_close > 0: base_price_for_execution = hist_ask_close
                    else: spread_for_fill = self._get_spread_in_price_terms(symbol); base_price_for_execution = fill_price_sim + (spread_for_fill / 2.0)
                    if order_type == OrderType.STOP: actual_fill_price = base_price_for_execution + slippage_for_stop_order_price_terms
                    elif order_type == OrderType.LIMIT: actual_fill_price = min(order_price, base_price_for_execution)
                    else: actual_fill_price = base_price_for_execution
                else: # OrderSide.SELL
                    if hist_bid_close is not None and hist_bid_close > 0: base_price_for_execution = hist_bid_close
                    else: spread_for_fill = self._get_spread_in_price_terms(symbol); base_price_for_execution = fill_price_sim - (spread_for_fill / 2.0)
                    if order_type == OrderType.STOP: actual_fill_price = base_price_for_execution - slippage_for_stop_order_price_terms
                    elif order_type == OrderType.LIMIT: actual_fill_price = max(order_price, base_price_for_execution)
                    else: actual_fill_price = base_price_for_execution

                actual_fill_price = round(actual_fill_price, precision)
                print(f"SimBroker: Pending order {order_id} ({symbol} {order_side.value} {order_type.value} @ {order_price}) TRIGGERED. Fill Price Sim: {fill_price_sim:.{precision}f}. Base for Exec: {base_price_for_execution:.{precision}f}. Final Fill: {actual_fill_price:.{precision}f}")
                ts_unix = self.current_simulated_time_unix
                margin_req = self._calculate_margin_required(symbol, order_volume, actual_fill_price)
                self._update_equity_and_margin()
                free_margin = self.equity - self.margin_used
                if free_margin < margin_req:
                    print(f"SimBroker: Insufficient margin for pending {order_id}. Need: {margin_req:.2f}, Have: {free_margin:.2f}. Removed.")
                    self.trade_history.append({"event_type": "PENDING_ORDER_FAIL_MARGIN", "timestamp": ts_unix, "order_id": order_id, "symbol": symbol, "side": order_side.value, "volume": order_volume, "trigger_price": fill_price_sim, "reason": "Insufficient margin"})
                    orders_to_remove_after_processing.append(order_id); continue
                commission = self._calculate_commission(symbol, order_volume); pos_id = self._generate_unique_id()
                new_pos = Position(position_id=pos_id, symbol=symbol, side=order_side, volume=order_volume, entry_price=actual_fill_price, current_price=actual_fill_price, profit_loss= -commission, stop_loss=sl_pos, take_profit=tp_pos, open_time=ts_unix, magic_number=magic_pos, comment=comment_pos)
                self.open_positions[pos_id] = new_pos; self.balance -= commission; self.margin_used += margin_req
                self._update_equity_and_margin()
                self.trade_history.append({"event_type": "PENDING_ORDER_FILLED", "timestamp": ts_unix, "original_order_id": order_id, "position_id": pos_id, "symbol": symbol, "side": order_side.value, "type": order_type.value, "volume": order_volume, "requested_price": order_price, "fill_price": actual_fill_price, "sl": sl_pos, "tp": tp_pos, "commission": commission, "comment": comment_pos})
                print(f"SimBroker: Pending order {order_id} FILLED. New PosID: {pos_id} for {symbol} {order_side.value} {order_volume} @ {actual_fill_price}. Comm: {commission:.2f}")
                orders_to_remove_after_processing.append(order_id)
        for oid in orders_to_remove_after_processing:
            if oid in self.pending_orders: del self.pending_orders[oid]

    def _update_equity_and_margin(self):
        current_total_unrealized_pnl = 0.0; current_total_margin_used = 0.0
        for pos_id, pos in list(self.open_positions.items()): # pos is a Position (dict)
            symbol_info = self._get_symbol_info(pos['symbol'])
            if not symbol_info:
                print(f"SimBroker._update_equity_and_margin: Missing symbol info for {pos['symbol']}, cannot update P/L accurately.")
                current_total_unrealized_pnl += pos.get('profit_loss', 0.0)
                current_total_margin_used += self._calculate_margin_required(pos['symbol'], pos['volume'], pos['entry_price'])
                continue
            current_bar = self.current_market_data.get(pos['symbol'])
            if not current_bar:
                current_total_unrealized_pnl += pos.get('profit_loss', 0.0)
                current_total_margin_used += self._calculate_margin_required(pos['symbol'], pos['volume'], pos['entry_price'])
                continue

            market_close_price = current_bar['close']; spread_amount_for_symbol = self._get_spread_in_price_terms(pos['symbol']); price_precision = symbol_info['price_precision']
            valuation_price: float
            if pos['side'] == OrderSide.BUY: valuation_price = round(market_close_price - (spread_amount_for_symbol / 2), price_precision)
            else: valuation_price = round(market_close_price + (spread_amount_for_symbol / 2), price_precision)

            unrealized_pnl_for_pos = self.calculate_pnl_in_account_currency(pos['symbol'], pos['side'], pos['volume'], pos['entry_price'], valuation_price)
            if unrealized_pnl_for_pos is not None:
                self.open_positions[pos_id]['profit_loss'] = unrealized_pnl_for_pos
                self.open_positions[pos_id]['current_price'] = valuation_price
                current_total_unrealized_pnl += unrealized_pnl_for_pos
            else:
                print(f"SimBroker._update_equity_and_margin: PNL calculation failed for {pos['symbol']} pos {pos_id}. Using last known PNL.")
                current_total_unrealized_pnl += pos.get('profit_loss', 0.0)

            margin_for_pos = self._calculate_margin_required(pos['symbol'], pos['volume'], pos['entry_price'])
            current_total_margin_used += margin_for_pos
        self.equity = self.balance + current_total_unrealized_pnl; self.margin_used = current_total_margin_used

    def modify_order(self, order_id: str, new_price: Optional[float] = None, new_stop_loss: Optional[float] = None, new_take_profit: Optional[float] = None) -> OrderResponse:
        ts = self.current_simulated_time_unix
        if order_id in self.open_positions:
            pos = self.open_positions[order_id] # pos is a dict (Position)
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

    def _close_position_at_price(self, position_dict: Position, close_price: float, reason: str): # position_dict is a Position (dict)
        current_position_id = position_dict['position_id']
        if current_position_id not in self.open_positions:
            print(f"SimBroker: Position {current_position_id} already actioned or does not exist. Cannot close for reason: {reason}.")
            return
        realized_pnl = self.calculate_pnl_in_account_currency(position_dict['symbol'], position_dict['side'], position_dict['volume'], position_dict['entry_price'], close_price)
        if realized_pnl is None:
            print(f"SimBroker: PNL calculation failed for closing pos {current_position_id} ({position_dict['symbol']}). Realized PNL recorded as 0.0. Position will still be closed.")
            realized_pnl = 0.0
        self.balance += realized_pnl
        margin_freed = self._calculate_margin_required(position_dict['symbol'], position_dict['volume'], position_dict['entry_price'])
        self.margin_used -= margin_freed
        if self.margin_used < 0: self.margin_used = 0
        open_time_log = position_dict.get('open_time', self.current_simulated_time_unix); comment_log = position_dict.get('comment', ""); magic_log = position_dict.get('magic_number', 0)
        self.trade_history.append({"event_type": "POSITION_CLOSED", "timestamp": self.current_simulated_time_unix, "position_id": current_position_id, "symbol": position_dict['symbol'], "side": position_dict['side'].value, "volume": position_dict['volume'], "entry_price": position_dict['entry_price'], "open_time": open_time_log, "close_price": close_price, "realized_pnl": realized_pnl, "reason_for_close": reason, "magic_number": magic_log, "comment": comment_log})
        del self.open_positions[current_position_id]
        print(f"SimBroker: Position {current_position_id} ({position_dict['symbol']} {position_dict['side'].value} {position_dict['volume']} lot(s)) CLOSED at {close_price} by {reason}. P/L: {realized_pnl:.2f}. Margin Freed: {margin_freed:.2f}")
        self._update_equity_and_margin()

    def check_for_sl_tp_triggers(self):
        if not self.current_market_data or not self.current_simulated_time_unix: return
        positions_to_action = []
        for pos_id, pos in list(self.open_positions.items()): # pos is a Position (dict)
            if pos['symbol'] not in self.current_market_data: continue
            bar = self.current_market_data[pos['symbol']]
            trigger_price = None; reason = None
            if pos['side'] == OrderSide.BUY:
                if pos['stop_loss'] is not None and bar['low'] <= pos['stop_loss']: trigger_price, reason = pos['stop_loss'], "STOP_LOSS_HIT"
                elif pos['take_profit'] is not None and bar['high'] >= pos['take_profit']: trigger_price, reason = pos['take_profit'], "TAKE_PROFIT_HIT"
            elif pos['side'] == OrderSide.SELL:
                if pos['stop_loss'] is not None and bar['high'] >= pos['stop_loss']: trigger_price, reason = pos['stop_loss'], "STOP_LOSS_HIT"
                elif pos['take_profit'] is not None and bar['low'] <= pos['take_profit']: trigger_price, reason = pos['take_profit'], "TAKE_PROFIT_HIT"
            if trigger_price is not None: positions_to_action.append({"position_to_close": pos, "close_price": trigger_price, "reason": reason})
        for item in positions_to_action: self._close_position_at_price(item["position_to_close"], item["close_price"], item["reason"])

    def close_order(self, order_id: str, volume: Optional[float] = None, price: Optional[float] = None) -> OrderResponse:
        if order_id not in self.open_positions: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Position not found.")
        pos_to_close_dict = self.open_positions[order_id] # It's already a dict (Position)
        current_bar = self.current_market_data.get(pos_to_close_dict['symbol'])
        if not current_bar: return OrderResponse(order_id=order_id, status="REJECTED", error_message="Market data unavailable.")
        close_price_to_use = price
        if close_price_to_use is None:
            spread_amount = self._get_spread_in_price_terms(pos_to_close_dict['symbol'])
            close_price_base = current_bar['close']
            close_price_to_use = (close_price_base - spread_amount / 2) if pos_to_close_dict['side'] == OrderSide.BUY else (close_price_base + spread_amount / 2)
            close_price_to_use = round(close_price_to_use, self._get_price_precision(pos_to_close_dict['symbol']))
        self._close_position_at_price(pos_to_close_dict, close_price_to_use, "CLOSED_BY_REQUEST")
        return OrderResponse(order_id=order_id, status="CLOSED", symbol=pos_to_close_dict['symbol'], side=pos_to_close_dict['side'], type=OrderType.MARKET, volume=pos_to_close_dict['volume'], price=close_price_to_use, timestamp=self.current_simulated_time_unix, position_id=order_id)

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        self._update_equity_and_margin()
        return [pos_data for pos_data in self.open_positions.values() if symbol is None or pos_data['symbol'] == symbol]

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        return [OrderResponse(**order_data) for order_data in self.pending_orders.values() if symbol is None or order_data['symbol'] == symbol]

    def check_for_margin_call(self):
        if self.margin_used == 0: return
        margin_level_pct = (self.equity / self.margin_used) * 100 if self.margin_used > 0 else float('inf')
        timestamp_unix = self.current_simulated_time_unix
        log_event_common = {"timestamp": timestamp_unix, "equity": self.equity, "margin_used": self.margin_used, "margin_level_pct": margin_level_pct}

        if margin_level_pct <= self.stop_out_level_pct:
            print(f"SimBroker: MARGIN CALL (STOP OUT)! Margin Level: {margin_level_pct:.2f}% <= Stop Out Level: {self.stop_out_level_pct:.2f}%. Force liquidating positions.")
            self.trade_history.append({**log_event_common, "event_type": "MARGIN_CALL_STOP_OUT_TRIGGERED"})
            while self.margin_used > 0 and ((self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')) <= self.stop_out_level_pct:
                if not self.open_positions: break
                worst_pos_id = None; largest_loss = float('inf')
                for pos_id, pos_data in self.open_positions.items(): # pos_data is a Position dict
                    current_pos_pnl = pos_data.get('profit_loss', 0.0)
                    if current_pos_pnl < largest_loss: largest_loss = current_pos_pnl; worst_pos_id = pos_id

                if worst_pos_id:
                    position_dict_to_liquidate = self.open_positions[worst_pos_id] # Already a dict
                    symbol_to_liquidate = position_dict_to_liquidate['symbol']
                    print(f"SimBroker: Liquidating position {worst_pos_id} ({symbol_to_liquidate}) due to margin call. Current P/L: {largest_loss:.2f}")
                    close_price_for_liquidation = None
                    if symbol_to_liquidate in self.current_market_data and self.current_market_data[symbol_to_liquidate]:
                        bar = self.current_market_data[symbol_to_liquidate]; spread_amount = self._get_spread_in_price_terms(symbol_to_liquidate); price_precision = self._get_price_precision(symbol_to_liquidate)
                        if position_dict_to_liquidate['side'] == OrderSide.BUY: close_price_for_liquidation = round(bar['close'] - (spread_amount / 2), price_precision)
                        else: close_price_for_liquidation = round(bar['close'] + (spread_amount / 2), price_precision)
                        self._close_position_at_price(position_dict_to_liquidate, close_price_for_liquidation, "MARGIN_CALL_LIQUIDATION")
                    else:
                        print(f"SimBroker ERROR: Market data unavailable for {symbol_to_liquidate} to liquidate {worst_pos_id}! Position remains for now (potential issue).")
                        self.trade_history.append({"event_type": "MARGIN_CALL_LIQUIDATION_ERROR", "timestamp": timestamp_unix, "position_id": worst_pos_id, "reason": "Market data unavailable for liquidation price."}); break
                else:
                    if not self.open_positions: break
                    print("SimBroker: Margin call, but no clear 'worst loss' position or all profitable. Consider alternative liquidation order. Halting this cycle.")
                    if self.open_positions:
                        first_pos_id = list(self.open_positions.keys())[0]; position_dict_to_liquidate = self.open_positions[first_pos_id]
                        print(f"SimBroker: Fallback liquidation of position {first_pos_id} due to margin call.")
                        symbol_to_liquidate = position_dict_to_liquidate['symbol']
                        if symbol_to_liquidate in self.current_market_data and self.current_market_data[symbol_to_liquidate]:
                            bar = self.current_market_data[symbol_to_liquidate]; spread_amount = self._get_spread_in_price_terms(symbol_to_liquidate); price_precision = self._get_price_precision(symbol_to_liquidate)
                            if position_dict_to_liquidate['side'] == OrderSide.BUY: close_price_for_liquidation = round(bar['close'] - (spread_amount / 2), price_precision)
                            else: close_price_for_liquidation = round(bar['close'] + (spread_amount / 2), price_precision)
                            self._close_position_at_price(position_dict_to_liquidate, close_price_for_liquidation, "MARGIN_CALL_LIQUIDATION_FALLBACK")
                        else: print(f"SimBroker ERROR: Market data also unavailable for fallback liquidation {first_pos_id}. Halting liquidation cycle."); break
                    else: break
                if self.margin_used == 0: break
            current_margin_level_after_liquidation = (self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')
            if current_margin_level_after_liquidation > self.stop_out_level_pct:
                 print(f"SimBroker: Margin level restored to {current_margin_level_after_liquidation:.2f}% after liquidations.")
                 self.trade_history.append({"event_type": "MARGIN_CALL_RESOLVED", "timestamp": timestamp_unix, "final_margin_level_pct": current_margin_level_after_liquidation })
            else:
                 print(f"SimBroker: Margin level at {current_margin_level_after_liquidation:.2f}% after liquidation attempts. Stop out may not be fully resolved if margin_used is still high.")
        elif margin_level_pct <= self.margin_call_warning_level_pct:
            print(f"SimBroker: MARGIN WARNING! Margin Level: {margin_level_pct:.2f}% (Warning Level: {self.margin_call_warning_level_pct:.2f}%)")
            self.trade_history.append({**log_event_common, "event_type": "MARGIN_WARNING_TRIGGERED"})
