import pandas as pd
import pandas_ta as ta
import numpy as np # Still used by other agents, but not directly here anymore for mock data
from typing import Any, Dict, List, Optional

class DayTraderAgent:
    def __init__(self, agent_id: str, llm: Any, memory: Any, broker_interface: Any): # Replace Any with actual types
        self.agent_id = agent_id
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.broker_interface = broker_interface
        # print(f"DayTraderAgent '{self.agent_id}' initialized.") # Reduced verbosity

    # _create_mock_data method is REMOVED

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
        # This helper method should already be present from previous steps
        directive_bias_info = strategic_directive.get("primary_bias", {})
        pair_bias_direction = None
        if isinstance(directive_bias_info.get("pair"), str) and directive_bias_info.get("pair") == pair: # Check type
            pair_bias_direction = directive_bias_info.get("direction")
        elif isinstance(directive_bias_info.get("currency"), str): # Check type
            base_currency, quote_currency = pair.split("/") if "/" in pair else (None, None)
            if base_currency and quote_currency: # Ensure pair splitting was successful
                target_currency = directive_bias_info["currency"]
                target_direction = directive_bias_info.get("direction")
                if target_currency == base_currency:
                    pair_bias_direction = target_direction
                elif target_currency == quote_currency:
                    if target_direction == "bullish": pair_bias_direction = "bearish"
                    elif target_direction == "bearish": pair_bias_direction = "bullish"

        if pair_bias_direction is None: # Only if not already set by pair or currency
            market_condition = directive_bias_info.get("market_condition")
            if market_condition in ["ranging", "neutral_or_mixed_signals", "neutral", "ranging_on_pair"]:
                return "ranging"
            if market_condition == "bullish_all" or \
               (isinstance(directive_bias_info.get("pairs"), list) and \
                pair in directive_bias_info.get("pairs", []) and "bullish" in market_condition): # Added default empty list for pairs
                return "bullish"
            if market_condition == "bearish_all" or \
               (isinstance(directive_bias_info.get("pairs"), list) and \
                pair in directive_bias_info.get("pairs", []) and "bearish" in market_condition):
                return "bearish"
        return pair_bias_direction

    def analyze_and_propose_trades(
        self,
        strategic_directive: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        print(f"DayTraderAgent '{self.agent_id}': Received directive - {strategic_directive.get('key_narrative', 'No narrative')}")
        trade_proposals = []

        focus_pairs = strategic_directive.get("focus_pairs", [])

        for pair in focus_pairs:
            print(f"DayTraderAgent '{self.agent_id}': Analyzing {pair}...")
            # Fetch data using the broker interface
            raw_market_data = self.broker_interface.get_historical_data(pair=pair, timeframe="M15", count=50)

            if raw_market_data is None or not raw_market_data:
                print(f"DayTraderAgent '{self.agent_id}': No market data received from broker for {pair}")
                continue

            # Convert list of dicts to DataFrame for pandas_ta
            try:
                market_data_df = pd.DataFrame(raw_market_data)
                if 'time' in market_data_df.columns:
                    market_data_df['time'] = pd.to_datetime(market_data_df['time'])
                    market_data_df.set_index('time', inplace=True)
                else:
                    print(f"DayTraderAgent '{self.agent_id}': 'time' column missing in data for {pair} from broker.")
                    continue

                required_ohlcv = ['open', 'high', 'low', 'close', 'volume']
                if not all(col in market_data_df.columns for col in required_ohlcv):
                    print(f"DayTraderAgent '{self.agent_id}': Data for {pair} missing one or more OHLCV columns. Has: {market_data_df.columns}")
                    continue

            except Exception as e:
                print(f"DayTraderAgent '{self.agent_id}': Error converting broker data to DataFrame for {pair}: {e}")
                continue

            if market_data_df.empty or len(market_data_df) < 20: # Need enough for EMAs
                print(f"DayTraderAgent '{self.agent_id}': Insufficient data points for {pair} after conversion ({len(market_data_df)}).")
                continue

            try:
                market_data_df.ta.ema(length=10, append=True, col="EMA_10")
                market_data_df.ta.ema(length=20, append=True, col="EMA_20")
                market_data_df.ta.rsi(length=14, append=True, col="RSI_14")
            except Exception as e:
                print(f"DayTraderAgent '{self.agent_id}': Error calculating indicators for {pair}: {e}")
                continue

            if not all(col in market_data_df.columns for col in ["EMA_10", "EMA_20", "RSI_14"]):
                print(f"DayTraderAgent '{self.agent_id}': Could not calculate all indicators for {pair}. Available: {market_data_df.columns}")
                continue

            latest_data = market_data_df.iloc[-1]
            previous_data = market_data_df.iloc[-2] if len(market_data_df) >= 2 else latest_data

            current_price = latest_data["close"]
            confidence = 0.5
            rationale_parts = [f"Analysis for {pair}:"]
            trade_side = None

            pair_bias_direction = self._get_pair_bias_from_directive(pair, strategic_directive)
            rationale_parts.append(f"Interpreted directive bias for {pair}: {pair_bias_direction if pair_bias_direction else 'none/neutral'}.")

            if pair_bias_direction == "bullish":
                rationale_parts.append("Strategic directive suggests bullish outlook.")
                if previous_data["EMA_10"] < previous_data["EMA_20"] and latest_data["EMA_10"] > latest_data["EMA_20"]:
                    if latest_data["RSI_14"] < 70:
                        trade_side = "buy"
                        confidence = 0.65
                        rationale_parts.append("Bullish EMA crossover (10/20) on M15.")
                        rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) is not overbought.")
                    else:
                        rationale_parts.append(f"EMA crossover detected but RSI ({latest_data['RSI_14']:.2f}) is overbought.")
                else:
                    rationale_parts.append("No bullish EMA crossover.")
            elif pair_bias_direction == "bearish":
                rationale_parts.append("Strategic directive suggests bearish outlook.")
                if previous_data["EMA_10"] > previous_data["EMA_20"] and latest_data["EMA_10"] < latest_data["EMA_20"]:
                    if latest_data["RSI_14"] > 30:
                        trade_side = "sell"
                        confidence = 0.65
                        rationale_parts.append("Bearish EMA crossover (10/20) on M15.")
                        rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) is not oversold.")
                    else:
                        rationale_parts.append(f"EMA crossover detected but RSI ({latest_data['RSI_14']:.2f}) is oversold.")
                else:
                    rationale_parts.append("No bearish EMA crossover.")
            elif pair_bias_direction == "ranging":
                rationale_parts.append(f"Market condition for {pair} is ranging/neutral. DayTrader looking for clearer signals or S/R bounces (logic not implemented in this skeleton).")

            if not trade_side and pair_bias_direction not in ["ranging", None, "neutral"] :
                 rationale_parts.append(f"No valid Day Trading signal found aligning with {pair_bias_direction} bias.")
            elif not trade_side and (pair_bias_direction is None or pair_bias_direction == "neutral"):
                 rationale_parts.append(f"No clear directional bias from directive for {pair} for Day Trading or bias is neutral.")


            if trade_side:
                pips_sl = 0.0020
                pips_tp = 0.0040
                decimals = 5
                if "JPY" in pair.upper():
                    pips_sl = 0.20
                    pips_tp = 0.40
                    decimals = 3

                sl_price = current_price - pips_sl if trade_side == "buy" else current_price + pips_sl
                tp_price = current_price + pips_tp if trade_side == "buy" else current_price - pips_tp

                trade_proposals.append({
                    "pair": pair, "type": "market", "side": trade_side,
                    "entry_price": None,
                    "stop_loss": round(sl_price, decimals),
                    "take_profit": round(tp_price, decimals),
                    "confidence_score": confidence, "origin_agent": self.agent_id,
                    "rationale": " ".join(rationale_parts)
                })

        if not trade_proposals:
            print(f"DayTraderAgent '{self.agent_id}': No compelling trade opportunities found for pairs: {focus_pairs} based on current rules and broker data.")
        else:
            print(f"DayTraderAgent '{self.agent_id}': Generated {len(trade_proposals)} proposals using broker data.")
            for prop_idx, prop in enumerate(trade_proposals):
                 print(f"  Proposal {prop_idx+1}: {prop['pair']} {prop['side']}, SL: {prop['stop_loss']}, TP: {prop['take_profit']}, Conf: {prop['confidence_score']}, Rat: {prop['rationale']}")

        return trade_proposals
