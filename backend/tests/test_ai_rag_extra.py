"""AI RAG extra tests: trust gating, unrelated fallback, isolation (full app).

Follows tests/test_ai_rag.py exactly: the shared conftest ``client`` fixture
(full create_app, SQLite StaticPool, get_db override), real JWTs via
``auth_headers``, ingestion helpers for verified/unverified knowledge.
"""

from __future__ import annotations

from tests.conftest import auth_headers
from app.modules.ai import ingestion


def _make_conversation(client, headers, language: str = "mr") -> str:
    response = client.post(
        "/api/v1/ai/conversations", json={"language": language}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _ask(client, headers, conversation_id: str, message: str) -> dict:
    response = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"message": message},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_unverified_document_is_never_cited(client, db_session, farmer_a):
    headers = auth_headers(farmer_a)
    document = ingestion.register_document(
        db_session, title="Wheat Sowing Guide", language="mr",
        source_name="State Agri University",
    )
    ingestion.ingest_text(
        db_session, document.id, "Wheat sowing guide. Sow wheat in November rows."
    )
    # Deliberately NOT verified → invisible to retrieval.
    body = _ask(
        client, headers,
        _make_conversation(client, headers), "When to sow wheat?",
    )
    assert body["sources"] == []
    assert "विश्वसनीय" in body["message"]["content"]


def test_revoked_document_stops_being_cited(client, db_session, farmer_a):
    headers = auth_headers(farmer_a)
    document = ingestion.register_document(
        db_session, title="Cotton Guide", language="mr", source_name="Agri Dept",
    )
    ingestion.ingest_text(
        db_session, document.id, "Cotton sowing guide. Sow cotton in June rows."
    )
    ingestion.verify_document(db_session, document.id, True)
    cited = _ask(
        client, headers,
        _make_conversation(client, headers), "When to sow cotton?",
    )
    assert cited["sources"], "verified chunk must be cited"
    ingestion.verify_document(db_session, document.id, False)
    fallback = _ask(
        client, headers,
        _make_conversation(client, headers), "When to sow cotton?",
    )
    assert fallback["sources"] == []


def test_unrelated_question_safe_fallback_despite_verified_kb(
    client, db_session, farmer_a
):
    headers = auth_headers(farmer_a)
    document = ingestion.register_document(
        db_session, title="Wheat Sowing Guide", language="mr",
        source_name="State Agri University",
    )
    ingestion.ingest_text(
        db_session, document.id, "Wheat sowing guide. Sow wheat in November rows."
    )
    ingestion.verify_document(db_session, document.id, True)
    body = _ask(
        client, headers,
        _make_conversation(client, headers),
        "Explain quantum computing qubits entanglement",
    )
    assert body["sources"] == []
    assert "Wheat" not in body["message"]["content"]  # no fabrication
    assert "विश्वसनीय" in body["message"]["content"]


def test_verified_citation_names_document(client, db_session, farmer_a):
    headers = auth_headers(farmer_a)
    document = ingestion.register_document(
        db_session, title="Jowar Sowing Notes", language="mr", source_name="KVK",
    )
    ingestion.ingest_text(
        db_session, document.id, "Jowar sowing notes. Sow jowar in June furrows."
    )
    ingestion.verify_document(db_session, document.id, True)
    body = _ask(
        client, headers,
        _make_conversation(client, headers), "When to sow jowar?",
    )
    assert body["sources"]
    assert body["sources"][0]["document_id"] == str(document.id)
    assert "Jowar Sowing Notes" in body["message"]["content"]
    assert "[MOCK" in body["message"]["content"]


def test_conversation_isolation_between_farmers(client, farmer_a, farmer_b, current_farmer):
    """Identity comes from the ``current_farmer`` override (headers are bypassed
    by design in this fixture — see conftest)."""
    _ = auth_headers(farmer_a)
    _ = auth_headers(farmer_b)
    assert current_farmer["id"] == farmer_a
    conversation_id = _make_conversation(client, auth_headers(farmer_a))
    current_farmer["id"] = farmer_b  # now acting as farmer B
    denied = client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=auth_headers(farmer_b)
    )
    assert denied.status_code == 404, denied.text
    assert denied.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
    denied_post = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"message": "Hello?"},
        headers=auth_headers(farmer_b),
    )
    assert denied_post.status_code == 404
    ids_b = [c["id"] for c in client.get(
        "/api/v1/ai/conversations", headers=auth_headers(farmer_b)).json()]
    assert conversation_id not in ids_b
    current_farmer["id"] = farmer_a
    ids_a = [c["id"] for c in client.get(
        "/api/v1/ai/conversations", headers=auth_headers(farmer_a)).json()]
    assert conversation_id in ids_a


def test_delete_conversation_then_detail_404(client, farmer_a):
    headers = auth_headers(farmer_a)
    conversation_id = _make_conversation(client, headers)
    deleted = client.delete(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    )
    assert deleted.status_code == 204, deleted.text
    assert client.get(
        f"/api/v1/ai/conversations/{conversation_id}", headers=headers
    ).status_code == 404


def test_empty_and_too_long_messages_rejected(client, farmer_a):
    headers = auth_headers(farmer_a)
    conversation_id = _make_conversation(client, headers)
    empty = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"message": "   "},
        headers=headers,
    )
    assert empty.status_code == 422
    long_text = "wheat " * 600  # > ai_max_message_length (2000)
    too_long = client.post(
        f"/api/v1/ai/conversations/{conversation_id}/messages",
        json={"message": long_text},
        headers=headers,
    )
    assert too_long.status_code == 422
    assert too_long.json()["error"]["code"] == "AI_MESSAGE_TOO_LONG"


def test_unknown_and_malformed_conversation_ids(client, farmer_a):
    """Unknown UUID → 404 envelope; malformed id → 422 (never 500)."""
    import uuid

    headers = auth_headers(farmer_a)
    missing = client.get(
        f"/api/v1/ai/conversations/{uuid.uuid4()}", headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "CONVERSATION_NOT_FOUND"
    malformed = client.get("/api/v1/ai/conversations/not-a-uuid", headers=headers)
    assert malformed.status_code == 422
    assert client.delete(
        f"/api/v1/ai/conversations/{uuid.uuid4()}", headers=headers
    ).status_code == 404
