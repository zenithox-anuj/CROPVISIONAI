"""CropVision AI — main FastAPI server.

Architecture:
  /api/auth/*        — JWT auth (register/login/refresh/me) + RBAC
  /api/fields/*      — CRUD for monitored fields (2dsphere geo index)
  /api/inference/*   — enqueue image, job status, results
  /api/detections/*  — read detections, escalate to agronomist
  /api/alerts/*      — alert feed (delivery log)
  /api/agronomist/*  — escalation queue
  /api/admin/*       — pipeline health, audit trail, metrics
  /api/health, /api/metrics — observability
"""
import os
import logging
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

from models import (
    User, UserPublic, RegisterIn, LoginIn, TokenPair, RefreshIn, UserRole,
    Field_, FieldCreate, GeoPoint, GeoPolygon,
    InferenceJob, JobStatus, InferenceRequest,
    Detection, Alert, AuditLog, EscalateRequest, iso, now_utc,
    Cooperative, CooperativeCreate,
)
from auth import (
    hash_password, verify_password, make_access, make_refresh, decode_token,
    current_user, require_role, to_public,
)
from vision import analyze_crop_image
from langgraph_agent import run_reasoning, state_to_dict
from job_queue import JobQueue
import twilio_delivery

log = logging.getLogger("cropvision")
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')

# ---------- Mongo ----------
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
_client = AsyncIOMotorClient(MONGO_URL)
_db = _client[DB_NAME]


def get_db() -> AsyncIOMotorDatabase:
    return _db


# ---------- App ----------
app = FastAPI(title="CropVision AI", version="1.0.0")
api = APIRouter(prefix="/api")


# ---------- Rate limit (very light, in-memory) ----------
_rate_state: dict[str, list[float]] = {}


async def rate_limit(req: Request, limit: int = 60, window: float = 60.0):
    key = req.client.host if req.client else "anon"
    now = asyncio.get_event_loop().time()
    bucket = _rate_state.setdefault(key, [])
    bucket[:] = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Too many requests")
    bucket.append(now)


# ---------- Audit ----------
async def audit(actor_id: Optional[str], action: str, resource: str,
                resource_id: Optional[str] = None, meta: Optional[dict] = None):
    entry = AuditLog(actor_id=actor_id, action=action, resource=resource,
                     resource_id=resource_id, meta=meta or {})
    d = entry.model_dump()
    d["created_at"] = iso(d["created_at"])
    await _db.audit_logs.insert_one(d)


# ================================================================
# AUTH
# ================================================================
@api.post("/auth/register", response_model=TokenPair)
async def register(payload: RegisterIn, req: Request):
    await rate_limit(req, limit=20)
    if payload.role not in (UserRole.FARMER, UserRole.AGRONOMIST, UserRole.COOP_ADMIN):
        # admins can't self-register
        raise HTTPException(status_code=400, detail="Invalid role for signup")
    existing = await _db.users.find_one({"email": payload.email.lower()})
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    if payload.cooperative_id:
        coop = await _db.cooperatives.find_one({"id": payload.cooperative_id}, {"_id": 0})
        if not coop:
            raise HTTPException(status_code=400, detail="Cooperative not found")
    user = User(
        email=payload.email.lower(), name=payload.name, role=payload.role,
        language=payload.language, phone=payload.phone,
        cooperative_id=payload.cooperative_id,
        password_hash=hash_password(payload.password),
    )
    doc = user.model_dump()
    doc["created_at"] = iso(doc["created_at"])
    await _db.users.insert_one(doc)
    await audit(user.id, "user.register", "user", user.id)
    return TokenPair(
        access_token=make_access(user.id, user.role),
        refresh_token=make_refresh(user.id, user.role),
        user=to_public(user),
    )


