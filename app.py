import os

import streamlit as st
from dotenv import load_dotenv
from openai import APIConnectionError, AuthenticationError, RateLimitError

from resume_match import COLLECTION, MODEL, connect, export_excel, generate_review, ingest, rank_candidates

load_dotenv()
collection_name = os.getenv("QDRANT_COLLECTION", COLLECTION).strip() or COLLECTION
st.set_page_config(page_title="Resume match", page_icon=":material/person_search:", layout="wide")


@st.cache_resource(max_entries=1)
def database():
    return connect(os.getenv("QDRANT_URL", ""), os.getenv("QDRANT_API_KEY", ""), os.getenv("QDRANT_PATH", "data/qdrant"), collection=collection_name)


@st.cache_resource(max_entries=1)
def embeddings():
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=MODEL, cache_dir="data/models", threads=2)


for key, default in {"results": [], "result_job": "", "reviews": {}, "excel": None}.items():
    st.session_state.setdefault(key, default)

st.title("Resume match")
st.write("Find relevant experience. Review the evidence. Export your shortlist.")
with st.sidebar:
    st.subheader("Your workspace")
    st.caption("Qdrant server" if os.getenv("QDRANT_URL") else "Persistent local Qdrant")
    st.caption(f"Collection: {collection_name}")
    st.write("1. Add resumes\n2. Paste the job description\n3. Review and download")
    st.divider()
    st.caption("Embeddings run locally. The first upload downloads the embedding model. Configure a server connection in .env and restart the app.")
    st.caption("Optional generated reviews use OpenAI. Configure OPENAI_API_KEY and OPENAI_MODEL in .env.")

upload_col, match_col = st.columns([1, 1.35], gap="large")
with upload_col, st.container(border=True):
    st.subheader("1. Add resumes")
    files = st.file_uploader("Upload multiple resumes", type=["pdf", "docx", "txt"], accept_multiple_files=True)
    st.caption("Up to 30 files per batch, 5 MB each. Text-based PDFs, Word documents, and UTF-8 text.")
    if st.button("Store resumes", type="primary", icon=":material/upload_file:", disabled=not files):
        if len(files) > 30:
            st.error("Select at most 30 resumes per batch.")
        else:
            try:
                with st.spinner("Preparing Qdrant and the embedding model…"):
                    client, model = database(), embeddings()
                added = skipped = 0
                progress = st.progress(0)
                for i, file in enumerate(files):
                    try:
                        if ingest(client, model, file.name, file.getvalue(), collection=collection_name):
                            added += 1
                        else:
                            skipped += 1
                    except ValueError as exc:
                        st.error(f"{file.name}: {exc}")
                    except Exception:
                        st.error(f"Could not process {file.name}. Check the file format and database connection.")
                    progress.progress((i + 1) / len(files))
                st.success(f"Stored {added} resumes. Skipped {skipped} duplicates.")
                if added:
                    st.session_state.update(results=[], reviews={}, excel=None)
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Could not initialize storage or embeddings. Check Qdrant settings and internet access for the first model download.")

with match_col, st.container(border=True):
    st.subheader("2. Match a job")
    with st.form("match"):
        job = st.text_area("Job description", height=230, max_chars=20_000,
                           placeholder="Paste the responsibilities, skills, and experience required for this role.")
        top_k = st.number_input("Maximum candidates to return", min_value=1, max_value=100, value=3)
        min_similarity = st.slider("Minimum similarity", min_value=0.0, max_value=1.0, value=0.65, step=0.01,
                                   help="Exclude weaker semantic matches. 0.65 is a starting point, not a validated qualification threshold.")
        submitted = st.form_submit_button("Rank candidates", type="primary", icon=":material/person_search:")
    if submitted:
        st.session_state.update(results=[], reviews={}, excel=None)
        if not job.strip():
            st.error("Enter a job description before ranking candidates.")
        else:
            try:
                with st.spinner("Matching stored resumes to the job description…"):
                    client = database()
                    stored_chunks = client.count(collection_name, exact=True).count
                    rows = rank_candidates(client, embeddings(), job, int(top_k), collection=collection_name,
                                           min_similarity=min_similarity) if stored_chunks else []
                    st.session_state.update(results=rows, result_job=job,
                                            excel=export_excel(rows, job, min_similarity) if rows else None)
                if not rows:
                    st.info("No resumes met the minimum similarity. Try a more detailed job description or adjust the similarity cutoff." if stored_chunks else "No resumes stored yet. Upload and store resumes first.")
                elif len(rows) < top_k:
                    st.info(f"{len(rows)} candidate(s) passed the filters. No additional candidates were added to fill the requested maximum.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception:
                st.error("Matching failed. Check the Qdrant connection and embedding model availability, then retry.")

if st.session_state.results:
    st.subheader("3. Review your shortlist")
    st.caption("Results use the last submitted job description. Submit again after edits. Similarity is a retrieval score, not a qualification percentage. Review candidates before making hiring decisions.")
    rows = st.session_state.results
    st.dataframe([{"Rank": r["rank"], "Candidate (verify)": r["name"] or "Not extracted",
                   "Email": r["email"], "Phone": r["phone"], "Resume": r["filename"],
                   "Similarity": round(r["score"], 4)} for r in rows], hide_index=True,
                 column_config={"Similarity": st.column_config.NumberColumn(format="%.4f")})
    st.download_button("Download candidate details (.xlsx)", data=st.session_state.excel,
                       file_name="candidate_ranking.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       icon=":material/download:")
    with st.expander("How ranking works"):
        st.write("Each resume is split into overlapping chunks and stored as vectors in Qdrant. The job description is embedded with the same model. Candidates are ranked by the mean cosine similarity of their best three chunks, or all available chunks when fewer than three exist. Ties use a stable candidate ID. Longer resumes can have an advantage. Names and contact information are extracted heuristically; verify them against the original.")
        st.text(st.session_state.result_job)
    for row in rows:
        with st.expander(f"#{row['rank']} · {row['name'] or row['filename']} · {row['score']:.4f}"):
            st.text(row["evidence"])
            st.caption("Generating a review sends the job description and these resume excerpts to OpenAI. The review can miss information elsewhere in the resume.")
            if st.button("Generate evidence-based review", key=f"review_{row['candidate_id']}"):
                try:
                    with st.spinner("Generating review…"):
                        st.session_state.reviews[row["candidate_id"]] = generate_review(
                            st.session_state.result_job, row, os.getenv("OPENAI_API_KEY", ""), os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
                except ValueError as exc:
                    st.error(str(exc))
                except AuthenticationError:
                    st.error("OpenAI rejected the API key. Check OPENAI_API_KEY in .env and restart the app.")
                except RateLimitError:
                    st.error("OpenAI quota or rate limit reached. Check your API billing and limits, then retry.")
                except APIConnectionError:
                    st.error("Could not connect to OpenAI. Check your internet connection and retry.")
                except Exception:
                    st.error("OpenAI review failed. Check OPENAI_MODEL and your project's model access, then retry.")
            if row["candidate_id"] in st.session_state.reviews:
                st.text(st.session_state.reviews[row["candidate_id"]])
