# Approach Document — SHL Assessment Recommendation Agent

## Architecture

The service is a stateless FastAPI app (`/health`, `/chat`). Each `/chat` call
receives the full message history and returns a structured response; no
server-side conversation state is kept, matching the spec.

Three components:

1. **Catalog loader** (`app/catalog.py`) — fetches the SHL product catalog JSON
   once at startup, normalizes heterogeneous field names (`name`/`title`,
   `url`/`link`, `test_type`/`category`, etc.) into a flat schema, and filters
   out Pre-packaged Job Solutions using name/category heuristics, keeping only
   Individual Test Solutions. Result is cached to disk so a transient upstream
   failure doesn't take the service down on restart.
2. **Retriever** (`app/retrieval.py`) — TF-IDF (word + bigram) over each item's
   name, description, test type, and job level, with cosine similarity ranking
   and optional test-type filtering. No external vector DB: the catalog is
   small enough (a few hundred items) that TF-IDF gives strong, fast, fully
   local lexical matching without embedding API cost or infra.
3. **Agent** (`app/agent.py`) — a two-stage LLM design using Claude (Sonnet):
   - **Stage 1 (router)**: a single structured-JSON call classifies the turn
     into `clarify | recommend | compare | refuse`, extracting a cumulative
     search query (combining old + new constraints across the whole
     conversation, so refinements like "actually, add personality tests"
     compose rather than reset) and an optional test-type filter.
   - **Stage 2 (grounding)**: for `recommend`/`compare`, the actual catalog
     items returned by the retriever (never the LLM's own knowledge) are
     deterministically formatted, and a second LLM call only writes natural
     language *around* that fixed list — it is explicitly instructed not to
     introduce any name/URL not present in the data passed to it. This
     separation is the main anti-hallucination mechanism: the LLM cannot
     invent a URL because URLs never originate from generation, only from
     catalog lookup.

## Conversational behaviors

- **Clarify**: router refuses to call `recommend` when there's no usable
  signal (no role/skill/competency at all), asking one targeted follow-up.
  It's instructed not to over-clarify once enough signal exists (role, JD
  text, or an explicit refinement is sufficient).
- **Recommend**: router builds a cumulative query from the whole transcript,
  not just the latest message, so context isn't lost turn to turn (necessary
  since the API is stateless and the only "memory" is the message list).
- **Refine**: handled by the same `recommend` path — the router always
  re-reads the full history, so "actually, add personality tests" merges into
  the existing query plus a `P` test-type hint rather than starting fresh.
- **Compare**: a dedicated path does fuzzy name matching against the catalog
  for both/all mentioned assessments and feeds only their catalog
  descriptions/test types to the LLM, returning empty `recommendations`
  (it's an explanatory answer, not a shortlist).
- **Refusal/scope**: the router's system prompt explicitly enumerates
  out-of-scope categories (general HR/legal advice, prompt injection, unrelated
  topics) and routes them to a templated refusal that doesn't touch the
  catalog or the LLM's free-form generation, keeping refusals consistent and
  injection-resistant (the router itself is told to ignore embedded
  instructions in user content).

## Schema compliance & limits

Pydantic models on the FastAPI side enforce the exact response shape; the
agent layer caps `recommendations` to 10 items and only sets
`end_of_conversation: true` on a turn where a shortlist was actually
delivered (matching the harness's simulated user, who ends the conversation
once it receives a shortlist). All other turns return `false`.

## Evaluation approach

Given sandbox network restrictions (no access to `shl.com` or the catalog
host from this environment — only package registries and the Anthropic API
were reachable), end-to-end validation here used:
1. A representative sample catalog matching the expected JSON shape, to
   exercise the loader/filter/cache logic.
2. Direct unit-level checks of the retriever against representative queries
   (e.g. "Java developer, mid-level, works with stakeholders" correctly
   surfaces Java coding tests above unrelated items).
3. A structural smoke test of `handle_chat` with the router/reply LLM calls
   stubbed, confirming the response always matches the required JSON schema
   and that recommendations only ever come from catalog data.

In a full deployment, the intended iteration loop is: run the 10 provided
public traces against `/chat`, compute Recall@10 per trace against the
labeled shortlist, and inspect router JSON outputs on misses to tighten the
query-extraction prompt (e.g. adding explicit test-type letter mappings,
which was added after noticing "personality" wasn't reliably mapped to `P`
without an explicit instruction).

## What didn't work / tradeoffs

- A single-call (no router/reply split) design was tried first but made
  grounding unreliable — the model would occasionally paraphrase or merge
  catalog names. Splitting into "decide" then "describe-only-given-data"
  fixed this and is the main quality lever in the design.
- A full embedding-based vector store was considered but skipped: TF-IDF was
  sufficient given catalog size and keeps the deployment dependency-free
  (no API key/cost for embeddings, no vector DB to host).

## AI tool usage

Claude (this assistant) was used directly to scaffold, write, and structurally
test the FastAPI service, catalog parser, retriever, and prompts described
above.
