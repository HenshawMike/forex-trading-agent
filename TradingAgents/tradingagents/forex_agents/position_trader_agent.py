from typing import Dict, Any, Optional, Tuple
from tradingagents.forex_utils.forex_states import ForexSubAgentTask, ForexTradeProposal, OrderSide
from tradingagents.broker_interface.base import BrokerInterface
import datetime
import pandas as pd
import pandas_ta as ta
import traceback

class PositionTraderAgent:
    def __init__(self,
                 broker: BrokerInterface,
                 agent_id: str = "PositionTraderAgent_1",
                 publisher: Any = None,
                 timeframe: str = "W1", # Weekly default for Position Trader
                 num_bars_to_fetch: int = 200, # e.g., ~4 years of weekly data
                 ema_short_period: int = 12,  # e.g., 12-week EMA
                 ema_long_period: int = 52,   # e.g., 52-week (1-year) EMA
                 rsi_period: int = 14,    # Standard RSI period on the long timeframe
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 # MACD might still be useful on weekly/monthly charts
                 macd_fast: int = 12,
                 macd_slow: int = 26,
                 macd_signal: int = 9,
                 stop_loss_pips: float = 500.0, # Very wide SL for position trades
                 take_profit_pips: float = 1000.0, # Very wide TP
                 fundamental_data_source: Optional[Any] = None # Placeholder for future use
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
        self.fundamental_data_source = fundamental_data_source # Store it

        print(f"{self.agent_id} initialized. Broker: {type(self.broker)}, TF: {self.timeframe}, Bars: {self.num_bars_to_fetch}, EMAs: ({self.ema_short_period}/{self.ema_long_period}), SL: {self.stop_loss_pips}, TP: {self.take_profit_pips}, Fundamentals: {self.fundamental_data_source is not None}")

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60
        if "M5" == timeframe_str: return 5 * 60
        if "M15" == timeframe_str: return 15 * 60
        if "M30" == timeframe_str: return 30 * 60
        if "H1" == timeframe_str: return 60 * 60
        if "H4" == timeframe_str: return 4 * 60 * 60
        if "D1" == timeframe_str: return 24 * 60 * 60
        if "W1" == timeframe_str: return 7 * 24 * 60 * 60 # Weekly
        if "MN1" == timeframe_str: return 30 * 24 * 60 * 60 # Monthly (approx)
        print(f"Warning: Unknown timeframe '{timeframe_str}' in _get_timeframe_seconds_approx for {self.agent_id}, defaulting to 1 week.")
        return 7 * 24 * 60 * 60

    def _calculate_pip_value_and_precision(self, currency_pair: str) -> Tuple[float, int]:
        pair_normalized = currency_pair.upper()
        if "JPY" in pair_normalized:
            return 0.01, 3
        elif "XAU" in pair_normalized or "GOLD" in pair_normalized:
            return 0.01, 2
        else:
            return 0.0001, 5

    def process_task(self, state: Dict) -> Dict:
        task: Optional[ForexSubAgentTask] = state.get("current_position_trader_task") # Expected key

        supporting_data_for_proposal = {
            "params_used": {
                "timeframe": self.timeframe, "num_bars": self.num_bars_to_fetch,
                "ema_s": self.ema_short_period, "ema_l": self.ema_long_period,
                "rsi_p": self.rsi_period, "rsi_os": self.rsi_oversold, "rsi_ob": self.rsi_overbought,
                "macd_f": self.macd_fast, "macd_s": self.macd_slow, "macd_sig": self.macd_signal,
                "sl_pips": self.stop_loss_pips, "tp_pips": self.take_profit_pips,
                "has_fundamental_source": self.fundamental_data_source is not None
            }
        }

        if not task:
            print(f"{self.agent_id}: No current_position_trader_task found in state.")
            current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()
            error_proposal = ForexTradeProposal(
                proposal_id=f"prop_pos_err_{current_time_iso_prop.replace(':', '-')}",
                source_agent_type="PositionTraderAgent", currency_pair="Unknown", timestamp=current_time_iso_prop,
                signal="HOLD", entry_price=None, stop_loss=None, take_profit=None, confidence_score=0.0,
                rationale=f"{self.agent_id}: Task not found in state.", sub_agent_risk_level="Unknown",
                supporting_data=supporting_data_for_proposal
            )
            return {"position_trader_proposal": error_proposal, "error": f"{self.agent_id}: Task not found."}

        currency_pair = task['currency_pair']
        task_id = task['task_id']

        current_simulated_time_iso = state.get("current_simulated_time")
        data_message = "No data fetching attempt due to missing simulated time."
        historical_data = None

        if not current_simulated_time_iso:
            print(f"{self.agent_id}: current_simulated_time not found in state for task {task_id}.")
        else:
            print(f"{self.agent_id}: Processing task '{task_id}' for {currency_pair} at simulated time {current_simulated_time_iso}.")
            print(f"{self.agent_id}: Config - TF:{self.timeframe}, Bars:{self.num_bars_to_fetch}")

            try:
                decision_time_dt = datetime.datetime.fromisoformat(current_simulated_time_iso.replace('Z', '+00:00'))
                decision_time_unix = decision_time_dt.timestamp()
                timeframe_duration_seconds = self._get_timeframe_seconds_approx(self.timeframe) # Uses the updated helper

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

    # --- START OF NEW TA CALCULATION & FUNDAMENTAL PLACEHOLDER LOGIC ---
    ta_message = "TA not performed."
    latest_indicators = {}
    fundamental_message = "Fundamental analysis not yet integrated."

    if self.fundamental_data_source: # Basic check on the placeholder
        # In future, this would trigger actual fundamental data fetching & analysis
        fundamental_message = "Fundamental data source configured but analysis pending implementation."
        print(f"{self.agent_id}: {fundamental_message} (Source: {self.fundamental_data_source})")
    else:
        fundamental_message = "No fundamental data source configured for this agent."
        print(f"{self.agent_id}: {fundamental_message}")

    # Check if historical_data is not None and has enough data for the longest EMA
    if historical_data and len(historical_data) >= self.ema_long_period:
        try:
            print(f"{self.agent_id}: Converting fetched data to DataFrame for TA...")
            df = pd.DataFrame(historical_data)
            if 'timestamp' not in df.columns:
                raise ValueError("DataFrame created from historical_data is missing 'timestamp' column.")

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s', utc=True)
            df.set_index('timestamp', inplace=True)

            required_ohlc = ['open', 'high', 'low', 'close']
            if not all(col in df.columns for col in required_ohlc):
                raise ValueError(f"DataFrame is missing one or more required OHLC columns: {required_ohlc}")

            print(f"{self.agent_id}: Calculating TA indicators for Position Trading (EMAs: {self.ema_short_period}/{self.ema_long_period}, RSI: {self.rsi_period} on {self.timeframe} chart)...")
            df.ta.rsi(length=self.rsi_period, append=True, col_names=(f'RSI_{self.rsi_period}',))
            df.ta.ema(length=self.ema_short_period, append=True, col_names=(f'EMA_{self.ema_short_period}',))
            df.ta.ema(length=self.ema_long_period, append=True, col_names=(f'EMA_{self.ema_long_period}',))
            df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal, append=True,
                       col_names=(f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                  f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                  f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'))

            if not df.empty and not df.iloc[-1].empty: # Check if last row is not empty
                last_row = df.iloc[-1]
                price_precision_for_emas = self._calculate_pip_value_and_precision(currency_pair)[1]
                rsi_col_name = f'RSI_{self.rsi_period}'
                ema_s_col_name = f'EMA_{self.ema_short_period}'
                ema_l_col_name = f'EMA_{self.ema_long_period}'
                macd_line_col_name = f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                macd_signal_col_name = f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                # Note: MACD hist is MACDH_...

                latest_indicators = {
                    rsi_col_name: round(last_row[rsi_col_name], 2) if rsi_col_name in last_row and pd.notna(last_row[rsi_col_name]) else None,
                    ema_s_col_name: round(last_row[ema_s_col_name], price_precision_for_emas) if ema_s_col_name in last_row and pd.notna(last_row[ema_s_col_name]) else None,
                    ema_l_col_name: round(last_row[ema_l_col_name], price_precision_for_emas) if ema_l_col_name in last_row and pd.notna(last_row[ema_l_col_name]) else None,
                    'MACD_line': round(last_row[macd_line_col_name], price_precision_for_emas) if macd_line_col_name in last_row and pd.notna(last_row[macd_line_col_name]) else None,
                    'MACD_signal_line': round(last_row[macd_signal_col_name], price_precision_for_emas) if macd_signal_col_name in last_row and pd.notna(last_row[macd_signal_col_name]) else None,
                    # Add MACD_hist if needed by strategy later
                }
                ta_message = f"TA calculated for Position Trading. Latest RSI: {latest_indicators.get(rsi_col_name)}"
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
    # --- END OF NEW TA CALCULATION & FUNDAMENTAL PLACEHOLDER LOGIC ---

    # Update supporting_data with latest info before strategy
    supporting_data_for_proposal["data_fetch_info"] = data_message
    supporting_data_for_proposal["ta_calculation_info"] = ta_message
    supporting_data_for_proposal["fundamental_analysis_info"] = fundamental_message
    supporting_data_for_proposal.update(latest_indicators)

    # --- START OF NEW POSITION TRADING STRATEGY RULE LOGIC ---
    final_signal = "HOLD"
    final_confidence = 0.5 # Default confidence for HOLD
    strategy_rationale_parts = [f"Position Strategy (TF: {self.timeframe}) based on EMAs ({self.ema_short_period}/{self.ema_long_period}), RSI ({self.rsi_period}, OB:{self.rsi_overbought},OS:{self.rsi_oversold}). Fundamentals: {fundamental_message}"]

    required_indicators = [
        f'EMA_{self.ema_short_period}', f'EMA_{self.ema_long_period}',
        f'RSI_{self.rsi_period}'
        # MACD could also be added here if desired for position trading
    ]

    indicators_present = all(indicator_key in latest_indicators and latest_indicators[indicator_key] is not None for indicator_key in required_indicators)

    if not latest_indicators or not indicators_present:
        strategy_rationale_parts.append("Not all indicators available for position strategy evaluation.")
        print(f"{self.agent_id}: Skipping position strategy rules due to missing indicators. {latest_indicators}")
    else:
        ema_short = latest_indicators[f'EMA_{self.ema_short_period}']
        ema_long = latest_indicators[f'EMA_{self.ema_long_period}']
        rsi = latest_indicators[f'RSI_{self.rsi_period}']
        # macd_line = latest_indicators.get('MACD_line') # If using MACD
        # macd_signal_line = latest_indicators.get('MACD_signal_line') # Corrected key if using MACD

        # Position Trading Conditions (focus on longer-term trends)

        # Buy Condition: Major trend is up (EMA short > EMA long on W1/MN1), RSI not extremely overbought for a long period.
        is_major_uptrend_ema = ema_short > ema_long
        # For position trades, RSI can stay "overbought" for long periods in strong trends.
        # We might use a higher threshold or just ensure it's not at an absolute peak (e.g. < 85-90).
        is_rsi_ok_for_buy = rsi < self.rsi_overbought # Using configured OB level, e.g. 70-80

        # Sell Condition: Major trend is down, RSI not extremely oversold.
        is_major_downtrend_ema = ema_short < ema_long
        is_rsi_ok_for_sell = rsi > self.rsi_oversold # Using configured OS level, e.g. 20-30

        if is_major_uptrend_ema and is_rsi_ok_for_buy: # Potentially add MACD confirmation
            final_signal = "BUY"
            final_confidence = 0.70 # Position trades are typically fewer but might have higher conviction if all aligns
            strategy_rationale_parts.append(f"BUY signal: Major trend bullish (EMA {self.ema_short_period} > EMA {self.ema_long_period} on {self.timeframe}).")
            strategy_rationale_parts.append(f"RSI ({rsi:.2f}) indicates room for upside (Limit: < {self.rsi_overbought}).")
            # if macd_line and macd_signal_line and macd_line > macd_signal_line:
            #     strategy_rationale_parts.append("MACD confirms bullish momentum.")
            # else:
            #     strategy_rationale_parts.append("MACD confirmation pending or neutral.")
            #     final_confidence -= 0.05 # Slightly reduce confidence if MACD not strongly confirming

        elif is_major_downtrend_ema and is_rsi_ok_for_sell: # Potentially add MACD confirmation
            final_signal = "SELL"
            final_confidence = 0.65
            strategy_rationale_parts.append(f"SELL signal: Major trend bearish (EMA {self.ema_short_period} < EMA {self.ema_long_period} on {self.timeframe}).")
            strategy_rationale_parts.append(f"RSI ({rsi:.2f}) indicates room for downside (Limit: > {self.rsi_oversold}).")
            # if macd_line and macd_signal_line and macd_line < macd_signal_line:
            #     strategy_rationale_parts.append("MACD confirms bearish momentum.")
            # else:
            #     strategy_rationale_parts.append("MACD confirmation pending or neutral.")
            #     final_confidence -= 0.05
        else:
            final_signal = "HOLD"
            final_confidence = 0.5
            strategy_rationale_parts.append("HOLD signal: Position trading conditions for long-term BUY or SELL not met.")
            if not is_major_uptrend_ema and not is_major_downtrend_ema and ema_short is not None and ema_long is not None : strategy_rationale_parts.append("Long-term EMAs are not clearly directional.")
            if is_major_uptrend_ema and not is_rsi_ok_for_buy : strategy_rationale_parts.append("Long-term uptrend EMA but RSI too high or other confirmations missing.")
            if is_major_downtrend_ema and not is_rsi_ok_for_sell : strategy_rationale_parts.append("Long-term downtrend EMA but RSI too low or other confirmations missing.")


    print(f"{self.agent_id}: Position Strategy decision: {final_signal}, Confidence: {final_confidence}")
    strategy_rationale_message = " ".join(strategy_rationale_parts)
    # --- END OF NEW POSITION TRADING STRATEGY RULE LOGIC ---

    # --- START OF NEW PRICE/SL/TP CALCULATION LOGIC FOR POSITION TRADER ---
    entry_price_calc: Optional[float] = None
    stop_loss_calc: Optional[float] = None
    take_profit_calc: Optional[float] = None
    price_calculation_message = "SL/TP not calculated for HOLD signal."

    if final_signal in ["BUY", "SELL"]:
        if not currency_pair:
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

                price_calculation_message = f"Entry: {entry_price_calc}, SL: {stop_loss_calc}, TP: {take_profit_calc} (pips SL: {self.stop_loss_pips}, TP: {self.take_profit_pips} for Position Trade)."
                print(f"{self.agent_id}: {price_calculation_message}")
            else:
                price_calculation_message = f"Could not get valid current tick data (ask/bid) for {currency_pair} to calculate SL/TP. Signal was {final_signal}."
                print(f"{self.agent_id}: {price_calculation_message}")
    # --- END OF NEW PRICE/SL/TP CALCULATION LOGIC FOR POSITION TRADER ---

    # Update the ForexTradeProposal creation:
    current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()

    supporting_data_for_proposal["final_signal_determined"] = final_signal
    supporting_data_for_proposal["final_confidence_determined"] = final_confidence
    supporting_data_for_proposal["strategy_rationale_details"] = strategy_rationale_message
    supporting_data_for_proposal["price_calculation_info"] = price_calculation_message

    data_fetch_msg = supporting_data_for_proposal.get("data_fetch_info", "Data fetch info N/A.")
    ta_calc_msg = supporting_data_for_proposal.get("ta_calculation_info", "TA calculation info N/A.")
    fundamental_msg_from_sup = supporting_data_for_proposal.get("fundamental_analysis_info", "Fundamental info N/A.")

    trade_proposal = ForexTradeProposal(
        proposal_id=f"prop_pos_{currency_pair if currency_pair else 'UNKPAIR'}_{current_time_iso_prop.replace(':', '-')}",
        source_agent_type="PositionTraderAgent",
        currency_pair=currency_pair if currency_pair else "Unknown",
        timestamp=current_time_iso_prop,
        signal=final_signal,
        entry_price=entry_price_calc,
        stop_loss=stop_loss_calc,
        take_profit=take_profit_calc,
        take_profit_2=None,
        confidence_score=final_confidence,
        rationale=f"PositionTraderAgent: {strategy_rationale_message} PriceCalc: {price_calculation_message} (Data: {data_fetch_msg} TA: {ta_calc_msg} Fundamentals: {fundamental_msg_from_sup})",
        sub_agent_risk_level="High" if final_signal not in ["HOLD", None] else "Low",
        supporting_data=supporting_data_for_proposal
    )

    print(f"{self.agent_id}: Generated proposal for {currency_pair} after strategy evaluation.") # Consistent print message

    return {"position_trader_proposal": trade_proposal}
