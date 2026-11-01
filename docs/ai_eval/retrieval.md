# Retrieval evaluation · 25 labeled queries · 83 chunks

Cutoff used by the app: cosine ≥ 0.35 (`tutor/knowledge.py`). TF-IDF scores are on a different scale, so the cutoff columns only apply to the embedding models.

| Retriever | Hit@1 | Hit@3 | MRR | Query time | Lowest gold score | Median gold score | Highest off-topic score | Gold ≥ cutoff | Off-topic ≥ cutoff (of 5) |
|---|---|---|---|---|---|---|---|---|---|
| TF-IDF (RAG notebook) | 68% | 92% | 0.81 | 0.2 ms | 0.04 | 0.21 | 0.18 | 0% | 0 |
| sentence-transformers/all-MiniLM-L6-v2 | 92% | 100% | 0.96 | 5.1 ms | 0.46 | 0.65 | 0.23 | 100% | 0 |
| BAAI/bge-base-en-v1.5 | 92% | 100% | 0.96 | 28.5 ms | 0.64 | 0.77 | 0.52 | 100% | 5 |
