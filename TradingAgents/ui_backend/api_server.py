from flask import Flask, jsonify, request
from flask_cors import CORS # For handling Cross-Origin Resource Sharing
from flask_socketio import SocketIO
import uuid
import threading
import time
import os
import json # For file operations
from datetime import datetime, timezone


app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing React dev server to call it
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Configuration for User Strategies ---
# __file__ is api_server.py, dirname(__file__) is TradingAgents/ui_backend/
# os.path.join(os.path.dirname(__file__), '..') goes up to TradingAgents/
# Then, join with 'user_strategies' to get TradingAgents/user_strategies/
STRATEGIES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'user_strategies'))

def _ensure_strategies_dir():
    """Ensures that the STRATEGIES_DIR exists."""
    os.makedirs(STRATEGIES_DIR, exist_ok=True)

_ensure_strategies_dir() # Call once at app startup

# For inter-process communication (simulated as in-memory Python lists for now)
trade_proposals_store = {} # Key: trade_id, Value: trade_proposal_details
trade_decisions_queue = [] # List of {'trade_id': trade_id, 'decision': 'approved'/'rejected'}
new_proposals_for_websocket_queue = [] # Queue for proposals to be sent via WebSocket


@socketio.on('connect')
def handle_connect():
    print('Client connected to WebSocket')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected from WebSocket')

def watch_proposal_queue():
    while True:
        if new_proposals_for_websocket_queue:
            proposal = new_proposals_for_websocket_queue.pop(0) # FIFO
            print(f"WebSocket: Emitting new proposal: {proposal.get('trade_id')}")
            socketio.emit('new_trade_proposal', proposal)
        time.sleep(0.5) # Check queue periodically

@app.route('/api/pending_trades', methods=['GET'])
def pending_trades():
    global trade_proposals_store
    print(f"API: /api/pending_trades called.")
    # Filter to only return trades that are still 'pending_approval' for the UI
    pending_list = [trade for trade in trade_proposals_store.values() if trade['status'] == 'pending_approval']
    print(f"Returning {len(pending_list)} trades that are pending approval.")
    return jsonify(pending_list)

@app.route('/api/trades/<string:trade_id>/approve', methods=['POST'])
def approve_trade(trade_id):
    global trade_proposals_store
    global trade_decisions_queue
    if trade_id in trade_proposals_store:
        trade = trade_proposals_store[trade_id]
        if trade['status'] == 'pending_approval':
            trade['status'] = 'approved'
            print(f"API Server: Trade {trade_id} status updated to approved in store.") # Added log
            trade_decisions_queue.append({'trade_id': trade_id, 'decision': 'approved'})
            print(f"API Server: Decision for {trade_id} (approved) added to decisions queue. Queue size: {len(trade_decisions_queue)}") # Added log
            # Original log below, can be kept or removed if redundant
            print(f"API: Trade {trade_id} approved by user. Decision queued.")
            return jsonify({"status": "success", "message": f"Trade {trade_id} approved."}), 200
        else:
            print(f"API: Trade {trade_id} was not pending approval (current status: {trade['status']}).")
            return jsonify({"status": "error", "message": f"Trade {trade_id} not in 'pending_approval' state.", "current_status": trade['status']}), 400
    else:
        print(f"API: Trade {trade_id} not found for approval.")
        return jsonify({"status": "error", "message": f"Trade {trade_id} not found."}), 404

@app.route('/api/trades/<string:trade_id>/reject', methods=['POST'])
def reject_trade(trade_id):
    global trade_proposals_store
    global trade_decisions_queue
    if trade_id in trade_proposals_store:
        trade = trade_proposals_store[trade_id]
        if trade['status'] == 'pending_approval':
            trade['status'] = 'rejected'
            print(f"API Server: Trade {trade_id} status updated to rejected in store.") # Added log
            trade_decisions_queue.append({'trade_id': trade_id, 'decision': 'rejected'})
            print(f"API Server: Decision for {trade_id} (rejected) added to decisions queue. Queue size: {len(trade_decisions_queue)}") # Added log
            # Original log below, can be kept or removed if redundant
            print(f"API: Trade {trade_id} rejected by user. Decision queued.")
            return jsonify({"status": "success", "message": f"Trade {trade_id} rejected."}), 200
        else:
            print(f"API: Trade {trade_id} was not pending approval (current status: {trade['status']}).")
            return jsonify({"status": "error", "message": f"Trade {trade_id} not in 'pending_approval' state.", "current_status": trade['status']}), 400
    else:
        print(f"API: Trade {trade_id} not found for rejection.")
        return jsonify({"status": "error", "message": f"Trade {trade_id} not found."}), 404


