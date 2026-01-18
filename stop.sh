#!/bin/bash

# Growth-OS Shutdown Script
echo "🛑 Stopping Growth-OS..."

# Kill all processes
pkill -f "python backend/main.py"
pkill -f "next dev"

echo "✅ All services stopped."
