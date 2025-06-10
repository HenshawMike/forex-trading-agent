import os
import json
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("AggressiveRiskAnalyst WARNING: LangChain packages not found. Will use mock logic.")
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
    class StrOutputParser:
        def __init__(self): pass
        def invoke(self, inputs): return str(inputs)

def create_risky_debator(llm_model_name: str = "gpt-3.5-turbo", memory: Any = None):
    llm_client = None
    if LANGCHAIN_AVAILABLE and os.getenv("OPENAI_API_KEY") and "gpt" in llm_model_name.lower() :
        try:
            llm_client = ChatOpenAI(model_name=llm_model_name, temperature=0.5)
            print(f"AggressiveRiskAnalyst initialized with LLM: {llm_model_name}")
        except Exception as e:
            print(f"AggressiveRiskAnalyst WARNING: Failed to initialize ChatOpenAI for {llm_model_name}. Error: {e}. Using mock logic.")
            llm_client = None
    elif LANGCHAIN_AVAILABLE and ("gpt" in llm_model_name.lower() and not os.getenv("OPENAI_API_KEY")):
        print(f"AggressiveRiskAnalyst WARNING: OPENAI_API_KEY not set for OpenAI model {llm_model_name}. Using mock logic.")
    elif not LANGCHAIN_AVAILABLE and "gpt" in llm_model_name.lower():
        pass
    else:
        print(f"AggressiveRiskAnalyst: Not using OpenAI model {llm_model_name}. Mock logic will be used if no other client provided.")

    def _run_aggressive_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("--- Running Aggressive Risk Analyst ---")
        trade_proposal = state.get("current_trade_proposal", {})
        strategic_directive = state.get("strategic_directive", {})
        portfolio_context = state.get("portfolio_context", {})

        llm_generated_risky = False
        pair = trade_proposal.get('pair', 'N/A')
        confidence = trade_proposal.get('confidence_score', 0)
        directive_bias_info = strategic_directive.get('primary_bias', {})
        directive_direction = directive_bias_info.get('direction', 'neutral')
        analysis_output = (
            f"Aggressive take on {pair}: This trade presents a significant reward potential. "
            f"The sub-agent's confidence of {confidence:.2f} is noted. "
            f"While risks exist, the current market {strategic_directive.get('volatility_expectation','conditions')} "
            f"and overall directive bias towards '{directive_direction}' suggest this calculated risk is acceptable for the potential upside. "
            f"Any downside seems limited if quick action is taken. Focus on the growth opportunity."
        )

        if llm_client:
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are an Aggressive Risk Analyst. Evaluate the provided Forex trade proposal. Focus on potential high rewards and upsides. Downplay minor risks if the potential gain is significant. Challenge conservative viewpoints. Provide your concise aggressive analysis:"),
                ("human", "Trade Proposal: {trade_proposal_str}\nStrategic Directive: {directive_str}\nPortfolio Context: {portfolio_str}")
            ])
            parser = StrOutputParser()
            chain = prompt_template | llm_client | parser

            try:
                print(f"AggressiveRiskAnalyst: Invoking LLM for trade on {pair}...")
                analysis_output = chain.invoke({
                    "trade_proposal_str": json.dumps(trade_proposal, default=str),
                    "directive_str": json.dumps(strategic_directive, default=str),
                    "portfolio_str": json.dumps(portfolio_context, default=str)
                })
                llm_generated_risky = True
                print(f"AggressiveRiskAnalyst (LLM): {analysis_output}")
            except Exception as e:
                print(f"AggressiveRiskAnalyst ERROR: LLM call failed: {e}. Using mock output.")
        else:
            print(f"AggressiveRiskAnalyst: Using mock logic for trade on {pair}.")

        return {"risky_analysis": analysis_output, "llm_generated_risky": llm_generated_risky} # Corrected key

    return _run_aggressive_node
