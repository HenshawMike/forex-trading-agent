from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional

# Assuming these will be imported from your existing structure or similar
# from tradingagents.agents.utils.memory import FinancialSituationMemory # Example
# from langchain_core.language_models.base import BaseLanguageModel # Example

# Import new Forex agent skeletons
from tradingagents.forex_master.forex_master_agent import ForexMasterAgent
from tradingagents.forex_meta.trade_meta_agent import TradeMetaAgent
from tradingagents.forex_agents.day_trader_agent import DayTraderAgent
from tradingagents.forex_agents.swing_trader_agent import SwingTraderAgent
from tradingagents.broker_interface.base import BrokerInterface
# from tradingagents.broker_interface.mt5_broker import MT5Broker # Example concrete broker
from tradingagents.graph.risk_assessment_graph import RiskAssessmentGraph # New import

# Define a placeholder for the LLM and Memory and Broker (these would be initialized and passed in)
# In a real setup, these would be properly initialized instances
class PlaceholderLLM:
    def invoke(self, prompt: str) -> str:
        # Simulate LLM behavior for different agent calls based on prompt content
        if "ForexMasterAgent" in prompt:
            return f"LLM invoked for MasterAgent: {prompt[:50]}... Directive: Bullish EUR/USD"
        elif "DayTraderAgent" in prompt:
            return f"LLM invoked for DayTrader: {prompt[:50]}... Proposal: Buy EUR/USD"
        elif "SwingTraderAgent" in prompt:
            return f"LLM invoked for SwingTrader: {prompt[:50]}... Proposal: Sell GBP/JPY"
        elif "TradeMetaAgent" in prompt: # This LLM is for TradeMetaAgent's own reasoning if any
            return f"LLM invoked for MetaAgent: {prompt[:50]}... Evaluating proposals"
        # Mocks for Risk Assessment Graph LLM calls
        elif "Aggressive take" in prompt or "Risky Risk Analyst" in prompt :
             return "Mock LLM (Risk): Aggressive: Looks like a winner, risks are minimal!"
        elif "Conservative view" in prompt or "Safe/Conservative Risk Analyst" in prompt:
             return "Mock LLM (Risk): Conservative: Too risky, potential for significant loss."
        elif "Neutral assessment" in prompt or "Neutral Risk Analyst" in prompt:
             return "Mock LLM (Risk): Neutral: Pros and cons are balanced, exercise caution."
        elif "Risk Management Judge" in prompt:
             return "Mock LLM (Risk): Risk Judge: Synthesizing all views for final risk call."
        return f"LLM invoked with: {prompt[:50]}..."


class PlaceholderMemory: # Used by Master, Sub-Agents, MetaAgent, and RiskManager
    def retrieve(self, query: str) -> List[str]:
        return [f"Memory retrieved for: {query}"]
    def add_memory(self, text: str, metadata: Optional[Dict] = None) -> None:
        # print(f"Memory: Added '{text[:50]}...' with metadata {metadata}") # Can be verbose
        pass
    def get_memories(self, query: str, n_matches: int = 2) -> List[Dict[str, Any]]: # For RiskManager
        return [{"recommendation": "Past lesson from PlaceholderMemory: be cautious with high volatility."}]


# Define the state for the Forex trading graph
class ForexGraphState(TypedDict):
    market_outlook: Optional[Dict[str, Any]]
    user_preferences: Optional[Dict[str, Any]]
    strategic_directive: Optional[Dict[str, Any]]
    day_trader_proposals: Optional[List[Dict[str, Any]]]
    swing_trader_proposals: Optional[List[Dict[str, Any]]]
    aggregated_proposals: List[Dict[str, Any]]
    finalized_trades_for_approval: Optional[List[Dict[str, Any]]]
    portfolio_status: Optional[Dict[str, Any]]
    error_message: Optional[str]


