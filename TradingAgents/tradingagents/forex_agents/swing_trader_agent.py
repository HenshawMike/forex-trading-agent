import pandas as pd
import pandas_ta as ta
import numpy as np # For mock data generation
from typing import Any, Dict, List, Optional

class SwingTraderAgent:
    def __init__(self, agent_id: str, llm: Any, memory: Any, broker_interface: Any): # Replace Any with actual types
        self.agent_id = agent_id
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.broker_interface = broker_interface # Placeholder
        # print(f"SwingTraderAgent '{self.agent_id}' initialized.") # Reduced verbosity

    def _create_mock_data(self, pair: str, num_bars: int = 200, freq: str = 'D') -> pd.DataFrame:
        # Create mock OHLCV data for daily timeframe
        dates = pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=num_bars, freq=freq)
        data = {
            'open': np.random.uniform(1.0, 1.2, size=num_bars), # Wider range for daily
            'high': 0.0,
            'low': 0.0,
            'close': np.random.uniform(1.0, 1.2, size=num_bars),
            'volume': np.random.randint(1000, 10000, size=num_bars)
        }
        df = pd.DataFrame(data, index=dates)
        df['high'] = df[['open', 'close']].max(axis=1) + np.random.uniform(0.001, 0.005, size=num_bars) # Wider daily moves
        df['low'] = df[['open', 'close']].min(axis=1) - np.random.uniform(0.001, 0.005, size=num_bars)
        df['low'] = np.minimum(df['low'], df[['open', 'close', 'high']].min(axis=1))
        df['high'] = np.maximum(df['high'], df[['open', 'close', 'low']].max(axis=1))
        # print(f"Mock daily data for {pair} (last 3 bars):\n{df.tail(3)}")
        return df

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
        # Helper to determine bias for a specific pair based on the directive
        directive_bias_info = strategic_directive.get("primary_bias", {})
        pair_bias_direction = None

        if isinstance(directive_bias_info.get("pair"), str) and directive_bias_info.get("pair") == pair:
            pair_bias_direction = directive_bias_info.get("direction")
        elif isinstance(directive_bias_info.get("currency"), str):
            base_currency, quote_currency = pair.split("/") if "/" in pair else (None,None)
            if base_currency and quote_currency:
                target_currency = directive_bias_info["currency"]
                target_direction = directive_bias_info.get("direction")
                if target_currency == base_currency:
                    pair_bias_direction = target_direction
                elif target_currency == quote_currency:
                    if target_direction == "bullish": pair_bias_direction = "bearish"
                    elif target_direction == "bearish": pair_bias_direction = "bullish"

        if pair_bias_direction is None:
            market_condition = directive_bias_info.get("market_condition")
            if market_condition in ["ranging", "neutral_or_mixed_signals", "neutral", "ranging_on_pair"]:
                return "ranging"
            if market_condition == "bullish_all" or \
               (isinstance(directive_bias_info.get("pairs"), list) and \
                pair in directive_bias_info.get("pairs", []) and "bullish" in market_condition):
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
        print(f"SwingTraderAgent '{self.agent_id}': Received directive - {strategic_directive.get('key_narrative')}")
        trade_proposals = []

        focus_pairs = strategic_directive.get("focus_pairs", [])

        for pair in focus_pairs:
            print(f"SwingTraderAgent '{self.agent_id}': Analyzing pair {pair}")
            # market_data_df = self.broker_interface.get_historical_data(pair, "D1", count=200)
            market_data_df = self._create_mock_data(pair, num_bars=200, freq='D')

            if market_data_df is None or market_data_df.empty or len(market_data_df) < 50: # Min length for EMAs
                print(f"SwingTraderAgent '{self.agent_id}': Insufficient market data for {pair} (need >50 bars). Got: {len(market_data_df) if market_data_df is not None else 0}")
                continue

            try:
                market_data_df.ta.ema(length=50, append=True, col="EMA_50")
                market_data_df.ta.ema(length=200, append=True, col="EMA_200")
                macd = market_data_df.ta.macd(append=False) # Calculate separately to handle column names
                if macd is not None and not macd.empty:
                    market_data_df['MACD_line'] = macd.iloc[:,0]
                    market_data_df['MACD_signal'] = macd.iloc[:,1]
                market_data_df.ta.rsi(length=14, append=True, col="RSI_14")
            except Exception as e:
                print(f"SwingTraderAgent '{self.agent_id}': Error calculating indicators for {pair}: {e}")
                continue

            required_cols = ["EMA_50", "EMA_200", "MACD_line", "MACD_signal", "RSI_14"]
            if not all(col in market_data_df.columns for col in required_cols):
                print(f"SwingTraderAgent '{self.agent_id}': Could not calculate all indicators for {pair}.")
                continue

            latest_data = market_data_df.iloc[-1]
            previous_data = market_data_df.iloc[-2]

            current_price = latest_data["close"]
            confidence = 0.5
            rationale_parts = [f"Analysis for {pair} (Swing):"]
            trade_side = None

            pair_bias_direction = self._get_pair_bias_from_directive(pair, strategic_directive)
            rationale_parts.append(f"Interpreted directive bias for {pair}: {pair_bias_direction}.")

            if pair_bias_direction == "bullish":
                rationale_parts.append("Strategic directive suggests bullish outlook.")
                if current_price > latest_data["EMA_50"] and latest_data["EMA_50"] > latest_data["EMA_200"]:
                    rationale_parts.append("Price above EMA_50, and EMA_50 above EMA_200 (uptrend structure).")
                    if previous_data["MACD_line"] < previous_data["MACD_signal"] and \
                       latest_data["MACD_line"] > latest_data["MACD_signal"]:
                        rationale_parts.append("Bullish MACD crossover.")
                        if latest_data["RSI_14"] < 70 and latest_data["RSI_14"] > 40 :
                            trade_side = "buy"
                            confidence = 0.70
                            rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) confirms momentum, not overbought.")
                        else:
                            rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) not in optimal buy zone for swing.")
                    else:
                        rationale_parts.append("No bullish MACD crossover, or crossover too old.")
                else:
                    rationale_parts.append("Price not showing clear uptrend structure above key EMAs.")

            elif pair_bias_direction == "bearish":
                rationale_parts.append("Strategic directive suggests bearish outlook.")
                if current_price < latest_data["EMA_50"] and latest_data["EMA_50"] < latest_data["EMA_200"]:
                    rationale_parts.append("Price below EMA_50, and EMA_50 below EMA_200 (downtrend structure).")
                    if previous_data["MACD_line"] > previous_data["MACD_signal"] and \
                       latest_data["MACD_line"] < latest_data["MACD_signal"]:
                        rationale_parts.append("Bearish MACD crossover.")
                        if latest_data["RSI_14"] > 30 and latest_data["RSI_14"] < 60:
                            trade_side = "sell"
                            confidence = 0.70
                            rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) confirms momentum, not oversold.")
                        else:
                            rationale_parts.append(f"RSI ({latest_data['RSI_14']:.2f}) not in optimal sell zone for swing.")
                    else:
                        rationale_parts.append("No bearish MACD crossover, or crossover too old.")
                else:
                    rationale_parts.append("Price not showing clear downtrend structure below key EMAs.")

            elif pair_bias_direction == "ranging":
                rationale_parts.append(f"Market condition for {pair} is ranging. SwingTrader might look for S/R bounces (not implemented in this skeleton).")
            else:
                rationale_parts.append(f"Neutral or unhandled bias '{pair_bias_direction}' for {pair}. No trend-following swing trades.")


            if trade_side:
                pips_sl = 0.0100
                pips_tp = 0.0200
                decimals = 5
                if "JPY" in pair.upper():
                    pips_sl = 1.00
                    pips_tp = 2.00
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
            print(f"SwingTraderAgent '{self.agent_id}': No compelling swing trade opportunities found for pairs: {focus_pairs}.")
        else:
            print(f"SwingTraderAgent '{self.agent_id}': Generated {len(trade_proposals)} proposals.")
            for prop_idx, prop in enumerate(trade_proposals):
                 print(f"  Proposal {prop_idx+1}: {prop['pair']} {prop['side']}, SL: {prop['stop_loss']}, TP: {prop['take_profit']}, Conf: {prop['confidence_score']}, Rat: {prop['rationale']}")

        return trade_proposals
