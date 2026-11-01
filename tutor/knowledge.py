"""Retrieval over the curated plant-care knowledge base (PRD FR-34, flow 6.4 A step 3).

Knowledge base = the Markdown guides in tutor/knowledge_base/ (one chunk per "## " section), two
chunks per plant in the catalog (profile + common problems) and a month-by-month planting calendar
built from the catalog. 83 chunks of 60-150 words,
small enough to embed in memory at first use, so no vector database is needed yet (pgvector later).

Embeddings come from a local sentence-transformers model (settings.EMBEDDING_MODEL_ID,
default all-MiniLM-L6-v2, ~90 MB, downloaded automatically on first use). It is loaded lazily, so
Django start-up, migrations and tests never need it.

Public API:
    search(query, k=TOP_K, min_score=MIN_SCORE) -> list[Hit]     best first; [] if nothing is close
    load_chunks() -> list[Chunk]
"""
import calendar
import logging
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from greenhand import mock_data as data

logger = logging.getLogger(__name__)

KB_DIR = Path(__file__).resolve().parent / "knowledge_base"
TOP_K = 4
MIN_SCORE = 0.35     # cosine similarity; below this a chunk is treated as "not relevant" (see evaluate_retrieval)

_lock = threading.Lock()
_index = {}          # filled by _get_index(): chunks, vectors, model


@dataclass(frozen=True)
class Chunk:
    id: str
    title: str
    text: str


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def _markdown_chunks(path):
    """One chunk per '## ' section; the title is 'Document title › Section heading'."""
    content = path.read_text(encoding="utf-8")
    doc_title = re.search(r"^# (.+)$", content, re.MULTILINE).group(1).strip()
    sections = re.split(r"^## ", content, flags=re.MULTILINE)[1:]
    chunks = []
    for number, section in enumerate(sections, start=1):
        heading, _, body = section.partition("\n")
        chunks.append(Chunk(f"{path.stem}-{number}", f"{doc_title} › {heading.strip()}", " ".join(body.split())))
    return chunks


def _plant_chunks(plant):
    """Profile and common-problems chunks for one catalog plant (plants.Plant + PlantProblemSummary)."""
    name = plant["common_name"]
    months = ", ".join(calendar.month_name[m] for m in plant["planting_months"]) or "any month (indoors)"
    frost = ("tolerates light frost" if plant["frost_tolerant"]
             else f"is frost-tender and is damaged below about {data.FROST_THRESHOLD_C} °C")
    profile = (
        f"{name} ({plant['scientific_name']}) is a {plant['category'].replace('_', ' ')} rated {plant['difficulty']} "
        f"for beginners. {plant['description']} Light: {plant['sunlight_requirement'].replace('_', ' ')}. "
        f"Water about every {plant['watering_interval_days']} days. Grows between {plant['min_temp_c']} and "
        f"{plant['max_temp_c']} °C and {frost}. Seeds sprout in {plant['days_to_germination'][0]}–"
        f"{plant['days_to_germination'][1]} days; first harvest {plant['days_to_harvest'][0]}–"
        f"{plant['days_to_harvest'][1]} days after planting. Space plants {plant['spacing_cm']} cm apart. "
        f"{'Grows well in containers. ' if plant['container_friendly'] else ''}"
        f"{'Can be grown indoors. ' if plant['indoor_friendly'] else ''}"
        f"Plant outdoors in hardiness zone {data.LOCATION['hardiness_zone']} in: {months}. "
        f"Care tips: {'; '.join(plant['care'])}."
    )
    problems = " ".join(f"{p['name']}: {p['symptoms']}. Fix: {p['solution']}" for p in plant["problems"])
    return [
        Chunk(f"plant-{plant['slug']}", f"{name} › Growing guide", profile),
        Chunk(f"plant-{plant['slug']}-problems", f"{name} › Common problems",
              f"Common {name.lower()} problems reported by Greenhand growers. {problems}"),
    ]


def _planting_calendar_chunk():
    """One chunk listing what to plant in each month. Per-plant chunks cannot answer "what can I plant
    in October?" because the answer is spread over many plants (eval case T5)."""
    zone = data.LOCATION["hardiness_zone"]
    months = []
    for month in range(1, 13):
        names = [p["common_name"].lower() for p in data.CATALOG if month in p["planting_months"]]
        months.append(f"{calendar.month_name[month]}: {', '.join(names) if names else 'nothing outdoors'}.")
    indoor = [p["common_name"].lower() for p in data.CATALOG if not p["planting_months"]]
    return Chunk("planting-calendar", f"What to plant each month in zone {zone}",
                 f"Vegetables, herbs and fruit to plant or sow outdoors in hardiness zone {zone}, by month. "
                 f"{' '.join(months)} Any month indoors: {', '.join(indoor)}.")


def load_chunks():
    chunks = [c for path in sorted(KB_DIR.glob("*.md")) for c in _markdown_chunks(path)]
    return chunks + [c for plant in data.CATALOG for c in _plant_chunks(plant)] + [_planting_calendar_chunk()]


def _load_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s (first use downloads it)...", settings.EMBEDDING_MODEL_ID)
    return SentenceTransformer(settings.EMBEDDING_MODEL_ID, device="cpu")


def _encode(model, texts):
    return model.encode(texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)


def _get_index():
    """Load the model and embed every chunk once per process (safe to call from many threads)."""
    if not _index:
        with _lock:
            if not _index:
                model = _load_model()
                chunks = load_chunks()
                vectors = _encode(model, [f"{c.title}. {c.text}" for c in chunks])
                _index.update(model=model, chunks=chunks, vectors=vectors)
    return _index


def search(query, k=TOP_K, min_score=MIN_SCORE):
    """Top-k chunks by cosine similarity to the query, dropping anything below min_score."""
    index = _get_index()
    scores = index["vectors"] @ _encode(index["model"], [query])[0]
    best = scores.argsort()[::-1][:k]
    return [Hit(index["chunks"][i], round(float(scores[i]), 3)) for i in best if scores[i] >= min_score]
