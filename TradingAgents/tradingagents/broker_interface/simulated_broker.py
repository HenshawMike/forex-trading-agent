from typing import List, Dict, Optional, Any, Tuple
from tradingagents.broker_interface.base import BrokerInterface
from tradingagents.forex_utils.forex_states import (
    PriceTick, Candlestick, AccountInfo, OrderResponse, Position, FillDetails, # Added FillDetails
    OrderType, OrderSide, TimeInForce, FillPolicy # Added FillPolicy
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
            "EURUSD": 0.5, "GBPUSD": 0.6, "USDJPY": 0.5, "AUDUSD": 0.7, "USDCAD": 0.7, "XAUUSD": 2.0, "default": 1.0
        }
        # self.commission_per_lot definition removed from here to avoid duplication
        self.leverage: int = 100
        self.margin_used: float = 0.0
        self.account_currency = "USD"
        self.margin_call_warning_level_pct = 100.0 # e.g., 100%
        self.stop_out_level_pct = 50.0          # e.g., 50%
        self.test_data_store: Dict[str, List[Dict]] = {}

        self.commission_per_lot: Dict[str, float] = {
            "EURUSD": 7.0, "GBPUSD": 7.0, "USDJPY": 7.0, "AUDUSD": 7.0, "USDCAD": 7.0, "XAUUSD": 7.0, "default": 7.0
        } # Assumed ROUND-TURN, in account currency per 1.0 lot

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

        # Default contract size for Forex
        contract_size_units = 100000.0

        # Structure:
        # "base_currency": str
        # "quote_currency": str
        # "price_precision": int (decimal places for price display)
        # "point_size": float (smallest price increment, e.g., 0.00001 for EURUSD)
        # "pip_definition": float (the value of 1 pip in terms of price, e.g., 0.0001 for EURUSD, 0.01 for USDJPY)
        # "contract_size_units": float

        info = None

        if len(symbol_upper) == 6 and symbol_upper.isalnum(): # Standard XXXYYY Forex pair
            base = symbol_upper[:3]
            quote = symbol_upper[3:]

            if "JPY" == quote:
                info = {
                    "base_currency": base, "quote_currency": quote,
                    "price_precision": 3,
                    "point_size": 0.001,
                    "pip_definition": 0.01, # 1 pip is the 2nd decimal place for JPY pairs
                    "contract_size_units": contract_size_units
                }
            else: # Most other Forex pairs (e.g., EURUSD, GBPUSD, AUDUSD)
                info = {
                    "base_currency": base, "quote_currency": quote,
                    "price_precision": 5,
                    "point_size": 0.00001,
                    "pip_definition": 0.0001, # 1 pip is the 4th decimal place
                    "contract_size_units": contract_size_units
                }

        elif symbol_upper in ["XAUUSD", "GOLD"]:
            info = {
                "base_currency": "XAU", "quote_currency": "USD",
                "price_precision": 2,
                "point_size": 0.01,
                "pip_definition": 0.1, # For XAUUSD, 1 pip is often defined as $0.10 change if price is e.g. 1800.XX
                                      # Sometimes it's $1.0. This needs to be consistent with broker.
                                      # If price is 1800.12, pip_definition of 0.1 means the first decimal.
                                      # Let's assume for XAUUSD, a "pip" might refer to the first decimal place for simplicity.
                                      # Or, often for XAUUSD, "ticks" or "points" (0.01) are used instead of pips.
                                      # If we define a "pip" as 10 points for XAUUSD, then pip_definition = 0.1
                "contract_size_units": 100.0 # Contract size for XAUUSD is often 100 ounces
            }
        # Add elif for other specific symbols like XAGUSD, indices, oil if needed

        if info:
            return info
        else:
            print(f"SimBroker._get_symbol_info: Symbol info not explicitly configured for '{symbol_upper}'. Attempting generic parsing or default.")
            # Attempt generic parsing for unlisted XXXYYY (less accurate for pip_definition)
            if len(symbol_upper) == 6 and symbol_upper.isalnum():
                base = symbol_upper[:3]
                quote = symbol_upper[3:]
                # Generic default for non-JPY (assuming 5 decimal places)
                return {
                    "base_currency": base, "quote_currency": quote,
                    "price_precision": 5, "point_size": 0.00001, "pip_definition": 0.0001,
                    "contract_size_units": contract_size_units
                }

            print(f"SimBroker._get_symbol_info: Could not determine info for '{symbol_upper}'. Returning None.")
            return None

    def _get_point_size(self, symbol: str) -> float:
        info = self._get_symbol_info(symbol)
        return info["point_size"] if info else 0.00001

    def _get_price_precision(self, symbol: str) -> int:
        info = self._get_symbol_info(symbol)
        return info["price_precision"] if info else 5

    def _get_pip_value_for_sl_tp(self, symbol: str) -> float: # This is the price change for 1 pip
        info = self._get_symbol_info(symbol)
        # Ensure this returns the actual price change for 1 pip, which is 'pip_definition'
        return info["pip_definition"] if info and "pip_definition" in info else (0.01 if "JPY" in symbol.upper() else 0.0001) # Fallback

    def _get_exchange_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr == to_curr:
            return 1.0

        if not self.current_market_data:
            print(f"SimBroker._get_exchange_rate: current_market_data is not populated. Cannot get rate for {from_curr}/{to_curr}.")
            return None

        def get_pair_close_price(symbol: str) -> Optional[float]:
            symbol_upper = symbol.upper()
            if symbol_upper in self.current_market_data and self.current_market_data[symbol_upper]:
                close_price = self.current_market_data[symbol_upper].get('close')
                if close_price is not None:
                    try: # Ensure conversion to float, as data might be strings from some sources
                        return float(close_price)
                    except ValueError:
                        print(f"SimBroker._get_exchange_rate: Could not convert close_price '{close_price}' to float for {symbol_upper}.")
                        return None
            return None

        # 1. Try Direct Pair (e.g., EURUSD for EUR to USD)
        direct_pair_symbol = f"{from_curr}{to_curr}"
        rate = get_pair_close_price(direct_pair_symbol)
        if rate is not None:
            # print(f"DEBUG SimBroker._get_exchange_rate: Found direct rate for {direct_pair_symbol}: {rate}")
            return rate

        # 2. Try Inverse Pair (e.g., USDJPY for JPY to USD, need 1/rate)
        inverse_pair_symbol = f"{to_curr}{from_curr}"
        inverse_rate = get_pair_close_price(inverse_pair_symbol)
        if inverse_rate is not None:
            if inverse_rate == 0:
                print(f"SimBroker._get_exchange_rate: Inverse rate for {inverse_pair_symbol} is zero, cannot divide.")
                return None # Avoid division by zero
            # print(f"DEBUG SimBroker._get_exchange_rate: Found inverse rate for {inverse_pair_symbol}: {inverse_rate}, using 1/{inverse_rate}")
            return 1.0 / inverse_rate
        elif inverse_rate == 0: # This condition was part of the if, should be outside if inverse_rate is None
             print(f"SimBroker._get_exchange_rate: Inverse rate for {inverse_pair_symbol} is zero (or data error), cannot divide.")


        # 3. Try Triangulation through the account currency
        intermediary_curr = self.account_currency.upper()

        # Path A: (FROM / INTERMEDIARY) / (TO / INTERMEDIARY)
        # Example: FROM=EUR, TO=GBP, INTERMEDIARY=USD. Requires EUR/USD and GBP/USD. Rate = (EUR/USD) / (GBP/USD)
        if from_curr != intermediary_curr and to_curr != intermediary_curr:
            # print(f"DEBUG SimBroker._get_exchange_rate: Triangulating {from_curr}/{to_curr} via {intermediary_curr} using Path A")
            from_curr_to_intermediary_rate = self._get_exchange_rate(from_curr, intermediary_curr) # Recursive call
            to_curr_to_intermediary_rate = self._get_exchange_rate(to_curr, intermediary_curr)     # Recursive call

            if from_curr_to_intermediary_rate is not None and to_curr_to_intermediary_rate is not None:
                if to_curr_to_intermediary_rate == 0:
                    print(f"SimBroker._get_exchange_rate: Triangulation Path A failed for {from_curr}/{to_curr}. Divisor (TO/{intermediary_curr}) is zero.")
                else:
                    calculated_rate = from_curr_to_intermediary_rate / to_curr_to_intermediary_rate
                    # print(f"DEBUG SimBroker._get_exchange_rate: Path A: {from_curr}/{intermediary_curr}={from_curr_to_intermediary_rate}, {to_curr}/{intermediary_curr}={to_curr_to_intermediary_rate}. Result {from_curr}/{to_curr}={calculated_rate}")
                    return calculated_rate

        # Path B: (INTERMEDIARY / TO) / (INTERMEDIARY / FROM) - This is equivalent to (FROM / INTERMEDIARY) / (TO / INTERMEDIARY) if intermediary is common base
        # Path C: (FROM / INTERMEDIARY_B) * (INTERMEDIARY_B / TO) - More complex, needs finding INTERMEDIARY_B
        # The current recursive structure primarily handles triangulation through self.account_currency.
        # If from_curr or to_curr is self.account_currency, direct/inverse lookup (steps 1 & 2) in recursive calls handle it.
        # e.g. EUR/JPY with account USD:
        # _get_exchange_rate("EUR", "JPY")
        #   triangulation: from_curr_to_usd = _get_exchange_rate("EUR", "USD") -> finds EURUSD (direct)
        #                  to_curr_to_usd   = _get_exchange_rate("JPY", "USD") -> finds USDJPY (inverse) -> 1/USDJPY
        #   result = EURUSD / (1/USDJPY) = EURUSD * USDJPY. This is correct.

        print(f"SimBroker._get_exchange_rate: Exchange rate for {from_curr}/{to_curr} could not be determined using intermediary {intermediary_curr} "
              f"at simulated time {datetime.datetime.fromtimestamp(self.current_simulated_time_unix, tz=datetime.timezone.utc).isoformat()}. "
              f" Ensure necessary pairs involving {from_curr}, {to_curr}, and {intermediary_curr} are in market data if direct pair is missing.")
        return None

    def calculate_pip_value_in_account_currency(self, symbol: str, volume_lots: float) -> Optional[float]:
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info:
            print(f"SimBroker.calculate_pip_value: Could not get symbol info for {symbol}.")
            return None

        pip_definition_in_price_terms = symbol_info['pip_definition'] # e.g., 0.0001 for EURUSD, 0.01 for USDJPY
        quote_currency = symbol_info['quote_currency']
        contract_size = symbol_info['contract_size_units'] # e.g., 100000 for FX, 100 for XAUUSD

        # Value of one pip for the given volume, in the QUOTE currency of the pair
        value_of_one_pip_in_quote_currency = pip_definition_in_price_terms * contract_size * volume_lots

        if quote_currency == self.account_currency:
            return value_of_one_pip_in_quote_currency
        else:
            # Need to convert from quote_currency to self.account_currency
            # Example: symbol=EURJPY (quote JPY), account_currency=USD. Need JPY/USD rate.
            # _get_exchange_rate("JPY", "USD")
            exchange_rate = self._get_exchange_rate(quote_currency, self.account_currency)

            if exchange_rate is None:
                print(f"SimBroker.calculate_pip_value: Failed to get exchange rate for {quote_currency} to {self.account_currency} for symbol {symbol} to calculate pip value.")
                return None

            return value_of_one_pip_in_quote_currency * exchange_rate

    def calculate_pnl_in_account_currency(self,
                                      symbol: str,
                                      side: OrderSide,
                                      volume_lots: float,
                                      entry_price: float,
                                      close_price: float) -> Optional[float]:
        symbol_info = self._get_symbol_info(symbol)
        if not symbol_info:
            print(f"SimBroker.calculate_pnl: Could not get symbol info for {symbol}.")
            return None

        # pip_definition is the price movement that constitutes 1 pip (e.g., 0.0001 for EURUSD)
        pip_definition_val = symbol_info['pip_definition']
        if pip_definition_val == 0: # Avoid division by zero
            print(f"SimBroker.calculate_pnl: Pip definition for {symbol} is zero. Cannot calculate P/L in pips.")
            return None

        price_difference = (close_price - entry_price) if side == OrderSide.BUY else (entry_price - close_price)

        # Calculate how many pips were moved
        pips_moved = price_difference / pip_definition_val

        # Get the value of 1 pip for 1 standard lot in account currency
        value_of_one_pip_for_one_lot_in_acct_curr = self.calculate_pip_value_in_account_currency(symbol, 1.0)

        if value_of_one_pip_for_one_lot_in_acct_curr is None:
            print(f"SimBroker.calculate_pnl: Could not calculate pip value in account currency for {symbol}.")
            return None

        # Total P/L = pips_moved * (value of 1 pip for 1 lot) * (actual lots traded)
        total_pnl = pips_moved * value_of_one_pip_for_one_lot_in_acct_curr * volume_lots

        return total_pnl

    def _get_spread_in_price_terms(self, symbol: str) -> float:
        symbol_info = self._get_symbol_info(symbol.upper()) # Already uppercased symbol
        if not symbol_info:
            print(f"SimBroker._get_spread_in_price_terms: Could not get symbol info for {symbol}, returning 0 spread.")
            return 0.0

        configured_pips = self.default_spread_pips.get(symbol.upper(), self.default_spread_pips.get("default", 1.0))
        pip_definition_for_symbol = symbol_info['pip_definition'] # e.g. 0.0001 for EURUSD

        return configured_pips * pip_definition_for_symbol

    def _calculate_commission(self, symbol: str, volume_lots: float) -> float:
        return self.commission_per_lot.get(symbol.upper(), self.commission_per_lot.get("default", 7.0)) * volume_lots


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

    def place_order(self,
                      symbol: str,
                      order_type: OrderType,
                      side: OrderSide,
                      volume: float,
                      price: Optional[float] = None,
                      stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None,
                      time_in_force: Optional[TimeInForce] = TimeInForce.GTC,
                      fill_policy: Optional[FillPolicy] = FillPolicy.NORMAL,
                      magic_number: Optional[int] = 0,
                      comment: Optional[str] = "",
                      client_order_id: Optional[str] = None
                     ) -> OrderResponse:

        order_id = self._generate_unique_id()
        creation_timestamp = self.current_simulated_time_unix

        # Prepare a base response
        response = OrderResponse(
            order_id=order_id,
            client_order_id=client_order_id,
            status="REJECTED", # Default to rejected, update on success
            symbol=symbol,
            order_type=order_type,
            side=side,
            requested_volume=volume,
            filled_volume=0.0,
            average_fill_price=None,
            requested_price=price,
            stop_loss_price=stop_loss,
            take_profit_price=take_profit,
            time_in_force=time_in_force or TimeInForce.GTC, # Ensure not None
            fill_policy=fill_policy or FillPolicy.NORMAL, # Ensure not None
            creation_timestamp=creation_timestamp,
            last_update_timestamp=creation_timestamp,
            fills=[],
            error_message=None,
            broker_native_response={"simulated_broker_comment": "Order received"},
            position_id=None
        )

        if not self.is_connected():
            response['error_message'] = "Broker not connected."
            return response

        current_bar = self.current_market_data.get(symbol)
        if not current_bar:
            response['error_message'] = f"Market data not available for {symbol} at {datetime.datetime.fromtimestamp(creation_timestamp, tz=datetime.timezone.utc).isoformat()}."
            return response

        price_precision = self._get_price_precision(symbol)

        if order_type == OrderType.MARKET:
            fill_price_base = current_bar['close']
            spread_amount = self._get_spread_in_price_terms(symbol)
            point_size = self._get_point_size(symbol)
            slippage_in_price = self.fixed_slippage_pips * point_size
            entry_price_final: float
            if side == OrderSide.BUY:
                entry_price_final = round(fill_price_base + (spread_amount / 2) + random.uniform(0, slippage_in_price), price_precision)
            elif side == OrderSide.SELL:
                entry_price_final = round(fill_price_base - (spread_amount / 2) - random.uniform(0, slippage_in_price), price_precision)
            else: # Should not happen due to Enum
                response['error_message'] = "Invalid order side."
                return response

            volume_to_fill = volume
            simulated_available_volume = round(random.uniform(0.5, 1.5) * volume, 2) # Mock available volume

            if fill_policy == FillPolicy.FOK:
                # In this simple sim, if it passes margin, FOK fills fully.
                # A more complex sim might check against a mock order book depth.
                # For now, FOK will behave like NORMAL unless margin fails.
                pass # volume_to_fill remains `volume`
            elif fill_policy == FillPolicy.IOC:
                volume_to_fill = min(volume, simulated_available_volume)
                if volume_to_fill < 0.01 : # Min lot size
                    response['error_message'] = f"IOC policy: No volume fillable at current market for {symbol} (available: {simulated_available_volume}, requested: {volume})."
                    response['status'] = "REJECTED" # Or CANCELLED if IOC implies that for zero fill
                    return response
            # NORMAL: volume_to_fill remains `volume`

            margin_for_this_trade = self._calculate_margin_required(symbol, volume_to_fill, entry_price_final)
            self._update_equity_and_margin()
            free_margin = self.equity - self.margin_used
            if free_margin < margin_for_this_trade:
                response['error_message'] = f"Insufficient free margin. Need: {margin_for_this_trade:.2f}, Have: {free_margin:.2f}"
                return response

            commission_cost = self._calculate_commission(symbol, volume_to_fill)
            position_id = self._generate_unique_id()

            fill_details = FillDetails(
                fill_id=f"sim_fill_{order_id}",
                fill_price=entry_price_final,
                fill_volume=volume_to_fill,
                fill_timestamp=creation_timestamp,
                commission=commission_cost,
                fee=0.0
            )
            response['fills'].append(fill_details)

            response['status'] = "FILLED" if volume_to_fill == volume else "PARTIALLY_FILLED"
            response['filled_volume'] = volume_to_fill
            response['average_fill_price'] = entry_price_final
            response['position_id'] = position_id
            response['last_update_timestamp'] = creation_timestamp
            response['broker_native_response'] = {"simulated_broker_comment": f"Market order executed. Spread: {spread_amount}, Slippage: {slippage_in_price}"}


            # Create and store position (using a dictionary that conforms to Position TypedDict)
            new_position_data: Position = { # Explicitly define keys to match Position TypedDict
                'position_id': position_id,
                'symbol': symbol,
                'side': side,
                'volume': volume_to_fill,
                'entry_price': entry_price_final,
                'current_price': entry_price_final, # Initial current_price
                'profit_loss': -commission_cost, # Initial P/L is just commission
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'open_time': creation_timestamp,
                'magic_number': magic_number,
                'comment': comment
            }
            self.open_positions[position_id] = new_position_data # Store as dict

            self.balance -= commission_cost
            self.margin_used += margin_for_this_trade
            self._update_equity_and_margin() # Recalculate equity after balance change

            self.trade_history.append({
                "event_type": response['status'], # FILLED or PARTIALLY_FILLED
                "timestamp": creation_timestamp, "order_id": order_id, "position_id": position_id,
                "symbol": symbol, "side": side.value, "requested_volume": volume, "filled_volume": volume_to_fill,
                "fill_price": entry_price_final, "sl": stop_loss, "tp": take_profit,
                "commission": commission_cost, "comment": comment, "client_order_id": client_order_id
            })
            print(f"SimBroker: {side.value} {volume_to_fill} (req: {volume}) {symbol} @ {entry_price_final}. PosID: {position_id}. Comm: {commission_cost:.2f}. FillPolicy: {fill_policy.value if fill_policy else 'N/A'}")
            return response

        elif order_type in [OrderType.LIMIT, OrderType.STOP]:
            if price is None:
                response['error_message'] = "Price required for pending orders."
                return response

            # Store pending order with all necessary details
            pending_order_details = {
                "order_id": order_id, "client_order_id": client_order_id,
                "status": "PENDING", "symbol": symbol, "side": side, "type": order_type,
                "volume": volume, "price": price, "timestamp": creation_timestamp,
                "stop_loss": stop_loss, "take_profit": take_profit,
                "magic_number": magic_number, "comment": comment,
                "time_in_force": time_in_force, "fill_policy": fill_policy
            }
            self.pending_orders[order_id] = pending_order_details

            response['status'] = "PENDING"
            response['broker_native_response'] = {"simulated_broker_comment": "Pending order accepted"}

            self.trade_history.append({
                "event_type": "PENDING_ORDER_PLACED", "timestamp": creation_timestamp, "order_id": order_id,
                "symbol": symbol, "side": side.value, "type": order_type.value, "volume": volume,
                "price": price, "sl": stop_loss, "tp": take_profit, "comment": comment, "client_order_id": client_order_id
            })
            print(f"SimBroker: Pending {side.value} {order_type.value} for {volume} {symbol} @ {price} SL:{stop_loss} TP:{take_profit} placed. OrderID: {order_id}")
            return response

        response['error_message'] = "Unsupported order type."
        return response

    def process_pending_orders(self):
        if not self.current_market_data or not self.current_simulated_time_unix: return
        orders_to_remove_after_processing = []

        for order_id, po_details_dict in list(self.pending_orders.items()):
            # Ensure po_details_dict has all necessary keys before accessing
            symbol = po_details_dict['symbol']
            bar = self.current_market_data.get(symbol)
            order_price = po_details_dict['price']
            order_type: OrderType = po_details_dict['type'] # Already OrderType enum
            order_side: OrderSide = po_details_dict['side'] # Already OrderSide enum
            order_volume = po_details_dict['volume']

            # Retrieve fill_policy, default if missing (should not happen with new place_order)
            order_fill_policy: FillPolicy = po_details_dict.get('fill_policy', FillPolicy.NORMAL)

            if not bar: continue

            sl_pos = po_details_dict.get('stop_loss')
            tp_pos = po_details_dict.get('take_profit')
            magic_pos = po_details_dict.get('magic_number')
            comment_pos = po_details_dict.get('comment', f"Filled from pending {order_id}")
            client_oid = po_details_dict.get('client_order_id')

            fill_price_sim: Optional[float] = None
            precision = self._get_price_precision(symbol)

            if order_type == OrderType.LIMIT:
                if order_side == OrderSide.BUY and bar['low'] <= order_price: fill_price_sim = min(order_price, bar['open'])
                elif order_side == OrderSide.SELL and bar['high'] >= order_price: fill_price_sim = max(order_price, bar['open'])
            elif order_type == OrderType.STOP:
                if order_side == OrderSide.BUY and bar['high'] >= order_price: fill_price_sim = max(order_price, bar['open'])
                elif order_side == OrderSide.SELL and bar['low'] <= order_price: fill_price_sim = min(order_price, bar['open'])

            if fill_price_sim is not None: # Triggered # Corrected variable name here
                effective_exec_base = round(fill_price_sim, precision)
                spread_for_fill = self._get_spread_in_price_terms(symbol)
                actual_fill_price: float

                if order_side == OrderSide.BUY:
                    actual_fill_price = effective_exec_base + (spread_for_fill / 2)
                    if order_type == OrderType.STOP: # Apply slippage for stop orders
                        actual_fill_price += random.uniform(0, self.fixed_slippage_pips * self._get_point_size(symbol))
                    if order_type == OrderType.LIMIT: # Ensure limit price or better
                        actual_fill_price = min(actual_fill_price, order_price)
                else: # SELL
                    actual_fill_price = effective_exec_base - (spread_for_fill / 2)
                    if order_type == OrderType.STOP: # Apply slippage for stop orders
                        actual_fill_price -= random.uniform(0, self.fixed_slippage_pips * self._get_point_size(symbol))
                    if order_type == OrderType.LIMIT: # Ensure limit price or better
                        actual_fill_price = max(actual_fill_price, order_price)

                actual_fill_price = round(actual_fill_price, precision)

                volume_to_fill = order_volume
                simulated_available_volume_at_price = round(random.uniform(0.5, 1.5) * order_volume, 2)

                if order_fill_policy == FillPolicy.FOK:
                    if simulated_available_volume_at_price < order_volume:
                        print(f"SimBroker: Pending FOK order {order_id} ({symbol}) could not be filled entirely ({simulated_available_volume_at_price} < {order_volume}). Order cancelled.")
                        self.trade_history.append({"event_type": "PENDING_ORDER_CANCELLED_FOK", "timestamp": self.current_simulated_time_unix, "order_id": order_id, "symbol": symbol, "reason": "FOK not fillable"})
                        orders_to_remove_after_processing.append(order_id)
                        continue
                elif order_fill_policy == FillPolicy.IOC:
                    volume_to_fill = min(order_volume, simulated_available_volume_at_price)
                    if volume_to_fill < 0.01: # Min lot size
                        print(f"SimBroker: Pending IOC order {order_id} ({symbol}) has zero fillable volume. Order cancelled.")
                        self.trade_history.append({"event_type": "PENDING_ORDER_CANCELLED_IOC", "timestamp": self.current_simulated_time_unix, "order_id": order_id, "symbol": symbol, "reason": "IOC zero fillable"})
                        orders_to_remove_after_processing.append(order_id)
                        continue
                # NORMAL: volume_to_fill remains order_volume

                print(f"SimBroker: Pending order {order_id} ({symbol} {order_side.value} {order_type.value} @ {order_price}) TRIGGERED. FillPolicy: {order_fill_policy.value}. Vol to Fill: {volume_to_fill}. Fill Price: {actual_fill_price}")

                ts_unix = self.current_simulated_time_unix
                margin_req = self._calculate_margin_required(symbol, volume_to_fill, actual_fill_price)
                self._update_equity_and_margin()
                free_margin = self.equity - self.margin_used

                if free_margin < margin_req:
                    print(f"SimBroker: Insufficient margin for pending {order_id}. Need: {margin_req:.2f}, Have: {free_margin:.2f}. Removed.")
                    self.trade_history.append({"event_type": "PENDING_ORDER_FAIL_MARGIN", "timestamp": ts_unix, "order_id": order_id, "symbol": symbol, "side": order_side.value, "volume": volume_to_fill, "trigger_price": fill_price_sim, "reason": "Insufficient margin"})
                    orders_to_remove_after_processing.append(order_id)
                    continue

                commission = self._calculate_commission(symbol, volume_to_fill)
                pos_id = self._generate_unique_id()

                # Create Position data (dictionary)
                new_pos_data: Position = {
                    'position_id': pos_id, 'symbol': symbol, 'side': order_side,
                    'volume': volume_to_fill, 'entry_price': actual_fill_price,
                    'current_price': actual_fill_price, 'profit_loss': -commission,
                    'stop_loss': sl_pos, 'take_profit': tp_pos, 'open_time': ts_unix,
                    'magic_number': magic_pos, 'comment': comment_pos
                }
                self.open_positions[pos_id] = new_pos_data

                self.balance -= commission
                self.margin_used += margin_req
                self._update_equity_and_margin()

                status_str = "FILLED"
                if order_fill_policy == FillPolicy.IOC and volume_to_fill < order_volume:
                    status_str = "PARTIALLY_FILLED_IOC" # More specific status

                self.trade_history.append({
                    "event_type": f"PENDING_ORDER_{status_str}", "timestamp": ts_unix,
                    "original_order_id": order_id, "client_order_id": client_oid, "position_id": pos_id,
                    "symbol": symbol, "side": order_side.value, "type": order_type.value,
                    "requested_volume": order_volume, "filled_volume": volume_to_fill,
                    "requested_price": order_price, "fill_price": actual_fill_price, "sl": sl_pos, "tp": tp_pos,
                    "commission": commission, "comment": comment_pos
                })
                print(f"SimBroker: Pending order {order_id} {status_str}. New PosID: {pos_id} for {symbol} {order_side.value} {volume_to_fill} @ {actual_fill_price}. Comm: {commission:.2f}")
                orders_to_remove_after_processing.append(order_id)

        for oid in orders_to_remove_after_processing:
            if oid in self.pending_orders: del self.pending_orders[oid]

    # Note: _update_equity_and_margin() is called by update_market_data, place_order,
    # _close_position_at_price, and potentially before critical checks in process_pending_orders.

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
            pos_data = self.open_positions[order_id] # This is a dict
            original_type = OrderType.MARKET # Positions are results of market or filled pending orders

            if new_stop_loss is not None: pos_data['stop_loss'] = new_stop_loss
            if new_take_profit is not None: pos_data['take_profit'] = new_take_profit

            # Position objects don't have a fill_policy or client_order_id in current Position TypedDict
            # So we use defaults or None for the OrderResponse
            return OrderResponse(
                order_id=order_id, # Position ID used as order_id for context
                client_order_id=None, # Not typically stored with position objects directly
                status="MODIFIED",
                symbol=pos_data['symbol'],
                order_type=original_type, # Reflect it was a modification on an existing position
                side=pos_data['side'],
                requested_volume=pos_data['volume'], # Original volume
                filled_volume=pos_data['volume'], # Fully filled to be open
                average_fill_price=pos_data['entry_price'],
                requested_price=pos_data['entry_price'], # Entry price as requested for this context
                stop_loss_price=pos_data['stop_loss'],
                take_profit_price=pos_data['take_profit'],
                time_in_force=TimeInForce.GTC, # Default for positions
                fill_policy=FillPolicy.NORMAL, # Default for positions
                creation_timestamp=pos_data['open_time'], # Position open time
                last_update_timestamp=ts,
                fills=[], # Modification doesn't create new fills usually
                error_message=None,
                broker_native_response={"simulated_broker_comment": "Position SL/TP updated"},
                position_id=order_id
            )
        elif order_id in self.pending_orders:
            po_data = self.pending_orders[order_id] # This is a dict

            if new_price is not None: po_data['price'] = new_price
            if new_stop_loss is not None: po_data['stop_loss'] = new_stop_loss
            if new_take_profit is not None: po_data['take_profit'] = new_take_profit

            # Reconstruct OrderResponse from pending order data
            return OrderResponse(
                order_id=order_id,
                client_order_id=po_data.get('client_order_id'),
                status="MODIFIED_PENDING",
                symbol=po_data['symbol'],
                order_type=po_data['type'],
                side=po_data['side'],
                requested_volume=po_data['volume'],
                filled_volume=0.0, # Pending orders are not filled
                average_fill_price=None,
                requested_price=po_data['price'],
                stop_loss_price=po_data['stop_loss'],
                take_profit_price=po_data['take_profit'],
                time_in_force=po_data.get('time_in_force', TimeInForce.GTC),
                fill_policy=po_data.get('fill_policy', FillPolicy.NORMAL),
                creation_timestamp=po_data['timestamp'],
                last_update_timestamp=ts,
                fills=[],
                error_message=None,
                broker_native_response={"simulated_broker_comment": "Pending order parameters updated"},
                position_id=None
            )

        # Fallback if order_id not found
        return OrderResponse(
            order_id=order_id, client_order_id=None, status="REJECTED", symbol="", order_type=OrderType.MARKET, # Dummy values
            side=OrderSide.BUY, requested_volume=0, filled_volume=0, average_fill_price=None, requested_price=None,
            stop_loss_price=None, take_profit_price=None, time_in_force=TimeInForce.GTC, fill_policy=FillPolicy.NORMAL,
            creation_timestamp=ts, last_update_timestamp=ts, fills=[], error_message="Order/Position not found.",
            broker_native_response=None, position_id=None
        )

    def _close_position_at_price(self, position_data: Position, close_price: float, reason: str, volume_to_close: Optional[float] = None) -> Tuple[Optional[float], Optional[FillDetails]]:
        current_position_id = position_data['position_id'] # type: ignore

        if current_position_id not in self.open_positions:
            print(f"SimBroker: Position {current_position_id} already actioned or does not exist. Cannot close for reason: {reason}.")
            return None, None

        actual_volume_closed = volume_to_close if volume_to_close is not None and volume_to_close <= position_data['volume'] else position_data['volume'] # type: ignore
        if actual_volume_closed < 0.01: # min lot
             print(f"SimBroker: Volume to close for {current_position_id} is too small ({actual_volume_closed}). No action taken.")
             return None, None


        realized_pnl = self.calculate_pnl_in_account_currency(position_data['symbol'], position_data['side'], actual_volume_closed, position_data['entry_price'], close_price) # type: ignore

        if realized_pnl is None:
            print(f"SimBroker: PNL calculation failed for closing pos {current_position_id} ({position_data['symbol']}). Realized PNL recorded as 0.0. Position will still be closed/adjusted.") # type: ignore
            realized_pnl = 0.0

        commission_for_closure = self._calculate_commission(position_data['symbol'], actual_volume_closed) # type: ignore
        net_pnl_after_commission = realized_pnl - commission_for_closure # Commission is a cost

        self.balance += net_pnl_after_commission # PNL already includes cost of spread, now subtract commission for this part of trade cycle

        original_pos_volume = position_data['volume'] # type: ignore
        margin_freed_ratio = actual_volume_closed / original_pos_volume
        original_margin_for_pos = self._calculate_margin_required(position_data['symbol'], original_pos_volume, position_data['entry_price']) # type: ignore
        margin_freed_this_close = original_margin_for_pos * margin_freed_ratio

        self.margin_used -= margin_freed_this_close
        if self.margin_used < 0.005 : self.margin_used = 0.0 # Threshold to avoid tiny float residuals

        fill_ts = self.current_simulated_time_unix
        closed_fill_details = FillDetails(
            fill_id=f"sim_fill_close_{current_position_id}_{str(uuid.uuid4())[:4]}",
            fill_price=close_price,
            fill_volume=actual_volume_closed,
            fill_timestamp=fill_ts,
            commission=commission_for_closure, # Commission for this closing part
            fee=0.0
        )

        self.trade_history.append({
            "event_type": "POSITION_CLOSED_PARTIAL" if actual_volume_closed < original_pos_volume else "POSITION_CLOSED_FULL",
            "timestamp": fill_ts, "position_id": current_position_id,
            "symbol": position_data['symbol'], "side": position_data['side'].value,  # type: ignore
            "closed_volume": actual_volume_closed, "remaining_volume": original_pos_volume - actual_volume_closed,
            "entry_price": position_data['entry_price'], "open_time": position_data['open_time'],  # type: ignore
            "close_price": close_price, "realized_pnl": realized_pnl, "commission_on_close": commission_for_closure,
            "reason_for_close": reason,
            "magic_number": position_data.get('magic_number',0), "comment": position_data.get('comment',"") # type: ignore
        })

        if actual_volume_closed < original_pos_volume:
            self.open_positions[current_position_id]['volume'] = round(original_pos_volume - actual_volume_closed, 2)
            # PNL for remaining part needs to be based on remaining volume.
            # The 'profit_loss' field in Position should reflect unrealized PNL of the open portion.
            # For simplicity, current _update_equity_and_margin will handle this.
            print(f"SimBroker: Position {current_position_id} ({position_data['symbol']}) PARTIALLY CLOSED {actual_volume_closed} lots at {close_price} by {reason}. P/L (this part): {realized_pnl:.2f}. Comm: {commission_for_closure:.2f}. Remaining vol: {self.open_positions[current_position_id]['volume']:.2f}")
        else:
            del self.open_positions[current_position_id]
            print(f"SimBroker: Position {current_position_id} ({position_data['symbol']}) FULLY CLOSED at {close_price} by {reason}. P/L: {realized_pnl:.2f}. Comm: {commission_for_closure:.2f}. Margin Freed: {margin_freed_this_close:.2f}")

        self._update_equity_and_margin()
        return realized_pnl, closed_fill_details


    def check_for_sl_tp_triggers(self):
        if not self.current_market_data or not self.current_simulated_time_unix: return
        positions_to_action = []
        for pos_id, pos_data_dict in list(self.open_positions.items()):
            # Ensure pos_data_dict is a dict before trying to construct Position from it
            # if not isinstance(pos_data_dict, dict):
            #    print(f"SimBroker Warning: pos_data for {pos_id} is not a dict, skipping SL/TP check. Data: {pos_data_dict}")
            #    continue
            pos = Position(**pos_data_dict) # Construct Position TypedDict instance for type safety

            if pos.symbol not in self.current_market_data: continue
            bar = self.current_market_data[pos.symbol]
            trigger_price = None; reason = None
            if pos.side == OrderSide.BUY:
                if pos.stop_loss is not None and bar['low'] <= pos.stop_loss: trigger_price, reason = pos.stop_loss, "STOP_LOSS_HIT"
                elif pos.take_profit is not None and bar['high'] >= pos.take_profit: trigger_price, reason = pos.take_profit, "TAKE_PROFIT_HIT"
            elif pos.side == OrderSide.SELL:
                if pos.stop_loss is not None and bar['high'] >= pos.stop_loss: trigger_price, reason = pos.stop_loss, "STOP_LOSS_HIT"
                elif pos.take_profit is not None and bar['low'] <= pos.take_profit: trigger_price, reason = pos.take_profit, "TAKE_PROFIT_HIT"

            if trigger_price is not None:
                positions_to_action.append({"position_to_close_data": pos_data_dict, "close_price": trigger_price, "reason": reason}) # Pass dict data

        for item in positions_to_action:
            # Pass the original dict from self.open_positions to _close_position_at_price
            # as it expects a mutable dict if partial closes are to update the original entry.
            # However, _close_position_at_price expects Position TypedDict for its first arg type hint.
            # We need to ensure consistency. If open_positions stores dicts, _close_position_at_price should handle dicts.
            # For now, constructing Position from dict when calling _close_position_at_price.
            position_obj_for_closing = Position(**item["position_to_close_data"])
            self._close_position_at_price(position_obj_for_closing, item["close_price"], item["reason"])


    def close_order(self, order_id: str, volume: Optional[float] = None, price: Optional[float] = None) -> OrderResponse: # order_id here is position_id
        ts = self.current_simulated_time_unix
        base_response_args = {"order_id": order_id, "client_order_id": None, "creation_timestamp": ts, "last_update_timestamp": ts, "broker_native_response": None, "fills": []}

        if order_id not in self.open_positions:
            return OrderResponse(status="REJECTED", error_message="Position not found.", symbol="", order_type=OrderType.MARKET, side=OrderSide.BUY, requested_volume=0, filled_volume=0, **base_response_args) # type: ignore

        pos_to_close_data = self.open_positions[order_id] # This is a dict
        pos_to_close_obj = Position(**pos_to_close_data) # Create Position object for type safety

        current_bar = self.current_market_data.get(pos_to_close_obj.symbol)
        if not current_bar:
            return OrderResponse(status="REJECTED", error_message="Market data unavailable.", symbol=pos_to_close_obj.symbol, order_type=OrderType.MARKET, side=pos_to_close_obj.side, requested_volume=pos_to_close_obj.volume, filled_volume=0, **base_response_args) # type: ignore

        close_price_to_use = price
        if close_price_to_use is None: # Market close
            spread_amount = self._get_spread_in_price_terms(pos_to_close_obj.symbol)
            close_price_base = current_bar['close']
            # Closing a BUY position means SELLING at BID; Closing a SELL position means BUYING at ASK
            close_price_to_use = (close_price_base - spread_amount / 2) if pos_to_close_obj.side == OrderSide.BUY else (close_price_base + spread_amount / 2)
            close_price_to_use = round(close_price_to_use, self._get_price_precision(pos_to_close_obj.symbol))

        volume_to_close_val = volume if volume is not None and volume > 0 else pos_to_close_obj.volume

        realized_pnl, closed_fill_details = self._close_position_at_price(pos_to_close_obj, close_price_to_use, "CLOSED_BY_REQUEST", volume_to_close_val)

        if closed_fill_details is None: # Close action failed in _close_position_at_price
            return OrderResponse(status="REJECTED", error_message="Failed to execute close action (e.g. already closed, zero volume).", symbol=pos_to_close_obj.symbol, order_type=OrderType.MARKET, side=pos_to_close_obj.side, requested_volume=volume_to_close_val, filled_volume=0, **base_response_args) # type: ignore

        final_status = "CLOSED"
        if order_id in self.open_positions: # Check if position still exists (i.e., was partially closed)
            if self.open_positions[order_id]['volume'] < pos_to_close_obj.volume:
                 final_status = "PARTIALLY_CLOSED" # This might be complex if original order_id is for the whole pos

        return OrderResponse(
            order_id=order_id, # Original position_id acts as the reference
            client_order_id=None, # Closures don't typically have new client_order_ids
            status=final_status,
            symbol=pos_to_close_obj.symbol,
            order_type=OrderType.MARKET, # Closure is effectively a market order
            side=OrderSide.SELL if pos_to_close_obj.side == OrderSide.BUY else OrderSide.BUY, # Opposite side for closure
            requested_volume=volume_to_close_val, # Volume requested to close
            filled_volume=closed_fill_details.fill_volume,
            average_fill_price=closed_fill_details.fill_price,
            requested_price=price, # If a specific price was requested for closing (e.g. limit close, not fully impl here)
            stop_loss_price=None, # Not relevant for a close order response
            take_profit_price=None, # Not relevant for a close order response
            time_in_force=TimeInForce.IOC, # Closures are typically IOC
            fill_policy=FillPolicy.IOC,    # Closures are typically IOC
            creation_timestamp=ts, # Timestamp of this close action
            last_update_timestamp=ts,
            fills=[closed_fill_details],
            error_message=None,
            broker_native_response={"simulated_broker_comment": f"Position {order_id} closed by request."},
            position_id=order_id # Refers to the (partially) closed position
        )

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
