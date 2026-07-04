# RAG Main.py - Startup Guide

## Quick Start

### Option 1: Using Batch File (Windows)
```
Double-click: start_rag_server.bat
```

### Option 2: Manual Start
```bash
cd "c:\Users\HP\OneDrive\Documents\dinesh sir\aagcp_pro\pii-rag-main"
python -m uvicorn main:app --port 8001 --reload
```

## Access the Test Console

Once the server is running:
- **Test Console:** http://localhost:8001/test
- **API Endpoint:** http://localhost:8001/query

## What's Changed in main.py

✅ **Added Test Console:**
- Beautiful UI for testing RAG queries
- Shows results with vault masking applied
- Role-based access control demo

✅ **New Endpoints:**
- `/test` - Test console page
- `/api/index-status` - Check RAG index status (how many chunks loaded)
- Enhanced `/query` - Better logging and chunk display

✅ **Better Logging:**
- Tracks each query through the pipeline
- Shows number of results at each step
- Helps debug missing chunks

## How to Test

1. **Start the server** (see above)

2. **Visit the test console:**
   http://localhost:8001/test

3. **Enter a query:**
   "who came to Apollo Hospital for diabetes checkup"

4. **Select a role:**
   - **Analyst:** Sees masked PII (tokens only)
   - **Finance/Manager:** Sees partial reveal (last 4 digits)
   - **Admin:** Sees full data (complete reveal)

5. **Click "Send Query"**

## Expected Results

### If Index Has Data:
```
✅ Query successful! Retrieved 2 chunks

[Result 1] Score: 0.5967
On <DATE_TIME_f925...>, <PERSON_35b60...>, a 51-year-old patient from <LOCATION_...>
visited Apollo Hospital for his routine diabetes checkup...

[Result 2] Score: 0.2754
...more results...
```

### If Index is Empty:
```
⚠️ Empty (upload documents first)
```

## First Time: Upload Documents

If index is empty, upload a document first:

1. Via RAG upload endpoint
2. Or copy a PDF to `uploads/` folder
3. Or use the main dashboard (app.py on port 8000)

## Troubleshooting

**No chunks returned?**
- Check `/api/index-status` - see if chunks are loaded
- Upload documents if index is empty
- Check server logs for errors

**Test console not loading?**
- Verify `static/test_console.html` exists
- Check server logs for HTML file errors
- Try `http://localhost:8001/` (main page)

**Chunks not showing masking?**
- Check vault is initialized
- Verify mask_pii checkbox is checked
- Look at Raw JSON tab to see actual response

## Logs to Watch

When you send a query, watch the terminal for:
```
[QUERY] question='...' auth=analyst_token mask_pii=True
[QUERY] resolved role=analyst
[QUERY] search_question returned 2 results
[QUERY] prepared 2 display results
```

If you see:
- `returned 0 results` → No data in index
- `prepared 0 display results` → Role filter blocked results

## Run Both Servers

You can run both at the same time:
- **AAGCP Dashboard:** `uvicorn app:app --port 8000` (root folder)
- **RAG Test Console:** `uvicorn pii-rag-main/main:app --port 8001` (in pii-rag-main)

Then:
- Dashboard: http://localhost:8000
- RAG Test: http://localhost:8001/test
