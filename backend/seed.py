"""Seed sample data for CropVision AI demo."""
import asyncio
import os
import random
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

from models import (User, UserRole, Field_, GeoPoint, GeoPolygon,
                    Detection, Alert, Cooperative, now_utc, iso)
from auth import hash_password


def square_polygon(lat: float, lng: float, half_deg: float = 0.008) -> GeoPolygon:
    """Small square polygon around a point (~1km at these latitudes)."""
    ring = [
        [lng - half_deg, lat - half_deg],
        [lng + half_deg, lat - half_deg],
        [lng + half_deg, lat + half_deg],
        [lng - half_deg, lat + half_deg],
        [lng - half_deg, lat - half_deg],
    ]
    return GeoPolygon(coordinates=[ring])


async def seed():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    print("Clearing existing seed data...")
    for coll in ["users", "fields", "detections", "alerts", "inference_jobs",
                 "audit_logs", "cooperatives"]:
        await db[coll].delete_many({})

    # Cooperatives
    coops = [
        Cooperative(name="Punjab Kisan Cooperative", region="Punjab, India",
                    contact_email="contact@pkc.in", contact_phone="+919000000100"),
        Cooperative(name="Haryana Grain Growers", region="Haryana, India",
                    contact_email="contact@hgg.in", contact_phone="+919000000101"),
    ]
    for c in coops:
        d = c.model_dump()
        d["created_at"] = iso(d["created_at"])
        await db.cooperatives.insert_one(d)
    print(f"Seeded {len(coops)} cooperatives")

    # Users
    farmer = User(email="farmer@cropvision.ai", name="Ramesh Kumar", role=UserRole.FARMER,
                  language="hi", phone="+919000000001",
                  cooperative_id=coops[0].id,
                  password_hash=hash_password("farmer123"))
    farmer2 = User(email="farmer2@cropvision.ai", name="Suresh Singh", role=UserRole.FARMER,
                   language="hi", phone="+919000000004",
                   cooperative_id=coops[0].id,
                   password_hash=hash_password("farmer123"))
    agro = User(email="agronomist@cropvision.ai", name="Dr. Priya Sharma", role=UserRole.AGRONOMIST,
                language="en", phone="+919000000002",
                password_hash=hash_password("agro123"))
    admin = User(email="admin@cropvision.ai", name="Admin", role=UserRole.ADMIN,
                 language="en", phone="+919000000003",
                 password_hash=hash_password("admin123"))
    coop_admin = User(email="coop@cropvision.ai", name="Kanwar Sandhu", role=UserRole.COOP_ADMIN,
                      language="en", phone="+919000000005",
                      cooperative_id=coops[0].id,
                      password_hash=hash_password("coop123"))
    for u in (farmer, farmer2, agro, admin, coop_admin):
        doc = u.model_dump()
        doc["created_at"] = iso(doc["created_at"])
        await db.users.insert_one(doc)
    print("Seeded 5 users")

    # Fields — spread across Punjab/Haryana/UP regions with polygon boundaries
    field_specs = [
        ("Green Acre 1", "wheat", "Punjab, India", 4.2, 30.9010, 75.8573, farmer, coops[0]),
        ("Rice Paddy North", "rice", "Punjab, India", 6.8, 30.9250, 75.9010, farmer, coops[0]),
        ("Cotton Belt A", "cotton", "Haryana, India", 3.5, 29.0588, 76.0856, farmer2, coops[1]),
        ("Maize Field 7", "maize", "Uttar Pradesh, India", 5.0, 26.8467, 80.9462, farmer, None),
        ("Sugarcane East", "sugarcane", "Uttar Pradesh, India", 8.1, 27.1767, 78.0081, farmer, None),
        ("Wheat West Plot", "wheat", "Punjab, India", 2.9, 31.6340, 74.8723, farmer, coops[0]),
        ("Rice Bhaini Sahib", "rice", "Punjab, India", 3.1, 30.7500, 76.2000, farmer2, coops[0]),
    ]
    fields = []
    for name, crop, region, area, lat, lng, owner, coop in field_specs:
        half = 0.006 + random.random() * 0.006
        f = Field_(
            owner_id=owner.id,
            cooperative_id=coop.id if coop else None,
            name=name, crop=crop, region=region,
            area_hectares=area,
            location=GeoPoint(coordinates=[lng, lat]),
            polygon=square_polygon(lat, lng, half),
            health_score=round(random.uniform(55, 95), 1),
            last_scan_at=now_utc() - timedelta(hours=random.randint(1, 48)),
        )
        f.status = ("healthy" if f.health_score > 80
                    else "monitoring" if f.health_score > 65
                    else "diseased" if f.health_score > 50 else "critical")
        doc = f.model_dump()
        doc["created_at"] = iso(doc["created_at"])
        doc["last_scan_at"] = iso(doc["last_scan_at"]) if doc["last_scan_at"] else None
        await db.fields.insert_one(doc)
        fields.append(f)
    await db.fields.create_index([("location", "2dsphere")])
    print(f"Seeded {len(fields)} fields (with polygons)")

    # Detections + alerts for historical trend
    diseases = [("Leaf Rust", "high"), ("Powdery Mildew", "moderate"),
                ("Healthy", "low"), ("Bacterial Blight", "critical"),
                ("Nutrient Deficiency", "moderate"), ("Water Stress", "moderate")]
    det_count = 0
    for f in fields:
        for day_ago in range(0, 14, 2):
            d_name, sev = random.choice(diseases)
            det = Detection(
                field_id=f.id, owner_id=f.owner_id,
                disease=d_name, severity=sev,
                confidence=round(random.uniform(0.65, 0.95), 2),
                affected_area_pct=round(random.uniform(2, 45), 1),
                advisory_en=f"Detected {d_name} at {sev} severity. Apply recommended treatment and re-scan in 5-7 days.",
                advisory_hi=f"{d_name} पाया गया ({sev}). अनुशंसित उपचार करें और 5-7 दिनों में पुनः जांच करें।",
                escalated=(sev in ("high", "critical")),
                escalated_to=(agro.id if sev in ("high", "critical") else None),
            )
            doc = det.model_dump()
            doc["created_at"] = iso(now_utc() - timedelta(days=day_ago, hours=random.randint(0, 12)))
            await db.detections.insert_one(doc)
            det_count += 1
            a = Alert(
                detection_id=det.id, field_id=f.id, owner_id=f.owner_id,
                channel="dashboard", severity=sev,
                message_en=det.advisory_en, message_hi=det.advisory_hi,
                delivered=True, delivered_at=now_utc() - timedelta(days=day_ago),
            )
            ad = a.model_dump()
            ad["created_at"] = doc["created_at"]
            ad["delivered_at"] = iso(a.delivered_at) if a.delivered_at else None
            await db.alerts.insert_one(ad)
    print(f"Seeded {det_count} detections + alerts")

    print("\n=== Seed users ===")
    print("Farmer:      farmer@cropvision.ai / farmer123")
    print("Farmer 2:    farmer2@cropvision.ai / farmer123")
    print("Agronomist:  agronomist@cropvision.ai / agro123")
    print("Coop admin:  coop@cropvision.ai / coop123")
    print("Admin:       admin@cropvision.ai / admin123")
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
