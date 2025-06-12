from typing import TypedDict, List, Optional, Dict
from enum import Enum

class ForexMarketContext(TypedDict):
    currency_pair: str
    timestamp: str  # ISO format timestamp of the context
    market_regime: Optional[str]  # e.g., "Trending-Up", "Trending-Down", "Ranging-Volatile", "Ranging-Quiet", "Breakout-Anticipated"
    relevant_economic_events: Optional[List[Dict]] # List of upcoming events, e.g., {"time": "2023-10-27T12:30:00Z", "event": "US CPI", "impact": "High"}
    master_agent_directives: Optional[Dict] # e.g., {"max_risk_per_trade_pct": 0.01, "preferred_direction": "BUY"}

class ForexSubAgentTask(TypedDict):
    task_id: str
    currency_pair: str
    timeframes_to_analyze: List[str] # e.g., ["M5", "M15"] for Scalper
    market_context_snapshot: ForexMarketContext # Snapshot of context at time of tasking

class ForexTradeProposal(TypedDict):
    proposal_id: str
    source_agent_type: str  # "Scalper", "DayTrader", "SwingTrader", "PositionTrader"
    currency_pair: str
    timestamp: str  # Time of proposal generation, ISO format
    signal: str  # "BUY", "SELL", "HOLD", "STRONG_BUY", "STRONG_SELL"
    entry_price: Optional[float]
    entry_price_range_upper: Optional[float] # For zone entries
    entry_price_range_lower: Optional[float] # For zone entries
    stop_loss: Optional[float]
    take_profit: Optional[float]
    take_profit_2: Optional[float] # Optional secondary TP
    confidence_score: float  # 0.0 to 1.0
    rationale: str  # Brief text from sub-agent
    sub_agent_risk_level: str # "Low", "Medium", "High"
    supporting_data: Optional[Dict] # e.g., {"RSI_14": 65, "MACD_signal_cross": "bullish"}

class AggregatedForexProposals(TypedDict):
    aggregation_id: str
    currency_pair: str
    timestamp: str # Time of aggregation, ISO format
    market_context_at_aggregation: ForexMarketContext # The overall context used for this round
    proposals: List[ForexTradeProposal]

class ForexFinalDecision(TypedDict):
    decision_id: str
    currency_pair: str
    timestamp: str # Time of decision, ISO format
    based_on_aggregation_id: str # ID of AggregatedForexProposals
    action: str  # "EXECUTE_BUY", "EXECUTE_SELL", "HOLD_POSITION", "STAND_ASIDE", "REASSESS_LATER", "EXECUTE_BUY_PENDING_APPROVAL"
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size: Optional[float] # e.g., in lots
    risk_percentage_of_capital: Optional[float] # if position size is derived from this
    meta_rationale: str  # Meta-Agent's justification for the decision
    meta_confidence_score: Optional[float] # Meta-Agent's confidence in this final decision
    meta_assessed_risk_level: Optional[str] # "Low", "Medium", "High"
    contributing_proposals_ids: Optional[List[str]] # IDs of sub-agent proposals that heavily influenced the decision
    # Fields for user approval lifecycle
    status: Optional[str] # e.g., "STATE_PENDING_USER_APPROVAL", "STATE_USER_APPROVED"
    pending_approval_timestamp: Optional[str] # ISO format
    approval_expiry_timestamp: Optional[str] # ISO format
    user_action_timestamp: Optional[str] # ISO format
    acted_by_user_id: Optional[str]

# (Keep existing TypedDict definitions above this)

class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    # Add other common types like STOP_LIMIT if needed by broker interfaces
    # e.g., BUY_STOP_LIMIT = "BUY_STOP_LIMIT"
    # e.g., SELL_STOP_LIMIT = "SELL_STOP_LIMIT"

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"

class TimeInForce(Enum):
    GTC = "GTC"  # Good 'Til Canceled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill
    DAY = "DAY"  # Good for the day (session)
    # GTD = "GTD" # Good 'Til Date/Time (if needed)

class Candlestick(TypedDict):
    timestamp: float  # Unix timestamp (seconds)
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float]
    bid_close: Optional[float] # Optional bid close price for the candlestick period
    ask_close: Optional[float] # Optional ask close price for the candlestick period

class Tick(TypedDict):
    symbol: str # Symbol/currency pair
    timestamp: float # Unix timestamp (seconds), can include milliseconds
    bid: float
    ask: float
    last: Optional[float] # Optional last traded price if available
    volume: Optional[float] # Optional volume for this tick

class AccountInfo(TypedDict):
    account_id: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: Optional[float]  # Can be float('inf') or a percentage
    currency: str

class OrderResponse(TypedDict):
    order_id: str
    status: str  # e.g., "PENDING", "FILLED", "REJECTED", "CANCELLED", "MODIFIED", "CLOSED"
    symbol: Optional[str]
    side: Optional[OrderSide]
    type: Optional[OrderType]
    volume: Optional[float]
    price: Optional[float] # Requested price for pending, fill price for market/filled
    timestamp: float  # Unix timestamp of the response/event
    error_message: Optional[str]
    position_id: Optional[str] # Associated position ID if order resulted in/affected a position

class Position(TypedDict):
    position_id: str
    symbol: str
    side: OrderSide  # BUY or SELL
    volume: float  # In lots
    entry_price: float
    current_price: float # Last valuation price
    profit_loss: float # Current unrealized P/L in account currency (excluding commission on open)
    stop_loss: Optional[float]
    take_profit: Optional[float]
    open_time: float  # Unix timestamp
    magic_number: Optional[int]
    comment: Optional[str]
