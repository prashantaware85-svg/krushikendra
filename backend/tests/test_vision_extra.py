"""Vision extra tests: limits, quality gates, isolation, wording (full app).

Follows tests/test_vision_soil_health.py exactly: the shared conftest
``client`` fixture (full create_app, SQLite StaticPool), real JWTs via
``auth_headers``, real PNG bytes via Pillow.
"""

from __future__ import annotations

import io
import os
import uuid

from PIL import Image

from tests.conftest import auth_headers


def _textured_png(seed: int = 42, size: int = 300) -> bytes:
    """Textured daylight-like photo (passes the blur/darkness quality gates)."""
    import random

    random.seed(seed)
    image = Image.new("RGB", (size, size))
    image.putdata([
        (random.randint(90, 180), random.randint(100, 190), random.randint(60, 140))
        for _ in range(size * size)
    ])
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _flat_png(color: tuple[int, int, int] = (5, 5, 5), size: int = 300) -> bytes:
    image = Image.new("RGB", (size, size), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _upload(client, headers, files, farm_id=None, crop_id=None, language="mr"):
    data = {"farm_id": farm_id or str(uuid.uuid4()), "language": language}
    if crop_id is not None:
        data["crop_id"] = crop_id
    return client.post(
        "/api/v1/crop-images", data=data, files=files, headers=headers
    )


def test_vision_rejects_garbage_bytes_422(client, farmer_a):
    headers = auth_headers(farmer_a)
    response = _upload(
        client, headers,
        files=[("images", ("leaf.jpg", b"not-an-image-at-all", "image/jpeg"))],
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "IMAGE_INVALID_TYPE"


def test_vision_rejects_oversize_bytes_422(client, farmer_a):
    from app.core.config import get_settings

    headers = auth_headers(farmer_a)
    big = os.urandom((get_settings().vision_max_file_mb + 1) * 1024 * 1024)
    response = _upload(
        client, headers, files=[("images", ("big.jpg", big, "image/jpeg"))]
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "IMAGE_TOO_LARGE"


def test_vision_rejects_too_small_dimensions_422(client, farmer_a):
    headers = auth_headers(farmer_a)
    tiny = _flat_png(color=(120, 140, 100), size=10)
    response = _upload(
        client, headers, files=[("images", ("tiny.png", tiny, "image/png"))]
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "IMAGE_QUALITY_INSUFFICIENT"


def test_vision_rejects_dark_photo_quality_gate(client, farmer_a):
    headers = auth_headers(farmer_a)
    dark = _flat_png(color=(5, 5, 5))
    response = _upload(
        client, headers, files=[("images", ("dark.png", dark, "image/png"))]
    )
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "IMAGE_QUALITY_INSUFFICIENT"
    assert "daylight" in response.json()["error"]["message"].lower()


def test_vision_rejects_more_than_max_images(client, farmer_a):
    headers = auth_headers(farmer_a)
    payload = _textured_png()
    files = [
        ("images", (f"leaf{i}.png", payload, "image/png")) for i in range(4)
    ]
    response = _upload(client, headers, files=files)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "IMAGE_TOO_MANY"


def test_vision_farmer_isolation_uniform_404(client, farmer_a, farmer_b, current_farmer):
    """Identity comes from the ``current_farmer`` override (headers are bypassed
    by design in this fixture — see conftest)."""
    assert current_farmer["id"] == farmer_a
    created = _upload(
        client, auth_headers(farmer_a),
        files=[("images", ("leaf.png", _textured_png(), "image/png"))],
    )
    assert created.status_code == 201, created.text
    analysis_id = created.json()["id"]
    current_farmer["id"] = farmer_b  # now acting as farmer B
    denied = client.get(f"/api/v1/crop-images/{analysis_id}", headers=auth_headers(farmer_b))
    assert denied.status_code == 404, denied.text
    assert denied.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
    assert client.get("/api/v1/crop-images", headers=auth_headers(farmer_b)).json() == []
    current_farmer["id"] = farmer_a
    assert client.get(f"/api/v1/crop-images/{analysis_id}", headers=auth_headers(farmer_a)).status_code == 200
    current_farmer["id"] = farmer_b
    assert client.delete(
        f"/api/v1/crop-images/{analysis_id}", headers=auth_headers(farmer_b)
    ).status_code == 404


def test_vision_uncertain_wording_and_disclaimer(client, farmer_a):
    headers = auth_headers(farmer_a)
    response = _upload(
        client, headers,
        files=[("images", ("leaf.png", _textured_png(seed=7), "image/png"))],
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "completed"
    assert body["is_mock"] is True
    assert body["possible_condition"] and "uncertain" in body["possible_condition"].lower()
    assert body["observations"] and all(
        "(uncertain)" in obs for obs in body["observations"]
    )
    assert body["disclaimer"], "every response carries the disclaimer"
    haystack = " ".join(
        [body["possible_condition"] or "", *body["observations"],
         *[s.get("title", "") for s in body.get("sources", [])]]
    ).lower()
    for forbidden in ("dosage", "prescription", "diagnosis is confirmed"):
        assert forbidden not in haystack
    assert body["response_language"] == "mr"


def test_vision_reanalyze_delete_lifecycle(client, farmer_a):
    headers = auth_headers(farmer_a)
    created = _upload(
        client, headers,
        files=[("images", ("leaf.png", _textured_png(seed=9), "image/png"))],
    )
    assert created.status_code == 201, created.text
    analysis_id = created.json()["id"]
    reanalyzed = client.post(
        f"/api/v1/crop-images/{analysis_id}/analyze", headers=headers
    )
    assert reanalyzed.status_code == 200, reanalyzed.text
    assert reanalyzed.json()["status"] == "completed"
    image = client.get(f"/api/v1/crop-images/{analysis_id}/image", headers=headers)
    assert image.status_code == 200, image.text
    assert image.headers["content-type"].startswith("image/")
    assert len(image.content) > 0
    assert client.delete(
        f"/api/v1/crop-images/{analysis_id}", headers=headers
    ).status_code == 204
    assert client.get(
        f"/api/v1/crop-images/{analysis_id}", headers=headers
    ).status_code == 404
    assert all(
        item["id"] != analysis_id
        for item in client.get("/api/v1/crop-images", headers=headers).json()
    )


def test_vision_unknown_analysis_404(client, farmer_a):
    """Unknown UUID → 404 envelope; malformed id → 422 (never 500)."""
    headers = auth_headers(farmer_a)
    missing = client.get(f"/api/v1/crop-images/{uuid.uuid4()}", headers=headers)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ANALYSIS_NOT_FOUND"
    malformed = client.get("/api/v1/crop-images/not-a-uuid", headers=headers)
    assert malformed.status_code == 422
