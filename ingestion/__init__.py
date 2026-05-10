"""
Ingestion package — handles all input sources for the HR Shortlisting Agent.

Sources supported:
- PDF resumes (via pdfplumber + PyMuPDF fallback)
- DOCX resumes (via python-docx)
- Plain text resumes
- LinkedIn exported JSON
- RapidAPI LinkedIn scrape response
- Job Description (txt/pdf/docx)
"""

from .document_loader import DocumentLoader
from .linkedin_ingestion import LinkedInIngestion

__all__ = ["DocumentLoader", "LinkedInIngestion"]
