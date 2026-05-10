"""
Scoring Engine — Produces structured scores across 5 mandatory dimensions.

Uses LLM reasoning combined with embedding-based semantic matching to produce
fair, consistent, and explainable scores for each candidate.

Scoring Rubric (Mandatory Output Format):
| Dimension            | Weight | 0=Poor              | 5=Average           | 10=Excellent          |
|----------------------|--------|----------------------|---------------------|-----------------------|
| Skills Match         | 30%    | <30% skills match    | 50-70% match        | >85% match            |
| Experience Relevance | 25%    | Unrelated domain     | Adjacent domain     | Exact domain+seniority|
| Education & Certs    | 15%    | Doesn't meet minimum | Meets minimum       | Exceeds + extra certs |
| Project / Portfolio  | 20%    | No evidence          | 1-2 generic projects| Strong relevant portfolio|
| Communication Quality| 10%    | Poor structure       | Adequate clarity    | Crisp, impactful      |
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from config import SCORING_RUBRIC, ScoringDimension
from parsers.jd_parser import JobRequirements
from parsers.resume_parser import CandidateProfile

logger = logging.getLogger(__name__)


@dataclass
class DimensionScore:
    """Score for a single rubric dimension."""
    dimension: str
    weight: float
    score: float           # 0-10
    weighted_score: float  # score * weight
    justification: str     # One-line justification (mandatory)
    confidence: float = 0.0  # 0-1, how confident the scoring is


@dataclass
class CandidateScore:
    """Complete scoring result for a single candidate."""
    candidate_name: str
    candidate_file: str
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    total_weighted_score: float = 0.0
    max_possible_score: float = 10.0
    recommendation: str = ""  # "Hire", "Maybe", "No Hire"
    overall_summary: str = ""
    semantic_similarity: float = 0.0  # Embedding-based similarity
    
    # Human override
    is_overridden: bool = False
    override_reason: str = ""
    override_recommendation: str = ""

    def compute_total(self):
        """Recalculate total weighted score from dimension scores."""
        self.total_weighted_score = round(
            sum(d.weighted_score for d in self.dimension_scores), 2
        )
        # Auto-recommend based on score
        if self.total_weighted_score >= 7.5:
            self.recommendation = "Strong Hire"
        elif self.total_weighted_score >= 6.0:
            self.recommendation = "Hire"
        elif self.total_weighted_score >= 4.5:
            self.recommendation = "Maybe"
        else:
            self.recommendation = "No Hire"

    def to_dict(self) -> dict:
        """Convert to dictionary for reporting."""
        return {
            "candidate_name": self.candidate_name,
            "candidate_file": self.candidate_file,
            "total_weighted_score": self.total_weighted_score,
            "max_possible_score": self.max_possible_score,
            "recommendation": self.recommendation,
            "overall_summary": self.overall_summary,
            "semantic_similarity": self.semantic_similarity,
            "dimension_scores": [
                {
                    "dimension": d.dimension,
                    "weight": d.weight,
                    "score": d.score,
                    "weighted_score": d.weighted_score,
                    "justification": d.justification,
                    "confidence": d.confidence,
                }
                for d in self.dimension_scores
            ],
            "is_overridden": self.is_overridden,
            "override_reason": self.override_reason,
            "override_recommendation": self.override_recommendation,
        }


# ============================================================
# LLM Scoring Prompt
# ============================================================

SCORING_PROMPT = """You are an expert HR evaluator. Score the following candidate against the job requirements using the mandatory rubric below.

## JOB REQUIREMENTS:
Title: {jd_title}
Required Skills: {jd_skills}
Experience: {jd_experience} years in {jd_domains}
Seniority Level: {jd_seniority}
Education: {jd_education}
Key Responsibilities: {jd_responsibilities}
Project Expectations: {jd_projects}

## CANDIDATE PROFILE:
Name: {cand_name}
Current Role: {cand_title} at {cand_company}
Total Experience: {cand_experience} years
Skills: {cand_skills}
Domains: {cand_domains}
Education: {cand_education}
Certifications: {cand_certs}
Projects: {cand_projects}
Work History: {cand_work}

## ADDITIONAL CONTEXT:
Semantic Skills Match Score (from embeddings): {semantic_skills_match}
Matched Skills: {matched_skills}
Unmatched Skills: {unmatched_skills}
Overall Profile Similarity: {profile_similarity}

