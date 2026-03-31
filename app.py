"""
NourishAI — AI-powered Smart Nutrition Assistant
Built for AMD Slingshot Campus Days 2026
"""

import os
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for, flash
)
from dotenv import load_dotenv
import google.generativeai as genai

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "nourishai-dev-secret-2026")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Gemini AI
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.0-flash")
    logger.info("✅ Gemini AI configured successfully")
else:
    model = None
    logger.warning("⚠️ GOOGLE_API_KEY not set — AI features will use fallback")

# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------
NUTRITIONIST_SYSTEM = """You are NourishAI, an expert AI nutritionist and health coach.
You provide evidence-based nutritional advice, meal suggestions, and dietary guidance.

RULES:
- Always be encouraging and supportive
- Provide specific, actionable advice with quantities
- Include calorie and macro estimates when discussing foods
- Consider cultural food preferences (especially Indian cuisine)
- Flag any medical disclaimers when appropriate
- Use emojis sparingly for warmth
- Keep responses concise but informative (max 300 words)
- Format responses with markdown for readability

USER PROFILE (if available): {profile}
"""

MEAL_PLAN_SYSTEM = """You are a professional meal planner AI. Generate a structured daily meal plan.

RULES:
- Create plans for: Breakfast, Mid-Morning Snack, Lunch, Evening Snack, Dinner
- Include exact portions and calorie counts for each item
- Balance macronutrients (protein, carbs, fats)
- Consider the user's dietary preferences and restrictions
- Include preparation time estimates
- Suggest practical, easy-to-prepare meals
- Include a mix of Indian and international cuisine

RESPOND IN THIS EXACT JSON FORMAT:
{
  "total_calories": number,
  "total_protein": number,
  "total_carbs": number,
  "total_fat": number,
  "meals": [
    {
      "type": "Breakfast",
      "time": "7:00 AM - 8:00 AM",
      "items": [
        {"name": "item name", "portion": "portion size", "calories": number, "protein": number, "carbs": number, "fat": number}
      ],
      "prep_time": "15 mins",
      "tip": "optional cooking tip"
    }
  ],
  "hydration_goal": "2.5L",
  "daily_tip": "a motivational nutrition tip"
}

USER PROFILE: {profile}
USER REQUEST: {request}
"""

FOOD_ANALYSIS_SYSTEM = """You are a nutrition analysis AI. Analyze the food described by the user.

Provide a detailed nutritional breakdown.

RESPOND IN THIS EXACT JSON FORMAT:
{
  "food_name": "identified food name",
  "serving_size": "standard serving size",
  "calories": number,
  "macros": {
    "protein": {"amount": number, "unit": "g", "daily_percent": number},
    "carbohydrates": {"amount": number, "unit": "g", "daily_percent": number},
    "fat": {"amount": number, "unit": "g", "daily_percent": number},
    "fiber": {"amount": number, "unit": "g", "daily_percent": number},
    "sugar": {"amount": number, "unit": "g", "daily_percent": number}
  },
  "micros": [
    {"name": "Vitamin C", "amount": "15mg", "daily_percent": 17}
  ],
  "health_score": number (1-10),
  "health_tags": ["High Protein", "Low Sugar"],
  "warnings": ["optional health warnings"],
  "healthier_alternatives": ["alternative 1", "alternative 2"],
  "fun_fact": "an interesting nutrition fact about this food"
}
"""

GROCERY_SYSTEM = """Based on the following meal plan, generate a smart grocery list.
Group items by category (Produce, Dairy, Grains, Protein, Pantry, Spices).
Include quantities needed for the plan duration.

RESPOND IN THIS EXACT JSON FORMAT:
{
  "categories": [
    {
      "name": "Produce",
      "icon": "🥬",
      "items": [
        {"name": "Spinach", "quantity": "200g", "estimated_cost": "₹30"}
      ]
    }
  ],
  "estimated_total": "₹XXX",
  "shopping_tips": ["Buy seasonal vegetables for freshness and savings"]
}

MEAL PLAN: {meal_plan}
"""


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def get_user_profile():
    """Retrieve user profile from session."""
    return session.get("profile", {})


