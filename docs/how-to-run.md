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

Initialize the database (creates tables):

```bash
python -c "from app.db import connect, init_db; conn = connect('ipocket.db'); init_db(conn); conn.close()"
```

Reset the database for local dev (removes data):

```bash
rm -f ipocket.db
python -c "from app.db import connect, init_db; conn = connect('ipocket.db'); init_db(conn); conn.close()"
```

Run the web app:

```bash
uvicorn app.main:app --reload
```

Endpoints:
- Health check: http://127.0.0.1:8000/health
- Metrics: http://127.0.0.1:8000/metrics

## Example API calls
Login and capture a token:

```bash
curl -s -X POST http://127.0.0.1:8000/login \
  -H "Content-Type: application/json" \
  -d '{"username":"editor","password":"editor-pass"}'
```

Create an IP asset (Editor/Admin):

```bash
curl -s -X POST http://127.0.0.1:8000/ip-assets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"ip_address":"10.0.0.50","subnet":"10.0.0.0/24","gateway":"10.0.0.1","type":"VM"}'
```

List unassigned IPs:

```bash
curl -s "http://127.0.0.1:8000/ip-assets?unassigned-only=true"
```

## Run tests
```bash
pytest
```
