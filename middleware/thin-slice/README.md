# DGF Middleware — Thin Slice PoC

Minimal runnable proof of the DGF Middleware coordination loop:

**Continuity Reference → SRV → Provisional → Revoke**

This is a proof of concept, not production software.

## What works

- `POST /continuity` — issue a Continuity Reference (stores in SQLite)
- `POST /srv` — emit a Systemic Risk Vector against a valid, unexpired Continuity Reference
- `POST /provisional` — issue a Provisional action
- `POST /provisional/{provisional_id}/revoke` — revoke a Provisional
- Expiry checks on Continuity References (410 when expired)
- Local SQLite storage

## What does not work yet (intentional limits)

- No real W3C Verifiable Presentation / DID cryptographic verification (VP is accepted as opaque input)
- No authentication / authorization on endpoints
- No ACQ endpoint
- No full degraded-mode policy logic (flags only)
- Debug endpoints only when `DGF_DEBUG=1`
- Not production-hardened

## Requirements

- Python 3.10+
- Windows / macOS / Linux

## Setup (local)

```bash
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

pip install fastapi uvicorn
uvicorn main:app --reload
```

Open: http://127.0.0.1:8000/docs

### Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `DGF_DB_PATH` | `dgf_middleware.db` | SQLite database file path |
| `DGF_DEBUG` | `0` | Set to `1` to enable `/debug/*` routes |
| `DGF_API_KEY` | `(unset)` | If set, require Authorization: Bearer <key> on coordination endpoints |

### Canonical end-to-end test

See `e2e-demo.http` or `e2e-demo.sh` (or the curl sequence in this repo) for Continuity → SRV → Provisional → Revoke.

### Docker

docker build -t dgf-middleware-thin:0.1.0 .
docker run --rm -p 8000:8000 dgf-middleware-thin:0.1.0

### API reference

OpenAPI-oriented public docs (design contract):  
[https://dgf-openapi-v1.redocly.app/](https://dgf-openapi-v1.redocly.app/)

### Version

`v0.1.0-thin-slice-poc` (see Git tags)

### Running with auth (demo)

set DGF_API_KEY=your-secret
set DGF_DEBUG=0
uvicorn main:app --host 0.0.0.0 --port 8000

Use header: Authorization: Bearer your-secret