def ai_generate(prompt, system_prompt="", retries=2):
    """Generate content using Gemini AI with retry logic."""
    if not model:
        return {"error": "AI service not configured. Please set GOOGLE_API_KEY."}

    full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt

    for attempt in range(retries):
        try:
            response = model.generate_content(
                full_prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2048,
                ),
            )
            return response.text
        except Exception as e:
            logger.error(f"Gemini API error (attempt {attempt + 1}): {e}")
            if attempt == retries - 1:
                return {"error": f"AI generation failed: {str(e)}"}
    return {"error": "AI service temporarily unavailable."}


def parse_ai_json(text):
    """Extract and parse JSON from AI response text."""
    try:
        # Try direct parse
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass

    if isinstance(text, str):
        # Try to find JSON in markdown code blocks
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find raw JSON object
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

    return None


# ---------------------------------------------------------------------------
# Page Routes
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    """Landing page."""
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    """Main dashboard with daily tracking."""
    profile = get_user_profile()
    return render_template("dashboard.html", profile=profile)


@app.route("/chat")
def chat():
    """AI nutritionist chatbot."""
    return render_template("chat.html")


@app.route("/meal-plan")
def meal_plan():
    """AI meal planner."""
    profile = get_user_profile()
    return render_template("meal_plan.html", profile=profile)


@app.route("/analyze")
def analyze():
    """Food nutrition analyzer."""
    return render_template("analyze.html")


@app.route("/grocery")
def grocery():
    """Smart grocery list."""
    return render_template("grocery.html")


