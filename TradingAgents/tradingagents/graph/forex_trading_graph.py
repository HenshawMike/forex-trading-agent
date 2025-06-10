from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Dict, Any, Optional, Union # Ensured Union is here
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
        if "ForexMasterAgent" in prompt:
            return f"LLM invoked for MasterAgent: {prompt[:50]}... Directive: Bullish EUR/USD"
        elif "DayTraderAgent" in prompt:
            return f"LLM invoked for DayTrader: {prompt[:50]}... Proposal: Buy EUR/USD"
        elif "SwingTraderAgent" in prompt:
            return f"LLM invoked for SwingTrader: {prompt[:50]}... Proposal: Sell GBP/JPY"
        elif "ScalperAgent" in prompt:
            return f"LLM invoked for Scalper: {prompt[:50]}... Proposal: Buy USD/CHF"
        elif "PositionTraderAgent" in prompt:
            return f"LLM invoked for PositionTrader: {prompt[:50]}... Proposal: Buy AUD/NZD"
        elif "TradeMetaAgent" in prompt:
            return f"LLM invoked for MetaAgent: {prompt[:50]}... Evaluating proposals"
        elif "Aggressive take" in prompt or "Risky Risk Analyst" in prompt :
             return "Mock LLM (Risk): Aggressive: Looks like a winner, risks are minimal!"
        elif "Conservative view" in prompt or "Safe/Conservative Risk Analyst" in prompt:
             return "Mock LLM (Risk): Conservative: Too risky, potential for significant loss."
        elif "Neutral assessment" in prompt or "Neutral Risk Analyst" in prompt:
             return "Mock LLM (Risk): Neutral: Pros and cons are balanced, exercise caution."
        elif "Risk Management Judge" in prompt:
             return "Mock LLM (Risk): Risk Judge: Synthesizing all views for final risk call."
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
    def __init__(self, llm: Any, broker_interface: BrokerInterface):
        self.llm = llm
        self.broker_interface = broker_interface
        shared_memory = PlaceholderMemory()

        self.forex_master_agent = ForexMasterAgent(llm=self.llm, memory=shared_memory)
        self.day_trader_agent = DayTraderAgent(agent_id="day_trader_main", llm=self.llm, memory=shared_memory, broker_interface=self.broker_interface)
        self.swing_trader_agent = SwingTraderAgent(agent_id="swing_trader_main", llm=self.llm, memory=shared_memory, broker_interface=self.broker_interface)
        self.scalper_agent = ScalperAgent(agent_id="scalper_main", llm=self.llm, memory=shared_memory, broker_interface=self.broker_interface)
        self.position_trader_agent = PositionTraderAgent(agent_id="position_trader_main", llm=self.llm, memory=shared_memory, broker_interface=self.broker_interface)

        self.risk_assessment_graph_instance = RiskAssessmentGraph(llm=self.llm, memory_manager=shared_memory)
        self.trade_meta_agent = TradeMetaAgent(
            llm=self.llm,
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

    def run_scalper_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Scalper Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive:
            print("ScalperAgent: Warning - Missing strategic directive.")
            return {"scalper_proposals": []}
        proposals = self.scalper_agent.analyze_and_propose_trades(strategic_directive)
        return {"scalper_proposals": proposals}

    def run_position_trader_agent(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Running Position Trader Agent ---")
        strategic_directive = state.get("strategic_directive")
        if not strategic_directive:
            print("PositionTraderAgent: Error - Missing strategic directive.")
            return {"error_message": "PositionTrader: Missing strategic directive.", "position_trader_proposals": []}
        proposals = self.position_trader_agent.analyze_and_propose_trades(strategic_directive)
        return {"position_trader_proposals": proposals}

    def aggregate_trading_proposals(self, state: ForexGraphState) -> Dict[str, Any]:
        print("--- Aggregating Trading Proposals ---")
        all_proposals = []
        day_proposals = state.get("day_trader_proposals")
        if day_proposals is not None: all_proposals.extend(day_proposals)

        swing_proposals = state.get("swing_trader_proposals")
        if swing_proposals is not None: all_proposals.extend(swing_proposals)

        scalper_proposals = state.get("scalper_proposals")
        if scalper_proposals is not None: all_proposals.extend(scalper_proposals)

        position_trader_proposals = state.get("position_trader_proposals")
        if position_trader_proposals is not None: all_proposals.extend(position_trader_proposals)

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
    mock_llm = PlaceholderLLM()

    class MockBroker(BrokerInterface):
        def connect(self, credentials): return True
        def disconnect(self): pass
        def get_account_info(self): return {"balance": 10000, "currency": "USD", "equity": 10000, "margin": 5000}
        def get_current_price(self, pair): return {"bid": 1.1, "ask": 1.1002, "time": datetime.now(timezone.utc)}

        def get_historical_data(self, pair: str, timeframe: str, start_date: Optional[Union[datetime, str]] = None, end_date: Optional[Union[datetime, str]] = None, count: Optional[int] = None) -> Optional[List[Dict[str, Any]]]:
            num_bars = count if count else 200

            freq_map = {"M1": "min", "M5": "5min", "M15": "15min", "H1": "h", "H4": "4h", "D1": "D", "W1": "W-MON"} # Corrected T to min, H to h
            data_freq = freq_map.get(timeframe, "D")

            end_ts = pd.Timestamp.now(tz='UTC')
            if end_date:
                end_ts = pd.to_datetime(end_date, utc=True)

            if start_date and not end_date and not count:
                start_ts = pd.to_datetime(start_date, utc=True)
                # This logic for calculating num_bars from date range is approximate
                if data_freq == 'min': num_bars = int((end_ts - start_ts).total_seconds() / 60)
                elif data_freq == '5min': num_bars = int((end_ts - start_ts).total_seconds() / (5*60))
                elif data_freq == '15min': num_bars = int((end_ts - start_ts).total_seconds() / (15*60))
                elif data_freq == 'h': num_bars = int((end_ts - start_ts).total_seconds() / 3600)
                elif data_freq == '4h': num_bars = int((end_ts - start_ts).total_seconds() / (4*3600))
                elif data_freq == 'D': num_bars = (end_ts - start_ts).days
                elif data_freq == 'W-MON': num_bars = (end_ts - start_ts).days // 7
                else: num_bars = (end_ts - start_ts).days
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
            if "JPY" not in pair.upper() and np.min(close_prices) < 0.5:
                close_prices = np.maximum(0.5, close_prices)

            open_prices = np.roll(close_prices, 1)
            open_prices[0] = close_prices[0] - price_changes[0]

            data_list = []
            for i in range(num_bars):
                o, c = open_prices[i], close_prices[i]
                volatility_factor = 0.0005 * start_price if timeframe not in ["W1", "MN1"] else 0.01 * start_price
                high = max(o, c) + abs(np.random.normal(0, volatility_factor))
                low = min(o, c) - abs(np.random.normal(0, volatility_factor))
                low = max(0.0001, low)
                data_list.append({
                    "time": dates[i], "open": o, "high": high, "low": low, "close": c,
                    "volume": np.random.randint(100, 10000)
                })
            return data_list

        def place_order(self, order_details): return {"success": True, "order_id": "sim123", "message": "Simulated order placed."}
        def modify_order(self, order_id, new_params): return {"success": True, "message": "Simulated order modified."}
        def close_order(self, order_id, size_to_close=None): return {"success": True, "message": "Simulated order closed."}
        def get_open_positions(self): return []
        def get_pending_orders(self): return []

    mock_broker = MockBroker()
    forex_graph_instance = ForexTradingGraph(llm=mock_llm, broker_interface=mock_broker)

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
        for k, v in strategic_directive_output.items(): print(f"  {k}: {v}")
    else: print("Strategic Directive not found in final output.")

    for agent_name_key in ["day_trader_proposals", "swing_trader_proposals", "scalper_proposals", "position_trader_proposals"]:
        print(f"\n--- Specific check for {agent_name_key.replace('_', ' ').title()} ---")
        proposals = final_output_state.get(agent_name_key)
        if proposals:
            print(f"{agent_name_key.replace('_', ' ').title()} ({len(proposals)}):")
            for proposal_idx, proposal in enumerate(proposals):
                print(f"  Proposal {proposal_idx + 1}: {proposal.get('pair')} {proposal.get('side')} - Conf: {proposal.get('confidence_score')}")
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
