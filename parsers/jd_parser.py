"""
Job Description Parser — Extracts structured requirements from a JD using LLM.

Converts free-text job descriptions into a structured JobRequirements object
containing required skills, experience level, education, and more.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class JobRequirements:
    """Structured representation of job description requirements."""
    title: str = ""
    company: str = ""
    department: str = ""
    
    # Skills
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    
    # Experience
    min_years_experience: int = 0
    max_years_experience: int = 0
    required_domains: list[str] = field(default_factory=list)
    seniority_level: str = ""  # Junior, Mid, Senior, Lead, Staff, Principal
    
    # Education
    min_education: str = ""  # High School, Bachelor's, Master's, PhD
    preferred_education: str = ""
    required_certifications: list[str] = field(default_factory=list)
    preferred_certifications: list[str] = field(default_factory=list)
    
    # Other
    key_responsibilities: list[str] = field(default_factory=list)
    project_expectations: str = ""
    communication_requirements: str = ""
    
    # Raw text for reference
    raw_text: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "title": self.title,
            "company": self.company,
            "department": self.department,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "min_years_experience": self.min_years_experience,
            "max_years_experience": self.max_years_experience,
            "required_domains": self.required_domains,
            "seniority_level": self.seniority_level,
            "min_education": self.min_education,
            "preferred_education": self.preferred_education,
            "required_certifications": self.required_certifications,
            "preferred_certifications": self.preferred_certifications,
            "key_responsibilities": self.key_responsibilities,
            "project_expectations": self.project_expectations,
            "communication_requirements": self.communication_requirements,
        }

    def summary(self) -> str:
        """Human-readable summary of the requirements."""
        parts = [f"**{self.title}**"]
        if self.company:
            parts[0] += f" at {self.company}"
        if self.required_skills:
            parts.append(f"Required Skills: {', '.join(self.required_skills)}")
        if self.min_years_experience:
            exp = f"{self.min_years_experience}"
            if self.max_years_experience:
                exp += f"-{self.max_years_experience}"
            parts.append(f"Experience: {exp} years")
        if self.seniority_level:
            parts.append(f"Level: {self.seniority_level}")
        if self.min_education:
            parts.append(f"Education: {self.min_education}+")
        return "\n".join(parts)


# ============================================================
# JD Parsing Prompt Template
# ============================================================

JD_PARSE_PROMPT = """You are an expert HR analyst. Extract structured requirements from the following Job Description.

**Job Description:**
{jd_text}

**Instructions:**
Analyze the JD carefully and extract ALL requirements into the following JSON format. Be thorough — do not miss any skills, qualifications, or requirements mentioned in the text.

For skills: List specific technical skills, tools, frameworks, languages, and soft skills separately.
For experience: Extract the exact years mentioned. If a range is given (e.g., "3-5 years"), use that.
For education: Identify minimum and preferred levels.
For seniority: Classify as one of: Junior, Mid, Senior, Lead, Staff, Principal.

**Output JSON:**
{{
    "title": "exact job title",
    "company": "company name if mentioned, else empty string",
    "department": "department if mentioned, else empty string",
    "required_skills": ["skill1", "skill2", ...],
    "preferred_skills": ["nice-to-have skill1", ...],
    "min_years_experience": integer,
    "max_years_experience": integer,
    "required_domains": ["domain1", "domain2"],
    "seniority_level": "Junior|Mid|Senior|Lead|Staff|Principal",
    "min_education": "High School|Bachelor's|Master's|PhD",
    "preferred_education": "level or empty string",
    "required_certifications": ["cert1", ...],
    "preferred_certifications": ["cert1", ...],
    "key_responsibilities": ["responsibility1", ...],
    "project_expectations": "description of expected projects/portfolio",
    "communication_requirements": "description of communication expectations"
}}

