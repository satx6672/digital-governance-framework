# DGF Middleware Slice

This document defines the **DGF Middleware Slice** — a minimal, optional coordination layer that sits alongside the core Digital Governance Framework architecture.

It provides standardized interfaces for:
- Continuity Reference establishment
- Systemic Risk Vector (SRV) emission and consumption
- Provisional action signaling and revocation
- Asymmetric Context Query (ACQ)

The middleware is designed to enable cross-platform risk coordination while remaining compatible with existing identity and safety systems. It is not a replacement for the core DGF governance architecture; it is a practical API/protocol layer that implements a focused subset of the framework’s coordination capabilities.

## OpenAPI Specification

The machine-readable API contract is defined here:

→ [`openapi.yaml`](../middleware/openapi.yaml)  
*(update the path if your file is located elsewhere)*

## OpenAPI Documentation

The API reference document is viewable here:

→ https://dgf-openapi-v1.redocly.app/openapi

## AI-Agent Support and W3C DID/VC Compatibility

The Middleware Slice treats **AI agents as first-class Holders**.

- An agent presents a standard W3C Verifiable Presentation containing its own DID and binding/capability Verifiable Credentials.
- Continuity References are derived from these presentations using normal DID resolution and verification (BBS selective disclosure preferred).
- The same SRV, Provisional, and ACQ interfaces work for both human and agent actors.
- Sponsor accountability is preserved through the verifiable agent-binding credential.
- Revocation of an agent’s binding or capability credentials (via standard status-list mechanisms) automatically invalidates related Continuity References and triggers provisional revocation.

All identity operations remain inside the W3C DID + Verifiable Credentials model. The middleware does not introduce a parallel identity system; it only adds the risk-coordination and provisional-response layer on top of that substrate.

## Formal Sub-Protocol Statements

### Sub-Protocol M.1 — Continuity Reference Lifecycle

A Continuity Reference SHALL be issued only after successful verification of a standard Verifiable Presentation that satisfies the relying-party policy, including BBS selective disclosure (or equivalent) and proof of non-revocation.

The maximum lifetime of any Continuity Reference SHALL be four (4) hours from the moment of successful verification.

Under detected partition or verification degradation, a locally cached continuity decision, if permitted by local policy, SHALL have a hard maximum lifetime of thirty (30) minutes and MUST be re-verified at the earliest opportunity.

A Continuity Reference is single-use for SRV emission within its lifetime unless explicitly refreshed by a new valid Verifiable Presentation. Revocation of any underlying binding or capability Verifiable Credential SHALL immediately invalidate all Continuity References derived from that credential.

### Sub-Protocol M.2 — SRV Confidence Dampening and Thresholds

Incoming confidence values SHALL be clamped to the closed interval [0.0, 1.0].

In normal mode the Middleware SHALL apply a confidence dampener of 0.85.  
In degraded mode (partition, missing ACQ, or incomplete mesh) the Middleware SHALL apply a confidence dampener of 0.60.

No cross-platform Provisional action SHALL be triggered unless the post-dampening confidence is at least 0.55.  
No SRV SHALL contribute to Composite formation or elevated trajectory state unless its post-dampening confidence is at least 0.70.

### Sub-Protocol M.3 — Provisional Action Bounds (Normal Mode)

The maximum initial expiry of any Provisional action SHALL be forty-eight (48) hours.

The maximum cumulative duration of Provisional actions against the same Continuity Reference within any rolling seven (7) day window SHALL be seventy-two (72) hours. Exceeding this limit SHALL freeze further automated Provisional actions against that Continuity Reference and force threshold or manual review.

Permitted action types are limited to: `CHALLENGE_PROMPT`, `RATE_LIMIT`, `TEMPORARY_INTERACTION_ZONE`, and `CAPABILITY_SUSPEND` (agent-specific).

### Sub-Protocol M.4 — Provisional Action Bounds (Degraded / Partition Mode)

Upon declaration of partition or degraded mode the following stricter bounds SHALL apply:

- Maximum initial expiry: twelve (12) hours.
- Maximum cumulative duration within any rolling seven (7) day window: twenty-four (24) hours.

Preferred action types, in descending order of preference, are `CHALLENGE_PROMPT` followed by light `RATE_LIMIT`.

