from typing import Dict, Any, Optional
from tradingagents.forex_utils.forex_states import ForexSubAgentTask, ForexTradeProposal
from tradingagents.broker_interface.base import BrokerInterface # Import the ABC
import datetime
import traceback # For printing tracebacks
import pandas as pd
import pandas_ta as ta

class SwingTraderAgent:
    def __init__(self,
                 broker: BrokerInterface,
                 agent_id: str = "SwingTraderAgent_1",
                 publisher: Any = None,
                 timeframe: str = "D1", # Default for Swing Trader
                 num_bars_to_fetch: int = 200, # More bars for longer-term view
                 ema_short_period: int = 20,  # e.g., 20-day EMA
                 ema_long_period: int = 50,   # e.g., 50-day EMA
                 rsi_period: int = 14,
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 macd_fast: int = 12,
                 macd_slow: int = 26,
                 macd_signal: int = 9,
                 stop_loss_pips: int = 150, # Wider SL for swing trades
                 take_profit_pips: int = 300 # Wider TP for swing trades
                ):
        self.broker = broker
        self.agent_id = agent_id
        self.publisher = publisher

        # Strategy Parameters
        self.timeframe = timeframe
        self.num_bars_to_fetch = num_bars_to_fetch
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

        print(f"{self.agent_id} initialized with broker. Timeframe: {self.timeframe}, Bars: {self.num_bars_to_fetch}, EMAs: ({self.ema_short_period}/{self.ema_long_period}), SL_pips: {self.stop_loss_pips}, TP_pips: {self.take_profit_pips}")
        print(f"Broker type: {type(self.broker)}")

    # Helper method (can be shared or moved to a utility if used by many agents)
    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60
        if "M5" == timeframe_str: return 5 * 60
        if "M15" == timeframe_str: return 15 * 60
        if "M30" == timeframe_str: return 30 * 60
        if "H1" == timeframe_str: return 60 * 60
        if "H4" == timeframe_str: return 4 * 60 * 60
        if "D1" == timeframe_str: return 24 * 60 * 60
        print(f"Warning: Unknown timeframe '{timeframe_str}' in _get_timeframe_seconds_approx for {self.agent_id}, defaulting to 1 day.")
        return 24 * 60 * 60 # Default to 1 day if unknown

    def process_task(self, state: Dict) -> Dict:
        task: Optional[ForexSubAgentTask] = state.get("current_swing_trader_task")

        # Initialize supporting_data for the proposal early
        supporting_data_for_proposal = {
            "params_used": {
                "timeframe": self.timeframe, "num_bars": self.num_bars_to_fetch,
                "ema_s": self.ema_short_period, "ema_l": self.ema_long_period,
                "rsi_p": self.rsi_period, "sl_pips": self.stop_loss_pips, "tp_pips": self.take_profit_pips,
                "macd_f": self.macd_fast, "macd_s": self.macd_slow, "macd_sig": self.macd_signal
            }
        }

        if not task:
            print(f"{self.agent_id}: No current_swing_trader_task found in state.")
            current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()
            error_proposal = ForexTradeProposal(
                proposal_id=f"prop_swing_err_{current_time_iso_prop.replace(':', '-')}",
                source_agent_type="SwingTrader", currency_pair="Unknown", timestamp=current_time_iso_prop,
                signal="HOLD", entry_price=None, stop_loss=None, take_profit=None, confidence_score=0.0,
                rationale=f"{self.agent_id}: Task not found in state.", sub_agent_risk_level="Unknown",
                supporting_data=supporting_data_for_proposal
            )
            return {"swing_trader_proposal": error_proposal, "error": f"{self.agent_id}: Task not found."}

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

                print(f"{self.agent_id}: Requesting historical data for {currency_pair} from {datetime.datetime.fromtimestamp(start_historical_data_request_unix, tz=datetime.timezone.utc).isoformat()} to {datetime.datetime.fromtimestamp(end_historical_data_request_unix, tz=datetime.timezone.utc).isoformat()}")

                fetched_data_list = self.broker.get_historical_data(
                    symbol=currency_pair, timeframe_str=self.timeframe,
                    start_time_unix=start_historical_data_request_unix,
                    end_time_unix=end_historical_data_request_unix
                )

                if fetched_data_list:
                    historical_data = fetched_data_list
                    data_message = f"Fetched {len(historical_data)} bars for {currency_pair}."
                    # Check if timestamps exist before trying to access them
                    if len(historical_data) > 0 and historical_data[0].get('timestamp') is not None and historical_data[-1].get('timestamp') is not None:
                        first_bar_time = datetime.datetime.fromtimestamp(historical_data[0]['timestamp'], tz=datetime.timezone.utc)
                        last_bar_time = datetime.datetime.fromtimestamp(historical_data[-1]['timestamp'], tz=datetime.timezone.utc)
                        data_message += f" Data from ~{first_bar_time.isoformat()} to ~{last_bar_time.isoformat()}."
                else:
                    data_message = f"No historical data fetched for {currency_pair} (broker returned None or empty list)."
                print(f"{self.agent_id}: {data_message}")

            except Exception as e:
                print(f"{self.agent_id}: Error during data fetching for {currency_pair}: {e}")
                data_message = f"Error fetching data: {e}"
                traceback.print_exc()

        # --- START OF NEW TA CALCULATION LOGIC FOR SWINGTRADER ---
        ta_message = "TA not performed."
        latest_indicators = {} # Initialize to empty dict

        # Check if historical_data is not None and has enough data for the longest EMA
        if historical_data and len(historical_data) >= self.ema_long_period:
            try:
                print(f"{self.agent_id}: Converting fetched data to DataFrame for TA...")
                df = pd.DataFrame(historical_data)
                # Ensure 'timestamp' column exists before using it
                if 'timestamp' not in df.columns:
                    raise ValueError("DataFrame created from historical_data is missing 'timestamp' column.")

                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                df.set_index('timestamp', inplace=True)

                # Ensure required OHLC columns exist
                required_ohlc = ['open', 'high', 'low', 'close']
                if not all(col in df.columns for col in required_ohlc):
                    raise ValueError(f"DataFrame is missing one or more required OHLC columns: {required_ohlc}")

                print(f"{self.agent_id}: Calculating TA indicators for Swing Trading (EMAs: {self.ema_short_period}/{self.ema_long_period}, RSI: {self.rsi_period})...")
                df.ta.rsi(length=self.rsi_period, append=True, col_names=(f'RSI_{self.rsi_period}',))
                df.ta.ema(length=self.ema_short_period, append=True, col_names=(f'EMA_{self.ema_short_period}',))
                df.ta.ema(length=self.ema_long_period, append=True, col_names=(f'EMA_{self.ema_long_period}',))
                df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal, append=True,
                           col_names=(f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                      f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                      f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'))

                if not df.empty and not df.iloc[-1].empty:
                    last_row = df.iloc[-1]
                    rsi_col_name = f'RSI_{self.rsi_period}'
                    ema_s_col_name = f'EMA_{self.ema_short_period}'
                    ema_l_col_name = f'EMA_{self.ema_long_period}'
                    macd_line_col_name = f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                    macd_signal_col_name = f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}' # Corrected key for MACD Signal
                    macd_hist_col_name = f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'


                    latest_indicators = {
                        rsi_col_name: round(last_row[rsi_col_name], 2) if rsi_col_name in last_row and pd.notna(last_row[rsi_col_name]) else None,
                        ema_s_col_name: round(last_row[ema_s_col_name], 5) if ema_s_col_name in last_row and pd.notna(last_row[ema_s_col_name]) else None,
                        ema_l_col_name: round(last_row[ema_l_col_name], 5) if ema_l_col_name in last_row and pd.notna(last_row[ema_l_col_name]) else None,
                        'MACD_line': round(last_row[macd_line_col_name], 5) if macd_line_col_name in last_row and pd.notna(last_row[macd_line_col_name]) else None,
                        'MACD_signal_line': round(last_row[macd_signal_col_name], 5) if macd_signal_col_name in last_row and pd.notna(last_row[macd_signal_col_name]) else None, # Corrected key name for proposal
                        'MACD_histogram': round(last_row[macd_hist_col_name], 5) if macd_hist_col_name in last_row and pd.notna(last_row[macd_hist_col_name]) else None, # Corrected key name for proposal
                    }
                    ta_message = f"TA calculated for Swing. Latest RSI: {latest_indicators.get(rsi_col_name)}"
                    print(f"{self.agent_id}: {ta_message}")
                else:
                    ta_message = "DataFrame was empty or last row was empty after TA calculation attempts."
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
        # --- END OF NEW TA CALCULATION LOGIC FOR SWINGTRADER ---

        # Update supporting_data (already done before this block by instructions)
        supporting_data_for_proposal["data_fetch_info"] = data_message
        supporting_data_for_proposal["ta_calculation_info"] = ta_message
        supporting_data_for_proposal.update(latest_indicators)


        # --- START OF NEW SWING TRADING STRATEGY RULE LOGIC ---
        final_signal = "HOLD"
        final_confidence = 0.5 # Default confidence for HOLD
        # Use more descriptive parameter names in rationale
        strategy_rationale_parts = [f"Swing Strategy based on EMA({self.ema_short_period}/{self.ema_long_period}), RSI({self.rsi_period}, OB:{self.rsi_overbought},OS:{self.rsi_oversold}), MACD({self.macd_fast},{self.macd_slow},{self.macd_signal})."]

        required_indicators = [
            f'EMA_{self.ema_short_period}', f'EMA_{self.ema_long_period}',
            f'RSI_{self.rsi_period}', 'MACD_line', 'MACD_signal_line' # Corrected to 'MACD_signal_line'
        ]

        indicators_present = all(indicator_key in latest_indicators and latest_indicators[indicator_key] is not None for indicator_key in required_indicators)

        if not latest_indicators or not indicators_present:
            strategy_rationale_parts.append("Not all indicators available for swing strategy evaluation.")
            print(f"{self.agent_id}: Skipping swing strategy rules due to missing indicators. {latest_indicators}")
        else:
            ema_short = latest_indicators[f'EMA_{self.ema_short_period}']
            ema_long = latest_indicators[f'EMA_{self.ema_long_period}']
            rsi = latest_indicators[f'RSI_{self.rsi_period}']
            macd_line = latest_indicators['MACD_line']
            macd_signal_line = latest_indicators['MACD_signal_line'] # Corrected to 'MACD_signal_line'

            # Swing Trading Conditions (can be more nuanced than Day Trader)
            # Example: Trend following with EMA orientation, confirmed by MACD, and RSI not at extremes.

            # Buy Condition: Longer trend (EMA_long) is generally respected, shorter EMA above longer, MACD bullish.
            is_uptrend_ema = ema_short > ema_long
            # For swing, RSI might stay in OB/OS longer, so use slightly wider or just as confirmation.
            is_rsi_ok_for_buy = rsi < self.rsi_overbought # Default: not overbought
            is_macd_bullish = macd_line > macd_signal_line

            # Sell Condition: Longer trend (EMA_long) respected, shorter EMA below longer, MACD bearish.
            is_downtrend_ema = ema_short < ema_long
            is_rsi_ok_for_sell = rsi > self.rsi_oversold # Default: not oversold
            is_macd_bearish = macd_line < macd_signal_line

            if is_uptrend_ema and is_rsi_ok_for_buy and is_macd_bullish:
                final_signal = "BUY"
                final_confidence = 0.70 # Swing trades might have slightly different confidence scaling
                strategy_rationale_parts.append("BUY signal: EMA orientation bullish (short > long).")
                strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is not extremely overbought (Limit: {self.rsi_overbought}).")
                strategy_rationale_parts.append("MACD is bullish (line > signal).")
            elif is_downtrend_ema and is_rsi_ok_for_sell and is_macd_bearish:
                final_signal = "SELL"
                final_confidence = 0.65
                strategy_rationale_parts.append("SELL signal: EMA orientation bearish (short < long).")
                strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is not extremely oversold (Limit: {self.rsi_oversold}).")
                strategy_rationale_parts.append("MACD is bearish (line < signal).")
            else:
                final_signal = "HOLD"
                final_confidence = 0.5
                strategy_rationale_parts.append("HOLD signal: Swing conditions for BUY or SELL not met.")
                # Add more specific reasons for HOLD if desired for debugging
                if not is_uptrend_ema and not is_downtrend_ema and ema_short is not None and ema_long is not None: strategy_rationale_parts.append("EMA short/long are close or crossed opposite to other signals.")
                if is_uptrend_ema and not (is_rsi_ok_for_buy and is_macd_bullish): strategy_rationale_parts.append("EMA bullish but RSI/MACD not confirming swing buy.")
                if is_downtrend_ema and not (is_rsi_ok_for_sell and is_macd_bearish): strategy_rationale_parts.append("EMA bearish but RSI/MACD not confirming swing sell.")


        print(f"{self.agent_id}: Swing Strategy decision: {final_signal}, Confidence: {final_confidence}")
        strategy_rationale_message = " ".join(strategy_rationale_parts)
        # --- END OF NEW SWING TRADING STRATEGY RULE LOGIC ---

        # --- START OF NEW PRICE/SL/TP CALCULATION LOGIC FOR SWINGTRADER ---
        entry_price_calc: Optional[float] = None
        stop_loss_calc: Optional[float] = None
        take_profit_calc: Optional[float] = None
        price_calculation_message = "SL/TP not calculated for HOLD signal."

        if final_signal in ["BUY", "SELL"]:
            # Ensure currency_pair is defined in this scope
            if not currency_pair: # currency_pair should be from task['currency_pair']
                 price_calculation_message = "Currency pair not available for price fetching."
                 print(f"{self.agent_id}: {price_calculation_message}")
            else:
                current_tick_data = self.broker.get_current_price(currency_pair)

                if current_tick_data and current_tick_data.get('ask') is not None and current_tick_data.get('bid') is not None:
                    pip_value, price_precision = self._calculate_pip_value_and_precision(currency_pair)

                    if final_signal == "BUY":
                        entry_price_calc = round(current_tick_data['ask'], price_precision)
                        # Use self.stop_loss_pips and self.take_profit_pips specific to SwingTrader
                        stop_loss_calc = round(entry_price_calc - (self.stop_loss_pips * pip_value), price_precision)
                        take_profit_calc = round(entry_price_calc + (self.take_profit_pips * pip_value), price_precision)
                    elif final_signal == "SELL":
                        entry_price_calc = round(current_tick_data['bid'], price_precision)
                        stop_loss_calc = round(entry_price_calc + (self.stop_loss_pips * pip_value), price_precision)
                        take_profit_calc = round(entry_price_calc - (self.take_profit_pips * pip_value), price_precision)

                    price_calculation_message = f"Entry: {entry_price_calc}, SL: {stop_loss_calc}, TP: {take_profit_calc} (pips SL: {self.stop_loss_pips}, TP: {self.take_profit_pips} for Swing)."
                    print(f"{self.agent_id}: {price_calculation_message}")
                else:
                    price_calculation_message = f"Could not get valid current tick data (ask/bid) for {currency_pair} to calculate SL/TP. Signal was {final_signal}."
                    print(f"{self.agent_id}: {price_calculation_message}")
                    # Optionally revert signal to HOLD or reduce confidence if prices can't be fetched
                    # For now, we'll let the proposal go through with None prices if fetch fails,
                    # which the MetaAgent might then handle.
        # --- END OF NEW PRICE/SL/TP CALCULATION LOGIC FOR SWINGTRADER ---

        # Update the ForexTradeProposal creation:
        current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # supporting_data_for_proposal should have been initialized and updated earlier
        supporting_data_for_proposal["final_signal_determined"] = final_signal
        supporting_data_for_proposal["final_confidence_determined"] = final_confidence
        supporting_data_for_proposal["strategy_rationale_details"] = strategy_rationale_message # From strategy block
        supporting_data_for_proposal["price_calculation_info"] = price_calculation_message

        data_fetch_msg = supporting_data_for_proposal.get("data_fetch_info", "Data fetch info N/A.")
        ta_calc_msg = supporting_data_for_proposal.get("ta_calculation_info", "TA calculation info N/A.")

        trade_proposal = ForexTradeProposal(
            proposal_id=f"prop_swing_{currency_pair if currency_pair else 'UNKPAIR'}_{current_time_iso_prop.replace(':', '-')}",
            source_agent_type="SwingTrader",
            currency_pair=currency_pair if currency_pair else "Unknown",
            timestamp=current_time_iso_prop,
            signal=final_signal,
            entry_price=entry_price_calc, # Use calculated value
            stop_loss=stop_loss_calc,   # Use calculated value
            take_profit=take_profit_calc, # Use calculated value
            take_profit_2=None,
            confidence_score=final_confidence,
            rationale=f"SwingTraderAgent: {strategy_rationale_message} PriceCalc: {price_calculation_message} (Data: {data_fetch_msg} TA: {ta_calc_msg})",
            sub_agent_risk_level="High" if final_signal not in ["HOLD", None] else "Low",
            supporting_data=supporting_data_for_proposal
        )

        print(f"{self.agent_id}: Generated proposal for {currency_pair} after strategy evaluation.") # Consistent print message

        return {"swing_trader_proposal": trade_proposal}
