# Resume match

A Streamlit resume retrieval and RAG application with persistent Qdrant storage, numbered candidate rankings, and downloadable Excel details.

## Run on Windows

Python 3.11 or 3.12 is recommended. From this directory:

```powershell
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.txt --link-mode copy
.venv/Scripts/python.exe -m streamlit run app.py
```

Alternatively, create a virtual environment with Python and install `requirements.txt` using pip. Open http://localhost:8501. Dependencies are already installed in this workspace's `.venv`.

1. Upload multiple PDF, DOCX, or UTF-8 TXT resumes, then select **Store resumes**.
2. Paste a job description. Set the maximum result count (default **3**) and minimum similarity (default **0.65**). Only resumes passing the cutoff are returned, so you may receive fewer than three or no matches. This cutoff is a heuristic; tune it against reviewed examples. Matching uses semantic similarity and does not require exact wording.
3. Select **Rank candidates**, inspect source excerpts, and download the Excel workbook.

The first upload downloads `BAAI/bge-small-en-v1.5` into `data/models`; internet access is needed once. Subsequent embedding and search work locally. Scanned PDFs require external OCR. Duplicate extracted text is skipped, retaining the first uploaded filename. Different versions of a resume count as separate records; the app does not merge people by name or email.

## Qdrant configuration

Default: embedded Qdrant persists to `data/qdrant`, with no Docker or API key required. Run only one app process against this local directory.

To use Qdrant Cloud or a server, copy `.env.example` to `.env`, set `QDRANT_URL` and optionally `QDRANT_API_KEY`, then restart Streamlit. The app creates a dedicated 384-dimensional cosine collection automatically. Use Qdrant server for concurrent processes or larger datasets. Local and remote databases are separate; changing the connection does not migrate resumes.

Set `QDRANT_COLLECTION` in `.env` to choose a collection. The app requires unnamed **384-dimensional Cosine** vectors for its local BGE embedding model. An existing 1,536-dimensional collection is incompatible. Choose a new collection name (for example `resumes_bge_small_en_v15_384_v1`) and restart; the app creates it automatically. Existing collections are preserved, and resumes must be uploaded into the selected collection.

## Optional RAG generation

Ranking and export do not need an LLM. For generated candidate reviews, create a `.env` file using `.env.example` (or update your existing `.env`) and set:

```dotenv
OPENAI_API_KEY=your-api-key-here
OPENAI_MODEL=gpt-4.1-mini
```

Restart Streamlit after changing `.env`. Keep the real key in `.env`, which is excluded from git; never put it in `.env.example`. The selected model must be available to your OpenAI API project.

Expand a candidate and select **Generate evidence-based review**. The app sends the submitted job description and that candidate's three best retrieved chunks to OpenAI using the [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create). Requests set `store=False` and limit output to 2,000 tokens. Generated reviews incur API usage charges. Responses cite chunk labels and describe supported qualifications, missing evidence, and interview questions. Review model output against the excerpts; it may contain errors or omit qualifications outside retrieved chunks.

## Ranking and exported fields

Resumes are split into overlapping 120-word chunks with a 100-word stride. Long job descriptions are chunked and their query vectors averaged and normalized. Qdrant returns exact cosine scores for all stored chunks. Each resume is scored by the mean of its three best chunks (all chunks if fewer than three), sorted descending, and assigned consecutive ranks. Ties use a stable content hash. This simple baseline can favor longer resumes and is intended for small candidate pools; it is not a calibrated hiring score or an ATS compliance measure. Tokenizer limits may truncate unusually token-dense chunks.

The Excel export contains rank, candidate name suggestion, email, phone, LinkedIn, filename, numeric cosine score, retrieved evidence, and candidate ID, plus the submitted job description and methodology. Names and contact details use conservative heuristics; blank means not extracted. Phone parsing currently targets common North American formats. Verify extracted data against original resumes. Workbook inputs are written as literal strings to prevent formula injection. Large evidence cells wrap and can be expanded in Excel.

This is a local reviewer tool with one shared resume collection and no user authentication. Keep it on localhost; add authentication and isolated collections before multi-user hosting. Extracted resume text and contact details persist in Qdrant; original upload files are not saved. Ranking supports human review and does not make hiring decisions.

## Tests

```powershell
.venv/Scripts/python.exe -m pytest -q
```

Tests cover persistence, deduplication, rankings that change with the job, parsing, safe Excel cell types, Streamlit validation, and mocked OpenAI requests. Deterministic test embeddings and mocked API calls avoid downloads and API charges; live model and OpenAI checks are separate.

Implementation references: [Qdrant Python client](https://github.com/qdrant/qdrant-client), [FastEmbed](https://qdrant.github.io/fastembed/), [Streamlit](https://docs.streamlit.io/).
