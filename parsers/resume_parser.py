"""
Resume Parser — Extracts structured candidate profiles from PDF/DOCX/TXT resumes.

Supports:
- PDF files (via PyMuPDF/fitz)
- DOCX files (via python-docx)
- TXT files (direct read)
- LLM-based intelligent extraction for structured fields
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CandidateProfile:
    """Structured representation of a candidate's resume."""
    # Identity (PII — masked in logs)
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    
    # Professional
    current_title: str = ""
    current_company: str = ""
    total_years_experience: float = 0.0
    
    # Skills
    technical_skills: list[str] = field(default_factory=list)
    soft_skills: list[str] = field(default_factory=list)
    tools_and_frameworks: list[str] = field(default_factory=list)
    programming_languages: list[str] = field(default_factory=list)
    
    # Experience
    work_experience: list[dict] = field(default_factory=list)
    # Each entry: {"title", "company", "duration", "domain", "highlights"}
    domains: list[str] = field(default_factory=list)
    
    # Education
    education: list[dict] = field(default_factory=list)
    # Each entry: {"degree", "institution", "year", "field"}
    highest_education: str = ""
    certifications: list[str] = field(default_factory=list)
    
    # Projects
    projects: list[dict] = field(default_factory=list)
    # Each entry: {"name", "description", "technologies", "impact"}
    
    # Communication (assessed from resume quality)
    resume_quality_notes: str = ""
    
    # Metadata
    source_file: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary (excluding raw_text for brevity)."""
        d = {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "current_title": self.current_title,
            "current_company": self.current_company,
            "total_years_experience": self.total_years_experience,
            "technical_skills": self.technical_skills,
            "soft_skills": self.soft_skills,
            "tools_and_frameworks": self.tools_and_frameworks,
            "programming_languages": self.programming_languages,
            "work_experience": self.work_experience,
            "domains": self.domains,
            "education": self.education,
            "highest_education": self.highest_education,
            "certifications": self.certifications,
            "projects": self.projects,
            "resume_quality_notes": self.resume_quality_notes,
            "source_file": self.source_file,
        }
        return d

    @property
    def all_skills(self) -> list[str]:
        """All skills combined."""
        return list(set(
            self.technical_skills + 
            self.soft_skills + 
            self.tools_and_frameworks + 
            self.programming_languages
        ))

    def summary(self) -> str:
        """Brief human-readable summary."""
        parts = [f"**{self.name}** — {self.current_title}"]
        if self.current_company:
            parts[0] += f" @ {self.current_company}"
        parts.append(f"Experience: {self.total_years_experience} years")
        if self.technical_skills:
            parts.append(f"Skills: {', '.join(self.technical_skills[:8])}")
        if self.highest_education:
            parts.append(f"Education: {self.highest_education}")
        return "\n".join(parts)


# ============================================================
# Resume Parsing Prompt Template
# ============================================================

RESUME_PARSE_PROMPT = """You are an expert resume analyst. Extract structured information from the following resume text.

**Resume Text:**
{resume_text}

**Instructions:**
Extract ALL information from the resume into the following JSON format. Be thorough and accurate.

For skills: Separate technical skills, programming languages, tools/frameworks, and soft skills.
For experience: Calculate total years based on work history dates.
For education: Identify the highest degree level.
For projects: Include personal, academic, and professional projects.

**Output JSON:**
{{
    "name": "full name",
    "email": "email address or empty string",
    "phone": "phone number or empty string",
    "location": "city, state/country or empty string",
    "current_title": "most recent job title",
    "current_company": "most recent company",
    "total_years_experience": number,
    "technical_skills": ["skill1", "skill2"],
    "soft_skills": ["skill1", "skill2"],
    "tools_and_frameworks": ["tool1", "framework1"],
    "programming_languages": ["lang1", "lang2"],
    "work_experience": [
        {{
            "title": "job title",
            "company": "company name",
            "duration": "start - end",
            "domain": "industry/domain",
            "highlights": ["achievement1", "achievement2"]
        }}
    ],
    "domains": ["domain1", "domain2"],
    "education": [
        {{
            "degree": "degree type",
            "institution": "school name",
            "year": "graduation year or expected",
            "field": "field of study"
        }}
    ],
    "highest_education": "High School|Bachelor's|Master's|PhD",
    "certifications": ["cert1", "cert2"],
    "projects": [
        {{
            "name": "project name",
            "description": "brief description",
            "technologies": ["tech1", "tech2"],
            "impact": "measurable impact if available"
        }}
    ],
    "resume_quality_notes": "brief assessment of resume clarity, structure, and writing quality"
}}

