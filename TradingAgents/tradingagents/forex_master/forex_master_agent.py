from typing import Any, Dict, List, Optional
# from tradingagents.agents.utils.memory import FinancialSituationMemory # Assuming this will be used
# from langchain_core.language_models.base import BaseLanguageModel # Assuming LLM type

class ForexMasterAgent:
    def __init__(self, llm: Any, memory: Any): # Replace Any with actual types later
        self.llm = llm
        self.memory = memory
        # print(f"ForexMasterAgent initialized with LLM: {self.llm} and Memory: {self.memory}") # Reduced verbosity

    def get_strategic_directive(self, market_outlook: Dict[str, Any], user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        print(f"ForexMasterAgent received market_outlook: {market_outlook}, user_preferences: {user_preferences}")

        # Initialize default directive
        directive = {
            "primary_bias": {"market_condition": "neutral", "pairs": []},
            "confidence_in_bias": "low",
            "preferred_timeframes": ["medium_term"],
            "volatility_expectation": "moderate",
            "focus_pairs": [],
            "key_narrative": "Default neutral stance. Awaiting clearer signals or preferences.",
            "key_levels_to_watch": {}
        }

        # Process market_outlook
        sentiment = market_outlook.get("sentiment", {}) # e.g., {"EUR": "bullish", "USD": "bearish", "AUD/JPY": "ranging"}
        outlook_volatility = market_outlook.get("volatility_forecast") # e.g., "low", "moderate", "high"
        market_summary = market_outlook.get("summary", "General market conditions are being assessed.")

        # Determine primary bias from sentiment
        strongest_sentiment_currency_or_pair = None
        strongest_sentiment_direction = "neutral"
        highest_sentiment_strength = 0 # 0: neutral, 1: weak, 2: moderate, 3: strong

        sentiment_map = {
            "weak_bearish": -1, "bearish": -2, "strong_bearish": -3,
            "weak_bullish": 1, "bullish": 2, "strong_bullish": 3,
            "neutral": 0, "ranging": 0
        }

        # Prioritize pair sentiment if available and strong
        for item, item_sentiment_str in sentiment.items():
            if "/" in item: # It's a pair
                current_strength = abs(sentiment_map.get(item_sentiment_str.lower(), 0))
                current_direction = "bullish" if sentiment_map.get(item_sentiment_str.lower(), 0) > 0 else \
                                    ("bearish" if sentiment_map.get(item_sentiment_str.lower(), 0) < 0 else "ranging")
                if current_strength > highest_sentiment_strength:
                    highest_sentiment_strength = current_strength
                    strongest_sentiment_currency_or_pair = item
                    strongest_sentiment_direction = current_direction
                    directive["primary_bias"] = {"pair": item, "direction": current_direction if current_direction != "ranging" else "ranging_on_pair"}

        # If no strong pair sentiment, check single currency sentiment
        if highest_sentiment_strength < 2: # Arbitrary threshold to prefer strong pair sentiment
            for item, item_sentiment_str in sentiment.items():
                if "/" not in item: # It's a single currency
                    current_strength = abs(sentiment_map.get(item_sentiment_str.lower(), 0))
                    current_direction = "bullish" if sentiment_map.get(item_sentiment_str.lower(), 0) > 0 else \
                                        ("bearish" if sentiment_map.get(item_sentiment_str.lower(), 0) < 0 else "neutral")
                    if current_strength > highest_sentiment_strength:
                        highest_sentiment_strength = current_strength
                        strongest_sentiment_currency_or_pair = item
                        strongest_sentiment_direction = current_direction
                        directive["primary_bias"] = {"currency": item, "direction": current_direction}

        if highest_sentiment_strength == 3:
            directive["confidence_in_bias"] = "high"
        elif highest_sentiment_strength == 2:
            directive["confidence_in_bias"] = "medium"
        else: # covers 0 and 1
            directive["confidence_in_bias"] = "low"
            if not strongest_sentiment_currency_or_pair : # if truly neutral or only weak signals
                 directive["primary_bias"] = {"market_condition": "neutral_or_mixed_signals"}


        if outlook_volatility:
            directive["volatility_expectation"] = outlook_volatility.lower()
        if market_outlook.get("key_levels"): # Ensure this matches the key in market_outlook
            directive["key_levels_to_watch"] = market_outlook["key_levels"]

        # Process user_preferences
        risk_appetite = user_preferences.get("risk_appetite", "moderate").lower()
        preferred_pairs_user = user_preferences.get("preferred_pairs", [])
        trading_style_preference = user_preferences.get("trading_style_preference", "swing_trader").lower()

        if risk_appetite == "conservative":
            if directive["confidence_in_bias"] == "high":
                directive["confidence_in_bias"] = "medium"
            if directive["volatility_expectation"] == "high":
                directive["volatility_expectation"] = "moderate"
            elif directive["volatility_expectation"] == "moderate":
                directive["volatility_expectation"] = "low"

        user_style_narrative = "User preference considered."
        if trading_style_preference == "scalper":
            directive["preferred_timeframes"] = ["scalping", "m1", "m5"]
            user_style_narrative = "User prefers scalping."
        elif trading_style_preference == "day_trader":
            directive["preferred_timeframes"] = ["intraday", "m5", "m15", "h1"]
            user_style_narrative = "User prefers day trading."
        elif trading_style_preference == "swing_trader":
            directive["preferred_timeframes"] = ["short_term", "medium_term", "h4", "d1"]
            user_style_narrative = "User prefers swing trading."
        elif trading_style_preference == "position_trader":
            directive["preferred_timeframes"] = ["long_term", "d1", "w1"]
            user_style_narrative = "User prefers position trading."

        if preferred_pairs_user:
            directive["focus_pairs"] = preferred_pairs_user
        elif strongest_sentiment_currency_or_pair and "/" in strongest_sentiment_currency_or_pair:
            directive["focus_pairs"] = [strongest_sentiment_currency_or_pair]
        elif strongest_sentiment_currency_or_pair:
            # Example default pairs based on single currency sentiment
            if strongest_sentiment_currency_or_pair == "USD" and strongest_sentiment_direction == "bullish":
                directive["focus_pairs"] = ["EUR/USD", "GBP/USD", "USD/JPY"] # Expect USD to rise
            elif strongest_sentiment_currency_or_pair == "USD" and strongest_sentiment_direction == "bearish":
                directive["focus_pairs"] = ["EUR/USD", "GBP/USD", "USD/JPY"] # Expect USD to fall
            elif strongest_sentiment_currency_or_pair == "EUR" and strongest_sentiment_direction == "bullish":
                directive["focus_pairs"] = ["EUR/USD", "EUR/JPY", "EUR/GBP"]
            elif strongest_sentiment_currency_or_pair == "EUR" and strongest_sentiment_direction == "bearish":
                directive["focus_pairs"] = ["EUR/USD", "EUR/JPY", "EUR/GBP"]
            else: # Fallback if specific currency logic isn't exhaustive
                directive["focus_pairs"] = ["EUR/USD", "USD/JPY", "GBP/USD"]
        else: # Absolute fallback
            directive["focus_pairs"] = ["EUR/USD", "USD/JPY", "GBP/USD"]


        # Formulate key_narrative
        bias_info = directive["primary_bias"]
        bias_desc = ""
        if "pair" in bias_info:
            bias_desc = f"{bias_info['direction']} on {bias_info['pair']}"
        elif "currency" in bias_info:
            bias_desc = f"{bias_info['direction']} on {bias_info['currency']}"
        else:
            bias_desc = bias_info.get("market_condition", "mixed")

        narrative = f"Strategic Directive: Primary bias is {bias_desc} with {directive['confidence_in_bias']} confidence. "
        narrative += f"Focus on {', '.join(directive['focus_pairs'])} using {', '.join(directive['preferred_timeframes'])} timeframes. "
        narrative += f"Volatility expectation: {directive['volatility_expectation']}. "
        narrative += f"Market Summary: {market_summary} User trading style: {trading_style_preference}."

        directive["key_narrative"] = narrative

        print(f"ForexMasterAgent generated strategic_directive: {directive}")
        return directive
