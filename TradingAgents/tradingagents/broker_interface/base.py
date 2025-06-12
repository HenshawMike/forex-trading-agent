from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any

# Forward declare or import specific TypedDicts if they are used as return types here.
# For now, using Any or more generic types for simplicity in this placeholder.
# from tradingagents.forex_utils.forex_states import PriceTick, Candlestick, AccountInfo, Position
from tradingagents.forex_utils.forex_states import OrderType, OrderSide, TimeInForce, FillPolicy, OrderResponse # Updated imports

class BrokerInterface(ABC):
    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        pass
    @abstractmethod
    def disconnect(self) -> None:
        pass
    @abstractmethod
    def is_connected(self) -> bool:
        pass
    @abstractmethod
    def get_current_price(self, symbol: str) -> Optional[Dict]: # Placeholder Dict, ideally PriceTick
        pass
    @abstractmethod
    def get_historical_data(self, symbol: str, timeframe_str: str, start_time_unix: float,
                              end_time_unix: Optional[float] = None, count: Optional[int] = None) -> List[Dict]: # Placeholder List[Dict], ideally List[Candlestick]
        pass
    @abstractmethod
    def get_account_info(self) -> Optional[Dict]: # Placeholder Dict, ideally AccountInfo
        pass
    @abstractmethod
    def place_order(self, symbol: str, order_type: OrderType, side: OrderSide, volume: float,
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None, time_in_force: Optional[TimeInForce] = None,
                      fill_policy: Optional[FillPolicy] = None, # Added fill_policy
                      magic_number: Optional[int] = 0, comment: Optional[str] = "") -> OrderResponse: # Return type changed
        pass
    # Add other abstract methods as designed previously if needed by agents directly
    # For now, these are the most likely to be used by a sub-agent.
