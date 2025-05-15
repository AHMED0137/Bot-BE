from flask import Flask, jsonify, request, redirect, url_for, session, send_from_directory
import os
import json
import subprocess
import sys
from threading import Thread
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["https://bot-fe-gamma.vercel.app/"])  # Allow React frontend to access API
app.secret_key = 'your-secret-key'  # Change this to a strong random string
bot_process = None

# Users and hashed passwords
USERS = {
    "admin": generate_password_hash("Admin@1220"),
    "Paradox": generate_password_hash("Paradox@137")
}

# -------------------- API Routes --------------------
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if username in USERS and check_password_hash(USERS[username], password):
        session["logged_in"] = True
        session["username"] = username
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Invalid credentials'}), 401

@app.route('/api/user')
def get_user():
    if not session.get("logged_in"):
        return jsonify({"username": "Guest"})
    return jsonify({"username": session.get("username", "User")})

@app.route('/api/signals')
def get_signals():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    if not os.path.exists('signals.json'):
        return jsonify([])
    try:
        with open('signals.json', 'r') as f:
            signals = json.load(f)
        return jsonify(signals)
    except Exception as e:
        print("Error loading signals:", e)
        return jsonify([])

@app.route('/api/start_bot', methods=['POST'])
def start_bot():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    global bot_process
    if bot_process is None or bot_process.poll() is not None:
        try:
            def run_bot():
                global bot_process
                bot_path = os.path.abspath("channel_bot.py")
                bot_process = subprocess.Popen([sys.executable, bot_path])
            Thread(target=run_bot).start()
            return jsonify({"message": "Bot started."}), 200
        except Exception as e:
            print("❌ Failed to start bot:", e)
            return jsonify({"error": "Failed to start bot."}), 500
    else:
        return jsonify({"message": "Bot is already running."}), 200

@app.route('/api/stop_bot', methods=['POST'])
def stop_bot():
    if not session.get('logged_in'):
        return jsonify({'error': 'Unauthorized'}), 401
    global bot_process
    if bot_process and bot_process.poll() is None:
        bot_process.terminate()
        bot_process = None
        return jsonify({"message": "Bot stopped."}), 200
    else:
        return jsonify({"message": "Bot is not running."}), 200


@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# -------------------- React Frontend Routing --------------------

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react(path):
    """
    Serves the React build if path exists, or index.html as fallback for client-side routes.
    """
    if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

# -------------------- Run Server --------------------

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
