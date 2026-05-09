# Agent Service

Python dependencies for this service are managed with `uv`.

## Setup

```bash
uv sync --dev
```

## Run

```bash
uv run uvicorn app.main:app --reload --port 8000
```

## AI Model

This service uses an OpenAI-compatible chat completions API. For DeepSeek, set:

```bash
OPENAI_API_KEY=your-deepseek-api-key
OPENAI_BASE_URL=https://api.deepseek.com
MODEL_NAME=deepseek-v4-flash
```

If `OPENAI_API_KEY` is empty or the model request fails, `/chat/messages` falls back to the local intent-based reply.

## Test

```bash
uv run pytest tests/e2e -q
```

## Seed Mock Orders

```bash
uv run python scripts/seed_orders.py
```

This creates these reusable mock order numbers:

- `ORD-20260508-0001`
- `ORD-20260508-0002`
- `ORD-20260508-0003`

## Lock Dependencies

After changing `pyproject.toml`, refresh the lock file:

```bash
uv lock
```
