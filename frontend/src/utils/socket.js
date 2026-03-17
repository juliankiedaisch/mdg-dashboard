import { io } from 'socket.io-client';

class SocketService {
  constructor() {
    this.socket = null;
    this.isConnected = false;
    this.shouldReconnect = true;
  }

  connect(namespace = '/main') {
    if (this.socket && this.isConnected) {
      console.log('Socket already connected');
      return this.socket;
    }

    // Reset reconnection flag when explicitly connecting
    this.shouldReconnect = true;

    // Socket URL is now injected by Vite from the central .env file
    const socketUrl = import.meta.env.VITE_SOCKET_URL || 'http://localhost:5000';
    
    this.socket = io(`${socketUrl}${namespace}`, {
      withCredentials: true,
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: 5,
    });

    this.socket.on('connect', () => {
      console.log('Socket connected:', this.socket.id);
      this.isConnected = true;
    });

    this.socket.on('disconnect', (reason) => {
      console.log('Socket disconnected:', reason);
      this.isConnected = false;
      
      // If disconnected due to auth issues, stop reconnecting
      if (reason === 'io server disconnect' || reason === 'io client disconnect') {
        this.shouldReconnect = false;
      }
    });

    this.socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error.message);
      
      // If we're not on the login page and socket fails, likely auth issue
      const isOnLoginPage = window.location.pathname === '/login';
      
      // Stop reconnection attempts to prevent spam
      if (this.socket.io.reconnectionAttempts >= 3) {
        console.log('Multiple socket connection failures, stopping reconnection');
        this.stopReconnecting();
        
        // Redirect to login if not already there (likely session expired)
        if (!isOnLoginPage) {
          console.log('Socket authentication failed, redirecting to login...');
          window.location.href = '/login';
        }
      }
    });

    this.socket.on('connected', (data) => {
      console.log('Server confirmed connection:', data);
    });

    return this.socket;
  }

  stopReconnecting() {
    this.shouldReconnect = false;
    if (this.socket) {
      this.socket.io.reconnection(false);
    }
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
      this.isConnected = false;
    }
  }

  emit(event, data) {
    if (this.socket && this.isConnected) {
      this.socket.emit(event, data);
    } else {
      console.error('Socket not connected. Cannot emit event:', event);
    }
  }

  on(event, callback) {
    if (this.socket) {
      this.socket.on(event, callback);
    } else {
      console.error('Socket not initialized. Cannot listen to event:', event);
    }
  }

  off(event, callback) {
    if (this.socket) {
      this.socket.off(event, callback);
    }
  }
}

export default new SocketService();
