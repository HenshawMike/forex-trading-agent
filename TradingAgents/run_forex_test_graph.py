import datetime
import sys
import os
import time # For simulating delays if needed
from typing import List, Dict, Any, Optional

# Path Adjustments (as before)
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
sys.path.insert(0, project_root)

try:
    from tradingagents.graph.forex_trading_graph import ForexTradingGraph
    from tradingagents.broker_interface.simulated_broker import SimulatedBroker
    from tradingagents.forex_utils.forex_states import ForexFinalDecision, OrderSide, OrderType, TimeInForce, Candlestick # For type hints & setup
except ImportError as e:
    print(f"ImportError: {e}. Check paths and ensure all modules are created.")
    print(f"Current sys.path includes: {sys.path[0]}")
    sys.exit(1)

def setup_scenario_broker(
    initial_capital: float = 10000.0,
    leverage: int = 100,
    default_spread_pips: Optional[Dict[str, float]] = None,
    commission_per_lot: Optional[Dict[str, float]] = None,
    margin_warning_level: float = 100.0,
    stop_out_level: float = 50.0
) -> SimulatedBroker:

    # Provide default spread and commission if None is passed
    spreads = default_spread_pips if default_spread_pips is not None else {"EURUSD": 0.5, "default": 1.0}
    commissions = commission_per_lot if commission_per_lot is not None else {"EURUSD": 0.0, "default": 0.0}

    broker = SimulatedBroker(
        initial_capital=initial_capital,
        # These params need to be passed to SimulatedBroker's __init__ if it accepts them
        # Currently, SimulatedBroker __init__ takes only initial_capital.
        # It sets default_spread_pips and commission_per_lot internally.
        # For this refactor, we'll update the broker instance directly after creation for these.
    )
    broker.leverage = leverage # Assuming leverage can be set like this, or pass in constructor
    broker.default_spread_pips = spreads
    broker.commission_per_lot = commissions
    broker.margin_call_warning_level_pct = margin_warning_level
    broker.stop_out_level_pct = stop_out_level
    return broker

