from flask import Flask, jsonify
from flask_cors import CORS # For handling Cross-Origin Resource Sharing
from flask_socketio import SocketIO
import uuid
import threading
import time

app = Flask(__name__)
CORS(app) # Enable CORS for all routes, allowing React dev server to call it
socketio = SocketIO(app, cors_allowed_origins="*")

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
