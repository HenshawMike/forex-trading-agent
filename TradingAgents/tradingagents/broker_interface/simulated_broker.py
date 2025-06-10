from typing import List, Dict, Optional, Any, Tuple # Ensure Tuple is imported
from tradingagents.broker_interface.base import BrokerInterface
# Import the actual TypedDicts and Enums
from tradingagents.forex_utils.forex_states import (
    PriceTick, Candlestick, AccountInfo, OrderResponse, Position,
    OrderType, OrderSide, TimeInForce
)
import datetime
import time
import random # For slippage
import uuid # For unique IDs

class SimulatedBroker(BrokerInterface):
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.balance = initial_capital
        self.equity = initial_capital
        self._connected = True # Always connected for sim
        self.current_simulated_time_unix = time.time() # Fallback, should be updated by backtester

        self.open_positions: Dict[str, Position] = {}
        self.pending_orders: Dict[str, OrderResponse] = {} # Not fully used in this step
        self.trade_history: List[Dict] = []

        self.order_fill_logic: str = "CURRENT_BAR_CLOSE" # Or "NEXT_BAR_OPEN"
        self.fixed_slippage_pips: float = 0.2 # Example: 0.2 pips slippage

        # Store current bar data provided by a backtester/data handler
        self.current_market_data: Dict[str, Candlestick] = {}

        # Configuration for symbols (can be expanded or made external)
        self.default_spread_pips: Dict[str, float] = {
            "EURUSD": 0.5, "GBPUSD": 0.6, "USDJPY": 0.5, "AUDUSD": 0.7, "USDCAD": 0.7, "XAUUSD": 2.0 # Gold spread in pips (e.g. 20 points if 1 pip = $0.10 for XAU)
        }
        self.commission_per_lot: Dict[str, float] = { # Per 1.0 lot (100,000 units) round turn
            "EURUSD": 7.0, "GBPUSD": 7.0, "USDJPY": 7.0, "AUDUSD": 7.0, "USDCAD": 7.0, "XAUUSD": 7.0
        }
        self.leverage: int = 100 # e.g., 100:1 leverage, margin requirement is 1/100 = 1%
        self.margin_used: float = 0.0

        print(f"SimulatedBroker initialized. Capital: {initial_capital}, Slippage: {self.fixed_slippage_pips} pips, Leverage: {self.leverage}:1")

    def _generate_unique_id(self) -> str:
        return str(uuid.uuid4())

    def _get_point_size(self, symbol: str) -> float:
        pair_normalized = symbol.upper()
        if "JPY" in pair_normalized: return 0.001
        if "XAU" in pair_normalized or "GOLD" in pair_normalized: return 0.01
        return 0.00001

    def _get_price_precision(self, symbol: str) -> int:
        pair_normalized = symbol.upper()
        if "JPY" in pair_normalized: return 3
        if "XAU" in pair_normalized or "GOLD" in pair_normalized: return 2
        return 5

    def _get_pip_value_for_sl_tp(self, symbol: str) -> float:
        # This is the value of 1 pip for SL/TP calculations in price terms
        pair_normalized = symbol.upper()
        if "JPY" in pair_normalized: return 0.01
        # For XAUUSD, 1 pip is often considered $0.10 if contract size is 100 oz and price is per oz.
        # If point size is 0.01, then a "pip" for XAU might be 10 points or $0.10.
        # Or if "pip" for XAU means the second decimal (like other pairs with 0.01 point size), then it's 0.01.
        # For simplicity, let's assume "pip" for XAU here refers to the second decimal place (same as JPY pairs).
        if "XAU" in pair_normalized or "GOLD" in pair_normalized: return 0.01
        return 0.0001


    def _get_spread_in_price_terms(self, symbol: str) -> float:
        pips = self.default_spread_pips.get(symbol.upper(), 1.0)
        pip_price_unit = self._get_pip_value_for_sl_tp(symbol) # 0.0001 for EURUSD, 0.01 for USDJPY
        return pips * pip_price_unit

    def _calculate_commission(self, symbol: str, volume_lots: float) -> float:
        # commission_per_lot is round-turn.
        return self.commission_per_lot.get(symbol.upper(), 0.0) * volume_lots

    def _calculate_margin_required(self, symbol: str, volume_lots: float, entry_price: float) -> float:
        contract_size = 100000
        notional_value = volume_lots * contract_size * entry_price
        # This is simplified; proper calculation depends on whether symbol base is account currency.
        # E.g., if trading EURUSD on a USD account, notional value is in USD (volume_lots * 100k EUR * EURUSD_price).
        # If trading USDJPY on a USD account, notional value is in JPY (volume_lots * 100k USD), which then needs to be converted if leverage applies to the base.
        # Standard Forex margin: (Market Price * Volume in Base Currency) / Leverage, result in Quote currency. Then convert to Account currency.
        # For simplicity, assuming Quote currency is USD or conversion is handled implicitly by "entry_price".
        return notional_value / self.leverage

    def update_current_time(self, simulated_time_unix: float):
        self.current_simulated_time_unix = simulated_time_unix

    def update_market_data(self, market_data: Dict[str, Candlestick]):
        self.current_market_data = market_data
        self._update_equity_and_margin() # Update P/L and equity after new prices

    def connect(self, credentials: Dict[str, Any]) -> bool:
        print("SimulatedBroker: connect() called (always successful).")
        self._connected = True
        return True

    def disconnect(self) -> None:
        print("SimulatedBroker: disconnect() called.")
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_current_price(self, symbol: str) -> Optional[PriceTick]:
        # This should use self.current_market_data (current bar) to derive a PriceTick
        # print(f"SimulatedBroker: get_current_price({symbol}) called for time {datetime.datetime.fromtimestamp(self.current_simulated_time_unix, tz=datetime.timezone.utc).isoformat()}")
        current_bar = self.current_market_data.get(symbol)
        if not current_bar:
            # Fallback to very basic static prices if no current bar data (e.g., for initial tests)
            if symbol == "EURUSD": base_bid = 1.08500
            elif symbol == "GBPUSD": base_bid = 1.27100
            else: print(f"SimulatedBroker: No current bar data or fallback static price for {symbol}"); return None
            spread = self._get_spread_in_price_terms(symbol)
            return PriceTick(symbol=symbol, timestamp=self.current_simulated_time_unix, bid=base_bid, ask=base_bid + spread, last=base_bid + (spread/2))

        # Derive tick from current bar's close, applying spread
        # This assumes get_current_price is called *after* new bar data is available for the "current" moment
        spread_amount = self._get_spread_in_price_terms(symbol)
        bid_price = round(current_bar['close'] - (spread_amount / 2.0), self._get_price_precision(symbol))
        ask_price = round(current_bar['close'] + (spread_amount / 2.0), self._get_price_precision(symbol))

        return PriceTick(
            symbol=symbol,
            timestamp=self.current_simulated_time_unix,
            bid=bid_price,
            ask=ask_price,
            last=current_bar['close']
        )

    def get_historical_data(self, symbol: str, timeframe_str: str,
                              start_time_unix: float, end_time_unix: Optional[float] = None,
                              count: Optional[int] = None) -> List[Candlestick]:
        # print(f"SimulatedBroker: get_historical_data({symbol}, {timeframe_str}, from {datetime.datetime.fromtimestamp(start_time_unix, tz=datetime.timezone.utc).isoformat()} to {datetime.datetime.fromtimestamp(end_time_unix, tz=datetime.timezone.utc).isoformat() if end_time_unix else 'N/A (count based)'}, count={count}) called.")
        dummy_bars: List[Candlestick] = []
        time_step_seconds = self._get_timeframe_seconds_approx(timeframe_str) # Using internal helper now

        actual_end_time = end_time_unix if end_time_unix is not None else self.current_simulated_time_unix

        if count is not None:
            num_bars_to_generate = count
            current_bar_start_time_unix = actual_end_time - time_step_seconds
        else:
            if actual_end_time < start_time_unix: return []
            num_bars_to_generate = int((actual_end_time - start_time_unix) / time_step_seconds)
            current_bar_start_time_unix = actual_end_time - time_step_seconds

        for i in range(num_bars_to_generate):
            bar_open_timestamp = current_bar_start_time_unix - (i * time_step_seconds)
            if bar_open_timestamp < start_time_unix: continue

            idx_from_oldest = num_bars_to_generate - 1 - i
            base_price = 1.0700 + (idx_from_oldest * 0.0001) # Example for EURUSD like pair
            if "JPY" in symbol.upper(): base_price = 150.00 + (idx_from_oldest * 0.01)
            elif "XAU" in symbol.upper(): base_price = 2300.00 + (idx_from_oldest * 0.1)


            precision = self._get_price_precision(symbol)
            open_val = round(base_price + (random.uniform(-0.0005, 0.0005) if "JPY" not in symbol.upper() else random.uniform(-0.05,0.05)), precision)
            close_val = round(base_price + (random.uniform(-0.0005, 0.0005) if "JPY" not in symbol.upper() else random.uniform(-0.05,0.05)), precision)
            high_val = round(max(open_val, close_val) + (random.uniform(0,0.0003) if "JPY" not in symbol.upper() else random.uniform(0,0.03)), precision)
            low_val = round(min(open_val, close_val) - (random.uniform(0,0.0003) if "JPY" not in symbol.upper() else random.uniform(0,0.03)), precision)

            dummy_bars.append(Candlestick(
                timestamp=bar_open_timestamp, open=open_val, high=high_val, low=low_val, close=close_val,
                volume=float(1000 + (idx_from_oldest * 10) + random.randint(-100, 100))
            ))

        dummy_bars.sort(key=lambda x: x['timestamp'])
        final_bars = [bar for bar in dummy_bars if bar['timestamp'] >= start_time_unix and bar['timestamp'] < actual_end_time]
        # print(f"SimulatedBroker: Returning {len(final_bars)} dummy bars for {symbol}.")
        return final_bars

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int: # Copied from agent for now
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60
        if "M5" == timeframe_str: return 5 * 60
        if "M15" == timeframe_str: return 15 * 60
        if "M30" == timeframe_str: return 30 * 60
        if "H1" == timeframe_str: return 60 * 60
        if "H4" == timeframe_str: return 4 * 60 * 60
        if "D1" == timeframe_str: return 24 * 60 * 60
        return 60 * 60

    def get_account_info(self) -> Optional[AccountInfo]:
        if not self.is_connected(): return None
        # _update_equity_and_margin() # Call this if it's not called by an external loop frequently

        free_margin = self.equity - self.margin_used
        margin_level = (self.equity / self.margin_used * 100) if self.margin_used > 0 else float('inf')

        return AccountInfo(
            account_id=self._generate_unique_id()[:8], # Short UID for account
            balance=round(self.balance, 2),
            equity=round(self.equity, 2),
            margin=round(self.margin_used, 2),
            free_margin=round(free_margin, 2),
            margin_level=round(margin_level, 2) if margin_level != float('inf') else float('inf'),
            currency="USD"
        )

    def place_order(self, symbol: str, order_type: OrderType, side: OrderSide, volume: float,
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None, time_in_force: TimeInForce = TimeInForce.GTC,
                      magic_number: Optional[int] = 0, comment: Optional[str] = "") -> OrderResponse:

        order_id = self._generate_unique_id()
        timestamp_unix = self.current_simulated_time_unix

        if not self.is_connected():
            return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Broker not connected.")

        if symbol not in self.current_market_data or not self.current_market_data[symbol]:
            return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message=f"Market data not available for {symbol} at {datetime.datetime.fromtimestamp(timestamp_unix, tz=datetime.timezone.utc).isoformat()}.")

        current_bar = self.current_market_data[symbol]
        price_precision = self._get_price_precision(symbol)

        if order_type == OrderType.MARKET:
            fill_price_base = current_bar['close']
            spread_amount = self._get_spread_in_price_terms(symbol)
            point_size = self._get_point_size(symbol)
            slippage_in_price = self.fixed_slippage_pips * point_size

            entry_price_final: float
            if side == OrderSide.BUY:
                entry_price_final = fill_price_base + (spread_amount / 2) # Ask
                entry_price_final += random.uniform(0, slippage_in_price)
            elif side == OrderSide.SELL:
                entry_price_final = fill_price_base - (spread_amount / 2) # Bid
                entry_price_final -= random.uniform(0, slippage_in_price)
            else: # Should not happen with Enum
                 return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Invalid order side.")

            entry_price_final = round(entry_price_final, price_precision)

            margin_for_this_trade = self._calculate_margin_required(symbol, volume, entry_price_final)
            current_acc_info = self.get_account_info() # This calls _update_equity_and_margin internally if designed so, or relies on external calls.
                                                 # For this flow, let's assume get_account_info provides current free_margin.
            if not current_acc_info or current_acc_info['free_margin'] < margin_for_this_trade:
                 return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=entry_price_final, timestamp=timestamp_unix, error_message=f"Insufficient free margin. Need: {margin_for_this_trade:.2f}, Have: {current_acc_info['free_margin'] if current_acc_info else 'N/A'}")

            commission_cost = self._calculate_commission(symbol, volume)
            position_id = self._generate_unique_id()

            new_position = Position(
                position_id=position_id, symbol=symbol, side=side, volume=volume,
                entry_price=entry_price_final, current_price=entry_price_final,
                profit_loss= -commission_cost, # Initial P/L
                stop_loss=stop_loss, take_profit=take_profit, open_time=timestamp_unix,
                magic_number=magic_number, comment=comment
            )
            self.open_positions[position_id] = new_position

            self.balance -= commission_cost
            self.margin_used += margin_for_this_trade
            self._update_equity_and_margin() # Update equity immediately after balance/margin change

            self.trade_history.append({
                "event_type": "MARKET_ORDER_FILLED", "timestamp": timestamp_unix, "order_id": order_id,
                "position_id": position_id, "symbol": symbol, "side": side.value,
                "volume": volume, "fill_price": entry_price_final, "sl": stop_loss, "tp": take_profit,
                "commission": commission_cost, "comment": comment
            })
            print(f"SimBroker: {side.value} {volume} {symbol} @ {entry_price_final} (spread/slip incl). PosID: {position_id}. Comm: {commission_cost:.2f}")

            return OrderResponse(
                order_id=order_id, status="FILLED", symbol=symbol, side=side, type=order_type,
                volume=volume, price=entry_price_final, timestamp=timestamp_unix, error_message=None,
                position_id=position_id
            )

        elif order_type in [OrderType.LIMIT, OrderType.STOP]:
            if price is None:
                return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Price required for pending orders.")

            # Inside place_order method
            elif order_type in [OrderType.LIMIT, OrderType.STOP]:
                if price is None:
                    return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Price required for pending orders.")

                # Store comprehensive details including SL/TP in self.pending_orders
                self.pending_orders[order_id] = {
                    "order_id": order_id,
                    "status": "PENDING", # This is the status of the order itself
                    "symbol": symbol,
                    "side": side, # OrderSide Enum
                    "type": order_type, # OrderType Enum
                    "volume": volume,
                    "price": price, # Activation price
                    "timestamp": timestamp_unix, # Placement time
                    "stop_loss": stop_loss, # SL for the future position
                    "take_profit": take_profit, # TP for the future position
                    "magic_number": magic_number, # Store these too
                    "comment": comment
                    # error_message is not typically part of the stored pending order, but for the response
                }

                self.trade_history.append({
                    "event_type": "PENDING_ORDER_PLACED",
                    "timestamp": timestamp_unix,
                    "order_id": order_id,
                    "symbol": symbol,
                    "side": side.value, # Log enum value
                    "type": order_type.value, # Log enum value
                    "volume": volume,
                    "price": price,
                    "sl": stop_loss,
                    "tp": take_profit,
                    "comment": comment
                })
                print(f"SimBroker: Pending {side.value} {order_type.value} for {volume} {symbol} @ {price} SL:{stop_loss} TP:{take_profit} placed. OrderID: {order_id}")

                # Return standard OrderResponse (which may not have SL/TP fields)
                return OrderResponse(
                    order_id=order_id, status="PENDING", symbol=symbol, side=side, type=order_type,
                    volume=volume, price=price, timestamp=timestamp_unix, error_message=None
                )

        return OrderResponse(order_id=order_id, status="REJECTED", symbol=symbol, side=side, type=order_type, volume=volume, price=price, timestamp=timestamp_unix, error_message="Unsupported order type in place_order.")

    def process_pending_orders(self):
        # Checks all pending orders against the current bar for trigger conditions.
        if not self.current_market_data or not self.current_simulated_time_unix:
            print("SimBroker.process_pending_orders: Market data or time not set.")
            return

        orders_to_remove_after_processing = []

        for order_id, pending_order_details in list(self.pending_orders.items()):
            symbol = pending_order_details['symbol']
            if symbol not in self.current_market_data or not self.current_market_data[symbol]:
                continue

            bar = self.current_market_data[symbol]
            order_price = pending_order_details['price']
            order_type: OrderType = pending_order_details['type']
            order_side: OrderSide = pending_order_details['side']
            order_volume = pending_order_details['volume']

            # Retrieve SL/TP, magic, comment from the stored pending order details
            sl_for_position = pending_order_details.get('stop_loss')
            tp_for_position = pending_order_details.get('take_profit')
            magic_for_position = pending_order_details.get('magic_number')
            comment_for_position = pending_order_details.get('comment', f"Filled from pending {order_id}")

            fill_price_simulated: Optional[float] = None
            price_precision = self._get_price_precision(symbol)

            if order_type == OrderType.LIMIT:
                if order_side == OrderSide.BUY and bar['low'] <= order_price:
                    fill_price_simulated = min(order_price, bar['open'])
                elif order_side == OrderSide.SELL and bar['high'] >= order_price:
                    fill_price_simulated = max(order_price, bar['open'])

            elif order_type == OrderType.STOP:
                if order_side == OrderSide.BUY and bar['high'] >= order_price:
                    fill_price_simulated = max(order_price, bar['open'])
                elif order_side == OrderSide.SELL and bar['low'] <= order_price:
                    fill_price_simulated = min(order_price, bar['open'])

            if fill_price_simulated is not None:
                fill_price_simulated = round(fill_price_simulated, price_precision)
                print(f"SimBroker: Pending order {order_id} ({symbol} {order_side.value} {order_type.value} @ {order_price}) TRIGGERED at simulated price {fill_price_simulated}.")

                timestamp_unix = self.current_simulated_time_unix

                # Apply slippage to the trigger price for the actual fill
                actual_fill_price = fill_price_simulated
                slippage_amount = self.fixed_slippage_pips * self._get_point_size(symbol)
                if order_type == OrderType.STOP: # Stop orders are prone to slippage
                    if order_side == OrderSide.BUY: actual_fill_price += random.uniform(0, slippage_amount)
                    else: actual_fill_price -= random.uniform(0, slippage_amount)
                actual_fill_price = round(actual_fill_price, price_precision)


                margin_for_this_trade = self._calculate_margin_required(symbol, order_volume, actual_fill_price)
                # Use a temporary get_account_info call to get current free margin
                # This is not ideal as get_account_info might call _update_equity_and_margin
                # A better way is to directly access self.equity and self.margin_used
                free_margin = self.equity - self.margin_used
                if free_margin < margin_for_this_trade:
                    print(f"SimBroker: Insufficient margin to fill pending order {order_id}. Need: {margin_for_this_trade:.2f}, Have: {free_margin:.2f}. Order removed.")
                    self.trade_history.append({
                        "event_type": "PENDING_ORDER_FAIL_MARGIN", "timestamp": timestamp_unix,
                        "order_id": order_id, "symbol": symbol, "side": order_side.value, "volume": order_volume,
                        "trigger_price": fill_price_simulated, "reason": "Insufficient margin"
                    })
                    orders_to_remove_after_processing.append(order_id)
                    continue

                commission = self._calculate_commission(symbol, order_volume)

                position_id = self._generate_unique_id()
                new_position = Position(
                    position_id=position_id, symbol=symbol, side=order_side, volume=order_volume,
                    entry_price=actual_fill_price,
                    current_price=actual_fill_price,
                    profit_loss= -commission,
                    stop_loss=sl_for_position,
                    take_profit=tp_for_position,
                    open_time=timestamp_unix,
                    magic_number=magic_for_position,
                    comment=comment_for_position
                )
                self.open_positions[position_id] = new_position

                self.balance -= commission
                self.margin_used += margin_for_this_trade

                self.trade_history.append({
                    "event_type": "PENDING_ORDER_FILLED", "timestamp": timestamp_unix,
                    "original_order_id": order_id, "position_id": position_id, "symbol": symbol,
                    "side": order_side.value, "type": order_type.value, "volume": order_volume,
                    "requested_price": order_price, "fill_price": actual_fill_price,
                    "sl": sl_for_position, "tp": tp_for_position, "commission": commission,
                    "comment": comment_for_position
                })
                print(f"SimBroker: Pending order {order_id} FILLED. New PosID: {position_id} for {symbol} {order_side.value} {order_volume} @ {actual_fill_price}. Comm: {commission:.2f}")

                orders_to_remove_after_processing.append(order_id)

        for order_id_to_remove in orders_to_remove_after_processing:
            if order_id_to_remove in self.pending_orders:
                del self.pending_orders[order_id_to_remove]

        # Call _update_equity_and_margin() once after all bar events are processed by backtester main loop
        # self._update_equity_and_margin() # Not here, but in main loop after this and SL/TP checks

    def _update_equity_and_margin(self):
        current_total_pnl = 0.0
        current_total_margin_used = 0.0 # Recalculate margin used based on open positions
        contract_size = 100000

        positions_to_remove = []

        for pos_id, pos_dict in self.open_positions.items():
            # Convert dict to Position TypedDict for safety if necessary, or ensure it's always stored as TypedDict
            pos = Position(**pos_dict) if isinstance(pos_dict, dict) else pos_dict

            current_bar = self.current_market_data.get(pos.symbol)
            if not current_bar:
                # If no current market data for an open position's symbol, P/L cannot be updated accurately.
                # Keep its last known P/L or handle as error/stale data.
                # For now, just add its last known P/L.
                current_total_pnl += pos.profit_loss
                current_total_margin_used += self._calculate_margin_required(pos.symbol, pos.volume, pos.entry_price) # Margin is on entry
                continue

            market_price_for_pnl = current_bar['close'] # Use close for P/L calculation
            spread_amount = self._get_spread_in_price_terms(pos.symbol)

            price_diff = 0.0
            current_exit_price_for_pos: float
            if pos.side == OrderSide.BUY:
                current_exit_price_for_pos = market_price_for_pnl - (spread_amount / 2) # Current Bid
                price_diff = current_exit_price_for_pos - pos.entry_price
            else: # SELL
                current_exit_price_for_pos = market_price_for_pnl + (spread_amount / 2) # Current Ask
                price_diff = pos.entry_price - current_exit_price_for_pos

            # P/L calculation needs to be accurate.
            # Simplified: (price_difference / point_size) * pip_value_in_account_currency * volume_in_lots * points_per_pip
            # Or (price_difference * contract_size_units * volume_in_lots) * (conversion_to_account_currency)
            # The prompt used: price_diff * pos.volume * contract_size. This assumes quote currency = account currency.
            pos_pnl_no_commission = price_diff * pos.volume * contract_size

            # Commission was already deducted from balance. P/L should reflect market movement.
            # So, the 'profit_loss' field in Position should be market_pnl.
            # The initial -commission in profit_loss was to reflect immediate equity change.
            # When updating, we calculate fresh market P/L. The "total P/L" for equity is this market P/L.
            # Commission is a one-off hit to balance.

            self.open_positions[pos_id]['profit_loss'] = pos_pnl_no_commission # Market P/L
            self.open_positions[pos_id]['current_price'] = current_exit_price_for_pos # Reflects realistic exit
            current_total_pnl += pos_pnl_no_commission

            # Margin for this position (recalculate, though usually fixed at entry unless rules change)
            current_total_margin_used += self._calculate_margin_required(pos.symbol, pos.volume, pos.entry_price)

        self.equity = self.balance + current_total_pnl
        self.margin_used = current_total_margin_used
        # print(f"SimBroker: Equity updated. Balance: {self.balance:.2f}, Total P/L: {current_total_pnl:.2f}, Equity: {self.equity:.2f}, Margin Used: {self.margin_used:.2f}")


    def modify_order(self, order_id: str, new_price: Optional[float] = None,
                       new_stop_loss: Optional[float] = None, new_take_profit: Optional[float] = None) -> OrderResponse:
        print(f"SimulatedBroker: modify_order({order_id}) called. SL:{new_stop_loss} TP:{new_take_profit}")
        if order_id in self.open_positions:
            pos = self.open_positions[order_id]
            if new_stop_loss is not None: pos['stop_loss'] = new_stop_loss
            if new_take_profit is not None: pos['take_profit'] = new_take_profit
            self.open_positions[order_id] = pos # Update the position dict
            return OrderResponse(order_id=order_id, status="MODIFIED", symbol=pos['symbol'], side=pos['side'], type=OrderType.MARKET, volume=pos['volume'], price=pos['entry_price'], timestamp=self.current_simulated_time_unix, position_id=order_id)
        elif order_id in self.pending_orders:
            # Logic for modifying pending orders (not fully implemented in this step)
            # self.pending_orders[order_id]['stop_loss'] = new_stop_loss ...
            return OrderResponse(order_id=order_id, status="MODIFIED_PENDING", symbol=self.pending_orders[order_id]['symbol'], side=self.pending_orders[order_id]['side'], type=self.pending_orders[order_id]['type'], volume=self.pending_orders[order_id]['volume'], price=self.pending_orders[order_id]['price'], timestamp=self.current_simulated_time_unix)
        return OrderResponse(order_id=order_id, status="REJECTED", error_message="Order/Position not found for modification.")

    def close_order(self, order_id: str, volume: Optional[float] = None, price: Optional[float] = None) -> OrderResponse:
        print(f"SimulatedBroker: close_order({order_id}, vol={volume}) called.")
        if order_id not in self.open_positions:
            return OrderResponse(order_id=order_id, status="REJECTED", error_message="Position not found to close.")

        pos_to_close_dict = self.open_positions[order_id]
        pos_to_close = Position(**pos_to_close_dict) # Ensure TypedDict for access

        # Use current market price for closing, including spread
        current_bar = self.current_market_data.get(pos_to_close.symbol)
        if not current_bar:
            return OrderResponse(order_id=order_id, status="REJECTED", symbol=pos_to_close.symbol, error_message="Market data not available to close position.")

        spread_amount = self._get_spread_in_price_terms(pos_to_close.symbol)
        close_price_base = current_bar['close']

        final_close_price: float
        if pos_to_close.side == OrderSide.BUY: # Closing a BUY means SELLING
            final_close_price = close_price_base - (spread_amount / 2) # Bid
        else: # Closing a SELL means BUYING
            final_close_price = close_price_base + (spread_amount / 2) # Ask

        final_close_price = round(final_close_price, self._get_price_precision(pos_to_close.symbol))

        # P/L calculation for the closed trade
        price_diff = 0.0
        if pos_to_close.side == OrderSide.BUY:
            price_diff = final_close_price - pos_to_close.entry_price
        else: # SELL
            price_diff = pos_to_close.entry_price - final_close_price

        # P/L = price_diff * volume_units. Assuming volume is in lots.
        contract_size = 100000
        realized_pnl = price_diff * pos_to_close.volume * contract_size # Simplified, assumes quote currency = account currency

        # Update account: balance reflects realized P/L. Margin for this trade is freed.
        self.balance += realized_pnl # Commission was already paid from balance at open.
        self.margin_used -= self._calculate_margin_required(pos_to_close.symbol, pos_to_close.volume, pos_to_close.entry_price)

        del self.open_positions[order_id]
        self._update_equity_and_margin() # Update overall equity and margin

        self.trade_history.append({
            "event_type": "POSITION_CLOSED", "timestamp": self.current_simulated_time_unix,
            "position_id": order_id, "symbol": pos_to_close.symbol, "side": pos_to_close.side.value,
            "volume": pos_to_close.volume, "entry_price": pos_to_close.entry_price, "close_price": final_close_price,
            "realized_pnl": realized_pnl, "comment": "Position closed by request."
        })
        print(f"SimBroker: Position {order_id} ({pos_to_close.symbol}) closed @ {final_close_price}. Realized P/L: {realized_pnl:.2f}")

        return OrderResponse(
            order_id=order_id, # Original order_id that opened position, or position_id itself if different
            status="CLOSED", symbol=pos_to_close.symbol, side=pos_to_close.side, type=OrderType.MARKET, # Type of closing order
            volume=pos_to_close.volume, price=final_close_price, timestamp=self.current_simulated_time_unix,
            position_id=order_id, # Redundant if order_id is same as pos_id
            error_message=None
        )

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Position]:
        # print(f"SimulatedBroker: get_open_positions({symbol if symbol else 'all'}) called.")
        self._update_equity_and_margin() # Ensure P/L is current
        positions = []
        for pos_data in self.open_positions.values():
            # Ensure it's a TypedDict before appending
            pos = Position(**pos_data) if isinstance(pos_data, dict) else pos_data
            if symbol is None or pos.symbol == symbol:
                positions.append(pos)
        return positions

    def get_pending_orders(self, symbol: Optional[str] = None) -> List[OrderResponse]:
        # print(f"SimulatedBroker: get_pending_orders({symbol if symbol else 'all'}) called.")
        orders = []
        for order_data in self.pending_orders.values():
            order = OrderResponse(**order_data) if isinstance(order_data, dict) else order_data
            if symbol is None or order.symbol == symbol:
                orders.append(order)
        return orders

    # Add this new method
    def check_for_sl_tp_triggers(self):
        # Checks all open positions against the current bar's data for SL/TP triggers.
        # This should be called by the backtester event loop for each new bar
        # BEFORE the strategy/agents generate new signals for that bar.
        if not self.current_market_data or not self.current_simulated_time_unix:
            print("SimBroker.check_for_sl_tp_triggers: Market data or time not set.")
            return

        positions_to_action = []

        for pos_id, pos_data in list(self.open_positions.items()): # Iterate on list copy for safe modification
            # Ensure pos is a Position TypedDict instance for type safety if it's stored as dict
            pos = Position(**pos_data) if isinstance(pos_data, dict) else pos_data

            if pos.symbol not in self.current_market_data or not self.current_market_data[pos.symbol]:
                # print(f"SimBroker.check_for_sl_tp_triggers: No current market data for symbol {pos.symbol} of position {pos_id}")
                continue

            bar = self.current_market_data[pos.symbol]
            trigger_price = None
            reason_for_close = None

            if pos.side == OrderSide.BUY:
                if pos.stop_loss is not None and bar['low'] <= pos.stop_loss:
                    trigger_price = pos.stop_loss
                    reason_for_close = "STOP_LOSS_HIT"
                elif pos.take_profit is not None and bar['high'] >= pos.take_profit:
                    trigger_price = pos.take_profit
                    reason_for_close = "TAKE_PROFIT_HIT"

            elif pos.side == OrderSide.SELL:
                if pos.stop_loss is not None and bar['high'] >= pos.stop_loss:
                    trigger_price = pos.stop_loss
                    reason_for_close = "STOP_LOSS_HIT"
                elif pos.take_profit is not None and bar['low'] <= pos.take_profit:
                    trigger_price = pos.take_profit
                    reason_for_close = "TAKE_PROFIT_HIT"

            if trigger_price is not None and reason_for_close is not None:
                positions_to_action.append({
                    "position_id": pos_id, # Keep original pos_id for reference
                    "position_to_close": pos,
                    "close_price": trigger_price,
                    "reason": reason_for_close
                })

        for action_item in positions_to_action:
            # Pass the actual Position object, not just its ID
            self._close_position_at_price(
                position=action_item["position_to_close"],
                close_price=action_item["close_price"],
                reason=action_item["reason"]
            )

    # Add this new internal helper method
    def _close_position_at_price(self, position: Position, close_price: float, reason: str):
        # Ensure position_id is correctly accessed from the Position TypedDict
        current_position_id = position.position_id

        if current_position_id not in self.open_positions:
            print(f"SimBroker: Position {current_position_id} already actioned or does not exist. Cannot close for reason: {reason}.")
            return

        contract_size = 100000
        price_diff = 0.0

        # Assuming SL/TP orders execute AT these prices without further spread/slippage for this sim level.
        if position.side == OrderSide.BUY:
            price_diff = close_price - position.entry_price
        elif position.side == OrderSide.SELL:
            price_diff = position.entry_price - close_price

        # Placeholder P/L - requires robust pip/point value calculation based on pair and account currency
        realized_pnl = price_diff * position.volume * contract_size

        self.balance += realized_pnl

        # Ensure Position TypedDict has 'open_time' and optionally 'comment'
        # Safely access using .get() for fields that might be missing from some Position dicts if not strictly enforced
        open_time_for_log = position.get('open_time', self.current_simulated_time_unix)
        comment_for_log = position.get('comment', "")
        magic_number_for_log = position.get('magic_number', 0)


        self.trade_history.append({
            "event_type": "POSITION_CLOSED",
            "timestamp": self.current_simulated_time_unix,
            "position_id": current_position_id,
            "symbol": position.symbol,
            "side": position.side.value,
            "volume": position.volume,
            "entry_price": position.entry_price,
            "open_time": open_time_for_log,
            "close_price": close_price,
            "realized_pnl": realized_pnl,
            "reason_for_close": reason,
            "magic_number": magic_number_for_log,
            "comment": comment_for_log
        })

        # Margin for this position is now freed
        margin_freed = self._calculate_margin_required(position.symbol, position.volume, position.entry_price)
        self.margin_used -= margin_freed
        if self.margin_used < 0: self.margin_used = 0 # Prevent negative margin

        removed_pos_dict = self.open_positions.pop(current_position_id, None)

        if removed_pos_dict:
            print(f"SimBroker: Position {current_position_id} ({position.symbol} {position.side.value} {position.volume} lot(s)) CLOSED at {close_price} by {reason}. P/L: {realized_pnl:.2f}. Margin Freed: {margin_freed:.2f}")
            self._update_equity_and_margin()
        else:
            # This case should ideally not be hit if logic is correct, as we check current_position_id in self.open_positions
            print(f"SimBroker Warning: Tried to log/update for position {current_position_id} but it was not found in open_positions after pop attempt.")

```
