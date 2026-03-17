from flask_socketio import SocketIO

socketio = SocketIO(
    cors_allowed_origins=["https://dashboard.hub.mdg-hamburg.de", "http://172.22.0.27:5001", "http://localhost:3000", "http://localhost:5173"],
    async_mode='gevent',
)
