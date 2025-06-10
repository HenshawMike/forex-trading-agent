from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional, Union
import numpy as np
from datetime import datetime, timezone, timedelta
import pandas as pd

from tradingagents.forex_master.forex_master_agent import ForexMasterAgent
from tradingagents.forex_meta.trade_meta_agent import TradeMetaAgent
from tradingagents.forex_agents.day_trader_agent import DayTraderAgent
from tradingagents.forex_agents.swing_trader_agent import SwingTraderAgent
from tradingagents.forex_agents.scalper_agent import ScalperAgent
from tradingagents.forex_agents.position_trader_agent import PositionTraderAgent
from tradingagents.broker_interface.base import BrokerInterface
from tradingagents.graph.risk_assessment_graph import RiskAssessmentGraph

class PlaceholderLLM:
    def invoke(self, prompt: str) -> str:
        if "Strategic Forex Directive" in str(prompt):
            mock_directive = {
                "primary_bias": {"currency": "USD", "direction": "bullish"},
                "confidence_in_bias": "medium",
                "preferred_timeframes": ["intraday", "h1"],
                "volatility_expectation": "moderate",
                "focus_pairs": ["EUR/USD", "USD/JPY"],
                "key_narrative": "LLM Mock: USD showing bullish signs, focus on intraday EUR/USD shorts and USD/JPY longs.",
                "key_levels_to_watch": {"EUR/USD_resistance": 1.0950},
                "llm_generated": True
            }
            import json
            return json.dumps(mock_directive)
        return f"LLM invoked with: {prompt[:50]}..."


class PlaceholderMemory:
    def retrieve(self, query: str) -> List[str]:
        return [f"Memory retrieved for: {query}"]
    def add_memory(self, text: str, metadata: Optional[Dict] = None) -> None:
        pass
    def get_memories(self, query: str, n_matches: int = 2) -> List[Dict[str, Any]]:
        return [{"recommendation": "Past lesson from PlaceholderMemory: be cautious with high volatility."}]

class ForexGraphState(TypedDict):
    market_outlook: Optional[Dict[str, Any]]
    user_preferences: Optional[Dict[str, Any]]
    strategic_directive: Optional[Dict[str, Any]]
    day_trader_proposals: Optional[List[Dict[str, Any]]]
    swing_trader_proposals: Optional[List[Dict[str, Any]]]
    scalper_proposals: Optional[List[Dict[str, Any]]]
    position_trader_proposals: Optional[List[Dict[str, Any]]]
    aggregated_proposals: List[Dict[str, Any]]
    finalized_trades_for_approval: Optional[List[Dict[str, Any]]]
    portfolio_status: Optional[Dict[str, Any]]
    error_message: Optional[str]

