"""
Embedding Engine — Computes semantic similarity between JD and candidate profiles.

Uses sentence-transformers for local embedding computation (no API key needed).
Provides cosine similarity scores to enhance LLM-based scoring.
"""

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Computes semantic embeddings and similarity scores."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding engine.
        
        Args:
            model_name: Sentence-transformers model name.
                        Options: all-MiniLM-L6-v2 (fast), all-mpnet-base-v2 (better quality)
        """
        self.model_name = model_name
        self._model = None

    @property
    def model(self):
        """Lazy-load the embedding model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                logger.info(f"Loading embedding model: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
                logger.info("Embedding model loaded successfully")
            except ImportError:
                logger.error("sentence-transformers not installed. Install with: pip install sentence-transformers")
                raise
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """
        Encode texts into embeddings.
        
        Args:
            texts: List of text strings to encode
            
        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        if not texts:
            return np.array([])
        return self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """
        Compute cosine similarity between two texts.
        
        Args:
            text_a: First text
            text_b: Second text
            
        Returns:
            Cosine similarity score between 0 and 1
        """
        embeddings = self.encode([text_a, text_b])
        if len(embeddings) < 2:
            return 0.0
        
        # Cosine similarity
        sim = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]) + 1e-8
        )
        return float(max(0.0, min(1.0, sim)))

    def compute_skills_match(self, jd_skills: list[str], candidate_skills: list[str]) -> dict:
        """
        Compute semantic skills match between JD requirements and candidate skills.
        
        Uses embedding similarity to catch synonyms and related terms
        (e.g., "React" matches "ReactJS", "ML" matches "Machine Learning").
        
        Args:
            jd_skills: Required skills from the job description
            candidate_skills: Skills listed on the candidate's resume
            
        Returns:
            Dict with match_score (0-1), matched_skills, unmatched_skills, similarity_matrix
        """
        if not jd_skills or not candidate_skills:
            return {
                "match_score": 0.0,
                "matched_skills": [],
                "unmatched_skills": jd_skills if jd_skills else [],
                "match_details": [],
            }

        # Normalize skill names
        jd_normalized = [s.lower().strip() for s in jd_skills]
        cand_normalized = [s.lower().strip() for s in candidate_skills]

        # First pass: exact match
        exact_matches = set(jd_normalized) & set(cand_normalized)
        
        # Second pass: semantic match for remaining
        remaining_jd = [s for s in jd_normalized if s not in exact_matches]
        remaining_cand = [s for s in cand_normalized if s not in exact_matches]

        matched_skills = list(exact_matches)
        match_details = [{"jd_skill": s, "matched_to": s, "method": "exact", "score": 1.0} 
                        for s in exact_matches]
        unmatched = []

        if remaining_jd and remaining_cand:
            try:
                # Encode remaining skills
                jd_embeddings = self.encode(remaining_jd)
                cand_embeddings = self.encode(remaining_cand)
                
                # Compute similarity matrix
                # shape: (len(remaining_jd), len(remaining_cand))
                similarity_matrix = np.dot(jd_embeddings, cand_embeddings.T) / (
                    np.linalg.norm(jd_embeddings, axis=1, keepdims=True) * 
                    np.linalg.norm(cand_embeddings, axis=1, keepdims=True).T + 1e-8
                )
                
                # For each JD skill, find best matching candidate skill
                SEMANTIC_THRESHOLD = 0.6  # Minimum similarity for a "match"
                
                for i, jd_skill in enumerate(remaining_jd):
                    best_idx = np.argmax(similarity_matrix[i])
                    best_score = float(similarity_matrix[i][best_idx])
                    
                    if best_score >= SEMANTIC_THRESHOLD:
                        matched_skills.append(jd_skill)
                        match_details.append({
                            "jd_skill": jd_skill,
                            "matched_to": remaining_cand[best_idx],
                            "method": "semantic",
                            "score": round(best_score, 3),
                        })
                    else:
                        unmatched.append(jd_skill)
                        match_details.append({
                            "jd_skill": jd_skill,
                            "matched_to": remaining_cand[best_idx] if remaining_cand else None,
                            "method": "no_match",
                            "score": round(best_score, 3),
                        })
            except Exception as e:
                logger.error(f"Semantic matching error: {e}")
                unmatched = remaining_jd
        else:
            unmatched = remaining_jd

        match_score = len(matched_skills) / len(jd_skills) if jd_skills else 0.0
        
        return {
            "match_score": round(match_score, 3),
            "matched_skills": matched_skills,
            "unmatched_skills": unmatched,
            "match_details": match_details,
        }

    def compute_profile_similarity(self, jd_text: str, resume_text: str) -> float:
        """
        Compute overall semantic similarity between full JD and resume texts.
        
        Args:
            jd_text: Full job description text
            resume_text: Full resume text
            
        Returns:
            Similarity score between 0 and 1
        """
        # For long texts, chunk and average
        jd_chunks = self._chunk_text(jd_text, max_length=500)
        resume_chunks = self._chunk_text(resume_text, max_length=500)
        
        if not jd_chunks or not resume_chunks:
            return 0.0

        jd_embeddings = self.encode(jd_chunks)
        resume_embeddings = self.encode(resume_chunks)
        
        # Average embeddings for each document
        jd_avg = np.mean(jd_embeddings, axis=0)
        resume_avg = np.mean(resume_embeddings, axis=0)
        
        # Cosine similarity of averaged embeddings
        sim = np.dot(jd_avg, resume_avg) / (
            np.linalg.norm(jd_avg) * np.linalg.norm(resume_avg) + 1e-8
        )
        return float(max(0.0, min(1.0, sim)))

    @staticmethod
    def _chunk_text(text: str, max_length: int = 500) -> list[str]:
        """Split text into chunks of roughly max_length characters."""
        words = text.split()
        chunks = []
        current = []
        current_len = 0
        
        for word in words:
            if current_len + len(word) + 1 > max_length and current:
                chunks.append(" ".join(current))
                current = [word]
                current_len = len(word)
            else:
                current.append(word)
                current_len += len(word) + 1
        
        if current:
            chunks.append(" ".join(current))
        
        return chunks if chunks else [text[:max_length]]
