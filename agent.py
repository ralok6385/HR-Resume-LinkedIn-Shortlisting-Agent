"""
Agent Orchestrator — 7-step HR Shortlisting Pipeline.

LLM Priority: Claude 3.5 Sonnet → Gemini → GPT-4o → Heuristic
"""

import logging
import time
from pathlib import Path
from typing import Optional, Callable

from config import LLMConfig, EmbeddingConfig, LLMProvider, load_config
from parsers.jd_parser import JDParser, JobRequirements
from parsers.resume_parser import ResumeParser, CandidateProfile
from parsers.linkedin_parser import LinkedInParser
from engine.embeddings import EmbeddingEngine
from engine.scoring import ScoringEngine, CandidateScore
from engine.ranking import RankingEngine, RankedCandidate
from ingestion.document_loader import DocumentLoader
from ingestion.linkedin_ingestion import LinkedInIngestion
from security import AuditLogger, sanitize_input

logger = logging.getLogger(__name__)


def create_llm_client(config: LLMConfig) -> Optional[Callable]:
    """Return LLM callable or None (heuristic). Priority: Claude → Gemini → OpenAI."""
    if not config.is_configured:
        logger.warning("No API key — heuristic mode.")
        return None

    if config.provider == LLMProvider.CLAUDE:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.anthropic_api_key)
            def claude_call(prompt: str) -> str:
                msg = client.messages.create(
                    model=config.claude_model,
                    max_tokens=config.max_output_tokens,
                    temperature=config.temperature,
                    system="You are an expert HR analyst. Return only valid JSON when asked.",
                    messages=[{"role": "user", "content": prompt}],
                )
                return msg.content[0].text
            logger.info(f"Claude LLM ready: {config.claude_model}")
            return claude_call
        except Exception as e:
            logger.error(f"Claude init failed: {e}")

    elif config.provider == LLMProvider.GEMINI:
        try:
            import google.generativeai as genai
            genai.configure(api_key=config.gemini_api_key)
            model = genai.GenerativeModel(config.gemini_model,
                generation_config=genai.GenerationConfig(
                    temperature=config.temperature,
                    max_output_tokens=config.max_output_tokens))
            def gemini_call(prompt: str) -> str:
                return model.generate_content(prompt).text
            logger.info(f"Gemini LLM ready: {config.gemini_model}")
            return gemini_call
        except Exception as e:
            logger.error(f"Gemini init failed: {e}")

    elif config.provider == LLMProvider.OPENAI:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=config.openai_api_key)
            def openai_call(prompt: str) -> str:
                r = client.chat.completions.create(
                    model=config.openai_model,
                    messages=[
                        {"role": "system", "content": "You are an expert HR analyst. Return only valid JSON when asked."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=config.temperature, max_tokens=config.max_output_tokens)
                return r.choices[0].message.content
            logger.info(f"OpenAI LLM ready: {config.openai_model}")
            return openai_call
        except Exception as e:
            logger.error(f"OpenAI init failed: {e}")

    return None


class ShortlistingAgent:
    """
    Orchestrates all 7 steps of the HR shortlisting pipeline.

    Step 1 INPUT   — HR uploads JD + resumes/LinkedIn
    Step 2 PARSE   — LLM extracts structured JD requirements
    Step 3 PROFILE — Parse each resume/LinkedIn into structured fields
    Step 4 SCORE   — Compute rubric scores per candidate
    Step 5 RANK    — Sort by weighted total score (descending)
    Step 6 REPORT  — Generate PDF/HTML/JSON report
    Step 7 OVERRIDE— HR adjusts scores; agent logs with timestamp
    """

    def __init__(self, llm_config=None, embedding_config=None, use_embeddings=True):
        if llm_config is None:
            llm_config = LLMConfig.from_env()
        if embedding_config is None:
            embedding_config = EmbeddingConfig.from_env()

        self.llm_config = llm_config
        self.llm_client = create_llm_client(llm_config)

        self.doc_loader = DocumentLoader()
        self.linkedin_ingestion = LinkedInIngestion()

        self.jd_parser = JDParser(llm_client=self.llm_client)
        self.resume_parser = ResumeParser(llm_client=self.llm_client)
        self.linkedin_parser = LinkedInParser(llm_client=self.llm_client)

        self.use_embeddings = use_embeddings
        self._embedding_engine = None
        self.embedding_config = embedding_config

        self.scoring_engine = ScoringEngine(llm_client=self.llm_client, embedding_engine=None)
        self.ranking_engine = RankingEngine()
        self.audit = AuditLogger()

        self.job_requirements: Optional[JobRequirements] = None
        self.candidates: list[CandidateProfile] = []
        self.scores: list[CandidateScore] = []
        self.ranked: list[RankedCandidate] = []

        logger.info(f"Agent ready — {llm_config.display_name}")

    @property
    def embedding_engine(self):
        if not self.use_embeddings:
            return None
        if self._embedding_engine is None:
            try:
                self._embedding_engine = EmbeddingEngine(self.embedding_config.model_name)
                self.scoring_engine.embedding_engine = self._embedding_engine
            except Exception as e:
                logger.error(f"Embedding engine failed: {e}")
                self.use_embeddings = False
        return self._embedding_engine

    # ── Step 2: Parse JD ─────────────────────────────────────────────────
    def parse_job_description(self, jd_text: str) -> JobRequirements:
        logger.info("Step 2: Parsing JD...")
        t = time.time()
        jd_text = sanitize_input(jd_text)
        self.job_requirements = self.jd_parser.parse(jd_text)
        self.audit.log("parse_jd", {"title": self.job_requirements.title, "duration_s": round(time.time()-t,2)})
        return self.job_requirements

    # ── Step 3: Profile — Resumes ─────────────────────────────────────────
    def ingest_resume_file(self, file_path) -> CandidateProfile:
        doc = self.doc_loader.load_file(file_path)
        return self._profile_doc(doc)

    def ingest_resume_bytes(self, content: bytes, filename: str) -> CandidateProfile:
        doc = self.doc_loader.load_bytes(content, filename)
        return self._profile_doc(doc)

    def parse_resume(self, file_path, raw_text=None) -> CandidateProfile:
        """Backward-compat wrapper."""
        if raw_text:
            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
            tmp.write(raw_text.encode()); tmp.close()
            doc = self.doc_loader.load_file(tmp.name)
            doc["name"] = Path(file_path).name
        else:
            doc = self.doc_loader.load_file(file_path)
        return self._profile_doc(doc)

    def _profile_doc(self, doc: dict) -> CandidateProfile:
        if doc.get("error"):
            raise ValueError(f"Load error: {doc['error']}")
        t = time.time()
        profile = self.resume_parser.parse(doc["path"], raw_text=doc["text"])
        self.candidates.append(profile)
        self.audit.log("parse_resume", {"file": doc["name"], "candidate": profile.name, "duration_s": round(time.time()-t,2)})
        return profile

    # ── Step 3: Profile — LinkedIn ────────────────────────────────────────
    def ingest_linkedin_file(self, file_path) -> CandidateProfile:
        normalized = self.linkedin_ingestion.load_file(file_path)
        return self._profile_linkedin(normalized)

    def ingest_linkedin_bytes(self, content: bytes, filename: str) -> CandidateProfile:
        normalized = self.linkedin_ingestion.load_bytes(content, filename)
        return self._profile_linkedin(normalized)

    def ingest_linkedin_dict(self, data: dict) -> CandidateProfile:
        normalized = self.linkedin_ingestion.load_dict(data)
        return self._profile_linkedin(normalized)

    def parse_linkedin(self, data) -> CandidateProfile:
        """Backward-compat wrapper."""
        return self.ingest_linkedin_dict(data) if isinstance(data, dict) else self.ingest_linkedin_file(data)

    def _profile_linkedin(self, normalized: dict) -> CandidateProfile:
        t = time.time()
        profile = self.linkedin_parser.parse(normalized)
        self.candidates.append(profile)
        self.audit.log("parse_linkedin", {"candidate": profile.name, "duration_s": round(time.time()-t,2)})
        return profile

    # ── Step 4: Score ─────────────────────────────────────────────────────
    def score_all_candidates(self, progress_callback=None) -> list[CandidateScore]:
        if not self.job_requirements:
            raise ValueError("Parse JD first.")
        if not self.candidates:
            raise ValueError("Ingest resumes first.")
        _ = self.embedding_engine  # trigger init
        logger.info(f"Step 4: Scoring {len(self.candidates)} candidates...")
        self.scores = []
        for i, candidate in enumerate(self.candidates):
            if progress_callback:
                progress_callback(i, len(self.candidates), candidate.name)
            t = time.time()
            score = self.scoring_engine.score_candidate(self.job_requirements, candidate)
            self.scores.append(score)
            self.audit.log("score_candidate", {"candidate": candidate.name, "score": score.total_weighted_score, "rec": score.recommendation, "duration_s": round(time.time()-t,2)})
        return self.scores

    # ── Step 5: Rank ─────────────────────────────────────────────────────
    def rank_candidates(self) -> list[RankedCandidate]:
        if not self.scores:
            raise ValueError("Score candidates first.")
        logger.info("Step 5: Ranking...")
        self.ranked = self.ranking_engine.rank(self.scores)
        self.audit.log("rank_candidates", {"total": len(self.ranked), "top": self.ranked[0].name if self.ranked else "N/A"})
        return self.ranked

    # ── Step 7: Override ──────────────────────────────────────────────────
    def override_candidate(self, candidate_name: str, recommendation: str, reason: str, hr_name: str = "HR"):
        """Human-in-the-loop override. Always logged with timestamp + reason."""
        if not reason.strip():
            raise ValueError("Override reason is mandatory.")
        self.ranked = self.ranking_engine.apply_override(self.ranked, candidate_name, recommendation, reason)
        self.audit.log("human_override", {"hr": hr_name, "candidate": candidate_name, "new_rec": recommendation, "reason": reason})

    def get_summary_stats(self) -> dict:
        return self.ranking_engine.generate_summary_stats(self.ranked)

    def to_output_json(self) -> list[dict]:
        """Return mandatory spec-compliant output format."""
        output = []
        for rc in self.ranked:
            s = rc.score
            dim_map = {d.dimension: d for d in s.dimension_scores}
            def get_dim(name):
                d = dim_map.get(name)
                return {"score": d.score, "justification": d.justification} if d else {"score": 0, "justification": "N/A"}
            override_log = []
            if s.is_overridden:
                override_log.append({"reason": s.override_reason, "new_recommendation": s.override_recommendation})
            output.append({
                "candidate_name": s.candidate_name,
                "rank": rc.rank,
                "scores": {
                    "skills_match": get_dim("Skills Match"),
                    "experience_relevance": get_dim("Experience Relevance"),
                    "education_certs": get_dim("Education & Certifications"),
                    "project_portfolio": get_dim("Project / Portfolio"),
                    "communication_quality": get_dim("Communication Quality"),
                },
                "weighted_total": round(s.total_weighted_score * 10, 1),
                "recommendation": s.recommendation.lower().replace(" ", "-"),
                "override_log": override_log,
            })
        return output

    def run_full_pipeline(self, jd_text, resume_files, linkedin_files=None, progress_callback=None):
        """Run all 7 steps end-to-end."""
        if progress_callback: progress_callback(0, 10, "Step 2: Parsing JD...")
        self.parse_job_description(jd_text)
        for i, rf in enumerate(resume_files):
            if progress_callback: progress_callback(1+i, 10, f"Step 3: {Path(rf).name}")
            self.ingest_resume_file(rf)
        for lf in (linkedin_files or []):
            self.ingest_linkedin_file(lf)
        if progress_callback: progress_callback(7, 10, "Step 4: Scoring...")
        self.score_all_candidates()
        if progress_callback: progress_callback(9, 10, "Step 5: Ranking...")
        self.rank_candidates()
        self.audit.save()
        if progress_callback: progress_callback(10, 10, "Complete!")
        return self.ranked

    def reset(self):
        self.job_requirements = None
        self.candidates = []
        self.scores = []
        self.ranked = []
        self.audit = AuditLogger()
