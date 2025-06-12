# TradingAgents/tradingagents/forex_agents/__init__.py
from .day_trader_agent import DayTraderAgent
from .swing_trader_agent import SwingTraderAgent
from .scalper_agent import ScalperAgent
from .position_trader_agent import PositionTraderAgent
from .trend_trader_agent import TrendTraderAgent

__all__ = [
    "DayTraderAgent",
    "SwingTraderAgent",
    "ScalperAgent",
    "PositionTraderAgent",
    "TrendTraderAgent"
]
