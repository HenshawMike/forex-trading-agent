import datetime
import time
import random
from typing import List, Dict, Any, Optional

# Assuming PYTHONPATH or sys.path is configured for 'TradingAgents' to be the root
from TradingAgents.tradingagents.broker_interface.simulated_broker import SimulatedBroker
from TradingAgents.tradingagents.backtester.engine import BacktestingEngine
from TradingAgents.tradingagents.forex_utils.forex_states import Candlestick, ForexFinalDecision, OrderSide, OrderType
# from TradingAgents.tradingagents.graph.forex_trading_graph import ForexTradingGraph # Moved inside try-except

def generate_dummy_market_data(symbol: str, start_time_unix: float, num_bars: int, initial_price: float, timeframe_seconds: int = 3600) -> List[Candlestick]:
    data: List[Candlestick] = []
    price = initial_price
    for i in range(num_bars):
        ts = start_time_unix + i * timeframe_seconds
        open_p = price
        close_p = open_p + random.uniform(-0.001, 0.001) * (1 + i*0.002) # Add some trend/volatility
        high_p = max(open_p, close_p) + random.uniform(0, 0.0005)
        low_p = min(open_p, close_p) - random.uniform(0, 0.0005)

        # Ensure OHLC consistency
        if low_p > open_p: low_p = open_p
        if low_p > close_p: low_p = close_p
        if high_p < open_p: high_p = open_p
        if high_p < close_p: high_p = close_p

        bid_c = close_p - random.uniform(0.00002, 0.00008) # Example historical bid
        ask_c = close_p + random.uniform(0.00002, 0.00008) # Example historical ask

        bar: Candlestick = {
            "timestamp": float(ts),
            "open": round(open_p, 5),
            "high": round(high_p, 5),
            "low": round(low_p, 5),
            "close": round(close_p, 5),
            "volume": random.uniform(100, 1000),
            "bid_close": round(bid_c, 5),
            "ask_close": round(ask_c, 5)
        }
        data.append(bar)
        price = close_p # Next bar opens near current close
    print(f"Generated {len(data)} dummy bars for {symbol}")
    return data

class DummyStrategyForTesting:
    def __init__(self, broker_for_info: SimulatedBroker, main_symbol: str):
        self.trade_countdown = 0
        self.last_action = "SELL" # Start by looking to buy
        self.broker = broker_for_info # For symbol info if needed
        self.main_symbol = main_symbol
        self.decision_id_counter = 0

    def invoke(self, state: Dict) -> Dict:
        self.trade_countdown -= 1
        final_decision = None

        # Ensure current_bar_candlestick is in state (added for robustness)
        current_bar = state.get('current_bar_candlestick')
        if not current_bar:
            # print("DummyStrategy: No current_bar_candlestick in state, cannot make decision.")
            state["forex_final_decision"] = None
            return state

        current_price = current_bar['close']

        if self.trade_countdown <= 0:
            self.decision_id_counter += 1
            action_to_take = OrderSide.BUY if self.last_action == "SELL" else OrderSide.SELL
            self.last_action = action_to_take.value

            # Use broker's method to get pip value for SL/TP calculation
            # This requires _get_symbol_info to be robust.
            symbol_info = self.broker._get_symbol_info(self.main_symbol)
            if not symbol_info or 'pip_definition' not in symbol_info:
                print(f"DummyStrategy: Could not get pip_definition for {self.main_symbol}. Using default 0.0001.")
                pip_val = 0.0001
                price_precision = 5
            else:
                pip_val = symbol_info['pip_definition']
                price_precision = symbol_info['price_precision']

            sl_pips = 20.0
            tp_pips = 40.0

            sl_price = current_price - sl_pips * pip_val if action_to_take == OrderSide.BUY else current_price + sl_pips * pip_val
            tp_price = current_price + tp_pips * pip_val if action_to_take == OrderSide.BUY else current_price - tp_pips * pip_val

            final_decision = ForexFinalDecision(
                decision_id=f"dummy_dec_{self.decision_id_counter}_{int(time.time())}",
                currency_pair=state['currency_pair'],
                timestamp=state['current_simulated_time'],
                based_on_aggregation_id="dummy_agg_id",
                action="EXECUTE_BUY" if action_to_take == OrderSide.BUY else "EXECUTE_SELL",
                entry_price=None, # Market order
                stop_loss=round(sl_price, price_precision),
                take_profit=round(tp_price, price_precision),
                position_size=0.01, # Trade 0.01 lots
                meta_rationale="Dummy strategy periodic trade",
                # Fill optional fields that might be expected by ForexFinalDecision
                risk_percentage_of_capital=None,
                meta_confidence_score=0.75,
                meta_assessed_risk_level="Medium",
                contributing_proposals_ids=[],
                status=None,
                pending_approval_timestamp=None,
                approval_expiry_timestamp=None,
                user_action_timestamp=None,
                acted_by_user_id=None
            )
            self.trade_countdown = random.randint(10, 30) # Trade every 10-30 bars

        state["forex_final_decision"] = final_decision
        return state

