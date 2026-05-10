"""
LinkedIn Profile Parser — Parses LinkedIn profile data (JSON export or scraped data).

Converts LinkedIn profile data into a CandidateProfile for unified scoring.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from .resume_parser import CandidateProfile

logger = logging.getLogger(__name__)


class LinkedInParser:
    """Parses LinkedIn profile data into CandidateProfile format."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client

    def parse(self, data: dict | str | Path) -> CandidateProfile:
        """
        Parse LinkedIn profile data into a CandidateProfile.
        
        Args:
            data: Can be:
                - dict: Already parsed JSON data
                - str: JSON string or file path
                - Path: Path to JSON file
                
        Returns:
            CandidateProfile with LinkedIn data mapped
        """
        # Resolve the data to a dict
        if isinstance(data, Path) or (isinstance(data, str) and Path(data).exists()):
            path = Path(data)
            raw = path.read_text(encoding="utf-8")
            profile_data = json.loads(raw)
        elif isinstance(data, str):
            profile_data = json.loads(data)
        elif isinstance(data, dict):
            profile_data = data
        else:
            raise ValueError(f"Unsupported data type: {type(data)}")

        return self._map_to_profile(profile_data)

    def _map_to_profile(self, data: dict) -> CandidateProfile:
        """Map LinkedIn JSON fields to CandidateProfile."""
        
        # Handle various LinkedIn JSON export formats
        # Standard LinkedIn data export format
        name = data.get("name", data.get("full_name", 
               f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()))
        
        # Extract headline/title
        headline = data.get("headline", data.get("title", ""))
        
        # Extract skills
        skills_data = data.get("skills", [])
        if isinstance(skills_data, list):
            if skills_data and isinstance(skills_data[0], dict):
                skills = [s.get("name", s.get("skill", "")) for s in skills_data]
            else:
                skills = skills_data
        else:
            skills = []

        # Extract experience
        experience = []
        exp_data = data.get("experience", data.get("positions", []))
        total_years = 0
        
        for exp in exp_data:
            if isinstance(exp, dict):
                entry = {
                    "title": exp.get("title", ""),
                    "company": exp.get("company", exp.get("companyName", "")),
                    "duration": exp.get("duration", exp.get("timePeriod", "")),
                    "domain": exp.get("industry", exp.get("domain", "")),
                    "highlights": exp.get("description", "").split("\n") if exp.get("description") else [],
                }
                experience.append(entry)
                
                # Estimate years from duration string
                duration_str = str(entry["duration"]).lower()
                import re
                years_match = re.search(r'(\d+)\s*yr', duration_str)
                months_match = re.search(r'(\d+)\s*mo', duration_str)
                if years_match:
                    total_years += int(years_match.group(1))
                if months_match:
                    total_years += int(months_match.group(1)) / 12

        # Extract education
        education = []
        edu_data = data.get("education", [])
        highest_edu = ""
        for edu in edu_data:
            if isinstance(edu, dict):
                degree = edu.get("degree", edu.get("degreeName", ""))
                entry = {
                    "degree": degree,
                    "institution": edu.get("school", edu.get("schoolName", "")),
                    "year": str(edu.get("year", edu.get("endDate", ""))),
                    "field": edu.get("field", edu.get("fieldOfStudy", "")),
                }
                education.append(entry)
                
                # Determine highest education
                deg_lower = degree.lower()
                if "phd" in deg_lower or "doctor" in deg_lower:
                    highest_edu = "PhD"
                elif "master" in deg_lower or "m.s" in deg_lower or "mba" in deg_lower:
                    if highest_edu not in ("PhD",):
                        highest_edu = "Master's"
                elif "bachelor" in deg_lower or "b.s" in deg_lower or "b.tech" in deg_lower:
                    if highest_edu not in ("PhD", "Master's"):
                        highest_edu = "Bachelor's"

        # Extract certifications
        certs = data.get("certifications", [])
        if certs and isinstance(certs[0], dict):
            cert_names = [c.get("name", "") for c in certs]
        else:
            cert_names = certs if isinstance(certs, list) else []

        # Extract projects
        projects = []
        proj_data = data.get("projects", [])
        for proj in proj_data:
            if isinstance(proj, dict):
                projects.append({
                    "name": proj.get("name", proj.get("title", "")),
                    "description": proj.get("description", ""),
                    "technologies": proj.get("technologies", []),
                    "impact": proj.get("impact", ""),
                })

        # Determine current role
        current_title = headline
        current_company = ""
        if experience:
            current_title = experience[0].get("title", headline)
            current_company = experience[0].get("company", "")

        profile = CandidateProfile(
            name=name,
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            location=data.get("location", data.get("locationName", "")),
            current_title=current_title,
            current_company=current_company,
            total_years_experience=round(total_years, 1),
            technical_skills=skills,
            work_experience=experience,
            domains=list(set(e.get("domain", "") for e in experience if e.get("domain"))),
            education=education,
            highest_education=highest_edu,
            certifications=cert_names,
            projects=projects,
            resume_quality_notes="Parsed from LinkedIn profile data",
            source_file="linkedin_profile.json",
        )

        logger.info(f"Parsed LinkedIn profile: {profile.name} — "
                    f"{len(profile.technical_skills)} skills, "
                    f"{total_years:.1f} years experience")
        return profile
