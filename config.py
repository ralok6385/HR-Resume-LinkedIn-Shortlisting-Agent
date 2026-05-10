"""
Configuration management for the HR Resume Shortlisting Agent.
Centralizes all settings and provides validated access to environment variables.

LLM Priority:
  1. Claude 3.5 Sonnet (primary, via Anthropic)
  2. Gemini 2.0 Flash (secondary)
  3. GPT-4o (fallback)
  4. Heuristic mode (offline, no LLM required)
"""

import os
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# ============================================================
# Project Paths
# ============================================================
PROJECT_ROOT = Path(__file__).parent.resolve()
DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_RESUMES_DIR = DATA_DIR / "sample_resumes"
OUTPUT_DIR = PROJECT_ROOT / "output"
REPORTS_DIR = PROJECT_ROOT / "reports"
TEMPLATES_DIR = REPORTS_DIR / "templates"
LOGS_DIR = PROJECT_ROOT / "logs"

# Ensure required directories exist
for _dir in [DATA_DIR, SAMPLE_RESUMES_DIR, OUTPUT_DIR, LOGS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# LLM Provider Enum
# ============================================================
class LLMProvider(str, Enum):
    CLAUDE = "claude"      # Anthropic Claude 3.5 Sonnet (primary)
    GEMINI = "gemini"      # Google Gemini (secondary)
    OPENAI = "openai"      # OpenAI GPT-4o (fallback)
    HEURISTIC = "heuristic"  # No LLM — offline mode


# ============================================================
# Scoring Rubric Configuration
# ============================================================
@dataclass
class ScoringDimension:
    name: str
    key: str        # JSON key
    weight: float   # Must sum to 1.0
    description: str
    score_0: str    # Criteria for score ~0
    score_5: str    # Criteria for score ~5
    score_10: str   # Criteria for score ~10


SCORING_RUBRIC: list[ScoringDimension] = [
    ScoringDimension(
        name="Skills Match",
        key="skills_match",
        weight=0.30,
        description="How well candidate's skills match JD requirements",
        score_0="Less than 30% of required skills present",
        score_5="50-70% of required skills present",
        score_10="More than 85% of required skills present",
    ),
    ScoringDimension(
        name="Experience Relevance",
        key="experience_relevance",
        weight=0.25,
        description="Domain and seniority alignment with JD",
        score_0="Unrelated domain, no relevant experience",
        score_5="Adjacent domain, some transferable experience",
        score_10="Exact domain match with matching seniority level",
    ),
    ScoringDimension(
        name="Education & Certifications",
        key="education_certs",
        weight=0.15,
        description="Educational qualifications and relevant certifications",
        score_0="Does not meet minimum educational requirements",
        score_5="Meets minimum requirements",
        score_10="Exceeds requirements with extra relevant certifications",
    ),
    ScoringDimension(
        name="Project / Portfolio",
        key="project_portfolio",
        weight=0.20,
        description="Evidence of relevant work / projects / portfolio",
        score_0="No evidence of relevant projects",
        score_5="1-2 generic projects listed",
        score_10="Strong portfolio with relevant, impactful projects",
    ),
    ScoringDimension(
        name="Communication Quality",
        key="communication_quality",
        weight=0.10,
        description="Clarity, structure, and impact of written communication",
        score_0="Poor structure or grammar issues",
        score_5="Adequate clarity and organization",
        score_10="Crisp, well-structured, and impactful writing",
    ),
]

assert abs(sum(d.weight for d in SCORING_RUBRIC) - 1.0) < 1e-9, "Rubric weights must sum to 1.0"


# ============================================================
# LLM Configuration
# ============================================================
@dataclass
class LLMConfig:
    provider: LLMProvider = LLMProvider.CLAUDE
    # Claude (primary)
    anthropic_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20241022"
    # Gemini (secondary)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    # OpenAI (fallback)
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    # Generation settings
    temperature: float = 0.1
    max_output_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "LLMConfig":
        # Auto-detect best available provider
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        openai_key = os.getenv("OPENAI_API_KEY", "")

        if anthropic_key:
            provider = LLMProvider.CLAUDE
        elif gemini_key:
            provider = LLMProvider.GEMINI
        elif openai_key:
            provider = LLMProvider.OPENAI
        else:
            provider = LLMProvider.HEURISTIC

        return cls(
            provider=provider,
            anthropic_api_key=anthropic_key,
            claude_model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
            gemini_api_key=gemini_key,
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            openai_api_key=openai_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        )

    @property
    def is_configured(self) -> bool:
        """Check if the selected provider has a valid API key."""
        if self.provider == LLMProvider.CLAUDE:
            return bool(self.anthropic_api_key)
        elif self.provider == LLMProvider.GEMINI:
            return bool(self.gemini_api_key)
        elif self.provider == LLMProvider.OPENAI:
            return bool(self.openai_api_key)
        return False  # Heuristic mode

    @property
    def display_name(self) -> str:
        if self.provider == LLMProvider.CLAUDE:
            return f"Claude 3.5 Sonnet ({self.claude_model})"
        elif self.provider == LLMProvider.GEMINI:
            return f"Gemini ({self.gemini_model})"
        elif self.provider == LLMProvider.OPENAI:
            return f"OpenAI ({self.openai_model})"
        return "Heuristic (Offline)"


# ============================================================
# Embedding Configuration
# ============================================================
@dataclass
class EmbeddingConfig:
    model_name: str = "all-MiniLM-L6-v2"  # Sentence-transformers local model
    use_gpu: bool = False
    cache_dir: str = str(PROJECT_ROOT / ".embedding_cache")

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        return cls(
            model_name=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            use_gpu=os.getenv("EMBEDDING_USE_GPU", "false").lower() == "true",
        )


# ============================================================
# Security Configuration
# ============================================================
@dataclass
class SecurityConfig:
    max_file_size_mb: int = 10
    max_batch_size: int = 100
    enable_pii_masking_in_logs: bool = True
    allowed_extensions: set = field(default_factory=lambda: {".pdf", ".docx", ".txt", ".json"})

    @classmethod
    def from_env(cls) -> "SecurityConfig":
        return cls(
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "10")),
            max_batch_size=int(os.getenv("MAX_BATCH_SIZE", "100")),
        )


# ============================================================
# Convenience loader
# ============================================================
def load_config() -> dict:
    return {
        "llm": LLMConfig.from_env(),
        "embedding": EmbeddingConfig.from_env(),
        "security": SecurityConfig.from_env(),
    }