@app.route("/profile")
def profile():
    """User profile setup."""
    profile = get_user_profile()
    return render_template("profile.html", profile=profile)


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------
@app.route("/api/profile", methods=["POST"])
def save_profile():
    """Save user health profile to session."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        profile = {
            "name": data.get("name", "User"),
            "age": data.get("age", 25),
            "gender": data.get("gender", "other"),
            "weight": data.get("weight", 70),
            "height": data.get("height", 170),
            "activity_level": data.get("activity_level", "moderate"),
            "goal": data.get("goal", "maintain"),
            "dietary_pref": data.get("dietary_pref", "none"),
            "allergies": data.get("allergies", []),
            "health_conditions": data.get("health_conditions", []),
            "daily_calorie_target": data.get("daily_calorie_target", 2000),
            "updated_at": datetime.now().isoformat(),
        }

        # Calculate BMR and TDEE
        if profile["gender"] == "male":
            bmr = 88.362 + (13.397 * profile["weight"]) + (4.799 * profile["height"]) - (5.677 * profile["age"])
        elif profile["gender"] == "female":
            bmr = 447.593 + (9.247 * profile["weight"]) + (3.098 * profile["height"]) - (4.330 * profile["age"])
        else:
            bmr = 260 + (11.3 * profile["weight"]) + (3.9 * profile["height"]) - (5.0 * profile["age"])

        activity_multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9,
        }
        tdee = bmr * activity_multipliers.get(profile["activity_level"], 1.55)

        goal_adjustments = {
            "lose": -500,
            "maintain": 0,
            "gain": 400,
        }
        profile["bmr"] = round(bmr)
        profile["tdee"] = round(tdee)
        profile["daily_calorie_target"] = round(tdee + goal_adjustments.get(profile["goal"], 0))

        # Macro targets (balanced split)
        cal = profile["daily_calorie_target"]
        profile["macro_targets"] = {
            "protein": round(cal * 0.30 / 4),   # 30% from protein
            "carbs": round(cal * 0.45 / 4),      # 45% from carbs
            "fat": round(cal * 0.25 / 9),        # 25% from fat
        }

        session["profile"] = profile
        logger.info(f"Profile saved: {profile['name']}, TDEE={profile['tdee']}")
        return jsonify({"success": True, "profile": profile})

    except Exception as e:
        logger.error(f"Profile save error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/profile", methods=["GET"])
def get_profile():
    """Get current user profile."""
    profile = get_user_profile()
    return jsonify({"profile": profile})


@app.route("/api/chat", methods=["POST"])
def chat_api():
    """AI nutritionist chat endpoint."""
    try:
        data = request.get_json()
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"error": "Please enter a message"}), 400

        if len(message) > 1000:
            return jsonify({"error": "Message too long (max 1000 chars)"}), 400

        profile = get_user_profile()
        profile_str = json.dumps(profile) if profile else "No profile set"
        system = NUTRITIONIST_SYSTEM.format(profile=profile_str)

        response = ai_generate(message, system)

        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 503

        # Store chat history in session (last 20 messages)
        history = session.get("chat_history", [])
        history.append({"role": "user", "content": message, "time": datetime.now().isoformat()})
        history.append({"role": "assistant", "content": response, "time": datetime.now().isoformat()})
        session["chat_history"] = history[-20:]

        return jsonify({"response": response})

    except Exception as e:
        logger.error(f"Chat API error: {e}")
        return jsonify({"error": "Something went wrong. Please try again."}), 500


@app.route("/api/meal-plan", methods=["POST"])
def generate_meal_plan():
    """Generate personalized meal plan using Gemini."""
    try:
        data = request.get_json()
        user_request = data.get("request", "Generate a healthy balanced meal plan for today")
        profile = get_user_profile()
        profile_str = json.dumps(profile) if profile else "Default: 2000 cal, balanced diet, no restrictions"

        system = MEAL_PLAN_SYSTEM.format(profile=profile_str, request=user_request)

        response = ai_generate(system)

        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 503

        meal_plan = parse_ai_json(response)
        if meal_plan:
            session["last_meal_plan"] = meal_plan
            return jsonify({"meal_plan": meal_plan})
        else:
            return jsonify({"meal_plan_text": response})

    except Exception as e:
        logger.error(f"Meal plan error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze", methods=["POST"])
def analyze_food():
    """Analyze food nutrition using Gemini."""
    try:
        data = request.get_json()
        food_description = data.get("food", "").strip()

        if not food_description:
            return jsonify({"error": "Please describe the food to analyze"}), 400

        prompt = f"Analyze this food item: {food_description}"
        response = ai_generate(prompt, FOOD_ANALYSIS_SYSTEM)

        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 503

        analysis = parse_ai_json(response)
        if analysis:
            # Log to meal history
            log = session.get("meal_log", [])
            log.append({
                "food": food_description,
                "calories": analysis.get("calories", 0),
                "time": datetime.now().isoformat(),
            })
            session["meal_log"] = log[-50:]
            return jsonify({"analysis": analysis})
        else:
            return jsonify({"analysis_text": response})

    except Exception as e:
        logger.error(f"Analyze error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/grocery-list", methods=["POST"])
def generate_grocery():
    """Generate smart grocery list from meal plan."""
    try:
        data = request.get_json()
        meal_plan = data.get("meal_plan") or session.get("last_meal_plan", {})

        if not meal_plan:
            return jsonify({"error": "Generate a meal plan first"}), 400

        system = GROCERY_SYSTEM.format(meal_plan=json.dumps(meal_plan))
        response = ai_generate(system)

        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 503

        grocery = parse_ai_json(response)
        if grocery:
            return jsonify({"grocery_list": grocery})
        else:
            return jsonify({"grocery_text": response})

    except Exception as e:
        logger.error(f"Grocery list error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/log-meal", methods=["POST"])
def log_meal():
    """Log a consumed meal for daily tracking."""
    try:
        data = request.get_json()
        meal = {
            "name": data.get("name", ""),
            "calories": data.get("calories", 0),
            "protein": data.get("protein", 0),
            "carbs": data.get("carbs", 0),
            "fat": data.get("fat", 0),
            "meal_type": data.get("meal_type", "snack"),
            "time": datetime.now().isoformat(),
        }

        log = session.get("meal_log", [])
        log.append(meal)
        session["meal_log"] = log

        # Calculate daily totals
        today = datetime.now().date().isoformat()
        today_meals = [m for m in log if m["time"].startswith(today)]
        daily_totals = {
            "calories": sum(m.get("calories", 0) for m in today_meals),
            "protein": sum(m.get("protein", 0) for m in today_meals),
            "carbs": sum(m.get("carbs", 0) for m in today_meals),
            "fat": sum(m.get("fat", 0) for m in today_meals),
            "meals_count": len(today_meals),
        }

        return jsonify({"success": True, "meal": meal, "daily_totals": daily_totals})

    except Exception as e:
        logger.error(f"Log meal error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/daily-summary", methods=["GET"])
def daily_summary():
    """Get today's nutrition summary."""
    try:
        log = session.get("meal_log", [])
        today = datetime.now().date().isoformat()
        today_meals = [m for m in log if m.get("time", "").startswith(today)]
        profile = get_user_profile()

        daily = {
            "calories": sum(m.get("calories", 0) for m in today_meals),
            "protein": sum(m.get("protein", 0) for m in today_meals),
            "carbs": sum(m.get("carbs", 0) for m in today_meals),
            "fat": sum(m.get("fat", 0) for m in today_meals),
            "meals_count": len(today_meals),
            "meals": today_meals,
            "target_calories": profile.get("daily_calorie_target", 2000),
            "macro_targets": profile.get("macro_targets", {"protein": 150, "carbs": 225, "fat": 56}),
        }

        # Calculate streak
        daily["streak"] = session.get("streak", 0)
        daily["water_glasses"] = session.get("water_today", 0)

        return jsonify({"summary": daily})

    except Exception as e:
        logger.error(f"Daily summary error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/water", methods=["POST"])
