from typing import Dict, Any, Optional, Tuple # Added Tuple
from tradingagents.forex_utils.forex_states import ForexSubAgentTask, ForexTradeProposal, OrderSide # Added OrderSide
from tradingagents.broker_interface.base import BrokerInterface
import datetime
import pandas as pd # Will be needed soon
import pandas_ta as ta # Will be needed soon
import traceback # For potential error logging in future steps

class ScalperAgent:
    def __init__(self,
                 broker: BrokerInterface,
                 agent_id: str = "ScalperAgent_1",
                 publisher: Any = None,
                 timeframe: str = "M1", # Default for Scalper
                 num_bars_to_fetch: int = 30, # Fewer bars for scalping
                 ema_short_period: int = 5,
                 ema_long_period: int = 10,
                 rsi_period: int = 7,
                 rsi_oversold: int = 25, # Tighter OS/OB for scalping
                 rsi_overbought: int = 75,
                 # MACD might be too slow for M1 scalping, consider removing or using very fast settings
                 # For now, keeping similar structure if we want to try
                 macd_fast: int = 5,
                 macd_slow: int = 12,
                 macd_signal: int = 3,
                 stop_loss_pips: float = 5.0, # Can be float for fractional pips
                 take_profit_pips: float = 8.0,
                 max_allowable_spread_pips: float = 1.0 # Critical for scalpers
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
        self.max_allowable_spread_pips = max_allowable_spread_pips

        print(f"{self.agent_id} initialized. Broker: {type(self.broker)}, TF: {self.timeframe}, Bars: {self.num_bars_to_fetch}, EMAs: ({self.ema_short_period}/{self.ema_long_period}), SL: {self.stop_loss_pips}, TP: {self.take_profit_pips}, MaxSpread: {self.max_allowable_spread_pips}")

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        # (Identical to other agents, consider moving to a shared utility later)
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60
        if "M5" == timeframe_str: return 5 * 60
        if "M15" == timeframe_str: return 15 * 60
        if "M30" == timeframe_str: return 30 * 60
        if "H1" == timeframe_str: return 60 * 60
        if "H4" == timeframe_str: return 4 * 60 * 60
        if "D1" == timeframe_str: return 24 * 60 * 60
        print(f"Warning: Unknown timeframe '{timeframe_str}' in _get_timeframe_seconds_approx for {self.agent_id}, defaulting to 1 minute.")
        return 60

    def _calculate_pip_value_and_precision(self, currency_pair: str) -> Tuple[float, int]:
        # (Identical to other agents, consider moving to a shared utility later)
        pair_normalized = currency_pair.upper()
        if "JPY" in pair_normalized:
            return 0.01, 3
        elif "XAU" in pair_normalized or "GOLD" in pair_normalized:
            return 0.01, 2
        else:
            return 0.0001, 5

    def process_task(self, state: Dict) -> Dict:
        task: Optional[ForexSubAgentTask] = state.get("current_scalper_task") # Expected key for this agent

        supporting_data_for_proposal = {
            "params_used": {
                "timeframe": self.timeframe, "num_bars": self.num_bars_to_fetch,
                "ema_s": self.ema_short_period, "ema_l": self.ema_long_period,
                "rsi_p": self.rsi_period, "rsi_os": self.rsi_oversold, "rsi_ob": self.rsi_overbought,
                "macd_f": self.macd_fast, "macd_s": self.macd_slow, "macd_sig": self.macd_signal,
                "sl_pips": self.stop_loss_pips, "tp_pips": self.take_profit_pips,
                "max_spread": self.max_allowable_spread_pips
            }
        }

        if not task:
            print(f"{self.agent_id}: No current_scalper_task found in state.")
            current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()
            error_proposal = ForexTradeProposal(
                proposal_id=f"prop_scalp_err_{current_time_iso_prop.replace(':', '-')}",
                source_agent_type="ScalperAgent", currency_pair="Unknown", timestamp=current_time_iso_prop,
                signal="HOLD", entry_price=None, stop_loss=None, take_profit=None, confidence_score=0.0,
                rationale=f"{self.agent_id}: Task not found in state.", sub_agent_risk_level="Unknown",
                supporting_data=supporting_data_for_proposal
            )
            return {"scalper_proposal": error_proposal, "error": f"{self.agent_id}: Task not found."}

        currency_pair = task['currency_pair']
        task_id = task['task_id']

        current_simulated_time_iso = state.get("current_simulated_time")
        data_message = "No data fetching attempt due to missing simulated time."
        spread_check_message = "Spread check not performed."
        historical_data = None

        if not current_simulated_time_iso:
            print(f"{self.agent_id}: current_simulated_time not found in state for task {task_id}.")
        else:
            print(f"{self.agent_id}: Processing task '{task_id}' for {currency_pair} at simulated time {current_simulated_time_iso}.")
            print(f"{self.agent_id}: Config - TF:{self.timeframe}, Bars:{self.num_bars_to_fetch}, MaxSpread:{self.max_allowable_spread_pips} pips")

            # 1. Spread Check (Crucial for Scalpers)
            try:
                current_tick = self.broker.get_current_price(currency_pair) # Expected PriceTick TypedDict
                if current_tick and current_tick.get('ask') is not None and current_tick.get('bid') is not None:
                    ask_price = current_tick['ask']
                    bid_price = current_tick['bid']
                    spread_price_terms = ask_price - bid_price

                    one_pip_in_price_terms = 0.01 if "JPY" in currency_pair.upper() else 0.0001
                    max_spread_value_in_price_terms = self.max_allowable_spread_pips * one_pip_in_price_terms

                    if spread_price_terms > max_spread_value_in_price_terms:
                        spread_check_message = f"Spread too wide! Current: {spread_price_terms:.5f} > Max Allowed: {max_spread_value_in_price_terms:.5f}. No trade."
                        print(f"{self.agent_id}: {spread_check_message}")
                    else:
                        spread_check_message = f"Spread OK: {spread_price_terms:.5f} <= {max_spread_value_in_price_terms:.5f}."
                        print(f"{self.agent_id}: {spread_check_message}")
                else:
                    spread_check_message = "Could not get current tick or bid/ask for spread check."
                    print(f"{self.agent_id}: {spread_check_message}")
            except Exception as e:
                spread_check_message = f"Error during spread check: {e}"
                print(f"{self.agent_id}: {spread_check_message}")
                # traceback.print_exc()

            # 2. Data Fetching
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

        # --- START OF NEW TA CALCULATION LOGIC FOR SCALPER ---
        ta_message = "TA not performed."
        latest_indicators = {} # Initialize to empty dict

        if historical_data and len(historical_data) >= self.ema_long_period:
            try:
                if "Spread too wide!" in spread_check_message:
                    ta_message = "TA skipped due to wide spread."
                    print(f"{self.agent_id}: {ta_message}")
                else:
                    print(f"{self.agent_id}: Converting fetched data to DataFrame for TA...")
                    df = pd.DataFrame(historical_data)
                    if 'timestamp' not in df.columns:
                        raise ValueError("DataFrame created from historical_data is missing 'timestamp' column.")

                    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
                    df.set_index('timestamp', inplace=True)

                    required_ohlc = ['open', 'high', 'low', 'close']
                    if not all(col in df.columns for col in required_ohlc):
                        raise ValueError(f"DataFrame is missing one or more required OHLC columns: {required_ohlc}")

                    print(f"{self.agent_id}: Calculating TA indicators for Scalping (EMAs: {self.ema_short_period}/{self.ema_long_period}, RSI: {self.rsi_period})...")
                    df.ta.rsi(length=self.rsi_period, append=True, col_names=(f'RSI_{self.rsi_period}',))
                    df.ta.ema(length=self.ema_short_period, append=True, col_names=(f'EMA_{self.ema_short_period}',))
                    df.ta.ema(length=self.ema_long_period, append=True, col_names=(f'EMA_{self.ema_long_period}',))
                    # Optionally add MACD for M5 scalping, but might be slow for M1
                    # df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal, append=True,
                    #            col_names=(f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                    #                       f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                    #                       f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'))

                    if not df.empty and not df.iloc[-1].empty: # Check if last row is not empty
                        last_row = df.iloc[-1]
                        rsi_col_name = f'RSI_{self.rsi_period}'
                        ema_s_col_name = f'EMA_{self.ema_short_period}'
                        ema_l_col_name = f'EMA_{self.ema_long_period}'

                        current_pair_precision = self._calculate_pip_value_and_precision(currency_pair)[1]

                        latest_indicators = {
                            rsi_col_name: round(last_row[rsi_col_name], 2) if rsi_col_name in last_row and pd.notna(last_row[rsi_col_name]) else None,
                            ema_s_col_name: round(last_row[ema_s_col_name], current_pair_precision) if ema_s_col_name in last_row and pd.notna(last_row[ema_s_col_name]) else None,
                            ema_l_col_name: round(last_row[ema_l_col_name], current_pair_precision) if ema_l_col_name in last_row and pd.notna(last_row[ema_l_col_name]) else None,
                        }
                        # Add MACD if calculated
                        # macd_line_col = f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                        # macd_signal_col = f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                        # if macd_line_col in df.columns and macd_signal_col in df.columns: # Check if columns exist
                        #     latest_indicators['MACD_line'] = round(last_row[macd_line_col], current_pair_precision) if pd.notna(last_row[macd_line_col]) else None
                        #     latest_indicators['MACD_signal_line'] = round(last_row[macd_signal_col], current_pair_precision) if pd.notna(last_row[macd_signal_col]) else None

                        ta_message = f"TA calculated for Scalping. Latest RSI: {latest_indicators.get(rsi_col_name)}"
                        print(f"{self.agent_id}: {ta_message}")
                    else:
                        ta_message = "DataFrame was empty or last row was empty after TA calculation attempts."
                        print(f"{self.agent_id}: {ta_message}")

            except Exception as e:
                print(f"{self.agent_id}: Error during TA calculation for {currency_pair}: {e}")
                ta_message = f"Error during TA calculation: {e}"
                traceback.print_exc()
        elif historical_data:
            ta_message = f"Insufficient data for TA (got {len(historical_data)} bars, need >= {self.ema_long_period})."
            print(f"{self.agent_id}: {ta_message}")
        else:
            ta_message = "TA not performed as no historical data was available."
            print(f"{self.agent_id}: {ta_message}")
        # --- END OF NEW TA CALCULATION LOGIC FOR SCALPER ---

        # Update supporting_data with ta_info before strategy block, as strategy might use it
        supporting_data_for_proposal["data_fetch_info"] = data_message
        supporting_data_for_proposal["spread_check_info"] = spread_check_message
        supporting_data_for_proposal["ta_calculation_info"] = ta_message
        supporting_data_for_proposal.update(latest_indicators)

        # --- START OF NEW SCALPING STRATEGY RULE LOGIC ---
        final_signal = "HOLD"
        final_confidence = 0.5 # Default confidence for HOLD
        strategy_rationale_parts = [f"Scalping Strategy based on EMA({self.ema_short_period}/{self.ema_long_period}), RSI({self.rsi_period}, OB:{self.rsi_overbought},OS:{self.rsi_oversold}), MaxSpread:{self.max_allowable_spread_pips} pips."]

        # Critical Check: Was spread acceptable?
        # spread_check_message is from the data fetching phase
        if "Spread too wide!" in spread_check_message:
            strategy_rationale_parts.append(f"HOLD due to wide spread: {spread_check_message}")
            final_confidence = 0.3 # Lower confidence for forced HOLD due to spread
            print(f"{self.agent_id}: Strategy resulted in HOLD due to wide spread condition.")
        else:
            # Proceed with indicator-based strategy only if spread was OK
            required_indicators = [
                f'EMA_{self.ema_short_period}', f'EMA_{self.ema_long_period}',
                f'RSI_{self.rsi_period}'
                # Not including MACD for this basic scalper strategy for now
            ]

            indicators_present = all(indicator_key in latest_indicators and latest_indicators[indicator_key] is not None for indicator_key in required_indicators)

            if not latest_indicators or not indicators_present:
                strategy_rationale_parts.append("Not all indicators available for scalping strategy evaluation.")
                print(f"{self.agent_id}: Skipping scalping strategy rules due to missing indicators. {latest_indicators}")
            else:
                ema_short = latest_indicators[f'EMA_{self.ema_short_period}']
                ema_long = latest_indicators[f'EMA_{self.ema_long_period}']
                rsi = latest_indicators[f'RSI_{self.rsi_period}']

                # Scalping Conditions (very simple example)
                # Looking for quick momentum confirmed by short EMA alignment and RSI not at extremes.

                # Buy Condition: Short EMA above Long EMA (quick uptrend/momentum), RSI not overbought.
                is_ema_bullish = ema_short > ema_long
                is_rsi_ok_for_buy = rsi < self.rsi_overbought

                # Sell Condition: Short EMA below Long EMA (quick downtrend/momentum), RSI not oversold.
                is_ema_bearish = ema_short < ema_long
                is_rsi_ok_for_sell = rsi > self.rsi_oversold

                if is_ema_bullish and is_rsi_ok_for_buy:
                    final_signal = "BUY"
                    final_confidence = 0.65 # Scalping signals might have lower conviction due to noise
                    strategy_rationale_parts.append("BUY signal: Short EMA > Long EMA indicating upward momentum.")
                    strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is below overbought ({self.rsi_overbought}).")
                elif is_ema_bearish and is_rsi_ok_for_sell:
                    final_signal = "SELL"
                    final_confidence = 0.65
                    strategy_rationale_parts.append("SELL signal: Short EMA < Long EMA indicating downward momentum.")
                    strategy_rationale_parts.append(f"RSI ({rsi:.2f}) is above oversold ({self.rsi_oversold}).")
                else:
                    final_signal = "HOLD"
                    final_confidence = 0.5
                    strategy_rationale_parts.append("HOLD signal: Scalping conditions for BUY or SELL not met.")
                    if not (is_ema_bullish and is_rsi_ok_for_buy) and not (is_ema_bearish and is_rsi_ok_for_sell):
                        strategy_rationale_parts.append("EMA alignment or RSI conditions not favorable for entry.")

        print(f"{self.agent_id}: Scalping Strategy decision: {final_signal}, Confidence: {final_confidence}")
        strategy_rationale_message = " ".join(strategy_rationale_parts)
        # --- END OF NEW SCALPING STRATEGY RULE LOGIC ---

        # --- START OF NEW PRICE/SL/TP CALCULATION LOGIC FOR SCALPER ---
        entry_price_calc: Optional[float] = None
        stop_loss_calc: Optional[float] = None
        take_profit_calc: Optional[float] = None
        price_calculation_message = "SL/TP not calculated for HOLD signal or if spread was too wide."

        # Only proceed to get price and calculate SL/TP if signal is BUY/SELL
        # AND if the spread was acceptable (i.e., "Spread too wide!" is not in spread_check_message)
        if final_signal in ["BUY", "SELL"] and "Spread too wide!" not in spread_check_message:
            # Ensure currency_pair is defined
            if not currency_pair: # currency_pair should be from task['currency_pair']
                 price_calculation_message = "Currency pair not available for price fetching."
                 print(f"{self.agent_id}: {price_calculation_message}")
            else:
                current_tick_data = self.broker.get_current_price(currency_pair)

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

                    price_calculation_message = f"Entry: {entry_price_calc}, SL: {stop_loss_calc}, TP: {take_profit_calc} (pips SL: {self.stop_loss_pips}, TP: {self.take_profit_pips} for Scalping)."
                    print(f"{self.agent_id}: {price_calculation_message}")
                else:
                    price_calculation_message = f"Could not get valid current tick data (ask/bid) for {currency_pair} to calculate SL/TP. Signal was {final_signal}."
                    print(f"{self.agent_id}: {price_calculation_message}")
                    # If prices can't be fetched, revert to HOLD for safety, especially for scalping
                    # final_signal = "HOLD"
                    # final_confidence = 0.4 # Lower confidence
                    # strategy_rationale_message += " Reverted to HOLD: Price fetch error for SL/TP."
        elif final_signal in ["BUY", "SELL"] and "Spread too wide!" in spread_check_message:
            price_calculation_message = "SL/TP calculation skipped due to wide spread."
            # Signal should already be HOLD if spread was too wide from previous step, but double check or ensure consistency
            # final_signal = "HOLD" # Ensure it's HOLD
            # final_confidence = 0.3
        # --- END OF NEW PRICE/SL/TP CALCULATION LOGIC FOR SCALPER ---

        # Update the ForexTradeProposal creation:
        current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # supporting_data_for_proposal should have been initialized and updated earlier
        supporting_data_for_proposal["final_signal_determined"] = final_signal
        supporting_data_for_proposal["final_confidence_determined"] = final_confidence
        supporting_data_for_proposal["strategy_rationale_details"] = strategy_rationale_message # From strategy block
        supporting_data_for_proposal["price_calculation_info"] = price_calculation_message

        data_fetch_msg = supporting_data_for_proposal.get("data_fetch_info", "Data fetch info N/A.")
        # spread_check_message should be defined from earlier in process_task
        # It's already in supporting_data_for_proposal["spread_check_info"]
        spread_check_msg_local = supporting_data_for_proposal.get("spread_check_info", "Spread check info N/A.") # Use local var for rationale string
        ta_calc_msg = supporting_data_for_proposal.get("ta_calculation_info", "TA calculation info N/A.")

        trade_proposal = ForexTradeProposal(
            proposal_id=f"prop_scalp_{currency_pair if currency_pair else 'UNKPAIR'}_{current_time_iso_prop.replace(':', '-')}",
            source_agent_type="ScalperAgent",
            currency_pair=currency_pair if currency_pair else "Unknown",
            timestamp=current_time_iso_prop,
            signal=final_signal,
            entry_price=entry_price_calc, # Use calculated value
            stop_loss=stop_loss_calc,   # Use calculated value
            take_profit=take_profit_calc, # Use calculated value
            take_profit_2=None,
            confidence_score=final_confidence,
            rationale=f"ScalperAgent: {strategy_rationale_message} PriceCalc: {price_calculation_message} (Data: {data_fetch_msg} Spread: {spread_check_msg_local} TA: {ta_calc_msg})",
            sub_agent_risk_level="Medium" if final_signal not in ["HOLD", None] else "Low", # Scalping can still be medium risk per trade
            supporting_data=supporting_data_for_proposal
        )

        print(f"{self.agent_id}: Generated proposal for {currency_pair} after strategy evaluation.") # Consistent print message

        return {"scalper_proposal": trade_proposal}
