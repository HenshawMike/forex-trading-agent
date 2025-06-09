from typing import Any, Dict, List, Optional, Callable # Added Callable
# from tradingagents.graph.risk_assessment_graph import RiskGraphState # For type hinting if needed, actual class not strictly needed for .run call

class TradeMetaAgent:
    def __init__(self, llm: Any, memory: Any, risk_assessment_workflow: Callable[[Dict], Dict]): # Changed risk_management_team to risk_assessment_workflow
        self.llm = llm # Placeholder
        self.memory = memory # Placeholder
        self.risk_assessment_workflow = risk_assessment_workflow # Store the compiled graph/workflow
        # print(f"TradeMetaAgent initialized with risk_assessment_workflow.") # Adjusted print

    def _get_pair_bias_from_directive(self, pair: str, strategic_directive: Dict[str, Any]) -> Optional[str]:
        directive_bias_info = strategic_directive.get("primary_bias", {})
        pair_bias_direction = None

        if isinstance(directive_bias_info.get("pair"), str) and directive_bias_info.get("pair") == pair:
            pair_bias_direction = directive_bias_info.get("direction")
        elif isinstance(directive_bias_info.get("currency"), str):
            base_currency, quote_currency = pair.split("/") if "/" in pair else (None,None)
            if base_currency and quote_currency:
                target_currency = directive_bias_info["currency"]
                target_direction = directive_bias_info.get("direction")
                if target_currency == base_currency:
                    pair_bias_direction = target_direction
                elif target_currency == quote_currency:
                    if target_direction == "bullish": pair_bias_direction = "bearish"
                    elif target_direction == "bearish": pair_bias_direction = "bullish"

        if pair_bias_direction is None:
            market_condition = directive_bias_info.get("market_condition")
            if market_condition in ["ranging", "neutral_or_mixed_signals", "neutral", "ranging_on_pair"]:
                return "ranging"
            if market_condition == "bullish_all" or \
               (isinstance(directive_bias_info.get("pairs"), list) and \
                pair in directive_bias_info.get("pairs", []) and "bullish" in market_condition):
                return "bullish"
            if market_condition == "bearish_all" or \
               (isinstance(directive_bias_info.get("pairs"), list) and \
                pair in directive_bias_info.get("pairs", []) and "bearish" in market_condition):
                return "bearish"

        return pair_bias_direction

    def coordinate_trades(
        self,
        trade_proposals: List[Dict[str, Any]],
        strategic_directive: Dict[str, Any],
        portfolio_status: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        print(f"TradeMetaAgent received {len(trade_proposals)} trade_proposals. Directive: {strategic_directive.get('key_narrative')}. Portfolio Status: {portfolio_status}")

        if not trade_proposals:
            print("TradeMetaAgent: No proposals to coordinate.")
            return []

        enriched_proposals = []
        for proposal in trade_proposals:
            pair = proposal.get("pair", "UnknownPair")
            proposal_side = proposal.get("side", "").lower()

            directive_pair_bias = self._get_pair_bias_from_directive(pair, strategic_directive)
            alignment_score = 0.5

            if directive_pair_bias == "bullish" and proposal_side == "buy":
                alignment_score = 1.0
            elif directive_pair_bias == "bearish" and proposal_side == "sell":
                alignment_score = 1.0
            elif directive_pair_bias == "ranging":
                alignment_score = 0.6
            elif directive_pair_bias and directive_pair_bias != "neutral":
                alignment_score = 0.1

            proposal["alignment_score"] = alignment_score
            proposal["directive_pair_bias"] = directive_pair_bias

            # --- Integration of RiskAssessmentGraph ---
            print(f"TradeMetaAgent: Invoking risk assessment for {proposal['pair']}...")
            risk_graph_input = {
                "current_trade_proposal": proposal.copy(),
                "strategic_directive": strategic_directive,
                "portfolio_context": portfolio_status
            }

            try:
                # The risk_assessment_workflow is the compiled graph from RiskAssessmentGraph
                # Its .run() method (or invoke on compiled graph) returns the final_risk_assessment_output directly (as designed in risk_assessment_graph.py)
                risk_assessment_output = self.risk_assessment_workflow.run(risk_graph_input)

                if risk_assessment_output is None:
                    print(f"TradeMetaAgent: Warning - Risk assessment for {proposal['pair']} returned None. Assigning default high risk.")
                    risk_assessment_output = {
                        "risk_score": 1.0,
                        "assessment_summary": "Risk assessment error or no output.",
                        "proceed_with_trade": False,
                        "recommended_modifications": {}
                    }
            except Exception as e:
                print(f"TradeMetaAgent: Error during risk assessment for {proposal['pair']}: {e}. Assigning default high risk.")
                risk_assessment_output = {
                    "risk_score": 1.0,
                    "assessment_summary": f"Exception during risk assessment: {e}",
                    "proceed_with_trade": False,
                    "recommended_modifications": {}
                }
            # --- End of RiskAssessmentGraph Integration ---

            proposal["risk_assessment"] = risk_assessment_output # This is now the dict from RiskManager

            enriched_proposals.append(proposal)
            risk_assessment_details = proposal.get("risk_assessment", {})
            print(f"TradeMetaAgent: Processed proposal for {pair} (Side: {proposal_side}, Sub-Agent Conf: {proposal.get('confidence_score',0):.2f}, Align: {alignment_score:.2f}, Risk Score: {risk_assessment_details.get('risk_score','N/A'):.2f}, Proceed: {risk_assessment_details.get('proceed_with_trade','N/A')}, Directive Bias: {directive_pair_bias})")

        def sort_key(p):
            risk_assessment = p.get("risk_assessment", {})
            risk_score = risk_assessment.get("risk_score", 1.0)
            proceed = risk_assessment.get("proceed_with_trade", False)

            if not proceed: # Heavily penalize trades not approved by risk manager
                return -1000

            return p.get("alignment_score", 0) + p.get("confidence_score", 0) + (1.0 - risk_score)

        # Filter out trades not recommended by risk assessment first
        # This is now handled by the sort_key giving a very low score.
        # We can also explicitly filter if preferred:
        # proceed_proposals = [p for p in enriched_proposals if p.get("risk_assessment", {}).get("proceed_with_trade", False)]

        min_alignment_threshold = 0.4
        # Proposals already have risk assessment; filter first by proceed_with_trade, then alignment
        candidate_proposals = [
            p for p in enriched_proposals
            if p.get("risk_assessment", {}).get("proceed_with_trade", False) and \
               p.get("alignment_score", 0) >= min_alignment_threshold
        ]

        if not candidate_proposals and enriched_proposals:
            # If no proposals meet both risk approval and alignment, check if any were at least risk-approved
            risk_approved_but_misaligned = [p for p in enriched_proposals if p.get("risk_assessment", {}).get("proceed_with_trade", False)]
            if risk_approved_but_misaligned:
                 print(f"TradeMetaAgent: No proposals met minimum alignment threshold of {min_alignment_threshold} (after risk approval). {len(risk_approved_but_misaligned)} proposal(s) were risk-approved but misaligned.")
            else:
                 print("TradeMetaAgent: No proposals were approved by risk assessment.")
            candidate_proposals = [] # Do not proceed with misaligned or non-risk-approved trades

        sorted_proposals = sorted(candidate_proposals, key=sort_key, reverse=True)

        if sorted_proposals:
            print(f"TradeMetaAgent: Sorted {len(sorted_proposals)} proposals. Top score: {sort_key(sorted_proposals[0]):.2f} for {sorted_proposals[0]['pair']}")
        else:
            print("TradeMetaAgent: No proposals available for final selection after filtering.")

        finalized_trades_for_approval = []
        max_trades_to_select = portfolio_status.get("max_concurrent_trades", 1)

        for selected_proposal in sorted_proposals[:max_trades_to_select]:
            current_proposal_score = sort_key(selected_proposal)
            # Adjust quality score threshold if needed, e.g., > 0 for any positively scored trade
            # A score of -1000 means proceed_with_trade was false.
            if current_proposal_score < 0: # Effectively checks if proceed_with_trade was false
                print(f"TradeMetaAgent: Proposal for {selected_proposal['pair']} with score {current_proposal_score:.2f} was not recommended by risk assessment or had critical issues. Skipping.")
                continue

            balance = portfolio_status.get("balance", 10000)
            risk_per_trade_percentage = portfolio_status.get("risk_per_trade_percentage", 0.01)
            amount_to_risk = balance * risk_per_trade_percentage

            stop_loss_price = selected_proposal.get("stop_loss")
            entry_price = selected_proposal.get("entry_price")

            # Refined mock entry price logic for sizing
            entry_price_for_sizing = entry_price
            if selected_proposal.get("type") == "market" and entry_price is None:
                print(f"TradeMetaAgent Warning: Market order for {selected_proposal['pair']} has no entry_price. Using mock current price for sizing.")
                entry_price_for_sizing = portfolio_status.get("mock_current_price", {}).get(selected_proposal['pair'])
                if entry_price_for_sizing is None: # Fallback if mock_current_price not available for the pair
                    print(f"TradeMetaAgent Error: No current price for {selected_proposal['pair']} for market order sizing. Skipping.")
                    continue
            elif entry_price is None: # Limit/Stop order without price (should not happen from sub-agent)
                 print(f"TradeMetaAgent Error: Non-market order for {selected_proposal['pair']} has no entry_price. Skipping.")
                 continue


            if stop_loss_price is None:
                print(f"TradeMetaAgent Error: Proposal for {selected_proposal['pair']} has no stop_loss_price. Cannot size. Skipping.")
                continue

            stop_loss_distance_pips = abs(entry_price_for_sizing - stop_loss_price) * (10000 if "JPY" not in selected_proposal["pair"].upper() else 100)

            if stop_loss_distance_pips <= 1e-5: # Check for zero or extremely small SL distance
                print(f"TradeMetaAgent Error: Stop loss distance is zero or too small for {selected_proposal['pair']}. SL: {stop_loss_price}, Entry: {entry_price_for_sizing}. Skipping.")
                continue

            value_per_pip_per_lot = 10.0
            if "JPY" in selected_proposal["pair"].upper():
                 value_per_pip_per_lot = 1000.0 / (100000.0 / (100 if "JPY" in selected_proposal["pair"].upper() else 1)) # More standard JPY pip value calc for $10/pip on std lot

            calculated_position_size = amount_to_risk / (stop_loss_distance_pips * value_per_pip_per_lot)
            calculated_position_size = max(0.01, round(calculated_position_size, 2))

            # Apply size factor from risk assessment
            size_factor = selected_proposal.get("risk_assessment", {}).get("recommended_modifications", {}).get("size_factor", 1.0)
            final_adjusted_size = round(calculated_position_size * size_factor, 2)
            final_adjusted_size = max(0.01, final_adjusted_size) # Ensure it doesn't go below min lot

            selected_proposal["calculated_position_size"] = final_adjusted_size

            risk_assessment_summary = selected_proposal.get("risk_assessment",{}).get('assessment_summary','N/A')
            selected_proposal["meta_rationale"] = (f"Selected (Overall Score: {current_proposal_score:.2f}). "
                                                  f"Align: {selected_proposal['alignment_score']:.2f}, "
                                                  f"Conf: {selected_proposal.get('confidence_score',0):.2f}. "
                                                  f"Risk: {risk_assessment_summary}. "
                                                  f"Sized to {final_adjusted_size} lots for {risk_per_trade_percentage*100:.1f}% risk. SL pips: {stop_loss_distance_pips:.1f}. Size factor: {size_factor:.2f}")

            finalized_trades_for_approval.append(selected_proposal)

        if finalized_trades_for_approval:
            print(f"TradeMetaAgent: Finalized {len(finalized_trades_for_approval)} trade(s) for approval.")
            for trade_idx, trade in enumerate(finalized_trades_for_approval):
                print(f"  Finalized Trade {trade_idx+1}: {trade['pair']} {trade['side']} Size: {trade['calculated_position_size']:.2f} lots. Rationale: {trade['meta_rationale']}")
        else:
            print("TradeMetaAgent: No trades were finalized for approval based on scoring, risk assessment, or sizing.")

        return finalized_trades_for_approval