class ForexTradingGraph:
    def __init__(self, llm_for_sub_agents: Any, broker_interface: BrokerInterface, llm_model_name_for_master: str = "gpt-3.5-turbo", llm_model_name_for_risk: str = "gpt-3.5-turbo"): # Added llm_model_name_for_risk
        self.llm_for_sub_agents = llm_for_sub_agents
        self.broker_interface = broker_interface
        self.llm_model_name_for_master = llm_model_name_for_master # Store it
        self.llm_model_name_for_risk = llm_model_name_for_risk # Store it
        shared_memory = PlaceholderMemory()

        self.forex_master_agent = ForexMasterAgent(llm_model_name=self.llm_model_name_for_master, memory=shared_memory)

        self.day_trader_agent = DayTraderAgent(
            agent_id="day_trader_main",
            llm_model_name="gpt-3.5-turbo", # Or your preferred default
            memory=shared_memory,
            broker_interface=self.broker_interface
        )
        self.swing_trader_agent = SwingTraderAgent(agent_id="swing_trader_main", llm=self.llm_for_sub_agents, memory=shared_memory, broker_interface=self.broker_interface)
        self.scalper_agent = ScalperAgent(agent_id="scalper_main", llm=self.llm_for_sub_agents, memory=shared_memory, broker_interface=self.broker_interface)
        self.position_trader_agent = PositionTraderAgent(agent_id="position_trader_main", llm=self.llm_for_sub_agents, memory=shared_memory, broker_interface=self.broker_interface)

        # RiskAssessmentGraph now gets its own model name config
        self.risk_assessment_graph_instance = RiskAssessmentGraph(llm_model_name=self.llm_model_name_for_risk, memory_manager=shared_memory)

        self.trade_meta_agent = TradeMetaAgent(
            llm=self.llm_for_sub_agents,
            memory=shared_memory,
            risk_assessment_workflow=self.risk_assessment_graph_instance
        )
        self.workflow = self._build_graph()

    def _build_graph(self) -> StateGraph:
        graph = StateGraph(ForexGraphState)

        graph.add_node("run_forex_master_agent", self.run_forex_master_agent)
        graph.add_node("run_day_trader_agent", self.run_day_trader_agent)
        graph.add_node("run_swing_trader_agent", self.run_swing_trader_agent)
        graph.add_node("run_scalper_agent", self.run_scalper_agent)
        graph.add_node("run_position_trader_agent", self.run_position_trader_agent)
        graph.add_node("aggregate_trading_proposals", self.aggregate_trading_proposals)
        graph.add_node("run_trade_meta_agent", self.run_trade_meta_agent)

        graph.set_entry_point("run_forex_master_agent")
        graph.add_edge("run_forex_master_agent", "run_day_trader_agent")
        graph.add_edge("run_forex_master_agent", "run_swing_trader_agent")
        graph.add_edge("run_forex_master_agent", "run_scalper_agent")
        graph.add_edge("run_forex_master_agent", "run_position_trader_agent")
        graph.add_edge("run_day_trader_agent", "aggregate_trading_proposals")
        graph.add_edge("run_swing_trader_agent", "aggregate_trading_proposals")
        graph.add_edge("run_scalper_agent", "aggregate_trading_proposals")
        graph.add_edge("run_position_trader_agent", "aggregate_trading_proposals")
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
        if not strategic_directive: return {"error_message": "DayTrader: Missing strategic directive."}
        proposals = self.day_trader_agent.analyze_and_propose_trades(strategic_directive)
        return {"day_trader_proposals": proposals}

    def run_swing_trader_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Swing Trader Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive: return {"error_message": "SwingTrader: Missing strategic directive."}
        proposals = self.swing_trader_agent.analyze_and_propose_trades(strategic_directive)
        return {"swing_trader_proposals": proposals}

    def run_scalper_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Scalper Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive: return {"scalper_proposals": []}
        proposals = self.scalper_agent.analyze_and_propose_trades(strategic_directive)
        return {"scalper_proposals": proposals}

    def run_position_trader_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Position Trader Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive: return {"error_message": "PositionTrader: Missing strategic directive.", "position_trader_proposals": []}
        proposals = self.position_trader_agent.analyze_and_propose_trades(strategic_directive)
        return {"position_trader_proposals": proposals}

    def aggregate_trading_proposals(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Aggregating Trading Proposals ---")
        all_proposals = []
        for key in ["day_trader_proposals", "swing_trader_proposals", "scalper_proposals", "position_trader_proposals"]:
            if state.get(key): all_proposals.extend(state[key]) # type: ignore
        print(f"Total proposals aggregated: {len(all_proposals)}")
        return {"aggregated_proposals": all_proposals}

    def run_trade_meta_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Trade Meta Agent ---")
        proposals = state.get("aggregated_proposals", [])
        strategic_directive = state.get("strategic_directive")
        portfolio_status = state.get("portfolio_status", {"balance": 10000, "open_positions": 0, "max_concurrent_trades": 1, "risk_per_trade_percentage": 0.01})
        if not strategic_directive: return {"error_message": "TradeMetaAgent: Missing strategic directive."}
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
            scalper_proposals=initial_state_dict.get("scalper_proposals"),
            position_trader_proposals=initial_state_dict.get("position_trader_proposals"),
            aggregated_proposals=initial_state_dict.get("aggregated_proposals", []),
            finalized_trades_for_approval=None,
            portfolio_status=initial_state_dict.get("portfolio_status"),
            error_message=None
        )
        final_state = self.workflow.invoke(graph_input)
        print("--- Forex Trading Graph Run Complete ---")
        return final_state

