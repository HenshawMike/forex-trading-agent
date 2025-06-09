import pandas as pd
import pandas_ta as ta
import numpy as np # For mock data generation
from typing import Any, Dict, List, Optional

class DayTraderAgent:
    def __init__(self, agent_id: str, llm: Any, memory: Any, broker_interface: Any): # Replace Any with actual types
        self.agent_id = agent_id
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.broker_interface = broker_interface # Placeholder
        # print(f"DayTraderAgent '{self.agent_id}' initialized.") # Reduced verbosity

    def _create_mock_data(self, pair: str, num_bars: int = 50) -> pd.DataFrame:
        # Create mock OHLCV data
        dates = pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=num_bars, freq='15min')
        data = {
            'open': np.random.uniform(1.0, 1.1, size=num_bars),
            'high': 0.0, # Will be set based on open/close
            'low': 0.0,  # Will be set based on open/close
            'close': np.random.uniform(1.0, 1.1, size=num_bars),
            'volume': np.random.randint(100, 1000, size=num_bars)
        }
        df = pd.DataFrame(data, index=dates)
        df['high'] = df[['open', 'close']].max(axis=1) + np.random.uniform(0.0001, 0.0005, size=num_bars)
        df['low'] = df[['open', 'close']].min(axis=1) - np.random.uniform(0.0001, 0.0005, size=num_bars)
        # Ensure low is not above high, open, or close after randomization
        df['low'] = np.minimum(df['low'], df[['open', 'close', 'high']].min(axis=1))
        df['high'] = np.maximum(df['high'], df[['open', 'close', 'low']].max(axis=1))

        # print(f"Mock data for {pair} (last 3 bars):\n{df.tail(3)}")
        return df

    def analyze_and_propose_trades(
        self,
        strategic_directive: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        print(f"DayTraderAgent '{self.agent_id}': Received directive - {strategic_directive.get('key_narrative', 'No narrative')}")
        trade_proposals = []

        focus_pairs = strategic_directive.get("focus_pairs", [])
        directive_bias_info = strategic_directive.get("primary_bias", {})

        for pair in focus_pairs:
            print(f"DayTraderAgent '{self.agent_id}': Analyzing pair {pair}")
            # In a real scenario, data would be fetched via self.broker_interface
            # market_data_df = self.broker_interface.get_historical_data(pair, "M15", count=50)
            # For now, using mock data:
            market_data_df = self._create_mock_data(pair, num_bars=50)

            if market_data_df is None or market_data_df.empty:
                print(f"DayTraderAgent '{self.agent_id}': No market data for {pair}")
                continue

            # Calculate indicators
            try:
                market_data_df.ta.ema(length=10, append=True, col="EMA_10")
                market_data_df.ta.ema(length=20, append=True, col="EMA_20")
                market_data_df.ta.rsi(length=14, append=True, col="RSI_14")
            except Exception as e:
                print(f"DayTraderAgent '{self.agent_id}': Error calculating indicators for {pair}: {e}")
                continue

            if not all(col in market_data_df.columns for col in ["EMA_10", "EMA_20", "RSI_14"]):
                print(f"DayTraderAgent '{self.agent_id}': Could not calculate all indicators for {pair}. Data length: {len(market_data_df)}")
                continue

            latest_data = market_data_df.iloc[-1]
            previous_data = market_data_df.iloc[-2] if len(market_data_df) >= 2 else latest_data

            current_price = latest_data["close"]
            confidence = 0.5
            rationale_parts = [f"Analysis for {pair}:"]

            pair_bias_direction = "neutral" # Default to neutral
            if isinstance(directive_bias_info.get("pair"), str) and directive_bias_info.get("pair") == pair:
                pair_bias_direction = directive_bias_info.get("direction", "neutral")
            elif isinstance(directive_bias_info.get("currency"), str):
                base_currency, quote_currency = pair.split("/") if "/" in pair else (None, None)
                if base_currency and quote_currency:
                    if directive_bias_info["currency"] == base_currency:
                        pair_bias_direction = directive_bias_info.get("direction", "neutral")
                    elif directive_bias_info["currency"] == quote_currency:
                        dir_map = {"bullish": "bearish", "bearish": "bullish"}
                        pair_bias_direction = dir_map.get(directive_bias_info.get("direction"), "neutral")
            elif directive_bias_info.get("market_condition") in ["ranging", "neutral_or_mixed_signals", "neutral"]:
                 pair_bias_direction = "ranging"

            rationale_parts.append(f"Interpreted directive bias for {pair}: {pair_bias_direction}.")

            trade_side = None
            if pair_bias_direction == "bullish":
                rationale_parts.append(f"Strategic directive suggests bullish outlook.")
                if previous_data["EMA_10"] < previous_data["EMA_20"] and latest_data["EMA_10"] > latest_data["EMA_20"]:
                    if latest_data["RSI_14"] < 70:
                        trade_side = "buy"
                        confidence = 0.65
                        rationale_parts.append("Bullish EMA crossover (10/20).")
                        rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) allows entry.")
                    else:
                        rationale_parts.append(f"EMA crossover bullish, but RSI ({latest_data['RSI_14']:.2f}) overbought.")
                else:
                    rationale_parts.append("No bullish EMA crossover signal.")
            elif pair_bias_direction == "bearish":
                rationale_parts.append(f"Strategic directive suggests bearish outlook.")
                if previous_data["EMA_10"] > previous_data["EMA_20"] and latest_data["EMA_10"] < latest_data["EMA_20"]:
                    if latest_data["RSI_14"] > 30:
                        trade_side = "sell"
                        confidence = 0.65
                        rationale_parts.append("Bearish EMA crossover (10/20).")
                        rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) allows entry.")
                    else:
                        rationale_parts.append(f"EMA crossover bearish, but RSI ({latest_data['RSI_14']:.2f}) oversold.")
                else:
                    rationale_parts.append("No bearish EMA crossover signal.")
            elif pair_bias_direction == "ranging":
                rationale_parts.append(f"Market condition for {pair} is ranging/neutral. DayTrader looking for S/R bounces (simplified logic: no EMA crossover trades).")
            else: # Neutral or other unhandled bias
                rationale_parts.append(f"Neutral or unhandled bias '{pair_bias_direction}' for {pair}. No EMA crossover trades.")


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
                    "pair": pair,
                    "type": "market",
                    "side": trade_side,
                    "entry_price": None,
                    "stop_loss": round(sl_price, decimals),
                    "take_profit": round(tp_price, decimals),
                    "confidence_score": confidence,
                    "origin_agent": self.agent_id,
                    "rationale": " ".join(rationale_parts)
                })

        if not trade_proposals:
            print(f"DayTraderAgent '{self.agent_id}': No compelling trade opportunities found based on current rules and directive for pairs: {focus_pairs}.")
        else:
            print(f"DayTraderAgent '{self.agent_id}': Generated {len(trade_proposals)} proposals.")
            for prop_idx, prop in enumerate(trade_proposals):
                print(f"  Proposal {prop_idx+1}: {prop['pair']} {prop['side']}, SL: {prop['stop_loss']}, TP: {prop['take_profit']}, Conf: {prop['confidence_score']}, Rat: {prop['rationale']}")

        return trade_proposals
