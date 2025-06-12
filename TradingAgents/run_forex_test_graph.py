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

    spreads = default_spread_pips if default_spread_pips is not None else {"EURUSD": 0.5, "default": 1.0}
    commissions = commission_per_lot if commission_per_lot is not None else {"EURUSD": 0.0, "default": 0.0}

    broker = SimulatedBroker(initial_capital=initial_capital)
    broker.leverage = leverage
    broker.default_spread_pips = spreads
    broker.commission_per_lot = commissions
    broker.margin_call_warning_level_pct = margin_warning_level
    broker.stop_out_level_pct = stop_out_level
    return broker

def run_simulation_loop(
    graph_instance: ForexTradingGraph,
    broker_instance: SimulatedBroker,
    currency_pair_to_trade: str,
    market_data_sequence: List[Dict],
    initial_graph_state_overrides: Optional[Dict] = None
):
    print(f"\n--- Starting Simulation Loop for {currency_pair_to_trade} ---")
    initial_account_info = broker_instance.get_account_info()
    if initial_account_info:
        print(f"Initial Account Info: Balance: {initial_account_info['balance']}, Equity: {initial_account_info['equity']}, Margin: {initial_account_info['margin']}, Free Margin: {initial_account_info['free_margin']}, Margin Level: {initial_account_info['margin_level']}%")
    else:
        print("Initial Account Info: Could not retrieve.")

    for i, bar_dict in enumerate(market_data_sequence):
        current_bar_candlestick = Candlestick(**bar_dict)
        bar_timestamp_unix = current_bar_candlestick['timestamp']
        bar_datetime_obj = datetime.datetime.fromtimestamp(bar_timestamp_unix, tz=datetime.timezone.utc)
        bar_iso_timestamp = bar_datetime_obj.isoformat()

        print(f"\n--- Bar {i+1} | Time: {bar_iso_timestamp} | {currency_pair_to_trade} C: {current_bar_candlestick['close']} H: {current_bar_candlestick['high']} L: {current_bar_candlestick['low']} O: {current_bar_candlestick['open']} ---")

        broker_instance.update_current_time(bar_timestamp_unix)
        # Pass all symbols relevant for this bar if broker needs to update multiple data points for _get_exchange_rate
        # Assuming bar_dict for run_simulation_loop is a single symbol's bar for now.
        # For multi-symbol needs in _get_exchange_rate, update_market_data should receive all.
        # The test scenarios will need to call update_market_data with all relevant pairs.
        broker_instance.update_market_data({currency_pair_to_trade: current_bar_candlestick})

        broker_instance.process_pending_orders()
        broker_instance.check_for_sl_tp_triggers()

        current_iteration_state = {
            "currency_pair": currency_pair_to_trade, "current_simulated_time": bar_iso_timestamp,
            "sub_agent_tasks": [], "market_regime": "TestRegime", "scalper_proposal": None,
            "day_trader_proposal": None, "swing_trader_proposal": None, "position_trader_proposal": None,
            "proposals_from_sub_agents": [], "aggregated_proposals_for_meta_agent": None,
            "forex_final_decision": None, "error_message": None
        }
        if initial_graph_state_overrides: current_iteration_state.update(initial_graph_state_overrides)

        print(f"Invoking graph for bar ending {bar_iso_timestamp}...")
        final_state_for_bar = graph_instance.graph.invoke(current_iteration_state)

        final_decision = final_state_for_bar.get("forex_final_decision")
        if final_decision:
            print(f"Graph produced decision: {final_decision['action']} for {final_decision['currency_pair']}")
        else:
            print("Graph did not produce a final decision for this bar.")

        broker_instance.check_for_margin_call()

        eob_account_info = broker_instance.get_account_info()
        if eob_account_info:
             print(f"End of Bar {i+1} Account Info: Balance: {eob_account_info['balance']}, Equity: {eob_account_info['equity']}, Margin: {eob_account_info['margin']}, Free Margin: {eob_account_info['free_margin']}, Margin Level: {eob_account_info['margin_level']}%")
        else:
            print(f"End of Bar {i+1} Account Info: Could not retrieve.")

    print(f"\n--- Simulation Loop Finished for {currency_pair_to_trade} ---")
    final_account_details = broker_instance.get_account_info()
    if final_account_details:
        print("Final Account Info:")
        for key, value in final_account_details.items(): print(f"  {key}: {value}")
    else:
        print("Final Account Info: Could not retrieve.")

    print("\nTrade History:")
    for i, trade_event in enumerate(broker_instance.trade_history):
        print(f"  {i+1}: {trade_event}")

