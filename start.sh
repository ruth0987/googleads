#!/bin/bash

# Growth-OS Startup Script
echo "🚀 Starting Growth-OS..."

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Start Backend
echo "📡 Starting Backend API..."
source "$DIR/venv/bin/activate"
python "$DIR/backend/main.py" > "$DIR/backend.log" 2>&1 &
BACKEND_PID=$!
echo "   Backend running (PID: $BACKEND_PID) - Logs: backend.log"

# Wait for backend to initialize
sleep 2

# Start Frontend
echo "🎨 Starting Frontend..."
cd "$DIR/growth-os-frontend"
npm run dev > "$DIR/frontend.log" 2>&1 &
FRONTEND_PID=$!
echo "   Frontend running (PID: $FRONTEND_PID) - Logs: frontend.log"

echo ""
echo "✅ Growth-OS is running!"
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo ""
echo "📊 View logs:"
echo "   Backend:  tail -f backend.log"
echo "   Frontend: tail -f frontend.log"
echo ""
echo "🛑 To stop:"
echo "   kill $BACKEND_PID $FRONTEND_PID"
echo ""