Return ONLY valid JSON. No markdown formatting, no code blocks, no explanation.
"""


class ResumeParser:
    """Parses resume documents into structured candidate profiles."""

    def __init__(self, llm_client=None):
        """
        Initialize the Resume Parser.
        
        Args:
            llm_client: A callable that takes a prompt string and returns a response string.
        """
        self.llm_client = llm_client

    def parse(self, file_path: str | Path, raw_text: Optional[str] = None) -> CandidateProfile:
        """
        Parse a resume file into a structured candidate profile.
        
        Args:
            file_path: Path to the resume file (PDF, DOCX, or TXT)
            raw_text: Optional pre-extracted text (skips file reading)
            
        Returns:
            CandidateProfile with extracted data
        """
        file_path = Path(file_path)
        
        # Extract text from file
        if raw_text:
            text = raw_text
        else:
            text = self._extract_text(file_path)
        
        if not text.strip():
            logger.error(f"No text extracted from {file_path}")
            return CandidateProfile(source_file=str(file_path))

        # Sanitize
        from security import sanitize_input
        clean_text, warnings = sanitize_input(text)
        if warnings:
            logger.warning(f"Resume sanitization warnings for {file_path.name}: {warnings}")

        # Parse with LLM or fallback
        if self.llm_client:
            profile = self._llm_parse(clean_text, str(file_path))
        else:
            profile = self._basic_parse(clean_text, str(file_path))
        
        profile.source_file = str(file_path.name)
        profile.raw_text = text
        return profile

    def _extract_text(self, file_path: Path) -> str:
        """Extract text content from various file formats."""
        suffix = file_path.suffix.lower()
        
        if suffix == ".pdf":
            return self._extract_pdf(file_path)
        elif suffix in (".docx", ".doc"):
            return self._extract_docx(file_path)
        elif suffix == ".txt":
            return file_path.read_text(encoding="utf-8", errors="ignore")
        elif suffix == ".json":
            return file_path.read_text(encoding="utf-8", errors="ignore")
        else:
            logger.warning(f"Unsupported file type: {suffix}, trying as text")
            return file_path.read_text(encoding="utf-8", errors="ignore")

    @staticmethod
    def _extract_pdf(file_path: Path) -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(file_path))
            text_parts = []
            for page in doc:
                text_parts.append(page.get_text())
            doc.close()
            return "\n".join(text_parts)
        except ImportError:
            logger.error("PyMuPDF not installed. Install with: pip install PyMuPDF")
            return ""
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""

    @staticmethod
    def _extract_docx(file_path: Path) -> str:
        """Extract text from DOCX using python-docx."""
        try:
            from docx import Document
            doc = Document(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n".join(paragraphs)
        except ImportError:
            logger.error("python-docx not installed. Install with: pip install python-docx")
            return ""
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            return ""

    def _llm_parse(self, text: str, source: str) -> CandidateProfile:
        """Parse resume text using LLM for intelligent extraction."""
        try:
            prompt = RESUME_PARSE_PROMPT.format(resume_text=text)
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
            
            profile = CandidateProfile(
                name=data.get("name", ""),
                email=data.get("email", ""),
                phone=data.get("phone", ""),
                location=data.get("location", ""),
                current_title=data.get("current_title", ""),
                current_company=data.get("current_company", ""),
                total_years_experience=float(data.get("total_years_experience", 0)),
                technical_skills=data.get("technical_skills", []),
                soft_skills=data.get("soft_skills", []),
                tools_and_frameworks=data.get("tools_and_frameworks", []),
                programming_languages=data.get("programming_languages", []),
                work_experience=data.get("work_experience", []),
                domains=data.get("domains", []),
                education=data.get("education", []),
                highest_education=data.get("highest_education", ""),
                certifications=data.get("certifications", []),
                projects=data.get("projects", []),
                resume_quality_notes=data.get("resume_quality_notes", ""),
            )
            
            logger.info(f"Parsed resume: {profile.name} — "
                       f"{len(profile.technical_skills)} skills, "
                       f"{len(profile.work_experience)} experiences")
            return profile

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response for resume: {e}")
            return self._basic_parse(text, source)
        except Exception as e:
            logger.error(f"Resume LLM parsing error: {e}")
            return self._basic_parse(text, source)

    def _basic_parse(self, text: str, source: str) -> CandidateProfile:
        """Fallback basic parsing without LLM."""
        import re
        
        lines = text.strip().split("\n")
        
        # Try to extract name from first non-empty line
        name = lines[0].strip() if lines else "Unknown"
        
        # Extract email
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        email = email_match.group() if email_match else ""
        
        # Extract phone
        phone_match = re.search(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}', text)
        phone = phone_match.group() if phone_match else ""
        
        # Extract skills (common keywords)
        text_lower = text.lower()
        tech_keywords = [
            "python", "java", "javascript", "typescript", "react", "angular", "vue",
            "node.js", "django", "flask", "fastapi", "spring", "sql", "nosql",
            "mongodb", "postgresql", "mysql", "redis", "docker", "kubernetes",
            "aws", "azure", "gcp", "git", "linux", "api", "rest",
            "machine learning", "deep learning", "nlp", "ai",
            "tensorflow", "pytorch", "pandas", "numpy",
            "html", "css", "c++", "c#", "go", "rust", "swift", "kotlin",
        ]
        found_skills = [s for s in tech_keywords if s in text_lower]
        
        # Education
        education = ""
        if "phd" in text_lower or "doctorate" in text_lower:
            education = "PhD"
        elif "master" in text_lower or "m.s." in text_lower or "m.tech" in text_lower:
            education = "Master's"
        elif "bachelor" in text_lower or "b.s." in text_lower or "b.tech" in text_lower:
            education = "Bachelor's"

        return CandidateProfile(
            name=name,
            email=email,
            phone=phone,
            technical_skills=found_skills,
            highest_education=education,
            source_file=source,
        )
