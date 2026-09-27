# Greenhand 🌱

**Making Farming Accessible to Everyone**

Greenhand is a web application designed to help beginners grow plants with confidence. It combines AI-powered gardening guidance, plant tracking, and a community platform into one accessible space.

## Features

* 🤖 **AI Gardening Tutor** — Get personalized answers to plant-care questions.
* 🌿 **Plant Database** — Explore plant information, care guides, and AI-generated recommendations.
* 📸 **My Garden** — Track plant growth through photos, notes, and lifecycle timelines.
* 📅 **Care Calendar** — Record watering, germination, and other important events with reminders.
* 💬 **Community Posts** — Share gardening experiences, ask questions, and learn from other growers.


GreenHand  Project Notes P1-A3: User Input, Analysis, & APIs
------------------------------------------------------------------------
Section 1: URL Linking & Navigation
------------------------------------------------------------------------
Question: For which feature you've implemented get_absolute_url() is useful?

Answer:
We implemented `get_absolute_url()` inside the `Plant` model (returning `/plants/<pk>`). 
This method is particularly useful for the Plant List page where each plant item in the `{% for %}` loop links to its corresponding Detail page. Instead of hard-coding URL string concatenations (e.g., '/plants/' + plant.id) or repeating `{% url 'plants_detail' plant.pk %}` across multiple templates, using `plant.get_absolute_url` enforces DRY (Don't Repeat Yourself) principles. If the URL structure changes in `urls.py` in the future, all template links update automatically without modifying individual HTML files.


------------------------------------------------------------------------
Section 3: Static Files & UI Styling
------------------------------------------------------------------------
Question: Static file organization choice?

Answer:
We chose a central project-level `static/` directory setup (configured via `STATICFILES_DIRS = [BASE_DIR / 'static']` in `settings.py`). 
This approach is preferred for our project because global design elements—such as our natural green theme palette (`#4CAF50` and `#1E4D2B`), site-wide custom CSS (`style.css`), and the main brand logo icon—are shared across multiple app templates (plants, posts, profile). A central folder keeps all design assets consolidated and easier to manage.

(Bonus) Cache Busting Explanation:
Browsers often cache static CSS files locally to speed up page loads, which can prevent newly updated CSS rules from showing immediately. "Cache busting" solves this by appending a unique query parameter or version hash to the static URL (e.g., `{% static 'style.css' %}?v=1.1` or using automated manifest storage). When the URL changes, the browser is forced to bypass its cache and download the updated stylesheet immediately.

------------------------------------------------------------------------
Section 6: Creating APIs
------------------------------------------------------------------------
Question 1: How you are planning on creating an API for your project?

Answer:
We created our API using Django's views and routing system by returning JSON responses instead of rendering HTML templates.
1. FBV API (`plant_api`): Uses Django's native `JsonResponse` to return serialized dictionary data. It parses HTTP GET parameters (`request.GET.get('q')`) to allow public search and filtering.
2. CBV API (`PlantsAPIView`): Extends `django.views.View` and demonstrates returning serialized JSON strings using `HttpResponse(json.dumps(...), content_type="application/json")` to highlight the Content-Type header difference.

Question 2: What kind of data are you planning to serve?

Answer:
We serve plant catalog data stored in our database model. The API exposes key attributes including `plant_id`, `plant_name`, `scientific_name`, `category`, and `usage_type`. This dataset allows external applications or frontend consumers to query, search, and filter our plant collection programmatically.

## Goal

Greenhand aims to make urban and backyard farming accessible to everyone, regardless of gardening experience.

## Team

Greenhand — Team 4

All team members are equal contributors.

---

Developed by Team Greenhand 🌱
