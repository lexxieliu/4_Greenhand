# Greenhand 🌱

**Making Farming Accessible to Everyone**

Greenhand is a web application designed to help beginners grow plants with confidence. It combines AI-powered gardening guidance, plant tracking, and a community platform into one accessible space.

## Features

* 🤖 **AI Gardening Tutor**: get personalized answers to plant-care questions. It runs locally on open models and is grounded in Greenhand's plant-care guides (see [README_AI.md](README_AI.md)).
* 🌿 **Plant Database**: explore plant information, care guides, and suitability for your climate.
* 📸 **My Garden**: track plant growth through photos, notes, and lifecycle timelines.
* 📅 **Care Calendar**: record watering, germination, and other important events with reminders.
* 💬 **Community Posts**: share gardening experiences, ask questions, and learn from other growers.

## Setup

Requirements: **Python 3.12+**, about **8 GB free RAM** for the AI tutor, and about **7 GB of disk** for the model weights. The weights are downloaded once, outside the repo. Tested on macOS (Apple M4, MPS) with the versions pinned in `requirements.txt`. CUDA GPUs and CPU-only machines also work; CPU-only is slower.

```bash
git clone https://github.com/lexxieliu/4_Greenhand.git
cd 4_Greenhand

# 1. Create an environment (venv or conda) and install dependencies
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Settings: copy the example env file and set SECRET_KEY to any long random string
cp .env.example .env

# 3. Database: the SQLite file in data/ is committed; this only applies any missing migrations
python manage.py migrate
```

## Run the server

```bash
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. `manage.py` uses `greenhand.settings.development` by default, with DEBUG on and SQLite in `data/db.sqlite3`.

The garden, plant, weather and community pages run on mock data (`greenhand/mock_data.py`) for the user *Maya (balcony_maya, Chicago, zone 5b)*, so every page works without signing in.

## Use the AI feature

The AI Gardening Tutor is reachable from three places in the UI:

| Where | URL | What it does |
|---|---|---|
| **AI Tutor page** (sidebar → *Learn* → *AI Tutor*, or *Tutor* in the mobile bar) | `/tutor/` | Full form: question, optional plant scope, the answer with steps, the cited guides with similarity scores, safety warnings, and recent questions |
| **Dashboard chat** ("This week in your garden" card) | `/garden/` | Quick questions about the whole garden; the plant is detected from the question |
| **My Garden → a plant → "Ask about this plant"** | `/garden/my-garden/` | Drawer chat scoped to that plant (its stage, logs and problems) |

There is also a JSON endpoint, `POST /tutor/api/ask/`, with body `{"question": "...", "plant": "<garden id or empty>"}`.

Questions to try: *"Why are the lower leaves on my basil turning yellow?"*, *"How do I protect my tomato plant from the frost this week?"*, or, scoped to Butterhead Lettuce, *"Should I water today?"*.

## AI models: download notes

| Model | Role | Size | Source |
|---|---|---|---|
| `Qwen/Qwen2.5-3B-Instruct` | writes the answer | ~6 GB | Hugging Face, public (Apache-2.0); no token needed |
| `sentence-transformers/all-MiniLM-L6-v2` | embeds questions and guides for retrieval | ~90 MB | Hugging Face, public (Apache-2.0) |

* **No weights are in this repo.** `.gitignore` excludes `*.bin`, `*.safetensors`, `*.pt` and the cache folders. On first use, Hugging Face downloads the models to `~/.cache/huggingface/`.
* The first tutor question after starting the server loads the models, which takes about 10–30 s once downloaded. To download and load them ahead of a demo, run:
  ```bash
  python manage.py warmup_model
  ```
* Once downloaded, the app works offline. Set `HF_HUB_OFFLINE=1` to skip the Hub version check.
* To use another model, set `LOCAL_MODEL_ID` or `EMBEDDING_MODEL_ID` in `.env`. For example, `Qwen/Qwen2.5-1.5B-Instruct` is faster but less reliable; see README_AI.md.
* No paid API is used anywhere in the AI feature.

## Tests and evaluation

```bash
python manage.py test tutor                   # 30 unit tests; the models are mocked, so this takes ~1 s
python manage.py evaluate_tutor --label me    # runs the real models on 11 test cases -> docs/ai_eval/results_me.md
python manage.py evaluate_retrieval           # TF-IDF vs. embedding retrievers -> docs/ai_eval/retrieval.md
```

## Project structure

```
greenhand/            settings (base / development / production), urls, mock data, context processors
garden/ plants/ weather/ community/ post/ userprofile/   the app's Django apps
tutor/                AI Gardening Tutor (where AI enters the app)
  views.py            /tutor/ page + /tutor/api/ask/ JSON endpoint (thin views)
  services.py         ask_tutor(): guardrails -> context -> retrieval -> LLM -> validation -> log
  guardrails.py       input checks, rate limit, JSON/schema validation, safety warning
  context.py          the user's garden + weather context for the prompt
  knowledge.py        knowledge-base chunking, embeddings and semantic search
  knowledge_base/     curated plant-care guides (Markdown) the tutor retrieves from
  prompts.py          system prompt and worked examples
  llm.py              local Hugging Face model loading + generation (prefix cache, timeout)
  eval/               test cases and labeled retrieval queries
  management/commands/ warmup_model, evaluate_tutor, evaluate_retrieval
templates/ static/    UI (Tailwind); static/js/tutor_client.js connects the chat widgets to the tutor
docs/ai_eval/         evaluation reports (before / after the improvement, retrieval comparison)
```

## Team

Greenhand, Team 4. All team members are equal contributors.