@api.post("/auth/login", response_model=TokenPair)
async def login(payload: LoginIn, req: Request):
    await rate_limit(req, limit=20)
    doc = await _db.users.find_one({"email": payload.email.lower()}, {"_id": 0})
    if not doc or not verify_password(payload.password, doc["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user = User(**doc)
    await audit(user.id, "user.login", "user", user.id)
    return TokenPair(
        access_token=make_access(user.id, user.role),
        refresh_token=make_refresh(user.id, user.role),
        user=to_public(user),
    )


@api.post("/auth/refresh", response_model=TokenPair)
async def refresh(payload: RefreshIn):
    p = decode_token(payload.refresh_token, "refresh")
    doc = await _db.users.find_one({"id": p["sub"]}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=401, detail="User not found")
    user = User(**doc)
    # rotate refresh token
    return TokenPair(
        access_token=make_access(user.id, user.role),
        refresh_token=make_refresh(user.id, user.role),
        user=to_public(user),
    )


@api.get("/auth/me", response_model=UserPublic)
async def me(user: User = Depends(current_user)):
    return to_public(user)


# ================================================================
# FIELDS
# ================================================================
@api.get("/fields")
async def list_fields(user: User = Depends(current_user), region: Optional[str] = None):
    q: dict = {}
    if user.role == UserRole.FARMER:
        q["owner_id"] = user.id
    elif user.role == UserRole.COOP_ADMIN:
        q["cooperative_id"] = user.cooperative_id
    if region:
        q["region"] = region
    docs = await _db.fields.find(q, {"_id": 0}).sort("created_at", -1).to_list(500)
    return docs


@api.post("/fields")
async def create_field(payload: FieldCreate, user: User = Depends(current_user)):
    polygon_doc = None
    if payload.polygon and len(payload.polygon) >= 3:
        ring = [list(map(float, p)) for p in payload.polygon]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        polygon_doc = GeoPolygon(coordinates=[ring])
    coop_id = payload.cooperative_id or user.cooperative_id
    f = Field_(
        owner_id=user.id, cooperative_id=coop_id,
        name=payload.name, crop=payload.crop,
        region=payload.region, area_hectares=payload.area_hectares,
        location=GeoPoint(coordinates=[payload.lng, payload.lat]),
        polygon=polygon_doc,
    )
    doc = f.model_dump()
    doc["created_at"] = iso(doc["created_at"])
    doc["last_scan_at"] = None
    await _db.fields.insert_one(doc)
    await audit(user.id, "field.create", "field", f.id)
    doc.pop("_id", None)
    return doc


@api.get("/fields/{field_id}")
async def get_field(field_id: str, user: User = Depends(current_user)):
    doc = await _db.fields.find_one({"id": field_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Field not found")
    if user.role == UserRole.FARMER and doc["owner_id"] != user.id:
        raise HTTPException(403, "Forbidden")
    if user.role == UserRole.COOP_ADMIN and doc.get("cooperative_id") != user.cooperative_id:
        raise HTTPException(403, "Forbidden")
    return doc


@api.get("/fields/{field_id}/history")
async def field_history(field_id: str, user: User = Depends(current_user)):
    dets = await _db.detections.find({"field_id": field_id}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return dets


# ================================================================
# INFERENCE PIPELINE
# ================================================================
async def _process_job(job_id: str) -> None:
    """Worker: pull image → vision → LangGraph → persist detection + alert."""
    db = get_db()
    job_doc = await db.inference_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job_doc:
        return
    job = InferenceJob(**job_doc)
    field_doc = await db.fields.find_one({"id": job.field_id}, {"_id": 0})
    if not field_doc:
        await db.inference_jobs.update_one({"id": job_id}, {"$set": {
            "status": JobStatus.FAILED, "error": "field not found",
            "finished_at": iso(now_utc()),
        }})
        return
    await db.inference_jobs.update_one({"id": job_id}, {"$set": {
        "status": JobStatus.RUNNING, "started_at": iso(now_utc()),
        "attempts": job.attempts + 1,
    }})

    try:
        vision_out = await analyze_crop_image(job.image_b64 or "", crop_hint=field_doc.get("crop", ""),
                                               session_id=f"vision-{job.field_id}")
        state = await run_reasoning(
            field_meta={"field_id": job.field_id, "crop": field_doc.get("crop"),
                        "region": field_doc.get("region")},
            raw_vision=vision_out,
        )
        # persist detection
        det = Detection(
            field_id=job.field_id, owner_id=job.owner_id,
            disease=state.disease, severity=state.severity,
            confidence=state.confidence,
            affected_area_pct=state.affected_area_pct,
            raw_model_output=vision_out,
            reasoning_trace=state.trace,
            advisory_en=state.advisory_en, advisory_hi=state.advisory_hi,
            escalated=state.escalate,
        )
        # find an agronomist for escalation
        if state.escalate:
            agro = await db.users.find_one({"role": UserRole.AGRONOMIST}, {"_id": 0})
            if agro:
                det.escalated_to = agro["id"]
        d = det.model_dump()
        d["created_at"] = iso(d["created_at"])
        await db.detections.insert_one(d)

        # alert
        a = Alert(
            detection_id=det.id, field_id=det.field_id, owner_id=det.owner_id,
            channel="dashboard", severity=det.severity,
            message_en=det.advisory_en, message_hi=det.advisory_hi,
            delivered=True, delivered_at=now_utc(),
        )
        ad = a.model_dump()
        ad["created_at"] = iso(ad["created_at"])
        ad["delivered_at"] = iso(a.delivered_at)
        await db.alerts.insert_one(ad)

        # Twilio WhatsApp delivery (real if configured, else mock)
        try:
            owner = await db.users.find_one({"id": det.owner_id}, {"_id": 0})
            if owner and owner.get("phone"):
                msg_text = det.advisory_hi if owner.get("language") == "hi" else det.advisory_en
                header = f"[CropVision] {field_doc.get('name','field')} — {det.disease} ({det.severity})\n\n"
                result = await twilio_delivery.send("whatsapp", owner["phone"], header + msg_text)
                wa_alert = Alert(
                    detection_id=det.id, field_id=det.field_id, owner_id=det.owner_id,
                    channel="whatsapp", severity=det.severity,
                    message_en=det.advisory_en, message_hi=det.advisory_hi,
                    delivered=result["delivered"],
                    delivered_at=now_utc() if result["delivered"] else None,
                    delivery_error=result.get("error"),
                )
                wa_doc = wa_alert.model_dump()
                wa_doc["created_at"] = iso(wa_doc["created_at"])
                wa_doc["delivered_at"] = iso(wa_alert.delivered_at) if wa_alert.delivered_at else None
                await db.alerts.insert_one(wa_doc)
        except Exception:
            log.exception("Twilio delivery step failed (non-fatal)")

        # update field snapshot
        # health score: 100 - affected_area
        health = max(0.0, 100.0 - det.affected_area_pct)
        status = ("healthy" if health > 80 else "monitoring" if health > 65
                  else "diseased" if health > 50 else "critical")
        await db.fields.update_one({"id": job.field_id}, {"$set": {
            "health_score": round(health, 1),
            "status": status,
            "last_scan_at": iso(now_utc()),
        }})

        await db.inference_jobs.update_one({"id": job_id}, {"$set": {
            "status": JobStatus.SUCCEEDED,
            "finished_at": iso(now_utc()),
            "detection_id": det.id,
            "image_b64": None,  # drop big blob after processing
        }})
        await audit(job.owner_id, "inference.succeeded", "job", job_id,
                    {"disease": det.disease, "severity": det.severity})
    except Exception as e:
        log.exception("Job %s failed", job_id)
        cur = await db.inference_jobs.find_one({"id": job_id}, {"_id": 0})
        attempts = (cur or {}).get("attempts", 1)
        if attempts >= (cur or {}).get("max_attempts", 3):
            new_status = JobStatus.DEAD
        else:
            new_status = JobStatus.FAILED
            # retry: re-enqueue
            await queue.enqueue(job_id)
        await db.inference_jobs.update_one({"id": job_id}, {"$set": {
            "status": new_status, "error": str(e),
            "finished_at": iso(now_utc()),
        }})


queue = JobQueue(worker=_process_job, concurrency=2)


@api.post("/inference/enqueue")
async def enqueue_inference(payload: InferenceRequest, user: User = Depends(current_user)):
    field_doc = await _db.fields.find_one({"id": payload.field_id}, {"_id": 0})
    if not field_doc:
        raise HTTPException(404, "Field not found")
    if user.role == UserRole.FARMER and field_doc["owner_id"] != user.id:
        raise HTTPException(403, "Forbidden")
    job = InferenceJob(
        field_id=payload.field_id, owner_id=field_doc["owner_id"],
        image_b64=payload.image_b64,
    )
    doc = job.model_dump()
    doc["created_at"] = iso(doc["created_at"])
    doc["started_at"] = None
    doc["finished_at"] = None
    await _db.inference_jobs.insert_one(doc)
    await queue.enqueue(job.id)
    await audit(user.id, "inference.enqueued", "job", job.id, {"field_id": payload.field_id})
    return {"job_id": job.id, "status": job.status}


@api.get("/inference/jobs/{job_id}")
async def get_job(job_id: str, user: User = Depends(current_user)):
    doc = await _db.inference_jobs.find_one({"id": job_id}, {"_id": 0, "image_b64": 0})
    if not doc:
        raise HTTPException(404, "Job not found")
    if user.role == UserRole.FARMER and doc["owner_id"] != user.id:
        raise HTTPException(403, "Forbidden")
    return doc


@api.get("/inference/jobs")
async def list_jobs(user: User = Depends(current_user), limit: int = 50):
    q: dict = {}
    if user.role == UserRole.FARMER:
        q["owner_id"] = user.id
    docs = await _db.inference_jobs.find(q, {"_id": 0, "image_b64": 0}).sort("created_at", -1).to_list(limit)
    return docs


# ================================================================
# DETECTIONS & ALERTS
# ================================================================
@api.get("/detections")
async def list_detections(user: User = Depends(current_user),
                          field_id: Optional[str] = None,
                          severity: Optional[str] = None,
                          limit: int = 100):
    q: dict = {}
    if user.role == UserRole.FARMER:
        q["owner_id"] = user.id
    elif user.role == UserRole.COOP_ADMIN:
        # coop scoping: find field ids in this coop
        coop_field_ids = [f["id"] async for f in _db.fields.find(
            {"cooperative_id": user.cooperative_id}, {"id": 1, "_id": 0})]
        q["field_id"] = {"$in": coop_field_ids}
    if field_id:
        q["field_id"] = field_id
    if severity:
        q["severity"] = severity
    return await _db.detections.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


@api.get("/detections/{det_id}")
async def get_detection(det_id: str, user: User = Depends(current_user)):
    doc = await _db.detections.find_one({"id": det_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Detection not found")
    if user.role == UserRole.FARMER and doc["owner_id"] != user.id:
        raise HTTPException(403, "Forbidden")
    if user.role == UserRole.COOP_ADMIN:
        field = await _db.fields.find_one({"id": doc["field_id"]}, {"_id": 0})
        if not field or field.get("cooperative_id") != user.cooperative_id:
            raise HTTPException(403, "Forbidden")
    return doc


@api.post("/detections/{det_id}/escalate")
async def escalate(det_id: str, payload: EscalateRequest,
                   user: User = Depends(require_role(UserRole.FARMER, UserRole.AGRONOMIST))):
    doc = await _db.detections.find_one({"id": det_id}, {"_id": 0})
    if not doc:
        raise HTTPException(404, "Not found")
    target = payload.agronomist_id
    if not target:
        agro = await _db.users.find_one({"role": UserRole.AGRONOMIST}, {"_id": 0})
        target = agro["id"] if agro else None
    await _db.detections.update_one({"id": det_id}, {"$set": {
        "escalated": True, "escalated_to": target,
    }})
    await audit(user.id, "detection.escalate", "detection", det_id, {"to": target})
    return {"ok": True, "escalated_to": target}


@api.get("/alerts")
async def list_alerts(user: User = Depends(current_user), limit: int = 100):
    q: dict = {}
    if user.role == UserRole.FARMER:
        q["owner_id"] = user.id
    elif user.role == UserRole.COOP_ADMIN:
        coop_field_ids = [f["id"] async for f in _db.fields.find(
            {"cooperative_id": user.cooperative_id}, {"id": 1, "_id": 0})]
        q["field_id"] = {"$in": coop_field_ids}
    return await _db.alerts.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


# ================================================================
# COOPERATIVES  (multi-tenant)
# ================================================================
@api.get("/cooperatives")
async def list_cooperatives():
    """Public list for signup dropdown."""
    return await _db.cooperatives.find({}, {"_id": 0, "contact_email": 0, "contact_phone": 0}).to_list(200)


@api.post("/cooperatives")
async def create_cooperative(payload: CooperativeCreate,
                             user: User = Depends(require_role(UserRole.ADMIN))):
    coop = Cooperative(**payload.model_dump())
    doc = coop.model_dump()
    doc["created_at"] = iso(doc["created_at"])
    await _db.cooperatives.insert_one(doc)
    await audit(user.id, "cooperative.create", "cooperative", coop.id)
    doc.pop("_id", None)
    return doc


@api.get("/coop/dashboard")
async def coop_dashboard(user: User = Depends(require_role(UserRole.COOP_ADMIN))):
    """Aggregations for a coop_admin's cooperative."""
    coop_id = user.cooperative_id
    if not coop_id:
        raise HTTPException(400, "User has no cooperative")
    coop = await _db.cooperatives.find_one({"id": coop_id}, {"_id": 0})
    fields = await _db.fields.find({"cooperative_id": coop_id}, {"_id": 0}).to_list(1000)
    farmers = await _db.users.find(
        {"cooperative_id": coop_id, "role": UserRole.FARMER},
        {"_id": 0, "password_hash": 0}).to_list(1000)
    field_ids = [f["id"] for f in fields]
    recent_dets = await _db.detections.find(
        {"field_id": {"$in": field_ids}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    total_area = sum(f.get("area_hectares", 0) for f in fields)
    avg_health = (sum(f.get("health_score", 0) for f in fields) / len(fields)) if fields else 0
    by_status: dict = {}
    for f in fields:
        by_status[f.get("status", "healthy")] = by_status.get(f.get("status", "healthy"), 0) + 1
    by_disease: dict = {}
    for d in recent_dets[:100]:
        by_disease[d["disease"]] = by_disease.get(d["disease"], 0) + 1

    return {
        "cooperative": coop,
        "totals": {
            "fields": len(fields), "farmers": len(farmers),
            "total_hectares": round(total_area, 1),
            "avg_health": round(avg_health, 1),
            "detections_recent": len(recent_dets),
        },
        "by_status": by_status,
        "top_diseases": sorted(by_disease.items(), key=lambda x: -x[1])[:6],
        "recent_detections": recent_dets[:15],
        "farmers": farmers[:50],
    }


# ================================================================
# AGRONOMIST QUEUE
# ================================================================
@api.get("/agronomist/queue")
async def agronomist_queue(user: User = Depends(require_role(UserRole.AGRONOMIST))):
    return await _db.detections.find(
        {"escalated": True, "escalated_to": user.id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(200)


# ================================================================
# ADMIN — pipeline health
# ================================================================
@api.get("/admin/pipeline")
async def admin_pipeline(user: User = Depends(require_role(UserRole.ADMIN))):
    total_jobs = await _db.inference_jobs.count_documents({})
    running = await _db.inference_jobs.count_documents({"status": JobStatus.RUNNING})
    failed = await _db.inference_jobs.count_documents({"status": JobStatus.FAILED})
    dead = await _db.inference_jobs.count_documents({"status": JobStatus.DEAD})
    succeeded = await _db.inference_jobs.count_documents({"status": JobStatus.SUCCEEDED})
    return {
        "queue": queue.stats(),
        "jobs": {"total": total_jobs, "running": running, "failed": failed,
                 "dead": dead, "succeeded": succeeded},
    }


@api.get("/admin/audit")
async def admin_audit(user: User = Depends(require_role(UserRole.ADMIN)), limit: int = 100):
    return await _db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)


# ================================================================
# OBSERVABILITY
# ================================================================
@api.get("/health")
async def health():
    try:
        await _db.command("ping")
        db_ok = True
    except Exception:
        db_ok = False
    return {"ok": db_ok, "ts": datetime.now(timezone.utc).isoformat(),
            "queue": queue.stats()}


@api.get("/metrics")
async def metrics():
    counts = {
        "users": await _db.users.count_documents({}),
        "fields": await _db.fields.count_documents({}),
        "detections": await _db.detections.count_documents({}),
        "alerts": await _db.alerts.count_documents({}),
        "jobs": await _db.inference_jobs.count_documents({}),
    }
    return {"counts": counts, "queue": queue.stats(),
            "ts": datetime.now(timezone.utc).isoformat()}


@api.get("/")
async def root():
    return {"service": "CropVision AI", "status": "ok", "version": "1.0.0"}


# ================================================================
# n8n webhook — imagery ingestion trigger
# ================================================================
@api.post("/n8n/ingest")
async def n8n_ingest(payload: dict, req: Request):
    """Webhook entry point for n8n: {field_id, image_b64, api_key}"""
    api_key = req.headers.get("x-api-key") or payload.get("api_key")
    if api_key != os.environ.get("EMERGENT_LLM_KEY", "internal"):
        # not real secret — just gate the webhook
        pass  # allow in dev
    field_id = payload.get("field_id")
    image_b64 = payload.get("image_b64")
    if not field_id or not image_b64:
        raise HTTPException(400, "field_id and image_b64 required")
    field_doc = await _db.fields.find_one({"id": field_id}, {"_id": 0})
    if not field_doc:
        raise HTTPException(404, "Field not found")
    job = InferenceJob(field_id=field_id, owner_id=field_doc["owner_id"], image_b64=image_b64)
    doc = job.model_dump()
    doc["created_at"] = iso(doc["created_at"])
    doc["started_at"] = None
    doc["finished_at"] = None
    await _db.inference_jobs.insert_one(doc)
    await queue.enqueue(job.id)
    return {"job_id": job.id}


# ---------- Wire up ----------
app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    # indexes
    await _db.fields.create_index([("location", "2dsphere")])
    await _db.users.create_index("email", unique=True)
    await _db.detections.create_index([("field_id", 1), ("created_at", -1)])
    await _db.alerts.create_index([("owner_id", 1), ("created_at", -1)])
    await _db.inference_jobs.create_index([("status", 1), ("created_at", -1)])
    queue.start()
    log.info("CropVision AI startup complete")


@app.on_event("shutdown")
async def _shutdown():
    await queue.stop()
    _client.close()
