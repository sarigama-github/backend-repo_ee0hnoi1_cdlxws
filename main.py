import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

from database import db, create_document
from schemas import Researchpaper

app = FastAPI(title="Research Improve API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Research Improvement Backend Running"}

class AnalyzeResponse(BaseModel):
    id: str
    recommendations: List[str]
    title: str

# Basic text extraction from uploaded file (txt/pdf/docx minimal)
import io

try:
    import pdfminer.high_level as pdf_high
    PDF_AVAILABLE = True
except Exception:
    PDF_AVAILABLE = False

try:
    import docx  # python-docx
    DOCX_AVAILABLE = True
except Exception:
    DOCX_AVAILABLE = False


def extract_text(file: UploadFile) -> str:
    content = file.file.read()
    # Reset for potential re-read
    file.file.seek(0)

    if file.filename.lower().endswith(".txt"):
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return content.decode("latin-1", errors="ignore")
    if file.filename.lower().endswith(".pdf") and PDF_AVAILABLE:
        try:
            with io.BytesIO(content) as f:
                return pdf_high.extract_text(f) or ""
        except Exception:
            return ""
    if file.filename.lower().endswith(".docx") and DOCX_AVAILABLE:
        try:
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception:
            return ""
    # Fallback: attempt decode as text
    try:
        return content.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def basic_analysis(text: str) -> dict:
    import re
    words = re.findall(r"\b\w+\b", text)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip()) if text.strip() else []
    sentence_count = len([s for s in sentences if s.strip()])
    word_count = len(words)
    avg_sentence_length = (word_count / sentence_count) if sentence_count else 0.0

    # Detect common academic sections
    section_patterns = [
        r"\babstract\b", r"\bintroduction\b", r"\bmethods?\b", r"\bmaterials?\b",
        r"\bresults?\b", r"\bdiscussion\b", r"\bconclusion\b", r"\breferences\b"
    ]
    lower = text.lower()
    sections = [s.strip('\\b') for s in ["abstract","introduction","methods","materials","results","discussion","conclusion","references"] if s in lower]

    # Very rough readability: average word length * avg sentence length
    avg_word_len = sum(len(w) for w in words) / word_count if word_count else 0
    readability = round(avg_word_len * (avg_sentence_length or 1), 2)

    recs: List[str] = []
    if not text.strip():
        recs.append("The file appears empty or unreadable. Upload a TXT, DOCX, or PDF.")
    if sentence_count and avg_sentence_length > 30:
        recs.append("Sentences are long on average. Consider splitting complex sentences.")
    if sentence_count and avg_sentence_length < 12:
        recs.append("Sentences are very short. Combine related ideas to improve flow.")
    if readability and readability > 140:
        recs.append("Language may be dense. Prefer simpler words where possible.")
    if "abstract" not in sections:
        recs.append("Add or refine an Abstract summarizing purpose, methods, results, and conclusions.")
    if "introduction" not in sections:
        recs.append("Ensure an Introduction with clear problem statement and contributions.")
    if not any(s in sections for s in ["methods","materials"]):
        recs.append("Include a Methods/Materials section detailing protocols and datasets.")
    if "results" not in sections:
        recs.append("Add a Results section with key findings and visuals.")
    if "discussion" not in sections:
        recs.append("Include a Discussion interpreting findings and limitations.")
    if "conclusion" not in sections:
        recs.append("Conclude with takeaways and future work.")
    if "references" not in sections:
        recs.append("Provide properly formatted References.")

    # Deduplicate
    recs = list(dict.fromkeys(recs))

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "avg_sentence_length": round(avg_sentence_length, 2),
        "sections": sections,
        "readability": readability,
        "recommendations": recs,
    }


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(file: UploadFile = File(...)):
    # Extract text
    text = extract_text(file)
    analysis = basic_analysis(text)

    # Title guess
    base_title = file.filename.rsplit(".", 1)[0] if file.filename else "Untitled Paper"

    # Save to DB
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    doc = Researchpaper(
        title=base_title,
        filename=file.filename,
        size_bytes=len(file.file.read()),
        word_count=analysis["word_count"],
        sentence_count=analysis["sentence_count"],
        avg_sentence_length=analysis["avg_sentence_length"],
        sections=analysis["sections"],
        readability=analysis["readability"],
        recommendations=analysis["recommendations"],
        status="analyzed",
    )

    # Reset pointer after read for size
    file.file.seek(0)

    inserted_id = create_document("researchpaper", doc)

    return AnalyzeResponse(
        id=inserted_id,
        recommendations=doc.recommendations,
        title=doc.title,
    )


@app.get("/api/papers")
async def list_papers(limit: int = 20):
    from database import get_documents
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    docs = get_documents("researchpaper", {}, limit)
    # Convert ObjectId if present
    for d in docs:
        if "_id" in d:
            d["id"] = str(d.pop("_id"))
    return {"items": docs}


@app.get("/test")
def test_database():
    from database import db as database_db
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if database_db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set"
            response["database_name"] = database_db.name
            response["connection_status"] = "Connected"
            try:
                collections = database_db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
