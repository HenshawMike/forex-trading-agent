import os
import json
from typing import Any, Dict, List, Optional

try:
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser
    LANGCHAIN_AVAILABLE = True
except ImportError:
    print("NeutralRiskAnalyst WARNING: LangChain packages not found. Will use mock logic.")
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

def create_neutral_debator(llm_model_name: str = "gpt-3.5-turbo", memory: Any = None):
    llm_client = None
    if LANGCHAIN_AVAILABLE and os.getenv("OPENAI_API_KEY") and "gpt" in llm_model_name.lower():
        try:
            llm_client = ChatOpenAI(model_name=llm_model_name, temperature=0.5)
            print(f"NeutralRiskAnalyst initialized with LLM: {llm_model_name}")
        except Exception as e:
            print(f"NeutralRiskAnalyst WARNING: Failed to initialize ChatOpenAI for {llm_model_name}. Error: {e}. Using mock logic.")
            llm_client = None
    elif LANGCHAIN_AVAILABLE and ("gpt" in llm_model_name.lower() and not os.getenv("OPENAI_API_KEY")):
        print(f"NeutralRiskAnalyst WARNING: OPENAI_API_KEY not set for OpenAI model {llm_model_name}. Using mock logic.")
    elif not LANGCHAIN_AVAILABLE and "gpt" in llm_model_name.lower():
        pass
    else:
        print(f"NeutralRiskAnalyst: Not using OpenAI model {llm_model_name}. Mock logic will be used if no other client provided.")

    def _run_neutral_node(state: Dict[str, Any]) -> Dict[str, Any]:
        print("--- Running Neutral Risk Analyst ---")
        trade_proposal = state.get("current_trade_proposal", {})
        strategic_directive = state.get("strategic_directive", {})
        portfolio_context = state.get("portfolio_context", {})

        llm_generated_neutral = False
        pair = trade_proposal.get('pair', 'N/A')
        mock_rsi = trade_proposal.get('indicators', {}).get('RSI_14', 'N/A')
        confidence = trade_proposal.get('confidence_score', 0)
        analysis_output = (
            f"Neutral assessment for {pair}: The proposal shows a confidence of {confidence:.2f}. "
            f"Directive alignment needs to be considered. If mock RSI is available: {mock_rsi}. "
            f"The reward/risk ratio appears balanced based on provided SL/TP. "
            f"Consider overall market conditions and upcoming news from directive ({strategic_directive.get('economic_events', 'none')})."
        )

        if llm_client:
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", "You are a Neutral Risk Analyst. Provide a balanced evaluation of the provided Forex trade proposal. Objectively weigh pros and cons. Consider market conditions, alignment with strategy, and risk/reward."),
                ("human", "Trade Proposal: {trade_proposal_str}\nStrategic Directive: {directive_str}\nPortfolio Context: {portfolio_str}\nProvide your concise neutral analysis:")
            ])
            parser = StrOutputParser()
            chain = prompt_template | llm_client | parser

            try:
                print(f"NeutralRiskAnalyst: Invoking LLM for trade on {pair}...")
                analysis_output = chain.invoke({
                    "trade_proposal_str": json.dumps(trade_proposal, default=str),
                    "directive_str": json.dumps(strategic_directive, default=str),
                    "portfolio_str": json.dumps(portfolio_context, default=str)
                })
                llm_generated_neutral = True
                print(f"NeutralRiskAnalyst (LLM): {analysis_output}")
            except Exception as e:
                print(f"NeutralRiskAnalyst ERROR: LLM call failed: {e}. Using mock output.")
        else:
            print(f"NeutralRiskAnalyst: Using mock logic for trade on {pair}.")

        return {"neutral_analysis": analysis_output, "llm_generated_neutral": llm_generated_neutral} # Corrected key

    return _run_neutral_node
