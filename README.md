# Greenhand 🌱

**Making Farming Accessible to Everyone**

Greenhand is a web application designed to help beginners grow plants with confidence. It combines AI-powered gardening guidance, plant tracking, and a community platform into one accessible space.

# Greenhand 🌱

### Making Farming Accessible to Everyone

Greenhand is a web application designed to help beginners grow plants with confidence. It combines AI-powered gardening guidance, plant tracking, and a community platform into one accessible space.

---

## 🎨 Design & Styling
- **Theme Color**: Uses natural green (`#4CAF50` & dark forest green header `#1E4D2B`) as the core theme color to complement plant care and nature.
- **Brand Icon**: Custom plant/leaf logo added to the top navigation header for brand identity.
- **Custom CSS**: Integrated via `static/style.css` for consistent table views, styled input forms, and navigation buttons.

---

## 🚀 Features

- 🤖 **AI Gardening Tutor** — Get personalized answers to plant-care questions.
- 🌿 **Plant Database & Navigation** — Explore plant information, search/filter by name and category, view detail pages via primary keys (`get_absolute_url()`), and analyze "Plants per Category" with server-side generated Matplotlib charts (`/plants/chart.png`).
- 📸 **My Garden** — Track plant growth through photos, notes, and lifecycle timelines.
- 📅 **Care Calendar** — Record watering, germination, and other important events with reminders.
- 💬 **Community Posts** — Share gardening experiences, ask questions, and learn from other growers.
- 📡 **JSON APIs** — Serve plant datasets via RESTful JSON endpoints (`/api/plants/` and `/api/plants_fbv/`) supporting dynamic query parameters for public access.

---

## 📡 API Reference

### Get Plant List (JSON API)
- **Endpoint**: `/api/plants_fbv/`
- **Method**: `GET`
- **Query Parameter**: `q` (optional, filter by plant name)
- **Example Request**: `http://127.0.0.1:8000/api/plants_fbv/?q=Cherry`
- **Response Format**:
  ```json
  {
    "count": 1,
    "result": [
      {
        "plant_id": 1,
        "plant_name": "Cherry Tomato",
        "category": "Fruit",
        "usage_type": "Edible"
      }
    ]
  }

## Goal

Greenhand aims to make urban and backyard farming accessible to everyone, regardless of gardening experience.

## Team

Greenhand — Team 4

All team members are equal contributors.

---

Developed by Team Greenhand 🌱
