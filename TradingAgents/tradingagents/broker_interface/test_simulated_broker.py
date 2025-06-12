import unittest
from unittest.mock import patch # MODIFIED: Import patch correctly
import time
import random
from typing import List, Dict, Any, Optional

from TradingAgents.tradingagents.broker_interface.simulated_broker import SimulatedBroker
from TradingAgents.tradingagents.forex_utils.forex_states import Candlestick, OrderType, OrderSide, Tick as PriceTick # Renamed Tick to PriceTick for this test context if needed, or ensure Tick is used if that was the final name. Assuming Tick is the final one.

# Helper to create a basic Candlestick dictionary
def create_candlestick(timestamp: float, o: float, h: float, l: float, c: float, vol: Optional[float] = 100, bid_c: Optional[float] = None, ask_c: Optional[float] = None) -> Candlestick:
    return {
        "timestamp": timestamp, "open": o, "high": h, "low": l, "close": c, "volume": vol,
        "bid_close": bid_c if bid_c is not None else (c - 0.0001 if c else None), # Ensure bid_c and ask_c are floats or None
        "ask_close": ask_c if ask_c is not None else (c + 0.0001 if c else None)
    }

class TestSimulatedBrokerSlippageAndHistoricalData(unittest.TestCase):

    def setUp(self):
        self.broker = SimulatedBroker(initial_capital=10000.0)
        self.broker.connect({}) # Connect broker
        self.test_symbol = "EURUSD"
        self.start_time = time.time()

        # Default symbol info for EURUSD for tests
        # Using a direct dictionary update for symbol_info_cache for test setup simplicity
        self.broker.symbol_info_cache = {} # Clear cache first
        self.broker.symbol_info_cache[self.test_symbol.upper()] = {
            "base_currency": "EUR", "quote_currency": "USD",
            "price_precision": 5, "point_size": 0.00001,
            "pip_definition": 0.0001, "contract_size_units": 100000.0
        }
        # Ensure a default for USDJPY if used in currency conversion tests implicitly
        self.broker.symbol_info_cache["USDJPY"] = {
             "base_currency": "USD", "quote_currency": "JPY",
            "price_precision": 3, "point_size": 0.001,
            "pip_definition": 0.01, "contract_size_units": 100000.0
        }


    # --- Tests for Historical Bid/Ask Data Handling ---

    def test_load_test_data_with_historical_bid_ask(self):
        ts1 = self.start_time
        data_seq = [
            create_candlestick(ts1, 1.10000, 1.10050, 1.09950, 1.10020, bid_c=1.10015, ask_c=1.10025),
            create_candlestick(ts1 + 3600, 1.10020, 1.10100, 1.10000, 1.10080, bid_c=1.10075, ask_c=1.10085)
        ]
        self.broker.load_test_data(self.test_symbol, data_seq)
        loaded_data = self.broker.test_data_store.get(self.test_symbol.upper())
        self.assertIsNotNone(loaded_data)
        self.assertEqual(len(loaded_data), 2)
        self.assertEqual(loaded_data[0]['bid_close'], 1.10015)
        self.assertEqual(loaded_data[0]['ask_close'], 1.10025)

    def test_load_test_data_validation(self):
        # Bar with non-positive price
        data_seq_invalid_price = [create_candlestick(self.start_time, 0, 1.1, 1.0, 1.05)] # Open is 0
        self.broker.load_test_data("INV1", data_seq_invalid_price)
        self.assertEqual(len(self.broker.test_data_store.get("INV1", [])), 0)

        # Bar with bid > ask
        data_seq_bid_ask_inv = [create_candlestick(self.start_time, 1.1, 1.11, 1.09, 1.10, bid_c=1.1005, ask_c=1.1000)]
        self.broker.load_test_data("INV2", data_seq_bid_ask_inv) # Should still load but log warning
        loaded_inv2 = self.broker.test_data_store.get("INV2", [])
        self.assertEqual(len(loaded_inv2), 1)
        self.assertEqual(loaded_inv2[0]['bid_close'], 1.1005)
        self.assertEqual(loaded_inv2[0]['ask_close'], 1.1000)


    def test_get_spread_in_price_terms_with_historical_data(self):
        # Case 1: Valid historical bid/ask available
        bar_with_hist_spread = create_candlestick(self.start_time, 1.1, 1.1, 1.1, 1.1, bid_c=1.09980, ask_c=1.10020) # 4 pips spread (0.00040)
        self.broker.current_market_data = {self.test_symbol: bar_with_hist_spread}
        spread = self.broker._get_spread_in_price_terms(self.test_symbol)
        self.assertAlmostEqual(spread, 0.00040, places=5)

        # Case 2: No historical bid/ask in bar, fallback to default_spread_pips
        bar_no_hist_spread = create_candlestick(self.start_time, 1.1, 1.1, 1.1, 1.1, bid_c=None, ask_c=None)
        self.broker.current_market_data = {self.test_symbol: bar_no_hist_spread}
        self.broker.default_spread_pips[self.test_symbol.upper()] = 2.0 # 2 pips
        # Ensure symbol_info_cache is used by _get_symbol_info
        symbol_info = self.broker._get_symbol_info(self.test_symbol)
        self.assertIsNotNone(symbol_info)
        expected_spread_default = 2.0 * symbol_info['pip_definition'] # 2 * 0.0001 = 0.00020
        spread = self.broker._get_spread_in_price_terms(self.test_symbol)
        self.assertAlmostEqual(spread, expected_spread_default, places=5)

    def test_get_current_price_with_historical_data(self):
        bar_with_hist_prices = create_candlestick(self.start_time, 1.1, 1.1, 1.1, 1.10000, bid_c=1.09980, ask_c=1.10020)
        self.broker.current_market_data = {self.test_symbol: bar_with_hist_prices}
        self.broker.update_current_time(self.start_time)

        price_tick = self.broker.get_current_price(self.test_symbol)
        self.assertIsNotNone(price_tick)
        self.assertEqual(price_tick['bid'], 1.09980)
        self.assertEqual(price_tick['ask'], 1.10020)
        self.assertEqual(price_tick['last'], 1.10000) # 'last' in Tick should be 'close' of bar if hist bid/ask used

    def test_market_order_fill_with_historical_bid_ask(self):
        bar_data = create_candlestick(self.start_time, 1.10000, 1.10050, 1.09950, 1.10020, bid_c=1.10010, ask_c=1.10030)
        self.broker.current_market_data = {self.test_symbol: bar_data}
        self.broker.update_current_time(self.start_time)
        self.broker.base_slippage_pips = 0
        self.broker.volume_slippage_factor_pips_per_million = 0

        with patch('random.uniform', return_value=1.0): # MODIFIED: Use patch
            response_buy = self.broker.place_order(self.test_symbol, OrderType.MARKET, OrderSide.BUY, 0.01)
        self.assertEqual(response_buy['status'], "FILLED")
        self.assertAlmostEqual(response_buy['price'], 1.10030, places=5)

        with patch('random.uniform', return_value=1.0): # MODIFIED: Use patch
            response_sell = self.broker.place_order(self.test_symbol, OrderType.MARKET, OrderSide.SELL, 0.01)
        self.assertEqual(response_sell['status'], "FILLED")
        self.assertAlmostEqual(response_sell['price'], 1.10010, places=5)

    # --- Tests for Slippage Model ---
    def test_market_order_slippage_base_only(self):
        self.broker.base_slippage_pips = 1.0
        self.broker.volume_slippage_factor_pips_per_million = 0.0
        symbol_info = self.broker._get_symbol_info(self.test_symbol)
        pip_def = symbol_info['pip_definition']

        bar_close = 1.10000
        bar_data = create_candlestick(self.start_time, bar_close, bar_close+0.0001, bar_close-0.0001, bar_close, bid_c=None, ask_c=None)
        self.broker.current_market_data = {self.test_symbol: bar_data}
        self.broker.update_current_time(self.start_time)
        self.broker.default_spread_pips[self.test_symbol.upper()] = 1.0 # 1 pip spread

        # pip_def = 0.0001
        # bar_close (c in create_candlestick) = 1.10000
        # hist_ask_close from create_candlestick default = c + 0.0001 = 1.10000 + 0.0001 = 1.10010
        # This hist_ask_close becomes fill_price_base_for_slippage in broker.
        fill_price_base_for_slippage = 1.10010

        # base_slippage_pips = 1.0, random factor for slippage pips = 1.0 -> final_slippage_pips = 1.0
        # slippage_amount_in_price_terms = 1.0 * pip_def = 0.00010
        slippage_amount_in_price_terms = 1.0 * pip_def
        expected_fill_buy = fill_price_base_for_slippage + slippage_amount_in_price_terms # 1.10010 + 0.00010 = 1.10020

        with patch('random.uniform') as mock_rand_uniform:
            mock_rand_uniform.return_value = 1.0
            response_buy = self.broker.place_order(self.test_symbol, OrderType.MARKET, OrderSide.BUY, 0.01)

        self.assertEqual(response_buy['status'], "FILLED")
        self.assertAlmostEqual(response_buy['price'], expected_fill_buy, places=5) # Expected 1.10020


    def test_market_order_slippage_volume_component(self):
        self.broker.base_slippage_pips = 0.5
        self.broker.volume_slippage_factor_pips_per_million = 0.1
        symbol_info = self.broker._get_symbol_info(self.test_symbol)
        contract_size = symbol_info['contract_size_units']
        pip_def = symbol_info['pip_definition']

        volume_lots = 0.5
        volume_in_units = volume_lots * contract_size
        volume_in_millions = volume_in_units / 1_000_000.0

        expected_dynamic_slippage_pips = volume_in_millions * 0.1
        expected_total_slippage_pips_before_random = 0.5 + expected_dynamic_slippage_pips

        bar_close = 1.20000
        bar_data = create_candlestick(self.start_time, bar_close, bar_close+0.0001, bar_close-0.0001, bar_close, bid_c=None, ask_c=None)
        self.broker.current_market_data = {self.test_symbol: bar_data}
        self.broker.update_current_time(self.start_time)
        self.broker.default_spread_pips[self.test_symbol.upper()] = 0.8
        # bar_close (c in create_candlestick) = 1.20000
        # hist_bid_close from create_candlestick default = c - 0.0001 = 1.20000 - 0.0001 = 1.19990
        # This hist_bid_close becomes fill_price_base_for_slippage in broker.
        fill_price_base_for_slippage = 1.19990

        # expected_total_slippage_pips_before_random = 0.505 pips. Random factor for slippage pips = 1.0
        # slippage_amount_in_price_terms = 0.505 * pip_def = 0.0000505
        slippage_amount_in_price_terms = expected_total_slippage_pips_before_random * pip_def
        expected_fill_sell = fill_price_base_for_slippage - slippage_amount_in_price_terms # 1.19990 - 0.0000505 = 1.1998495

        with patch('random.uniform') as mock_rand_uniform:
            mock_rand_uniform.return_value = 1.0
            response_sell = self.broker.place_order(self.test_symbol, OrderType.MARKET, OrderSide.SELL, volume_lots)

        self.assertEqual(response_sell['status'], "FILLED")
        self.assertAlmostEqual(response_sell['price'], round(expected_fill_sell, 5), places=5) # Expected 1.19985


    def test_stop_order_slippage(self):
        self.broker.base_slippage_pips = 1.0
        self.broker.volume_slippage_factor_pips_per_million = 0.05
        symbol_info = self.broker._get_symbol_info(self.test_symbol)
        pip_def = symbol_info['pip_definition']
        contract_size = symbol_info['contract_size_units']

        stop_price = 1.10000
        order_volume = 0.1
        expected_dynamic_slippage = (order_volume * contract_size / 1_000_000.0) * 0.05
        expected_total_slippage_pips_before_random = 1.0 + expected_dynamic_slippage

        trigger_bar = create_candlestick(self.start_time, stop_price, stop_price + 0.00100, stop_price - 0.00010, stop_price + 0.00050, bid_c=None, ask_c=None)
        self.broker.current_market_data = {self.test_symbol: trigger_bar}
        self.broker.update_current_time(self.start_time)
        self.broker.default_spread_pips[self.test_symbol.upper()] = 1.2
        spread_for_fill = 1.2 * pip_def

        order_id = "test_buy_stop_order"
        self.broker.pending_orders[order_id] = {
            "order_id": order_id, "status": "PENDING", "symbol": self.test_symbol,
            "side": OrderSide.BUY, "type": OrderType.STOP, "volume": order_volume,
            "price": stop_price, "timestamp": self.start_time -100,
            "stop_loss": None, "take_profit": None
        }

        # trigger_bar close 'c' = stop_price (1.10000) + 0.00050 = 1.10050
        # hist_ask_close from create_candlestick default = c + 0.0001 = 1.10050 + 0.0001 = 1.10060
        # This hist_ask_close becomes base_price_for_execution for BUY STOP in broker.
        base_price_for_execution = 1.10060

        # expected_total_slippage_pips_before_random = 1.0005 pips. Random factor for slippage pips = 1.0
        # slippage_for_stop_order_price_terms = 1.0005 * pip_def = 0.00010005
        slippage_for_stop_order_price_terms = expected_total_slippage_pips_before_random * pip_def
        expected_fill_price = base_price_for_execution + slippage_for_stop_order_price_terms # 1.10060 + 0.00010005 = 1.10070005

        with patch('random.uniform') as mock_rand_uniform:
            mock_rand_uniform.return_value = 1.0
            self.broker.process_pending_orders()

        self.assertNotIn(order_id, self.broker.pending_orders)
        filled_order_event = next((e for e in self.broker.trade_history if e.get("original_order_id") == order_id), None)
        self.assertIsNotNone(filled_order_event)
        self.assertEqual(filled_order_event['type'], OrderType.STOP.value)

        self.assertAlmostEqual(filled_order_event['fill_price'], round(expected_fill_price, 5), places=5) # Expected 1.10070

    def test_limit_order_no_dynamic_slippage(self):
        self.broker.base_slippage_pips = 10.0
        self.broker.volume_slippage_factor_pips_per_million = 1.0
        symbol_info = self.broker._get_symbol_info(self.test_symbol)
        pip_def = symbol_info['pip_definition']

        limit_price = 1.10000

        trigger_bar = create_candlestick(self.start_time, limit_price, limit_price + 0.00050, limit_price - 0.00050, limit_price - 0.00020, bid_c=None, ask_c=None)
        self.broker.current_market_data = {self.test_symbol: trigger_bar}
        self.broker.update_current_time(self.start_time)
        self.broker.default_spread_pips[self.test_symbol.upper()] = 1.0
        spread_for_fill = 1.0 * pip_def

        order_id = "test_buy_limit_order"
        self.broker.pending_orders[order_id] = {
            "order_id": order_id, "status": "PENDING", "symbol": self.test_symbol,
            "side": OrderSide.BUY, "type": OrderType.LIMIT, "volume": 0.01,
            "price": limit_price, "timestamp": self.start_time -100,
            "stop_loss": None, "take_profit": None
        }

        # Corrected expected_fill_price calculation based on how create_candlestick and broker logic interact
        # bar_close ('c') for trigger_bar is limit_price - 0.00020 = 1.09980
        # hist_ask_close from create_candlestick default is c + 0.0001 = 1.09980 + 0.0001 = 1.09990
        # This hist_ask_close (1.09990) will be used as base_price_for_execution.
        # Fill price for BUY LIMIT is min(order_price, base_price_for_execution)
        expected_fill_price = min(limit_price, 1.09990) # min(1.10000, 1.09990) = 1.09990

        self.broker.process_pending_orders()
        self.assertNotIn(order_id, self.broker.pending_orders)
        filled_order_event = next((e for e in self.broker.trade_history if e.get("original_order_id") == order_id), None)
        self.assertIsNotNone(filled_order_event)
        self.assertEqual(filled_order_event['type'], OrderType.LIMIT.value)
        self.assertAlmostEqual(filled_order_event['fill_price'], expected_fill_price, places=5) # Changed to expected_fill_price


if __name__ == '__main__':
    # Adjust sys.path if running the script directly and TradingAgents is not in PYTHONPATH
    import os
    import sys
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    # Assumes this test script is in TradingAgents/tradingagents/broker_interface/
    # Project root is ../../ part
    project_root_path = os.path.abspath(os.path.join(current_script_path, '..', '..', '..'))
    if project_root_path not in sys.path:
        sys.path.insert(0, project_root_path)
        # print(f"Adjusted sys.path for test_simulated_broker.py to include {project_root_path}")
    unittest.main()