Return ONLY valid JSON. No markdown formatting, no code blocks, no explanation.
"""


class JDParser:
    """Parses Job Descriptions into structured requirements using LLM."""

    def __init__(self, llm_client=None):
        """
        Initialize the JD Parser.
        
        Args:
            llm_client: A callable that takes a prompt string and returns a response string.
                        This abstracts away the specific LLM provider.
        """
        self.llm_client = llm_client

    def parse(self, jd_text: str) -> JobRequirements:
        """
        Parse a job description into structured requirements.
        
        Args:
            jd_text: Raw job description text
            
        Returns:
            JobRequirements object with extracted data
        """
        from security import sanitize_input

        # Sanitize input
        clean_text, warnings = sanitize_input(jd_text)
        if warnings:
            logger.warning(f"JD sanitization warnings: {warnings}")

        if not self.llm_client:
            logger.warning("No LLM client configured, using basic extraction")
            return self._basic_parse(clean_text)

        try:
            # Use LLM for intelligent parsing
            prompt = JD_PARSE_PROMPT.format(jd_text=clean_text)
            response = self.llm_client(prompt)
            
            # Clean the response — remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[1] if "\n" in response else response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            if response.startswith("json"):
                response = response[4:].strip()

            # Parse JSON response
            data = json.loads(response)
            
            requirements = JobRequirements(
                title=data.get("title", ""),
                company=data.get("company", ""),
                department=data.get("department", ""),
                required_skills=data.get("required_skills", []),
                preferred_skills=data.get("preferred_skills", []),
                min_years_experience=int(data.get("min_years_experience", 0)),
                max_years_experience=int(data.get("max_years_experience", 0)),
                required_domains=data.get("required_domains", []),
                seniority_level=data.get("seniority_level", ""),
                min_education=data.get("min_education", ""),
                preferred_education=data.get("preferred_education", ""),
                required_certifications=data.get("required_certifications", []),
                preferred_certifications=data.get("preferred_certifications", []),
                key_responsibilities=data.get("key_responsibilities", []),
                project_expectations=data.get("project_expectations", ""),
                communication_requirements=data.get("communication_requirements", ""),
                raw_text=jd_text,
            )
            
            logger.info(f"Successfully parsed JD: {requirements.title} — "
                       f"{len(requirements.required_skills)} required skills extracted")
            return requirements

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.debug(f"Raw response: {response[:500]}")
            return self._basic_parse(clean_text)
        except Exception as e:
            logger.error(f"JD parsing error: {e}")
            return self._basic_parse(clean_text)

    def _basic_parse(self, jd_text: str) -> JobRequirements:
        """
        Fallback basic parsing without LLM.
        Uses keyword extraction and pattern matching.
        """
        import re

        text_lower = jd_text.lower()

        # Extract potential skills (common tech keywords)
        tech_keywords = [
            "python", "java", "javascript", "typescript", "react", "angular", "vue",
            "node.js", "django", "flask", "fastapi", "spring", "sql", "nosql",
            "mongodb", "postgresql", "mysql", "redis", "docker", "kubernetes",
            "aws", "azure", "gcp", "ci/cd", "git", "linux", "api", "rest",
            "graphql", "machine learning", "deep learning", "nlp", "ai",
            "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn",
            "html", "css", "sass", "webpack", "agile", "scrum", "jira",
            "communication", "leadership", "teamwork", "problem solving",
            "c++", "c#", "go", "rust", "swift", "kotlin", "scala",
        ]
        
        found_skills = [s for s in tech_keywords if s in text_lower]

        # Extract years of experience
        exp_match = re.search(r'(\d+)\+?\s*(?:to|-)\s*(\d+)?\s*years?', text_lower)
        min_exp = int(exp_match.group(1)) if exp_match else 0
        max_exp = int(exp_match.group(2)) if exp_match and exp_match.group(2) else min_exp

        # Extract education
        education = ""
        if "phd" in text_lower or "doctorate" in text_lower:
            education = "PhD"
        elif "master" in text_lower or "m.s." in text_lower or "m.tech" in text_lower:
            education = "Master's"
        elif "bachelor" in text_lower or "b.s." in text_lower or "b.tech" in text_lower:
            education = "Bachelor's"

        # Extract title from first line
        first_line = jd_text.strip().split("\n")[0].strip()
        title = first_line if len(first_line) < 100 else "Unknown Position"

        return JobRequirements(
            title=title,
            required_skills=found_skills,
            min_years_experience=min_exp,
            max_years_experience=max_exp,
            min_education=education,
            seniority_level=self._guess_seniority(min_exp),
            raw_text=jd_text,
        )

    @staticmethod
    def _guess_seniority(min_years: int) -> str:
        """Guess seniority level from years of experience."""
        if min_years >= 10:
            return "Principal"
        elif min_years >= 7:
            return "Staff"
        elif min_years >= 5:
            return "Senior"
        elif min_years >= 2:
            return "Mid"
        else:
            return "Junior"
