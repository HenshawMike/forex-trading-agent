from typing import Dict, List, TypedDict, Any, Optional # Corrected import for Optional
import operator # For StateGraph update operations

from langgraph.graph import StateGraph, END

# Import our new agents and states
from tradingagents.forex_master.forex_master_agent import ForexMasterAgent
from tradingagents.forex_agents.day_trader_agent import DayTraderAgent
from tradingagents.forex_agents.swing_trader_agent import SwingTraderAgent
from tradingagents.forex_meta.trade_meta_agent import ForexMetaAgent
from tradingagents.forex_utils.forex_states import (
    ForexSubAgentTask,
    ForexTradeProposal,
    AggregatedForexProposals,
    ForexFinalDecision
)
import datetime # For default timestamp

# Define the State for our Forex graph
class ForexGraphState(TypedDict):
    currency_pair: str
    current_simulated_time: str # ISO format string

    # From Master Agent (Initial Processing)
    sub_agent_tasks: List[ForexSubAgentTask]
    market_regime: str

    # For collecting proposals from sub-agents
    # We'll have specific keys for each agent's proposal for simplicity in this skeleton
    day_trader_proposal: Optional[ForexTradeProposal]
    swing_trader_proposal: Optional[ForexTradeProposal]
    # This list will be populated by the master_aggregation_node based on above
    proposals_from_sub_agents: List[ForexTradeProposal]

    # From Master Agent (Aggregation)
    aggregated_proposals_for_meta_agent: Optional[AggregatedForexProposals]

    # From Meta Agent
    forex_final_decision: Optional[ForexFinalDecision]

    # To track errors or issues if any node fails
    error_message: Optional[str]


