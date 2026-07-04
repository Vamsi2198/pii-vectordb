# RAG Main.py Server Launcher
# Run: powershell -ExecutionPolicy Bypass -File run_rag_server.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "RAG Main.py Server Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Host "Working directory: $scriptPath" -ForegroundColor Gray
Write-Host ""

# Step 1: Pre-flight check
Write-Host "[1/3] Running pre-flight checks..." -ForegroundColor Yellow
try {
    cd $scriptPath
    python precheck.py
    Write-Host ""
} catch {
    Write-Host "Pre-flight check failed: $_" -ForegroundColor Red
    Read-Host "Press Enter to continue anyway"
}

# Step 2: Start server
Write-Host "[2/3] Starting RAG server..." -ForegroundColor Yellow
Write-Host "Server will run on: http://localhost:8001" -ForegroundColor Cyan
Write-Host "Test console: http://localhost:8001/test" -ForegroundColor Cyan
Write-Host "API endpoint: http://localhost:8001/query" -ForegroundColor Cyan
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Start uvicorn
try {
    python -m uvicorn main:app --port 8001 --reload --host 0.0.0.0
} catch {
    Write-Host "Error starting server: $_" -ForegroundColor Red
    Read-Host "Press Enter to exit"
}
