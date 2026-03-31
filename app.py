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
# Feature: Recipe Suggestions
# ---------------------------------------------------------------------------
RECIPE_SYSTEM = """You are a recipe suggestion AI. Based on the ingredients or preferences
described, suggest 3 quick, healthy recipes.

RESPOND IN THIS EXACT JSON FORMAT:
{
  "recipes": [
    {
      "name": "Recipe Name",
      "cuisine": "Indian",
      "prep_time": "20 mins",
      "cook_time": "15 mins",
      "difficulty": "Easy",
      "servings": 2,
      "calories_per_serving": 350,
      "ingredients": ["ingredient 1", "ingredient 2"],
      "instructions": ["Step 1", "Step 2"],
      "nutrition_highlight": "High in protein, low in fat",
      "health_benefits": ["Boosts immunity", "Good for digestion"]
    }
  ]
}
"""


@app.route("/api/recipes", methods=["POST"])
def suggest_recipes():
    """Get AI-powered recipe suggestions based on ingredients or preferences."""
    try:
        data = request.get_json()
        query = data.get("query", "").strip()
        if not query:
            return jsonify({"error": "Please describe ingredients or preferences"}), 400

        profile = get_user_profile()
        dietary = profile.get("dietary_pref", "none")
        allergies = profile.get("allergies", [])

        prompt = f"""Suggest 3 healthy recipes for: {query}
Dietary preference: {dietary}
Allergies to avoid: {', '.join(allergies) if allergies else 'None'}
"""
        response = ai_generate(prompt, RECIPE_SYSTEM)
        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 503

        recipes = parse_ai_json(response)
        if recipes:
            return jsonify({"recipes": recipes.get("recipes", [])})
        return jsonify({"recipes_text": response})

    except Exception as e:
        logger.error(f"Recipe suggestion error: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Feature: Food Comparison
# ---------------------------------------------------------------------------
COMPARE_SYSTEM = """Compare the nutritional value of two foods side by side.
Provide a clear winner and explain why.

RESPOND IN THIS EXACT JSON FORMAT:
{
  "food_a": {
    "name": "Food A",
    "calories": 250,
    "protein": 20,
    "carbs": 30,
    "fat": 8,
    "fiber": 5,
    "health_score": 7
  },
  "food_b": {
    "name": "Food B",
    "calories": 400,
    "protein": 10,
    "carbs": 55,
    "fat": 15,
    "fiber": 2,
    "health_score": 4
  },
  "winner": "Food A",
  "reason": "Lower calories, higher protein, more fiber",
  "verdict": "Choose Food A for a healthier option with better macro balance",
  "context_tips": ["Food B is okay as an occasional treat", "Consider portion size"]
}
"""


@app.route("/api/compare", methods=["POST"])
def compare_foods():
    """Compare two foods nutritionally using Gemini AI."""
    try:
        data = request.get_json()
        food_a = data.get("food_a", "").strip()
        food_b = data.get("food_b", "").strip()

        if not food_a or not food_b:
            return jsonify({"error": "Please provide two foods to compare"}), 400

        prompt = f"Compare these two foods: '{food_a}' vs '{food_b}'"
        response = ai_generate(prompt, COMPARE_SYSTEM)

        if isinstance(response, dict) and "error" in response:
            return jsonify(response), 503

        comparison = parse_ai_json(response)
        if comparison:
            return jsonify({"comparison": comparison})
        return jsonify({"comparison_text": response})

    except Exception as e:
        logger.error(f"Compare error: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Feature: BMI Calculator with Health Insights
# ---------------------------------------------------------------------------
@app.route("/api/bmi", methods=["POST"])
def calculate_bmi():
    """Calculate BMI and provide AI-powered health insights."""
    try:
        data = request.get_json()
        weight = float(data.get("weight", 0))
        height_cm = float(data.get("height", 0))

        if weight <= 0 or height_cm <= 0:
            return jsonify({"error": "Invalid weight or height"}), 400

        height_m = height_cm / 100
        bmi = round(weight / (height_m ** 2), 1)

        # BMI classification
        if bmi < 18.5:
            category = "Underweight"
            color = "#3b82f6"
            advice = "Consider nutrient-dense foods to reach a healthy weight."
        elif bmi < 25:
            category = "Normal"
            color = "#22c55e"
            advice = "Great! Maintain your healthy weight with balanced nutrition."
        elif bmi < 30:
            category = "Overweight"
            color = "#f59e0b"
            advice = "Small dietary changes and regular activity can help."
        else:
            category = "Obese"
            color = "#ef4444"
            advice = "Consider consulting a healthcare provider for guidance."

        # Healthy weight range
        healthy_min = round(18.5 * (height_m ** 2), 1)
        healthy_max = round(24.9 * (height_m ** 2), 1)

        return jsonify({
            "bmi": bmi,
            "category": category,
            "color": color,
            "advice": advice,
            "healthy_range": {"min": healthy_min, "max": healthy_max},
            "current_weight": weight,
        })

    except Exception as e:
        logger.error(f"BMI calc error: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Feature: Nutrition Knowledge Quiz
# ---------------------------------------------------------------------------
QUIZ_SYSTEM = """Generate a nutrition knowledge quiz question.

RESPOND IN THIS EXACT JSON FORMAT:
{
  "question": "Which food is highest in vitamin C?",
  "options": ["Orange", "Guava", "Apple", "Banana"],
  "correct_answer": 1,
  "explanation": "Guava contains about 228mg of vitamin C per 100g, which is more than 4 times that of an orange.",
  "fun_fact": "Bell peppers actually contain more vitamin C than oranges!",
  "difficulty": "medium",
  "category": "Vitamins"
}
"""


@app.route("/api/quiz", methods=["GET"])
def nutrition_quiz():
    """Generate a nutrition knowledge quiz question."""
    try:
        topics = [
            "vitamins and minerals", "macronutrients", "Indian superfoods",
            "hydration", "meal timing", "protein sources", "healthy fats",
            "fiber-rich foods", "antioxidants", "gut health"
        ]
        import random
        topic = random.choice(topics)

        prompt = f"Generate ONE nutrition quiz question about {topic}. Make it educational and fun."
        response = ai_generate(prompt, QUIZ_SYSTEM)

        if isinstance(response, dict) and "error" in response:
            # Fallback quiz question
            return jsonify({
                "question": "Which nutrient helps build and repair muscles?",
                "options": ["Carbohydrates", "Protein", "Vitamin C", "Fat"],
                "correct_answer": 1,
                "explanation": "Protein provides amino acids that are essential for building and repairing muscle tissue.",
                "fun_fact": "Your body needs about 0.8-1g of protein per kg of body weight daily!",
                "difficulty": "easy",
                "category": "Macronutrients",
            })

        quiz = parse_ai_json(response)
        if quiz:
            return jsonify(quiz)
        return jsonify({"question_text": response})

    except Exception as e:
        logger.error(f"Quiz error: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Feature: Health Insights Report
# ---------------------------------------------------------------------------
@app.route("/api/health-report", methods=["GET"])
def health_report():
    """Generate a comprehensive health insights report based on user data."""
    try:
        profile = get_user_profile()
        log = session.get("meal_log", [])
        water = session.get("water_today", 0)

        today = datetime.now().date().isoformat()
        today_meals = [m for m in log if m.get("time", "").startswith(today)]
        total_cal = sum(m.get("calories", 0) for m in today_meals)
        total_protein = sum(m.get("protein", 0) for m in today_meals)
        total_carbs = sum(m.get("carbs", 0) for m in today_meals)
        total_fat = sum(m.get("fat", 0) for m in today_meals)

        target_cal = profile.get("daily_calorie_target", 2000)
        macro_targets = profile.get("macro_targets", {"protein": 150, "carbs": 225, "fat": 56})

        # Calculate scores
        calorie_score = min(100, round(total_cal / target_cal * 100)) if target_cal else 0
        protein_score = min(100, round(total_protein / macro_targets.get("protein", 150) * 100)) if macro_targets.get("protein") else 0
        water_score = min(100, round(water / 8 * 100))
        meal_count_score = min(100, len(today_meals) * 25)  # Ideal: 4 meals

        overall_score = round((calorie_score + protein_score + water_score + meal_count_score) / 4)

        # Insights
        insights = []
        if calorie_score < 50:
            insights.append({"type": "warning", "message": f"You've only consumed {total_cal} of {target_cal} kcal today. Consider eating a balanced meal."})
        elif calorie_score > 100:
            insights.append({"type": "warning", "message": f"You've exceeded your calorie target by {total_cal - target_cal} kcal."})
        else:
            insights.append({"type": "success", "message": f"Great calorie management! {total_cal}/{target_cal} kcal."})

        if protein_score < 50:
            insights.append({"type": "tip", "message": "Try adding eggs, dal, or paneer to boost your protein intake."})

        if water < 4:
            insights.append({"type": "warning", "message": f"Drink more water! Only {water}/8 glasses today."})
        elif water >= 8:
            insights.append({"type": "success", "message": "Excellent hydration! You've hit your water goal. 💧"})

        if len(today_meals) < 3:
            insights.append({"type": "tip", "message": "Eating 4-5 smaller meals helps maintain energy levels throughout the day."})

        report = {
            "overall_score": overall_score,
            "scores": {
                "calories": calorie_score,
                "protein": protein_score,
                "hydration": water_score,
                "meal_frequency": meal_count_score,
            },
            "today_summary": {
                "calories": total_cal,
                "protein": total_protein,
                "carbs": total_carbs,
                "fat": total_fat,
                "meals": len(today_meals),
                "water": water,
            },
            "targets": {
                "calories": target_cal,
                "macro_targets": macro_targets,
                "water": 8,
            },
            "insights": insights,
            "generated_at": datetime.now().isoformat(),
        }

        return jsonify({"report": report})

    except Exception as e:
        logger.error(f"Health report error: {e}")
        return jsonify({"error": str(e)}), 500


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
