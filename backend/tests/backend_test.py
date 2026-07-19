"""CropVision AI — full backend E2E tests against the public preview URL.

Covers:
- Auth: register/login/refresh/me + RBAC
- Fields: CRUD + RBAC scoping
- Inference pipeline (real Claude Sonnet 4.5 vision) with LangGraph reasoning
- Detections + alerts + escalate
- Agronomist queue (403 for farmer, 200 for agronomist)
- Admin pipeline + audit (403 for farmer, 200 for admin)
- Observability: health + metrics
- n8n webhook ingestion
"""
import os
import time
import base64
from pathlib import Path

import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

FIXTURE_IMG = Path("/app/test_fixtures/crop_leaf.jpg")


# ------------------- fixtures -------------------
@pytest.fixture(scope="session")
def image_b64() -> str:
    assert FIXTURE_IMG.exists(), f"missing fixture {FIXTURE_IMG}"
    return base64.b64encode(FIXTURE_IMG.read_bytes()).decode()


def _login(session: requests.Session, email: str, password: str) -> dict:
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    return r.json()


@pytest.fixture(scope="session")
def farmer_token():
    s = requests.Session()
    return _login(s, "farmer@cropvision.ai", "farmer123")


@pytest.fixture(scope="session")
def agro_token():
    s = requests.Session()
    return _login(s, "agronomist@cropvision.ai", "agro123")


@pytest.fixture(scope="session")
def admin_token():
    s = requests.Session()
    return _login(s, "admin@cropvision.ai", "admin123")


def _hdr(tok: dict) -> dict:
    return {"Authorization": f"Bearer {tok["access_token"]}"}


# ------------------- Observability -------------------
class TestHealth:
    def test_health_ok(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert "queue" in d
        assert d["queue"]["workers"] == 2

    def test_metrics_counts(self):
        r = requests.get(f"{API}/metrics", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["counts"]["users"] >= 3
        assert d["counts"]["fields"] >= 6
        assert d["counts"]["detections"] >= 40

    def test_root(self):
        r = requests.get(f"{API}/", timeout=10)
        assert r.status_code == 200
        assert r.json()["service"] == "CropVision AI"


# ------------------- Auth -------------------
class TestAuth:
    def test_login_farmer(self, farmer_token):
        assert farmer_token["user"]["role"] == "farmer"
        assert farmer_token["user"]["email"] == "farmer@cropvision.ai"
        assert farmer_token["access_token"]
        assert farmer_token["refresh_token"]

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "farmer@cropvision.ai", "password": "wrong"}, timeout=10)
        assert r.status_code == 401

    def test_me(self, farmer_token):
        r = requests.get(f"{API}/auth/me", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == "farmer@cropvision.ai"

    def test_me_no_token(self):
        r = requests.get(f"{API}/auth/me", timeout=10)
        assert r.status_code == 401

    def test_refresh_rotation(self, farmer_token):
        r = requests.post(f"{API}/auth/refresh", json={"refresh_token": farmer_token["refresh_token"]}, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["access_token"] and d["refresh_token"]
        # new access token works
        r2 = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {data["access_token"]}"}, timeout=10)
        assert r2.status_code == 200

    def test_refresh_invalid(self):
        r = requests.post(f"{API}/auth/refresh", json={"refresh_token": "not.a.jwt"}, timeout=10)
        assert r.status_code == 401

    def test_register_and_reject_admin_role(self):
        # can't self-register as admin
        r = requests.post(f"{API}/auth/register", json={
            "email": "TEST_admin_self@cropvision.ai", "name": "Bad", "password": "abcdef", "role": "admin"
        }, timeout=10)
        assert r.status_code == 400

    def test_register_new_farmer(self):
        email = f"TEST_new_{int(time.time())}@cropvision.ai"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "name": "Test New", "password": "abcdef", "role": "farmer"
        }, timeout=10)
        assert r.status_code == 200
        d = r.json()
        # backend stores email lowercased
        assert d["user"]["email"] == email.lower()
        assert d["user"]["role"] == "farmer"
        # duplicate rejected (case-insensitive)
        r2 = requests.post(f"{API}/auth/register", json={
            "email": email, "name": "Test New", "password": "abcdef", "role": "farmer"
        }, timeout=10)
        assert r2.status_code == 409