def test_scenario_winning_buy_tp():
    print("\n\n===== SCENARIO 1: WINNING BUY MARKET ORDER (HITTING TP) =====")
    broker = setup_scenario_broker(initial_capital=10000.0, default_spread_pips={"EURUSD": 1.0}, commission_per_lot={"EURUSD": 0.0})
    start_time_unix = int(datetime.datetime(2023, 10, 1, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    eurusd_market_data: List[Dict[str, Any]] = []
    base_price = 1.08000
    for i in range(30):
        ts = start_time_unix + (i * 3600); eurusd_market_data.append({"timestamp": float(ts), "open": base_price + (i * 0.00010), "high": base_price + (i * 0.00010) + 0.00050, "low": base_price + (i * 0.00010) - 0.00020, "close": base_price + (i * 0.00010) + 0.00030, "volume": float(1000 + i * 10)})
    trigger_bar_price_close = eurusd_market_data[-1]['close']
    entry_bar_ts = start_time_unix + (30 * 3600)
    eurusd_market_data.append({"timestamp": float(entry_bar_ts), "open": trigger_bar_price_close, "high": trigger_bar_price_close + 0.00050, "low": trigger_bar_price_close - 0.00020, "close": trigger_bar_price_close + 0.00010, "volume": float(1200)})
    tp_hit_bar_ts = start_time_unix + (31 * 3600)
    eurusd_market_data.append({"timestamp": float(tp_hit_bar_ts), "open": eurusd_market_data[-1]['close'], "high": 1.08800, "low": eurusd_market_data[-1]['close'] - 0.00010, "close": 1.08750, "volume": float(1100)})
    for i in range(2):
        ts = start_time_unix + ((32 + i) * 3600); eurusd_market_data.append({"timestamp": float(ts), "open": eurusd_market_data[-1]['close'], "high": eurusd_market_data[-1]['close'] + 0.00020, "low": eurusd_market_data[-1]['close'] - 0.00020, "close": eurusd_market_data[-1]['close'] + (0.00010 * (1 if i % 2 == 0 else -1)), "volume": float(1000)})
    broker.load_test_data("EURUSD", eurusd_market_data)
    graph = ForexTradingGraph(broker=broker)
    print("MANUALLY PLACING TEST ORDER for Scenario 1 to test broker TP...")
    broker.update_current_time(entry_bar_ts)
    broker.update_market_data({"EURUSD": Candlestick(**eurusd_market_data[30])})
    entry_order_response = broker.place_order(symbol="EURUSD", order_type=OrderType.MARKET, side=OrderSide.BUY, volume=0.01, stop_loss=None, take_profit=None)
    test_position_id = None
    if entry_order_response and entry_order_response.get("status") == "FILLED":
        print(f"Manual BUY order placed and filled: {entry_order_response}"); test_position_id = entry_order_response.get("position_id")
        actual_entry_price = entry_order_response.get("price")
        if actual_entry_price and test_position_id:
            pip_val, precision = broker._calculate_pip_value_and_precision("EURUSD"); sl_price = round(actual_entry_price - (20 * pip_val), precision); tp_price = round(actual_entry_price + (40 * pip_val), precision)
            broker.modify_order(test_position_id, stop_loss=sl_price, take_profit=tp_price); print(f"Manually set SL: {sl_price}, TP: {tp_price} for position {test_position_id}")
    else: print(f"Manual BUY order failed or not filled: {entry_order_response}"); return
    run_simulation_loop(graph_instance=graph, broker_instance=broker, currency_pair_to_trade="EURUSD", market_data_sequence=eurusd_market_data[31:])
    print("===== VERIFICATION FOR SCENARIO 1 =====")
    final_account_info = broker.get_account_info()
    if final_account_info:
        print(f"Final Balance: {final_account_info['balance']:.2f}"); day_trader_tp_pips_scenario1 = 40.0; pip_value_for_0_01_lots_eurusd = 0.10
        expected_profit = day_trader_tp_pips_scenario1 * pip_value_for_0_01_lots_eurusd
        print(f"Expected Profit (for {day_trader_tp_pips_scenario1} pip TP, 0.01 lots, 0 commission): ${expected_profit:.2f}"); print(f"Actual Profit: ${final_account_info['balance'] - 10000.0:.2f}")
        found_buy_fill = False; found_tp_close = False
        for event in broker.trade_history:
            if event.get("event_type") == "MARKET_ORDER_FILLED" and event.get("side") == "BUY": found_buy_fill = True; print(f"Found BUY Fill: {event}")
            if event.get("event_type") == "POSITION_CLOSED" and event.get("reason_for_close") == "TAKE_PROFIT_HIT": found_tp_close = True; print(f"Found TP Close: {event}")
        if found_buy_fill and found_tp_close: print("VERIFICATION: Winning BUY order filled and closed by TP successfully.")
        else: print("VERIFICATION ERROR: Winning BUY order TP scenario not fully verified in trade history.")
    else: print("VERIFICATION ERROR: Could not retrieve final account info.")
    print("==========================================")

def test_scenario_losing_sell_sl():
    print("\n\n===== SCENARIO 2: LOSING SELL MARKET ORDER (HITTING SL) =====")
    broker = setup_scenario_broker(initial_capital=10000.0, default_spread_pips={"EURUSD": 1.0}, commission_per_lot={"EURUSD": 0.0})
    start_time_unix = int(datetime.datetime(2023, 10, 2, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    eurusd_market_data: List[Dict[str, Any]] = []
    base_price = 1.08500
    for i in range(30):
        ts = start_time_unix + (i * 3600); eurusd_market_data.append({"timestamp": float(ts), "open": base_price - (i * 0.00010), "high": base_price - (i * 0.00010) + 0.00020, "low": base_price - (i * 0.00010) - 0.00050, "close": base_price - (i * 0.00010) - 0.00030, "volume": float(1000 + i * 10)})
    trigger_bar_price_close = eurusd_market_data[-1]['close']
    entry_bar_ts = start_time_unix + (30 * 3600)
    eurusd_market_data.append({"timestamp": float(entry_bar_ts), "open": trigger_bar_price_close, "high": trigger_bar_price_close + 0.00020, "low": trigger_bar_price_close - 0.00010, "close": trigger_bar_price_close - 0.00005, "volume": float(1200)})
    broker.update_current_time(entry_bar_ts); broker.update_market_data({"EURUSD": Candlestick(**eurusd_market_data[30])})
    print(f"Attempting to place SELL order at simulated time: {datetime.datetime.fromtimestamp(entry_bar_ts, tz=datetime.timezone.utc).isoformat()}")
    day_trader_sl_pips = 20.0; day_trader_tp_pips = 40.0
    sell_order_response = broker.place_order(symbol="EURUSD", order_type=OrderType.MARKET, side=OrderSide.SELL, volume=0.01, comment="Test SL Scenario - Manual Sell")
    position_id_to_track = None
    if sell_order_response and sell_order_response.get("status") == "FILLED":
        print(f"Manual SELL Order Filled: {sell_order_response}"); position_id_to_track = sell_order_response.get("position_id")
        if position_id_to_track:
            fill_price = sell_order_response['price']; pip_unit_value = broker._get_pip_value_for_sl_tp("EURUSD"); price_precision = broker._get_price_precision("EURUSD")
            sl_price = round(fill_price + (day_trader_sl_pips * pip_unit_value), price_precision); tp_price = round(fill_price - (day_trader_tp_pips * pip_unit_value), price_precision)
            print(f"Setting SL/TP for position {position_id_to_track}: SL={sl_price}, TP={tp_price}. Fill price: {fill_price}"); broker.modify_order(position_id_to_track, new_stop_loss=sl_price, new_take_profit=tp_price)
        else: print("ERROR: Could not get position_id from filled order to set SL/TP."); return
    else: print(f"ERROR: Manual SELL Order failed to fill: {sell_order_response}"); return
    sl_hit_bar_ts = entry_bar_ts + 3600
    eurusd_market_data.append({"timestamp": float(sl_hit_bar_ts), "open": eurusd_market_data[-1]['close'], "high": 1.08400, "low": eurusd_market_data[-1]['close'] - 0.00010, "close": 1.08380, "volume": float(1100)})
    for i in range(2):
        ts = sl_hit_bar_ts + ((i + 1) * 3600); eurusd_market_data.append({"timestamp": float(ts), "open": eurusd_market_data[-1]['close'], "high": eurusd_market_data[-1]['close'] + 0.00020, "low": eurusd_market_data[-1]['close'] - 0.00020, "close": eurusd_market_data[-1]['close'] + (0.00010 * (1 if i % 2 == 0 else -1)), "volume": float(1000)})
    broker.load_test_data("EURUSD", eurusd_market_data)
    graph = ForexTradingGraph(broker=broker)
    run_simulation_loop(graph_instance=graph, broker_instance=broker, currency_pair_to_trade="EURUSD", market_data_sequence=eurusd_market_data[31:])
    print("===== VERIFICATION FOR SCENARIO 2 =====")
    final_account_info = broker.get_account_info()
    if final_account_info:
        print(f"Final Balance: {final_account_info['balance']:.2f}"); day_trader_sl_pips_scenario2 = 20.0; pip_value_for_0_01_lots_eurusd = 0.10
        expected_loss = day_trader_sl_pips_scenario2 * pip_value_for_0_01_lots_eurusd
        print(f"Expected Loss (for {day_trader_sl_pips_scenario2} pip SL, 0.01 lots, 0 commission): ${expected_loss:.2f}"); actual_loss_from_balance = 10000.0 - final_account_info['balance']
        print(f"Actual Loss reflected in balance: ${actual_loss_from_balance:.2f}")
        found_sell_fill = False; found_sl_close = False
        for event in broker.trade_history:
            if event.get("event_type") == "MARKET_ORDER_FILLED" and event.get("side") == "SELL": found_sell_fill = True; print(f"Found SELL Fill: {event}")
            if event.get("event_type") == "POSITION_CLOSED" and event.get("reason_for_close") == "STOP_LOSS_HIT": found_sl_close = True; print(f"Found SL Close: {event}")
        if found_sell_fill and found_sl_close: print("VERIFICATION: Losing SELL order filled and closed by SL successfully.")
        else: print("VERIFICATION ERROR: Losing SELL order SL scenario not fully verified in trade history.")
    else: print("VERIFICATION ERROR: Could not retrieve final account info.")
    print("==========================================")

def test_scenario_pending_buy_limit():
    print("\n\n===== SCENARIO 3: PENDING BUY LIMIT ORDER FILLED & HITS TP =====")
    broker = setup_scenario_broker(initial_capital=10000.0, default_spread_pips={"EURUSD": 1.0}, commission_per_lot={"EURUSD": 0.0})
    limit_price = 1.08000; sl_pips = 15.0; tp_pips = 30.0
    pip_unit, precision = broker._calculate_pip_value_and_precision("EURUSD")
    actual_fill_price_if_limit_hit = round(limit_price + (broker._get_spread_in_price_terms("EURUSD") / 2), precision)
    sl_abs_price = round(actual_fill_price_if_limit_hit - (sl_pips * pip_unit), precision)
    tp_abs_price = round(actual_fill_price_if_limit_hit + (tp_pips * pip_unit), precision)
    start_time_unix = int(datetime.datetime(2023, 10, 3, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    eurusd_market_data: List[Dict[str, Any]] = []
    eurusd_market_data.append({"timestamp": float(start_time_unix), "open": 1.08100, "high": 1.08150, "low": 1.08050, "close": 1.08080, "volume": float(1000)})
    fill_trigger_bar_ts = start_time_unix + 3600
    eurusd_market_data.append({"timestamp": float(fill_trigger_bar_ts), "open": 1.08030, "high": 1.08040, "low": 1.07980, "close": 1.07990, "volume": float(1200)})
    tp_hit_bar_ts = start_time_unix + (2 * 3600)
    eurusd_market_data.append({"timestamp": float(tp_hit_bar_ts), "open": 1.08000, "high": 1.08350, "low": 1.07950, "close": 1.08320, "volume": float(1100)})
    eurusd_market_data.append({"timestamp": float(start_time_unix + (3 * 3600)), "open": 1.08320, "high": 1.08330, "low": 1.08300, "close": 1.08310, "volume": float(1000)})
    broker.load_test_data("EURUSD", eurusd_market_data)
    broker.update_current_time(eurusd_market_data[0]['timestamp'])
    broker.update_market_data({"EURUSD": Candlestick(**eurusd_market_data[0])})
    print(f"Attempting to place BUY LIMIT order at {limit_price}, effective fill target {actual_fill_price_if_limit_hit}, SL {sl_abs_price}, TP {tp_abs_price} at simulated time: {datetime.datetime.fromtimestamp(eurusd_market_data[0]['timestamp'], tz=datetime.timezone.utc).isoformat()}")
    buy_limit_response = broker.place_order(symbol="EURUSD", order_type=OrderType.LIMIT, side=OrderSide.BUY, volume=0.01, price=limit_price, stop_loss=sl_abs_price, take_profit=tp_abs_price, comment="Test BUY LIMIT Scenario")
    if not (buy_limit_response and buy_limit_response['status'] == "PENDING"): print(f"ERROR: BUY LIMIT Order failed to place: {buy_limit_response}"); return
    print(f"BUY LIMIT Order Placed: {buy_limit_response}")
    graph = ForexTradingGraph(broker=broker)
    run_simulation_loop(graph_instance=graph, broker_instance=broker, currency_pair_to_trade="EURUSD", market_data_sequence=eurusd_market_data[1:])
    print("===== VERIFICATION FOR SCENARIO 3 =====")
    final_account_info = broker.get_account_info()
    if final_account_info:
        print(f"Final Balance: {final_account_info['balance']:.2f}"); pip_value_for_0_01_lots_eurusd = 0.10; expected_profit = tp_pips * pip_value_for_0_01_lots_eurusd
        print(f"Expected Profit (for {tp_pips} pip TP, 0.01 lots, 0 commission): ${expected_profit:.2f}"); print(f"Actual Profit: ${final_account_info['balance'] - 10000.0:.2f}")
        found_pending_placed = False; found_pending_filled = False; found_tp_close = False; position_id_of_filled_order = None
        for event in broker.trade_history:
            if event.get("event_type") == "PENDING_ORDER_PLACED" and event.get("type") == OrderType.LIMIT.value and event.get("side") == OrderSide.BUY.value and event.get("order_id") == buy_limit_response['order_id']: found_pending_placed = True; print(f"Found Pending Placed: {event}")
            if event.get("event_type") == "PENDING_ORDER_FILLED" and event.get("original_order_id") == buy_limit_response['order_id']: found_pending_filled = True; position_id_of_filled_order = event.get("position_id"); print(f"Found Pending Filled, new PosID {position_id_of_filled_order}: {event}")
            if event.get("event_type") == "POSITION_CLOSED" and event.get("reason_for_close") == "TAKE_PROFIT_HIT":
                if event.get("position_id") == position_id_of_filled_order and position_id_of_filled_order is not None: found_tp_close = True; print(f"Found TP Close for previously filled pending order: {event}")
        if found_pending_placed and found_pending_filled and found_tp_close: print("VERIFICATION: Pending BUY LIMIT order placed, filled, and hit TP successfully.")
        else: print(f"VERIFICATION ERROR: Pending BUY LIMIT TP scenario not fully verified. Placed:{found_pending_placed}, Filled:{found_pending_filled}, TP Closed:{found_tp_close}")
    else: print("VERIFICATION ERROR: Could not retrieve final account info for Scenario 3.")
    print("===========================================")

def test_scenario_margin_call():
    print("\n\n===== SCENARIO 4: MARGIN CALL LIQUIDATION =====")
    initial_cap = 200.0; leverage_sim = 100; stop_out_lvl_pct = 50.0
    broker = setup_scenario_broker(initial_capital=initial_cap, leverage=leverage_sim, default_spread_pips={"EURUSD": 1.0}, commission_per_lot={"EURUSD": 0.0}, stop_out_level=stop_out_lvl_pct)
    start_time_unix = int(datetime.datetime(2023, 10, 4, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
    eurusd_market_data: List[Dict[str, Any]] = []
    entry_bar_price = 1.08000
    eurusd_market_data.append({"timestamp": float(start_time_unix), "open": entry_bar_price, "high": entry_bar_price + 0.00050, "low": entry_bar_price - 0.00050, "close": entry_bar_price, "volume": float(1000)})
    adverse_move_bar_ts = start_time_unix + 3600; price_after_drop = entry_bar_price - 0.01000
    eurusd_market_data.append({"timestamp": float(adverse_move_bar_ts), "open": entry_bar_price, "high": entry_bar_price, "low": price_after_drop, "close": price_after_drop, "volume": float(1500)})
    further_move_bar_ts = start_time_unix + (2 * 3600); price_further_drop = price_after_drop - 0.00050
    eurusd_market_data.append({"timestamp": float(further_move_bar_ts), "open": price_after_drop, "high": price_after_drop, "low": price_further_drop, "close": price_further_drop, "volume": float(1200)})
    broker.load_test_data("EURUSD", eurusd_market_data)
    broker.update_current_time(eurusd_market_data[0]['timestamp'])
    broker.update_market_data({"timestamp": datetime.datetime.fromtimestamp(eurusd_market_data[0]['timestamp'], tz=datetime.timezone.utc), "bars": {"EURUSD": Candlestick(**eurusd_market_data[0])}})
    trade_volume = 0.03
    print(f"Attempting to place BUY order for {trade_volume} lots at simulated time: {datetime.datetime.fromtimestamp(eurusd_market_data[0]['timestamp'], tz=datetime.timezone.utc).isoformat()}")
    buy_order_response = broker.place_order(symbol="EURUSD", order_type=OrderType.MARKET, side=OrderSide.BUY, volume=trade_volume, stop_loss=None, take_profit=None, comment="Test Margin Call Scenario - Manual BUY")
    position_id_to_track = None
    if not (buy_order_response and buy_order_response.get("status") == "FILLED"): print(f"ERROR: Manual BUY Order for margin call test failed to fill: {buy_order_response}"); return
    print(f"Manual BUY Order Filled: {buy_order_response}"); position_id_to_track = buy_order_response.get("position_id")
    if not position_id_to_track: print("ERROR: Could not retrieve position_id for margin call test from order response."); return
    graph = ForexTradingGraph(broker=broker)
    print(f"Account Info before adverse move (after order placement): {broker.get_account_info()}")
    run_simulation_loop(graph_instance=graph, broker_instance=broker, currency_pair_to_trade="EURUSD", market_data_sequence=eurusd_market_data[1:])
    print("===== VERIFICATION FOR SCENARIO 4 (MARGIN CALL) =====")
    final_account_info = broker.get_account_info()
    print(f"Final Account Info: {final_account_info}")
    found_margin_call_trigger = False; found_liquidation_closure = False; liquidated_pos_id_in_history = None
    for event in broker.trade_history:
        print(f"History Event: {event}")
        if event.get("event_type") == "MARGIN_CALL_STOP_OUT_TRIGGERED": found_margin_call_trigger = True
        if event.get("event_type") == "POSITION_CLOSED" and event.get("reason_for_close") == "MARGIN_CALL_LIQUIDATION": found_liquidation_closure = True; liquidated_pos_id_in_history = event.get("position_id")
    if found_margin_call_trigger: print("VERIFICATION: MARGIN_CALL_STOP_OUT_TRIGGERED event found.")
    else: print("VERIFICATION ERROR: MARGIN_CALL_STOP_OUT_TRIGGERED event NOT found.")
    if found_liquidation_closure:
        print(f"VERIFICATION: POSITION_CLOSED due to MARGIN_CALL_LIQUIDATION (Pos ID: {liquidated_pos_id_in_history}) event found.")
        if liquidated_pos_id_in_history == position_id_to_track: print("VERIFICATION: Correct position was liquidated.")
        else: print(f"VERIFICATION WARNING: A position was liquidated ({liquidated_pos_id_in_history}), but ID doesn't match tracked test position ID ({position_id_to_track}).")
    else: print("VERIFICATION ERROR: No POSITION_CLOSED due to MARGIN_CALL_LIQUIDATION event found.")
    open_positions_final = broker.get_open_positions()
    if not any(p['position_id'] == position_id_to_track for p in open_positions_final): print(f"VERIFICATION: Tracked position {position_id_to_track} is confirmed closed.")
    else: print(f"VERIFICATION ERROR: Tracked position {position_id_to_track} is still listed as open.")
    if final_account_info and (final_account_info['margin_level'] == float('inf') or final_account_info['margin_level'] > stop_out_lvl_pct) : print(f"VERIFICATION: Final margin level ({final_account_info['margin_level']}) is healthy or no positions open.")
    elif final_account_info: print(f"VERIFICATION WARNING: Final margin level ({final_account_info['margin_level']}) is still critical (Stop Out: {stop_out_lvl_pct}). Liquidation might have been incomplete or equity very low.")
    else: print("VERIFICATION ERROR: Could not retrieve final account info for margin level check.")
    print("==================================================")

def test_scenario_cross_currency_pnl():
    print("\n\n===== SCENARIO 5: CROSS-CURRENCY P&L (AUDJPY BUY in USD account) =====")
    broker = setup_scenario_broker(initial_capital=10000.0, default_spread_pips={"AUDJPY": 1.5, "AUDUSD": 0.8, "USDJPY": 0.7, "default": 1.0}, commission_per_lot={"default": 0.0})
    broker.account_currency = "USD"
    bar0_ts = int(datetime.datetime(2023, 10, 5, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp()); bar1_ts = bar0_ts + 3600
    audjpy_data = [{"timestamp": float(bar0_ts), "open": 98.00, "high": 98.10, "low": 97.90, "close": 98.05, "volume": 1000.0}, {"timestamp": float(bar1_ts), "open": 98.05, "high": 98.60, "low": 98.00, "close": 98.55, "volume": 1200.0}]
    audusd_data = [{"timestamp": float(bar0_ts), "open": 0.66000, "high": 0.66050, "low": 0.65950, "close": 0.66010, "volume": 1000.0}, {"timestamp": float(bar1_ts), "open": 0.66010, "high": 0.66250, "low": 0.66000, "close": 0.66220, "volume": 1200.0}]
    usdjpy_data = [{"timestamp": float(bar0_ts), "open": 148.00, "high": 148.10, "low": 147.90, "close": 148.05, "volume": 1000.0}, {"timestamp": float(bar1_ts), "open": 148.05, "high": 148.90, "low": 148.00, "close": 148.85, "volume": 1200.0}]
    broker.load_test_data("AUDJPY", audjpy_data); broker.load_test_data("AUDUSD", audusd_data); broker.load_test_data("USDJPY", usdjpy_data)
    broker.update_current_time(bar0_ts)
    broker.update_market_data({"timestamp": datetime.datetime.fromtimestamp(bar0_ts, tz=datetime.timezone.utc), "bars": {"AUDJPY": audjpy_data[0], "AUDUSD": audusd_data[0], "USDJPY": usdjpy_data[0]}})
    trade_volume = 0.01
    print(f"Attempting to place BUY order for {trade_volume} lots AUDJPY at simulated time of Bar 0...")
    buy_order_response = broker.place_order(symbol="AUDJPY", order_type=OrderType.MARKET, side=OrderSide.BUY, volume=trade_volume, comment="Test Cross-Currency PNL - Manual BUY AUDJPY")
    position_id_to_track = None; entry_price_actual = None
    if not (buy_order_response and buy_order_response.get("status") == "FILLED"): print(f"ERROR: Manual BUY Order for cross-currency test failed to fill: {buy_order_response}"); return
    print(f"Manual BUY Order Filled: {buy_order_response}"); entry_price_actual = buy_order_response['price']; position_id_to_track = buy_order_response.get("position_id")
    if not position_id_to_track: print("ERROR: Could not retrieve position_id for cross-currency test from order response."); return
    print(f"\nAdvancing market to Bar 1 time: {datetime.datetime.fromtimestamp(bar1_ts, tz=datetime.timezone.utc).isoformat()}")
    broker.update_current_time(bar1_ts)
    broker.update_market_data({"timestamp": datetime.datetime.fromtimestamp(bar1_ts, tz=datetime.timezone.utc), "bars": {"AUDJPY": audjpy_data[1], "AUDUSD": audusd_data[1], "USDJPY": usdjpy_data[1]}})
    broker.check_for_sl_tp_triggers(); broker.process_pending_orders(); broker.check_for_margin_call()
    print(f"Attempting to close position {position_id_to_track} at simulated time of Bar 1...")
    close_order_response = broker.close_order(position_id_to_track, volume=trade_volume)
    print(f"Close Order Response: {close_order_response}")
    actual_close_price = None
    if close_order_response and close_order_response['status'] == "CLOSED":
        actual_close_price = close_order_response.get("price")
        if actual_close_price is None:
            for event in reversed(broker.get_trade_history()):
                if event.get("event_type") == "POSITION_CLOSED" and event.get("position_id") == position_id_to_track: actual_close_price = event.get("close_price"); break
        if actual_close_price is None: print("ERROR: Could not retrieve actual close price from history or response for verification."); return
    else: print("ERROR: Position did not close as expected."); return
    print("===== VERIFICATION FOR SCENARIO 5 (CROSS-CURRENCY P&L) =====")
    final_account_info = broker.get_account_info(); print(f"Final Account Info: {final_account_info}")
    audjpy_info = broker._get_symbol_info("AUDJPY")
    if not audjpy_info or entry_price_actual is None or actual_close_price is None : print("ERROR: Missing critical info for PNL verification (symbol_info, entry_price, or close_price)."); return
    contract_size_audjpy = audjpy_info['contract_size_units']; price_diff_audjpy = actual_close_price - entry_price_actual
    expected_pnl_in_jpy = price_diff_audjpy * contract_size_audjpy * trade_volume
    usdjpy_rate_at_close = None
    if "USDJPY" in broker.current_market_data and broker.current_market_data["USDJPY"]: usdjpy_rate_at_close = broker.current_market_data["USDJPY"]['close']
    expected_pnl_in_usd_manual: Any = "N/A"
    if usdjpy_rate_at_close and usdjpy_rate_at_close != 0:
        expected_pnl_in_usd_manual = expected_pnl_in_jpy / usdjpy_rate_at_close
        print(f"Details for manual verification: Entry AUDJPY: {entry_price_actual}, Close AUDJPY: {actual_close_price}"); print(f"Price Diff (AUDJPY): {price_diff_audjpy:.{audjpy_info['price_precision']}f}"); print(f"P/L in JPY (direct calc): {expected_pnl_in_jpy:.2f}"); print(f"USDJPY rate at close: {usdjpy_rate_at_close}"); print(f"Expected P/L in USD (manual calc): {expected_pnl_in_usd_manual:.2f}")
    else: print("ERROR: Could not get USDJPY rate for P/L conversion verification.")
    actual_pnl_usd = final_account_info['balance'] - initial_cap; print(f"Actual P/L in USD (from balance change): {actual_pnl_usd:.2f}")
    found_audjpy_buy_fill = False; found_audjpy_close = False; realized_pnl_from_history = None
    for event in broker.trade_history:
        if event.get("event_type") == "MARKET_ORDER_FILLED" and event.get("symbol") == "AUDJPY" and event.get("side") == OrderSide.BUY.value: found_audjpy_buy_fill = True
        if event.get("event_type") == "POSITION_CLOSED" and event.get("symbol") == "AUDJPY" and event.get("position_id") == position_id_to_track : found_audjpy_close = True; realized_pnl_from_history = event.get("realized_pnl")
    if found_audjpy_buy_fill and found_audjpy_close:
        print(f"VERIFICATION: Cross-currency AUDJPY BUY trade filled and closed. Broker Realized P/L: {realized_pnl_from_history:.2f} USD")
        if isinstance(expected_pnl_in_usd_manual, float) and realized_pnl_from_history is not None:
            if abs(expected_pnl_in_usd_manual - realized_pnl_from_history) < 0.01: print("VERIFICATION SUCCESS: Broker P/L matches expected P/L.")
            else: print(f"VERIFICATION WARNING: Broker P/L ({realized_pnl_from_history:.2f}) differs from expected ({expected_pnl_in_usd_manual:.2f}).")
        else: print("VERIFICATION NOTE: Could not automatically compare expected P/L with broker P/L.")
    else: print(f"VERIFICATION ERROR: Cross-currency P/L scenario not fully verified. BuyFill:{found_audjpy_buy_fill}, Closed:{found_audjpy_close}")
    print("==================================================")

def main():
    print("--- Main Test Runner for Forex Trading Scenarios ---")

    test_scenario_winning_buy_tp()
    test_scenario_losing_sell_sl()
    test_scenario_pending_buy_limit()
    test_scenario_margin_call() # Add this call

if __name__ == "__main__":
>>>>>>> REPLACE
