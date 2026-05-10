# Technical Disclosure — HR Resume Shortlisting Agent

## 1. LLM Chosen

**Model:** LLaMA-3.3-70b-versatile  
**Provider:** Groq (via `groq` Python SDK)  
**Version:** `llama-3.3-70b-versatile` (latest as of deployment)

**Rationale:**
- **Blazing-fast inference** via Groq's LPU (Language Processing Unit) — sub-second latency per call, critical when scoring dozens of resumes synchronously
- **GPT-4 class reasoning** at a fraction of the cost — LLaMA-3.3-70b provides excellent structured JSON extraction and nuanced scoring
- **Free tier** available (sufficient for prototype development and demo)
- **Excellent structured output** — reliably produces valid JSON with 5-dimension rubric scores
- **Large context window** — handles long resumes without truncation
- **Cost-effective** for production — significantly cheaper than GPT-4o or Claude 3.5

## 2. Agent Framework

**Framework:** Custom Python Orchestrator (`agent.py`)  
**Architecture:** Plan-and-Execute (deterministic 7-step sequential pipeline)

**Agent Flow Diagram:**
```
[1. Input] → [2. Parse JD] → [3. Profile] → [4. Score] → [5. Rank] → [6. Report] → [7. Override]
    ↓              ↓               ↓             ↓            ↓            ↓             ↓
 HR uploads    LLM extracts    Parse each    LLM rubric   Sort by      JSON/HTML/    HR adjusts
 JD + resumes  structured      resume into   scoring +    weighted     CSV export    scores with
 + LinkedIn    requirements    structured    TF-IDF       total desc.  with rubric   reason →
 URLs          (JSON)          fields        similarity                breakdown     audit log
```

**Why a custom orchestrator instead of LangChain / CrewAI / AutoGen?**
- The task is inherently **sequential** — each step depends on the previous
- A ReAct loop or multi-agent system adds unnecessary complexity and unpredictability
- Our deterministic pipeline provides **reproducible, auditable results**
- **No infinite agent loops** — saves API costs and ensures reliability
- Easier to debug, test, and audit each step independently
- Direct Groq SDK usage is faster than LangChain's abstraction overhead

## 3. Prompt Design

### Key System Prompts:

**JD Parsing Prompt:**
```
Extract structured requirements from this job description.
Respond ONLY with valid JSON, no markdown:
{"role_title": "...", "required_skills": ["skill1", "skill2"], "experience": "...",
 "education": "...", "certifications": ["cert1"], "key_responsibilities": ["resp1"]}
```
- **Guardrails:** Strict JSON-only output, temperature=0.1, max_tokens=500

**Scoring Prompt:**
```
You are an expert HR analyst. Score the candidate resume against the job description.
Respond ONLY with a single valid JSON object — no markdown, no explanation, no preamble.
Use this exact schema:
{"name": "...", "scores": {"skills_match": {"score": 0, "justification": "one concise line"}, ...}, "recommendation": "hire"}
Each score must be an integer 0-10.
```
- **Scoring guide embedded:** Explicit rubric criteria (e.g., "skills_match: 0=less than 30% match, 5=50-70% match, 10=85%+ match")
- **Semantic grounding:** TF-IDF cosine similarity score injected into prompt as `SEMANTIC SIMILARITY SCORE (TF-IDF cosine): {X}%`
- **Recommendation constraint:** Must be exactly one of: `hire`, `maybe`, `no-hire`

**Prompt Engineering Decisions:**
1. **Low temperature (0.1)** for consistent, reproducible scoring
2. **Semantic match data injected** into prompt to ground LLM reasoning with objective evidence
3. **Explicit rubric criteria** in prompt to prevent score drift
4. **Mandatory justification field** forces reasoning transparency
5. **JSON-only output** with post-processing validation (strip markdown backticks, `json.loads()`)
6. **Score clamping** — all scores validated to [0, 10] range after LLM response

## 4. Security Mitigations

See [SECURITY.md](SECURITY.md) for full details.

**Summary:**
- **Prompt injection detection** via 10+ regex patterns in `security.py`
- **PII masking** in all logs and audit trails (email, phone, SSN, Aadhaar, PAN)
- **API keys** managed via `.env` + `os.getenv()` (never hardcoded, `.env` in `.gitignore`)
- **Output validation:** all scores clamped to [0, 10] range via `validate_score()`
- **File validation:** extension whitelist, 10MB size limit, path traversal detection
- **Human-in-the-loop** as final safety net against hallucinated scores
- **Blind Hiring Mode** — optional PII redaction in UI and all exports for unbiased screening
