import datetime
import time
import uuid
import os
import sys
from typing import List, Dict, Any, Optional

# --- Path Adjustments ---
# Assuming this script is in TradingAgents/ and the tradingagents module is in TradingAgents/tradingagents/
# and ui_backend is in TradingAgents/ui_backend/
current_dir = os.path.dirname(os.path.abspath(__file__)) # Should be TradingAgents/
project_root = current_dir # This is TradingAgents/

# Add project_root to sys.path to allow imports like `from tradingagents.graph...`
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add project_root to sys.path to allow imports like `from ui_backend.api_server...`
# This assumes api_server.py is directly under ui_backend.
# If ui_backend is a package, this structure is fine.
if project_root not in sys.path: # Though it should be already added by the above
    sys.path.insert(0, project_root)

try:
    from tradingagents.graph.forex_trading_graph import ForexTradingGraph
    from tradingagents.broker_interface.simulated_broker import SimulatedBroker
    from tradingagents.forex_utils.forex_states import (
        ForexFinalDecision, OrderSide, OrderType, Candlestick
    )
    # Import shared stores from the UI backend
    # This requires ui_backend to be structured in a way that api_server's globals are importable,
    # or these stores are defined in a shared location.
    # For this task, we assume they are directly importable from api_server.
    from ui_backend.api_server import trade_proposals_store, trade_decisions_queue, new_proposals_for_websocket_queue
except ImportError as e:
    print(f"ImportError in live_trading_orchestrator: {e}")
    print(f"Current sys.path: {sys.path}")
    print(f"Attempted to load from project_root: {project_root}")
    print("Ensure that TradingAgents/ is in your PYTHONPATH or run this script from within TradingAgents/ directory.")
    print("Also ensure ui_backend/api_server.py exists and defines the shared stores.")
    sys.exit(1)

# --- Broker and Graph Initialization ---
def setup_dependencies(initial_capital: float = 10000.0) -> tuple[SimulatedBroker, ForexTradingGraph]:
    """Initializes and returns SimulatedBroker and ForexTradingGraph instances."""
    print("Setting up broker and graph dependencies...")
    broker = SimulatedBroker(initial_capital=initial_capital)
    # Configure broker further if needed (e.g., spreads, commissions)
    broker.default_spread_pips = {"EURUSD": 0.5, "default": 1.0}
    broker.commission_per_lot = {"EURUSD": 0.0, "default": 0.0}

    graph_instance = ForexTradingGraph(broker=broker)
    print("Broker and graph initialized.")
    return broker, graph_instance

# --- Market Data ---
# Simplified market data sequence for EURUSD (adapted from test_scenario_winning_buy_tp)
# We'll loop over this data.
EURUSD_MARKET_DATA_SEQUENCE: List[Dict[str, Any]] = []
_start_time_unix = int(datetime.datetime(2023, 10, 1, 10, 0, 0, tzinfo=datetime.timezone.utc).timestamp())
_base_price = 1.08000

# Create a small sequence of 10 bars
for i in range(10): # Reduced number of bars for faster cycling in live sim
    ts = _start_time_unix + (i * 60) # Using 1-minute bars for faster simulation
    bar_data = {
        "timestamp": float(ts),
        "open": _base_price + (i * 0.00005),
        "high": _base_price + (i * 0.00005) + 0.00020,
        "low": _base_price + (i * 0.00005) - 0.00010,
        "close": _base_price + (i * 0.00005) + 0.00010,
        "volume": float(100 + i * 5)
    }
    EURUSD_MARKET_DATA_SEQUENCE.append(bar_data)

# --- Helper Functions for Enum Mapping ---
def map_side_to_enum(side_str: Optional[str]) -> Optional[OrderSide]:
    if not side_str:
        return None
    side_str_lower = side_str.lower()
    if side_str_lower == 'buy':
        return OrderSide.BUY
    elif side_str_lower == 'sell':
        return OrderSide.SELL
    print(f"Warning: Unknown side string '{side_str}'. Cannot map to OrderSide enum.")
    return None # Or raise ValueError

def map_type_to_enum(type_str: Optional[str]) -> OrderType:
    if not type_str:
        return OrderType.MARKET # Default to MARKET if not specified
    type_str_lower = type_str.lower()
    if type_str_lower == 'market':
        return OrderType.MARKET
    elif type_str_lower == 'limit':
        return OrderType.LIMIT
    elif type_str_lower == 'stop':
        return OrderType.STOP
    # Add other OrderType enum members if they exist and are used
    print(f"Warning: Unknown type string '{type_str}'. Defaulting to OrderType.MARKET.")
    return OrderType.MARKET # Default, consider proper error handling or raising ValueError

