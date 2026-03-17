"""
WSGI entry point for production deployment with Gunicorn
"""
from app import app

# The app is already wrapped with SocketIO via socketio.init_app() in create_app()
# Gunicorn will use this as the WSGI application
application = app
