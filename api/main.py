"""
FastAPI REST API — HR Resume Shortlisting Agent

Endpoints:
  POST /api/analyze          — Full pipeline: upload JD + resumes → ranked shortlist
  POST /api/parse-jd         — Parse JD only
  POST /api/override          — Apply HR override to a candidate
  GET  /api/report/{job_id}  — Fetch JSON report for a job run
  GET  /api/health            — Health check
"""

import json
import logging
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import LLMConfig, EmbeddingConfig, LLMProvider, OUTPUT_DIR
from agent import ShortlistingAgent
from reports.generator import ReportGenerator

logger = logging.getLogger(__name__)

# ── FastAPI App ────────────────────────────────────────────────────────────
app = FastAPI(
    title="HR Resume Shortlisting Agent",
    description=(
        "AI-powered candidate evaluation system. "
        "Ingests JD + resumes → ranks candidates with transparent 5-dimension scoring."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory job store (for demo; use Redis/DB in production)
_jobs: dict[str, dict] = {}


# ── Pydantic Schemas ───────────────────────────────────────────────────────
class OverrideRequest(BaseModel):
    job_id: str
    candidate_name: str
    new_recommendation: str  # "hire" | "no-hire" | "maybe"
    reason: str
    hr_name: Optional[str] = "HR"
    dimension: Optional[str] = None
    new_score: Optional[float] = None


class AnalyzeRequest(BaseModel):
    """Used when calling the endpoint with JSON (not multipart)."""
    jd_text: str
    anthropic_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    provider: str = "claude"
    use_embeddings: bool = True


# ── Health Check ──────────────────────────────────────────────────────────
@app.get("/api/health", tags=["System"])
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "timestamp": time.time(),
        "llm_priority": ["Claude 3.5 Sonnet", "Gemini 2.0 Flash", "GPT-4o", "Heuristic"],
    }


# ── Full Pipeline ─────────────────────────────────────────────────────────
@app.post("/api/analyze", tags=["Pipeline"])
async def analyze(
    jd_text: str = Form(..., description="Job description text"),
    resumes: list[UploadFile] = File(default=[], description="Resume files (PDF/DOCX/TXT)"),
    linkedin_files: list[UploadFile] = File(default=[], description="LinkedIn JSON files"),
    anthropic_api_key: str = Form(default=""),
    gemini_api_key: str = Form(default=""),
    openai_api_key: str = Form(default=""),
    provider: str = Form(default="claude"),
    use_embeddings: bool = Form(default=False),
):
    """
    Full 7-step pipeline: upload JD + resumes → ranked shortlist JSON.

    Returns spec-compliant output for every candidate.
    """
    if not jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description is required.")
    if not resumes and not linkedin_files:
        raise HTTPException(status_code=400, detail="At least one resume or LinkedIn profile is required.")

    # Build LLM config from provided keys
    llm_config = _build_llm_config(provider, anthropic_api_key, gemini_api_key, openai_api_key)

    # Initialize agent
    agent = ShortlistingAgent(
        llm_config=llm_config,
        use_embeddings=use_embeddings,
    )

    try:
        # Parse JD (Step 2)
        agent.parse_job_description(jd_text)

        # Ingest resumes (Step 3)
        for upload in resumes:
            content = await upload.read()
            agent.ingest_resume_bytes(content, upload.filename or "resume")

        # Ingest LinkedIn (Step 3)
        for upload in linkedin_files:
            content = await upload.read()
            agent.ingest_linkedin_bytes(content, upload.filename or "linkedin.json")

        # Score (Step 4)
        agent.score_all_candidates()

        # Rank (Step 5)
        agent.rank_candidates()

        # Generate JSON report (Step 6)
        generator = ReportGenerator()
        stats = agent.get_summary_stats()
        json_path = generator.generate_json(agent.ranked, agent.job_requirements, stats, agent=agent)

        # Store job for override endpoint
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {"agent": agent, "stats": stats, "json_path": str(json_path)}

        return JSONResponse({
            "job_id": job_id,
            "status": "complete",
            "summary": stats,
            "candidates": agent.to_output_json(),
            "report_url": f"/api/report/{job_id}",
        })

    except Exception as e:
        logger.exception("Pipeline error")
        raise HTTPException(status_code=500, detail=str(e))


# ── Parse JD Only ─────────────────────────────────────────────────────────
@app.post("/api/parse-jd", tags=["Pipeline"])
async def parse_jd(
    jd_text: str = Form(...),
    anthropic_api_key: str = Form(default=""),
    gemini_api_key: str = Form(default=""),
    openai_api_key: str = Form(default=""),
    provider: str = Form(default="claude"),
):
    """Parse a job description and return structured requirements."""
    llm_config = _build_llm_config(provider, anthropic_api_key, gemini_api_key, openai_api_key)
    agent = ShortlistingAgent(llm_config=llm_config, use_embeddings=False)
    try:
        jd = agent.parse_job_description(jd_text)
        return {
            "title": jd.title,
            "required_skills": jd.required_skills,
            "preferred_skills": jd.preferred_skills,
            "min_years_experience": jd.min_years_experience,
            "seniority_level": jd.seniority_level,
            "min_education": jd.min_education,
            "key_responsibilities": jd.key_responsibilities,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Override ──────────────────────────────────────────────────────────────
@app.post("/api/override", tags=["Human-in-the-loop"])
async def apply_override(req: OverrideRequest):
    """
    Apply a human override to a candidate's recommendation.

    All overrides are logged with timestamp + reason in the audit trail.
    The agent NEVER makes final decisions — HR has final say.
    """
    job = _jobs.get(req.job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {req.job_id} not found.")

    agent: ShortlistingAgent = job["agent"]
    try:
        agent.override_candidate(
            candidate_name=req.candidate_name,
            recommendation=req.new_recommendation,
            reason=req.reason,
            hr_name=req.hr_name or "HR",
        )
        return {
            "status": "override_applied",
            "candidate": req.candidate_name,
            "new_recommendation": req.new_recommendation,
            "reason": req.reason,
            "updated_shortlist": agent.to_output_json(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Fetch Report ──────────────────────────────────────────────────────────
@app.get("/api/report/{job_id}", tags=["Reports"])
async def get_report(job_id: str):
    """Fetch the JSON report for a completed analysis job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    agent: ShortlistingAgent = job["agent"]
    return {
        "job_id": job_id,
        "summary": job["stats"],
        "candidates": agent.to_output_json(),
    }


@app.get("/api/report/{job_id}/pdf", tags=["Reports"])
async def download_pdf_report(job_id: str):
    """Download the PDF report for a completed analysis job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    agent: ShortlistingAgent = job["agent"]
    generator = ReportGenerator()
    pdf_path = generator.generate_pdf(agent.ranked, agent.job_requirements, job["stats"])
    return FileResponse(str(pdf_path), media_type="application/pdf", filename=pdf_path.name)


@app.get("/api/report/{job_id}/html", tags=["Reports"])
async def download_html_report(job_id: str):
    """Download the HTML report for a completed analysis job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    agent: ShortlistingAgent = job["agent"]
    generator = ReportGenerator()
    html_path = generator.generate_html(agent.ranked, agent.job_requirements, job["stats"])
    return FileResponse(str(html_path), media_type="text/html", filename=html_path.name)


# ── Helpers ───────────────────────────────────────────────────────────────
def _build_llm_config(provider: str, anthropic_key: str, gemini_key: str, openai_key: str) -> LLMConfig:
    """Build LLM config from API request parameters."""
    provider_map = {
        "claude": LLMProvider.CLAUDE,
        "gemini": LLMProvider.GEMINI,
        "openai": LLMProvider.OPENAI,
    }
    p = provider_map.get(provider.lower(), LLMProvider.CLAUDE)

    # Fall back to env vars if no key provided in request
    import os
    cfg = LLMConfig(
        provider=p,
        anthropic_api_key=anthropic_key or os.getenv("ANTHROPIC_API_KEY", ""),
        gemini_api_key=gemini_key or os.getenv("GEMINI_API_KEY", ""),
        openai_api_key=openai_key or os.getenv("OPENAI_API_KEY", ""),
    )
    # Auto-detect if specified provider has no key
    if not cfg.is_configured:
        cfg = LLMConfig.from_env()
    return cfg


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
