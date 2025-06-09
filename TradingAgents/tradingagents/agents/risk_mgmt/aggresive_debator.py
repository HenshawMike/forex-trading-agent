from typing import Any, Dict, List, Optional

# Placeholder for actual LLM, assuming it's passed in and has an invoke method
# class PlaceholderLLM:
#     def invoke(self, prompt: str) -> str:
#         return f"LLM mock response to: {prompt[:100]}..."

def create_risky_debator(llm: Any): # llm is passed but not used in this mock version
    """
    Creates a node function for the Aggressive Risk Analyst.
    This analyst focuses on potential upsides and downplays risks.
    """

    def analyze_trade_risk(
        state: Dict[str, Any] # LangGraph state
    ) -> Dict[str, Any]: # Returns a dictionary to update the state
        """
        Analyzes a specific trade proposal from an aggressive perspective.
        Expected in state:
        - current_trade_proposal: Dict[str, Any]
        - strategic_directive: Optional[Dict[str, Any]]
        - portfolio_context: Optional[Dict[str, Any]] (not used in this mock)
        """
        trade_proposal = state.get("current_trade_proposal")
        strategic_directive = state.get("strategic_directive", {}) # Default to empty dict
        # portfolio_context = state.get("portfolio_context", {}) # Not used in this mock

        if not trade_proposal:
            print("AggressiveRiskAnalyst: No trade proposal found in state.")
            return {"aggressive_analysis_result": "Error: No trade proposal provided."}

        print(f"AggressiveRiskAnalyst received trade proposal for {trade_proposal.get('pair')}")

        # Mock analysis logic
        pair = trade_proposal.get('pair', 'N/A')
        confidence = trade_proposal.get('confidence_score', 0)
        directive_bias_info = strategic_directive.get('primary_bias', {})
        directive_direction = directive_bias_info.get('direction', 'neutral')

        # Example of incorporating parts of the directive into the rationale
        analysis_string = (
            f"Aggressive take on {pair}: This trade presents a significant reward potential. "
            f"The sub-agent's confidence of {confidence:.2f} is noted. "
            f"While risks exist, the current market {strategic_directive.get('volatility_expectation','conditions')} "
            f"and overall directive bias towards '{directive_direction}' suggest this calculated risk is acceptable for the potential upside. "
            f"Any downside seems limited if quick action is taken. Focus on the growth opportunity."
        )

        print(f"AggressiveRiskAnalyst generated analysis: {analysis_string}")

        # In a debate graph, this would update a specific key in the risk_debate_state
        # For now, let's assume it returns its analysis under a defined key
        return {"aggressive_analysis_output": analysis_string}

    return analyze_trade_risk
