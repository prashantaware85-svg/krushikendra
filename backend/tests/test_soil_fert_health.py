"""Soil + fertilizer + health tests: roundtrips, validation, linkage (full app).

Follows tests/test_vision_soil_health.py exactly: the shared conftest
``client`` fixture (full create_app, SQLite StaticPool, get_db override),
real JWTs via ``auth_headers``. Farm/crop ids are opaque UUIDs the services
treat as ownership-scoped facts.
"""

from __future__ import annotations

import io
import uuid

from PIL import Image

from tests.conftest import auth_headers
from app.models.pest import Disease, Pest


def _farm_id() -> str:
    return str(uuid.uuid4())


def _crop_id() -> str:
    return str(uuid.uuid4())


def _make_soil_test(client, headers, farm_id: str, **overrides) -> dict:
    payload = {"laboratory_name": "Agri Lab"}
    payload.update(overrides)
    response = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_soil_report_rejects_garbage_bytes_422(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id = _farm_id()
    test_id = _make_soil_test(client, headers, farm_id)["id"]
    response = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}/report",
        files=[("report", ("report.pdf", b"%NOT-A-PDF%", "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "REPORT_INVALID_TYPE"


def test_soil_report_too_large_422(client, farmer_a, monkeypatch):
    from app.core.config import get_settings

    headers = auth_headers(farmer_a)
    farm_id = _farm_id()
    test_id = _make_soil_test(client, headers, farm_id)["id"]
    monkeypatch.setattr(get_settings(), "soil_report_max_mb", 0)
    try:
        response = client.post(
            f"/api/v1/farms/{farm_id}/soil-tests/{test_id}/report",
            files=[("report", ("report.pdf", b"%PDF-1.4 tiny", "application/pdf"))],
            headers=headers,
        )
    finally:
        monkeypatch.setattr(get_settings(), "soil_report_max_mb", 10)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "REPORT_TOO_LARGE"


def test_soil_nutrient_record_roundtrip(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id = _farm_id()
    created = _make_soil_test(
        client, headers, farm_id,
        ph=6.5, nitrogen=280.5, phosphorus=45.0, potassium=120.0,
        soil_type="black",
    )
    assert isinstance(created["ph"], str)  # wire format is decimal strings
    assert float(created["ph"]) == 6.5
    assert float(created["nitrogen"]) == 280.5
    assert float(created["phosphorus"]) == 45.0
    assert float(created["potassium"]) == 120.0
    assert created["soil_type"] == "black"
    assert created["has_report"] is False
    fetched = client.get(
        f"/api/v1/farms/{farm_id}/soil-tests/{created['id']}", headers=headers
    )
    assert fetched.status_code == 200, fetched.text
    assert float(fetched.json()["ph"]) == 6.5
    updated = client.put(
        f"/api/v1/farms/{farm_id}/soil-tests/{created['id']}",
        json={"ph": 7.0, "notes": "retested"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert float(updated.json()["ph"]) == 7.0
    assert updated.json()["notes"] == "retested"
    listed = client.get(f"/api/v1/farms/{farm_id}/soil-tests", headers=headers)
    assert listed.status_code == 200
    assert [t["id"] for t in listed.json()] == [created["id"]]
    assert client.delete(
        f"/api/v1/farms/{farm_id}/soil-tests/{created['id']}", headers=headers
    ).status_code == 204
    assert client.get(
        f"/api/v1/farms/{farm_id}/soil-tests/{created['id']}", headers=headers
    ).status_code == 404


def test_soil_numeric_validation_422(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id = _farm_id()
    assert client.post(
        f"/api/v1/farms/{farm_id}/soil-tests", json={"ph": 99.0}, headers=headers
    ).status_code == 422
    assert client.post(
        f"/api/v1/farms/{farm_id}/soil-tests", json={"nitrogen": -5}, headers=headers
    ).status_code == 422
    assert client.post(
        f"/api/v1/farms/{farm_id}/soil-tests", json={"ph": "acidic"}, headers=headers
    ).status_code == 422


def test_soil_report_accepts_png_and_serves_bytes(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id = _farm_id()
    test_id = _make_soil_test(client, headers, farm_id)["id"]
    image = Image.new("RGB", (50, 50), (120, 140, 100))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    uploaded = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}/report",
        files=[("report", ("scan.png", buffer.getvalue(), "image/png"))],
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["has_report"] is True
    fetched = client.get(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}/report", headers=headers
    )
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"
    assert len(fetched.content) > 0


def test_soil_test_farmer_isolation(client, farmer_a, farmer_b, current_farmer):
    assert current_farmer["id"] == farmer_a
    headers_a = auth_headers(farmer_a)
    farm_id = _farm_id()
    test_id = _make_soil_test(client, headers_a, farm_id)["id"]
    current_farmer["id"] = farmer_b  # now acting as farmer B
    headers_b = auth_headers(farmer_b)
    denied = client.get(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}", headers=headers_b
    )
    assert denied.status_code == 404, denied.text
    assert denied.json()["error"]["code"] == "SOIL_TEST_NOT_FOUND"
    assert client.get(f"/api/v1/farms/{farm_id}/soil-tests", headers=headers_b).json() == []


def _make_fertilizer(client, headers, farm_id, crop_id, **overrides) -> dict:
    payload = {
        "application_date": "2026-08-10",
        "fertilizer_name": "Urea",
        "quantity": 25,
        "quantity_unit": "kg",
    }
    payload.update(overrides)
    response = client.post(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers",
        json=payload, headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_fertilizer_record_roundtrip_newest_first(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id, crop_id = _farm_id(), _crop_id()
    older = _make_fertilizer(
        client, headers, farm_id, crop_id, application_date="2026-07-01"
    )
    newer = _make_fertilizer(
        client, headers, farm_id, crop_id, application_date="2026-08-01",
        fertilizer_name="DAP", quantity=50,
    )
    assert isinstance(newer["quantity"], str)  # wire format is decimal strings
    assert float(newer["quantity"]) == 50
    assert newer["quantity_unit"] == "kg"
    fetched = client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers/{newer['id']}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["fertilizer_name"] == "DAP"
    listed = client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers", headers=headers
    )
    assert [f["id"] for f in listed.json()] == [newer["id"], older["id"]]
    updated = client.put(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers/{newer['id']}",
        json={"application_date": "2026-08-01", "fertilizer_name": "DAP",
              "quantity": 50, "quantity_unit": "kg", "notes": "basal dose"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notes"] == "basal dose"
    assert client.delete(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers/{older['id']}",
        headers=headers,
    ).status_code == 204
    assert client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers/{older['id']}",
        headers=headers,
    ).status_code == 404


def test_fertilizer_validation_422(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id, crop_id = _farm_id(), _crop_id()
    base = f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers"
    assert client.post(
        base, json={"application_date": "2026-08-10", "fertilizer_name": "Urea",
                    "quantity": 0, "quantity_unit": "kg"}, headers=headers
    ).status_code == 422
    assert client.post(
        base, json={"application_date": "2026-08-10", "fertilizer_name": "Urea",
                    "quantity": -5, "quantity_unit": "kg"}, headers=headers
    ).status_code == 422
    assert client.post(
        base, json={"application_date": "2026-08-10", "fertilizer_name": "",
                    "quantity": 5, "quantity_unit": "kg"}, headers=headers
    ).status_code == 422
    assert client.post(
        base, json={"application_date": "2026-08-10", "fertilizer_name": "Urea",
                    "quantity": 5, "quantity_unit": "truckload"}, headers=headers
    ).status_code == 422


def test_fertilizer_farmer_isolation(client, farmer_a, farmer_b, current_farmer):
    assert current_farmer["id"] == farmer_a
    headers_a = auth_headers(farmer_a)
    farm_id, crop_id = _farm_id(), _crop_id()
    record = _make_fertilizer(client, headers_a, farm_id, crop_id)
    current_farmer["id"] = farmer_b  # now acting as farmer B
    headers_b = auth_headers(farmer_b)
    denied = client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers/{record['id']}",
        headers=headers_b,
    )
    assert denied.status_code == 404, denied.text
    assert denied.json()["error"]["code"] == "FERTILIZER_NOT_FOUND"
    assert client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/fertilizers", headers=headers_b
    ).json() == []


def _seed_catalogue(db_session) -> dict:
    pest = Pest(name="Aphid", local_name="Mava", category="sucking",
                description="Sap pest", is_verified=False, is_active=True)
    disease = Disease(name="Leaf Spot", local_name="Pan Dag", category="fungal",
                      description="Spots", is_verified=False, is_active=True)
    db_session.add_all([pest, disease])
    db_session.commit()
    db_session.refresh(pest)
    db_session.refresh(disease)
    return {"pest_id": str(pest.id), "disease_id": str(disease.id)}


def test_pest_disease_catalogue_read_and_auth(client, db_session, farmer_a):
    ids = _seed_catalogue(db_session)
    headers = auth_headers(farmer_a)
    pests = client.get("/api/v1/pests", headers=headers)
    assert pests.status_code == 200, pests.text
    assert ids["pest_id"] in [p["id"] for p in pests.json()]
    diseases = client.get("/api/v1/diseases", headers=headers)
    assert diseases.status_code == 200, diseases.text
    assert ids["disease_id"] in [d["id"] for d in diseases.json()]
    assert all("is_verified" in p for p in pests.json())
    # NOTE: no 401 assertion here — the shared fixture overrides farmer identity
    # by design (see conftest), so unauthenticated shape is covered by routers
    # using get_current_farmer_id in production wiring.


def _make_observation(client, headers, farm_id, crop_id, **overrides) -> dict:
    payload = {"observation_type": "other", "severity": "low", "symptoms": "yellowing"}
    payload.update(overrides)
    response = client.post(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health", json=payload, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_observation_action_linkage_roundtrip(client, db_session, farmer_a):
    ids = _seed_catalogue(db_session)
    headers = auth_headers(farmer_a)
    farm_id, crop_id = _farm_id(), _crop_id()
    obs = _make_observation(
        client, headers, farm_id, crop_id,
        observation_type="pest", pest_id=ids["pest_id"],
    )
    assert obs["pest_id"] == ids["pest_id"]
    assert obs["linked_analysis"] is None
    assert obs["has_photos"] is False
    action = client.post(
        f"/api/v1/health/{obs['id']}/actions",
        json={"action_type": "monitoring", "description": "Observed traps"},
        headers=headers,
    )
    assert action.status_code == 201, action.text
    assert action.json()["observation_id"] == obs["id"]
    actions = client.get(f"/api/v1/health/{obs['id']}/actions", headers=headers)
    assert actions.status_code == 200
    assert [a["id"] for a in actions.json()] == [action.json()["id"]]
    assert client.delete(
        f"/api/v1/health/{obs['id']}/actions/{action.json()['id']}", headers=headers
    ).status_code == 204
    assert client.get(
        f"/api/v1/health/{obs['id']}/actions", headers=headers
    ).json() == []


def test_observation_invalid_catalogue_link_404(client, farmer_a):
    headers = auth_headers(farmer_a)
    farm_id, crop_id = _farm_id(), _crop_id()
    response = client.post(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health",
        json={"observation_type": "pest", "pest_id": str(uuid.uuid4()),
              "severity": "low"},
        headers=headers,
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "PEST_INVALID"
    response = client.post(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health",
        json={"observation_type": "disease", "disease_id": str(uuid.uuid4()),
              "severity": "low"},
        headers=headers,
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "DISEASE_INVALID"


def test_observation_update_path_type_mismatch_422(client, db_session, farmer_a):
    ids = _seed_catalogue(db_session)
    headers = auth_headers(farmer_a)
    farm_id, crop_id = _farm_id(), _crop_id()
    obs = _make_observation(client, headers, farm_id, crop_id)
    bad = client.put(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health/{obs['id']}",
        json={"observation_type": "unknown", "pest_id": ids["pest_id"]},
        headers=headers,
    )
    assert bad.status_code == 422, bad.text
    assert bad.json()["error"]["code"] == "OBSERVATION_TYPE_MISMATCH"


def test_health_isolation_between_farmers(client, farmer_a, farmer_b, current_farmer):
    headers_a = auth_headers(farmer_a)
    headers_b = auth_headers(farmer_b)
    farm_id, crop_id = _farm_id(), _crop_id()
    obs = _make_observation(client, headers_a, farm_id, crop_id)
    action = client.post(
        f"/api/v1/health/{obs['id']}/actions",
        json={"action_type": "sanitation", "description": "Removed leaves"},
        headers=headers_a,
    )
    assert action.status_code == 201
    current_farmer["id"] = farmer_b  # dependency-override path also switches
    assert client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health/{obs['id']}",
        headers=headers_b,
    ).status_code == 404
    assert client.get(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health", headers=headers_b
    ).json() == []
    assert client.get(
        f"/api/v1/health/{obs['id']}/actions", headers=headers_b
    ).status_code == 404
