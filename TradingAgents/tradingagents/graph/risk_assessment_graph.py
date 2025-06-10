from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

# Corrected import paths based on actual creator functions
from tradingagents.agents.risk_mgmt.aggresive_debator import create_risky_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_safe_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.managers.risk_manager import create_risk_manager

class RiskGraphState(TypedDict):
    current_trade_proposal: Dict[str, Any]
    strategic_directive: Optional[Dict[str, Any]]
    portfolio_context: Optional[Dict[str, Any]]

    risky_analysis: Optional[str]
    safe_analysis: Optional[str]
    neutral_analysis: Optional[str]

    llm_generated_risky: bool
    llm_generated_safe: bool
    llm_generated_neutral: bool

    risk_manager_judgment: Optional[Dict[str, Any]]
    error_message: Optional[str]

class RiskAssessmentGraph:
    def __init__(self, llm_model_name: str = "gpt-3.5-turbo", memory_manager: Any = None):
        self.llm_model_name = llm_model_name
        self.memory_manager = memory_manager

        self.aggressive_analyst_node = create_risky_debator(llm_model_name=self.llm_model_name)
        self.conservative_analyst_node = create_safe_debator(llm_model_name=self.llm_model_name)
        self.neutral_analyst_node = create_neutral_debator(llm_model_name=self.llm_model_name)
        self.risk_manager_node = create_risk_manager(llm_model_name=self.llm_model_name, memory=self.memory_manager)

        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(RiskGraphState)

        graph.add_node("run_aggressive_analyst", self.aggressive_analyst_node)
        graph.add_node("run_conservative_analyst", self.conservative_analyst_node)
        graph.add_node("run_neutral_analyst", self.neutral_analyst_node)
        graph.add_node("run_risk_manager_judge", self.risk_manager_node)

        graph.set_entry_point("run_aggressive_analyst")
        graph.add_edge("run_aggressive_analyst", "run_conservative_analyst")
        graph.add_edge("run_conservative_analyst", "run_neutral_analyst")
        graph.add_edge("run_neutral_analyst", "run_risk_manager_judge")
        graph.add_edge("run_risk_manager_judge", END)

        return graph.compile()

    def run(self, input_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        initial_graph_state = RiskGraphState(
            current_trade_proposal=input_state.get("current_trade_proposal"),
            strategic_directive=input_state.get("strategic_directive"),
            portfolio_context=input_state.get("portfolio_context"),
            risky_analysis=None,
            safe_analysis=None, # Corrected initialization key
            neutral_analysis=None, # Corrected initialization key
            llm_generated_risky=False,
            llm_generated_safe=False,
            llm_generated_neutral=False,
            risk_manager_judgment=None,
            error_message=None
        )
        final_state = self.workflow.invoke(initial_graph_state)
        return final_state.get("risk_manager_judgment")

if __name__ == "__main__":
    # Placeholder for memory if the actual one is complex or not needed for this test
    class PlaceholderTestMemory:
        def get_memories(self, query: str, n_matches: int = 2) -> List[Dict[str, Any]]:
            print(f"RiskAssessmentGraph Test: PlaceholderMemory.get_memories called for query: {query}")
            return [{"recommendation": "Test memory: Always double check risk scores."}]

    mock_memory_for_risk_manager = PlaceholderTestMemory()

    risk_graph_instance = RiskAssessmentGraph(
        llm_model_name="gpt-3.5-turbo-mock",
        memory_manager=mock_memory_for_risk_manager
    )

    sample_trade_proposal = {
        "pair": "EUR/USD", "type": "market", "side": "buy",
        "entry_price": 1.0850, "stop_loss": 1.0800, "take_profit": 1.0950,
        "confidence_score": 0.75, "origin_agent": "DayTraderAgent_Test",
        "rationale": "Test proposal for risk assessment: Bullish EMA crossover.",
        "indicators": {"RSI_14": 55}
    }
    sample_directive = {
        "primary_bias": {"currency": "USD", "direction": "bearish"},
        "volatility_expectation": "moderate",
        "key_narrative": "Test directive: USD bearish, moderate volatility."
    }
    sample_portfolio = {"balance": 10000, "open_positions": []}

    input_for_risk_graph = {
        "current_trade_proposal": sample_trade_proposal,
        "strategic_directive": sample_directive,
        "portfolio_context": sample_portfolio
    }

    print("--- Running Risk Assessment Sub-Graph Test ---")
    assessment_output = risk_graph_instance.run(input_for_risk_graph)

    print("\n--- Risk Assessment Sub-Graph Output ---")
    if assessment_output:
        llm_status_manager = assessment_output.get("llm_generated_judgment", False)
        print(f"  LLM Generated (Manager Judgment): {llm_status_manager}")
        for key, value in assessment_output.items():
            if key != "llm_generated_judgment":
                if isinstance(value, dict):
                    print(f"  {key}:")
                    for sub_k, sub_v in value.items():
                        print(f"    {sub_k}: {sub_v}")
                else:
                    print(f"  {key}: {value}")
    else:
        print("  No assessment output received or error occurred.")

    # To see the full state including intermediate analyses and their llm_generated flags:
    # print("\n--- Full Final State of Risk Graph (for debugging debater LLM flags) ---")
    # initial_graph_state_for_full_run = RiskGraphState(
    #         current_trade_proposal=input_for_risk_graph.get("current_trade_proposal"),
    #         strategic_directive=input_for_risk_graph.get("strategic_directive"),
    #         portfolio_context=input_for_risk_graph.get("portfolio_context"),
    #         risky_analysis=None, safe_analysis=None, neutral_analysis=None,
    #         llm_generated_risky=False, llm_generated_safe=False, llm_generated_neutral=False,
    #         risk_manager_judgment=None, error_message=None
    # )
    # full_final_state = risk_graph_instance.workflow.invoke(initial_graph_state_for_full_run)
    # for key, value in full_final_state.items():
    #     if value is not None:
    #          print(f"  {key}: {value}")
