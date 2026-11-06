# Acme login agent

A Browser Use agent (`agent.py`) that signs in to a local staging copy of the
Acme login (`app.py`, http://127.0.0.1:{{PORT}}). Demo account: `demo` / `demo123`.

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py &
ANTHROPIC_API_KEY=... .venv/bin/python agent.py
```