def main():
    print("--- Starting Backtest Run Script ---")

    # 1. Setup SimulatedBroker
    broker = SimulatedBroker(initial_capital=10000.0)
    broker.base_slippage_pips = 0.2
    broker.volume_slippage_factor_pips_per_million = 0.1
    broker.default_spread_pips = {"EURUSD": 0.6, "USDJPY": 0.7, "default": 1.0} # Adjusted spread
    broker.commission_per_lot = {"EURUSD": 3.0, "default": 3.0} # Example commission

    # 2. Prepare Market Data
    start_ts = int(datetime.datetime(2023, 1, 1, tzinfo=datetime.timezone.utc).timestamp())
    num_days = 90 # About 3 months of H1 data
    eurusd_data = generate_dummy_market_data("EURUSD", start_ts, num_bars=num_days * 24, initial_price=1.0800)
    usdjpy_data = generate_dummy_market_data("USDJPY", start_ts, num_bars=num_days * 24, initial_price=140.00)

    # Load data into broker (SimulatedBroker's load_test_data now handles validation)
    broker.load_test_data("EURUSD", eurusd_data)
    broker.load_test_data("USDJPY", usdjpy_data) # For currency conversions if needed by broker

    historical_data_for_engine = {"EURUSD": eurusd_data, "USDJPY": usdjpy_data}
    main_trade_symbol = "EURUSD"

    # 3. Initialize Trading Strategy
    strategy_to_use = None
    use_dummy_strategy = False # Flag to control which strategy is used.

    try:
        # Attempt to use the actual ForexTradingGraph
        # This assumes ForexTradingGraph can be initialized with just the broker
        # and its internal setup (like config loading) can handle a simulated environment.
        # If it requires more complex setup (e.g. specific config files, API keys for sub-agents even if mocked),
        # this might fail or the graph might not make decisions.
        print("Attempting to import and initialize ForexTradingGraph...")
        from TradingAgents.tradingagents.graph.forex_trading_graph import ForexTradingGraph # Moved import here
        forex_graph_strategy = ForexTradingGraph(broker=broker)
        # It's possible the graph needs to be "compiled" or specifically run.
        # The engine expects an object with an 'invoke' method (or 'graph.invoke').
        # If ForexTradingGraph itself is the invokable, that's fine.
        # If it's forex_graph_strategy.graph.invoke, the engine handles that.
        strategy_to_use = forex_graph_strategy
        print("ForexTradingGraph initialized (or at least attempted).")
    except Exception as e:
        print(f"Could not initialize ForexTradingGraph: {e}. Falling back to DummyStrategyForTesting.")
        use_dummy_strategy = True

    if use_dummy_strategy or strategy_to_use is None:
        print("Using DummyStrategyForTesting.")
        strategy_to_use = DummyStrategyForTesting(broker_for_info=broker, main_symbol=main_trade_symbol)


    # 4. Initialize and Run BacktestingEngine
    print(f"Initializing BacktestingEngine with {'DummyStrategyForTesting' if use_dummy_strategy else 'ForexTradingGraph (or its invoker)'}.")
    engine = BacktestingEngine(
        trading_strategy=strategy_to_use,
        broker=broker,
        historical_data_source=historical_data_for_engine,
        main_symbol_to_trade=main_trade_symbol,
        initial_graph_state_overrides={} # Add any specific overrides if your graph needs them
    )

    print("\n--- Commencing Engine Run ---")
    engine.run()

    # 5. Calculate Performance
    print("\n--- Commencing Performance Calculation ---")
    report_prefix = "forex_graph_backtest" if not use_dummy_strategy else "dummy_strategy_backtest"
    engine.calculate_performance(report_filename_prefix=report_prefix)

    print(f"--- Backtest Run Script Finished ---")
    print(f"Trade history events: {len(broker.trade_history)}")
    # Further inspection of broker.trade_history or equity_curve could be done here if needed.

if __name__ == "__main__":
    # This structure ensures that imports work correctly when run as a script,
    # assuming the TradingAgents directory is in PYTHONPATH or the script is run from its parent.
    # For robust execution, it's often better to run from the project root:
    # python -m TradingAgents.run_backtest

    # Adjust sys.path if running the script directly and TradingAgents is not in PYTHONPATH
    import os
    import sys
    current_script_path = os.path.dirname(os.path.abspath(__file__))
    project_root_path = os.path.abspath(os.path.join(current_script_path, '..')) # Assuming script is in TradingAgents/
    if project_root_path not in sys.path:
        sys.path.insert(0, project_root_path)
        # print(f"Adjusted sys.path to include {project_root_path}")

    main()
