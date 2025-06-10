import os
import json # Added
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser # For structured output
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("RiskManager WARNING: LangChain packages not found. Will use mock logic.")
    LANGCHAIN_AVAILABLE = False
    class ChatOpenAI:
        def __init__(self, model_name: str, temperature: float): pass
    class ChatPromptTemplate:
        @staticmethod
        def from_messages(messages):
            class MockPromptTemplate:
                def pipe(self, next_component): return next_component
                def __or__(self, next_component): return next_component
                def invoke(self, inputs): return str(inputs)
            return MockPromptTemplate()
    class JsonOutputParser:  # Changed from StrOutputParser
        def __init__(self, pydantic_object=None): pass # pydantic_object for PydanticOutputParser
        def invoke(self, inputs): # Simulate parsing JSON string
            try:
                return json.loads(inputs) if isinstance(inputs, str) else inputs
            except json.JSONDecodeError:
                print("RiskManager Mock JsonOutputParser: Failed to decode JSON string.")
                # Fallback to a default structure if parsing fails during mock
                return {
                    "risk_score": 0.5, "assessment_summary": "Mock fallback due to JSON parse error.",
                    "recommended_modifications": {}, "proceed_with_trade": False
                }


def create_risk_manager(llm_model_name: str = "gpt-3.5-turbo", memory: Any = None):
    llm_client = None
    # RiskManager now also uses memory, so it's passed to its constructor if available
    # For now, memory is a placeholder, but actual FinancialSituationMemory would be passed.

    if LANGCHAIN_AVAILABLE and os.getenv("OPENAI_API_KEY") and "gpt" in llm_model_name.lower():
        try:
            llm_client = ChatOpenAI(model_name=llm_model_name, temperature=0.3) # Lower temp for more deterministic judgment
            print(f"RiskManager initialized with LLM: {llm_model_name}")
        except Exception as e:
            print(f"RiskManager WARNING: Failed to initialize ChatOpenAI for {llm_model_name}. Error: {e}. Using mock logic.")
            llm_client = None
    elif LANGCHAIN_AVAILABLE and ("gpt" in llm_model_name.lower() and not os.getenv("OPENAI_API_KEY")):
        print(f"RiskManager WARNING: OPENAI_API_KEY not set for OpenAI model {llm_model_name}. Using mock logic.")
    elif not LANGCHAIN_AVAILABLE and "gpt" in llm_model_name.lower():
        pass
    else:
        print(f"RiskManager: Not using OpenAI model {llm_model_name}. Mock logic will be used if no other client provided.")

    # The actual RiskManager logic with LLM or fallback
    risk_manager_instance = RiskManagerLogic(llm_client=llm_client, memory=memory)

    def _run_risk_manager_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("--- Running Risk Manager (Judge) ---")
        # Use the corrected keys as per RiskGraphState and debater outputs
        risky_analysis = state.get("risky_analysis", "No aggressive analysis provided.")
        neutral_analysis = state.get("neutral_analysis", "No neutral analysis provided.")
        safe_analysis = state.get("safe_analysis", "No conservative analysis provided.")
        original_trade_proposal = state.get("current_trade_proposal") # This is the key from RiskGraphState

        if not original_trade_proposal:
            print("RiskManager: No trade proposal found in state for judgment.")
            return {"risk_manager_judgment": {"error": "No trade proposal provided for judgment.", "llm_generated_judgment": False}}

        judgment = risk_manager_instance.judge_trade_risk(
            risky_analysis=risky_analysis,
            neutral_analysis=neutral_analysis,
            safe_analysis=safe_analysis,
            original_trade_proposal=original_trade_proposal,
            llm_generated_flags={ # Pass the generation flags for context
                "risky": state.get("llm_generated_risky", False),
                "neutral": state.get("llm_generated_neutral", False),
                "safe": state.get("llm_generated_safe", False)
            }
        )

        return {"risk_manager_judgment": judgment}

    return _run_risk_manager_node