class ForexTradingGraph:
    def __init__(self, llm: Any, broker_interface: BrokerInterface):
        self.llm = llm
        self.broker_interface = broker_interface

        # General memory instance if shared, or specific ones per agent
        shared_memory = PlaceholderMemory()

        self.forex_master_agent = ForexMasterAgent(llm=self.llm, memory=shared_memory)
        self.day_trader_agent = DayTraderAgent(agent_id="day_trader_main", llm=self.llm, memory=shared_memory, broker_interface=self.broker_interface)
        self.swing_trader_agent = SwingTraderAgent(agent_id="swing_trader_main", llm=self.llm, memory=shared_memory, broker_interface=self.broker_interface)

        # Instantiate the RiskAssessmentGraph and get its compiled workflow
        # Risk agents might use a different LLM or memory, passed here. For now, using the same.
        self.risk_assessment_graph_instance = RiskAssessmentGraph(llm=self.llm, memory_manager=shared_memory)

        self.trade_meta_agent = TradeMetaAgent(
            llm=self.llm,
            memory=shared_memory,
            risk_assessment_workflow=self.risk_assessment_graph_instance # Pass the graph instance, .run will be called on it
        )

        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(ForexGraphState)

        graph.add_node("run_forex_master_agent", self.run_forex_master_agent)
        graph.add_node("run_day_trader_agent", self.run_day_trader_agent)
        graph.add_node("run_swing_trader_agent", self.run_swing_trader_agent)
        graph.add_node("aggregate_trading_proposals", self.aggregate_trading_proposals)
        graph.add_node("run_trade_meta_agent", self.run_trade_meta_agent)

        graph.set_entry_point("run_forex_master_agent")
        graph.add_edge("run_forex_master_agent", "run_day_trader_agent")
        graph.add_edge("run_forex_master_agent", "run_swing_trader_agent")
        graph.add_edge("run_day_trader_agent", "aggregate_trading_proposals")
        graph.add_edge("run_swing_trader_agent", "aggregate_trading_proposals")
        graph.add_edge("aggregate_trading_proposals", "run_trade_meta_agent")
        graph.add_edge("run_trade_meta_agent", END)

        return graph.compile()

    def run_forex_master_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Forex Master Agent ---")
        market_outlook = state.get("market_outlook", {"summary": "Default neutral market outlook."})
        user_preferences = state.get("user_preferences", {"risk_appetite": "moderate"})
        directive = self.forex_master_agent.get_strategic_directive(market_outlook, user_preferences)
        return {"strategic_directive": directive}

    def run_day_trader_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Day Trader Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive:
            return {"error_message": "DayTrader: Missing strategic directive."}
        proposals = self.day_trader_agent.analyze_and_propose_trades(strategic_directive)
        return {"day_trader_proposals": proposals}

    def run_swing_trader_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Swing Trader Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive:
            return {"error_message": "SwingTrader: Missing strategic directive."}
        proposals = self.swing_trader_agent.analyze_and_propose_trades(strategic_directive)
        return {"swing_trader_proposals": proposals}

    def aggregate_trading_proposals(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Aggregating Trading Proposals ---")
        all_proposals = []
        day_proposals = state.get("day_trader_proposals")
        if day_proposals is not None:
             all_proposals.extend(day_proposals)
        swing_proposals = state.get("swing_trader_proposals")
        if swing_proposals is not None:
            all_proposals.extend(swing_proposals)
        print(f"Total proposals aggregated: {len(all_proposals)}")
        return {"aggregated_proposals": all_proposals}

    def run_trade_meta_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Trade Meta Agent ---")
        proposals = state.get("aggregated_proposals", [])
        strategic_directive = state.get("strategic_directive")
        portfolio_status = state.get("portfolio_status", {"balance": 10000, "open_positions": 0, "max_concurrent_trades": 1, "risk_per_trade_percentage": 0.01})
        if not strategic_directive:
            return {"error_message": "TradeMetaAgent: Missing strategic directive."}
        final_trades = self.trade_meta_agent.coordinate_trades(proposals, strategic_directive, portfolio_status)
        return {"finalized_trades_for_approval": final_trades}

    def run(self, initial_state_dict: Dict[str, Any]) -> Dict[str, Any]:
        print("--- Running Forex Trading Graph ---")
        graph_input = ForexGraphState(
            market_outlook=initial_state_dict.get("market_outlook"),
            user_preferences=initial_state_dict.get("user_preferences"),
            strategic_directive=None,
            day_trader_proposals=initial_state_dict.get("day_trader_proposals"),
            swing_trader_proposals=initial_state_dict.get("swing_trader_proposals"),
            aggregated_proposals=initial_state_dict.get("aggregated_proposals", []),
            finalized_trades_for_approval=None,
            portfolio_status=initial_state_dict.get("portfolio_status"),
            error_message=None
        )

        final_state = self.workflow.invoke(graph_input)
        print("--- Forex Trading Graph Run Complete ---")
        return final_state


if __name__ == "__main__":
    from datetime import datetime, timezone

    mock_llm = PlaceholderLLM() # This will be used by ForexTradingGraph and passed to RiskAssessmentGraph

    class MockBroker(BrokerInterface):
        def connect(self, credentials): return True
        def disconnect(self): pass
        def get_account_info(self): return {"balance": 10000, "currency": "USD", "equity": 10000, "margin": 5000}
        def get_current_price(self, pair): return {"bid": 1.1, "ask": 1.1002, "time": datetime.now(timezone.utc)}
        def get_historical_data(self, pair, timeframe, start_date=None, end_date=None, count=None):
            # print(f"MockBroker: Getting historical data for {pair} ({timeframe})")
            return [{"time": datetime.now(timezone.utc), "open": 1.0, "high": 1.1, "low": 0.9, "close": 1.05, "volume": 100}]
        def place_order(self, order_details): return {"success": True, "order_id": "sim123", "message": "Simulated order placed."}
        def modify_order(self, order_id, new_params): return {"success": True, "message": "Simulated order modified."}
        def close_order(self, order_id, size_to_close=None): return {"success": True, "message": "Simulated order closed."}
        def get_open_positions(self): return []
        def get_pending_orders(self): return []

    mock_broker = MockBroker()

    # ForexTradingGraph now instantiates RiskAssessmentGraph internally
    forex_graph_instance = ForexTradingGraph(llm=mock_llm, broker_interface=mock_broker)

    initial_run_state = {
        "market_outlook": {
            "summary": "Overall market is cautious. USD showed some strength on recent data.",
            "sentiment": {"USD": "strong_bullish", "EUR": "neutral", "AUD/JPY": "neutral"},
            "volatility_forecast": "moderate",
            "key_levels": {"EUR/USD_resistance": 1.0900, "USD/JPY_support": 148.50},
            "economic_events": ["US CPI next week"]
        },
        "user_preferences": {
            "risk_appetite": "moderate",
            "preferred_pairs": ["EUR/USD", "USD/JPY", "GBP/JPY"],
            "trading_style_preference": "day_trader", # To get DayTrader to propose something
            "disallowed_pairs": ["USD/CAD"]
        },
        "portfolio_status": {
            "balance": 25000,
            "equity": 25000,
            "margin_available": 25000,
            "open_positions": [],
            "max_concurrent_trades": 2,
            "risk_per_trade_percentage": 0.01,
            "mock_current_price": {"EUR/USD": 1.0850, "USD/JPY": 149.50, "GBP/JPY": 189.50}
        }
    }

    final_output_state = forex_graph_instance.run(initial_run_state)

    print("\n--- Final Graph Output (all keys from final state) ---")
    for key, value in final_output_state.items():
        if value is not None and (not isinstance(value, list) or value):
             print(f"{key}: {value}")

    print("\n--- Specific check for Strategic Directive ---")
    strategic_directive_output = final_output_state.get("strategic_directive")
    if strategic_directive_output:
        print("Strategic Directive Output:")
        for k, v in strategic_directive_output.items():
            print(f"  {k}: {v}")
    else:
        print("Strategic Directive not found in final output.")

    print("\n--- Specific check for Day Trader Proposals ---")
    day_trader_proposals = final_output_state.get("day_trader_proposals")
    if day_trader_proposals:
        print(f"Day Trader Proposals ({len(day_trader_proposals)}):")
        for proposal_idx, proposal in enumerate(day_trader_proposals):
            print(f"  Proposal {proposal_idx + 1}:")
            # Risk assessment is now part of the proposal after TradeMetaAgent
            # This print is before TradeMetaAgent modifies it with full risk assessment
            for k, v_prop in proposal.items():
                 print(f"    {k}: {v_prop}")
    elif day_trader_proposals == []:
         print("Day Trader Proposals: [] (No trades proposed)")
    else:
        print("Day Trader Proposals not found or not run in output.")

    print("\n--- Specific check for Swing Trader Proposals ---")
    swing_trader_proposals = final_output_state.get("swing_trader_proposals")
    if swing_trader_proposals:
        print(f"Swing Trader Proposals ({len(swing_trader_proposals)}):")
        for proposal_idx, proposal in enumerate(swing_trader_proposals):
            print(f"  Proposal {proposal_idx + 1}:")
            for k, v_prop in proposal.items():
                 print(f"    {k}: {v_prop}")
    elif swing_trader_proposals == []:
        print("Swing Trader Proposals: [] (No trades proposed)")
    else:
        print("Swing Trader Proposals not found or not run in output.")

    print("\n--- Specific check for Finalized Trades for Approval ---")
    finalized_trades = final_output_state.get("finalized_trades_for_approval")
    if finalized_trades:
        print(f"Finalized Trades for Approval ({len(finalized_trades)}):")
        for trade_idx, trade in enumerate(finalized_trades):
            print(f"  Trade {trade_idx + 1}:")
            for k, v_trade in trade.items(): # Changed v to v_trade to avoid conflict
                if k == "risk_assessment" and isinstance(v_trade, dict):
                    print(f"    {k}:")
                    for ra_k, ra_v in v_trade.items():
                        print(f"      {ra_k}: {ra_v}")
                else:
                    print(f"    {k}: {v_trade}")
    elif finalized_trades == []:
        print("Finalized Trades for Approval: [] (No trades finalized)")
    else:
        print("Finalized Trades for Approval not found in output.")
