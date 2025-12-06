#!/bin/bash
# Startup script for the Legal AI API
echo "Starting Legal AI API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