if __name__ == '__main__':
    print("Starting API server with WebSocket support for UI development on http://127.0.0.1:5000 ...")

    # Start the watcher thread
    watcher_thread = threading.Thread(target=watch_proposal_queue, daemon=True)
    watcher_thread.start()

    # Run SocketIO server
    # use_reloader=False is important for background threads
    socketio.run(app, debug=True, port=5000, use_reloader=False, allow_unsafe_werkzeug=True)


# --- CRUD API for User Documented Strategies ---

@app.route('/api/strategies', methods=['POST'])
def create_strategy():
    # _ensure_strategies_dir() # No longer needed here if called at startup
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    strategy_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    new_strategy = {
        "strategy_id": strategy_id,
        "created_at": now_iso,
        "updated_at": now_iso,
        # Ensure all fields from data are captured.
        # It's good practice to explicitly list fields or validate them.
        # For now, we'll spread the data assuming it's all relevant.
        **data
    }

    file_path = os.path.join(STRATEGIES_DIR, f"{strategy_id}.json")
    try:
        with open(file_path, 'w') as f:
            json.dump(new_strategy, f, indent=4)
        return jsonify(new_strategy), 201
    except IOError as e:
        print(f"Error writing strategy file {file_path}: {e}")
        return jsonify({"error": "Failed to save strategy"}), 500


@app.route('/api/strategies', methods=['GET'])
def get_strategies():
    # _ensure_strategies_dir()
    strategies_summary = []
    try:
        if not os.path.exists(STRATEGIES_DIR): # Should be created by _ensure_strategies_dir
             os.makedirs(STRATEGIES_DIR) # Create if it somehow got deleted after startup call

        for filename in os.listdir(STRATEGIES_DIR):
            if filename.endswith(".json"):
                file_path = os.path.join(STRATEGIES_DIR, filename)
                try:
                    with open(file_path, 'r') as f:
                        strategy_data = json.load(f)
                    strategies_summary.append({
                        'strategy_id': strategy_data.get('strategy_id'),
                        'name': strategy_data.get('name'), # Assuming 'name' is a field in the strategy data
                        'author': strategy_data.get('author'), # Assuming 'author' is a field
                        'updated_at': strategy_data.get('updated_at')
                    })
                except json.JSONDecodeError:
                    print(f"Error decoding JSON from file {filename}") # Log and skip
                except IOError:
                    print(f"Error reading file {filename}") # Log and skip
        return jsonify(strategies_summary)
    except Exception as e:
        print(f"Error listing strategies: {e}")
        return jsonify({"error": "Failed to retrieve strategies"}), 500


@app.route('/api/strategies/<string:strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    # _ensure_strategies_dir()
    file_path = os.path.join(STRATEGIES_DIR, f"{strategy_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                strategy_data = json.load(f)
            return jsonify(strategy_data)
        except json.JSONDecodeError:
            return jsonify({"error": "Failed to decode strategy data"}), 500
        except IOError:
            return jsonify({"error": "Failed to read strategy file"}), 500
    else:
        return jsonify({"error": "Strategy not found"}), 404


@app.route('/api/strategies/<string:strategy_id>', methods=['PUT'])
def update_strategy(strategy_id):
    # _ensure_strategies_dir()
    file_path = os.path.join(STRATEGIES_DIR, f"{strategy_id}.json")
    if not os.path.exists(file_path):
        return jsonify({"error": "Strategy not found"}), 404

    update_data = request.get_json()
    if not update_data:
        return jsonify({"error": "Invalid JSON data"}), 400

    try:
        with open(file_path, 'r') as f:
            existing_strategy_data = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error reading strategy file for update {file_path}: {e}")
        return jsonify({"error": "Failed to read existing strategy data"}), 500

    # Merge update_data into existing_strategy_data
    # Important: Do not allow strategy_id or created_at to be changed by update_data
    original_id = existing_strategy_data.get('strategy_id')
    original_created_at = existing_strategy_data.get('created_at')

    existing_strategy_data.update(update_data) # Apply updates

    # Restore original immutable fields if they were in update_data
    existing_strategy_data['strategy_id'] = original_id
    existing_strategy_data['created_at'] = original_created_at

    existing_strategy_data['updated_at'] = datetime.now(timezone.utc).isoformat()

    try:
        with open(file_path, 'w') as f:
            json.dump(existing_strategy_data, f, indent=4)
        return jsonify(existing_strategy_data)
    except IOError as e:
        print(f"Error writing updated strategy file {file_path}: {e}")
        return jsonify({"error": "Failed to save updated strategy"}), 500


@app.route('/api/strategies/<string:strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    # _ensure_strategies_dir()
    file_path = os.path.join(STRATEGIES_DIR, f"{strategy_id}.json")
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            return jsonify({"message": "Strategy deleted successfully"}), 200 # 204 No Content is also an option
        except OSError as e:
            print(f"Error deleting strategy file {file_path}: {e}")
            return jsonify({"error": "Failed to delete strategy"}), 500
    else:
        return jsonify({"error": "Strategy not found"}), 404
