"""0015: backfill Step 3–11 domain tables (farms/crops/activities/weather/market/AI+RAG/vision/soil/pest).

0003–0011 are empty `pass` chain slots; this migration creates ALL tables owned
by those slots in dependency order so a fresh DB matches app.db.base metadata.
Plain create_table (fresh-DB path, mirrors 0002/0012–0014 style).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.db.vector import EmbeddingVector

revision = "0015_backfill_step3_11_domains"
down_revision = "0014_create_payments_khata"
branch_labels = None
depends_on = None

_TS = dict(type_=sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    # --- 0003 slot: farms + soil_records ---
    op.create_table(
        "farms",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_user_id", sa.String(64), nullable=False),
        sa.Column("farm_name", sa.String(128), nullable=False),
        sa.Column("village", sa.String(64), nullable=True),
        sa.Column("taluka", sa.String(64), nullable=True),
        sa.Column("district", sa.String(64), nullable=True),
        sa.Column("state", sa.String(64), nullable=True),
        sa.Column("area_acres", sa.Float(), nullable=True),
        sa.Column("area_unit", sa.String(16), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("land_type", sa.String(32), nullable=True),
        sa.Column("soil_type", sa.String(32), nullable=True),
        sa.Column("irrigation_type", sa.String(32), nullable=True),
        sa.Column("water_source", sa.String(32), nullable=True),
        sa.Column("ownership_type", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(op.f("ix_farms_owner_user_id"), "farms", ["owner_user_id"])

    op.create_table(
        "soil_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("soil_type", sa.String(64), nullable=True),
        sa.Column("soil_test_available", sa.Boolean(), nullable=False),
        sa.Column("soil_test_date", sa.Date(), nullable=True),
        sa.Column("ph", sa.Float(), nullable=True),
        sa.Column("organic_carbon", sa.Float(), nullable=True),
        sa.Column("nitrogen", sa.Float(), nullable=True),
        sa.Column("phosphorus", sa.Float(), nullable=True),
        sa.Column("potassium", sa.Float(), nullable=True),
        sa.Column("soil_test_document_reference", sa.String(256), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            name=op.f("fk_soil_records_farm_id_farms"),
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("farm_id", name=op.f("uq_soil_records_farm_id")),
    )

    # --- 0004 slot: crop_varieties + farm_crops ---
    op.create_table(
        "crop_varieties",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("crop_name", sa.String(64), nullable=False),
        sa.Column("variety_name", sa.String(64), nullable=True),
        sa.Column("crop_category", sa.String(32), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("season", sa.String(16), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(op.f("ix_crop_varieties_crop_name"), "crop_varieties", ["crop_name"])

    op.create_table(
        "farm_crops",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("crop_variety_id", sa.Uuid(), nullable=True),
        sa.Column("crop_name", sa.String(64), nullable=False),
        sa.Column("variety_name", sa.String(64), nullable=True),
        sa.Column("sowing_date", sa.Date(), nullable=True),
        sa.Column("expected_harvest_date", sa.Date(), nullable=True),
        sa.Column("area_acres", sa.Float(), nullable=True),
        sa.Column("area_unit", sa.String(16), nullable=False),
        sa.Column("season", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_id"],
            ["farms.id"],
            name=op.f("fk_farm_crops_farm_id_farms"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["crop_variety_id"],
            ["crop_varieties.id"],
            name=op.f("fk_farm_crops_crop_variety_id_crop_varieties"),
            ondelete="SET NULL",
        ),
    )
    op.create_index(op.f("ix_farm_crops_farm_id"), "farm_crops", ["farm_id"])
    op.create_index(op.f("ix_farm_crops_crop_variety_id"), "farm_crops", ["crop_variety_id"])
    op.create_index(op.f("ix_farm_crops_status"), "farm_crops", ["status"])

    # --- 0005 slot: farm_activities ---
    op.create_table(
        "farm_activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farm_crop_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=True),
        sa.Column("quantity_unit", sa.String(32), nullable=True),
        sa.Column("cost_amount", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["farm_crop_id"],
            ["farm_crops.id"],
            name=op.f("fk_farm_activities_farm_crop_id_farm_crops"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_farm_activities_farm_crop_id"), "farm_activities", ["farm_crop_id"])

    # --- 0006 slot: weather_records ---
    op.create_table(
        "weather_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("temp_c", sa.Float(), nullable=True),
        sa.Column("humidity", sa.Float(), nullable=True),
        sa.Column("rainfall_mm", sa.Float(), nullable=True),
        sa.Column("raw_json", sa.Text(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(op.f("ix_weather_records_latitude"), "weather_records", ["latitude"])
    op.create_index(op.f("ix_weather_records_longitude"), "weather_records", ["longitude"])

    # --- 0007 slot: markets + market_commodities + market_prices ---
    op.create_table(
        "markets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("district", sa.String(64), nullable=True),
        sa.Column("state", sa.String(64), nullable=True),
        sa.Column("taluka", sa.String(64), nullable=True),
        sa.Column("village", sa.String(64), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_table(
        "market_commodities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("variety", sa.String(128), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("local_name", sa.String(128), nullable=True),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.UniqueConstraint("name", name=op.f("uq_market_commodities_name")),
    )
    op.create_table(
        "market_prices",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("commodity_id", sa.Uuid(), nullable=False),
        sa.Column("market_id", sa.Uuid(), nullable=False),
        sa.Column("price_per_quintal", sa.Float(), nullable=False),
        sa.Column("modal_price", sa.Float(), nullable=True),
        sa.Column("min_price", sa.Float(), nullable=True),
        sa.Column("max_price", sa.Float(), nullable=True),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(128), nullable=True),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("is_sample", sa.Boolean(), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["commodity_id"],
            ["market_commodities.id"],
            name=op.f("fk_market_prices_commodity_id_market_commodities"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["market_id"],
            ["markets.id"],
            name=op.f("fk_market_prices_market_id_markets"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_market_prices_commodity_id"), "market_prices", ["commodity_id"])
    op.create_index(op.f("ix_market_prices_market_id"), "market_prices", ["market_id"])
    op.create_index(op.f("ix_market_prices_price_date"), "market_prices", ["price_date"])

    # --- 0008 slot: documents + document_chunks, ai_conversations + ai_messages ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("source_name", sa.String(256), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("doc_type", sa.String(64), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", EmbeddingVector(dimensions=1536), nullable=True),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_chunks_document_id_documents"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_document_chunks_document_id"), "document_chunks", ["document_id"])

    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("language", sa.String(8), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(op.f("ix_ai_conversations_farmer_user_id"), "ai_conversations", ["farmer_user_id"])
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources_json", sa.Text(), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["ai_conversations.id"],
            name=op.f("fk_ai_messages_conversation_id_ai_conversations"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(op.f("ix_ai_messages_conversation_id"), "ai_messages", ["conversation_id"])

    # --- 0009 slot: crop_image_analyses (no hard FKs by design) ---
    op.create_table(
        "crop_image_analyses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("farm_crop_id", sa.Uuid(), nullable=True),
        sa.Column("image_path", sa.String(512), nullable=False),
        sa.Column("thumbnail_path", sa.String(512), nullable=True),
        sa.Column("extra_image_references", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("is_mock", sa.Boolean(), nullable=False),
        sa.Column("possible_condition", sa.String(256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("observations_json", sa.Text(), nullable=True),
        sa.Column("needs_info_json", sa.Text(), nullable=True),
        sa.Column("next_steps_json", sa.Text(), nullable=True),
        sa.Column("image_quality", sa.String(32), nullable=True),
        sa.Column("quality_notes", sa.Text(), nullable=True),
        sa.Column("sources_json", sa.Text(), nullable=True),
        sa.Column("response_language", sa.String(8), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(
        op.f("ix_crop_image_analyses_farmer_user_id"), "crop_image_analyses", ["farmer_user_id"]
    )
    op.create_index(op.f("ix_crop_image_analyses_farm_id"), "crop_image_analyses", ["farm_id"])
    op.create_index(
        op.f("ix_crop_image_analyses_farm_crop_id"), "crop_image_analyses", ["farm_crop_id"]
    )

    # --- 0010 slot: soil_tests + fertilizer_applications (no hard FKs by design) ---
    op.create_table(
        "soil_tests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("tested_on", sa.Date(), nullable=True),
        sa.Column("lab_name", sa.String(128), nullable=True),
        sa.Column("laboratory_name", sa.String(128), nullable=True),
        sa.Column("report_number", sa.String(64), nullable=True),
        sa.Column("soil_type", sa.String(32), nullable=True),
        sa.Column("ph", sa.Numeric(4, 2), nullable=True),
        sa.Column("electrical_conductivity", sa.Numeric(6, 3), nullable=True),
        sa.Column("organic_carbon", sa.Numeric(5, 2), nullable=True),
        sa.Column("nitrogen", sa.Numeric(8, 2), nullable=True),
        sa.Column("phosphorus", sa.Numeric(8, 2), nullable=True),
        sa.Column("potassium", sa.Numeric(8, 2), nullable=True),
        sa.Column("sulphur", sa.Numeric(8, 2), nullable=True),
        sa.Column("zinc", sa.Numeric(8, 2), nullable=True),
        sa.Column("iron", sa.Numeric(8, 2), nullable=True),
        sa.Column("manganese", sa.Numeric(8, 2), nullable=True),
        sa.Column("copper", sa.Numeric(8, 2), nullable=True),
        sa.Column("boron", sa.Numeric(8, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("report_file_path", sa.String(512), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(op.f("ix_soil_tests_farmer_user_id"), "soil_tests", ["farmer_user_id"])
    op.create_index(op.f("ix_soil_tests_farm_id"), "soil_tests", ["farm_id"])
    op.create_table(
        "fertilizer_applications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("farm_crop_id", sa.Uuid(), nullable=False),
        sa.Column("fertilizer_name", sa.String(128), nullable=False),
        sa.Column("fertilizer_type", sa.String(32), nullable=True),
        sa.Column("quantity_kg", sa.Numeric(10, 3), nullable=True),
        sa.Column("quantity_unit", sa.String(16), nullable=False),
        sa.Column("application_method", sa.String(64), nullable=True),
        sa.Column("purpose", sa.String(256), nullable=True),
        sa.Column("applied_on", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
    )
    op.create_index(
        op.f("ix_fertilizer_applications_farmer_user_id"),
        "fertilizer_applications",
        ["farmer_user_id"],
    )
    op.create_index(
        op.f("ix_fertilizer_applications_farm_id"), "fertilizer_applications", ["farm_id"]
    )
    op.create_index(
        op.f("ix_fertilizer_applications_farm_crop_id"),
        "fertilizer_applications",
        ["farm_crop_id"],
    )

    # --- 0011 slot: pests + diseases + crop_health_observations + health_actions ---
    op.create_table(
        "pests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("local_name", sa.String(128), nullable=True),
        sa.Column("scientific_name", sa.String(256), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.UniqueConstraint("name", name=op.f("uq_pests_name")),
    )
    op.create_table(
        "diseases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("local_name", sa.String(128), nullable=True),
        sa.Column("scientific_name", sa.String(256), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.UniqueConstraint("name", name=op.f("uq_diseases_name")),
    )
    op.create_table(
        "crop_health_observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("farmer_user_id", sa.Uuid(), nullable=False),
        sa.Column("farm_id", sa.Uuid(), nullable=False),
        sa.Column("farm_crop_id", sa.Uuid(), nullable=False),
        sa.Column("observation_type", sa.String(16), nullable=False),
        sa.Column("pest_id", sa.Uuid(), nullable=True),
        sa.Column("disease_id", sa.Uuid(), nullable=True),
        sa.Column("observed_name", sa.String(256), nullable=True),
        sa.Column("observed_on", sa.Date(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=True),
        sa.Column("affected_area", sa.Numeric(10, 2), nullable=True),
        sa.Column("affected_area_unit", sa.String(16), nullable=True),
        sa.Column("symptoms", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("photo_references", sa.Text(), nullable=True),
        sa.Column("linked_analysis_id", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["pest_id"],
            ["pests.id"],
            name=op.f("fk_crop_health_observations_pest_id_pests"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["disease_id"],
            ["diseases.id"],
            name=op.f("fk_crop_health_observations_disease_id_diseases"),
            ondelete="SET NULL",
        ),
    )
    op.create_index(
        op.f("ix_crop_health_observations_farmer_user_id"),
        "crop_health_observations",
        ["farmer_user_id"],
    )
    op.create_index(
        op.f("ix_crop_health_observations_farm_id"), "crop_health_observations", ["farm_id"]
    )
    op.create_index(
        op.f("ix_crop_health_observations_farm_crop_id"),
        "crop_health_observations",
        ["farm_crop_id"],
    )
    op.create_table(
        "health_actions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("product_name", sa.String(128), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 3), nullable=True),
        sa.Column("quantity_unit", sa.String(16), nullable=True),
        sa.Column("acted_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", **_TS, nullable=False),
        sa.Column("updated_at", **_TS, nullable=False),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["crop_health_observations.id"],
            name=op.f("fk_health_actions_observation_id_crop_health_observations"),
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        op.f("ix_health_actions_observation_id"), "health_actions", ["observation_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_health_actions_observation_id"), table_name="health_actions")
    op.drop_table("health_actions")
    op.drop_index(
        op.f("ix_crop_health_observations_farm_crop_id"),
        table_name="crop_health_observations",
    )
    op.drop_index(
        op.f("ix_crop_health_observations_farm_id"), table_name="crop_health_observations"
    )
    op.drop_index(
        op.f("ix_crop_health_observations_farmer_user_id"),
        table_name="crop_health_observations",
    )
    op.drop_table("crop_health_observations")
    op.drop_table("diseases")
    op.drop_table("pests")
    op.drop_index(
        op.f("ix_fertilizer_applications_farm_crop_id"),
        table_name="fertilizer_applications",
    )
    op.drop_index(
        op.f("ix_fertilizer_applications_farm_id"), table_name="fertilizer_applications"
    )
    op.drop_index(
        op.f("ix_fertilizer_applications_farmer_user_id"),
        table_name="fertilizer_applications",
    )
    op.drop_table("fertilizer_applications")
    op.drop_index(op.f("ix_soil_tests_farm_id"), table_name="soil_tests")
    op.drop_index(op.f("ix_soil_tests_farmer_user_id"), table_name="soil_tests")
    op.drop_table("soil_tests")
    op.drop_index(
        op.f("ix_crop_image_analyses_farm_crop_id"), table_name="crop_image_analyses"
    )
    op.drop_index(op.f("ix_crop_image_analyses_farm_id"), table_name="crop_image_analyses")
    op.drop_index(
        op.f("ix_crop_image_analyses_farmer_user_id"), table_name="crop_image_analyses"
    )
    op.drop_table("crop_image_analyses")
    op.drop_index(op.f("ix_ai_messages_conversation_id"), table_name="ai_messages")
    op.drop_table("ai_messages")
    op.drop_index(
        op.f("ix_ai_conversations_farmer_user_id"), table_name="ai_conversations"
    )
    op.drop_table("ai_conversations")
    op.drop_index(op.f("ix_document_chunks_document_id"), table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_index(op.f("ix_market_prices_price_date"), table_name="market_prices")
    op.drop_index(op.f("ix_market_prices_market_id"), table_name="market_prices")
    op.drop_index(op.f("ix_market_prices_commodity_id"), table_name="market_prices")
    op.drop_table("market_prices")
    op.drop_table("market_commodities")
    op.drop_table("markets")
    op.drop_index(op.f("ix_weather_records_longitude"), table_name="weather_records")
    op.drop_index(op.f("ix_weather_records_latitude"), table_name="weather_records")
    op.drop_table("weather_records")
    op.drop_index(op.f("ix_farm_activities_farm_crop_id"), table_name="farm_activities")
    op.drop_table("farm_activities")
    op.drop_index(op.f("ix_farm_crops_status"), table_name="farm_crops")
    op.drop_index(op.f("ix_farm_crops_crop_variety_id"), table_name="farm_crops")
    op.drop_index(op.f("ix_farm_crops_farm_id"), table_name="farm_crops")
    op.drop_table("farm_crops")
    op.drop_index(op.f("ix_crop_varieties_crop_name"), table_name="crop_varieties")
    op.drop_table("crop_varieties")
    op.drop_table("soil_records")
    op.drop_index(op.f("ix_farms_owner_user_id"), table_name="farms")
    op.drop_table("farms")
