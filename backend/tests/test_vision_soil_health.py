"""Vision / soil / health tests: validation, uncertainty, farmer scoping."""

from __future__ import annotations

import io
import uuid

from PIL import Image

from tests.conftest import auth_headers


def _png_bytes() -> bytes:
    """Textured daylight-like photo (passes the blur/darkness quality gates)."""
    import random

    random.seed(42)
    image = Image.new("RGB", (300, 300))
    image.putdata([
        (random.randint(90, 180), random.randint(100, 190), random.randint(60, 140))
        for _ in range(300 * 300)
    ])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_vision_rejects_non_image_bytes(client, farmer_a):
    """Magic-byte validation (not extension): garbage → 422."""
    headers = auth_headers(farmer_a)
    farm_id, crop_id = str(uuid.uuid4()), str(uuid.uuid4())
    response = client.post(
        "/api/v1/crop-images",
        data={"farm_id": farm_id, "crop_id": crop_id, "language": "mr"},
        files=[("images", ("leaf.jpg", b"not-an-image-at-all", "image/jpeg"))],
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "IMAGE_INVALID_TYPE"


def test_vision_uncertain_language_only(client, farmer_a):
    """Mock returns UNCERTAIN observations + disclaimer — never a diagnosis."""
    headers = auth_headers(farmer_a)
    farm_id, crop_id = str(uuid.uuid4()), str(uuid.uuid4())
    response = client.post(
        "/api/v1/crop-images",
        data={"farm_id": farm_id, "crop_id": crop_id, "language": "mr"},
        files=[("images", ("leaf.png", _png_bytes(), "image/png"))],
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["is_mock"] is True
    haystack = " ".join(
        [(body["possible_condition"] or ""), *body["observations"]]
    ).lower()
    assert "uncertain" in haystack
    assert all("(uncertain)" in obs for obs in body["observations"])
    assert body["disclaimer"], "every response carries the disclaimer"
    assert "dosage" not in haystack and "prescription" not in haystack


def test_soil_report_rejects_non_pdf_image_bytes(client, farmer_a):
    """Report sniffing: garbage bytes → 422 (filename never trusted)."""
    headers = auth_headers(farmer_a)
    farm_id = str(uuid.uuid4())
    created = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests",
        json={"laboratory_name": "Lab", "ph": 6.5},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    test_id = created.json()["id"]
    response = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}/report",
        files=[("report", ("report.pdf", b"%NOT-A-PDF%", "application/pdf"))],
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "REPORT_INVALID_TYPE"


def test_soil_report_accepts_pdf_magic(client, farmer_a):
    """Minimal %PDF- magic passes validation and serves back bytes."""
    headers = auth_headers(farmer_a)
    farm_id = str(uuid.uuid4())
    test_id = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests",
        json={"laboratory_name": "Lab"},
        headers=headers,
    ).json()["id"]
    payload = b"%PDF-1.4 fake report bytes"
    uploaded = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}/report",
        files=[("report", ("report.pdf", payload, "application/pdf"))],
        headers=headers,
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["has_report"] is True


def test_farmer_scoping_uniform_404(client, farmer_a, farmer_b, current_farmer):
    """Farmer B cannot read farmer A's soil test (uniform 404, no oracle)."""
    farm_id = str(uuid.uuid4())
    created = client.post(
        f"/api/v1/farms/{farm_id}/soil-tests",
        json={"laboratory_name": "A-Lab"},
        headers=auth_headers(farmer_a),
    )
    assert created.status_code == 201
    test_id = created.json()["id"]

    current_farmer["id"] = farmer_b  # dependency override path also switches
    response = client.get(
        f"/api/v1/farms/{farm_id}/soil-tests/{test_id}",
        headers=auth_headers(farmer_b),
    )
    assert response.status_code == 404, response.text
    assert response.json()["error"]["code"] == "SOIL_TEST_NOT_FOUND"


def test_health_unknown_type_rejects_catalogue_links(client, farmer_a):
    """`unknown` observations carry NO catalogue links (422, create path)."""
    headers = auth_headers(farmer_a)
    farm_id, crop_id = str(uuid.uuid4()), str(uuid.uuid4())
    response = client.post(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health",
        json={
            "observation_type": "unknown",
            "pest_id": str(uuid.uuid4()),
            "severity": "low",
        },
        headers=headers,
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "OBSERVATION_TYPE_MISMATCH"

    # Same payload without links records fine (tracking only, no diagnosis).
    created = client.post(
        f"/api/v1/farms/{farm_id}/crops/{crop_id}/health",
        json={"observation_type": "unknown", "severity": "low", "symptoms": "yellowing"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["observation_type"] == "unknown"
