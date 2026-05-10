"""
Ranking Engine — Sorts and ranks candidates by their weighted total scores.

Produces a final ranked shortlist with hire/no-hire recommendations.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .scoring import CandidateScore

logger = logging.getLogger(__name__)


@dataclass
class RankedCandidate:
    """A candidate with their rank position."""
    rank: int
    score: CandidateScore
    percentile: float = 0.0  # Position relative to other candidates

    @property
    def name(self) -> str:
        return self.score.candidate_name

    @property
    def total_score(self) -> float:
        return self.score.total_weighted_score

    @property
    def recommendation(self) -> str:
        if self.score.is_overridden:
            return self.score.override_recommendation
        return self.score.recommendation


class RankingEngine:
    """Ranks candidates by their total weighted scores."""

    def rank(self, scores: list[CandidateScore]) -> list[RankedCandidate]:
        """
        Rank candidates by total weighted score (descending).
        
        Args:
            scores: List of CandidateScore objects
            
        Returns:
            List of RankedCandidate objects sorted by rank
        """
        if not scores:
            return []

        # Sort by total weighted score, descending
        sorted_scores = sorted(scores, key=lambda s: s.total_weighted_score, reverse=True)
        
        total_candidates = len(sorted_scores)
        ranked = []
        
        for i, score in enumerate(sorted_scores):
            percentile = round((1 - i / total_candidates) * 100, 1) if total_candidates > 1 else 100.0
            ranked.append(RankedCandidate(
                rank=i + 1,
                score=score,
                percentile=percentile,
            ))

        logger.info(f"Ranked {len(ranked)} candidates. "
                    f"Top: {ranked[0].name} ({ranked[0].total_score}/10)")
        return ranked

    def apply_override(
        self,
        ranked_list: list[RankedCandidate],
        candidate_name: str,
        new_recommendation: str,
        reason: str,
        dimension: str = None,
        new_score: float = None,
    ) -> list[RankedCandidate]:
        """
        Apply a human-in-the-loop override to a candidate's recommendation.
        
        The override changes the recommendation but preserves the original scores.
        This maintains transparency and audit trail.
        
        Args:
            ranked_list: Current ranked candidates
            candidate_name: Name of the candidate to override
            new_recommendation: New recommendation (e.g., "Hire", "No Hire", "Flag")
            reason: Reason for the override
            
        Returns:
            Updated ranked list (same order, updated recommendation)
        """
        import datetime
        for candidate in ranked_list:
            if candidate.score.candidate_name.lower() == candidate_name.lower():
                candidate.score.is_overridden = True
                candidate.score.override_recommendation = new_recommendation
                candidate.score.override_reason = reason
                candidate.score.override_timestamp = datetime.datetime.now().isoformat()
                # Optionally update a specific dimension score
                if dimension and new_score is not None:
                    for d in candidate.score.dimension_scores:
                        if d.dimension.lower() == dimension.lower():
                            d.score = max(0.0, min(10.0, float(new_score)))
                            d.weighted_score = round(d.score * d.weight, 2)
                            d.justification = f"[HR Override] Score changed to {d.score}. Reason: {reason}"
                    candidate.score.compute_total()
                logger.info(f"Override: {candidate_name} → {new_recommendation} | {reason}")
                return ranked_list

        logger.warning(f"Candidate '{candidate_name}' not found for override")
        return ranked_list

    def get_shortlist(
        self,
        ranked_list: list[RankedCandidate],
        top_n: Optional[int] = None,
        min_score: float = 0.0,
    ) -> list[RankedCandidate]:
        """
        Get a filtered shortlist from the ranked candidates.
        
        Args:
            ranked_list: Full ranked list
            top_n: Maximum number of candidates to include
            min_score: Minimum total score threshold
            
        Returns:
            Filtered shortlist
        """
        filtered = [c for c in ranked_list if c.total_score >= min_score]
        
        if top_n:
            filtered = filtered[:top_n]
        
        return filtered

    def generate_summary_stats(self, ranked_list: list[RankedCandidate]) -> dict:
        """Generate summary statistics for the ranked candidates."""
        if not ranked_list:
            return {"total_candidates": 0}

        scores = [c.total_score for c in ranked_list]
        
        return {
            "total_candidates": len(ranked_list),
            "average_score": round(sum(scores) / len(scores), 2),
            "top_score": round(max(scores), 2),
            "max_score": round(max(scores), 2),
            "min_score": round(min(scores), 2),
            "median_score": round(sorted(scores)[len(scores) // 2], 2),
            "strong_hire_count": sum(1 for c in ranked_list if c.recommendation == "Strong Hire"),
            "hire_count": sum(1 for c in ranked_list if c.recommendation == "Hire"),
            "maybe_count": sum(1 for c in ranked_list if c.recommendation == "Maybe"),
            "no_hire_count": sum(1 for c in ranked_list if c.recommendation == "No Hire"),
            "overridden_count": sum(1 for c in ranked_list if c.score.is_overridden),
        }
