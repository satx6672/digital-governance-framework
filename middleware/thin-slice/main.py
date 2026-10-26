from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import os
import uuid
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlalchemy.orm import declarative_base

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./dgf_ledger.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(DATABASE_URL, pool_size=20, max_overflow=40, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS continuity_references (
                continuity_ref TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                actor_type TEXT,
                degraded INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS srvs (
                srv_id TEXT PRIMARY KEY,
                passport_ref TEXT NOT NULL,
                harm_class TEXT NOT NULL,
                severity TEXT NOT NULL,
                confidence REAL NOT NULL,
                timestamp TEXT NOT NULL,
                emitter TEXT NOT NULL,
                actor_type TEXT,
                degraded_emission INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS provisionals (
                provisional_id TEXT PRIMARY KEY,
                target_passport_ref TEXT NOT NULL,
                action_type TEXT NOT NULL,
                expiry TEXT NOT NULL,
                originating_srv_ids TEXT NOT NULL,
                degraded_mode INTEGER DEFAULT 0,
                actor_type TEXT,
                created_at TEXT NOT NULL,
                revoked INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS acqs (
                acq_id TEXT PRIMARY KEY,
                srv_id TEXT,
                target_passport_ref TEXT NOT NULL,
                requesting_platform TEXT,
                query_type TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                nonce TEXT
            );
        """))

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await engine.dispose()

app = FastAPI(
    title="DGF Middleware API",
    version="1.0.0-mvp",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dgf.middleware")

class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

app.add_middleware(RequestLogMiddleware)

API_KEY = os.getenv("DGF_API_KEY")  # if unset, auth is disabled
security = HTTPBearer(auto_error=False)
if API_KEY:
    logger.info("Auth enabled (DGF_API_KEY is set)")
else:
    logger.info("Auth disabled (DGF_API_KEY unset)")

def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
):
    """If DGF_API_KEY is set, require Authorization: Bearer <key>."""
    if not API_KEY:
        return  # auth disabled

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header. Use: Bearer <api_key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

DEBUG_MODE = os.getenv("DGF_DEBUG", "0") == "1"

class ACQRequest(BaseModel):
    srv_id: Optional[str] = None
    target_passport_ref: str
    requesting_platform: Optional[str] = None
    query_type: str = "STRUCTURAL_CATEGORY_SYNTAX"
    nonce: Optional[str] = None

class ACQResponse(BaseModel):
    acq_id: str
    srv_id: Optional[str] = None
    status: str
    timestamp: str
    error_detail: Optional[str] = None

class RevokeProvisionalRequest(BaseModel):
    provisional_id: str
    target_passport_ref: str
    reason: str
    evidence_ref: Optional[str] = None

class ProvisionalRequest(BaseModel):
    target_passport_ref: str
    action_type: str
    expiry: str
    originating_srv_ids: list[str]
    degraded_mode: Optional[bool] = False
    actor_type: Optional[str] = None

class SRVRequest(BaseModel):
    passport_ref: str
    harm_class: str
    severity: str
    confidence: float
    timestamp: str
    emitter: str
    actor_type: Optional[str] = None
    degraded_emission: Optional[bool] = False

class ContinuityRequest(BaseModel):
    verifiablePresentation: Any

class ContinuityResponse(BaseModel):
    continuity_ref: str
    expires_at: str
    degraded: bool
    actor_type: str
    sponsor_did: Optional[str] = None

@app.get("/debug/acqs")
async def list_acqs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        SELECT acq_id, srv_id, target_passport_ref, requesting_platform,
               query_type, status, created_at, nonce
        FROM acqs ORDER BY created_at DESC
    """))
    rows = result.fetchall()
    
    items = [
        {
            "acq_id": r[0],
            "srv_id": r[1],
            "target_passport_ref": r[2],
            "requesting_platform": r[3],
            "query_type": r[4],
            "status": r[5],
            "created_at": r[6],
            "nonce": r[7],
        }
        for r in rows
    ]
    return {"count": len(items), "items": items}

@app.get("/debug/provisionals")
async def list_provisionals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        SELECT provisional_id, target_passport_ref, action_type, expiry,
               originating_srv_ids, degraded_mode, actor_type, created_at, revoked
        FROM provisionals
        ORDER BY created_at DESC
    """))
    rows = result.fetchall()

    results = []
    for row in rows:
        results.append({
            "provisional_id": row[0],
            "target_passport_ref": row[1],
            "action_type": row[2],
            "expiry": row[3],
            "originating_srv_ids": row[4].split(",") if row[4] else [],
            "degraded_mode": bool(row[5]),
            "actor_type": row[6],
            "created_at": row[7],
            "revoked": bool(row[8])
        })

    return {
        "count": len(results),
        "items": results
    }

@app.get("/debug/srvs")
async def list_srvs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        SELECT srv_id, passport_ref, harm_class, severity, confidence,
               timestamp, emitter, actor_type, degraded_emission, created_at
        FROM srvs
        ORDER BY created_at DESC
    """))
    rows = result.fetchall()

    results = []
    for row in rows:
        results.append({
            "srv_id": row[0],
            "passport_ref": row[1],
            "harm_class": row[2],
            "severity": row[3],
            "confidence": row[4],
            "timestamp": row[5],
            "emitter": row[6],
            "actor_type": row[7],
            "degraded_emission": bool(row[8]),
            "created_at": row[9]
        })

    return {
        "count": len(results),
        "items": results
    }

