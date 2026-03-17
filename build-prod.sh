#!/bin/bash

echo "Building MDG Admin Dashboard for production..."
echo ""

# Build frontend
echo "Building frontend..."
cd frontend
npm install
npm run build
cd ..

echo ""
echo "Frontend built successfully in frontend/dist"
echo ""

# Setup backend for production
echo "Setting up backend..."
cd backend

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt

cd ..

echo ""
echo "================================"
echo "Build completed successfully!"
echo "================================"
echo ""
echo "To run in production:"
echo "1. Copy frontend/dist contents to backend/static/frontend"
echo "2. Configure backend to serve static files"
echo "3. Run: cd backend && gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 app:app"
echo ""
