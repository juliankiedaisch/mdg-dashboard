#!/bin/bash

# Load environment variables from .env file
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "Starting MDG Admin Dashboard (dev mode)..."
echo ""

# ── Start Docker services (PostgreSQL + Qdrant) ─────────────────────
echo "Starting PostgreSQL and Qdrant via Docker..."
docker compose -f docker-compose.dev.yml up -d

echo "Waiting for PostgreSQL to be ready..."

echo "PostgreSQL is ready."
echo ""

# Check if backend dependencies are installed
if [ ! -d "backend/venv" ]; then
    echo "Setting up backend virtual environment..."
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    cd ..
fi

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo "Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

echo ""
echo "Starting backend server..."
cd backend
source venv/bin/activate
python app.py &
BACKEND_PID=$!
cd ..

echo "Backend started with PID: $BACKEND_PID"
echo ""
echo "Waiting for backend to initialize..."
sleep 3

echo "Starting frontend development server..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "================================"
echo "MDG Admin Dashboard is running!"
echo "================================"
echo "Frontend: http://${FRONTEND_HOST}:${FRONTEND_PORT}"
echo "Backend API: http://${BACKEND_HOST}:${BACKEND_PORT}"
echo ""
echo "Press Ctrl+C to stop both servers"
echo ""

# Wait for user interrupt
trap "echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; echo 'Stopping Docker services...'; docker compose -f docker-compose.dev.yml down; exit" INT
wait
