# FocusFlow AI Study Planner

A working prototype based on `details.md`: React frontend, Python FastAPI backend, and a heuristic scheduling engine.

## Run locally

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

The prototype keeps task data in the browser for now. The API is designed around the Users and Tasks model in `details.md`, so MongoDB persistence can be added without changing the scheduler contract.
