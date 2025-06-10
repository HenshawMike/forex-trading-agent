import os
import json
import pandas as pd
import pandas_ta as ta
import numpy as np
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("DayTraderAgent WARNING: LangChain packages not found. LLM functionality will be disabled.")
    LANGCHAIN_AVAILABLE = False
    # Define dummy classes for type hinting and basic structure if langchain is not available
    class ChatOpenAI: # type: ignore
        def __init__(self, model_name: str, temperature: float): pass
    class ChatPromptTemplate: # type: ignore
        @staticmethod
        def from_messages(messages): pass
    class JsonOutputParser: # type: ignore
        def __init__(self): pass

class DayTraderAgent:
    def __init__(self, agent_id: str, llm_model_name: str = "gpt-3.5-turbo", memory: Any = None, broker_interface: Any = None):
        self.agent_id = agent_id
        self.llm_model_name = llm_model_name
        self.memory = memory # Placeholder
        self.broker_interface = broker_interface
        self.llm_client = None

        if not LANGCHAIN_AVAILABLE:
            print(f"DayTraderAgent ({self.agent_id}) INFO: LangChain not available. Using rule-based logic only.")
        elif not os.getenv("OPENAI_API_KEY"):
            print(f"DayTraderAgent ({self.agent_id}) WARNING: OPENAI_API_KEY not set. Using rule-based logic only.")
        else:
            try:
                self.llm_client = ChatOpenAI(model_name=self.llm_model_name, temperature=0.7) # type: ignore
                print(f"DayTraderAgent ({self.agent_id}) initialized with LLM: {self.llm_model_name}")
            except Exception as e:
                print(f"DayTraderAgent ({self.agent_id}) WARNING: Failed to initialize ChatOpenAI. Error: {e}. Using rule-based logic only.")
                self.llm_client = None

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
        directive_bias_info = strategic_directive.get("primary_bias", {})
        pair_bias_direction = None
        if directive_bias_info.get("pair") == pair:
            pair_bias_direction = directive_bias_info.get("direction")
        elif directive_bias_info.get("currency"):
            base_currency, quote_currency = pair.split("/")
            if directive_bias_info["currency"] == base_currency:
                pair_bias_direction = directive_bias_info.get("direction")
            elif directive_bias_info["currency"] == quote_currency:
                if directive_bias_info.get("direction") == "bullish": pair_bias_direction = "bearish"
                elif directive_bias_info.get("direction") == "bearish": pair_bias_direction = "bullish"

        # If primary bias doesn't directly apply, check secondary or market condition
        if not pair_bias_direction:
            secondary_bias_info = strategic_directive.get("secondary_bias", {})
            if secondary_bias_info.get("pair") == pair:
                 pair_bias_direction = secondary_bias_info.get("direction")
            elif secondary_bias_info.get("currency"):
                base_currency, quote_currency = pair.split("/")
                if secondary_bias_info["currency"] == base_currency: pair_bias_direction = secondary_bias_info.get("direction")
                elif secondary_bias_info["currency"] == quote_currency:
                    if secondary_bias_info.get("direction") == "bullish": pair_bias_direction = "bearish"
                    elif secondary_bias_info.get("direction") == "bearish": pair_bias_direction = "bullish"

        if not pair_bias_direction and strategic_directive.get("market_outlook", {}).get("overall_sentiment", "").lower() == "ranging":
             return "ranging" # General market condition
        if not pair_bias_direction and directive_bias_info.get("market_condition") in ["ranging", "neutral_or_mixed_signals", "neutral", "ranging_on_pair"]:
            return "ranging" # More specific condition from directive

        return pair_bias_direction

    def _get_rule_based_proposal(self, pair: str, market_data_df: pd.DataFrame, strategic_directive: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # print(f"DayTraderAgent ({self.agent_id}): Applying rule-based logic for {pair}")
        if not all(col in market_data_df.columns for col in ["EMA_10", "EMA_20", "RSI_14"]):
            print(f"DayTraderAgent ({self.agent_id}): Rule-based: Could not calculate all indicators for {pair}. Available: {market_data_df.columns}")
            return None

        latest_data = market_data_df.iloc[-1]
        previous_data = market_data_df.iloc[-2] if len(market_data_df) >= 2 else latest_data
        current_price = latest_data["close"]
        confidence = 0.5
        rationale_parts = ["Rule-based decision."]
        trade_side = None
        pair_bias_direction = self._get_pair_bias_from_directive(pair, strategic_directive)

        rationale_parts.append(f"Directive bias for {pair} is '{pair_bias_direction if pair_bias_direction else 'neutral/unclear'}'.")

        if pair_bias_direction == "bullish":
            if previous_data["EMA_10"] < previous_data["EMA_20"] and latest_data["EMA_10"] > latest_data["EMA_20"]: # Bullish crossover
                if latest_data["RSI_14"] < 70: # Not overbought
                    trade_side = "buy"; confidence = 0.65
                    rationale_parts.extend(["Bullish EMA crossover (10/20).", f"RSI ({latest_data['RSI_14']:.2f}) not overbought."])
                else: rationale_parts.append(f"EMA crossover but RSI ({latest_data['RSI_14']:.2f}) overbought.")
            else: rationale_parts.append("No bullish EMA crossover signal.")
        elif pair_bias_direction == "bearish":
            if previous_data["EMA_10"] > previous_data["EMA_20"] and latest_data["EMA_10"] < latest_data["EMA_20"]: # Bearish crossover
                if latest_data["RSI_14"] > 30: # Not oversold
                    trade_side = "sell"; confidence = 0.65
                    rationale_parts.extend(["Bearish EMA crossover (10/20).", f"RSI ({latest_data['RSI_14']:.2f}) not oversold."])
                else: rationale_parts.append(f"EMA crossover but RSI ({latest_data['RSI_14']:.2f}) oversold.")
            else: rationale_parts.append("No bearish EMA crossover signal.")
        else: # Ranging or no clear bias from directive
            rationale_parts.append("No strong directional signal from rules or directive bias for ranging market.")

        if trade_side:
            pips_sl = 0.0020; pips_tp = 0.0040 # Default for non-JPY pairs
            if "JPY" in pair.upper(): pips_sl = 0.20; pips_tp = 0.40

            sl_price = current_price - pips_sl if trade_side == "buy" else current_price + pips_sl
            tp_price = current_price + pips_tp if trade_side == "buy" else current_price - pips_tp
            return {
                "pair": pair, "type": "market", "side": trade_side, "entry_price": None, # Market order, entry price TBD by broker
                "stop_loss": round(sl_price, 5 if "JPY" not in pair.upper() else 3),
                "take_profit": round(tp_price, 5 if "JPY" not in pair.upper() else 3),
                "confidence_score": confidence, "origin_agent": self.agent_id,
                "rationale": " ".join(rationale_parts), "llm_generated_proposal": False
            }
        return None

    def analyze_and_propose_trades(self, strategic_directive: Dict[str, Any]) -> List[Dict[str, Any]]:
        print(f"DayTraderAgent ({self.agent_id}) received directive: {strategic_directive.get('key_narrative', 'N/A')}")
        all_proposals = []
        focus_pairs = strategic_directive.get("focus_pairs", [])
        if not focus_pairs:
            print(f"DayTraderAgent ({self.agent_id}): No focus pairs in directive.")
            return []

        for pair in focus_pairs:
            print(f"DayTraderAgent ({self.agent_id}): Analyzing {pair}...")
            # Day trading typically uses shorter timeframes like M15 or M5
            raw_market_data = self.broker_interface.get_historical_data(pair=pair, timeframe="M15", count=50) # Approx 12.5 hours of data

            if raw_market_data is None or not raw_market_data:
                print(f"DayTraderAgent ({self.agent_id}): No market data from broker for {pair}")
                continue
            try:
                market_data_df = pd.DataFrame(raw_market_data)
                if 'time' in market_data_df.columns:
                    market_data_df['time'] = pd.to_datetime(market_data_df['time'])
                    market_data_df.set_index('time', inplace=True)
                else:
                    print(f"DayTraderAgent ({self.agent_id}): 'time' column missing in data for {pair}. Skipping."); continue
                required_ohlcv = ['open', 'high', 'low', 'close', 'volume']
                if not all(col in market_data_df.columns for col in required_ohlcv):
                    print(f"DayTraderAgent ({self.agent_id}): Missing OHLCV columns in data for {pair}. Skipping."); continue
            except Exception as e:
                print(f"DayTraderAgent ({self.agent_id}): Error converting data for {pair}: {e}"); continue

            if market_data_df.empty or len(market_data_df) < 20: # Need enough data for indicators
                print(f"DayTraderAgent ({self.agent_id}): Insufficient data for {pair} (need >=20 bars, got {len(market_data_df)}). Skipping."); continue

            # Calculate indicators
            market_data_df.ta.ema(length=10, append=True, col="EMA_10") # Fast EMA
            market_data_df.ta.ema(length=20, append=True, col="EMA_20") # Slow EMA
            market_data_df.ta.rsi(length=14, append=True, col="RSI_14")
            try: # MACD can sometimes fail with very short data series or specific values
                macd_df = market_data_df.ta.macd(fast=12, slow=26, signal=9, append=False) # Standard MACD params
                if macd_df is not None and not macd_df.empty:
                    market_data_df['MACD_line'] = macd_df.iloc[:,0] # MACD line
                    market_data_df['MACD_signal'] = macd_df.iloc[:,1] # Signal line
                    market_data_df['MACD_hist'] = macd_df.iloc[:,2] # Histogram
                else: market_data_df['MACD_line'] = np.nan; market_data_df['MACD_signal'] = np.nan; market_data_df['MACD_hist'] = np.nan
            except Exception as e_macd:
                print(f"DayTraderAgent ({self.agent_id}): Error calculating MACD for {pair}: {e_macd}. Proceeding without MACD.")
                market_data_df['MACD_line'] = np.nan; market_data_df['MACD_signal'] = np.nan; market_data_df['MACD_hist'] = np.nan


            if not self.llm_client:
                # print(f"DayTraderAgent ({self.agent_id}): LLM client not available for {pair}. Using rule-based.")
                proposal = self._get_rule_based_proposal(pair, market_data_df, strategic_directive)
                if proposal: all_proposals.append(proposal)
                continue

            # LLM Path
            try:
                print(f"DayTraderAgent ({self.agent_id}): Invoking LLM for {pair}...")
                system_message = ("You are an expert Day Trader AI. Analyze the provided strategic directive, latest market data (OHLC), "
                                  "and technical indicators for a specific currency pair. Decide whether to 'buy', 'sell', or 'hold'. "
                                  "If proposing a trade, provide a confidence score (0.0-1.0, where 1.0 is highest confidence), "
                                  "a concise rationale (1-2 sentences highlighting key reasons), and suggest specific stop_loss and take_profit prices. "
                                  "The stop_loss should be reasonably tight for day trading (e.g. 15-30 pips for non-JPY, 0.15-0.30 for JPY pairs). The take_profit should aim for at least 1:1.5 risk/reward. "
                                  "Return your decision as a SINGLE JSON object with keys: 'pair' (string, same as input), 'action' ('buy'|'sell'|'hold'), "
                                  "'confidence' (float), 'rationale' (string), 'stop_loss' (float), 'take_profit' (float). "
                                  "If 'hold', other fields like confidence, rationale, sl, tp can be null or omitted. Base your SL/TP on the current_price provided.")
                human_template = ("Strategic Directive: {directive_str}\nPair: {current_pair}\n"
                                  "Latest Data (last 3 bars OHLCV, most recent last): {data_str}\n"
                                  "Latest Indicators: EMA10={ema10:.5f}, EMA20={ema20:.5f}, RSI14={rsi14:.2f}, "
                                  "MACD_line={macd_line:.5f}, MACD_signal={macd_signal:.5f}, MACD_hist={macd_hist:.5f}.\n"
                                  "Current Close Price: {current_price:.5f}. Provide your JSON decision.")

                prompt = ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])
                parser = JsonOutputParser()
                chain = prompt | self.llm_client | parser

                latest_indicators = market_data_df.iloc[-1]
                llm_input = {
                    "directive_str": json.dumps(strategic_directive), "current_pair": pair,
                    "data_str": market_data_df.tail(3)[['open', 'high', 'low', 'close', 'volume']].to_json(orient="records", date_format="iso"),
                    "ema10": latest_indicators.get("EMA_10", 0.0), "ema20": latest_indicators.get("EMA_20", 0.0),
                    "rsi14": latest_indicators.get("RSI_14", 50.0),
                    "macd_line": latest_indicators.get("MACD_line", 0.0), "macd_signal": latest_indicators.get("MACD_signal", 0.0), "macd_hist": latest_indicators.get("MACD_hist", 0.0),
                    "current_price": latest_indicators.get("close", 0.0)
                }
                llm_response = chain.invoke(llm_input)

                if llm_response and isinstance(llm_response, dict) and llm_response.get("action") in ["buy", "sell"]:
                    if not all(k in llm_response for k in ["confidence", "rationale", "stop_loss", "take_profit"]):
                        print(f"DayTraderAgent ({self.agent_id}): LLM response for {pair} trade action missing required fields. Resp: {llm_response}")
                        raise ValueError("LLM response for trade action missing required fields.")

                    all_proposals.append({
                        "pair": pair, "type": "market", "side": llm_response["action"],
                        "entry_price": None, # Market order
                        "stop_loss": float(llm_response["stop_loss"]),
                        "take_profit": float(llm_response["take_profit"]),
                        "confidence_score": float(llm_response["confidence"]),
                        "origin_agent": self.agent_id,
                        "rationale": llm_response["rationale"], "llm_generated_proposal": True
                    })
                    print(f"DayTraderAgent ({self.agent_id}): LLM proposed {llm_response['action']} for {pair}.")
                else:
                    action_taken = llm_response.get('action', 'N/A') if isinstance(llm_response, dict) else "Invalid LLM response format"
                    print(f"DayTraderAgent ({self.agent_id}): LLM decided 'hold' or invalid action for {pair}. Action: {action_taken}")

            except Exception as e:
                print(f"DayTraderAgent ({self.agent_id}): LLM call/parsing failed for {pair}: {e}. Using rule-based.")
                proposal = self._get_rule_based_proposal(pair, market_data_df, strategic_directive)
                if proposal: all_proposals.append(proposal)

        if not all_proposals:
            print(f"DayTraderAgent ({self.agent_id}): No trade proposals generated for any focus pair.")
        else:
            print(f"DayTraderAgent ({self.agent_id}) generated {len(all_proposals)} total proposals.")
            # for prop in all_proposals: print(json.dumps(prop, indent=2)) # Can be verbose for debugging

        return all_proposals

```
