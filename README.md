# SHL Assessment Recommendation Agent

A stateless conversational agent that turns a vague hiring intent into a grounded
shortlist of SHL Individual Test Solutions, with clarification, refinement, and
comparison support.

## Run locally

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

On startup the service fetches the SHL catalog JSON from
`https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json`,
filters it down to Individual Test Solutions (Job Solutions are excluded), and caches
the normalized result to `catalog_cache.json` so restarts don't depend on the
upstream endpoint being reachable.

> Note: this dev sandbox's network egress only allows package registries and
> `api.anthropic.com`, so the live SHL fetch couldn't be exercised here. The
> loader was validated against a representative sample catalog with the same
> shape; it should fetch correctly from any normal deployment environment
> (Render, Fly, Railway, HF Spaces, etc.) with standard internet access.

## Endpoints

- `GET /health` -> `{"status": "ok"}`
- `POST /chat` -> body `{"messages": [{"role": "user"|"assistant", "content": "..."}]}`,
  returns `{"reply": str, "recommendations": [{"name","url","test_type"}] (0-10 items), "end_of_conversation": bool}`

## Deploy

`Dockerfile` included. Any container host works (Render/Fly/Railway/HF Spaces).
Set `ANTHROPIC_API_KEY` as an environment variable on the host.

See `APPROACH.md` for design rationale.