# --- Main Orchestration Loop ---
def run_orchestrator(
    graph_instance: ForexTradingGraph,
    broker_instance: SimulatedBroker,
    currency_pair: str,
    market_data_sequence: List[Dict[str, Any]]
):
    """Main orchestration loop for live trading simulation."""
    print(f"Starting orchestrator for {currency_pair}...")
    data_idx = 0

    while True:
        # Cycle through market data
        if data_idx >= len(market_data_sequence):
            data_idx = 0
            print("Cycling market data sequence...")

        bar_dict = market_data_sequence[data_idx]
        current_bar_candlestick = Candlestick(**bar_dict)
        bar_timestamp_unix = current_bar_candlestick['timestamp']
        bar_datetime_obj = datetime.datetime.fromtimestamp(bar_timestamp_unix, tz=datetime.timezone.utc)
        bar_iso_timestamp = bar_datetime_obj.isoformat()

        print(f"\n--- Orchestrator Cycle: Bar {data_idx + 1}/{len(market_data_sequence)} | Time: {bar_iso_timestamp} | {currency_pair} C: {current_bar_candlestick['close']} ---")

        # 1. Update broker time and market data
        broker_instance.update_current_time(bar_timestamp_unix)
        broker_instance.update_market_data({currency_pair: current_bar_candlestick})

        # 2. Broker processes internal events
        broker_instance.process_pending_orders()
        broker_instance.check_for_sl_tp_triggers()

        # 3. Prepare graph state and invoke graph
        current_iteration_state = {
            "currency_pair": currency_pair,
            "current_simulated_time": bar_iso_timestamp,
            # Initialize other state keys as expected by the graph, potentially with defaults
            "sub_agent_tasks": [], "market_regime": "SimulatedLive",
            "scalper_proposal": None, "day_trader_proposal": None,
            "swing_trader_proposal": None, "position_trader_proposal": None,
            "proposals_from_sub_agents": [], "aggregated_proposals_for_meta_agent": None,
            "forex_final_decision": None, "error_message": None
        }

        print("Invoking trading graph...")
        final_state_for_bar = graph_instance.graph.invoke(current_iteration_state)
        final_decision: Optional[ForexFinalDecision] = final_state_for_bar.get("forex_final_decision")

        # 4. Proposal Handling
        if final_decision and final_decision.get('action') in ["EXECUTE_BUY", "EXECUTE_SELL", "PROPOSE_BUY", "PROPOSE_SELL"]: # Assuming these actions mean a proposal
            trade_id = str(uuid.uuid4())
            action = final_decision['action']

            # Determine side and order type (assuming market orders for now if not specified)
            side = 'buy' if "BUY" in action else 'sell'
            order_type_value = final_decision.get('order_type')
            if isinstance(order_type_value, OrderType):
                order_type_str = order_type_value.value
            elif isinstance(order_type_value, str):
                order_type_str = order_type_value
            else: # Default if not specified or unclear
                order_type_str = OrderType.MARKET.value


            proposal_data = {
                "trade_id": trade_id,
                "pair": final_decision.get('currency_pair', currency_pair),
                "side": side,
                "type": order_type_str,
                "entry_price": final_decision.get('entry_price'), # Can be None for market orders
                "sl": final_decision.get('stop_loss'),
                "tp": final_decision.get('take_profit'),
                "calculated_position_size": final_decision.get('position_size', 0.01), # Default size
                "meta_rationale": final_decision.get('meta_rationale', 'No rationale provided.'),
                "sub_agent_confidence": final_decision.get('meta_confidence_score', 0.5), # Using meta_confidence as placeholder
                "risk_assessment": { # Basic structure, adapt if more details in ForexFinalDecision
                    "risk_score": 0.3, # Placeholder
                    "assessment_summary": final_decision.get('meta_assessed_risk_level', 'Medium Risk'), # Placeholder
                    "proceed_with_trade": True, # Default
                    "recommended_modifications": {}
                },
                "status": "pending_approval" # Critical for UI
            }

            trade_proposals_store[trade_id] = proposal_data
            print(f"Added trade proposal {trade_id} to store: {proposal_data['side']} {proposal_data['pair']} @ {proposal_data.get('entry_price', 'Market')}")

            # Add to WebSocket queue for real-time UI update
            new_proposals_for_websocket_queue.append(proposal_data.copy())
            print(f"Orchestrator: Added proposal {proposal_data['trade_id']} to WebSocket queue.")
        elif final_decision:
            print(f"Graph decision: {final_decision.get('action')}. Not a new trade proposal.")
        else:
            print("Graph did not produce a final decision.")

        # 5. Decision Handling (Basic Logging & Removal)
        if trade_decisions_queue: # Check if queue is not empty
            print(f"Orchestrator: Detected {len(trade_decisions_queue)} items in decisions queue. Processing one.")
            # Iterate over a copy for safe removal
            decisions_to_process = list(trade_decisions_queue) # Create a copy for safe iteration
            for decision in decisions_to_process: # This loop will process all items in the queue at this snapshot
                trade_id = decision.get('trade_id')
                decision_action = decision.get('decision')
                print(f"Orchestrator: Processing decision: {decision_action} for trade_id: {trade_id}")

                if decision_action == 'approved':
                    proposal_data = trade_proposals_store.get(trade_id)
                    if proposal_data:

                        order_side_enum = map_side_to_enum(proposal_data.get('side'))
                        order_type_enum = map_type_to_enum(proposal_data.get('type'))

                        if order_side_enum is None:
                            print(f"Orchestrator ERROR: Could not map side '{proposal_data.get('side')}' for trade {trade_id}. Skipping placement.")
                        else:
                            # Ensure required fields are present
                            symbol = proposal_data.get('pair')
                            volume = proposal_data.get('calculated_position_size')

                            if not symbol or volume is None:
                                print(f"Orchestrator ERROR: Missing symbol or volume for trade {trade_id}. Data: {proposal_data}. Skipping placement.")
                            else:
                                print(f"Orchestrator: Preparing to place order for trade_id: {trade_id}")
                                print(f"  Symbol: {symbol}")
                                print(f"  Type: {order_type_enum}")
                                print(f"  Side: {order_side_enum}")
                                print(f"  Volume: {float(volume)}")
                                print(f"  SL: {proposal_data.get('sl')}")
                                print(f"  TP: {proposal_data.get('tp')}")
                                current_entry_price = proposal_data.get('entry_price')
                                if order_type_enum == OrderType.LIMIT or order_type_enum == OrderType.STOP:
                                     print(f"  Price: {current_entry_price}")

                                order_response = broker_instance.place_order(
                                    symbol=symbol,
                                    order_type=order_type_enum,
                                    side=order_side_enum,
                                    volume=float(volume), # Ensure volume is float
                                    stop_loss=proposal_data.get('sl'), # Pass directly
                                    take_profit=proposal_data.get('tp'), # Pass directly
                                    price=current_entry_price if (order_type_enum == OrderType.LIMIT or order_type_enum == OrderType.STOP) else None,
                                    comment=f"User approved trade: {trade_id}"
                                )
                                print(f"Orchestrator: Broker response for trade {trade_id}: {order_response}")
                                # Optionally, update proposal_data status in trade_proposals_store if broker accepts
                                # e.g., proposal_data['status'] = 'execution_sent' or similar
                else:
                    print(f"Orchestrator ERROR: Proposal {trade_id} not found in store for approval.")

            elif decision_action == 'rejected':
                print(f"Orchestrator: Trade {trade_id} was rejected by user.")
                # Optionally, update status in trade_proposals_store
                if trade_id in trade_proposals_store:
                    trade_proposals_store[trade_id]['status'] = 'user_rejected' # Mark as user_rejected

            # Attempt to remove the decision from the original queue
            try:
                trade_decisions_queue.remove(decision)
                # print(f"Orchestrator: Decision for {trade_id} removed from queue.")
            except ValueError:
                # This might happen if another part of the system could also remove items,
                # or if the item was already removed in a previous iteration (less likely with current logic).
                print(f"Orchestrator WARNING: Decision for {trade_id} was already removed from queue or not found for removal.")

        # 6. Broker checks for margin calls
        broker_instance.check_for_margin_call()

        # 7. Account Info Logging (optional)
        # eob_account_info = broker_instance.get_account_info()
        # if eob_account_info:
        #      print(f"EOB Account: Bal: {eob_account_info['balance']:.2f}, Eq: {eob_account_info['equity']:.2f}, MrgLvl: {eob_account_info.get('margin_level', 'N/A')}%")

        data_idx += 1
        time.sleep(5) # Simulate delay between bars

# --- Main Execution Block ---
if __name__ == "__main__":
    print("Initializing live trading orchestrator...")

    # Ensure ui_backend path is correct for direct execution if api_server is not a package
    # The path adjustment at the top should handle most cases.
    # If 'ui_backend.api_server' still fails, it might be due to how Python resolves modules
    # when running a script directly vs importing it.
    # For example, if TradingAgents/ is the project root and contains ui_backend/ and this script,
    # then `from ui_backend.api_server import ...` should work if TradingAgents/ is in sys.path.

    broker, graph = setup_dependencies()

    currency_pair_to_trade = "EURUSD" # Define the pair we are trading

    # Start the orchestration loop
    try:
        run_orchestrator(
            graph_instance=graph,
            broker_instance=broker,
            currency_pair=currency_pair_to_trade,
            market_data_sequence=EURUSD_MARKET_DATA_SEQUENCE
        )
    except KeyboardInterrupt:
        print("\nOrchestrator stopped by user.")
    except Exception as e:
        print(f"\nAn error occurred in the orchestrator: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Orchestrator shutting down.")
