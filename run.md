# Running RootCause locally

Two processes, two terminals. Start the **backend first**, then the **frontend**.

| Process  | Folder          | URL                     |
|----------|-----------------|-------------------------|
| Backend  | `backend/`      | http://localhost:8000   |
| Frontend | `frontend-new/` | http://localhost:5173   |

The frontend proxies every `/api/...` request to port 8000, so the browser only ever talks to 5173.

> `frontend-new/` is the current UI. `frontend/` is the earlier version and also serves on
> port 5173, so never run both at once.

---

## Prerequisites

- **Python 3.11+**
- **Node.js `^20.19` or `>=22.12`** (the Vite version in use refuses older Node)
- An LLM to plan and narrate answers. Any one of these works:
  - the **Claude Code CLI** (`claude`) installed and logged in, with no API key needed, or
  - an **OpenRouter**, **NVIDIA NIM** or **Anthropic** API key (see [Choosing an LLM](#choosing-an-llm)).

  Without one the app still starts and logs a "No LLM provider is configured" warning; it then
  falls back to simple heuristic planning, so expect weaker answers to open-ended questions.

---

## Terminal 1: Backend

From the repo root.

**PowerShell (Windows)**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Git Bash / macOS / Linux**
```bash
cd backend
python -m venv .venv
source .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

You should see `Application startup complete.` and a line such as
`LLM providers available: claude_code (active: openrouter)`.

- Setup (venv and `pip install`) is a one-time step. Next time, activate the venv and run only the
  `uvicorn` line.
- If PowerShell blocks `Activate.ps1`, run
  `Set-ExecutionPolicy -Scope Process Bypass` once in that window, then activate again.
- Interactive API docs: http://localhost:8000/docs

---

## Terminal 2: Frontend

```bash
cd frontend-new
npm install
npm run dev
```

`npm install` is also one-time. Open **http://localhost:5173**.

On the **Data** page, choose files (Excel or CSV) or click **Use the sample retail data**.
Then go to **Ask** and try *"Show revenue by month"*.

---

## Choosing an LLM

The app runs with no configuration. To pick a provider explicitly, either:

- click the **settings** control in the app's left sidebar and choose one, or
- create `backend/.env` (start from `backend/.env.example`) and restart the backend:

```env
LLM_PROVIDER=claude_code          # openrouter | nvidia_nim | claude_code | anthropic

OPENROUTER_API_KEY=...            # only for the provider you use
NVIDIA_NIM_API_KEY=...
ANTHROPIC_API_KEY=...
```

Never commit `.env`. It is gitignored, and only `.env.example` belongs in the repo.

---

## Checks

| What                   | Command (folder)                          |
|------------------------|-------------------------------------------|
| Backend tests          | `pytest -q` (`backend/`, venv active)     |
| Frontend type check    | `npx tsc -b` (`frontend-new/`)            |
| Frontend lint          | `npm run lint` (`frontend-new/`)          |
| Frontend prod build    | `npm run build` (`frontend-new/`)         |
| Backend is up          | open http://localhost:8000/api/settings   |

---

## Stopping

Press `Ctrl+C` in each terminal.

Uploaded datasets and chat sessions live in `backend/data/` (created automatically, gitignored).
Delete that folder to reset everything to a clean state.

---

## Troubleshooting

**Port already in use** (`5173` or `8000`): find and stop what holds it.
```powershell
netstat -ano | findstr ":5173"      # note the PID in the last column
Stop-Process -Id <PID>
```

**Frontend shows network errors or `ECONNREFUSED` in the Vite terminal:** the backend is not
running. Start Terminal 1 first.

**Answers are shallow, or the backend log says "No LLM provider is configured":** none of the
providers is usable, so the backend is using heuristic planning. Log in to the Claude Code CLI,
or add an API key as described above, then restart the backend.

**`Cannot find module '../components/data/...'`:** you are on an older checkout. That folder was
once excluded by a `.gitignore` rule and is now committed. Pull the latest.

**`npm install` warns about the engine / Vite refuses to start:** upgrade Node to
`20.19+` or `22.12+`.