class RiskManagerLogic: # Encapsulating the logic in a class
    def __init__(self, llm_client: Optional[ChatOpenAI], memory: Any):
        self.llm_client = llm_client
        self.memory = memory # For future use with get_memories

    def _get_rule_based_judgment(self, risky_analysis: str, neutral_analysis: str, safe_analysis: str, original_trade_proposal: Dict[str, Any]) -> Dict[str, Any]:
        print(f"RiskManager (Rule-Based Fallback) for {original_trade_proposal.get('pair')}")
        risk_score = 0.3
        if "conservative" in safe_analysis.lower() and "tight" in safe_analysis.lower(): risk_score = max(risk_score, 0.6)
        if "high reward potential" in risky_analysis.lower() and "acceptable risk" in risky_analysis.lower(): risk_score = min(risk_score, 0.4)
        if "borderline" in neutral_analysis.lower() or "mixed" in neutral_analysis.lower(): risk_score = (risk_score + 0.5) / 2

        original_confidence = original_trade_proposal.get("confidence_score", 0.5)
        if original_confidence < 0.6: risk_score = min(1.0, risk_score + 0.1)

        proceed = risk_score <= 0.65
        size_factor = 1.0
        if risk_score > 0.6: size_factor = 0.5
        elif risk_score > 0.4: size_factor = 0.8

        assessment_summary = (
            f"Rule-based synthesized risk for {original_trade_proposal.get('pair')} {original_trade_proposal.get('side')}: "
            f"Overall risk score is {risk_score:.2f}. Proceed: {proceed}."
        )
        return {
            "risk_score": round(risk_score, 2),
            "assessment_summary": assessment_summary,
            "recommended_modifications": {"sl": None, "tp": None, "size_factor": size_factor },
            "proceed_with_trade": proceed,
            "llm_generated_judgment": False
        }

    def judge_trade_risk(self, risky_analysis: str, neutral_analysis: str, safe_analysis: str, original_trade_proposal: Dict[str, Any], llm_generated_flags: Dict[str, bool]) -> Dict[str, Any]:
        print(f"RiskManager judging proposal for {original_trade_proposal.get('pair')}")
        # print(f"  Aggressive Analysis: {risky_analysis}") # Can be verbose
        # print(f"  Neutral Analysis: {neutral_analysis}")
        # print(f"  Conservative Analysis: {safe_analysis}")

        if self.llm_client is None or not LANGCHAIN_AVAILABLE:
            print("RiskManager: LLM client not available. Falling back to rule-based judgment.")
            return self._get_rule_based_judgment(risky_analysis, neutral_analysis, safe_analysis, original_trade_proposal)

        system_message = (
            "You are a Risk Manager Judge in a Forex trading system. Your role is to synthesize analyses from three risk analysts (Aggressive, Neutral, Conservative) "
            "regarding a specific trade proposal. Based on these analyses and the original proposal, you must make a final judgment. "
            "Return your judgment as a JSON object with these exact keys: "
            "1. 'risk_score': A float between 0.0 (very low risk) and 1.0 (very high risk). "
            "2. 'assessment_summary': A concise (1-2 sentences) textual summary of your overall risk assessment and key reasons. "
            "3. 'recommended_modifications': A dictionary that can contain 'sl' (float, new stop-loss), 'tp' (float, new take-profit), "
            "   or 'size_factor' (float, e.g., 0.5 for half size, 1.0 for original size). Use null if no change. "
            "4. 'proceed_with_trade': A boolean (true if trade is approved from risk perspective, false otherwise)."
        )
        human_template = (
            "Original Trade Proposal:\n{trade_proposal_str}\n\n"
            "Aggressive Risk Analyst's Input (LLM Generated: {was_risky_llm_generated}):\n{risky_analysis_str}\n\n"
            "Neutral Risk Analyst's Input (LLM Generated: {was_neutral_llm_generated}):\n{neutral_analysis_str}\n\n"
            "Conservative Risk Analyst's Input (LLM Generated: {was_safe_llm_generated}):\n{safe_analysis_str}\n\n"
            # "Relevant Past Memories/Lessons (if any from self.memory):\n{past_memories_str}\n\n" # For future memory integration
            "Based on all inputs, provide your final risk judgment as a JSON object."
        )
        prompt = ChatPromptTemplate.from_messages([("system", system_message), ("human", human_template)])
        parser = JsonOutputParser() # Expecting a JSON dict from LLM
        chain = prompt | self.llm_client | parser

        try:
            print(f"RiskManager: Invoking LLM for judgment on {original_trade_proposal.get('pair')}...")
            # past_memories = self.memory.get_memories(f"Risk judgment for {original_trade_proposal.get('pair')}", n_matches=1) if self.memory else []
            # past_memories_str = json.dumps(past_memories, default=str) if past_memories else "None"

            llm_response = chain.invoke({
                "trade_proposal_str": json.dumps(original_trade_proposal, default=str),
                "risky_analysis_str": risky_analysis,
                "neutral_analysis_str": neutral_analysis,
                "safe_analysis_str": safe_analysis,
                "was_risky_llm_generated": llm_generated_flags.get('risky', False),
                "was_neutral_llm_generated": llm_generated_flags.get('neutral', False),
                "was_safe_llm_generated": llm_generated_flags.get('safe', False),
                # "past_memories_str": past_memories_str
            })

            # Validate LLM response structure
            required_keys = ["risk_score", "assessment_summary", "recommended_modifications", "proceed_with_trade"]
            if not all(key in llm_response for key in required_keys) or \
               not isinstance(llm_response.get("recommended_modifications"), dict):
                print(f"RiskManager WARNING: LLM response structure incorrect: {llm_response}")
                raise ValueError("LLM response structure for risk judgment incorrect.")

            llm_response["llm_generated_judgment"] = True
            print(f"RiskManager (LLM) generated judgment: {llm_response}")
            return llm_response

        except Exception as e:
            print(f"RiskManager WARNING: LLM call or parsing failed for judgment: {e}. Falling back to rule-based logic.")
            return self._get_rule_based_judgment(risky_analysis, neutral_analysis, safe_analysis, original_trade_proposal)
