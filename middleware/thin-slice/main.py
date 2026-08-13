from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import os
import uuid
import sqlite3

app = FastAPI(
    title="DGF Middleware API",
    version="1.0.0-mvp"
)

DB_NAME = os.getenv("DGF_DB_PATH", "dgf_middleware.db")

DEBUG_MODE = os.getenv("DGF_DEBUG", "0") == "1"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS continuity_references (
            continuity_ref TEXT PRIMARY KEY,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            actor_type TEXT,
            degraded INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
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
        )
    """)  

    cursor.execute("""
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
        )
    """)

    conn.commit()
    conn.close()

init_db()

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

@app.get("/debug/provisionals")
def list_provisionals():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT provisional_id, target_passport_ref, action_type, expiry,
               originating_srv_ids, degraded_mode, actor_type, created_at, revoked
        FROM provisionals
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

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
def list_srvs():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT srv_id, passport_ref, harm_class, severity, confidence,
               timestamp, emitter, actor_type, degraded_emission, created_at
        FROM srvs
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

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
  def list_continuity_references():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT continuity_ref, expires_at, created_at, actor_type, degraded
        FROM continuity_references
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

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

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "DGF Middleware thin slice is running"
    }

@app.post("/provisional/{provisional_id}/revoke")
def revoke_provisional(provisional_id: str, request: RevokeProvisionalRequest):
    if provisional_id != request.provisional_id:
        raise HTTPException(
            status_code=400,
            detail="provisional_id in path and body must match"
        )

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT provisional_id, target_passport_ref, revoked
        FROM provisionals
        WHERE provisional_id = ?
        """,
        (provisional_id,)
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Provisional not found")

    if row[1] != request.target_passport_ref:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="target_passport_ref does not match this Provisional"
        )

    if row[2] == 1:
        conn.close()
        raise HTTPException(status_code=409, detail="Provisional already revoked")

    cursor.execute(
        """
        UPDATE provisionals
        SET revoked = 1
        WHERE provisional_id = ?
        """,
        (provisional_id,)
    )
    conn.commit()
    conn.close()

    return {
        "status": "revoked",
        "provisional_id": provisional_id,
        "reason": request.reason
    }

@app.post("/continuity", response_model=ContinuityResponse)
def establish_continuity(request: ContinuityRequest):
    if request.verifiablePresentation is None:
        raise HTTPException(status_code=400, detail="verifiablePresentation is required")

    continuity_ref = f"cont_{uuid.uuid4().hex[:16]}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=4)

    # Store in database
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO continuity_references
        (continuity_ref, expires_at, created_at, actor_type, degraded)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            continuity_ref,
            expires_at.isoformat().replace("+00:00", "Z"),
            now.isoformat().replace("+00:00", "Z"),
            "human",
            0
        )
    )
    conn.commit()
    conn.close()

    return {
        "continuity_ref": continuity_ref,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "degraded": False,
        "actor_type": "human"
    }

@app.post("/srv")
def emit_srv(request: SRVRequest):
    # 1. Check that the Continuity Reference exists and is not expired
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT expires_at FROM continuity_references
        WHERE continuity_ref = ?
        """,
        (request.passport_ref,)
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Continuity Reference not found")

    expires_at = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    if now > expires_at:
        conn.close()
        raise HTTPException(status_code=410, detail="Continuity Reference has expired")

    # 2. Create and store the SRV
    srv_id = f"srv_{uuid.uuid4().hex[:16]}"
    created_at = now.isoformat().replace("+00:00", "Z")

    cursor.execute(
        """
        INSERT INTO srvs (
            srv_id, passport_ref, harm_class, severity, confidence,
            timestamp, emitter, actor_type, degraded_emission, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            srv_id,
            request.passport_ref,
            request.harm_class,
            request.severity,
            request.confidence,
            request.timestamp,
            request.emitter,
            request.actor_type,
            1 if request.degraded_emission else 0,
            created_at
        )
    )
    conn.commit()
    conn.close()

    return {
        "srv_id": srv_id,
        "dampened_confidence": request.confidence * 0.85  # simple normal-mode dampener for now
    }

@app.post("/provisional")
def issue_provisional(request: ProvisionalRequest):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # 1. Check Continuity Reference exists and is not expired
    cursor.execute(
        """
        SELECT expires_at FROM continuity_references
        WHERE continuity_ref = ?
        """,
        (request.target_passport_ref,)
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Continuity Reference not found")

    expires_at = datetime.fromisoformat(row[0].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    if now > expires_at:
        conn.close()
        raise HTTPException(status_code=410, detail="Continuity Reference has expired")

    # 2. Basic check that at least one originating SRV exists
    if not request.originating_srv_ids:
        conn.close()
        raise HTTPException(status_code=400, detail="At least one originating_srv_id is required")

    # 3. Create and store the Provisional
    provisional_id = f"prov_{uuid.uuid4().hex[:16]}"
    created_at = now.isoformat().replace("+00:00", "Z")

    # Store originating_srv_ids as a comma-separated string for simplicity
    srv_ids_str = ",".join(request.originating_srv_ids)

    cursor.execute(
        """
        INSERT INTO provisionals (
            provisional_id, target_passport_ref, action_type, expiry,
            originating_srv_ids, degraded_mode, actor_type, created_at, revoked
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            provisional_id,
            request.target_passport_ref,
            request.action_type,
            request.expiry,
            srv_ids_str,
            1 if request.degraded_mode else 0,
            request.actor_type,
            created_at,
            0
        )
    )
    conn.commit()
    conn.close()

    return {
        "provisional_id": provisional_id
    }