from typing import Any, Dict, List, Optional

# Placeholder for actual LLM
# class PlaceholderLLM:
#     def invoke(self, prompt: str) -> str:
#         return f"LLM mock response to: {prompt[:100]}..."

def create_safe_debator(llm: Any): # llm is passed but not used in this mock version
    """
    Creates a node function for the Conservative Risk Analyst.
    This analyst focuses on capital preservation and potential downsides.
    """

    def analyze_trade_risk(
        state: Dict[str, Any] # LangGraph state
    ) -> Dict[str, Any]: # Returns a dictionary to update the state
        """
        Analyzes a specific trade proposal from a conservative perspective.
        Expected in state:
        - current_trade_proposal: Dict[str, Any]
        - strategic_directive: Optional[Dict[str, Any]]
        - portfolio_context: Optional[Dict[str, Any]] (not used in this mock)
        """
        trade_proposal = state.get("current_trade_proposal")
        strategic_directive = state.get("strategic_directive", {})
        # portfolio_context = state.get("portfolio_context", {})

        if not trade_proposal:
            print("ConservativeRiskAnalyst: No trade proposal found in state.")
            return {"conservative_analysis_result": "Error: No trade proposal provided."}

        print(f"ConservativeRiskAnalyst received trade proposal for {trade_proposal.get('pair')}")

        # Mock analysis logic
        pair = trade_proposal.get('pair', 'N/A')
        stop_loss = trade_proposal.get('stop_loss', 'N/A')
        volatility_expectation = strategic_directive.get('volatility_expectation', 'unknown')
        confidence = trade_proposal.get('confidence_score', 0)

        analysis_string = (
            f"Conservative view on {pair}: The proposed stop-loss at {stop_loss} might be too tight, "
            f"especially given the market's expected volatility of '{volatility_expectation}'. "
            f"Confidence score of {confidence:.2f} is noted, but potential downside exists if key support levels are breached. "
            f"Consider a wider stop or waiting for more confirmation to ensure capital preservation."
        )

        print(f"ConservativeRiskAnalyst generated analysis: {analysis_string}")

        return {"conservative_analysis_output": analysis_string}

    return analyze_trade_risk