`TEMPORARY_INTERACTION_ZONE` and `CAPABILITY_SUSPEND` are permitted only when post-dampening confidence is at least 0.75 **and** the harm class is Class 1 or Class 2.

Absolute (irreversible) enforcement actions remain fully prohibited until quorum is restored.

### Sub-Protocol M.5 — Asymmetric Context Query (ACQ) Timing and Failure Handling

An Asymmetric Context Query SHALL time out after fifteen (15) seconds.

On timeout or error a Provisional action may still proceed; however, an additional dampening factor of 0.80 SHALL be applied and the applicable expiry ceiling SHALL be halved (subject to the degraded-mode maximum).

A consuming platform is limited to one (1) ACQ attempt per SRV.

### Sub-Protocol M.6 — Partition Detection, Declaration, and Recovery

Coordination nodes SHALL emit heartbeats at a strict interval of twenty-four (24) hours.

A quorum timeout of seventy-two (72) hours of missing valid heartbeats SHALL trigger node-replacement procedures.

Partition SHALL be declared when either:  
(a) a majority of attested mesh participants is unreachable for more than sixty (60) consecutive seconds, or  
(b) the SRV or ACQ failure rate reaches or exceeds thirty percent (30 %) over any five (5) minute window.

Upon partition declaration all new Provisional actions SHALL automatically enter degraded mode.

Reconciliation SHALL begin within five (5) minutes of partition healing. All degraded Provisionals that no longer satisfy normal-mode policy after reconciliation MUST be revoked. Downstream membranes SHALL flush the corresponding constraints with a target latency of five (5) seconds or less.

### Sub-Protocol M.7 — Fail-Safe Default and Narrow Fail-Secure Exception

Under degraded confidence or partition the default posture SHALL be fail-safe (preserve agent or user access).

A fail-secure Provisional action is permitted only for harm classes designated Class 1 that also carry independent multi-modal corroboration **and** post-dampening confidence of at least 0.85. Even in this case the action remains Provisional and is bound by the degraded-mode expiry ceilings.

No Provisional action may be converted into an Absolute Enforcement action without a completed threshold consensus after connectivity and quorum are restored.

### Sub-Protocol M.8 — Agent-Specific Obligations

When the `actor_type` is `"agent"`:

- Sponsor notification is mandatory for any Provisional whose duration exceeds one (1) hour or whose action type is stronger than `CHALLENGE_PROMPT`.
- `CAPABILITY_SUSPEND` actions MUST reference the specific capability Verifiable Credential(s) being restricted.
- Revocation of the agent’s binding or capability Verifiable Credential via standard status-list mechanisms SHALL immediately invalidate any Continuity Reference derived from that credential and SHALL trigger automatic revocation of all related Provisional actions.

### Sub-Protocol M.9 — Simplified Trajectory and Composite Formation (MVP)

Composite formation requires SRVs of differing harm classes from at least two (2) distinct participation-attested platforms, each carrying post-dampening confidence of at least 0.70.

The low-severity trajectory retention window in the MVP SHALL be forty-five (45) days, with progressive confidence decay applied after day thirty (30). The full ninety (90) day window and advanced decay functions are deferred to a subsequent protocol revision.

### Sub-Protocol M.10 — Parameter Governance

All numeric parameters defined in Sub-Protocols M.1 through M.9 are versioned. Any change requires public notice of at least fourteen (14) days, recorded multi-party approval according to the Middleware governance process, and publication of updated reference test vectors.

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

## Environment variables

| Variable | Default | Meaning |
|----------|---------|---------|
| `DGF_DB_PATH` | `dgf_middleware.db` | SQLite database file path |
| `DGF_DEBUG` | `0` | Set to `1` to enable `/debug/*` routes |

## Canonical end-to-end test

See `e2e-demo.http` or `e2e-demo.sh` (or the curl sequence in this repo) for Continuity → SRV → Provisional → Revoke.

## Docker

docker build -t dgf-middleware-thin:0.1.0 .
docker run --rm -p 8000:8000 dgf-middleware-thin:0.1.0

## API reference

OpenAPI-oriented public docs (design contract):  
https://dgf-middleware-slice.redocly.app/

## Version

`v0.1.0-thin-slice-poc` (see Git tags)
