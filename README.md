# MDG Admin Dashboard

This project has been restructured into a separate backend and frontend architecture.

## Project Structure

```
/backend  - Flask API backend
/frontend - React frontend
```

## Backend (Flask API)

### Setup
```bash
cd backend
pip install -r requirements.txt
```

### Run
```bash
cd backend
python app.py
```

The backend API will run on `http://localhost:5000`

### API Endpoints
- `GET /api/modules` - Get available modules for current user
- `GET /api/applications` - Get list of applications
- `GET /api/user` - Get current user information
- `GET /api/auth/status` - Check authentication status
- `GET /api/login` - Initiate OAuth login
- `GET /api/authorize` - OAuth callback handler
- `GET /api/logout` - Logout and clear session

## Frontend (React + Vite)

### Setup
```bash
cd frontend
npm install
```

### Run Development Server
```bash
cd frontend
npm run dev
```

The frontend will run on `http://localhost:3000`

### Build for Production
```bash
cd frontend
npm run build
```

## Development

1. Start the backend server:
   ```bash
   cd backend
   python app.py
   ```

2. In a new terminal, start the frontend:
   ```bash
   cd frontend
   npm run dev
   ```

3. Open your browser to `http://localhost:3000`

## Features

- ✅ OAuth authentication
- ✅ Module-based architecture
- ✅ Real-time communication via WebSocket (Socket.IO)
- ✅ Session management
- ✅ Role-based access control
- ✅ Responsive design

## Technology Stack

### Backend
- Flask
- Flask-SocketIO
- Flask-Session
- Authlib (OAuth)
- SQLAlchemy
- Flask-CORS

### Frontend
- React 18
- React Router v6
- Vite
- Axios
- Socket.IO Client

## Environment Variables

Create a `.env` file in the backend directory with the following variables:

```env
OIDC_CLIENT_ID=your_client_id
OIDC_CLIENT_SECRET=your_client_secret
OIDC_USER_ENDPOINT=your_user_endpoint
OIDC_AUTHORIZE_URL=your_authorize_url
OIDC_JWK_URL=your_jwk_url
OIDC_ACCESS_TOKEN_URL=your_access_token_url
OIDC_REDIRECT_URL=http://localhost:5000/api/authorize
SQLALCHEMY_DATABASE_URI=db/database.db
HOST_NAME=localhost
HOST_PORT=5000
DEBUG=1
APP_SECRET_KEY=your_secret_key
SESSION_COOKIE_DOMAIN=.localhost
```

## Migration from Old Structure

The original Flask application has been split into:

### Backend Changes:
- All routes now return JSON responses
- Added CORS support for frontend communication
- Updated authentication to work with SPA
- Maintained all existing modules and functionality

### Frontend Changes:
- Converted Jinja2 templates to React components
- Implemented client-side routing
- Added API integration with Axios
- Maintained original design and functionality
