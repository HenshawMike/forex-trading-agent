# Assuming your existing TradingAgentsGraph is also here, or other graph setups
# from .original_trading_graph import TradingAgentsGraph # If you have one
from .forex_trading_graph import ForexTradingGraph, ForexGraphState

# Also re-exporting other potentially useful items from the original graph module if they exist
# For example, if you have these in your current __init__.py for the existing graph:
# from .conditional_logic import ConditionalLogic
# from .propagation import Propagator
# from .reflection import Reflector
# from .setup import GraphSetup
# from .signal_processing import SignalProcessor

# If the original TradingAgentsGraph is still relevant and distinct:
# __all__ = ["ForexTradingGraph", "ForexGraphState", "TradingAgentsGraph"]
# Else, if ForexTradingGraph is the main one now:
__all__ = ["ForexTradingGraph", "ForexGraphState"]
