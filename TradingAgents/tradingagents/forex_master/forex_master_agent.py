from typing import Dict, List, Any
from tradingagents.forex_utils.forex_states import (
    ForexMarketContext,
    ForexSubAgentTask,
    ForexTradeProposal,
    AggregatedForexProposals
)

# Placeholder for actual agent state if we use the more complex AgentState TypedDict from the main project
# For now, we'll pass dicts around, which LangGraph supports.
# from tradingagents.agents.utils.agent_states import AgentState

class ForexMasterAgent:
    def __init__(self, publisher: Any = None): # Optional publisher for UI updates
        self.publisher = publisher
        print("ForexMasterAgent initialized.")

    def assess_market_regime(self, currency_pair: str, current_state: Dict) -> str:
        # Placeholder logic
        print(f"ForexMasterAgent: Assessing market regime for {currency_pair}...")
        # In a real implementation, this would analyze market data from current_state
        # or call other tools/services.
        # For now, return a default regime.
        regime = "Ranging"
        if self.publisher:
            # Example of publishing an update if a publisher is configured
            # self.publisher.publish('ui:forex_master_updates',
            #                        {"pair": currency_pair, "regime": regime, "timestamp": current_state.get("timestamp")})
            pass
        return regime

    def delegate_tasks_to_sub_agents(self, currency_pair: str, market_regime: str, current_state: Dict) -> List[ForexSubAgentTask]:
        # Placeholder logic
        print(f"ForexMasterAgent: Delegating tasks for {currency_pair} in regime '{market_regime}'.")

        tasks: List[ForexSubAgentTask] = []

        current_time_str = str(current_state.get("current_simulated_time", "N/A_TIME"))

        market_context_snapshot = ForexMarketContext(
            currency_pair=currency_pair,
            timestamp=current_time_str,
            market_regime=market_regime,
            relevant_economic_events=[],
            master_agent_directives={}
        )

        tasks.append(ForexSubAgentTask(
            task_id=f"task_day_{currency_pair}_{current_time_str.replace(':', '-')}",
            currency_pair=currency_pair,
            timeframes_to_analyze=["H1", "M15"],
            market_context_snapshot=market_context_snapshot
        ))

        tasks.append(ForexSubAgentTask(
            task_id=f"task_swing_{currency_pair}_{current_time_str.replace(':', '-')}",
            currency_pair=currency_pair,
            timeframes_to_analyze=["D1", "H4"],
            market_context_snapshot=market_context_snapshot
        ))

        # Task for ScalperAgent
        tasks.append(ForexSubAgentTask(
            task_id=f"task_scalp_{currency_pair}_{current_time_str.replace(':', '-')}", # Use current_time_str
            currency_pair=currency_pair,
            timeframes_to_analyze=["M1", "M5"], # Example scalper timeframes
            market_context_snapshot=market_context_snapshot
        ))

        # Task for PositionTraderAgent
        tasks.append(ForexSubAgentTask(
            task_id=f"task_pos_{currency_pair}_{current_time_str.replace(':', '-')}", # Use current_time_str
            currency_pair=currency_pair,
            timeframes_to_analyze=["W1", "MN1"], # Example position trader timeframes
            market_context_snapshot=market_context_snapshot
        ))

        print(f"ForexMasterAgent: Created {len(tasks)} tasks.")
        return tasks

    def aggregate_proposals(self, proposals: List[ForexTradeProposal], current_state: Dict) -> AggregatedForexProposals:
        # Placeholder logic
        print(f"ForexMasterAgent: Aggregating {len(proposals)} proposals.")

        currency_pair = current_state.get('currency_pair', "N/A_PAIR")
        if proposals: # If there are proposals, use the currency pair from the first one
            currency_pair = proposals[0]['currency_pair']

        current_time_str = str(current_state.get("current_simulated_time", "N/A_TIME"))

        market_context_snap = ForexMarketContext(
             currency_pair=currency_pair,
             timestamp=current_time_str,
             market_regime=str(current_state.get("market_regime", "Unknown")),
             relevant_economic_events=[],
             master_agent_directives={}
        )

        aggregated = AggregatedForexProposals(
            aggregation_id=f"agg_{currency_pair}_{current_time_str.replace(':', '-')}",
            currency_pair=currency_pair,
            timestamp=current_time_str,
            market_context_at_aggregation=market_context_snap,
            proposals=proposals
        )
        return aggregated

    def initial_processing_node(self, state: Dict) -> Dict:
        print(f"ForexMasterAgent: Initial processing node called with state: {state}")
        currency_pair = str(state.get("currency_pair", "EURUSD_DEFAULT"))

        market_regime = self.assess_market_regime(currency_pair, state)
        sub_agent_tasks = self.delegate_tasks_to_sub_agents(currency_pair, market_regime, state)

        updated_state = state.copy()
        updated_state["sub_agent_tasks"] = sub_agent_tasks
        updated_state["market_regime"] = market_regime
        updated_state["proposals_from_sub_agents"] = []
        print(f"ForexMasterAgent: initial_processing_node returning state with {len(sub_agent_tasks)} tasks.")
        return updated_state

    def aggregation_node(self, state: Dict) -> Dict:
        print(f"ForexMasterAgent: Aggregation node called with state: {state}")
        proposals = state.get("proposals_from_sub_agents", [])

        # Ensure market_context_at_aggregation is properly formed even if proposals is empty
        current_time_str = str(state.get("current_simulated_time", "N/A_TIME"))
        current_pair_str = str(state.get("currency_pair", "N/A_PAIR"))
        current_regime_str = str(state.get("market_regime", "Unknown"))

        default_market_context = ForexMarketContext(
            currency_pair=current_pair_str,
            timestamp=current_time_str,
            market_regime=current_regime_str,
            relevant_economic_events=[],
            master_agent_directives={}
        )

        if not proposals:
            print("ForexMasterAgent: No proposals from sub-agents to aggregate.")
            aggregated_data = AggregatedForexProposals(
                aggregation_id=f"agg_empty_{current_pair_str}_{current_time_str.replace(':', '-')}",
                currency_pair=current_pair_str,
                timestamp=current_time_str,
                market_context_at_aggregation=default_market_context,
                proposals=[]
            )
        else:
            aggregated_data = self.aggregate_proposals(proposals, state)

        updated_state = state.copy()
        updated_state["aggregated_proposals_for_meta_agent"] = aggregated_data
        print(f"ForexMasterAgent: aggregation_node returning state with aggregated data for {aggregated_data['currency_pair']}.")
        return updated_state
