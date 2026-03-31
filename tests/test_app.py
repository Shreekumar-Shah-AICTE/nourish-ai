"""
NourishAI — Test Suite
Validates core API endpoints and application logic
"""

import json
import pytest
from app import app


@pytest.fixture
def client():
    """Create test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


class TestHealthCheck:
    """Health check endpoint tests."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_service_name(self, client):
        response = client.get("/health")
        data = json.loads(response.data)
        assert data["service"] == "NourishAI"
        assert data["status"] == "healthy"
        assert "version" in data


class TestPageRoutes:
    """Page rendering tests."""

    def test_index_page(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert b"NourishAI" in response.data

    def test_dashboard_page(self, client):
        response = client.get("/dashboard")
        assert response.status_code == 200

    def test_chat_page(self, client):
        response = client.get("/chat")
        assert response.status_code == 200

    def test_meal_plan_page(self, client):
        response = client.get("/meal-plan")
        assert response.status_code == 200

    def test_analyze_page(self, client):
        response = client.get("/analyze")
        assert response.status_code == 200

    def test_profile_page(self, client):
        response = client.get("/profile")
        assert response.status_code == 200

    def test_404_page(self, client):
        response = client.get("/nonexistent")
        assert response.status_code == 404


class TestProfileAPI:
    """Profile API endpoint tests."""

    def test_save_profile(self, client):
        profile_data = {
            "name": "Test User",
            "age": 25,
            "gender": "male",
            "weight": 70,
            "height": 175,
            "activity_level": "moderate",
            "goal": "lose",
            "dietary_pref": "vegetarian",
            "allergies": ["gluten", "dairy"],
        }
        response = client.post(
            "/api/profile",
            data=json.dumps(profile_data),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert "bmr" in data["profile"]
        assert "tdee" in data["profile"]
        assert "daily_calorie_target" in data["profile"]
        assert "macro_targets" in data["profile"]

    def test_save_profile_empty_body(self, client):
        response = client.post(
            "/api/profile",
            data=json.dumps(None),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_get_profile(self, client):
        response = client.get("/api/profile")
        assert response.status_code == 200

    def test_bmr_calculation_male(self, client):
        profile = {"gender": "male", "weight": 80, "height": 180, "age": 30}
        response = client.post(
            "/api/profile",
            data=json.dumps(profile),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["profile"]["bmr"] > 0
        assert data["profile"]["tdee"] > data["profile"]["bmr"]

    def test_bmr_calculation_female(self, client):
        profile = {"gender": "female", "weight": 60, "height": 165, "age": 28}
        response = client.post(
            "/api/profile",
            data=json.dumps(profile),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["profile"]["bmr"] > 0


class TestMealLogAPI:
    """Meal logging tests."""

    def test_log_meal(self, client):
        meal = {
            "name": "Grilled Chicken",
            "calories": 350,
            "protein": 40,
            "carbs": 10,
            "fat": 15,
            "meal_type": "lunch",
        }
        response = client.post(
            "/api/log-meal",
            data=json.dumps(meal),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["success"] is True
        assert data["daily_totals"]["calories"] == 350

    def test_daily_summary(self, client):
        response = client.get("/api/daily-summary")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "summary" in data


class TestWaterAPI:
    """Water tracking tests."""

    def test_add_water(self, client):
        response = client.post(
            "/api/water",
            data=json.dumps({"action": "add"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["glasses"] == 1
        assert data["ml"] == 250

    def test_remove_water(self, client):
        # Add first
        client.post("/api/water", data=json.dumps({"action": "add"}), content_type="application/json")
        # Remove
        response = client.post(
            "/api/water",
            data=json.dumps({"action": "remove"}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["glasses"] == 0


class TestChatAPI:
    """Chat API validation tests (without actual AI calls)."""

    def test_chat_empty_message(self, client):
        response = client.post(
            "/api/chat",
            data=json.dumps({"message": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_chat_long_message(self, client):
        response = client.post(
            "/api/chat",
            data=json.dumps({"message": "x" * 1001}),
            content_type="application/json",
        )
        assert response.status_code == 400


class TestAnalyzeAPI:
    """Food analysis validation tests."""

    def test_analyze_empty_food(self, client):
        response = client.post(
            "/api/analyze",
            data=json.dumps({"food": ""}),
            content_type="application/json",
        )
        assert response.status_code == 400


class TestQuickTip:
    """Quick tip endpoint test."""

    def test_quick_tip(self, client):
        response = client.get("/api/quick-tip")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "tip" in data