if DEBUG_MODE:
    @app.get("/debug/continuity")
    async def list_continuity_references(db: AsyncSession = Depends(get_db)):
        result = await db.execute(text("""
            SELECT continuity_ref, expires_at, created_at, actor_type, degraded
            FROM continuity_references
            ORDER BY created_at DESC
        """))
        rows = result.fetchall()

        results = []
        for row in rows:
            results.append({
                "continuity_ref": row[0],
                "expires_at": row[1],
                "created_at": row[2],
                "actor_type": row[3],
                "degraded": bool(row[4])
            })

        return {
            "count": len(results),
            "items": results
        }

@app.get("/debug/init")
async def manual_init():
    await init_db()
    return {"message": "Database tables initialized"}

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "DGF Middleware thin slice is running"
    }

@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <html>
        <head><title>Privacy Policy - DGF Middleware</title></head>
        <body style="font-family: sans-serif; max-width: 800px; margin: 40px auto; line-height: 1.6;">
            <h2>Privacy Policy for DGF Middleware Edge Proxy</h2>
            <p><strong>Last Updated: October 2026</strong></p>
            <p><strong>1. Data Collection:</strong> DGF Middleware processes browsing network requests locally to block trackers. Basic telemetry regarding blocked trackers (Multiplicity Principle data) is transmitted securely to our cloud engine strictly for operational continuity.</p>
            <p><strong>2. Data Usage & Sharing:</strong> We do not sell, rent, or monetize your personal data, browsing history, or tracking analytics to third parties.</p>
            <p><strong>3. Permissions:</strong> The extension requires permissions such as <code>declarativeNetRequest</code> and <code>storage</code> solely to function securely as an edge proxy.</p>
            <p><strong>4. Contact:</strong> For any privacy-related questions, please contact the developer via the Chrome Web Store support tab.</p>
        </body>
    </html>
    """

@app.post("/continuity", response_model=ContinuityResponse)
async def establish_continuity(
    request: ContinuityRequest,
    _: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    if request.verifiablePresentation is None:
        raise HTTPException(status_code=400, detail="verifiablePresentation is required")

    continuity_ref = f"cont_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=4)

    # Store in database asynchronously
    await db.execute(
        text("""
        INSERT INTO continuity_references
        (continuity_ref, expires_at, created_at, actor_type, degraded)
        VALUES (:ref, :exp, :creat, :actor, :deg)
        """),
        {
            "ref": continuity_ref,
            "exp": expires_at.isoformat().replace("+00:00", "Z"),
            "creat": now.isoformat().replace("+00:00", "Z"),
            "actor": "human",
            "deg": 0
        }
    )
    await db.commit()

    return {
        "continuity_ref": continuity_ref,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "degraded": False,
        "actor_type": "human"
    }

@app.post("/srv")
async def emit_srv(
    request: SRVRequest,
    _: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check that the Continuity Reference exists and is not expired
    result = await db.execute(
        text("""
        SELECT expires_at FROM continuity_references
        WHERE continuity_ref = :ref
        """),
        {"ref": request.passport_ref}
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Continuity Reference not found")

    expires_at = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    if now > expires_at:
        raise HTTPException(status_code=410, detail="Continuity Reference has expired")

    # 2. Create and store the SRV
    srv_id = f"srv_{uuid.uuid4().hex[:16]}"
    created_at = now.isoformat().replace("+00:00", "Z")

    await db.execute(
        text("""
        INSERT INTO srvs (
            srv_id, passport_ref, harm_class, severity, confidence,
            timestamp, emitter, actor_type, degraded_emission, created_at
        ) VALUES (:srv_id, :passport, :harm, :sev, :conf, :ts, :emit, :actor, :deg, :creat)
        """),
        {
            "srv_id": srv_id,
            "passport": request.passport_ref,
            "harm": request.harm_class,
            "sev": request.severity,
            "conf": request.confidence,
            "ts": request.timestamp,
            "emit": request.emitter,
            "actor": request.actor_type,
            "deg": 1 if request.degraded_emission else 0,
            "creat": created_at
        }
    )
    await db.commit()

    return {
        "srv_id": srv_id,
        "dampened_confidence": request.confidence * 0.85  # simple normal-mode dampener for now
    }

@app.post("/provisional")
async def issue_provisional(
    request: ProvisionalRequest,
    _: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    # 1. Check Continuity Reference exists and is not expired
    result = await db.execute(
        text("""
        SELECT expires_at FROM continuity_references
        WHERE continuity_ref = :ref
        """),
        {"ref": request.target_passport_ref}
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Continuity Reference not found")

    expires_at = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    if now > expires_at:
        raise HTTPException(status_code=410, detail="Continuity Reference has expired")

    # 2. Basic check that at least one originating SRV exists
    if not request.originating_srv_ids:
        raise HTTPException(status_code=400, detail="At least one originating_srv_id is required")

    # 3. Create and store the Provisional
    provisional_id = f"prov_{uuid.uuid4().hex[:16]}"
    created_at = now.isoformat().replace("+00:00", "Z")
    srv_ids_str = ",".join(request.originating_srv_ids)

    await db.execute(
        text("""
        INSERT INTO provisionals (
            provisional_id, target_passport_ref, action_type, expiry,
            originating_srv_ids, degraded_mode, actor_type, created_at, revoked
        ) VALUES (:prov_id, :target, :action, :expiry, :orig_srvs, :deg, :actor, :creat, :revoked)
        """),
        {
            "prov_id": provisional_id,
            "target": request.target_passport_ref,
            "action": request.action_type,
            "expiry": request.expiry,
            "orig_srvs": srv_ids_str,
            "deg": 1 if request.degraded_mode else 0,
            "actor": request.actor_type,
            "creat": created_at,
            "revoked": 0
        }
    )
    await db.commit()

    return {
        "provisional_id": provisional_id
    }

@app.post("/provisional/{provisional_id}/revoke")
async def revoke_provisional(
    provisional_id: str,
    request: RevokeProvisionalRequest,
    _: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    if provisional_id != request.provisional_id:
        raise HTTPException(
            status_code=400,
            detail="provisional_id in path and body must match"
        )

    result = await db.execute(
        text("""
        SELECT provisional_id, target_passport_ref, revoked
        FROM provisionals
        WHERE provisional_id = :prov_id
        """),
        {"prov_id": provisional_id}
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Provisional not found")

    if row[1] != request.target_passport_ref:
        raise HTTPException(
            status_code=400,
            detail="target_passport_ref does not match this Provisional"
        )

    if row[2] == 1:
        raise HTTPException(status_code=409, detail="Provisional already revoked")

    await db.execute(
        text("""
        UPDATE provisionals
        SET revoked = 1
        WHERE provisional_id = :prov_id
        """),
        {"prov_id": provisional_id}
    )
    await db.commit()

    return {
        "status": "revoked",
        "provisional_id": provisional_id,
        "reason": request.reason
    }

@app.post("/acq", response_model=ACQResponse)
async def issue_acq(
    request: ACQRequest,
    _: None = Depends(require_api_key),
    db: AsyncSession = Depends(get_db)
):
    # Continuity must exist and not be expired
    result = await db.execute(
        text("""
        SELECT expires_at FROM continuity_references
        WHERE continuity_ref = :ref
        """),
        {"ref": request.target_passport_ref}
    )
    row = result.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Continuity Reference not found")

    expires_at = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    if now > expires_at:
        raise HTTPException(status_code=410, detail="Continuity Reference has expired")

    # Thin policy: if srv_id provided, require it to exist
    if request.srv_id:
        srv_result = await db.execute(
            text("SELECT srv_id FROM srvs WHERE srv_id = :srv_id"), 
            {"srv_id": request.srv_id}
        )
        if srv_result.fetchone() is None:
            return {
                "acq_id": f"acq_{uuid.uuid4().hex[:16]}",
                "srv_id": request.srv_id,
                "status": "DENIED",
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "error_detail": "srv_id not found",
            }

    acq_id = f"acq_{uuid.uuid4().hex[:16]}"
    status = "CONFIRMED"
    created_at = now.isoformat().replace("+00:00", "Z")

    await db.execute(
        text("""
        INSERT INTO acqs (
            acq_id, srv_id, target_passport_ref, requesting_platform,
            query_type, status, created_at, nonce
        ) VALUES (:acq_id, :srv_id, :target, :req_plat, :q_type, :status, :creat, :nonce)
        """),
        {
            "acq_id": acq_id,
            "srv_id": request.srv_id,
            "target": request.target_passport_ref,
            "req_plat": request.requesting_platform,
            "q_type": request.query_type,
            "status": status,
            "creat": created_at,
            "nonce": request.nonce
        }
    )
    await db.commit()

    return {
        "acq_id": acq_id,
        "srv_id": request.srv_id,
        "status": status,
        "timestamp": created_at,
        "error_detail": None,
    }
