import unittest
import datetime
import time # For generating timestamps
from typing import List, Dict, Any, Optional, Tuple

# Assuming the TradingAgents module is in the PYTHONPATH
from tradingagents.forex_agents.trend_trader_agent import TrendTraderAgent
from tradingagents.forex_utils.forex_states import ForexSubAgentTask, ForexTradeProposal
from tradingagents.broker_interface.base import BrokerInterface

# Mock BrokerInterface
class MockBroker(BrokerInterface):
    def __init__(self, test_case_name: str):
        self.test_case_name = test_case_name
        self.historical_data_override: Optional[List[Dict[str, Any]]] = None
        self.current_price_override: Optional[Dict[str, float]] = None

    def connect(self, credentials: Dict[str, Any]) -> bool:
        return True

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        return True

    def get_historical_data(self, symbol: str, timeframe_str: str, start_time_unix: float,
                              end_time_unix: Optional[float] = None, count: Optional[int] = None) -> List[Dict]:
        if self.historical_data_override is not None:
            return self.historical_data_override

        # Default historical data if not overridden by a specific test
        # Generate some generic data if needed, but tests should ideally provide it
        base_time = end_time_unix if end_time_unix else time.time()
        num_bars = count if count else 200 # Default to agent's num_bars_to_fetch

        data = []
        for i in range(num_bars):
            ts = base_time - (num_bars - 1 - i) * (24 * 60 * 60) # Assuming D1 for default generation
            price = 1.1000 + i * 0.0001 # Simple increasing price
            data.append({
                'timestamp': ts,
                'open': price,
                'high': price + 0.0005,
                'low': price - 0.0005,
                'close': price + 0.0001, # Ensure close price changes for TA
                'volume': 100 + i
            })
        return data


    def get_current_price(self, symbol: str) -> Optional[Dict]:
        if self.current_price_override is not None:
            return self.current_price_override
        return {'ask': 1.12000, 'bid': 1.11980} # Default if not set

    def get_account_info(self) -> Optional[Dict]:
        return {'balance': 10000.0, 'currency': 'USD'}

    def place_order(self, symbol: str, order_type: Any, side: Any, volume: float,
                      price: Optional[float] = None, stop_loss: Optional[float] = None,
                      take_profit: Optional[float] = None, time_in_force: Any = None,
                      magic_number: Optional[int] = 0, comment: Optional[str] = "") -> Dict:
        return {'order_id': 'mock_order_123', 'status': 'accepted'}