def log_water():
    """Log water intake."""
    current = session.get("water_today", 0)
    action = request.get_json().get("action", "add")
    if action == "add" and current < 15:
        current += 1
    elif action == "remove" and current > 0:
        current -= 1
    session["water_today"] = current
    return jsonify({"glasses": current, "ml": current * 250})


@app.route("/api/quick-tip", methods=["GET"])
def quick_tip():
    """Get a quick nutrition tip from Gemini."""
    try:
        profile = get_user_profile()
        goal = profile.get("goal", "maintain health")
        prompt = f"Give me ONE short, practical nutrition tip for someone trying to {goal}. Keep it under 50 words. Be specific and actionable."

        response = ai_generate(prompt)
        if isinstance(response, dict) and "error" in response:
            tips = [
                "🥤 Start your day with a glass of warm lemon water to kickstart metabolism.",
                "🥗 Fill half your plate with colorful vegetables at every meal.",
                "🥜 Keep a handful of mixed nuts as an emergency healthy snack.",
                "⏰ Try to eat dinner at least 2 hours before bedtime.",
                "🫘 Add a source of protein to every meal to stay fuller longer.",
            ]
            import random
            return jsonify({"tip": random.choice(tips)})

        return jsonify({"tip": response.strip()})
    except Exception as e:
        return jsonify({"tip": "🥗 Eat a rainbow of vegetables daily for optimal nutrition!"}), 200


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# ---------------------------------------------------------------------------
# Health Check (Cloud Run)
# ---------------------------------------------------------------------------
@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "NourishAI",
        "version": "1.0.0",
        "ai_configured": model is not None,
        "timestamp": datetime.now().isoformat(),
    })


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    debug = os.environ.get("FLASK_ENV") == "development"
    app.run(host="0.0.0.0", port=port, debug=debug)
