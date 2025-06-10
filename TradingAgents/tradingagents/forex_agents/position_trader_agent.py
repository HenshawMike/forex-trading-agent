# In TradingAgents/tradingagents/forex_agents/position_trader_agent.py
import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Any, Dict, List, Optional

class PositionTraderAgent:
    def __init__(self, agent_id: str, llm: Any, memory: Any, broker_interface: Any):
        self.agent_id = agent_id
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.broker_interface = broker_interface # Placeholder
        # print(f"PositionTraderAgent '{self.agent_id}' initialized.")

    def _create_mock_data(self, pair: str, num_bars: int = 200, freq: str = 'W-MON') -> pd.DataFrame: # Weekly data
        dates = pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=num_bars, freq=freq)
        start_price = np.random.uniform(1.0, 1.5)
        if "JPY" in pair.upper():
            start_price = np.random.uniform(100.0, 180.0)

        trend_slope = np.random.uniform(-0.005, 0.005)
        price_series = start_price + trend_slope * np.arange(num_bars) + np.random.normal(0, 0.02, size=num_bars)
        if "JPY" in pair.upper():
             price_series = start_price + np.random.uniform(-0.5, 0.5) * np.arange(num_bars) + np.random.normal(0, 2, size=num_bars)

        close_prices = np.maximum(0.01, price_series) # Ensure positive prices, use a smaller floor for JPY pairs potentially
        if "JPY" not in pair.upper() and np.min(close_prices) < 0.5: # Adjust floor for non-JPY if too low
            close_prices = np.maximum(0.5, price_series)

        open_prices = np.roll(close_prices, 1)
        open_prices[0] = close_prices[0] - (price_series[0] - (start_price + np.random.normal(0,0.02)) ) # More realistic first open


        data = {
            'open': open_prices,
            'high': 0.0,
            'low': 0.0,
            'close': close_prices,
            'volume': np.random.randint(10000, 100000, size=num_bars)
        }
        df = pd.DataFrame(data, index=dates)
        df['high'] = df[['open', 'close']].max(axis=1) + abs(np.random.normal(0, 0.01 * start_price, size=num_bars)) # Scale volatility with price
        df['low'] = df[['open', 'close']].min(axis=1) - abs(np.random.normal(0, 0.01 * start_price, size=num_bars))
        df['low'] = np.minimum(df['low'], df[['open', 'close', 'high']].min(axis=1))
        df['high'] = np.maximum(df['high'], df[['open', 'close', 'low']].max(axis=1))
        df['low'] = np.maximum(0.0001, df['low']) # Ensure low is positive

        # print(f"PositionTraderAgent: Mock W1 data for {pair} (last 3 bars):\n{df.tail(3)}")
        return df

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
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
        print(f"PositionTraderAgent '{self.agent_id}': Received directive - {strategic_directive.get('key_narrative')}")
        trade_proposals = []

        focus_pairs = strategic_directive.get("focus_pairs", [])
        directive_confidence = strategic_directive.get("confidence_in_bias", "low").lower()

        if directive_confidence not in ["high", "medium"]:
            print(f"PositionTraderAgent '{self.agent_id}': Directive confidence '{directive_confidence}' too low for position trading. Requires 'medium' or 'high'.")
            return []

        for pair in focus_pairs:
            print(f"PositionTraderAgent '{self.agent_id}': Analyzing pair {pair}")
            # market_data_df = self.broker_interface.get_historical_data(pair, "W1", count=200) # 'W1' for weekly
            market_data_df = self._create_mock_data(pair, num_bars=200, freq='W-MON')

            if market_data_df is None or market_data_df.empty or len(market_data_df) < 50:
                print(f"PositionTraderAgent '{self.agent_id}': Insufficient market data for {pair} (need >50 bars). Got: {len(market_data_df) if market_data_df is not None else 0}")
                continue

            try:
                market_data_df.ta.sma(length=20, append=True, col="SMA_20W")
                market_data_df.ta.sma(length=50, append=True, col="SMA_50W")
            except Exception as e:
                print(f"PositionTraderAgent '{self.agent_id}': Error calculating indicators for {pair}: {e}")
                continue

            required_cols = ["SMA_20W", "SMA_50W"]
            if not all(col in market_data_df.columns for col in required_cols):
                print(f"PositionTraderAgent '{self.agent_id}': Could not calculate all indicators for {pair}.")
                continue

            latest_data = market_data_df.iloc[-1]
            # previous_data = market_data_df.iloc[-2] # Not used in this simple SMA logic

            current_price = latest_data["close"]
            confidence = 0.5
            rationale_parts = [f"Position analysis for {pair}: Directive confidence: {directive_confidence}."]
            trade_side = None

            pair_bias_direction = self._get_pair_bias_from_directive(pair, strategic_directive)
            rationale_parts.append(f"Interpreted directive bias for {pair}: {pair_bias_direction if pair_bias_direction else 'none/neutral'}.")


            if pair_bias_direction == "bullish":
                rationale_parts.append("Strategic directive strongly bullish.")
                if current_price > latest_data["SMA_20W"] and latest_data["SMA_20W"] > latest_data["SMA_50W"]:
                    trade_side = "buy"
                    confidence = 0.75 if directive_confidence == "high" else 0.60
                    rationale_parts.append("Price above 20W & 50W SMAs; 20W SMA above 50W SMA (long-term uptrend).")
                else:
                    rationale_parts.append("Price action not confirming long-term bullish SMA structure.")

            elif pair_bias_direction == "bearish":
                rationale_parts.append("Strategic directive strongly bearish.")
                if current_price < latest_data["SMA_20W"] and latest_data["SMA_20W"] < latest_data["SMA_50W"]:
                    trade_side = "sell"
                    confidence = 0.75 if directive_confidence == "high" else 0.60
                    rationale_parts.append("Price below 20W & 50W SMAs; 20W SMA below 50W SMA (long-term downtrend).")
                else:
                    rationale_parts.append("Price action not confirming long-term bearish SMA structure.")
            else:
                rationale_parts.append(f"Directive for {pair} is '{pair_bias_direction}', not suitable for clear position trade based on SMA logic.")


            if trade_side:
                pips_sl_abs = 0.0500
                pips_tp_abs = 0.1000
                decimals = 5
                if "JPY" in pair.upper():
                    pips_sl_abs = 5.00
                    pips_tp_abs = 10.00
                    decimals = 3

                # More robust SL/TP placement based on % of price or ATR if available
                # For now, using absolute pips from current price
                sl_price = current_price - pips_sl_abs if trade_side == "buy" else current_price + pips_sl_abs
                tp_price = current_price + pips_tp_abs if trade_side == "buy" else current_price - pips_tp_abs

                trade_proposals.append({
                    "pair": pair, "type": "market", "side": trade_side,
                    "entry_price": None,
                    "stop_loss": round(sl_price, decimals),
                    "take_profit": round(tp_price, decimals),
                    "confidence_score": confidence, "origin_agent": self.agent_id,
                    "rationale": " ".join(rationale_parts) + f" Key Narrative Snippet: {strategic_directive.get('key_narrative', '')[:100]}..."
                })

        if not trade_proposals:
            print(f"PositionTraderAgent '{self.agent_id}': No compelling position trade opportunities found for pairs: {focus_pairs}.")
        else:
            print(f"PositionTraderAgent '{self.agent_id}': Generated {len(trade_proposals)} proposals.")
            for prop_idx, prop in enumerate(trade_proposals):
                 print(f"  Proposal {prop_idx+1}: {prop['pair']} {prop['side']}, SL: {prop['stop_loss']}, TP: {prop['take_profit']}, Conf: {prop['confidence_score']}, Rat: {prop['rationale']}")

        return trade_proposals