def run_simulation_loop(
    graph_instance: ForexTradingGraph,
    broker_instance: SimulatedBroker,
    currency_pair_to_trade: str,
    market_data_sequence: List[Dict], # List of Candlestick-like dicts
    initial_graph_state_overrides: Optional[Dict] = None
):
    print(f"\n--- Starting Simulation Loop for {currency_pair_to_trade} ---")
    initial_account_info = broker_instance.get_account_info()
    if initial_account_info:
        print(f"Initial Account Info: Balance: {initial_account_info['balance']}, Equity: {initial_account_info['equity']}, Margin: {initial_account_info['margin']}, Free Margin: {initial_account_info['free_margin']}, Margin Level: {initial_account_info['margin_level']}%")
    else:
        print("Initial Account Info: Could not retrieve.")


    for i, bar_dict in enumerate(market_data_sequence):
        # Ensure bar_dict is converted to Candlestick TypedDict for broker.update_market_data
        # Or ensure broker.update_market_data can handle dicts.
        # For now, assuming dicts are fine as per current SimulatedBroker structure for market_data.
        # The Candlestick TypedDict is primarily for type hinting and explicit object creation.
        current_bar_candlestick = Candlestick(**bar_dict)


        bar_timestamp_unix = current_bar_candlestick['timestamp']
        bar_datetime_obj = datetime.datetime.fromtimestamp(bar_timestamp_unix, tz=datetime.timezone.utc)
        bar_iso_timestamp = bar_datetime_obj.isoformat()

        print(f"\n--- Bar {i+1} | Time: {bar_iso_timestamp} | {currency_pair_to_trade} C: {current_bar_candlestick['close']} H: {current_bar_candlestick['high']} L: {current_bar_candlestick['low']} O: {current_bar_candlestick['open']} ---")

        # 1. Update broker's knowledge of current time and market prices
        broker_instance.update_current_time(bar_timestamp_unix)
        broker_instance.update_market_data({currency_pair_to_trade: current_bar_candlestick})

        # 2. Broker processes events based on new market data (before agent logic for this bar)
        broker_instance.process_pending_orders()
        broker_instance.check_for_sl_tp_triggers()

        # 3. Agent system runs its logic for the current bar
        current_iteration_state = {
            "currency_pair": currency_pair_to_trade,
            "current_simulated_time": bar_iso_timestamp,
            "sub_agent_tasks": [], "market_regime": "TestRegime",
            "scalper_proposal": None, "day_trader_proposal": None,
            "swing_trader_proposal": None, "position_trader_proposal": None,
            "proposals_from_sub_agents": [], "aggregated_proposals_for_meta_agent": None,
            "forex_final_decision": None, "error_message": None
        }
        if initial_graph_state_overrides:
            current_iteration_state.update(initial_graph_state_overrides)

        print(f"Invoking graph for bar ending {bar_iso_timestamp}...")
        # The graph instance passed should already have the broker instance from its __init__
        final_state_for_bar = graph_instance.graph.invoke(current_iteration_state)

        final_decision = final_state_for_bar.get("forex_final_decision")
        if final_decision:
            print(f"Graph produced decision: {final_decision['action']} for {final_decision['currency_pair']}")
            # Here, one might implement logic to take the 'final_decision' and translate it
            # into an actual order placement call to broker_instance.place_order(...)
            # This part is crucial for a full backtest but is outside the scope of just running the graph's logic.
            # For example:
            # if final_decision['action'] == "EXECUTE_BUY":
            #    broker_instance.place_order(symbol=final_decision['currency_pair'], type=OrderType.MARKET, ...)
        else:
            print("Graph did not produce a final decision for this bar.")

        # 4. Broker processes margin calls after all trades and P/L updates for the bar
        # _update_equity_and_margin is called by update_market_data, and after any order fills/closures.
        # So, by the time check_for_margin_call is called, equity and margin_used should be current.
        broker_instance.check_for_margin_call()

        # 5. Log EOD/EOB account info
        eob_account_info = broker_instance.get_account_info()
        if eob_account_info:
             print(f"End of Bar {i+1} Account Info: Balance: {eob_account_info['balance']}, Equity: {eob_account_info['equity']}, Margin: {eob_account_info['margin']}, Free Margin: {eob_account_info['free_margin']}, Margin Level: {eob_account_info['margin_level']}%")
        else:
            print(f"End of Bar {i+1} Account Info: Could not retrieve.")


    print(f"\n--- Simulation Loop Finished for {currency_pair_to_trade} ---")
    final_account_details = broker_instance.get_account_info()
    if final_account_details:
        print("Final Account Info:")
        for key, value in final_account_details.items():
            print(f"  {key}: {value}")
    else:
        print("Final Account Info: Could not retrieve.")

    print("\nTrade History:")
    for i, trade_event in enumerate(broker_instance.trade_history): # Use trade_history attribute
        print(f"  {i+1}: {trade_event}")

