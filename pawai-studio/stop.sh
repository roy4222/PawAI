#!/usr/bin/env bash
# 停止 PawAI Studio
pkill -f "uvicorn mock_server:app" 2>/dev/null && echo "Mock Server stopped" || echo "Mock Server not running"
pkill -f "next dev" 2>/dev/null && echo "Frontend stopped" || echo "Frontend not running"