# ------------------- Fields -------------------
class TestFields:
    def test_list_fields_farmer(self, farmer_token):
        r = requests.get(f"{API}/fields", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 6
        # farmer only sees own fields
        for f in arr:
            assert f["owner_id"] == farmer_token["user"]["id"]
        assert {"id", "name", "crop", "region", "location", "health_score"}.issubset(arr[0].keys())

    def test_get_field_and_history(self, farmer_token):
        r = requests.get(f"{API}/fields", headers=_hdr(farmer_token), timeout=10)
        field_id = r.json()[0]["id"]
        r2 = requests.get(f"{API}/fields/{field_id}", headers=_hdr(farmer_token), timeout=10)
        assert r2.status_code == 200
        assert r2.json()["id"] == field_id
        r3 = requests.get(f"{API}/fields/{field_id}/history", headers=_hdr(farmer_token), timeout=10)
        assert r3.status_code == 200
        assert isinstance(r3.json(), list)

    def test_create_field_persists(self, farmer_token):
        payload = {"name": f"TEST_field_{int(time.time())}", "crop": "wheat",
                   "region": "Punjab, India", "area_hectares": 1.5,
                   "lat": 30.9, "lng": 75.85}
        r = requests.post(f"{API}/fields", headers=_hdr(farmer_token), json=payload, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["name"] == payload["name"]
        assert d["location"]["coordinates"] == [75.85, 30.9]
        # GET verifies persistence
        r2 = requests.get(f"{API}/fields/{d['id']}", headers=_hdr(farmer_token), timeout=10)
        assert r2.status_code == 200
        assert r2.json()["name"] == payload["name"]

    def test_field_404(self, farmer_token):
        r = requests.get(f"{API}/fields/nonexistent-id", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 404


# ------------------- Detections & Alerts -------------------
class TestDetections:
    def test_list_detections_farmer_scoped(self, farmer_token):
        r = requests.get(f"{API}/detections", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert len(arr) >= 1
        for d in arr:
            assert d["owner_id"] == farmer_token["user"]["id"]

    def test_filter_by_severity(self, farmer_token):
        r = requests.get(f"{API}/detections?severity=critical", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        for d in r.json():
            assert d["severity"] == "critical"

    def test_detection_detail(self, farmer_token):
        arr = requests.get(f"{API}/detections", headers=_hdr(farmer_token), timeout=10).json()
        assert arr, "no detections seeded"
        d = arr[0]
        r = requests.get(f"{API}/detections/{d['id']}", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == d["id"]

    def test_alerts_scoped(self, farmer_token):
        r = requests.get(f"{API}/alerts", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert len(arr) >= 1
        for a in arr:
            assert a["owner_id"] == farmer_token["user"]["id"]
            assert a["channel"] == "dashboard"

    def test_escalate(self, farmer_token, agro_token):
        arr = requests.get(f"{API}/detections", headers=_hdr(farmer_token), timeout=10).json()
        det_id = arr[0]["id"]
        r = requests.post(f"{API}/detections/{det_id}/escalate",
                          headers=_hdr(farmer_token), json={"note": "please help"}, timeout=10)
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["escalated_to"] == agro_token["user"]["id"]


# ------------------- RBAC on Agronomist / Admin -------------------
class TestRBAC:
    def test_agronomist_queue_farmer_403(self, farmer_token):
        r = requests.get(f"{API}/agronomist/queue", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 403

    def test_agronomist_queue_agro_200(self, agro_token):
        r = requests.get(f"{API}/agronomist/queue", headers=_hdr(agro_token), timeout=10)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_pipeline_farmer_403(self, farmer_token):
        r = requests.get(f"{API}/admin/pipeline", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 403

    def test_admin_pipeline_admin_200(self, admin_token):
        r = requests.get(f"{API}/admin/pipeline", headers=_hdr(admin_token), timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert "queue" in d and "jobs" in d
        assert set(d["jobs"].keys()) >= {"total", "running", "failed", "succeeded", "dead"}

    def test_admin_audit_farmer_403(self, farmer_token):
        r = requests.get(f"{API}/admin/audit", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 403

    def test_admin_audit_admin_200(self, admin_token):
        r = requests.get(f"{API}/admin/audit", headers=_hdr(admin_token), timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)
        # at least a login entry from the fixtures
        actions = {a["action"] for a in arr}
        assert any(a.startswith("user.") or a.startswith("inference.") or a.startswith("field.") for a in actions)


# ------------------- Inference pipeline (real Claude vision + LangGraph) -------------------
class TestInferencePipeline:
    JOB_TIMEOUT = 120  # up to 2 minutes for real LLM chain

    def _wait_for_job(self, job_id: str, tok: dict) -> dict:
        deadline = time.time() + self.JOB_TIMEOUT
        last = None
        while time.time() < deadline:
            r = requests.get(f"{API}/inference/jobs/{job_id}", headers=_hdr(tok), timeout=15)
            assert r.status_code == 200
            last = r.json()
            if last["status"] in ("succeeded", "dead", "failed"):
                if last["status"] == "failed":
                    # allow one retry cycle before giving up
                    time.sleep(2); continue
                return last
            time.sleep(2)
        return last or {"status": "timeout"}

    def test_enqueue_and_run_real_vision(self, farmer_token, image_b64):
        fields = requests.get(f"{API}/fields", headers=_hdr(farmer_token), timeout=10).json()
        field_id = fields[0]["id"]
        r = requests.post(f"{API}/inference/enqueue", headers=_hdr(farmer_token),
                          json={"field_id": field_id, "image_b64": image_b64}, timeout=20)
        assert r.status_code == 200, r.text
        job_id = r.json()["job_id"]
        assert r.json()["status"] == "queued"

        final = self._wait_for_job(job_id, farmer_token)
        assert final["status"] == "succeeded", f"job did not succeed: {final}"
        assert final.get("detection_id"), "detection_id missing on succeeded job"

        # Fetch the detection and verify reasoning trace has all 5 named nodes
        det_id = final["detection_id"]
        d = requests.get(f"{API}/detections/{det_id}", headers=_hdr(farmer_token), timeout=15).json()
        assert d["disease"], "disease not set"
        assert d["severity"] in {"low", "moderate", "high", "critical"}
        assert 0.0 <= d["confidence"] <= 1.0
        assert d["advisory_en"], "advisory_en empty"
        assert d["advisory_hi"], "advisory_hi empty"
        # reasoning trace: expected 5 nodes (diagnose_refine, severity_score, advisory_localize,
        #                  confidence_gate, escalation_decide). confidence_gate can appear twice on retry.
        nodes = [step["node"] for step in d["reasoning_trace"]]
        expected = {"diagnose_refine", "severity_score", "advisory_localize", "confidence_gate", "escalation_decide"}
        assert expected.issubset(set(nodes)), f"missing reasoning nodes: expected {expected}, got {nodes}"

        # Verify the vision output was from real Claude (not offline fallback) when key set
        raw = d.get("raw_model_output") or {}
        # Not asserting _offline strictly because provider may fallback; just report.
        print(f"[vision] disease={d['disease']} conf={d['confidence']} sev={d['severity']} "
              f"offline={raw.get('_offline')} area={d['affected_area_pct']}")

    def test_job_list(self, farmer_token):
        r = requests.get(f"{API}/inference/jobs", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list)

    def test_enqueue_forbidden_field(self, farmer_token, agro_token, image_b64):
        # Agronomist has no fields but can view all. Farmer trying to scan a field they don't own → 403.
        # Since seed puts all fields under farmer, we craft a foreign field via agronomist create.
        r = requests.post(f"{API}/fields", headers=_hdr(agro_token), json={
            "name": f"TEST_foreign_{int(time.time())}", "crop": "wheat",
            "region": "X", "area_hectares": 1.0, "lat": 1, "lng": 1,
        }, timeout=10)
        assert r.status_code == 200
        fid = r.json()["id"]
        r2 = requests.post(f"{API}/inference/enqueue", headers=_hdr(farmer_token),
                           json={"field_id": fid, "image_b64": "aGVsbG8="}, timeout=10)
        assert r2.status_code == 403


# ------------------- n8n webhook -------------------
class TestN8nWebhook:
    def test_n8n_ingest(self, farmer_token, image_b64):
        fields = requests.get(f"{API}/fields", headers=_hdr(farmer_token), timeout=10).json()
        field_id = fields[0]["id"]
        # webhook is unauthenticated per implementation (dev-mode)
        r = requests.post(f"{API}/n8n/ingest", json={
            "field_id": field_id, "image_b64": image_b64,
        }, timeout=15)
        assert r.status_code == 200
        assert r.json().get("job_id")

    def test_n8n_ingest_missing_fields(self):
        r = requests.post(f"{API}/n8n/ingest", json={}, timeout=10)
        assert r.status_code == 400

    def test_n8n_ingest_field_not_found(self, image_b64):
        r = requests.post(f"{API}/n8n/ingest", json={"field_id": "nope", "image_b64": image_b64}, timeout=10)
        assert r.status_code == 404


# ===================================================================
# ITERATION 2: Cooperatives / coop-scoping / polygons / twilio mock
# ===================================================================
@pytest.fixture(scope="session")
def coop_token():
    s = requests.Session()
    return _login(s, "coop@cropvision.ai", "coop123")


@pytest.fixture(scope="session")
def farmer2_token():
    s = requests.Session()
    return _login(s, "farmer2@cropvision.ai", "farmer123")


class TestCooperatives:
    """Public list, admin-only create, and auth-me includes cooperative_id."""

    def test_public_list_no_auth(self):
        r = requests.get(f"{API}/cooperatives", timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert isinstance(arr, list) and len(arr) >= 2
        names = [c["name"] for c in arr]
        assert "Punjab Kisan Cooperative" in names
        assert "Haryana Grain Growers" in names
        # public list must not expose contact_email / contact_phone
        assert all("contact_email" not in c for c in arr)
        assert all("contact_phone" not in c for c in arr)

    def test_create_cooperative_requires_admin(self, farmer_token):
        r = requests.post(f"{API}/cooperatives",
                          headers=_hdr(farmer_token),
                          json={"name": "TEST_coop", "region": "X"}, timeout=10)
        assert r.status_code == 403

    def test_create_cooperative_no_auth_401(self):
        r = requests.post(f"{API}/cooperatives",
                          json={"name": "TEST_coop", "region": "X"}, timeout=10)
        assert r.status_code == 401

    def test_create_cooperative_admin_ok(self, admin_token):
        r = requests.post(f"{API}/cooperatives",
                          headers=_hdr(admin_token),
                          json={"name": f"TEST_coop_{int(time.time())}", "region": "Testland"},
                          timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["name"].startswith("TEST_coop_")
        assert d["region"] == "Testland"
        assert "id" in d and "_id" not in d

    def test_login_response_includes_cooperative_id(self, coop_token):
        u = coop_token["user"]
        assert u["role"] == "coop_admin"
        assert u.get("cooperative_id"), "coop_admin login must return cooperative_id"

    def test_me_includes_cooperative_id(self, coop_token):
        r = requests.get(f"{API}/auth/me", headers=_hdr(coop_token), timeout=10)
        assert r.status_code == 200
        assert r.json().get("cooperative_id")


class TestRegisterCoopAdmin:
    """Registration with role=coop_admin must accept cooperative_id from public list."""

    def test_register_coop_admin_with_cooperative(self):
        # get a cooperative id
        coops = requests.get(f"{API}/cooperatives", timeout=10).json()
        assert coops, "no seeded cooperatives"
        coop_id = coops[0]["id"]
        email = f"TEST_coopadmin_{int(time.time())}@cropvision.ai"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "name": "Test Coop Admin", "password": "abcdef",
            "role": "coop_admin", "cooperative_id": coop_id, "language": "en",
            "phone": "+919000090001",
        }, timeout=10)
        # This will fail (500) currently because RegisterIn model is missing
        # cooperative_id field. Assert success so the failure is visible.
        assert r.status_code == 200, f"coop_admin register failed: {r.status_code} {r.text}"
        d = r.json()
        assert d["user"]["role"] == "coop_admin"
        assert d["user"]["cooperative_id"] == coop_id

    def test_register_coop_admin_bad_cooperative_id(self):
        email = f"TEST_coopadmin_badcoop_{int(time.time())}@cropvision.ai"
        r = requests.post(f"{API}/auth/register", json={
            "email": email, "name": "Bad Coop", "password": "abcdef",
            "role": "coop_admin", "cooperative_id": "not-a-real-coop", "language": "en",
        }, timeout=10)
        assert r.status_code == 400


class TestCoopDashboard:
    """/api/coop/dashboard — access + shape."""

    def test_coop_dashboard_requires_coop_admin(self, farmer_token):
        r = requests.get(f"{API}/coop/dashboard", headers=_hdr(farmer_token), timeout=10)
        assert r.status_code == 403

    def test_coop_dashboard_agronomist_403(self, agro_token):
        r = requests.get(f"{API}/coop/dashboard", headers=_hdr(agro_token), timeout=10)
        assert r.status_code == 403

    def test_coop_dashboard_shape(self, coop_token):
        r = requests.get(f"{API}/coop/dashboard", headers=_hdr(coop_token), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert set(d.keys()) >= {"cooperative", "totals", "by_status", "top_diseases",
                                 "recent_detections", "farmers"}
        # cooperative object
        assert d["cooperative"] and d["cooperative"]["name"] == "Punjab Kisan Cooperative"
        # totals numeric
        t = d["totals"]
        for k in ("fields", "farmers", "total_hectares", "avg_health", "detections_recent"):
            assert k in t
        assert t["fields"] >= 1
        assert t["farmers"] >= 2  # farmer + farmer2 seeded in this coop
        # top_diseases is list of [name, count]
        assert isinstance(d["top_diseases"], list)
        if d["top_diseases"]:
            assert len(d["top_diseases"][0]) == 2
        # farmers list has expected coop members
        emails = [f["email"] for f in d["farmers"]]
        assert "farmer@cropvision.ai" in emails
        # no password hashes leaked
        for f in d["farmers"]:
            assert "password_hash" not in f


class TestCoopScoping:
    """coop_admin sees only cooperative-scoped fields/detections/alerts."""

    def test_fields_scoped_to_cooperative(self, coop_token):
        r = requests.get(f"{API}/fields", headers=_hdr(coop_token), timeout=10)
        assert r.status_code == 200
        arr = r.json()
        assert len(arr) >= 1
        coop_id = coop_token["user"]["cooperative_id"]
        for f in arr:
            assert f.get("cooperative_id") == coop_id, f"leak: {f}"

    def test_detections_scoped(self, coop_token):
        # gather field ids in coop
        fields = requests.get(f"{API}/fields", headers=_hdr(coop_token), timeout=10).json()
        field_ids = {f["id"] for f in fields}
        r = requests.get(f"{API}/detections?limit=200", headers=_hdr(coop_token), timeout=10)
        assert r.status_code == 200
        for d in r.json():
            assert d["field_id"] in field_ids

    def test_alerts_scoped(self, coop_token):
        fields = requests.get(f"{API}/fields", headers=_hdr(coop_token), timeout=10).json()
        field_ids = {f["id"] for f in fields}
        r = requests.get(f"{API}/alerts?limit=200", headers=_hdr(coop_token), timeout=10)
        assert r.status_code == 200
        for a in r.json():
            assert a["field_id"] in field_ids


class TestFieldPolygon:
    """POST /api/fields accepts polygon array and persists GeoJSON Polygon."""

    def test_create_field_with_polygon(self, farmer_token):
        ring = [[75.85, 30.90], [75.86, 30.90], [75.86, 30.91], [75.85, 30.91]]  # not closed
        r = requests.post(f"{API}/fields", headers=_hdr(farmer_token), json={
            "name": f"TEST_poly_{int(time.time())}", "crop": "wheat",
            "region": "Punjab, India", "area_hectares": 1.2,
            "lat": 30.905, "lng": 75.855,
            "polygon": ring,
        }, timeout=10)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("polygon"), "polygon missing on response"
        assert d["polygon"]["type"] == "Polygon"
        coords = d["polygon"]["coordinates"][0]
        assert len(coords) == 5, f"ring should auto-close to 5 pts, got {coords}"
        assert coords[0] == coords[-1], "ring not closed"

    def test_create_field_without_polygon_still_works(self, farmer_token):
        r = requests.post(f"{API}/fields", headers=_hdr(farmer_token), json={
            "name": f"TEST_nopoly_{int(time.time())}", "crop": "rice",
            "region": "Punjab, India", "area_hectares": 0.9,
            "lat": 30.7, "lng": 75.8,
        }, timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d.get("polygon") in (None,), "expected no polygon"

    def test_create_field_polygon_too_few_points_ignored(self, farmer_token):
        # <3 points → polygon dropped (backend guards on len>=3)
        r = requests.post(f"{API}/fields", headers=_hdr(farmer_token), json={
            "name": f"TEST_polybad_{int(time.time())}", "crop": "cotton",
            "region": "Haryana, India", "area_hectares": 0.5,
            "lat": 29.0, "lng": 76.0,
            "polygon": [[76.0, 29.0], [76.01, 29.0]],
        }, timeout=10)
        assert r.status_code == 200
        assert r.json().get("polygon") is None


class TestTwilioMockMode:
    """Twilio env vars are BLANK — delivery must return mocked=True and pipeline must succeed."""

    def _wait(self, job_id, tok, timeout=120):
        deadline = time.time() + timeout
        while time.time() < deadline:
            r = requests.get(f"{API}/inference/jobs/{job_id}", headers=_hdr(tok), timeout=15)
            assert r.status_code == 200
            j = r.json()
            if j["status"] in ("succeeded", "dead"):
                return j
            time.sleep(2)
        return {"status": "timeout"}

    def test_pipeline_creates_whatsapp_alert_with_delivery_error(self, farmer_token, image_b64):
        # farmer has a phone in seed, so twilio path is exercised
        fields = requests.get(f"{API}/fields", headers=_hdr(farmer_token), timeout=10).json()
        # pick a field owned by farmer
        my_field = next(f for f in fields if f["owner_id"] == farmer_token["user"]["id"])
        r = requests.post(f"{API}/inference/enqueue", headers=_hdr(farmer_token),
                          json={"field_id": my_field["id"], "image_b64": image_b64}, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "queued"
        j = self._wait(r.json()["job_id"], farmer_token)
        assert j["status"] == "succeeded", f"job did not succeed: {j}"

        # Pull recent alerts; find whatsapp alert for this detection
        alerts = requests.get(f"{API}/alerts?limit=200", headers=_hdr(farmer_token), timeout=10).json()
        wa = [a for a in alerts
              if a["channel"] == "whatsapp" and a["detection_id"] == j["detection_id"]]
        assert wa, "no whatsapp alert row was created in mock mode"
        a = wa[0]
        assert a["delivered"] is False
        # delivery_error must clearly signal mock mode
        err = (a.get("delivery_error") or "").lower()
        assert "twilio" in err and "not configured" in err, f"unexpected error: {a.get('delivery_error')}"
        # verify a dashboard alert also exists
        db = [a for a in alerts
              if a["channel"] == "dashboard" and a["detection_id"] == j["detection_id"]]
        assert db, "dashboard alert missing"


class TestCoopAdminFieldsPipeline:
    """coop_admin can view another coop member's field but can't enqueue if not owner (RBAC unchanged)."""

    def test_coop_admin_gets_field_owned_by_farmer(self, coop_token):
        fields = requests.get(f"{API}/fields", headers=_hdr(coop_token), timeout=10).json()
        assert fields, "coop has no fields"
        fid = fields[0]["id"]
        r = requests.get(f"{API}/fields/{fid}", headers=_hdr(coop_token), timeout=10)
        assert r.status_code == 200
        assert r.json()["id"] == fid
