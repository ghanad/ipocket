# How to run

## Requirements
- Python 3.11+
- SQLite (built-in)

## Run locally
Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the web app:

```bash
uvicorn app.main:app --reload
```

Endpoints:
- Health check: http://127.0.0.1:8000/health
- Metrics: http://127.0.0.1:8000/metrics

## Run tests
```bash
pytest
```
