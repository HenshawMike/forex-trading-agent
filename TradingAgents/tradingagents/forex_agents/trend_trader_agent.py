from typing import Dict, Any, Optional, Tuple
from tradingagents.forex_utils.forex_states import ForexSubAgentTask, ForexTradeProposal, OrderSide
from tradingagents.broker_interface.base import BrokerInterface
import datetime
import pandas as pd
import pandas_ta as ta
import traceback

class TrendTraderAgent:  # Changed class name
    def __init__(self,
                 broker: BrokerInterface,
                 agent_id: str = "TrendTraderAgent_1",  # Updated agent_id
                 publisher: Any = None,
                 timeframe: str = "D1",  # Changed timeframe to Daily
                 num_bars_to_fetch: int = 200,
                 ema_short_period: int = 20,  # Adjusted EMA short period
                 ema_long_period: int = 50,   # Adjusted EMA long period
                 rsi_period: int = 14,
                 rsi_oversold: int = 30,
                 rsi_overbought: int = 70,
                 macd_fast: int = 12,
                 macd_slow: int = 26,
                 macd_signal: int = 9,
                 stop_loss_pips: float = 200.0,  # Adjusted stop_loss_pips
                 take_profit_pips: float = 400.0, # Adjusted take_profit_pips
                 fundamental_data_source: Optional[Any] = None
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
        self.fundamental_data_source = fundamental_data_source

        print(f"{self.agent_id} initialized. Broker: {type(self.broker)}, TF: {self.timeframe}, Bars: {self.num_bars_to_fetch}, EMAs: ({self.ema_short_period}/{self.ema_long_period}), SL: {self.stop_loss_pips}, TP: {self.take_profit_pips}, Fundamentals: {self.fundamental_data_source is not None}") # Updated print statement

    def _get_timeframe_seconds_approx(self, timeframe_str: str) -> int:
        timeframe_str = timeframe_str.upper()
        if "M1" == timeframe_str: return 60
        if "M5" == timeframe_str: return 5 * 60
        if "M15" == timeframe_str: return 15 * 60
        if "M30" == timeframe_str: return 30 * 60
        if "H1" == timeframe_str: return 60 * 60
        if "H4" == timeframe_str: return 4 * 60 * 60
        if "D1" == timeframe_str: return 24 * 60 * 60
        if "W1" == timeframe_str: return 7 * 24 * 60 * 60
        if "MN1" == timeframe_str: return 30 * 24 * 60 * 60
        print(f"Warning: Unknown timeframe '{timeframe_str}' in _get_timeframe_seconds_approx for {self.agent_id}, defaulting to 1 day.") # Updated default warning
        return 24 * 60 * 60 # Default to D1 if unknown

    def _calculate_pip_value_and_precision(self, currency_pair: str) -> Tuple[float, int]:
        pair_normalized = currency_pair.upper()
        if "JPY" in pair_normalized:
            return 0.01, 3
        elif "XAU" in pair_normalized or "GOLD" in pair_normalized:
            return 0.01, 2
        else:
            return 0.0001, 5

    def process_task(self, state: Dict) -> Dict:
        task: Optional[ForexSubAgentTask] = state.get("current_trend_trader_task") # Changed task key

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
            print(f"{self.agent_id}: No current_trend_trader_task found in state.") # Changed log message
            current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()
            error_proposal = ForexTradeProposal(
                proposal_id=f"prop_trend_err_{current_time_iso_prop.replace(':', '-')}", # Updated proposal_id prefix
                source_agent_type="TrendTraderAgent", # Updated source_agent_type
                currency_pair="Unknown", timestamp=current_time_iso_prop,
                signal="HOLD", entry_price=None, stop_loss=None, take_profit=None, confidence_score=0.0,
                rationale=f"{self.agent_id}: Task not found in state.", sub_agent_risk_level="Unknown",
                supporting_data=supporting_data_for_proposal
            )
            return {"trend_trader_proposal": error_proposal, "error": f"{self.agent_id}: Task not found."} # Changed key for return

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

        ta_message = "TA not performed."
        latest_indicators = {}
        fundamental_message = "Fundamental analysis not yet integrated." # Trend traders may also use fundamentals

        if self.fundamental_data_source:
            fundamental_message = "Fundamental data source configured but analysis pending implementation for Trend Trader."
            print(f"{self.agent_id}: {fundamental_message} (Source: {self.fundamental_data_source})")
        else:
            fundamental_message = "No fundamental data source configured for this Trend Trader agent."
            print(f"{self.agent_id}: {fundamental_message}")

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

                print(f"{self.agent_id}: Calculating TA indicators for Trend Trading (EMAs: {self.ema_short_period}/{self.ema_long_period}, RSI: {self.rsi_period} on {self.timeframe} chart)...") # Updated log
                df.ta.rsi(length=self.rsi_period, append=True, col_names=(f'RSI_{self.rsi_period}',))
                df.ta.ema(length=self.ema_short_period, append=True, col_names=(f'EMA_{self.ema_short_period}',))
                df.ta.ema(length=self.ema_long_period, append=True, col_names=(f'EMA_{self.ema_long_period}',))
                df.ta.macd(fast=self.macd_fast, slow=self.macd_slow, signal=self.macd_signal, append=True,
                           col_names=(f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                      f'MACDH_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}',
                                      f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'))

                if not df.empty and not df.iloc[-1].empty:
                    last_row = df.iloc[-1]
                    price_precision_for_emas = self._calculate_pip_value_and_precision(currency_pair)[1]
                    rsi_col_name = f'RSI_{self.rsi_period}'
                    ema_s_col_name = f'EMA_{self.ema_short_period}'
                    ema_l_col_name = f'EMA_{self.ema_long_period}'
                    macd_line_col_name = f'MACD_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'
                    macd_signal_col_name = f'MACDS_{self.macd_fast}_{self.macd_slow}_{self.macd_signal}'

                    latest_indicators = {
                        rsi_col_name: round(last_row[rsi_col_name], 2) if rsi_col_name in last_row and pd.notna(last_row[rsi_col_name]) else None,
                        ema_s_col_name: round(last_row[ema_s_col_name], price_precision_for_emas) if ema_s_col_name in last_row and pd.notna(last_row[ema_s_col_name]) else None,
                        ema_l_col_name: round(last_row[ema_l_col_name], price_precision_for_emas) if ema_l_col_name in last_row and pd.notna(last_row[ema_l_col_name]) else None,
                        'MACD_line': round(last_row[macd_line_col_name], price_precision_for_emas) if macd_line_col_name in last_row and pd.notna(last_row[macd_line_col_name]) else None,
                        'MACD_signal_line': round(last_row[macd_signal_col_name], price_precision_for_emas) if macd_signal_col_name in last_row and pd.notna(last_row[macd_signal_col_name]) else None,
                    }
                    ta_message = f"TA calculated for Trend Trading. Latest RSI: {latest_indicators.get(rsi_col_name)}" # Updated log
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

        supporting_data_for_proposal["data_fetch_info"] = data_message
        supporting_data_for_proposal["ta_calculation_info"] = ta_message
        supporting_data_for_proposal["fundamental_analysis_info"] = fundamental_message
        supporting_data_for_proposal.update(latest_indicators)

        final_signal = "HOLD"
        final_confidence = 0.5
        strategy_rationale_parts = [f"Trend Strategy (TF: {self.timeframe}) based on EMAs ({self.ema_short_period}/{self.ema_long_period}), RSI ({self.rsi_period}, OB:{self.rsi_overbought},OS:{self.rsi_oversold}). Fundamentals: {fundamental_message}"] # Updated rationale

        required_indicators = [
            f'EMA_{self.ema_short_period}', f'EMA_{self.ema_long_period}',
            f'RSI_{self.rsi_period}'
        ]

        indicators_present = all(indicator_key in latest_indicators and latest_indicators[indicator_key] is not None for indicator_key in required_indicators)

        if not latest_indicators or not indicators_present:
            strategy_rationale_parts.append("Not all indicators available for trend strategy evaluation.") # Updated rationale
            print(f"{self.agent_id}: Skipping trend strategy rules due to missing indicators. {latest_indicators}") # Updated log
        else:
            ema_short = latest_indicators[f'EMA_{self.ema_short_period}']
            ema_long = latest_indicators[f'EMA_{self.ema_long_period}']
            rsi = latest_indicators[f'RSI_{self.rsi_period}']

            # Trend Trading Conditions
            is_uptrend_ema = ema_short > ema_long
            is_rsi_ok_for_buy_trend = rsi > self.rsi_oversold # Buy into established trends, RSI confirming momentum (e.g. > 40-50)
                                                         # and not extremely overbought (e.g. < 80 for D1)
            is_downtrend_ema = ema_short < ema_long
            is_rsi_ok_for_sell_trend = rsi < self.rsi_overbought # Sell into established trends, RSI confirming momentum (e.g. < 60-50)
                                                          # and not extremely oversold (e.g. > 20 for D1)

            if is_uptrend_ema and rsi < self.rsi_overbought : # Primary: EMA crossover indicates uptrend. RSI not overbought.
                final_signal = "BUY"
                final_confidence = 0.70
                strategy_rationale_parts.append(f"BUY signal: Trend bullish (EMA {self.ema_short_period} > EMA {self.ema_long_period} on {self.timeframe}).")
                strategy_rationale_parts.append(f"RSI ({rsi:.2f}) indicates ongoing momentum (Limit: < {self.rsi_overbought}).")
                # Optionally, add MACD confirmation for trend strength
                macd_line = latest_indicators.get('MACD_line')
                macd_signal_line = latest_indicators.get('MACD_signal_line')
                if macd_line and macd_signal_line and macd_line > macd_signal_line:
                     strategy_rationale_parts.append("MACD confirms bullish momentum.")
                else:
                     strategy_rationale_parts.append("MACD confirmation pending or neutral for trend.")
                     final_confidence -= 0.05


            elif is_downtrend_ema and rsi > self.rsi_oversold: # Primary: EMA crossover indicates downtrend. RSI not oversold.
                final_signal = "SELL"
                final_confidence = 0.65
                strategy_rationale_parts.append(f"SELL signal: Trend bearish (EMA {self.ema_short_period} < EMA {self.ema_long_period} on {self.timeframe}).")
                strategy_rationale_parts.append(f"RSI ({rsi:.2f}) indicates ongoing momentum (Limit: > {self.rsi_oversold}).")
                macd_line = latest_indicators.get('MACD_line')
                macd_signal_line = latest_indicators.get('MACD_signal_line')
                if macd_line and macd_signal_line and macd_line < macd_signal_line:
                     strategy_rationale_parts.append("MACD confirms bearish momentum.")
                else:
                     strategy_rationale_parts.append("MACD confirmation pending or neutral for trend.")
                     final_confidence -= 0.05
            else:
                final_signal = "HOLD"
                final_confidence = 0.5
                strategy_rationale_parts.append("HOLD signal: Trend trading conditions for BUY or SELL not clearly met.") # Updated rationale
                if not is_uptrend_ema and not is_downtrend_ema and ema_short is not None and ema_long is not None : strategy_rationale_parts.append("EMAs are not clearly directional for trend.")
                if is_uptrend_ema and not (rsi < self.rsi_overbought) : strategy_rationale_parts.append("Uptrend EMA but RSI too high or other confirmations missing for trend entry.")
                if is_downtrend_ema and not (rsi > self.rsi_oversold) : strategy_rationale_parts.append("Downtrend EMA but RSI too low or other confirmations missing for trend entry.")

        print(f"{self.agent_id}: Trend Strategy decision: {final_signal}, Confidence: {final_confidence}") # Updated log
        strategy_rationale_message = " ".join(strategy_rationale_parts)

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

                    price_calculation_message = f"Entry: {entry_price_calc}, SL: {stop_loss_calc}, TP: {take_profit_calc} (pips SL: {self.stop_loss_pips}, TP: {self.take_profit_pips} for Trend Trade)." # Updated log
                    print(f"{self.agent_id}: {price_calculation_message}")
                else:
                    price_calculation_message = f"Could not get valid current tick data (ask/bid) for {currency_pair} to calculate SL/TP. Signal was {final_signal}."
                    print(f"{self.agent_id}: {price_calculation_message}")

        current_time_iso_prop = datetime.datetime.now(datetime.timezone.utc).isoformat()

        supporting_data_for_proposal["final_signal_determined"] = final_signal
        supporting_data_for_proposal["final_confidence_determined"] = final_confidence
        supporting_data_for_proposal["strategy_rationale_details"] = strategy_rationale_message
        supporting_data_for_proposal["price_calculation_info"] = price_calculation_message

        data_fetch_msg = supporting_data_for_proposal.get("data_fetch_info", "Data fetch info N/A.")
        ta_calc_msg = supporting_data_for_proposal.get("ta_calculation_info", "TA calculation info N/A.")
        fundamental_msg_from_sup = supporting_data_for_proposal.get("fundamental_analysis_info", "Fundamental info N/A.")

        trade_proposal = ForexTradeProposal(
            proposal_id=f"prop_trend_{currency_pair if currency_pair else 'UNKPAIR'}_{current_time_iso_prop.replace(':', '-')}", # Updated proposal_id prefix
            source_agent_type="TrendTraderAgent", # Updated source_agent_type
            currency_pair=currency_pair if currency_pair else "Unknown",
            timestamp=current_time_iso_prop,
            signal=final_signal,
            entry_price=entry_price_calc,
            stop_loss=stop_loss_calc,
            take_profit=take_profit_calc,
            take_profit_2=None,
            confidence_score=final_confidence,
            rationale=f"TrendTraderAgent: {strategy_rationale_message} PriceCalc: {price_calculation_message} (Data: {data_fetch_msg} TA: {ta_calc_msg} Fundamentals: {fundamental_msg_from_sup})", # Updated rationale
            sub_agent_risk_level="Medium" if final_signal not in ["HOLD", None] else "Low", # Trend trading might be Medium risk
            supporting_data=supporting_data_for_proposal
        )

        print(f"{self.agent_id}: Generated proposal for {currency_pair} after trend strategy evaluation.") # Updated log

        return {"trend_trader_proposal": trade_proposal} # Changed key for return