if __name__ == "__main__":
    placeholder_llm_instance = PlaceholderLLM()

    class MockBroker(BrokerInterface):
        def connect(self, credentials): return True
        def disconnect(self): pass
        def get_account_info(self): return {"balance": 10000, "currency": "USD", "equity": 10000, "margin": 5000}
        def get_current_price(self, pair): return {"bid": 1.1, "ask": 1.1002, "time": datetime.now(timezone.utc)}
        def get_historical_data(self, pair: str, timeframe: str, start_date: Optional[Union[datetime, str]] = None, end_date: Optional[Union[datetime, str]] = None, count: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
            num_bars = count if count else 200
            freq_map = {"M1": "min", "M5": "5min", "M15": "15min", "H1": "h", "H4": "4h", "D1": "D", "W1": "W-MON"}
            data_freq = freq_map.get(timeframe, "D")
            end_ts = pd.Timestamp.now(tz='UTC')
            if end_date: end_ts = pd.to_datetime(end_date, utc=True)
            if start_date and not end_date and not count:
                start_ts = pd.to_datetime(start_date, utc=True)
                time_delta_map = {'min': 60, '5min': 5*60, '15min': 15*60, 'h': 3600, '4h': 4*3600, 'D': 24*3600, 'W-MON': 7*24*3600}
                num_bars = int((end_ts - start_ts).total_seconds() / time_delta_map.get(data_freq, 24*3600))
                num_bars = max(num_bars, 50)
            num_bars = max(num_bars, 50)
            dates = pd.date_range(end=end_ts, periods=num_bars, freq=data_freq)
            start_price = np.random.uniform(1.0, 1.5)
            if "JPY" in pair.upper(): start_price = np.random.uniform(100.0, 180.0)
            price_changes = np.random.normal(0, 0.001, size=num_bars)
            if "JPY" in pair.upper(): price_changes = np.random.normal(0, 0.1, size=num_bars)
            if timeframe in ["M1", "M5", "M15"]:
                price_changes = np.random.normal(0, 0.0001, size=num_bars)
                if "JPY" in pair.upper(): price_changes = np.random.normal(0, 0.01, size=num_bars)
            close_prices = start_price + np.cumsum(price_changes)
            close_prices = np.maximum(0.01, close_prices)
            if "JPY" not in pair.upper() and np.min(close_prices) < 0.5: close_prices = np.maximum(0.5, close_prices)
            open_prices = np.roll(close_prices, 1)
            open_prices[0] = close_prices[0] - price_changes[0]
            data_list = []
            for i in range(num_bars):
                o, c = open_prices[i], close_prices[i]
                volatility_factor = 0.0005 * start_price if timeframe not in ["W1", "MN1"] else 0.01 * start_price
                high = max(o, c) + abs(np.random.normal(0, volatility_factor))
                low = min(o, c) - abs(np.random.normal(0, volatility_factor))
                low = max(0.0001, low)
                data_list.append({"time": dates[i], "open": o, "high": high, "low": low, "close": c, "volume": np.random.randint(100, 10000)})
            return data_list
        def place_order(self, order_details): return {"success": True, "order_id": "sim123", "message": "Simulated order placed."}
        def modify_order(self, order_id, new_params): return {"success": True, "message": "Simulated order modified."}
        def close_order(self, order_id, size_to_close=None): return {"success": True, "message": "Simulated order closed."}
        def get_open_positions(self): return []
        def get_pending_orders(self): return []

    mock_broker = MockBroker()
    forex_graph_instance = ForexTradingGraph(
        llm_for_sub_agents=placeholder_llm_instance, # For agents not using internal LLM client based on name
        broker_interface=mock_broker,
        llm_model_name_for_master="gpt-3.5-turbo", # ForexMasterAgent will use this
        llm_model_name_for_risk="gpt-3.5-turbo-mock-risk" # RiskAssessmentGraph will pass this to its agents
    )

    initial_run_state = {
        "market_outlook": {
            "summary": "Overall market is cautious. USD showed some strength on recent data.",
            "sentiment": {"USD": "strong_bullish", "EUR": "neutral", "AUD/JPY": "ranging"},
            "volatility_forecast": "moderate",
            "key_levels": {"EUR/USD_resistance": 1.0900, "USD/JPY_support": 148.50},
            "economic_events": ["US CPI next week"]
        },
        "user_preferences": {
            "risk_appetite": "aggressive",
            "preferred_pairs": ["EUR/USD", "USD/JPY", "GBP/JPY", "AUD/USD"],
            "trading_style_preference": "day_trader",
            "disallowed_pairs": ["USD/CAD"]
        },
        "portfolio_status": {
            "balance": 25000, "equity": 25000, "margin_available": 25000,
            "open_positions": [], "max_concurrent_trades": 3,
            "risk_per_trade_percentage": 0.01,
            "mock_current_price": {"EUR/USD": 1.0850, "USD/JPY": 149.50, "GBP/JPY": 189.50, "AUD/USD": 0.6550}
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
        llm_gen_status = strategic_directive_output.get("llm_generated", False)
        print(f"  LLM Generated: {llm_gen_status}")
        for k, v in strategic_directive_output.items():
            if k != "llm_generated":
                print(f"    {k}: {v}")
    else:
        print("  Strategic Directive not found in output.")

    # Specific handling for DayTraderAgent proposals to show llm_generated_proposal flag
    print("\n--- Specific check for Day Trader Proposals ---")
    day_trader_proposals = final_output_state.get("day_trader_proposals")
    if day_trader_proposals:
        print(f"Day Trader Proposals ({len(day_trader_proposals)}):")
        for proposal_idx, proposal in enumerate(day_trader_proposals):
            print(f"  Proposal {proposal_idx + 1}:")
            for k, v in proposal.items():
                if k == "llm_generated_proposal": # Specifically highlight this flag
                    print(f"    {k}: {v} <--- LLM Status")
                else:
                    print(f"    {k}: {v}")
    elif day_trader_proposals == []: # Explicitly check for empty list
            print("Day Trader Proposals: [] (No trades proposed by DayTraderAgent)")
    else:
        print("Day Trader Proposals not found or DayTraderAgent did not run.")

    # Handling for other agents (SwingTrader, Scalper, PositionTrader)
    for agent_name_key in ["swing_trader_proposals", "scalper_proposals", "position_trader_proposals"]:
        print(f"\n--- Specific check for {agent_name_key.replace('_', ' ').title()} ---")
        proposals = final_output_state.get(agent_name_key)
        if proposals:
            print(f"{agent_name_key.replace('_', ' ').title()} ({len(proposals)}):")
            for proposal_idx, proposal in enumerate(proposals):
                # Generic print for these agents, can be expanded if they also get llm_generated_proposal
                print(f"  Proposal {proposal_idx + 1}: {proposal.get('pair')} {proposal.get('side')} - Conf: {proposal.get('confidence_score')}, Rationale: {proposal.get('rationale', 'N/A')[:50]}...")
        elif proposals == []:
             print(f"{agent_name_key.replace('_', ' ').title()}: [] (No trades proposed)")
        else:
            print(f"{agent_name_key.replace('_', ' ').title()} not found or not run in output.")

    print("\n--- Specific check for Finalized Trades for Approval ---")
    finalized_trades = final_output_state.get("finalized_trades_for_approval")
    if finalized_trades:
        print(f"Finalized Trades for Approval ({len(finalized_trades)}):")
        for trade_idx, trade in enumerate(finalized_trades):
            print(f"  Trade {trade_idx + 1}:")
            for k, v_trade in trade.items():
                if k == "risk_assessment" and isinstance(v_trade, dict):
                    print(f"    {k}:")
                    for ra_k, ra_v in v_trade.items(): print(f"      {ra_k}: {ra_v}")
                else: print(f"    {k}: {v_trade}")
    elif finalized_trades == []:
        print("Finalized Trades for Approval: [] (No trades finalized)")
    else:
        print("Finalized Trades for Approval not found in output.")