class ForexTradingGraph:
    def __init__(self):
        print("Initializing ForexTradingGraph...")
        self.master_agent = ForexMasterAgent()
        self.day_trader_agent = DayTraderAgent()
        self.swing_trader_agent = SwingTraderAgent()
        self.meta_agent = ForexMetaAgent()

        self.graph = self._setup_graph()
        print("ForexTradingGraph: Graph setup complete.")

    def _setup_graph(self) -> StateGraph:
        # Define the state merger/updater logic if needed, default is dict.update
        # For lists like proposals_from_sub_agents, if nodes return partial lists,
        # a custom merger might be needed. But here, master_aggregation_node creates the full list.

        # graph_state_merger = operator.add # Example, not suitable for TypedDict state generally
        # For TypedDict, the default update mechanism (merging dictionaries) is usually fine
        # if nodes return dicts with keys corresponding to ForexGraphState fields.

        builder = StateGraph(ForexGraphState)

        # Add Nodes
        builder.add_node("master_initial_processing", self.master_agent.initial_processing_node)
        builder.add_node("day_trader_processing", self._run_day_trader)
        builder.add_node("swing_trader_processing", self._run_swing_trader)
        builder.add_node("master_aggregation", self._run_master_aggregation) # Changed to wrapper
        builder.add_node("meta_agent_evaluation", self.meta_agent.evaluate_proposals)

        # Define Edges
        builder.set_entry_point("master_initial_processing")

        # After master_initial_processing, it prepares tasks.
        # For this skeleton, we'll run Day Trader then Swing Trader sequentially.
        # A more advanced graph would use conditional edges based on tasks in state["sub_agent_tasks"].
        builder.add_edge("master_initial_processing", "day_trader_processing")
        builder.add_edge("day_trader_processing", "swing_trader_processing")

        # After all relevant sub-agents have run, go to master_aggregation
        builder.add_edge("swing_trader_processing", "master_aggregation")

        builder.add_edge("master_aggregation", "meta_agent_evaluation")

        # The meta_agent_evaluation is the final step in this simple flow
        builder.add_edge("meta_agent_evaluation", END)

        return builder.compile()

    def _run_day_trader(self, state: ForexGraphState) -> Dict[str, Any]:
        print("ForexTradingGraph: Running Day Trader...")
        # Find the DayTrader task from sub_agent_tasks
        day_task = None
        for task in state.get("sub_agent_tasks", []):
            # This matching is simplistic; real tasks might have agent_type field
            if "task_day_" in task.get("task_id", ""):
                day_task = task
                break

        if day_task:
            # The agent expects its task under a specific key in a new state dict
            # It returns a dict like {"day_trader_proposal": ...}
            # This will be merged into the main graph state by LangGraph
            # Pass along the whole state as agents might need other info like current_simulated_time
            return self.day_trader_agent.process_task({"current_day_trader_task": day_task, **state})
        else:
            print("ForexTradingGraph: No Day Trader task found.")
            # Ensure the key is part of the output so StateGraph can merge it.
            return {"day_trader_proposal": None, "error_message": state.get("error_message")}


    def _run_swing_trader(self, state: ForexGraphState) -> Dict[str, Any]:
        print("ForexTradingGraph: Running Swing Trader...")
        swing_task = None
        for task in state.get("sub_agent_tasks", []):
            if "task_swing_" in task.get("task_id", ""):
                swing_task = task
                break

        if swing_task:
            return self.swing_trader_agent.process_task({"current_swing_trader_task": swing_task, **state})
        else:
            print("ForexTradingGraph: No Swing Trader task found.")
            return {"swing_trader_proposal": None, "error_message": state.get("error_message")}

    def _run_master_aggregation(self, state: ForexGraphState) -> Dict[str, Any]:
        print("ForexTradingGraph: Running Master Aggregation wrapper...")

        current_proposals_list: List[ForexTradeProposal] = []
        day_proposal = state.get('day_trader_proposal')
        if day_proposal:
            current_proposals_list.append(day_proposal)

        swing_proposal = state.get('swing_trader_proposal')
        if swing_proposal:
            current_proposals_list.append(swing_proposal)

        # The master_agent.aggregation_node expects the list of proposals under
        # the 'proposals_from_sub_agents' key in the state dict it receives.
        aggregation_input_state = state.copy() # Start with a copy of the current state
        aggregation_input_state["proposals_from_sub_agents"] = current_proposals_list

        # Now call the actual master agent's aggregation node with the prepared state
        return self.master_agent.aggregation_node(aggregation_input_state)


    def invoke_graph(self, currency_pair: str, simulated_time_iso: str) -> Optional[ForexFinalDecision]:
        print(f"ForexTradingGraph: Invoking graph for {currency_pair} at {simulated_time_iso}")
        initial_state = ForexGraphState(
            currency_pair=currency_pair,
            current_simulated_time=simulated_time_iso,
            sub_agent_tasks=[],
            market_regime="Unknown", # Master will assess
            day_trader_proposal=None,
            swing_trader_proposal=None,
            proposals_from_sub_agents=[], # Initialize as empty list
            aggregated_proposals_for_meta_agent=None,
            forex_final_decision=None,
            error_message=None
        )

        # Ensure all keys are present in the initial state for TypedDict validation by Langgraph
        # Even if Optional, they should be explicitly None if not set.
        # The above initialization handles this correctly for Optional fields.

        final_state_dict = self.graph.invoke(initial_state) # LangGraph returns a dict

        # Convert dict back to TypedDict for type safety, though it's mostly for static analysis
        # final_state: ForexGraphState = final_state_dict
        # No, LangGraph StateGraph already works with TypedDicts if defined.
        # The output of invoke will match the structure of ForexGraphState.

        if final_state_dict.get("error_message"):
            print(f"Graph execution error: {final_state_dict['error_message']}")
            return None # Or raise an exception

        print(f"ForexTradingGraph: Graph invocation complete. Final decision: {final_state_dict.get('forex_final_decision')}")
        return final_state_dict.get("forex_final_decision")

# Example of how this might be run (will be in the test script)
if __name__ == '__main__':
    print("Manual test of ForexTradingGraph setup:")
    forex_graph_instance = ForexTradingGraph()

    # Test invocation
    # In a real scenario, current_simulated_time would come from the backtester or live environment
    dummy_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
    decision = forex_graph_instance.invoke_graph("EURUSD", dummy_time)

    if decision:
        print("\n--- Final Decision from Graph ---")
        # decision is ForexFinalDecision (a TypedDict)
        for key, value in decision.items(): # Iterate through TypedDict items
            print(f"{key}: {value}")
    else:
        print("\n--- No decision or error in graph ---")
