import os
import json
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    # Define dummy classes if langchain is not available
    class ChatOpenAI:
        def __init__(self, model_name: str, temperature: float):
            pass
    class ChatPromptTemplate:
        @staticmethod
        def from_messages(messages: List):
            return None # Or a dummy object that can be invoked
    class JsonOutputParser:
        def __init__(self):
            pass


class ForexMasterAgent:
    def __init__(self, llm_model_name: str = "gpt-3.5-turbo", memory: Any = None): # memory is not used yet
        self.llm_model_name = llm_model_name
        self.memory = memory
        self.llm_client: Optional[ChatOpenAI] = None # Correct type hint

        if not LANGCHAIN_AVAILABLE:
            print("ForexMasterAgent WARNING: langchain_openai or related packages not found. LLM functionality will be disabled. Falling back to rule-based logic.")
        elif not os.getenv("OPENAI_API_KEY") and "gpt" in self.llm_model_name.lower(): # Check only if intending to use OpenAI models
            print("ForexMasterAgent WARNING: OPENAI_API_KEY environment variable not set for OpenAI model. LLM functionality will be disabled. Falling back to rule-based logic.")
        else:
            try:
                # Only initialize if it's an OpenAI model type, otherwise assume different client or it's a placeholder
                if "gpt" in self.llm_model_name.lower() or isinstance(llm_model_name, ChatOpenAI): # Allow passing instance for testing
                     self.llm_client = ChatOpenAI(model_name=self.llm_model_name, temperature=0.7) if isinstance(llm_model_name, str) else llm_model_name
                     print(f"ForexMasterAgent initialized with LLM: {self.llm_model_name}")
                elif llm_model_name == "PlaceholderLLM": # From graph test script
                     self.llm_client = llm_model_name # Accept the placeholder instance
                     print(f"ForexMasterAgent initialized with PlaceholderLLM.")
                else:
                     print(f"ForexMasterAgent WARNING: LLM model '{self.llm_model_name}' not recognized as OpenAI or Placeholder. LLM calls might fail or use different client. Falling back to rule-based logic for safety.")
                     self.llm_client = None # Ensure it's None if not a recognized type that can be initialized here
            except Exception as e:
                print(f"ForexMasterAgent WARNING: Failed to initialize ChatOpenAI with model {self.llm_model_name}. Error: {e}. LLM functionality disabled. Falling back to rule-based logic.")
                self.llm_client = None

    def _get_rule_based_directive(self, market_outlook: Dict[str, Any], user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        # print(f"ForexMasterAgent (Rule-Based Fallback) received market_outlook: {market_outlook}, user_preferences: {user_preferences}")
        directive = {
            "primary_bias": {"market_condition": "neutral", "pairs": []},
            "confidence_in_bias": "low",
            "preferred_timeframes": ["medium_term"],
            "volatility_expectation": "moderate",
            "focus_pairs": [],
            "key_narrative": "Default neutral stance (rule-based fallback). Awaiting clearer signals or preferences.",
            "key_levels_to_watch": {},
            "llm_generated": False
        }
        sentiment = market_outlook.get("sentiment", {})
        outlook_volatility = market_outlook.get("volatility_forecast")
        market_summary = market_outlook.get("summary", "General market conditions assessed by rules.")

        strongest_sentiment_currency_or_pair = None
        strongest_sentiment_direction = "neutral"
        highest_sentiment_strength = 0
        sentiment_map = {
            "weak_bearish": -1, "bearish": -2, "strong_bearish": -3,
            "weak_bullish": 1, "bullish": 2, "strong_bullish": 3,
            "neutral": 0, "ranging": 0
        }

        for item, item_sentiment_str_any in sentiment.items():
            item_sentiment_str = str(item_sentiment_str_any).lower()
            current_strength = abs(sentiment_map.get(item_sentiment_str, 0))
            current_direction = "bullish" if sentiment_map.get(item_sentiment_str, 0) > 0 else \
                                ("bearish" if sentiment_map.get(item_sentiment_str, 0) < 0 else "ranging")
            if "/" in item :
                if current_strength > highest_sentiment_strength :
                    highest_sentiment_strength = current_strength
                    strongest_sentiment_currency_or_pair = item
                    strongest_sentiment_direction = current_direction
                    directive["primary_bias"] = {"pair": item, "direction": current_direction if current_direction != "ranging" else "ranging_on_pair"}
            elif current_strength > highest_sentiment_strength and not isinstance(directive["primary_bias"].get("pair"), str) :
                highest_sentiment_strength = current_strength
                strongest_sentiment_currency_or_pair = item
                strongest_sentiment_direction = current_direction
                directive["primary_bias"] = {"currency": item, "direction": current_direction}

        if highest_sentiment_strength == 3: directive["confidence_in_bias"] = "high"
        elif highest_sentiment_strength == 2: directive["confidence_in_bias"] = "medium"
        else:
            directive["confidence_in_bias"] = "low"
            if not strongest_sentiment_currency_or_pair :
                 directive["primary_bias"] = {"market_condition": "neutral_or_mixed_signals"}

        if outlook_volatility: directive["volatility_expectation"] = outlook_volatility.lower()
        if market_outlook.get("key_levels"):
            directive["key_levels_to_watch"] = market_outlook["key_levels"]

        risk_appetite = user_preferences.get("risk_appetite", "moderate").lower()
        preferred_pairs_user = user_preferences.get("preferred_pairs", [])
        trading_style_preference = user_preferences.get("trading_style_preference", "swing_trader").lower()

        if risk_appetite == "conservative":
            if directive["confidence_in_bias"] == "high": directive["confidence_in_bias"] = "medium"
            if directive["volatility_expectation"] == "high": directive["volatility_expectation"] = "moderate"
            elif directive["volatility_expectation"] == "moderate": directive["volatility_expectation"] = "low"

        style_to_timeframes = {
            "scalper": ["scalping", "m1", "m5"], "day_trader": ["intraday", "m5", "m15", "h1"],
            "swing_trader": ["short_term", "medium_term", "h4", "d1"],
            "position_trader": ["long_term", "d1", "w1"]
        }
        directive["preferred_timeframes"] = style_to_timeframes.get(trading_style_preference, ["medium_term", "h1", "h4"])
        user_style_narrative = f"User prefers {trading_style_preference if trading_style_preference else 'default medium-term focus'}."

        valid_preferred_pairs = [p for p in preferred_pairs_user if isinstance(p, str) and "/" in p]
        if valid_preferred_pairs: directive["focus_pairs"] = valid_preferred_pairs
        elif strongest_sentiment_currency_or_pair and "/" in strongest_sentiment_currency_or_pair:
            directive["focus_pairs"] = [strongest_sentiment_currency_or_pair]
        elif strongest_sentiment_currency_or_pair:
            if strongest_sentiment_currency_or_pair == "USD" and strongest_sentiment_direction == "bullish": directive["focus_pairs"] = ["EUR/USD", "GBP/USD", "USD/JPY"]
            elif strongest_sentiment_currency_or_pair == "USD" and strongest_sentiment_direction == "bearish": directive["focus_pairs"] = ["EUR/USD", "GBP/USD", "USD/JPY"]
            elif strongest_sentiment_currency_or_pair == "EUR" and strongest_sentiment_direction == "bullish": directive["focus_pairs"] = ["EUR/USD", "EUR/JPY", "EUR/GBP"]
            elif strongest_sentiment_currency_or_pair == "EUR" and strongest_sentiment_direction == "bearish": directive["focus_pairs"] = ["EUR/USD", "EUR/JPY", "EUR/GBP"]
            else: directive["focus_pairs"] = ["EUR/USD", "USD/JPY"]
        else: directive["focus_pairs"] = ["EUR/USD", "USD/JPY"]

        bias_info = directive["primary_bias"]
        bias_desc = ""
        if "pair" in bias_info: bias_desc = f"{bias_info['direction']} on {bias_info['pair']}"
        elif "currency" in bias_info: bias_desc = f"{bias_info['direction']} on {bias_info['currency']}"
        else: bias_desc = bias_info.get("market_condition", "mixed")

        narrative = f"Rule-based Directive: Bias {bias_desc} ({directive['confidence_in_bias']}). Focus: {', '.join(directive['focus_pairs'])} ({', '.join(directive['preferred_timeframes'])}). Vol: {directive['volatility_expectation']}. {market_summary} {user_style_narrative}"
        directive["key_narrative"] = narrative
        return directive

    def get_strategic_directive(self, market_outlook: Dict[str, Any], user_preferences: Dict[str, Any]) -> Dict[str, Any]:
        print(f"ForexMasterAgent received market_outlook (keys: {list(market_outlook.keys()) if market_outlook else 'None'}), user_preferences (keys: {list(user_preferences.keys()) if user_preferences else 'None'})")

        if self.llm_client is None or not LANGCHAIN_AVAILABLE: # Check LANGCHAIN_AVAILABLE as well
            print("ForexMasterAgent: LLM client not available or Langchain components missing. Falling back to rule-based logic.")
            return self._get_rule_based_directive(market_outlook, user_preferences)

        system_message = (
            "You are an expert Forex Chief Strategist for a multi-agent trading system. "
            "Your role is to analyze the provided market outlook and user preferences to formulate a clear, actionable 'Strategic Forex Directive'. "
            "The directive guides specialized trading agents (Scalper, Day Trader, Swing Trader, Position Trader). "
            "You must return your directive as a JSON object with the following fields: "
            "1. 'primary_bias': A dictionary indicating the main directional view. Examples: "
            "   - {'currency': 'USD', 'direction': 'bullish'} "
            "   - {'pair': 'EUR/JPY', 'direction': 'bearish'} "
            "   - {'market_condition': 'ranging', 'pairs': ['AUD/CAD', 'NZD/USD']} (list specific pairs if ranging) "
            "   - {'market_condition': 'neutral_or_mixed_signals'} (if no clear bias) "
            "2. 'confidence_in_bias': Your confidence in this bias ('low', 'medium', 'high'). "
            "3. 'preferred_timeframes': A list of strings indicating suitable timeframes for action based on outlook and user style (e.g., ['intraday', 'm15', 'h1'] or ['long_term', 'd1', 'w1']). Valid general terms: 'scalping', 'intraday', 'short_term', 'medium_term', 'long_term'. Also include specific chart timeframes like 'm1', 'm5', 'm15', 'm30', 'h1', 'h4', 'd1', 'w1', 'mn1'. "
            "4. 'volatility_expectation': Expected market volatility ('low', 'moderate', 'high', 'high_impact_news_expected'). "
            "5. 'focus_pairs': A list of 1-3 currency pairs that agents should primarily focus on, derived from the outlook and user preferences. "
            "6. 'key_narrative': A concise (2-3 sentences) textual summary explaining your reasoning for the directive, integrating the market outlook and user preferences. "
            "7. 'key_levels_to_watch': An OPTIONAL dictionary of important support/resistance levels for key pairs if clearly identifiable and critical (e.g., {'EUR/USD_support': 1.0700, 'USD/JPY_resistance': 150.00})."
            "Ensure the JSON output is complete and correctly formatted."
        )

        human_template = (
            "Market Outlook:\n{market_outlook_str}\n\n"
            "User Preferences:\n{user_preferences_str}\n\n"
            "Based on the above, provide the Strategic Forex Directive as a JSON object."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("human", human_template)
        ])

        parser = JsonOutputParser()
        chain = prompt | self.llm_client | parser

        try:
            print("ForexMasterAgent: Invoking LLM for strategic directive...")
            market_outlook_str = json.dumps(market_outlook, indent=2)
            user_preferences_str = json.dumps(user_preferences, indent=2)

            llm_response = chain.invoke({
                "market_outlook_str": market_outlook_str,
                "user_preferences_str": user_preferences_str
            })

            required_keys = ["primary_bias", "confidence_in_bias", "preferred_timeframes", "volatility_expectation", "focus_pairs", "key_narrative"]
            if not all(key in llm_response for key in required_keys):
                print(f"ForexMasterAgent WARNING: LLM response missing one or more required keys. Response: {llm_response}")
                raise ValueError("LLM response structure incorrect.")

            llm_response["llm_generated"] = True
            print(f"ForexMasterAgent: LLM generated strategic_directive: {llm_response}")
            return llm_response

        except Exception as e:
            print(f"ForexMasterAgent WARNING: LLM call or parsing failed: {e}. Falling back to rule-based logic.")
            return self._get_rule_based_directive(market_outlook, user_preferences)
