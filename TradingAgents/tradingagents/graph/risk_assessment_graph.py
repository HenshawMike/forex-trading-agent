from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

# Corrected import paths based on actual creator functions
from tradingagents.agents.risk_mgmt.aggresive_debator import create_risky_debator
from tradingagents.agents.risk_mgmt.conservative_debator import create_safe_debator
from tradingagents.agents.risk_mgmt.neutral_debator import create_neutral_debator
from tradingagents.agents.managers.risk_manager import create_risk_manager # Risk Manager is in 'managers'

# Placeholder for LLM and Memory (these would be passed in during graph instantiation)
class PlaceholderLLM:
    def invoke(self, prompt: str) -> str:
        # Provide slightly more distinct mock responses for risk agents
        if "Aggressive take" in prompt or "Risky Risk Analyst" in prompt :
             return "Mock LLM: Aggressive: Looks like a winner, risks are minimal!"
        if "Conservative view" in prompt or "Safe/Conservative Risk Analyst" in prompt:
             return "Mock LLM: Conservative: Too risky, potential for significant loss."
        if "Neutral assessment" in prompt or "Neutral Risk Analyst" in prompt:
             return "Mock LLM: Neutral: Pros and cons are balanced, exercise caution."
        if "Risk Management Judge" in prompt:
             return "Mock LLM: Risk Judge: Synthesizing all views for final risk call."
        return f"LLM invoked for risk: {prompt[:50]}..."

class PlaceholderMemory: # If risk agents use memory (RiskManager does)
    def get_memories(self, query: str, n_matches: int = 2) -> List[Dict[str, Any]]:
        return [{"recommendation": "Past lesson: high volatility requires wider stops."}]


class RiskGraphState(TypedDict):
    # Inputs for the sub-graph
    current_trade_proposal: Dict[str, Any] # Renamed from trade_proposal_input for clarity
    strategic_directive: Optional[Dict[str, Any]]
    portfolio_context: Optional[Dict[str, Any]]

    # Outputs from analyst nodes
    aggressive_analysis_output: Optional[str] # Key used by aggressive_debator.py
    conservative_analysis_output: Optional[str] # Key used by conservative_debator.py
    neutral_analysis_output: Optional[str] # Key used by neutral_debator.py

    # Final output from the sub-graph
    risk_manager_judgment: Optional[Dict[str, Any]] # Key used by risk_manager.py
    error_message: Optional[str]

class RiskAssessmentGraph:
    def __init__(self, llm: Any, memory_manager: Any = None): # memory_manager for RiskManager
        self.llm = llm
        self.memory_manager = memory_manager

        # Create agent runnables (nodes)
        self.aggressive_analyst_node = create_risky_debator(llm=self.llm)
        self.conservative_analyst_node = create_safe_debator(llm=self.llm)
        self.neutral_analyst_node = create_neutral_debator(llm=self.llm)
        # RiskManager's creator expects llm and memory
        self.risk_manager_node = create_risk_manager(llm=self.llm, memory=self.memory_manager if self.memory_manager else PlaceholderMemory())

        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(RiskGraphState)

        # Define nodes - these are the functions returned by the creators
        graph.add_node("run_aggressive_analyst", self.aggressive_analyst_node)
        graph.add_node("run_conservative_analyst", self.conservative_analyst_node)
        graph.add_node("run_neutral_analyst", self.neutral_analyst_node)
        graph.add_node("run_risk_manager_judge", self.risk_manager_node)

        # This sub-graph assumes 'current_trade_proposal', 'strategic_directive',
        # and 'portfolio_context' are already in the state when it's invoked.

        # Run analysts in parallel conceptually.
        # For LangGraph, if nodes don't have direct data dependency in their return for the *next immediate step*,
        # and can operate on the same initial state, they can be branched from a common point.
        # The state updates from each will be merged.
        # A more explicit parallel setup would use graph.add_conditional_edges or a custom collector.
        # For this sketch, a sequential flow ensures each analyst's output is in the state
        # before the next, which is fine if they don't truly need to run in parallel for logic.
        # However, the prompt implies they should run in parallel and then feed the manager.
        # To achieve this simply, we can make them all depend on an entry point and then all feed the manager.
        # Let's refine this to a more parallel-like structure feeding the judge.

        graph.set_entry_point("run_aggressive_analyst") # Start with one, others can be parallel if no direct data dep

        # Edges to run analysts - assuming they can run based on initial state.
        # If they were truly parallel and independent before judge:
        # graph.add_edge(START, "run_aggressive_analyst")
        # graph.add_edge(START, "run_conservative_analyst")
        # graph.add_edge(START, "run_neutral_analyst")
        # Then all these edges would go to "run_risk_manager_judge".
        # LangGraph handles merging of state updates from parallel branches.
        # For simplicity and to ensure sequential update of state keys for now:
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
            aggressive_analysis_output=None, # Corrected key based on agent
            conservative_analysis_output=None, # Corrected key
            neutral_analysis_output=None, # Corrected key
            risk_manager_judgment=None, # Corrected key
            error_message=None
        )
        final_state = self.workflow.invoke(initial_graph_state)
        return final_state.get("risk_manager_judgment")

if __name__ == "__main__":
    mock_llm_for_risk = PlaceholderLLM()
    mock_memory_for_risk_manager = PlaceholderMemory()

    risk_graph_instance = RiskAssessmentGraph(llm=mock_llm_for_risk, memory_manager=mock_memory_for_risk_manager)

    sample_trade_proposal = {
        "pair": "EUR/USD", "type": "market", "side": "buy",
        "entry_price": 1.0850, "stop_loss": 1.0800, "take_profit": 1.0950,
        "confidence_score": 0.75, "origin_agent": "DayTraderAgent_Test",
        "rationale": "Test proposal for risk assessment: Bullish EMA crossover.",
        "indicators": {"RSI_14": 55} # Example indicator that Neutral might use
    }
    sample_directive = {
        "primary_bias": {"currency": "USD", "direction": "bearish"}, # EUR/USD bullish
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
    print("\n--- Risk Assessment Sub-Graph Output (Risk Manager Judgment) ---")
    if assessment_output:
        for key, value in assessment_output.items():
            print(f"  {key}: {value}")
    else:
        print("  No assessment output received or error occurred.")

    # To see the full state including intermediate analyses:
    # full_final_state = risk_graph_instance.workflow.invoke(input_for_risk_graph)
    # print("\n--- Full Final State of Risk Graph ---")
    # for key, value in full_final_state.items():
    #     if value is not None:
    #          print(f"  {key}: {value}")