## SCORING RUBRIC:
Score each dimension from 0 to 10 using these criteria:

1. **Skills Match** (Weight: 30%)
   - 0 = Less than 30% of required skills present
   - 5 = 50-70% of required skills present
   - 10 = More than 85% of required skills present

2. **Experience Relevance** (Weight: 25%)
   - 0 = Unrelated domain, no relevant experience
   - 5 = Adjacent domain, some transferable experience
   - 10 = Exact domain match with matching seniority

3. **Education & Certifications** (Weight: 15%)
   - 0 = Does not meet minimum educational requirements
   - 5 = Meets minimum requirements
   - 10 = Exceeds requirements with relevant certifications

4. **Project / Portfolio** (Weight: 20%)
   - 0 = No evidence of relevant projects
   - 5 = 1-2 generic projects
   - 10 = Strong portfolio with relevant, impactful projects

5. **Communication Quality** (Weight: 10%)
   - 0 = Poor structure, grammar issues
   - 5 = Adequate clarity
   - 10 = Crisp, well-structured, impactful writing

## INSTRUCTIONS:
- Be fair and consistent. Use the semantic match data to inform your Skills Match score.
- Provide a one-line justification for EACH dimension score.
- Consider the embedding similarity as additional evidence but rely primarily on your analysis.
- Do NOT inflate scores. Be honest and precise.

## OUTPUT FORMAT — return ONLY this JSON, nothing else (no markdown, no code fences):
{{
    "candidates": [
        {{
            "name": "{cand_name}",
            "scores": {{
                "skills_match":          {{"score": <0-10>, "justification": "<one-line>"}},
                "experience_relevance":  {{"score": <0-10>, "justification": "<one-line>"}},
                "education_certs":       {{"score": <0-10>, "justification": "<one-line>"}},
                "project_portfolio":     {{"score": <0-10>, "justification": "<one-line>"}},
                "communication_quality": {{"score": <0-10>, "justification": "<one-line>"}}
            }},
            "weighted_total": <score*0.30 + score*0.25 + score*0.15 + score*0.20 + score*0.10, multiplied by 10, range 0-100>,
            "recommendation": "<hire | no-hire | maybe>",
            "overall_summary": "<2-3 sentence assessment>"
        }}
    ]
}}