# Placeholder for Scenario 1 (to be implemented in next step)
def test_scenario_winning_buy_tp():
    print("\n\n===== SCENARIO 1: WINNING BUY MARKET ORDER (HITTING TP) =====")

    # 1. Setup Broker
    broker = setup_scenario_broker(
        initial_capital=10000.0,
        default_spread_pips={"EURUSD": 1.0}, # 1 pip spread
        commission_per_lot={"EURUSD": 0.0} # No commission for this test
    )

    # 2. Prepare Market Data Sequence for EURUSD
    start_time_unix = int(datetime.datetime(2023, 10, 1, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    eurusd_market_data: List[Dict[str, Any]] = [] # Ensure type for clarity
    base_price = 1.08000

    # Warm-up period (30 bars for indicators) - simple upward trend
    for i in range(30):
        ts = start_time_unix + (i * 3600)
        eurusd_market_data.append({
            "timestamp": float(ts), "open": base_price + (i * 0.00010),
            "high": base_price + (i * 0.00010) + 0.00050,
            "low": base_price + (i * 0.00010) - 0.00020,
            "close": base_price + (i * 0.00010) + 0.00030,
            "volume": float(1000 + i * 10)
        })

    trigger_bar_price_close = eurusd_market_data[-1]['close']
    entry_bar_ts = start_time_unix + (30 * 3600)
    eurusd_market_data.append({
        "timestamp": float(entry_bar_ts), "open": trigger_bar_price_close,
        "high": trigger_bar_price_close + 0.00050, "low": trigger_bar_price_close - 0.00020,
        "close": trigger_bar_price_close + 0.00010, "volume": float(1200)
    })

    # Assuming entry around Ask of 1.08330 (close) + 0.00005 (half of 1 pip spread) = 1.08335
    # TP target = 1.08335 + 0.00400 (40 pips) = 1.08735
    tp_hit_bar_ts = start_time_unix + (31 * 3600)
    eurusd_market_data.append({
        "timestamp": float(tp_hit_bar_ts), "open": eurusd_market_data[-1]['close'],
        "high": 1.08800, # Must be >= TP target 1.08735
        "low": eurusd_market_data[-1]['close'] - 0.00010,
        "close": 1.08750, "volume": float(1100)
    })

    for i in range(2): # Add a few more bars
        ts = start_time_unix + ((32 + i) * 3600)
        eurusd_market_data.append({
            "timestamp": float(ts), "open": eurusd_market_data[-1]['close'],
            "high": eurusd_market_data[-1]['close'] + 0.00020,
            "low": eurusd_market_data[-1]['close'] - 0.00020,
            "close": eurusd_market_data[-1]['close'] + (0.00010 * (1 if i % 2 == 0 else -1)),
            "volume": float(1000)
        })

    broker.load_test_data("EURUSD", eurusd_market_data)

    # 3. Initialize Graph
    graph = ForexTradingGraph(broker=broker)

    # 4. Execute Simulation Loop
    # For this specific test, we assume the DayTraderAgent will be triggered on the "entry_bar_ts"
    # and will decide to BUY. The graph logic currently processes all agents.
    # We need a mechanism for the graph to actually place the trade.
    # For now, we will manually place the order with the broker to test broker mechanics.
    # This means we are testing the broker's TP mechanism, not the agent's decision making yet.

    print("MANUALLY PLACING TEST ORDER for Scenario 1 to test broker TP...")
    # Simulate agent's decision time as the beginning of the entry_bar_ts
    broker.update_current_time(entry_bar_ts)
    # Provide market data for that specific bar so get_current_price works for order placement
    broker.update_market_data({"EURUSD": Candlestick(**eurusd_market_data[30])})


    # Manually place the order that the agent *should* have made
    # Assume DayTraderAgent default stop_loss_pips = 20, take_profit_pips = 40
    # Assume volume 0.01 lots for P/L calculation test
    entry_order_response = broker.place_order(
        symbol="EURUSD",
        order_type=OrderType.MARKET,
        side=OrderSide.BUY,
        volume=0.01, # Critical for P/L calculation test
        stop_loss=None, # Will be calculated based on pips if agent logic were complete
        take_profit=None # Will be calculated
    )

    test_position_id = None
    if entry_order_response and entry_order_response.get("status") == "FILLED":
        print(f"Manual BUY order placed and filled: {entry_order_response}")
        test_position_id = entry_order_response.get("position_id")
        # Manually set SL/TP on the position as agent would
        # This requires a way to get the actual entry price.
        actual_entry_price = entry_order_response.get("price")
        if actual_entry_price and test_position_id:
            pip_val, precision = broker._calculate_pip_value_and_precision("EURUSD") # Accessing private for test setup
            sl_price = round(actual_entry_price - (20 * pip_val), precision)
            tp_price = round(actual_entry_price + (40 * pip_val), precision)
            broker.modify_order(test_position_id, stop_loss=sl_price, take_profit=tp_price)
            print(f"Manually set SL: {sl_price}, TP: {tp_price} for position {test_position_id}")
    else:
        print(f"Manual BUY order failed or not filled: {entry_order_response}")
        return # Cannot proceed with test if order isn't placed

    # Now run the simulation loop for the bars *after* the order was placed
    # The first bar in this sequence will be tp_hit_bar_ts
    run_simulation_loop(
        graph_instance=graph, # Graph is run, but not strictly making decisions for this test
        broker_instance=broker,
        currency_pair_to_trade="EURUSD",
        market_data_sequence=eurusd_market_data[31:] # Start from the TP hit bar
    )

    print("===== VERIFICATION FOR SCENARIO 1 =====")
    final_account_info = broker.get_account_info()
    if final_account_info:
        print(f"Final Balance: {final_account_info['balance']:.2f}")

        day_trader_tp_pips_scenario1 = 40.0
        pip_value_for_0_01_lots_eurusd = 0.10

        expected_profit = day_trader_tp_pips_scenario1 * pip_value_for_0_01_lots_eurusd
        print(f"Expected Profit (for {day_trader_tp_pips_scenario1} pip TP, 0.01 lots, 0 commission): ${expected_profit:.2f}")
        print(f"Actual Profit: ${final_account_info['balance'] - 10000.0:.2f}")

        found_buy_fill = False
        found_tp_close = False
        for event in broker.trade_history: # Use attribute directly
            if event.get("event_type") == "MARKET_ORDER_FILLED" and event.get("side") == "BUY":
                found_buy_fill = True
                print(f"Found BUY Fill: {event}")
            if event.get("event_type") == "POSITION_CLOSED" and event.get("reason_for_close") == "TAKE_PROFIT_HIT":
                found_tp_close = True
                print(f"Found TP Close: {event}")

        if found_buy_fill and found_tp_close:
            print("VERIFICATION: Winning BUY order filled and closed by TP successfully.")
        else:
            print("VERIFICATION ERROR: Winning BUY order TP scenario not fully verified in trade history.")
    else:
        print("VERIFICATION ERROR: Could not retrieve final account info.")
    print("==========================================")


# Placeholder for Scenario 2
def test_scenario_losing_sell_sl():
    print("\n\n===== SCENARIO 2: LOSING SELL MARKET ORDER (HITTING SL) =====")

    # 1. Setup Broker
    broker = setup_scenario_broker(
        initial_capital=10000.0,
        default_spread_pips={"EURUSD": 1.0}, # 1 pip spread
        commission_per_lot={"EURUSD": 0.0} # No commission for this test
    )

    # 2. Prepare Market Data Sequence for EURUSD
    start_time_unix = int(datetime.datetime(2023, 10, 2, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    eurusd_market_data: List[Dict[str, Any]] = []
    base_price = 1.08500 # Start higher for a sell setup

    # Warm-up period (30 bars for indicators) - simple downward trend
    for i in range(30):
        ts = start_time_unix + (i * 3600) # H1 timeframe
        eurusd_market_data.append({
            "timestamp": float(ts),
            "open": base_price - (i * 0.00010),
            "high": base_price - (i * 0.00010) + 0.00020,
            "low": base_price - (i * 0.00010) - 0.00050,
            "close": base_price - (i * 0.00010) - 0.00030,
            "volume": float(1000 + i * 10)
        })

    trigger_bar_price_close = eurusd_market_data[-1]['close']
    entry_bar_ts = start_time_unix + (30 * 3600) # This is timestamp of bar 31 (index 30)
    eurusd_market_data.append({
        "timestamp": float(entry_bar_ts), "open": trigger_bar_price_close,
        "high": trigger_bar_price_close + 0.00020, "low": trigger_bar_price_close - 0.00010,
        "close": trigger_bar_price_close - 0.00005, "volume": float(1200)
    })

    # Set broker's current time and market data for the moment of placing the order
    broker.update_current_time(entry_bar_ts)
    broker.update_market_data({"EURUSD": Candlestick(**eurusd_market_data[30])})

    print(f"Attempting to place SELL order at simulated time: {datetime.datetime.fromtimestamp(entry_bar_ts, tz=datetime.timezone.utc).isoformat()}")

    day_trader_sl_pips = 20.0
    day_trader_tp_pips = 40.0 # Though TP won't be hit in this scenario

    sell_order_response = broker.place_order(
        symbol="EURUSD", order_type=OrderType.MARKET, side=OrderSide.SELL,
        volume=0.01, comment="Test SL Scenario - Manual Sell"
    )

    position_id_to_track = None
    if sell_order_response and sell_order_response.get("status") == "FILLED":
        print(f"Manual SELL Order Filled: {sell_order_response}")
        position_id_to_track = sell_order_response.get("position_id")

        if position_id_to_track:
            fill_price = sell_order_response['price']
            # Use broker's helper for pip unit value for accuracy
            pip_unit_value = broker._get_pip_value_for_sl_tp("EURUSD")
            price_precision = broker._get_price_precision("EURUSD")

            sl_price = round(fill_price + (day_trader_sl_pips * pip_unit_value), price_precision)
            tp_price = round(fill_price - (day_trader_tp_pips * pip_unit_value), price_precision)
            print(f"Setting SL/TP for position {position_id_to_track}: SL={sl_price}, TP={tp_price}. Fill price: {fill_price}")
            broker.modify_order(position_id_to_track, new_stop_loss=sl_price, new_take_profit=tp_price)
        else:
            print("ERROR: Could not get position_id from filled order to set SL/TP.")
            return
    else:
        print(f"ERROR: Manual SELL Order failed to fill: {sell_order_response}")
        return

    # SL is approx fill_price (e.g. 1.08170 from comments in prompt) + 0.00200 = 1.08370
    # This bar (index 31) needs its HIGH to hit that SL
    sl_hit_bar_ts = entry_bar_ts + 3600
    eurusd_market_data.append({
        "timestamp": float(sl_hit_bar_ts), "open": eurusd_market_data[-1]['close'],
        "high": 1.08400, # Ensure this is >= SL target (e.g. if fill was 1.08170, SL is 1.08370)
        "low": eurusd_market_data[-1]['close'] - 0.00010,
        "close": 1.08380, "volume": float(1100)
    })

    for i in range(2): # Add a few more bars
        ts = sl_hit_bar_ts + ((i + 1) * 3600)
        eurusd_market_data.append({
            "timestamp": float(ts), "open": eurusd_market_data[-1]['close'],
            "high": eurusd_market_data[-1]['close'] + 0.00020,
            "low": eurusd_market_data[-1]['close'] - 0.00020,
            "close": eurusd_market_data[-1]['close'] + (0.00010 * (1 if i % 2 == 0 else -1)),
            "volume": float(1000)
        })

    broker.load_test_data("EURUSD", eurusd_market_data)

    graph = ForexTradingGraph(broker=broker)

    # Simulation loop starts from the bar that can hit the SL (index 31)
    run_simulation_loop(
        graph_instance=graph, broker_instance=broker, currency_pair_to_trade="EURUSD",
        market_data_sequence=eurusd_market_data[31:]
    )

    print("===== VERIFICATION FOR SCENARIO 2 =====")
    final_account_info = broker.get_account_info()
    if final_account_info:
        print(f"Final Balance: {final_account_info['balance']:.2f}")

        day_trader_sl_pips_scenario2 = 20.0
        pip_value_for_0_01_lots_eurusd = 0.10

        expected_loss = day_trader_sl_pips_scenario2 * pip_value_for_0_01_lots_eurusd
        print(f"Expected Loss (for {day_trader_sl_pips_scenario2} pip SL, 0.01 lots, 0 commission): ${expected_loss:.2f}")
        # Actual loss calculation from balance change:
        actual_loss_from_balance = 10000.0 - final_account_info['balance']
        print(f"Actual Loss reflected in balance: ${actual_loss_from_balance:.2f}")

        found_sell_fill = False
        found_sl_close = False
        for event in broker.trade_history:
            if event.get("event_type") == "MARKET_ORDER_FILLED" and event.get("side") == "SELL":
                found_sell_fill = True
                print(f"Found SELL Fill: {event}")
            if event.get("event_type") == "POSITION_CLOSED" and event.get("reason_for_close") == "STOP_LOSS_HIT":
                found_sl_close = True
                print(f"Found SL Close: {event}")

        if found_sell_fill and found_sl_close:
            print("VERIFICATION: Losing SELL order filled and closed by SL successfully.")
        else:
            print("VERIFICATION ERROR: Losing SELL order SL scenario not fully verified in trade history.")
    else:
        print("VERIFICATION ERROR: Could not retrieve final account info.")
    print("==========================================")

def main():
    print("--- Main Test Runner for Forex Trading Scenarios ---")

    # Call scenario functions
    test_scenario_winning_buy_tp()
    test_scenario_losing_sell_sl()

if __name__ == "__main__":
    main()
