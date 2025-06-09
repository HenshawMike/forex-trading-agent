from typing import Any, Dict, List, Optional

class TradeMetaAgent:
    def __init__(self, llm: Any, memory: Any, risk_management_team: Any): # Replace Any with actual types
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.risk_management_team = risk_management_team # This would be an interface to the risk agents/graph
        # print(f"TradeMetaAgent initialized.") # Reduced verbosity

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
        # Helper to determine bias for a specific pair based on the directive
        directive_bias_info = strategic_directive.get("primary_bias", {})
        pair_bias_direction = None # Default to None if no specific bias can be determined

        # Check for pair-specific bias first
        if isinstance(directive_bias_info.get("pair"), str) and directive_bias_info.get("pair") == pair:
            pair_bias_direction = directive_bias_info.get("direction")
        # Then check for currency-specific bias
        elif isinstance(directive_bias_info.get("currency"), str):
            base_currency, quote_currency = pair.split("/") if "/" in pair else (None, None)
            if base_currency and quote_currency:
                target_currency = directive_bias_info["currency"]
                target_direction = directive_bias_info.get("direction")
                if target_currency == base_currency:
                    pair_bias_direction = target_direction
                elif target_currency == quote_currency:
                    if target_direction == "bullish": pair_bias_direction = "bearish"
                    elif target_direction == "bearish": pair_bias_direction = "bullish"

        # If still no specific direction, check for market_condition
        if pair_bias_direction is None: # Only if not already set by pair or currency
            market_condition = directive_bias_info.get("market_condition")
            if market_condition in ["ranging", "neutral_or_mixed_signals", "neutral", "ranging_on_pair"]:
                return "ranging" # or "neutral" - consistent term is better
            # If market condition is bullish/bearish on ALL or on a set of pairs that includes this one
            if market_condition == "bullish_all" or (isinstance(directive_bias_info.get("pairs"), list) and pair in directive_bias_info.get("pairs") and "bullish" in market_condition):
                return "bullish"
            if market_condition == "bearish_all" or (isinstance(directive_bias_info.get("pairs"), list) and pair in directive_bias_info.get("pairs") and "bearish" in market_condition):
                return "bearish"

        return pair_bias_direction # Can be "bullish", "bearish", "ranging", or None

    def coordinate_trades(
        self,
        trade_proposals: List[Dict[str, Any]],
        strategic_directive: Dict[str, Any],
        portfolio_status: Dict[str, Any] # e.g., {"balance": 10000, "max_concurrent_trades": 3, "risk_per_trade_percentage": 0.01}
    ) -> List[Dict[str, Any]]:
        print(f"TradeMetaAgent received {len(trade_proposals)} trade_proposals. Directive: {strategic_directive.get('key_narrative')}. Portfolio Status: {portfolio_status}")

        if not trade_proposals:
            print("TradeMetaAgent: No proposals to coordinate.")
            return []

        enriched_proposals = []
        for proposal in trade_proposals:
            pair = proposal.get("pair", "UnknownPair")
            proposal_side = proposal.get("side", "").lower() # "buy" or "sell"

            directive_pair_bias = self._get_pair_bias_from_directive(pair, strategic_directive)
            alignment_score = 0.5 # Default for neutral/ranging or if bias unclear

            if directive_pair_bias == "bullish" and proposal_side == "buy":
                alignment_score = 1.0
            elif directive_pair_bias == "bearish" and proposal_side == "sell":
                alignment_score = 1.0
            elif directive_pair_bias == "ranging":
                alignment_score = 0.6
            elif directive_pair_bias and directive_pair_bias != "neutral": # Exists but does not match proposal side
                alignment_score = 0.1

            proposal["alignment_score"] = alignment_score
            proposal["directive_pair_bias"] = directive_pair_bias # For logging/rationale

            # Simulated Risk Assessment (using placeholder risk team)
            # In a real scenario, self.risk_management_team would be an agent or graph invocation
            risk_assessment_output = self.risk_management_team.assess_trade(proposal)
            proposal["risk_assessment"] = risk_assessment_output

            enriched_proposals.append(proposal)
            print(f"TradeMetaAgent: Processed proposal for {pair} (Side: {proposal_side}, Sub-Agent Conf: {proposal.get('confidence_score',0):.2f}, Align: {alignment_score:.2f}, Risk Score: {risk_assessment_output.get('risk_score',0):.2f}, Directive Bias for Pair: {directive_pair_bias})")

        def sort_key(p):
            # Higher score is better.
            # (alignment_score (0-1) + sub-agent_confidence (0-1) + (1 - risk_assessment_score (0-1)))
            # Default risk_score to 1.0 (max risk) if not present, making the term (1-risk_score) = 0
            risk_metric = (1.0 - p.get("risk_assessment", {}).get("risk_score", 1.0))
            return p.get("alignment_score", 0) + p.get("confidence_score", 0) + risk_metric

        min_alignment_threshold = 0.4
        aligned_proposals = [p for p in enriched_proposals if p.get("alignment_score",0) >= min_alignment_threshold]

        if not aligned_proposals and enriched_proposals:
             print("TradeMetaAgent: No proposals met minimum alignment threshold of {min_alignment_threshold}, considering all {len(enriched_proposals)} enriched proposals for sorting.")
             aligned_proposals = enriched_proposals # Fallback to all if none meet threshold
        elif not enriched_proposals:
             print("TradeMetaAgent: No enriched proposals to sort.")
             aligned_proposals = []


        sorted_proposals = sorted(aligned_proposals, key=sort_key, reverse=True)

        if sorted_proposals:
            print(f"TradeMetaAgent: Sorted {len(sorted_proposals)} proposals. Top score: {sort_key(sorted_proposals[0]):.2f} for {sorted_proposals[0]['pair']}")
        else:
            print("TradeMetaAgent: No proposals available for sorting or after alignment filtering.")


        finalized_trades_for_approval = []
        max_trades_to_select = portfolio_status.get("max_concurrent_trades", 1)

        for selected_proposal in sorted_proposals[:max_trades_to_select]:
            # Example threshold for combined score (align + confidence + (1-risk))
            # Max possible score is 1 (align) + 1 (confidence) + 1 (1-0 risk) = 3
            # Let's set a threshold like 1.5 (meaning decent alignment, confidence, and not max risk)
            current_proposal_score = sort_key(selected_proposal)
            if current_proposal_score < 1.5:
                print(f"TradeMetaAgent: Proposal for {selected_proposal['pair']} with score {current_proposal_score:.2f} did not meet minimum quality score of 1.5. Skipping.")
                continue

            balance = portfolio_status.get("balance", 10000)
            risk_per_trade_percentage = portfolio_status.get("risk_per_trade_percentage", 0.01)
            amount_to_risk = balance * risk_per_trade_percentage

            stop_loss_price = selected_proposal.get("stop_loss")
            entry_price = selected_proposal.get("entry_price") # This is None for market orders
            # For sizing, we need a definite entry. If market order, assume current price (not available here directly)
            # This highlights the need for current price access or for sub-agents to provide intended entry for market orders

            # MOCKING entry for sizing if market order
            if selected_proposal.get("type") == "market" and entry_price is None:
                # This is a significant simplification. In reality, TradeMetaAgent would need access to current prices
                # or the sub-agent should provide an indicative entry price even for market orders.
                # Let's assume for mock purposes, an indicative entry can be derived or is already in proposal.
                # For this skeleton, we'll use a fixed SL pips if prices aren't there.
                print(f"TradeMetaAgent Warning: Market order for {selected_proposal['pair']} has no entry_price for precise sizing. Using fixed SL pips for mock sizing.")
                entry_price_for_sizing = portfolio_status.get("mock_current_price", {}).get(selected_proposal['pair'], 1.1000) # Needs a mock current price source
                if selected_proposal.get("side") == "buy":
                    stop_loss_price_for_sizing = entry_price_for_sizing - 0.0020 # Default 20 pips
                else:
                    stop_loss_price_for_sizing = entry_price_for_sizing + 0.0020 # Default 20 pips
                if "JPY" in selected_proposal["pair"].upper():
                     stop_loss_price_for_sizing = entry_price_for_sizing - 0.20 if selected_proposal.get("side") == "buy" else entry_price_for_sizing + 0.20


            stop_loss_distance_pips = abs(entry_price_for_sizing - stop_loss_price_for_sizing) * (10000 if "JPY" not in selected_proposal["pair"].upper() else 100)

            if stop_loss_distance_pips <= 0:
                print(f"TradeMetaAgent Error: Stop loss distance is zero or negative for {selected_proposal['pair']}. Cannot size. SL: {stop_loss_price}, Entry: {entry_price_for_sizing}")
                continue

            # Simplified pip value assumption: $10 per pip per standard lot for non-JPY, $7 for JPY.
            value_per_pip_per_lot = 7 if "JPY" in selected_proposal["pair"].upper() else 10

            calculated_position_size = amount_to_risk / (stop_loss_distance_pips * value_per_pip_per_lot)
            calculated_position_size = max(0.01, round(calculated_position_size, 2))

            selected_proposal["calculated_position_size"] = calculated_position_size
            selected_proposal["meta_rationale"] = (f"Selected (Score: {current_proposal_score:.2f}). "
                                                  f"Align: {selected_proposal['alignment_score']:.2f}, "
                                                  f"Conf: {selected_proposal.get('confidence_score',0):.2f}, "
                                                  f"Risk Assess: {selected_proposal.get('risk_assessment',{}).get('assessment','N/A')} (Score: {selected_proposal.get('risk_assessment',{}).get('risk_score',1.0):.2f}). "
                                                  f"Sized for {risk_per_trade_percentage*100:.1f}% risk. SL pips (approx): {stop_loss_distance_pips:.1f}")

            finalized_trades_for_approval.append(selected_proposal)

        if finalized_trades_for_approval:
            print(f"TradeMetaAgent: Finalized {len(finalized_trades_for_approval)} trade(s) for approval.")
            for trade_idx, trade in enumerate(finalized_trades_for_approval):
                print(f"  Finalized Trade {trade_idx+1}: {trade['pair']} {trade['side']} Size: {trade['calculated_position_size']:.2f} lots. Rationale: {trade['meta_rationale']}")
        else:
            print("TradeMetaAgent: No trades were finalized for approval based on scoring or sizing.")

        return finalized_trades_for_approval
