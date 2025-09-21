# backend/main.py

import os
import re
import io
import pypdf
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.scoring import compute_score

# Create FastAPI app
app = FastAPI()

# -------- Secure CORS (only allow your frontend) --------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-analyst-startup-frontend.onrender.com"],  # only your frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------- API Key protection --------
API_KEY = os.getenv("API_KEY", None)

@app.middleware("http")
async def check_api_key(request: Request, call_next):
    if request.method == "OPTIONS":  # allow preflight
        return await call_next(request)

    if API_KEY:  # only check if API_KEY is set
        key = request.headers.get("x-api-key")
        if key != API_KEY:
            raise HTTPException(status_code=403, detail="Forbidden")

    return await call_next(request)

# -------- Health check --------
@app.get("/")
def home():
    return {"message": "Backend is working ✅"}

# -------- Manual entry (numbers form) --------
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

# -------- PDF upload / analysis --------
def extract_scores_from_text(text: str):
    text_lower = text.lower()
    numbers = [float(x) for x in re.findall(r"\b(\d{1,3}(?:\.\d+)?)\b", text_lower)]

    def normalize_val(v):
        if v > 10 and v <= 100:
            return round(v / 10.0, 2)
        return round(v, 2)

    def find_near(keyword):
        idx = text_lower.find(keyword)
        if idx == -1:
            return None
        window = text_lower[max(0, idx-100): idx+100]
        found = re.findall(r"\b(\d{1,3}(?:\.\d+)?)\b", window)
        if found:
            return normalize_val(float(found[0]))
        return None

    market = find_near("market") or find_near("addressable") or None
    business = find_near("business") or find_near("model") or None
    team = find_near("team") or find_near("founder") or None
    traction = find_near("traction") or find_near("users") or find_near("growth") or None
    risk = find_near("risk") or find_near("challenge") or None

    fallback = [normalize_val(x) for x in numbers] if numbers else []
    def fallback_take(val):
        if val is not None:
            return val
        if fallback:
            m = fallback[len(fallback)//2]
            return m if m <= 10 else round(m/10.0, 2)
        return 5.0

    market = fallback_take(market)
    business = fallback_take(business)
    team = fallback_take(team)
    traction = fallback_take(traction)
    risk = fallback_take(risk)

    def clamp(v): return float(max(0.0, min(10.0, v)))
    return clamp(market), clamp(business), clamp(team), clamp(traction), clamp(risk)

@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...)):
    data = await file.read()
    try:
        reader = pypdf.PdfReader(io.BytesIO(data))
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    except Exception:
        text = ""

    market, business, team, traction, risk = extract_scores_from_text(text)

    result = compute_score(
        market=market,
        business=business,
        team=team,
        traction=traction,
        risk=risk,
    )

    return {
        "pdf_text_preview": text[:2000],
        "analysis": result
    }
