"""Run the real embedding pipeline against synthetic resumes without saving them."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastembed import TextEmbedding
from resume_match import MODEL, connect, ingest, rank_candidates

model = TextEmbedding(model_name=MODEL, cache_dir="data/models", threads=2, local_files_only=True)
client = connect(path=":memory:")
samples = {
    "engineer.txt": "Alex Sample\nPython backend engineer with five years developing FastAPI services, PostgreSQL databases, Docker containers and automated software tests.",
    "sales.txt": "Jordan Sample\nSales manager with five years leading account executives, negotiating contracts, growing revenue and managing enterprise customer relationships.",
    "designer.txt": "Taylor Sample\nGraphic designer with five years creating brand identities, illustrations, typography and print layouts using Adobe Illustrator and Photoshop.",
}
for name, text in samples.items():
    ingest(client, model, name, text.encode())
rows = rank_candidates(client, model, "Python backend engineer with FastAPI, PostgreSQL and Docker experience", 3)
assert rows[0]["filename"] == "engineer.txt", rows
assert [row["rank"] for row in rows] == list(range(1, len(rows) + 1))
assert rank_candidates(client, model, "Civil engineer", 3) == []
assert rank_candidates(client, model, "Sales manager leading account executives and negotiating enterprise contracts", 3)[0]["filename"] == "sales.txt"
print("Real embedding smoke test passed: engineering and sales jobs select the expected synthetic candidates.")
client.close()
