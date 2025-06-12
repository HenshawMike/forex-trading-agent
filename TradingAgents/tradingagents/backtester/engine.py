import datetime
import time # For simulating delays if needed
import random # For dummy data generation in __main__ (will be removed, but import kept for now if other parts need it)
from typing import List, Dict, Any, Optional, Union

import pandas as pd
import quantstats # Ensure this is installed

from TradingAgents.tradingagents.broker_interface.simulated_broker import SimulatedBroker
from TradingAgents.tradingagents.forex_utils.forex_states import Candlestick, AccountInfo, ForexFinalDecision, OrderType, OrderSide

# Placeholder for the actual strategy type
# from TradingAgents.tradingagents.graph.forex_trading_graph import ForexTradingGraph

class BacktestingEngine:
    def __init__(self,
                 trading_strategy: Any, # Replace Any with actual strategy type e.g., ForexTradingGraph
                 broker: SimulatedBroker,
                 historical_data_source: Dict[str, List[Candlestick]], # Symbol -> List of Candlesticks
                 main_symbol_to_trade: str,
                 initial_graph_state_overrides: Optional[Dict] = None):
        self.trading_strategy = trading_strategy
        self.broker = broker
        self.historical_data_source = historical_data_source
        self.main_symbol_to_trade = main_symbol_to_trade.upper()
        self.initial_graph_state_overrides = initial_graph_state_overrides if initial_graph_state_overrides else {}

        self.equity_curve: List[Dict[str, Any]] = []
        self.account_snapshots: List[Optional[AccountInfo]] = []

        if self.main_symbol_to_trade not in self.historical_data_source:
            raise ValueError(f"Main symbol {self.main_symbol_to_trade} not found in historical_data_source keys.")
        if not self.historical_data_source[self.main_symbol_to_trade]:
            raise ValueError(f"No historical data provided for main symbol {self.main_symbol_to_trade}.")

        print(f"BacktestingEngine initialized for {self.main_symbol_to_trade}.")
        print(f"Data for {self.main_symbol_to_trade}: {len(self.historical_data_source[self.main_symbol_to_trade])} bars.")

    def run(self):
        print(f"--- Starting Backtesting Run for {self.main_symbol_to_trade} ---")

        data_sequence_for_main_symbol = self.historical_data_source[self.main_symbol_to_trade]

        initial_account_info = self.broker.get_account_info()
        if initial_account_info:
            print(f"Initial Account: Balance: {initial_account_info['balance']:.2f}, Equity: {initial_account_info['equity']:.2f}")
            self.account_snapshots.append(initial_account_info)
            first_bar_ts = data_sequence_for_main_symbol[0]['timestamp'] if data_sequence_for_main_symbol else time.time()
            self.equity_curve.append({'timestamp': first_bar_ts -1, 'equity': initial_account_info['equity']})


        for i, bar_data in enumerate(data_sequence_for_main_symbol):
            current_bar_candlestick = Candlestick(**bar_data)
            bar_timestamp_unix = current_bar_candlestick['timestamp']
            bar_datetime_obj = datetime.datetime.fromtimestamp(bar_timestamp_unix, tz=datetime.timezone.utc)

            if (i + 1) % 200 == 0: # Print progress every 200 bars
                 print(f"Processing Bar {i+1}/{len(data_sequence_for_main_symbol)} | Time: {bar_datetime_obj.isoformat()} | {self.main_symbol_to_trade} C: {current_bar_candlestick['close']}")

            # 1. Update broker time and market data
            self.broker.update_current_time(bar_timestamp_unix)

            current_market_snapshot: Dict[str, Candlestick] = {}
            current_market_snapshot[self.main_symbol_to_trade] = current_bar_candlestick

            for sym, data_list in self.historical_data_source.items():
                if sym != self.main_symbol_to_trade and len(data_list) > i:
                    sym_bar_data = data_list[i]
                    if sym_bar_data['timestamp'] == bar_timestamp_unix:
                         current_market_snapshot[sym.upper()] = Candlestick(**sym_bar_data)

            self.broker.update_market_data(current_market_snapshot)

            # 2. Process broker events (SL/TP, pending orders)
            self.broker.process_pending_orders()
            self.broker.check_for_sl_tp_triggers()

            # 3. Invoke trading strategy
            current_iteration_state = {
                "currency_pair": self.main_symbol_to_trade,
                "current_simulated_time": bar_datetime_obj.isoformat(),
                "current_bar_candlestick": current_bar_candlestick,
                "sub_agent_tasks": [],
                "market_regime": "BacktestRegime", # Or derive this if possible
                "proposals_from_sub_agents": [],
                "forex_final_decision": None, # To be populated by the graph
                "error_message": None
            }
            current_iteration_state.update(self.initial_graph_state_overrides)

            # print(f"Invoking strategy for bar ending {bar_datetime_obj.isoformat()}...")
            if hasattr(self.trading_strategy, 'graph') and hasattr(self.trading_strategy.graph, 'invoke'):
                final_state_for_bar = self.trading_strategy.graph.invoke(current_iteration_state)
            elif hasattr(self.trading_strategy, 'invoke'): # If strategy itself is directly invokable
                 final_state_for_bar = self.trading_strategy.invoke(current_iteration_state)
            else:
                print("ERROR: Trading strategy does not have a recognized 'invoke' method.")
                final_state_for_bar = current_iteration_state # No decision

            strategy_decision: Optional[ForexFinalDecision] = final_state_for_bar.get("forex_final_decision")

            if strategy_decision and isinstance(strategy_decision, dict):
                action = strategy_decision.get("action")
                # print(f"Strategy decision: {action} for {strategy_decision.get('currency_pair')}")
                if action in ["EXECUTE_BUY", "EXECUTE_SELL"]:
                    vol = strategy_decision.get("position_size", 0.01) # Default to 0.01 lots
                    sl = strategy_decision.get("stop_loss")
                    tp = strategy_decision.get("take_profit")
                    order_side = OrderSide.BUY if action == "EXECUTE_BUY" else OrderSide.SELL

                    if strategy_decision.get("currency_pair") == self.main_symbol_to_trade:
                        # print(f"Attempting to place {order_side.value} order for {vol} lots of {self.main_symbol_to_trade} | SL: {sl} TP: {tp}")
                        self.broker.place_order(
                            symbol=self.main_symbol_to_trade,
                            order_type=OrderType.MARKET,
                            side=order_side,
                            volume=vol,
                            stop_loss=sl,
                            take_profit=tp,
                            comment=f"Strategy Decision: {action}"
                        )
                    # else:
                        # print(f"Strategy decision for {strategy_decision.get('currency_pair')} ignored as main trade symbol is {self.main_symbol_to_trade}.")

            # 4. Check margin calls after any new trades
            self.broker.check_for_margin_call()

            # 5. Record equity and account snapshot
            current_account_info = self.broker.get_account_info()
            if current_account_info:
                self.equity_curve.append({
                    'timestamp': bar_timestamp_unix,
                    'equity': current_account_info['equity']
                })
                self.account_snapshots.append(current_account_info)
            else:
                if self.equity_curve: last_equity = self.equity_curve[-1]['equity']
                elif initial_account_info: last_equity = initial_account_info['equity']
                else: last_equity = self.broker.initial_capital
                self.equity_curve.append({'timestamp': bar_timestamp_unix, 'equity': last_equity})
                self.account_snapshots.append(None)

        print(f"--- Backtesting Run Finished for {self.main_symbol_to_trade} ---")
        final_account_details = self.broker.get_account_info()
        if final_account_details:
            print("Final Account Info:")
            for key, value in final_account_details.items(): print(f"  {key}: {value}")

        print(f"Total equity curve points recorded: {len(self.equity_curve)}")
        print(f"Total trade history events in broker: {len(self.broker.trade_history)}")

    def calculate_performance(self, report_filename_prefix: str = "backtest_report"):
        print("\n--- Calculating Performance Metrics ---")
        if not self.equity_curve:
            print("No equity curve data to calculate performance.")
            return

        # Prepare returns series for QuantStats
        equity_df = pd.DataFrame(self.equity_curve)
        equity_df['timestamp'] = pd.to_datetime(equity_df['timestamp'], unit='s', utc=True)
        equity_df = equity_df.set_index('timestamp')

        # Ensure equity series is sorted by time and has no duplicate timestamps
        equity_df = equity_df.sort_index()
        equity_df = equity_df[~equity_df.index.duplicated(keep='last')]

        returns_series = equity_df['equity'].pct_change().fillna(0)

        # Resample to daily returns for QuantStats compatibility and standard reporting
        daily_returns = returns_series.resample('D').sum().fillna(0) # Added fillna(0) after resampling


        if daily_returns.empty or daily_returns.isnull().all() or (daily_returns == 0).all():
            print("Daily returns series is empty, all NaN, or all zeros after resampling. Cannot generate QuantStats report.")
            if not daily_returns.empty:
                print("Daily Returns Series Head:\n", daily_returns.head())
                print("Daily Returns Series Describe:\n", daily_returns.describe())
            # Also print info about the original returns_series for more context
            print("Original (Sub-Daily) Returns Series Head:\n", returns_series.head())
            print("Original (Sub-Daily) Returns Series Describe:\n", returns_series.describe())
            return

        output_filename = f"{report_filename_prefix}_{self.main_symbol_to_trade}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        try:
            print(f"Generating QuantStats HTML report to: {output_filename}")
            quantstats.reports.html(daily_returns, output=output_filename, title=f"{self.main_symbol_to_trade} Backtest Report")
            print(f"QuantStats report generated successfully: {output_filename}")
        except Exception as e:
            print(f"Error generating QuantStats report: {e}")
            print("Make sure QuantStats and its dependencies (like IPython) are installed.")
            print("Returns Series Head:\n", returns_series.head())
            print("Returns Series Tail:\n", returns_series.tail())
            print("Returns Series Describe:\n", returns_series.describe())

# The 'random' import is kept as it was in the previous version from Part 3b.
# ForexTradingGraph import is still commented out.
# The __main__ block remains removed.
