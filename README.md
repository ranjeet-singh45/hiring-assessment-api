# Hiring Assessment Recommendation API

A stateless conversational agent that helps recruiters and hiring managers find the right
assessments for any role — through natural dialogue rather than keyword search.

## What it does

- Asks clarifying questions when the hiring need is vague
- Recommends 1–10 relevant assessments once it has enough context
- Refines recommendations mid-conversation when requirements change
- Compares specific assessments when asked
- Stays on topic — refuses general HR advice, legal questions, and off-scope requests

## Run locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...        # or use a .env file
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The service fetches and caches the assessment catalog on startup. Subsequent
restarts use the cached version so the service comes up instantly even if the
upstream catalog endpoint is temporarily unreachable.

## API

### GET /health
Returns `{"status": "ok"}` when the service is ready.

### POST /chat

**Request:**
```json
{
  "messages": [
    {"role": "user", "content": "I am hiring a mid-level Java developer"},
    {"role": "assistant", "content": "What competencies matter most for this role?"},
    {"role": "user", "content": "Strong OOP skills and stakeholder communication"}
  ]
}
```

**Response:**
```json
{
  "reply": "Here are assessments that fit a mid-level Java developer...",
  "recommendations": [
    {
      "name": "Java 8 (New)",
      "url": "https://www.shl.com/...",
      "test_type": "K"
    }
  ],
  "end_of_conversation": true
}
```

- `recommendations` is empty while the agent is gathering context
- `recommendations` has 1–10 items when the agent commits to a shortlist
- `end_of_conversation` is `true` only when the agent considers the task complete
- The API is fully stateless — send the full conversation history on every request

## Deploy

A `Dockerfile` is included. Deploy to any container platform:

```bash
docker build -t hiring-assessment-api .
docker run -e GROQ_API_KEY=gsk_... -p 8000:8000 hiring-assessment-api
```

Or deploy directly to Render / Fly / Railway / HF Spaces without Docker —
just set the build command to `pip install -r requirements.txt` and the
start command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq API key for LLM calls |

## Tech stack

- **FastAPI** — API framework
- **Groq** (llama-3.3-70b-versatile) — LLM for routing and reply generation
- **TF-IDF** — lightweight local retrieval over the assessment catalog
- **httpx** — catalog fetching
- **Pydantic** — request/response validation
