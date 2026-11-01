import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from tutor.knowledge import MIN_SCORE, load_chunks

QUERIES = Path(__file__).resolve().parents[2] / "eval" / "retrieval_queries.json"
OUT = settings.BASE_DIR / "docs" / "ai_eval" / "retrieval.md"
EMBEDDERS = ["sentence-transformers/all-MiniLM-L6-v2", "BAAI/bge-base-en-v1.5"]


def tfidf_scorer(texts):
    """The retriever from the RAG notebook (2_rag_slm.ipynb): TF-IDF + cosine similarity."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform(texts)
    return lambda query: (matrix @ vectorizer.transform([query]).T).toarray().ravel()


def embedding_scorer(model_id, texts):
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_id, device="cpu")
    vectors = model.encode(texts, normalize_embeddings=True)
    return lambda query: vectors @ model.encode([query], normalize_embeddings=True)[0]


def evaluate(score, ids, queries, off_topic):
    hit1 = hit3 = reciprocal = 0.0
    gold_scores, start = [], time.perf_counter()
    for item in queries:
        scores = score(item["q"])
        ranking = [ids[i] for i in scores.argsort()[::-1]]
        rank = next(r for r, chunk_id in enumerate(ranking, start=1) if chunk_id in item["gold"])
        hit1 += rank == 1
        hit3 += rank <= 3
        reciprocal += 1 / rank
        gold_scores.append(max(scores[ids.index(g)] for g in item["gold"]))
    ms = (time.perf_counter() - start) * 1000 / len(queries)
    off_max = [float(score(q).max()) for q in off_topic]
    n = len(queries)
    return {"hit@1": hit1 / n, "hit@3": hit3 / n, "mrr": reciprocal / n, "ms": ms,
            "gold_min": min(gold_scores), "gold_median": sorted(gold_scores)[n // 2], "off_max": max(off_max),
            "gold_above_cutoff": sum(s >= MIN_SCORE for s in gold_scores) / n,
            "off_above_cutoff": sum(s >= MIN_SCORE for s in off_max)}


class Command(BaseCommand):
    help = "Compare retrievers (TF-IDF from the RAG notebook vs. sentence-transformers) on labeled queries."

    def handle(self, *args, **options):
        spec = json.loads(QUERIES.read_text(encoding="utf-8"))
        chunks = load_chunks()
        ids, texts = [c.id for c in chunks], [f"{c.title}. {c.text}" for c in chunks]
        scorers = {"TF-IDF (RAG notebook)": tfidf_scorer(texts)}
        scorers.update({model_id: embedding_scorer(model_id, texts) for model_id in EMBEDDERS})

        lines = [
            f"# Retrieval evaluation · {len(spec['queries'])} labeled queries · {len(chunks)} chunks", "",
            f"Cutoff used by the app: cosine ≥ {MIN_SCORE} (`tutor/knowledge.py`). TF-IDF scores are on a different scale, "
            "so the cutoff columns only apply to the embedding models.", "",
            "| Retriever | Hit@1 | Hit@3 | MRR | Query time | Lowest gold score | Median gold score | Highest off-topic score "
            f"| Gold ≥ cutoff | Off-topic ≥ cutoff (of {len(spec['off_topic'])}) |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for name, score in scorers.items():
            r = evaluate(score, ids, spec["queries"], spec["off_topic"])
            lines.append(f"| {name} | {r['hit@1']:.0%} | {r['hit@3']:.0%} | {r['mrr']:.2f} | {r['ms']:.1f} ms | {r['gold_min']:.2f} "
                         f"| {r['gold_median']:.2f} | {r['off_max']:.2f} | {r['gold_above_cutoff']:.0%} | {r['off_above_cutoff']} |")
            self.stdout.write(lines[-1])
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.stdout.write(f"Saved {OUT.relative_to(settings.BASE_DIR)}")
