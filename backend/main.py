# backend/main.py
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from scoring import compute_score
import pypdf
import io
import re

app = FastAPI()

# Allow CORS (for now open to all — lock later to your frontend domain)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Manual entry (numbers form) ----------
class StartupData(BaseModel):
    market: float
    business: float
    team: float
    traction: float
    risk: float

@app.post("/analyze")
def analyze_startup(data: StartupData):
    return compute_score(
        market=data.market,
        business=data.business,
        team=data.team,
        traction=data.traction,
        risk=data.risk,
    )

# ---------- PDF upload / analysis ----------
def extract_scores_from_text(text: str):
    """
    Simple heuristic extractor:
    - Looks around keywords for numbers 0..100.
    - If nothing found for a field, fallback to median-ish default (5).
    """
    text_lower = text.lower()
    # find all numbers in text as floats
    numbers = [float(x) for x in re.findall(r"\b(\d{1,3}(?:\.\d+)?)\b", text_lower)]
    # normalize percent-like numbers above 10 down to scale 0-10 if needed
    def normalize_val(v):
        if v > 10 and v <= 100:  # treat as percentage -> scale to 0-10
            return round(v / 10.0, 2)
        return round(v, 2)

    # helper: search for a numeric token near the keyword
    def find_near(keyword):
        idx = text_lower.find(keyword)
        if idx == -1:
            return None
        # take window around keyword
        window = text_lower[max(0, idx-100): idx+100]
        found = re.findall(r"\b(\d{1,3}(?:\.\d+)?)\b", window)
        if found:
            return normalize_val(float(found[0]))
        return None

    # try keywords
    market = find_near("market") or find_near("addressable") or None
    business = find_near("business") or find_near("model") or None
    team = find_near("team") or find_near("founder") or None
    traction = find_near("traction") or find_near("users") or find_near("growth") or None
    risk = find_near("risk") or find_near("challenge") or None

    # fallback: use some numbers found in doc
    fallback = [normalize_val(x) for x in numbers] if numbers else []
    def fallback_take(val):
        if val is not None:
            return val
        if fallback:
            # pick median-like value from doc numbers, scaled to 0-10 if necessary
            m = fallback[len(fallback)//2]
            return m if m <= 10 else round(m/10.0, 2)
        return 5.0

    market = fallback_take(market)
    business = fallback_take(business)
    team = fallback_take(team)
    traction = fallback_take(traction)
    risk = fallback_take(risk)
    # clamp to 0..10
    def clamp(v): return float(max(0.0, min(10.0, v)))
    return clamp(market), clamp(business), clamp(team), clamp(traction), clamp(risk)

@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    # Read PDF bytes
    data = await file.read()
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception as e:
        text = ""  # if PDF parsing fails, text will be empty

    # Extract scores heuristically
    market, business, team, traction, risk = extract_scores_from_text(text)

    # Compute final result using existing scoring logic
    result = compute_score(
        market=market,
        business=business,
        team=team,
        traction=traction,
        risk=risk,
    )

    return {
        "pdf_text_preview": text[:2000],   # short preview (first 2000 chars)
        "analysis": result
    }