class TestTrendTraderAgent(unittest.TestCase):
    def setUp(self):
        self.mock_broker = MockBroker(self._testMethodName)
        self.agent = TrendTraderAgent(
            broker=self.mock_broker,
            agent_id="TestTrendAgent_1",
            # Using default params from TrendTraderAgent for most tests
            # timeframe="D1", ema_short_period=20, ema_long_period=50,
            # stop_loss_pips=200.0, take_profit_pips=400.0
        )
        self.test_currency_pair = "EURUSD" # Default test pair

    def _generate_historical_data(self, num_bars: int, base_price: float, trend: str = "neutral", timeframe_seconds: int = 24*60*60) -> List[Dict]:
        data = []
        current_price = base_price
        current_time = time.time() # Use current time as the end time for data generation

        for i in range(num_bars):
            ts = current_time - (num_bars - 1 - i) * timeframe_seconds
            o = current_price
            h = current_price + 0.0010 * (1 if "JPY" not in self.test_currency_pair else 0.1)
            l = current_price - 0.0010 * (1 if "JPY" not in self.test_currency_pair else 0.1)

            price_factor = 0.01 if "JPY" in self.test_currency_pair else 0.0001 # Pip factor for JPY pairs vs others

            price_factor = 0.01 if "JPY" in self.test_currency_pair else 0.0001

            if trend == "uptrend": # Aim for RSI in 50-69 range
                if i % 5 < 3: # 3 up days
                    c = current_price + price_factor * (3 + (i%2)) # Varying up moves
                else: # 2 down days
                    c = current_price - price_factor * (2 + (i%2)) # Varying down moves
                current_price = c
            elif trend == "downtrend": # Aim for RSI in 31-50 range
                if i % 5 < 3: # 3 down days
                    c = current_price - price_factor * (3 + (i%2))
                else: # 2 up days
                    c = current_price + price_factor * (2 + (i%2))
                current_price = c
            else: # neutral or choppy for HOLD signal - Aim for RSI ~50
                if i % 2 == 0:
                    c = current_price + price_factor * 4
                else:
                    c = current_price - price_factor * 4
                current_price = c

            # Basic ohlc based on c
            o = current_price - (price_factor * 2 * (1 if i%2==0 else -1)) # open slightly different from prev close logic
            h = max(o, c) + price_factor * 3
            l = min(o, c) - price_factor * 3
            # Ensure close is within high/low
            c = max(l + price_factor * 0.5, min(c, h - price_factor * 0.5))


            data.append({
                'timestamp': ts, 'open': o, 'high': h, 'low': l, 'close': c, 'volume': 100 + i
            })
        return data

    def test_initialization(self):
        self.assertEqual(self.agent.agent_id, "TestTrendAgent_1")
        self.assertEqual(self.agent.timeframe, "D1")
        self.assertEqual(self.agent.ema_short_period, 20)
        self.assertEqual(self.agent.ema_long_period, 50)
        self.assertEqual(self.agent.stop_loss_pips, 200.0)
        self.assertEqual(self.agent.take_profit_pips, 400.0)
        self.assertTrue(self.agent.agent_id.startswith("TestTrendAgent"))

    def test_process_task_hold_signal_no_clear_trend(self):
        # Data where EMAs would be close or crossing (choppy price action)
        # For D1, 50 bars should be enough to calculate EMAs
        # RSI around 50
        historical_data = self._generate_historical_data(num_bars=100, base_price=1.1000, trend="neutral")
        # To make RSI neutral, ensure close prices oscillate
        for i in range(len(historical_data)):
            if i > 0 and i % 5 == 0 : # make some small ups and downs
                 historical_data[i]['close'] = historical_data[i-1]['close'] + (0.0001 * (-1 if i % 10 == 0 else 1))

        self.mock_broker.historical_data_override = historical_data

        task = ForexSubAgentTask(task_id="task_hold_1", currency_pair=self.test_currency_pair)
        state = {
            "current_trend_trader_task": task,
            "current_simulated_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        result = self.agent.process_task(state)
        proposal = result.get("trend_trader_proposal")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['signal'], "HOLD")
        self.assertIsNone(proposal['entry_price'])
        self.assertIsNone(proposal['stop_loss'])
        self.assertIsNone(proposal['take_profit'])
        self.assertIn("Trend trading conditions for BUY or SELL not clearly met", proposal['rationale'])

    def test_process_task_buy_signal_uptrend(self):
        self.test_currency_pair = "EURUSD"
        historical_data = self._generate_historical_data(num_bars=100, base_price=1.0800, trend="uptrend") # Start lower, trend up
        self.mock_broker.historical_data_override = historical_data
        self.mock_broker.current_price_override = {'ask': 1.10000, 'bid': 1.09980}

        task = ForexSubAgentTask(task_id="task_buy_1", currency_pair=self.test_currency_pair)
        state = {
            "current_trend_trader_task": task,
            "current_simulated_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        result = self.agent.process_task(state)
        proposal: ForexTradeProposal = result.get("trend_trader_proposal")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['signal'], "BUY")
        self.assertEqual(proposal['currency_pair'], "EURUSD")
        self.assertEqual(proposal['entry_price'], 1.10000)

        # SL/TP for EURUSD (pip = 0.0001)
        # SL = entry - (sl_pips * pip_value) = 1.10000 - (200.0 * 0.0001) = 1.10000 - 0.0200 = 1.08000
        # TP = entry + (tp_pips * pip_value) = 1.10000 + (400.0 * 0.0001) = 1.10000 + 0.0400 = 1.14000
        self.assertAlmostEqual(proposal['stop_loss'], 1.08000, places=5)
        self.assertAlmostEqual(proposal['take_profit'], 1.14000, places=5)
        self.assertTrue(proposal['rationale'].startswith("TrendTraderAgent: Trend Strategy"))
        self.assertIn("BUY signal: Trend bullish", proposal['rationale'])


    def test_process_task_sell_signal_downtrend(self):
        self.test_currency_pair = "USDJPY"
        # Adjust agent for JPY pair SL/TP calculation if necessary, or ensure mock broker handles it
        # For this test, we assume the agent's _calculate_pip_value_and_precision works.
        historical_data = self._generate_historical_data(num_bars=100, base_price=132.50, trend="downtrend") # Start higher, trend down
        self.mock_broker.historical_data_override = historical_data
        self.mock_broker.current_price_override = {'ask': 130.500, 'bid': 130.480}

        task = ForexSubAgentTask(task_id="task_sell_1", currency_pair=self.test_currency_pair)
        state = {
            "current_trend_trader_task": task,
            "current_simulated_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        result = self.agent.process_task(state)
        proposal: ForexTradeProposal = result.get("trend_trader_proposal")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['signal'], "SELL")
        self.assertEqual(proposal['currency_pair'], "USDJPY")
        self.assertEqual(proposal['entry_price'], 130.480)

        # SL/TP for USDJPY (pip = 0.01)
        # SL = entry + (sl_pips * pip_value) = 130.480 + (200.0 * 0.01) = 130.480 + 2.00 = 132.480
        # TP = entry - (tp_pips * pip_value) = 130.480 - (400.0 * 0.01) = 130.480 - 4.00 = 126.480
        self.assertAlmostEqual(proposal['stop_loss'], 132.480, places=3)
        self.assertAlmostEqual(proposal['take_profit'], 126.480, places=3)
        self.assertTrue(proposal['rationale'].startswith("TrendTraderAgent: Trend Strategy"))
        self.assertIn("SELL signal: Trend bearish", proposal['rationale'])

    def test_process_task_insufficient_data(self):
        # EMA long period is 50 by default. Provide fewer bars.
        historical_data = self._generate_historical_data(num_bars=40, base_price=1.1000, trend="neutral")
        self.mock_broker.historical_data_override = historical_data

        task = ForexSubAgentTask(task_id="task_insufficient_1", currency_pair=self.test_currency_pair)
        state = {
            "current_trend_trader_task": task,
            "current_simulated_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

        result = self.agent.process_task(state)
        proposal: ForexTradeProposal = result.get("trend_trader_proposal")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['signal'], "HOLD") # Should default to HOLD
        self.assertIn("Insufficient data for TA", proposal['supporting_data'].get("ta_calculation_info", ""))
        self.assertIn("Not all indicators available", proposal['rationale'])


    def test_process_task_no_task(self):
        state = {
             "current_simulated_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
             # Missing "current_trend_trader_task"
        }
        result = self.agent.process_task(state)
        proposal: ForexTradeProposal = result.get("trend_trader_proposal")

        self.assertIsNotNone(proposal)
        self.assertEqual(proposal['signal'], "HOLD")
        self.assertEqual(proposal['source_agent_type'], "TrendTraderAgent") # Error proposal should still identify source
        self.assertTrue(proposal['proposal_id'].startswith("prop_trend_err_"))
        self.assertIn("Task not found in state", proposal['rationale'])
        self.assertIsNone(proposal['entry_price'])


if __name__ == '__main__':
    unittest.main()
