"""
LinkedIn Ingestion — Parses LinkedIn profile data from multiple formats.

Supported formats:
1. LinkedIn Data Export JSON (exported from Settings > Data Privacy)
2. RapidAPI LinkedIn Scrape response
3. Manual LinkedIn JSON (custom HR tool export)
4. Plain text (copy-paste from LinkedIn profile page)

All data stays local — no API calls made from this module.
"""

import json
import logging
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


class LinkedInIngestion:
    """
    Ingests LinkedIn profile data from various JSON formats and raw text.
    Normalizes to a standard dict structure for the LinkedIn parser.
    """

    def load_file(self, file_path: str | Path) -> dict:
        """
        Load LinkedIn data from a JSON file or text file.

        Args:
            file_path: Path to LinkedIn JSON or text export.

        Returns:
            Normalized LinkedIn profile dict.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"LinkedIn file not found: {path}")

        if path.suffix.lower() == ".json":
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return self._normalize(raw)
        else:
            # Plain text fallback
            text = path.read_text(encoding="utf-8", errors="ignore")
            return {"raw_text": text, "format": "plain_text"}

    def load_bytes(self, content: bytes, filename: str) -> dict:
        """Load LinkedIn data from bytes (API upload)."""
        if filename.endswith(".json"):
            try:
                raw = json.loads(content.decode("utf-8"))
                return self._normalize(raw)
            except json.JSONDecodeError as e:
                logger.warning(f"LinkedIn JSON parse failed: {e}. Treating as text.")
        return {"raw_text": content.decode("utf-8", errors="ignore"), "format": "plain_text"}

    def load_dict(self, data: dict) -> dict:
        """Load LinkedIn data from a Python dict (e.g., RapidAPI response)."""
        return self._normalize(data)

    def _normalize(self, raw: Union[dict, list]) -> dict:
        """
        Normalize various LinkedIn JSON formats to a standard structure.

        Handles:
        - LinkedIn official export (nested lists for positions/education)
        - RapidAPI format (flat with different key names)
        - Custom/manual format
        """
        if isinstance(raw, list):
            # LinkedIn export wraps everything in a list
            raw = raw[0] if raw else {}

        # Detect format
        if "positions" in raw or "educations" in raw:
            return self._parse_official_export(raw)
        elif "experience" in raw or "headline" in raw:
            return self._parse_rapidapi_format(raw)
        else:
            return self._parse_generic(raw)

    def _parse_official_export(self, data: dict) -> dict:
        """Parse LinkedIn's official data export format."""
        profile = {
            "format": "linkedin_official_export",
            "name": f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
            "headline": data.get("headline", ""),
            "summary": data.get("summary", ""),
            "location": data.get("geoLocationName", data.get("location", {}).get("name", "")),
            "email": data.get("emailAddress", ""),
            "skills": [],
            "experience": [],
            "education": [],
            "certifications": [],
            "projects": [],
        }

        # Skills
        for skill in data.get("skills", []):
            if isinstance(skill, dict):
                profile["skills"].append(skill.get("name", ""))
            elif isinstance(skill, str):
                profile["skills"].append(skill)
        profile["skills"] = [s for s in profile["skills"] if s]

        # Experience / positions
        for pos in data.get("positions", []):
            profile["experience"].append({
                "title": pos.get("title", ""),
                "company": pos.get("companyName", pos.get("company", {}).get("name", "")),
                "start_date": f"{pos.get('startMonthYear', {}).get('year', '')}",
                "end_date": f"{pos.get('endMonthYear', {}).get('year', 'Present')}",
                "description": pos.get("description", ""),
            })

        # Education
        for edu in data.get("educations", []):
            profile["education"].append({
                "degree": f"{edu.get('degreeName', '')} in {edu.get('fieldOfStudy', '')}".strip(" in"),
                "institution": edu.get("schoolName", ""),
                "end_year": str(edu.get("endMonthYear", {}).get("year", "")),
            })

        # Certifications
        for cert in data.get("certifications", []):
            profile["certifications"].append({
                "name": cert.get("name", ""),
                "issuer": cert.get("authority", ""),
            })

        # Projects
        for proj in data.get("projects", []):
            profile["projects"].append({
                "name": proj.get("title", ""),
                "description": proj.get("description", ""),
            })

        return profile

    def _parse_rapidapi_format(self, data: dict) -> dict:
        """Parse RapidAPI LinkedIn scrape response format."""
        profile = {
            "format": "rapidapi_scrape",
            "name": data.get("fullName", data.get("name", "")),
            "headline": data.get("headline", data.get("title", "")),
            "summary": data.get("summary", data.get("about", "")),
            "location": data.get("location", ""),
            "email": data.get("email", ""),
            "skills": data.get("skills", []),
            "experience": [],
            "education": [],
            "certifications": data.get("certifications", []),
            "projects": data.get("projects", []),
        }

        # Normalize skills to list of strings
        if isinstance(profile["skills"], list):
            profile["skills"] = [
                s.get("name", s) if isinstance(s, dict) else str(s)
                for s in profile["skills"]
            ]

        # Experience
        for exp in data.get("experience", data.get("experiences", [])):
            profile["experience"].append({
                "title": exp.get("title", exp.get("position", "")),
                "company": exp.get("company", exp.get("companyName", "")),
                "start_date": exp.get("startDate", ""),
                "end_date": exp.get("endDate", "Present"),
                "description": exp.get("description", ""),
            })

        # Education
        for edu in data.get("education", data.get("educations", [])):
            profile["education"].append({
                "degree": edu.get("degree", edu.get("degreeName", "")),
                "institution": edu.get("school", edu.get("schoolName", "")),
                "end_year": str(edu.get("endYear", edu.get("graduationYear", ""))),
            })

        return profile

    def _parse_generic(self, data: dict) -> dict:
        """Parse a generic/manual LinkedIn JSON format."""
        return {
            "format": "generic",
            "name": data.get("name", data.get("full_name", "")),
            "headline": data.get("headline", data.get("title", "")),
            "summary": data.get("summary", data.get("about", data.get("bio", ""))),
            "location": data.get("location", ""),
            "email": data.get("email", ""),
            "skills": data.get("skills", []),
            "experience": data.get("experience", data.get("work", [])),
            "education": data.get("education", []),
            "certifications": data.get("certifications", data.get("certs", [])),
            "projects": data.get("projects", []),
            "raw": data,  # Keep original for LLM extraction
        }
