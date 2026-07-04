@echo off
REM Start RAG main.py server on port 8001
echo Starting RAG main.py server on http://localhost:8001
cd /d "c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro\pii-rag-main"
python -m uvicorn main:app --port 8001 --reload
pause
