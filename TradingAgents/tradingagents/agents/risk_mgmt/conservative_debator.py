import os
import json
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("ConservativeRiskAnalyst WARNING: LangChain packages not found. Will use mock logic.")
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

def create_safe_debator(llm_model_name: str = "gpt-3.5-turbo", memory: Any = None):
    llm_client = None
    if LANGCHAIN_AVAILABLE and os.getenv("OPENAI_API_KEY") and "gpt" in llm_model_name.lower():
        try:
            llm_client = ChatOpenAI(model_name=llm_model_name, temperature=0.5)
            print(f"ConservativeRiskAnalyst initialized with LLM: {llm_model_name}")
        except Exception as e:
            print(f"ConservativeRiskAnalyst WARNING: Failed to initialize ChatOpenAI for {llm_model_name}. Error: {e}. Using mock logic.")
            llm_client = None
    elif LANGCHAIN_AVAILABLE and ("gpt" in llm_model_name.lower() and not os.getenv("OPENAI_API_KEY")):
        print(f"ConservativeRiskAnalyst WARNING: OPENAI_API_KEY not set for OpenAI model {llm_model_name}. Using mock logic.")
    elif not LANGCHAIN_AVAILABLE and "gpt" in llm_model_name.lower():
        pass
    else:
        print(f"ConservativeRiskAnalyst: Not using OpenAI model {llm_model_name}. Mock logic will be used if no other client provided.")

    def _run_conservative_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("--- Running Conservative Risk Analyst ---")
        trade_proposal = state.get("current_trade_proposal", {})
        strategic_directive = state.get("strategic_directive", {})
        portfolio_context = state.get("portfolio_context", {})

        llm_generated_safe = False
        pair = trade_proposal.get('pair', 'N/A')
        stop_loss = trade_proposal.get('stop_loss', 'N/A')
        volatility_expectation = strategic_directive.get('volatility_expectation', 'unknown')
        confidence = trade_proposal.get('confidence_score', 0)
        analysis_output = (
            f"Conservative view on {pair}: The proposed stop-loss at {stop_loss} might be too tight, "
            f"especially given the market's expected volatility of '{volatility_expectation}'. "
            f"Confidence score of {confidence:.2f} is noted, but potential downside exists if key support levels are breached. "
            f"Consider a wider stop or waiting for more confirmation to ensure capital preservation."
        )

        if llm_client:
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are a Conservative Risk Analyst. Evaluate the provided Forex trade proposal. Prioritize capital preservation and identify all potential downsides and reasons the trade might fail. Scrutinize risk/reward."),
                ("human", "Trade Proposal: {trade_proposal_str}\nStrategic Directive: {directive_str}\nPortfolio Context: {portfolio_str}\nProvide your concise conservative analysis:")
            ])
            parser = StrOutputParser()
            chain = prompt_template | llm_client | parser

            try:
                print(f"ConservativeRiskAnalyst: Invoking LLM for trade on {pair}...")
                analysis_output = chain.invoke({
                    "trade_proposal_str": json.dumps(trade_proposal, default=str),
                    "directive_str": json.dumps(strategic_directive, default=str),
                    "portfolio_str": json.dumps(portfolio_context, default=str)
                })
                llm_generated_safe = True
                print(f"ConservativeRiskAnalyst (LLM): {analysis_output}")
            except Exception as e:
                print(f"ConservativeRiskAnalyst ERROR: LLM call failed: {e}. Using mock output.")
        else:
            print(f"ConservativeRiskAnalyst: Using mock logic for trade on {pair}.")

        return {"safe_analysis": analysis_output, "llm_generated_safe": llm_generated_safe} # Corrected key

    return _run_conservative_node
