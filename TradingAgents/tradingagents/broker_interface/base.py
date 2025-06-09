from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union
from datetime import datetime

class BrokerInterface(ABC):
    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        '''Connects to the broker.'''
        pass

    @abstractmethod
    def disconnect(self) -> None:
        '''Disconnects from the broker.'''
        pass

    @abstractmethod
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        '''Retrieves account information (balance, equity, margin, etc.).'''
        pass

    @abstractmethod
    def get_current_price(self, pair: str) -> Optional[Dict[str, float]]:
        '''Retrieves the current bid/ask price for a currency pair.'''
        # e.g., {"bid": 1.0800, "ask": 1.0802}
        pass

    @abstractmethod
    def get_historical_data(
        self,
        pair: str,
        timeframe: str, # e.g., "M1", "H1", "D1"
        start_date: Optional[Union[datetime, str]] = None, # Can be datetime object or ISO format string
        end_date: Optional[Union[datetime, str]] = None,   # Can be datetime object or ISO format string
        count: Optional[int] = None # Number of candles from end_date, or from now if end_date is None
    ) -> Optional[List[Dict[str, Any]]]: # e.g., pandas DataFrame or list of dicts
        '''Retrieves historical OHLCV data.'''
        # List of dicts: [{"time": datetime, "open": ..., "high": ..., "low": ..., "close": ..., "volume": ...}]
        pass

    @abstractmethod
    def place_order(self, order_details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        '''
        Places an order.
        order_details: {
            "pair": str, "type": str ("market", "limit", "stop"),
            "side": str ("buy", "sell"), "size": float (lots),
            "price": Optional[float] (for limit/stop),
            "sl": Optional[float] (stop_loss price),
            "tp": Optional[float] (take_profit price),
            "magic_number": Optional[int], "comment": Optional[str]
        }
        Returns: {"success": bool, "order_id": Optional[str], "message": Optional[str]}
        '''
        pass

    @abstractmethod
    def modify_order(self, order_id: str, new_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        '''
        Modifies an existing pending order or SL/TP of an open position.
        new_params: {"sl": Optional[float], "tp": Optional[float], "price": Optional[float] (for pending)}
        Returns: {"success": bool, "message": Optional[str]}
        '''
        pass

    @abstractmethod
    def close_order(self, order_id: str, size_to_close: Optional[float] = None) -> Optional[Dict[str, Any]]:
        '''
        Closes an open position.
        size_to_close: Optional. If None, close the entire position. Otherwise, close specified lots.
        Returns: {"success": bool, "message": Optional[str]}
        '''
        pass

    @abstractmethod
    def get_open_positions(self) -> Optional[List[Dict[str, Any]]]:
        '''Retrieves a list of all open positions.'''
        # List of dicts, each like: {"id": str, "pair": str, "type": str, "side": str, "size": float, "open_price": float, "sl": float, "tp": float, "profit": float, ...}
        pass

    @abstractmethod
    def get_pending_orders(self) -> Optional[List[Dict[str, Any]]]:
        '''Retrieves a list of all pending orders.'''
        # Similar structure to open_positions but for pending orders
        pass
