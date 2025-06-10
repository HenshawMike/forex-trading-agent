from typing import Dict, Any, Optional, Tuple
from tradingagents.forex_utils.forex_states import ForexSubAgentTask, ForexTradeProposal, OrderSide
from tradingagents.broker_interface.base import BrokerInterface # Import the ABC
import datetime
import traceback # For printing tracebacks
import pandas as pd
import pandas_ta as ta

class DayTraderAgent:
    def __init__(self,
                 broker: BrokerInterface,
                 agent_id: str = "DayTraderAgent_1",
                 publisher: Any = None,
                 timeframe: str = "H1",
                 num_bars_to_fetch: int = 100,
                 ema_short_period: int = 12,
                 ema_long_period: int = 26,
                 rsi_period: int = 14,
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 macd_fast: int = 12,
                 macd_slow: int = 26,
                 macd_signal: int = 9,
                 stop_loss_pips: int = 20,
                 take_profit_pips: int = 40
                ):
        self.broker = broker
        self.agent_id = agent_id
        self.publisher = publisher
        self.timeframe = timeframe
        self.num_bars_to_fetch = num_bars_to_fetch

        # Strategy Parameters
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.stop_loss_pips = stop_loss_pips
        self.take_profit_pips = take_profit_pips

        print(f"{self.agent_id} initialized with broker. Timeframe: {self.timeframe}, Bars: {self.num_bars_to_fetch}, Strategy Params: EMA({self.ema_short_period}/{self.ema_long_period}), RSI({self.rsi_period}), MACD({self.macd_fast}/{self.macd_slow}/{self.macd_signal})")
        print(f"Broker type: {type(self.broker)}")

    # Helper method for SL/TP calculation based on pair characteristics
    def _calculate_pip_value_and_precision(self, currency_pair: str) -> tuple[float, int]:
        pair_normalized = currency_pair.upper()
        if "JPY" in pair_normalized:
            return 0.01, 3
        elif "XAU" in pair_normalized or "GOLD" in pair_normalized: # Example for Gold
            return 0.01, 2
        else: # Most FX pairs
            return 0.0001, 5

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        timeframe_str = timeframe_str.upper() # Ensure consistent casing
        if "M1" == timeframe_str: return 60
        if "M5" == timeframe_str: return 5 * 60
        if "M15" == timeframe_str: return 15 * 60
        if "M30" == timeframe_str: return 30 * 60
        if "H1" == timeframe_str: return 60 * 60
        if "H4" == timeframe_str: return 4 * 60 * 60
        if "D1" == timeframe_str: return 24 * 60 * 60
        print(f"Warning: Unknown timeframe '{timeframe_str}', defaulting to 1 hour for duration calculation.")
        return 60 * 60 # Default to 1 hour if unknown

    def process_task(self, state: Dict) -> Dict:
        task: Optional[ForexSubAgentTask] = state.get("current_day_trader_task")
        # Initialize supporting_data for the proposal early
        supporting_data_for_proposal = {"params_used": {"timeframe": self.timeframe, "num_bars": self.num_bars_to_fetch, "ema_s": self.ema_short_period, "ema_l": self.ema_long_period, "rsi_p": self.rsi_period}}

        if not task:
            print(f"{self.agent_id}: No current_day_trader_task found in state.")
            current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()
            error_proposal = ForexTradeProposal(
                proposal_id=f"prop_day_err_{current_time_iso_prop.replace(':', '-')}",
                source_agent_type="DayTrader", currency_pair="Unknown", timestamp=current_time_iso_prop,
                signal="HOLD", entry_price=None, stop_loss=None, take_profit=None, confidence_score=0.0,
                rationale=f"{self.agent_id}: Task not found in state.", sub_agent_risk_level="Unknown",
                supporting_data=supporting_data_for_proposal # Include params even in error
            )
            return {"day_trader_proposal": error_proposal, "error": f"{self.agent_id}: Task not found."}

        currency_pair = task['currency_pair']
        task_id = task['task_id']

        current_simulated_time_iso = state.get("current_simulated_time")
        data_message = "No data fetching attempt due to missing simulated time."
        historical_data = None # Initialize

        if not current_simulated_time_iso:
            print(f"{self.agent_id}: current_simulated_time not found in state for task {task_id}.")
        else:
            print(f"{self.agent_id}: Processing task '{task_id}' for {currency_pair} at simulated time {current_simulated_time_iso}.")
            print(f"{self.agent_id}: Using broker: {self.broker}, Timeframe: {self.timeframe}, Bars to fetch: {self.num_bars_to_fetch}")

            try:
                decision_time_dt = datetime.datetime.fromisoformat(current_simulated_time_iso.replace('Z', '+00:00'))
                decision_time_unix = decision_time_dt.timestamp()
                timeframe_duration_seconds = self._get_timeframe_seconds_approx(self.timeframe)
                end_historical_data_request_unix = decision_time_unix
                start_historical_data_request_unix = end_historical_data_request_unix - (self.num_bars_to_fetch * timeframe_duration_seconds)

                print(f"{self.agent_id}: Requesting historical data for {currency_pair} from {datetime.datetime.fromtimestamp(start_historical_data_request_unix, tz=datetime.timezone.utc)} to {datetime.datetime.fromtimestamp(end_historical_data_request_unix, tz=datetime.timezone.utc)}")

                # The broker interface is expected to return List[Dict] where each Dict is like a Candlestick TypedDict
                fetched_data_list = self.broker.get_historical_data(
                    symbol=currency_pair, timeframe_str=self.timeframe,
                    start_time_unix=start_historical_data_request_unix,
                    end_time_unix=end_historical_data_request_unix
                )

                if fetched_data_list: # Check if list is not None and not empty
                    historical_data = fetched_data_list # Assign to the variable initialized earlier
                    data_message = f"Fetched {len(historical_data)} bars for {currency_pair}."
                    if len(historical_data) > 0:
                        first_bar_time = datetime.datetime.fromtimestamp(historical_data[0].get('timestamp',0), tz=datetime.timezone.utc)
                        last_bar_time = datetime.datetime.fromtimestamp(historical_data[-1].get('timestamp',0), tz=datetime.timezone.utc)
                        data_message += f" Data from ~{first_bar_time.isoformat()} to ~{last_bar_time.isoformat()}."
                else:
                    data_message = f"No historical data fetched for {currency_pair} (broker returned None or empty list)."
                print(f"{self.agent_id}: {data_message}")

            except Exception as e:
                print(f"{self.agent_id}: Error during data fetching for {currency_pair}: {e}")
                data_message = f"Error fetching data: {e}"
                traceback.print_exc()

        # --- START OF NEW TA CALCULATION LOGIC ---
        ta_message = "TA not performed."
        latest_indicators = {}

        if historical_data and len(historical_data) >= self.ema_long_period: # Check if enough data for longest EMA
            try:
                print(f"{self.agent_id}: Converting fetched data to DataFrame for TA...")
                df = pd.DataFrame(historical_data)
                # Ensure 'timestamp' column exists before using it
                if 'timestamp' not in df.columns:
                    raise ValueError("DataFrame from broker is missing 'timestamp' column.")
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                df.set_index('timestamp', inplace=True)

                # Ensure correct column names if they differ from pandas_ta defaults
                # pandas_ta typically expects 'open', 'high', 'low', 'close', 'volume'
                # Standardize column names if necessary, e.g., df.rename(columns={'bid_open': 'open', ...}, inplace=True)
                # For now, assume columns are named as expected by pandas_ta or that Candlestick TypedDict aligns.

                print(f"{self.agent_id}: Calculating TA indicators...")
                df.ta.rsi(length=self.rsi_period, append=True, col_names=(f'RSI_{self.rsi_period}',))
                df.ta.ema(length=self.ema_short_period, append=True, col_names=(f'EMA_{self.ema_short_period}',))
                df.ta.ema(length=self.ema_long_period, append=True, col_names=(f'EMA_{self.ema_long_period}',))
                df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal, append=True,
                           col_names=(f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                      f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                      f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'))

                if not df.empty and not df.iloc[-1].empty: # Check if last row is not empty
                    # Store latest indicator values (last row)
                    last_row = df.iloc[-1]
                    rsi_col_name = f'RSI_{self.rsi_period}'
                    ema_s_col_name = f'EMA_{self.ema_short_period}'
                    ema_l_col_name = f'EMA_{self.ema_long_period}'
                    macd_line_col_name = f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                    macd_signal_col_name = f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                    macd_hist_col_name = f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'

                    latest_indicators = {
                        rsi_col_name: round(last_row[rsi_col_name], 2) if rsi_col_name in last_row and pd.notna(last_row[rsi_col_name]) else None,
                        ema_s_col_name: round(last_row[ema_s_col_name], 5) if ema_s_col_name in last_row and pd.notna(last_row[ema_s_col_name]) else None,
                        ema_l_col_name: round(last_row[ema_l_col_name], 5) if ema_l_col_name in last_row and pd.notna(last_row[ema_l_col_name]) else None,
                        # Renaming MACD parts for clarity in supporting_data
                        'MACD_line': round(last_row[macd_line_col_name], 5) if macd_line_col_name in last_row and pd.notna(last_row[macd_line_col_name]) else None,
                        'MACD_signal_line': round(last_row[macd_signal_col_name], 5) if macd_signal_col_name in last_row and pd.notna(last_row[macd_signal_col_name]) else None,
                        'MACD_histogram': round(last_row[macd_hist_col_name], 5) if macd_hist_col_name in last_row and pd.notna(last_row[macd_hist_col_name]) else None,
                    }
                    ta_message = f"TA calculated. Latest RSI: {latest_indicators.get(rsi_col_name)}"
                    print(f"{self.agent_id}: {ta_message}")
                    # Add all calculated indicators to supporting_data
                    supporting_data_for_proposal.update(latest_indicators) # latest_indicators already has good keys
                else:
                    ta_message = "DataFrame was empty or last row was empty after TA calculation."
                    print(f"{self.agent_id}: {ta_message}")

            except Exception as e:
                print(f"{self.agent_id}: Error during TA calculation for {currency_pair}: {e}")
                ta_message = f"Error during TA calculation: {e}"
                traceback.print_exc()
        elif historical_data: # Data fetched but not enough for TA
            ta_message = f"Insufficient data for TA (got {len(historical_data)} bars, need >= {self.ema_long_period})."
            print(f"{self.agent_id}: {ta_message}")
        else: # No historical data was fetched
             ta_message = "TA not performed as no historical data was available."
             print(f"{self.agent_id}: {ta_message}")
        # --- END OF NEW TA CALCULATION LOGIC ---

        # --- START OF NEW STRATEGY RULE LOGIC ---
        final_signal = "HOLD"
        final_confidence = 0.5 # Default confidence for HOLD
        strategy_rationale_parts = [f"Strategy based on EMA({self.ema_short_period}/{self.ema_long_period}), RSI({self.rsi_period}), MACD({self.macd_fast},{self.macd_slow},{self.macd_signal})."]

        # Ensure all needed indicators are available before applying rules
        required_indicators = [
            f'EMA_{self.ema_short_period}', f'EMA_{self.ema_long_period}',
            f'RSI_{self.rsi_period}', 'MACD_line', 'MACD_signal_line' # Corrected: 'MACD_signal' to 'MACD_signal_line' to match key in latest_indicators
        ]

        # Check if latest_indicators has all required keys and they are not None
        indicators_present = all(indicator_key in latest_indicators and latest_indicators[indicator_key] is not None for indicator_key in required_indicators)

        if not latest_indicators or not indicators_present:
            strategy_rationale_parts.append("Not all indicators available for strategy evaluation.")
            print(f"{self.agent_id}: Skipping strategy rules due to missing indicators. {latest_indicators}")
        else:
            # Retrieve indicator values
            ema_short = latest_indicators[f'EMA_{self.ema_short_period}']
            ema_long = latest_indicators[f'EMA_{self.ema_long_period}']
            rsi = latest_indicators[f'RSI_{self.rsi_period}']
            macd_line = latest_indicators['MACD_line']
            macd_signal_line = latest_indicators['MACD_signal_line'] # Corrected

            # Buy Condition
            is_ema_bullish = ema_short > ema_long
            is_rsi_not_overbought = rsi < self.rsi_overbought
            is_macd_bullish = macd_line > macd_signal_line

            # Sell Condition
            is_ema_bearish = ema_short < ema_long
            is_rsi_not_oversold = rsi > self.rsi_oversold
            is_macd_bearish = macd_line < macd_signal_line

            if is_ema_bullish and is_rsi_not_overbought and is_macd_bullish:
                final_signal = "BUY"
                final_confidence = 0.75 # Example confidence for BUY
                strategy_rationale_parts.append("BUY signal: EMAs bullish crossover/orientation.")
                strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is below overbought ({self.rsi_overbought}).")
                strategy_rationale_parts.append("MACD line is above signal line (bullish).")
            elif is_ema_bearish and is_rsi_not_oversold and is_macd_bearish:
                final_signal = "SELL"
                final_confidence = 0.70 # Example confidence for SELL
                strategy_rationale_parts.append("SELL signal: EMAs bearish crossover/orientation.")
                strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is above oversold ({self.rsi_oversold}).")
                strategy_rationale_parts.append("MACD line is below signal line (bearish).")
            else:
                final_signal = "HOLD"
                final_confidence = 0.5
                strategy_rationale_parts.append("HOLD signal: Conditions for BUY or SELL not met.")
                if not is_ema_bullish and not is_ema_bearish and ema_short is not None and ema_long is not None : strategy_rationale_parts.append("EMAs are not clearly trending or are crossed over.") # Added None check
                if is_rsi_not_overbought is False : strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is in overbought territory.")
                if is_rsi_not_oversold is False : strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is in oversold territory.")
                if not is_macd_bullish and not is_macd_bearish and macd_line is not None and macd_signal_line is not None: strategy_rationale_parts.append("MACD is neutral or conflicting.") # Added None check


        print(f"{self.agent_id}: Strategy decision: {final_signal}, Confidence: {final_confidence}")
        strategy_rationale_message = " ".join(strategy_rationale_parts)
        # --- END OF NEW STRATEGY RULE LOGIC ---

        # --- START OF NEW PRICE/SL/TP CALCULATION LOGIC ---
        entry_price_calc: Optional[float] = None
        stop_loss_calc: Optional[float] = None
        take_profit_calc: Optional[float] = None
        price_calculation_message = "SL/TP not calculated for HOLD signal."

        if final_signal in ["BUY", "SELL"]:
            # Ensure currency_pair is defined in this scope; it should be from the 'task' object.
            if not currency_pair: # currency_pair should be from task['currency_pair']
                 price_calculation_message = "Currency pair not available for price fetching."
                 print(f"{self.agent_id}: {price_calculation_message}")
            else:
                current_tick_data = self.broker.get_current_price(currency_pair) # Returns a PriceTick TypedDict or None

                if current_tick_data and current_tick_data.get('ask') is not None and current_tick_data.get('bid') is not None:
                    pip_value, price_precision = self._calculate_pip_value_and_precision(currency_pair)

                    if final_signal == "BUY":
                        entry_price_calc = round(current_tick_data['ask'], price_precision)
                        stop_loss_calc = round(entry_price_calc - (self.stop_loss_pips * pip_value), price_precision)
                        take_profit_calc = round(entry_price_calc + (self.take_profit_pips * pip_value), price_precision)
                    elif final_signal == "SELL":
                        entry_price_calc = round(current_tick_data['bid'], price_precision)
                        stop_loss_calc = round(entry_price_calc + (self.stop_loss_pips * pip_value), price_precision)
                        take_profit_calc = round(entry_price_calc - (self.take_profit_pips * pip_value), price_precision)

                    price_calculation_message = f"Entry: {entry_price_calc}, SL: {stop_loss_calc}, TP: {take_profit_calc} (pips SL: {self.stop_loss_pips}, TP: {self.take_profit_pips})."
                    print(f"{self.agent_id}: {price_calculation_message}")
                else:
                    price_calculation_message = f"Could not get valid current tick data (ask/bid) for {currency_pair} to calculate SL/TP. Signal was {final_signal}."
                    print(f"{self.agent_id}: {price_calculation_message}")
                    # Optionally revert signal to HOLD if prices can't be fetched for a tradeable signal
                    # final_signal = "HOLD"
                    # final_confidence = 0.3 # Reduce confidence
                    # strategy_rationale_message += " Reverted to HOLD due to price fetch error for SL/TP."
        # --- END OF NEW PRICE/SL/TP CALCULATION LOGIC ---

        current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # Ensure supporting_data_for_proposal is initialized and updated
        # supporting_data_for_proposal should have been initialized at the start of process_task
        supporting_data_for_proposal["final_signal_determined"] = final_signal
        supporting_data_for_proposal["final_confidence_determined"] = final_confidence
        # strategy_rationale_message should be from the strategy block
        supporting_data_for_proposal["strategy_rationale_details"] = strategy_rationale_message
        supporting_data_for_proposal["price_calculation_info"] = price_calculation_message

        # These should be from earlier in process_task. Ensure they have default values if execution skipped those parts.
        data_fetch_msg = supporting_data_for_proposal.get("data_fetch_info", "Data fetch info N/A.")
        ta_calc_msg = supporting_data_for_proposal.get("ta_calculation_info", "TA calculation info N/A.")

        trade_proposal = ForexTradeProposal(
            proposal_id=f"prop_day_{currency_pair if currency_pair else 'UNKPAIR'}_{current_time_iso_prop.replace(':', '-')}",
            source_agent_type="DayTrader",
            currency_pair=currency_pair if currency_pair else "Unknown",
            timestamp=current_time_iso_prop,
            signal=final_signal,
            entry_price=entry_price_calc, # Use calculated value
            stop_loss=stop_loss_calc,   # Use calculated value
            take_profit=take_profit_calc, # Use calculated value
            take_profit_2=None,
            confidence_score=final_confidence,
            # Combine all rationales. strategy_rationale_message should already be quite comprehensive.
            rationale=f"Strategy: {strategy_rationale_message} PriceCalc: {price_calculation_message} Data: {data_fetch_msg} TA: {ta_calc_msg}",
            sub_agent_risk_level="Medium" if final_signal not in ["HOLD", None] else "Low",
            supporting_data=supporting_data_for_proposal
        )

        return {"day_trader_proposal": trade_proposal}
