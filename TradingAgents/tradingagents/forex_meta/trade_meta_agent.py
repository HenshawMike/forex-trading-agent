from typing import Dict, Any
from tradingagents.forex_utils.forex_states import (
    AggregatedForexProposals,
    ForexFinalDecision,
    ForexMarketContext # For creating a default context if needed
)
import datetime # For timestamping dummy decisions

class ForexMetaAgent:
    def __init__(self, publisher: Any = None, agent_id: str = "ForexMetaAgent_1"): # Optional publisher
        self.publisher = publisher
        self.agent_id = agent_id
        print(f"{self.agent_id} initialized.")

    def evaluate_proposals(self, state: Dict) -> Dict:
        # Expects AggregatedForexProposals under 'aggregated_proposals_for_meta_agent' in state
        aggregated_proposals: AggregatedForexProposals = state.get("aggregated_proposals_for_meta_agent")

        if not aggregated_proposals:
            print(f"{self.agent_id}: No aggregated_proposals_for_meta_agent found in state.")
            # Potentially create a default "STAND_ASIDE" decision if this happens
            current_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            dummy_decision = ForexFinalDecision(
                decision_id=f"dec_meta_error_{current_time_iso.replace(':', '-')}",
                currency_pair=state.get("currency_pair", "N/A_PAIR"), # Try to get from state
                timestamp=current_time_iso,
                based_on_aggregation_id="N/A",
                action="STAND_ASIDE",
                meta_rationale="MetaAgent: Error - No aggregated proposals received.",
                # Fill other Optional fields as None or default
                entry_price=None, stop_loss=None, take_profit=None, position_size=None,
                risk_percentage_of_capital=None, meta_confidence_score=0.0,
                meta_assessed_risk_level="Unknown", contributing_proposals_ids=[],
                status="STATE_SYSTEM_ACTIONED", # Or a specific error status
                pending_approval_timestamp=None, approval_expiry_timestamp=None,
                user_action_timestamp=None, acted_by_user_id=None
            )
            return {"forex_final_decision": dummy_decision}

        aggregation_id = aggregated_proposals['aggregation_id']
        currency_pair = aggregated_proposals['currency_pair']
        num_proposals = len(aggregated_proposals['proposals'])

        print(f"{self.agent_id}: Evaluating {num_proposals} proposals for {currency_pair} from aggregation '{aggregation_id}'.")

        # Placeholder logic: Generate a dummy decision
        # In a real implementation, this would involve:
        # - Regime alignment checks
        # - Confidence score weighting
        # - Conflict resolution
        # - Risk assessment

        current_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        final_action = "STAND_ASIDE"
        final_rationale = f"MetaAgent: Placeholder evaluation for {currency_pair}. Defaulting to STAND_ASIDE."
        final_confidence = 0.3
        final_risk = "Low"

        # Example: If any sub-agent proposed a BUY, MetaAgent weakly agrees for skeleton
        if num_proposals > 0:
            for prop in aggregated_proposals['proposals']:
                if prop['signal'] == "BUY" and prop['confidence_score'] > 0.55: # SwingTrader was 0.6
                    final_action = "EXECUTE_BUY_PENDING_APPROVAL" # Requires user approval
                    final_rationale = f"MetaAgent: Placeholder - Acknowledging a BUY signal from {prop['source_agent_type']} for {currency_pair}."
                    final_confidence = prop['confidence_score'] * 0.8 # Meta slightly less confident than source
                    final_risk = prop['sub_agent_risk_level']
                    # Carry over some trade params for the dummy decision
                    entry_price = prop.get('entry_price')
                    stop_loss = prop.get('stop_loss')
                    take_profit = prop.get('take_profit')
                    break
                # Could add a SELL condition too for testing

        dummy_final_decision = ForexFinalDecision(
            decision_id=f"dec_meta_{currency_pair}_{current_time_iso.replace(':', '-')}",
            currency_pair=currency_pair,
            timestamp=current_time_iso,
            based_on_aggregation_id=aggregation_id,
            action=final_action,
            entry_price=entry_price if 'entry_price' in locals() else None,
            stop_loss=stop_loss if 'stop_loss' in locals() else None,
            take_profit=take_profit if 'take_profit' in locals() else None,
            position_size=0.01 if final_action != "STAND_ASIDE" else None, # Dummy size
            risk_percentage_of_capital=None, # To be calculated by risk manager or from directives
            meta_rationale=final_rationale,
            meta_confidence_score=final_confidence,
            meta_assessed_risk_level=final_risk,
            contributing_proposals_ids=[p['proposal_id'] for p in aggregated_proposals['proposals'] if final_action != "STAND_ASIDE"],
            # User approval related fields
            status="STATE_PENDING_USER_APPROVAL" if "PENDING_APPROVAL" in final_action else "STATE_SYSTEM_ACTIONED",
            pending_approval_timestamp=current_time_iso if "PENDING_APPROVAL" in final_action else None,
            approval_expiry_timestamp= (datetime.datetime.fromisoformat(current_time_iso.replace('Z', '+00:00')) + datetime.timedelta(minutes=5)).isoformat() if "PENDING_APPROVAL" in final_action else None, # 5 min expiry
            user_action_timestamp=None,
            acted_by_user_id=None
        )

        print(f"{self.agent_id}: Generated dummy final decision for {currency_pair}: {dummy_final_decision['action']}")

        # This node updates the graph state with its final decision.
        updated_state_part = {"forex_final_decision": dummy_final_decision}
        return updated_state_part
