# In TradingAgents/tradingagents/forex_agents/scalper_agent.py
import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Any, Dict, List, Optional

class ScalperAgent:
    def __init__(self, agent_id: str, llm: Any, memory: Any, broker_interface: Any):
        self.agent_id = agent_id
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.broker_interface = broker_interface # Placeholder
        # print(f"ScalperAgent '{self.agent_id}' initialized.")

    def _create_mock_data(self, pair: str, num_bars: int = 60, freq: str = 'T') -> pd.DataFrame: # 'T' for minutes
        # Create mock OHLCV data for M1 timeframe
        dates = pd.date_range(end=pd.Timestamp.now(tz='UTC'), periods=num_bars, freq=freq)

        start_price = np.random.uniform(1.05, 1.15)
        if "JPY" in pair.upper():
            start_price = np.random.uniform(140.0, 160.0)

        price_changes = np.random.normal(0, 0.00005, size=num_bars) # Very small changes for M1 ticks effectively
        if "JPY" in pair.upper():
            price_changes = np.random.normal(0, 0.005, size=num_bars)

        close_prices = start_price + np.cumsum(price_changes)
        # Ensure prices are positive
        close_prices[close_prices <= 0] = start_price / 2 # Reset to a positive floor if it goes negative

        open_prices = np.roll(close_prices, 1) # Open is previous close for simplicity here
        open_prices[0] = close_prices[0] - price_changes[0] # Adjust first open

        data = {
            'open': open_prices,
            'high': np.maximum(open_prices, close_prices) + np.random.uniform(0.00001, 0.0001, size=num_bars),
            'low': np.minimum(open_prices, close_prices) - np.random.uniform(0.00001, 0.0001, size=num_bars),
            'close': close_prices,
            'volume': np.random.randint(10, 100, size=num_bars)
        }
        df = pd.DataFrame(data, index=dates)

        df['high'] = np.maximum(df['high'], df[['open', 'close']].max(axis=1))
        df['low'] = np.minimum(df['low'], df[['open', 'close']].min(axis=1))

        # Ensure low <= open, close, high and high >= open, close, low
        df['low'] = np.minimum(df['low'], df[['open', 'close', 'high']].min(axis=1))
        df['high'] = np.maximum(df['high'], df[['open', 'close', 'low']].max(axis=1))

        # print(f"ScalperAgent: Mock M1 data for {pair} (last 3 bars):\n{df.tail(3)}")
        return df

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
        directive_bias_info = strategic_directive.get("primary_bias", {})
        pair_bias_direction = None
        if isinstance(directive_bias_info.get("pair"), str) and directive_bias_info.get("pair") == pair:
            pair_bias_direction = directive_bias_info.get("direction")
        elif isinstance(directive_bias_info.get("currency"), str):
            base_currency, quote_currency = pair.split("/") if "/" in pair else (None, None)
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
        print(f"ScalperAgent '{self.agent_id}': Received directive - {strategic_directive.get('key_narrative')}")
        trade_proposals = []

        focus_pairs = strategic_directive.get("focus_pairs", [])

        for pair in focus_pairs:
            print(f"ScalperAgent '{self.agent_id}': Analyzing pair {pair}")
            # market_data_df = self.broker_interface.get_historical_data(pair, "M1", count=60)
            market_data_df = self._create_mock_data(pair, num_bars=60, freq='T')

            if market_data_df is None or market_data_df.empty or len(market_data_df) < 20:
                print(f"ScalperAgent '{self.agent_id}': Insufficient market data for {pair} (need >20 bars). Got: {len(market_data_df) if market_data_df is not None else 0}")
                continue

            try:
                market_data_df.ta.ema(length=5, append=True, col="EMA_5")
                market_data_df.ta.ema(length=10, append=True, col="EMA_10")
                stoch = market_data_df.ta.stoch(k=5, d=3, smooth_k=3, append=False)
                if stoch is not None and not stoch.empty:
                    market_data_df['STOCH_K'] = stoch.iloc[:,0]
                    market_data_df['STOCH_D'] = stoch.iloc[:,1]
            except Exception as e:
                print(f"ScalperAgent '{self.agent_id}': Error calculating indicators for {pair}: {e}")
                continue

            required_cols = ["EMA_5", "EMA_10", "STOCH_K", "STOCH_D"]
            if not all(col in market_data_df.columns for col in required_cols):
                print(f"ScalperAgent '{self.agent_id}': Could not calculate all indicators for {pair}.")
                continue

            latest_data = market_data_df.iloc[-1]
            previous_data = market_data_df.iloc[-2]

            current_price = latest_data["close"]
            confidence = 0.5
            rationale_parts = [f"Scalp analysis for {pair}:"]
            trade_side = None

            pair_bias_direction = self._get_pair_bias_from_directive(pair, strategic_directive)
            rationale_parts.append(f"Directive bias for {pair}: {pair_bias_direction if pair_bias_direction else 'none/neutral'}.")

            # Scalping logic: EMA crossover + Stochastic confirmation
            # Allow trades if bias matches or if bias is 'ranging' (scalper might find opportunities)
            can_buy = pair_bias_direction in ["bullish", "ranging", None] # None bias means no strong counter-signal
            can_sell = pair_bias_direction in ["bearish", "ranging", None]

            if can_buy and previous_data["EMA_5"] < previous_data["EMA_10"] and latest_data["EMA_5"] > latest_data["EMA_10"]:
                rationale_parts.append("Bullish EMA crossover (5/10).")
                if latest_data["STOCH_K"] < 80 and latest_data["STOCH_D"] < 80 and latest_data["STOCH_K"] > latest_data["STOCH_D"]: # Stochastic rising and not overbought
                    trade_side = "buy"
                    confidence = 0.60
                    rationale_parts.append(f"Stoch K({latest_data['STOCH_K']:.2f}) / D({latest_data['STOCH_D']:.2f}) bullish confirmation.")
                else:
                    rationale_parts.append(f"Stoch K({latest_data['STOCH_K']:.2f}) / D({latest_data['STOCH_D']:.2f}) no bullish confirmation.")

            # Check for sell only if no buy signal was confirmed (to avoid immediate flip-flop on same bar)
            if not trade_side and can_sell and previous_data["EMA_5"] > previous_data["EMA_10"] and latest_data["EMA_5"] < latest_data["EMA_10"]:
                rationale_parts.append("Bearish EMA crossover (5/10).")
                if latest_data["STOCH_K"] > 20 and latest_data["STOCH_D"] > 20 and latest_data["STOCH_K"] < latest_data["STOCH_D"]: # Stochastic falling and not oversold
                    trade_side = "sell"
                    confidence = 0.60
                    rationale_parts.append(f"Stoch K({latest_data['STOCH_K']:.2f}) / D({latest_data['STOCH_D']:.2f}) bearish confirmation.")
                else:
                    rationale_parts.append(f"Stoch K({latest_data['STOCH_K']:.2f}) / D({latest_data['STOCH_D']:.2f}) no bearish confirmation.")

            if not trade_side :
                 rationale_parts.append("No qualifying EMA/Stochastic signal found under current bias.")


            if trade_side:
                pips_sl = 0.0007
                pips_tp = 0.0012
                decimals = 5
                if "JPY" in pair.upper():
                    pips_sl = 0.07
                    pips_tp = 0.12
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
            print(f"ScalperAgent '{self.agent_id}': No compelling scalping opportunities found for pairs: {focus_pairs}.")
        else:
            print(f"ScalperAgent '{self.agent_id}': Generated {len(trade_proposals)} proposals.")
            for prop_idx, prop in enumerate(trade_proposals):
                 print(f"  Proposal {prop_idx+1}: {prop['pair']} {prop['side']}, SL: {prop['stop_loss']}, TP: {prop['take_profit']}, Conf: {prop['confidence_score']}, Rat: {prop['rationale']}")

        return trade_proposals
