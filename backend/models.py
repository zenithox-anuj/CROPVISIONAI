"""CropVision AI - Data models (Mongo-friendly Pydantic)."""
from datetime import datetime, timezone
from typing import Any, Optional, List, Annotated
from pydantic import BaseModel, Field, EmailStr, BeforeValidator, ConfigDict
from bson import ObjectId
import uuid


def _to_str(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v) if v is not None else ""


PyObjectId = Annotated[str, BeforeValidator(_to_str)]


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class BaseDoc(BaseModel):
    """Base document with UUID id + timestamps."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=now_utc)


# ------------------ Auth ------------------
class UserRole:
    FARMER = "farmer"
    AGRONOMIST = "agronomist"
    ADMIN = "admin"
    COOP_ADMIN = "coop_admin"


class Cooperative(BaseDoc):
    name: str
    region: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class CooperativeCreate(BaseModel):
    name: str
    region: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None


class User(BaseDoc):
    email: EmailStr
    name: str
    role: str = UserRole.FARMER
    language: str = "en"  # en | hi
    phone: Optional[str] = None
    cooperative_id: Optional[str] = None
    password_hash: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str
    language: str
    phone: Optional[str] = None
    cooperative_id: Optional[str] = None


class RegisterIn(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=6)
    role: str = UserRole.FARMER
    language: str = "en"
    phone: Optional[str] = None
    cooperative_id: Optional[str] = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshIn(BaseModel):
    refresh_token: str


# ------------------ Fields (agricultural plots) ------------------
class GeoPoint(BaseModel):
    """GeoJSON Point (lng, lat)."""
    type: str = "Point"
    coordinates: List[float]  # [lng, lat]


class GeoPolygon(BaseModel):
    """GeoJSON Polygon: outer ring only. First == last coordinate."""
    type: str = "Polygon"
    coordinates: List[List[List[float]]]  # [[[lng,lat], ...]]


class Field_(BaseDoc):
    """A monitored agricultural field."""
    owner_id: str
    cooperative_id: Optional[str] = None
    name: str
    crop: str  # e.g. wheat, rice, maize, cotton
    region: str  # e.g. "Punjab, India"
    area_hectares: float
    location: GeoPoint  # centroid
    polygon: Optional[GeoPolygon] = None  # optional field boundary
    # health snapshot (updated by inference)
    health_score: float = 100.0  # 0-100
    last_scan_at: Optional[datetime] = None
    status: str = "healthy"  # healthy | monitoring | diseased | critical


class FieldCreate(BaseModel):
    name: str
    crop: str
    region: str
    area_hectares: float
    lat: float
    lng: float
    polygon: Optional[List[List[float]]] = None  # list of [lng,lat] outer ring
    cooperative_id: Optional[str] = None


# ------------------ Inference Jobs ------------------
class JobStatus:
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"


class InferenceJob(BaseDoc):
    field_id: str
    owner_id: str
    image_b64: Optional[str] = None  # kept short-lived; cleared after inference
    status: str = JobStatus.QUEUED
    attempts: int = 0
    max_attempts: int = 3
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    detection_id: Optional[str] = None


# ------------------ Detections & Advisories ------------------
class Detection(BaseDoc):
    field_id: str
    owner_id: str
    disease: str  # e.g. "Leaf Rust"
    severity: str  # low | moderate | high | critical
    confidence: float  # 0-1
    affected_area_pct: float
    raw_model_output: dict = Field(default_factory=dict)
    reasoning_trace: List[dict] = Field(default_factory=list)  # LangGraph steps
    advisory_en: str = ""
    advisory_hi: str = ""
    escalated: bool = False
    escalated_to: Optional[str] = None  # agronomist user_id


# ------------------ Alerts (delivery log) ------------------
class Alert(BaseDoc):
    detection_id: str
    field_id: str
    owner_id: str
    channel: str  # sms | whatsapp | dashboard
    severity: str
    message_en: str
    message_hi: str
    delivered: bool = False
    delivered_at: Optional[datetime] = None
    delivery_error: Optional[str] = None


# ------------------ Audit log ------------------
class AuditLog(BaseDoc):
    actor_id: Optional[str] = None
    action: str
    resource: str
    resource_id: Optional[str] = None
    meta: dict = Field(default_factory=dict)


# ------------------ Requests ------------------
class InferenceRequest(BaseModel):
    field_id: str
    image_b64: str  # base64 image (JPEG/PNG/WEBP)


class EscalateRequest(BaseModel):
    agronomist_id: Optional[str] = None
    note: Optional[str] = None
