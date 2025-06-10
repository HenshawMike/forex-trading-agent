import datetime
import sys
import os

# Adjust the Python path to include the TradingAgents directory
# This allows a script in the root to import modules from the tradingagents package
# This is a common pattern for test/run scripts located at the project root.
current_dir = os.path.dirname(os.path.abspath(__file__))
# Assuming the 'tradingagents' package is at the same level as this script,
# or one level down if this script is in a 'tests' folder, for example.
# If TradingAgents/ is the project root and contains run_forex_test_graph.py
# and the package is TradingAgents/tradingagents/, then TradingAgents/ needs to be in path.
project_root = current_dir # If script is in TradingAgents/
# project_root = os.path.dirname(current_dir) # If script is in TradingAgents/tests/
sys.path.insert(0, project_root)


try:
    from tradingagents.graph.forex_trading_graph import ForexTradingGraph
    from tradingagents.broker_interface.simulated_broker import SimulatedBroker # Import
    from tradingagents.forex_utils.forex_states import ForexFinalDecision # For type hinting if needed
except ImportError as e:
    print(f"ImportError: {e}. Please ensure that the TradingAgents package is correctly structured")
    print("and that this script is run from a location where 'tradingagents' can be imported.")
    print(f"Current sys.path includes: {sys.path[0]}")
    sys.exit(1)

def main():
    print("--- Starting Forex Trading Graph Test Script ---")

    # Instantiate SimulatedBroker
    sim_broker = SimulatedBroker()

    # Define sample inputs
    currency_pair_to_test = "EURUSD"
    simulated_time_iso = "2023-10-27T10:00:00+00:00" # Fixed dummy ISO time

    # Update the simulated broker's current time to match the test time
    # This is important for get_current_price and get_historical_data in the sim broker
    simulated_dt_obj = datetime.datetime.fromisoformat(simulated_time_iso.replace('Z', '+00:00'))
    sim_broker.update_current_time(simulated_dt_obj.timestamp())


    # Initialize the graph, passing the broker
    try:
        forex_graph_instance = ForexTradingGraph(broker=sim_broker) # Pass broker
    except Exception as e:
        print(f"Error initializing ForexTradingGraph: {e}")
        return

    print(f"\nInvoking graph for: {currency_pair_to_test} at {simulated_time_iso}")

    # Invoke the graph
    try:
        # The type hint ForexFinalDecision might need to be Optional if invoke_graph can return None on error
        final_decision_obj: Optional[ForexFinalDecision] = forex_graph_instance.invoke_graph(
            currency_pair_to_test,
            simulated_time_iso
        )
        # For pretty print, it's fine if it's None, the check `if final_decision_obj:` handles it
        final_decision = final_decision_obj
    except Exception as e:
        print(f"Error invoking ForexTradingGraph: {e}")
        # Potentially print more detailed traceback if in debug mode
        import traceback
        traceback.print_exc()
        return

    print("\n--- Forex Graph Execution Complete ---")

    if final_decision: # final_decision is now final_decision_obj
        print("\n=== Final Decision Received ===")
        # Pretty print the TypedDict
        for key, value in final_decision.items(): # Use final_decision here as it's the one for printing
            if isinstance(value, list) and value: # If it's a list of proposals
                print(f"  {key}:")
                for item in value:
                    if isinstance(item, dict): # e.g. a proposal_id string, or a dict itself
                        print(f"    - {item}")
                    else:
                        print(f"    - {item}")
            elif isinstance(value, dict) and value: # If it's a dictionary (like supporting_data)
                 print(f"  {key}:")
                 for sub_key, sub_value in value.items():
                      print(f"    {sub_key}: {sub_value}")
            else:
                print(f"  {key}: {value}")
    else:
        print("\n=== No final decision was returned or an error occurred. ===")
        print("This might be expected if the graph logic leads to an END state")
        print("without populating the 'forex_final_decision' field in the state,")
        print("or if an error was caught and handled by returning None.")

    print("\n--- End of Forex Trading Graph Test Script ---")

if __name__ == "__main__":
    main()