Return ONLY valid JSON. No markdown, no code blocks, no extra text.
"""


class ScoringEngine:
    """
    Scores candidates across 5 mandatory dimensions using LLM + embeddings.
    """

    def __init__(self, llm_client=None, embedding_engine=None):
        """
        Initialize the scoring engine.
        
        Args:
            llm_client: Callable that takes a prompt and returns a response string
            embedding_engine: EmbeddingEngine instance for semantic matching
        """
        self.llm_client = llm_client
        self.embedding_engine = embedding_engine
        self.rubric = SCORING_RUBRIC

    def score_candidate(
        self,
        job_requirements: JobRequirements,
        candidate: CandidateProfile,
    ) -> CandidateScore:
        """
        Score a single candidate against job requirements.
        
        Args:
            job_requirements: Parsed job description requirements
            candidate: Parsed candidate profile
            
        Returns:
            CandidateScore with dimension-level scores
        """
        # Compute semantic similarity (embedding-based)
        semantic_data = self._compute_semantic_context(job_requirements, candidate)
        
        if self.llm_client:
            return self._llm_score(job_requirements, candidate, semantic_data)
        else:
            return self._heuristic_score(job_requirements, candidate, semantic_data)

    def _compute_semantic_context(
        self,
        jd: JobRequirements,
        candidate: CandidateProfile,
    ) -> dict:
        """Compute embedding-based semantic matching data."""
        if not self.embedding_engine:
            return {
                "skills_match": {"match_score": 0.0, "matched_skills": [], "unmatched_skills": jd.required_skills, "match_details": []},
                "profile_similarity": 0.0,
            }

        try:
            # Skills-level semantic matching
            all_jd_skills = jd.required_skills + jd.preferred_skills
            all_cand_skills = candidate.all_skills
            skills_match = self.embedding_engine.compute_skills_match(all_jd_skills, all_cand_skills)
            
            # Profile-level similarity
            jd_text = f"{jd.title}. {' '.join(jd.required_skills)}. {' '.join(jd.key_responsibilities)}"
            cand_text = (
                f"{candidate.current_title}. {' '.join(candidate.technical_skills)}. "
                f"{' '.join(d.get('highlights', [''])[0] if d.get('highlights') else '' for d in candidate.work_experience[:3])}"
            )
            profile_similarity = self.embedding_engine.compute_profile_similarity(jd_text, cand_text)
            
            return {
                "skills_match": skills_match,
                "profile_similarity": round(profile_similarity, 3),
            }
        except Exception as e:
            logger.error(f"Semantic computation error: {e}")
            return {
                "skills_match": {"match_score": 0.0, "matched_skills": [], "unmatched_skills": [], "match_details": []},
                "profile_similarity": 0.0,
            }

    def _llm_score(
        self,
        jd: JobRequirements,
        candidate: CandidateProfile,
        semantic_data: dict,
    ) -> CandidateScore:
        """Score using LLM with semantic context."""
        from security import validate_score

        # Format projects for prompt
        projects_str = "; ".join(
            f"{p.get('name', 'N/A')}: {p.get('description', 'N/A')[:100]}"
            for p in candidate.projects[:5]
        ) or "None listed"

        # Format work history
        work_str = "; ".join(
            f"{w.get('title', 'N/A')} at {w.get('company', 'N/A')} ({w.get('duration', 'N/A')})"
            for w in candidate.work_experience[:5]
        ) or "None listed"

        # Format education
        edu_str = "; ".join(
            f"{e.get('degree', 'N/A')} from {e.get('institution', 'N/A')}"
            for e in candidate.education
        ) or candidate.highest_education or "Not specified"

        skills_data = semantic_data.get("skills_match", {})

        prompt = SCORING_PROMPT.format(
            jd_title=jd.title,
            jd_skills=", ".join(jd.required_skills),
            jd_experience=f"{jd.min_years_experience}-{jd.max_years_experience}" if jd.max_years_experience else str(jd.min_years_experience),
            jd_domains=", ".join(jd.required_domains) or "Not specified",
            jd_seniority=jd.seniority_level,
            jd_education=jd.min_education,
            jd_responsibilities="; ".join(jd.key_responsibilities[:5]) or "Not specified",
            jd_projects=jd.project_expectations or "Not specified",
            cand_name=candidate.name,
            cand_title=candidate.current_title,
            cand_company=candidate.current_company,
            cand_experience=candidate.total_years_experience,
            cand_skills=", ".join(candidate.all_skills[:20]),
            cand_domains=", ".join(candidate.domains) or "Not specified",
            cand_education=edu_str,
            cand_certs=", ".join(candidate.certifications) or "None",
            cand_projects=projects_str,
            cand_work=work_str,
            semantic_skills_match=f"{skills_data.get('match_score', 0) * 100:.1f}%",
            matched_skills=", ".join(skills_data.get("matched_skills", [])),
            unmatched_skills=", ".join(skills_data.get("unmatched_skills", [])),
            profile_similarity=f"{semantic_data.get('profile_similarity', 0) * 100:.1f}%",
        )

        try:
            response = self.llm_client(prompt)
            
            # Clean response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1] if "\n" in response else response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            if response.startswith("json"):
                response = response[4:].strip()

            data = json.loads(response)

            # Unwrap spec-format: {"candidates": [{...}]}
            # Also accept flat format for backward compat
            if "candidates" in data and isinstance(data["candidates"], list) and data["candidates"]:
                cand_data = data["candidates"][0]
                scores_block = cand_data.get("scores", {})
                overall_summary = cand_data.get("overall_summary", "")
            else:
                # Flat format fallback (old prompt style)
                scores_block = data
                overall_summary = data.get("overall_summary", "")

            # Key mapping: spec key → display name, weight
            # Accepts both 'education_certs' and 'education_certifications'
            dimension_mapping = [
                ("Skills Match",            0.30, "skills_match"),
                ("Experience Relevance",     0.25, "experience_relevance"),
                ("Education & Certifications", 0.15, "education_certs"),
                ("Project / Portfolio",      0.20, "project_portfolio"),
                ("Communication Quality",    0.10, "communication_quality"),
            ]

            dimension_scores = []
            for dim_name, weight, key in dimension_mapping:
                # Try spec key first, then legacy key
                dim_data = scores_block.get(key) or scores_block.get(
                    key.replace("education_certs", "education_certifications"), {}
                )
                raw_score = dim_data.get("score", 5.0) if isinstance(dim_data, dict) else 5.0
                score = validate_score(raw_score, dim_name)
                justification = (
                    dim_data.get("justification", "No justification provided")
                    if isinstance(dim_data, dict) else "No justification"
                )
                dimension_scores.append(DimensionScore(
                    dimension=dim_name,
                    weight=weight,
                    score=score,
                    weighted_score=round(score * weight, 2),
                    justification=justification,
                    confidence=0.85,
                ))

            result = CandidateScore(
                candidate_name=candidate.name,
                candidate_file=candidate.source_file,
                dimension_scores=dimension_scores,
                overall_summary=overall_summary,
                semantic_similarity=semantic_data.get("profile_similarity", 0.0),
            )
            result.compute_total()

            logger.info(f"Scored {candidate.name}: {result.total_weighted_score}/10 — {result.recommendation}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scoring response: {e}")
            return self._heuristic_score(jd, candidate, semantic_data)
        except Exception as e:
            logger.error(f"LLM scoring error: {e}")
            return self._heuristic_score(jd, candidate, semantic_data)

    def _heuristic_score(
        self,
        jd: JobRequirements,
        candidate: CandidateProfile,
        semantic_data: dict,
    ) -> CandidateScore:
        """Fallback heuristic scoring without LLM."""
        skills_data = semantic_data.get("skills_match", {})
        skills_match_pct = skills_data.get("match_score", 0.0)
        
        # Skills Match: based on semantic match percentage
        if skills_match_pct >= 0.85:
            skills_score = 9.0
        elif skills_match_pct >= 0.70:
            skills_score = 7.0
        elif skills_match_pct >= 0.50:
            skills_score = 5.0
        elif skills_match_pct >= 0.30:
            skills_score = 3.0
        else:
            skills_score = 1.0

        # Experience Relevance: based on years and domain overlap
        exp_score = 5.0
        if candidate.total_years_experience >= jd.min_years_experience:
            exp_score += 2.0
        if set(d.lower() for d in candidate.domains) & set(d.lower() for d in jd.required_domains):
            exp_score += 2.0
        exp_score = min(10.0, exp_score)

        # Education: based on level match
        edu_levels = {"": 0, "High School": 1, "Bachelor's": 2, "Master's": 3, "PhD": 4}
        cand_level = edu_levels.get(candidate.highest_education, 0)
        req_level = edu_levels.get(jd.min_education, 0)
        if cand_level >= req_level + 1:
            edu_score = 9.0
        elif cand_level >= req_level:
            edu_score = 6.0
        elif cand_level >= req_level - 1:
            edu_score = 4.0
        else:
            edu_score = 2.0
        if candidate.certifications:
            edu_score = min(10.0, edu_score + 1.0)

        # Projects: based on count and relevance
        proj_count = len(candidate.projects)
        if proj_count >= 4:
            proj_score = 8.0
        elif proj_count >= 2:
            proj_score = 5.0
        elif proj_count >= 1:
            proj_score = 3.0
        else:
            proj_score = 1.0

        # Communication: based on resume quality
        comm_score = 5.0  # Default average

        dimensions = [
            DimensionScore("Skills Match", 0.30, skills_score, round(skills_score * 0.30, 2),
                          f"{skills_match_pct*100:.0f}% skills matched via semantic analysis", 0.6),
            DimensionScore("Experience Relevance", 0.25, exp_score, round(exp_score * 0.25, 2),
                          f"{candidate.total_years_experience} years experience in {', '.join(candidate.domains[:2]) or 'unspecified domain'}", 0.5),
            DimensionScore("Education & Certifications", 0.15, edu_score, round(edu_score * 0.15, 2),
                          f"{candidate.highest_education or 'Not specified'}, {len(candidate.certifications)} certifications", 0.7),
            DimensionScore("Project / Portfolio", 0.20, proj_score, round(proj_score * 0.20, 2),
                          f"{proj_count} projects listed", 0.5),
            DimensionScore("Communication Quality", 0.10, comm_score, round(comm_score * 0.10, 2),
                          "Heuristic default (LLM unavailable for quality assessment)", 0.3),
        ]

        result = CandidateScore(
            candidate_name=candidate.name,
            candidate_file=candidate.source_file,
            dimension_scores=dimensions,
            overall_summary=f"Heuristic scoring (LLM unavailable). Skills match: {skills_match_pct*100:.0f}%, Experience: {candidate.total_years_experience}y",
            semantic_similarity=semantic_data.get("profile_similarity", 0.0),
        )
        result.compute_total()
        return result
