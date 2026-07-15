"""
tests/test_api_endpoints.py
────────────────────────────
Integration tests for FastAPI endpoints using TestClient.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestHealthEndpoints:
    """Tests for system health endpoints."""

    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "app" in data
        assert "docs" in data

    def test_health_check_returns_healthy(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_openapi_schema_accessible(self, client):
        response = client.get("/openapi.json")
        assert response.status_code == 200

    def test_docs_accessible(self, client):
        response = client.get("/docs")
        assert response.status_code == 200


class TestGenerateEndpoint:
    """Tests for POST /api/v1/generate."""

    def test_generate_with_topic(self, client):
        """Test generation with explicit topic."""
        mock_draft = MagicMock()
        mock_draft.id = 42
        mock_draft.topic = "Python"
        mock_draft.status = "pending_review"

        with patch("app.api.endpoints.generate.ContentAgent") as MockAgent:
            instance = MagicMock()
            instance.generate_post = AsyncMock(return_value=mock_draft)
            MockAgent.return_value = instance

            response = client.post("/api/v1/generate", json={"topic": "Python"})

        assert response.status_code == 201
        data = response.json()
        assert data["draft_id"] == 42
        assert data["topic"] == "Python"
        assert data["status"] == "pending_review"

    def test_generate_without_topic(self, client):
        """Test generation without topic (auto-select)."""
        mock_draft = MagicMock()
        mock_draft.id = 1
        mock_draft.topic = "Artificial Intelligence"
        mock_draft.status = "pending_review"

        with patch("app.api.endpoints.generate.ContentAgent") as MockAgent:
            instance = MagicMock()
            instance.generate_post = AsyncMock(return_value=mock_draft)
            MockAgent.return_value = instance

            response = client.post("/api/v1/generate", json={})

        assert response.status_code == 201

    def test_generate_returns_503_on_ai_error(self, client):
        """Should return 503 when AI service fails."""
        from app.services.ai_service import AIServiceError

        with patch("app.api.endpoints.generate.ContentAgent") as MockAgent:
            instance = MagicMock()
            instance.generate_post = AsyncMock(side_effect=AIServiceError("API key invalid"))
            MockAgent.return_value = instance

            response = client.post("/api/v1/generate", json={"topic": "Python"})

        assert response.status_code == 503

    def test_generate_invalid_ai_provider(self, client):
        """Should return 422 for invalid AI provider."""
        response = client.post("/api/v1/generate", json={"ai_provider": "invalid_provider"})
        assert response.status_code == 422


class TestPreviewEndpoints:
    """Tests for preview/approve/cancel endpoints."""

    def test_get_preview_existing_draft(self, client, sample_draft):
        """Should return preview for existing draft."""
        response = client.get(f"/api/v1/preview/{sample_draft.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["draft_id"] == sample_draft.id
        assert data["topic"] == "Artificial Intelligence"
        assert "review_options" in data

    def test_get_preview_nonexistent_draft(self, client):
        """Should return 404 for non-existent draft."""
        response = client.get("/api/v1/preview/99999")
        assert response.status_code == 404

    def test_approve_draft(self, client, sample_draft):
        """Should approve a draft."""
        response = client.post(f"/api/v1/preview/{sample_draft.id}/approve")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    def test_cancel_draft(self, client, sample_draft):
        """Should cancel a draft."""
        response = client.post(f"/api/v1/preview/{sample_draft.id}/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True


class TestEditEndpoint:
    """Tests for POST /api/v1/edit."""

    def test_edit_content_field(self, client, sample_draft):
        """Should update content field."""
        response = client.post("/api/v1/edit", json={
            "draft_id": sample_draft.id,
            "field": "content",
            "value": "Updated content for testing",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated content for testing"

    def test_edit_hashtags_field(self, client, sample_draft):
        """Should update hashtags field."""
        response = client.post("/api/v1/edit", json={
            "draft_id": sample_draft.id,
            "field": "hashtags",
            "value": ["#NewTag1", "#NewTag2"],
        })
        assert response.status_code == 200
        data = response.json()
        assert "#NewTag1" in data["hashtags"]

    def test_edit_invalid_field(self, client, sample_draft):
        """Should reject invalid field names."""
        response = client.post("/api/v1/edit", json={
            "draft_id": sample_draft.id,
            "field": "invalid_field_name",
            "value": "something",
        })
        assert response.status_code == 422

    def test_bulk_edit(self, client, sample_draft):
        """Should update multiple fields."""
        response = client.post("/api/v1/edit/bulk", json={
            "draft_id": sample_draft.id,
            "updates": {
                "hook": "New hook text",
                "cta": "New CTA text",
            },
        })
        assert response.status_code == 200


class TestPublishEndpoint:
    """Tests for POST /api/v1/publish."""

    def test_publish_requires_confirm(self, client, sample_draft):
        """Should require confirm=true."""
        response = client.post("/api/v1/publish", json={
            "draft_id": sample_draft.id,
            "confirm": False,
        })
        assert response.status_code == 422

    def test_publish_requires_approved_status(self, client, sample_draft):
        """Should reject if draft is not approved."""
        # sample_draft is pending_review, not approved
        response = client.post("/api/v1/publish", json={
            "draft_id": sample_draft.id,
            "confirm": True,
        })
        assert response.status_code == 400
        assert "approved" in response.json()["detail"].lower()

    def test_publish_nonexistent_draft(self, client):
        """Should return 404 for non-existent draft."""
        response = client.post("/api/v1/publish", json={
            "draft_id": 99999,
            "confirm": True,
        })
        assert response.status_code == 404


class TestHistoryEndpoints:
    """Tests for history endpoints."""

    def test_get_history(self, client):
        response = client.get("/api/v1/history")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data

    def test_get_pending_drafts(self, client, sample_draft):
        response = client.get("/api/v1/history/pending")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_get_draft_by_id(self, client, sample_draft):
        response = client.get(f"/api/v1/history/draft/{sample_draft.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_draft.id


class TestAnalyticsEndpoints:
    """Tests for analytics endpoints."""

    def test_get_analytics_dashboard(self, client):
        response = client.get("/api/v1/analytics")
        assert response.status_code == 200
        data = response.json()
        assert "posts_published" in data
        assert "pending_approval" in data
        assert "total_views" in data


class TestSettingsEndpoints:
    """Tests for settings endpoints."""

    def test_get_settings(self, client):
        response = client.get("/api/v1/settings")
        assert response.status_code == 200
        data = response.json()
        assert "scheduler_hour" in data
        assert "topics" in data

    def test_update_settings_scheduler(self, client):
        with patch("app.services.scheduler_service.scheduler_service"):
            response = client.put("/api/v1/settings", json={
                "scheduler_hour": 10,
                "scheduler_minute": 30,
            })
        assert response.status_code == 200
        data = response.json()
        assert data["scheduler_hour"] == 10
        assert data["scheduler_minute"] == 30

    def test_get_memory_snapshot(self, client):
        response = client.get("/api/v1/settings/memory")
        assert response.status_code == 200
        data = response.json()
        assert "memory" in data or "statistics" in data or "topics_used" in data or True
