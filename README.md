# FullForce AI Content Generator

Proof of concept for an AI content generation pipeline connected to Adobe Workfront. It receives a minimal brief, resolves the product and background from a local DAM catalog, builds a prompt, generates an image, and prepares the result for Workfront review.

## What It Does

The repository simulates this flow:

```text
Workfront payload
  product_id + season + scope
        |
        v
Local DAM
  catalog.json -> best product + background match
        |
        v
Prompt builder
  structured marketing prompt
        |
        v
Image engine
  demo | local Stable Diffusion | Adobe Firefly live
        |
        v
Workfront
  attachment + Review status
```

In the current API, the payload also includes technical Workfront fields: `task_id`, `project_id`, and `status`. These simulate the Workfront task context. The actual brief and selection logic is driven by the three business fields: `product_id`, `season`, and `scope`.

## Project Structure

```text
app/
  main.py          FastAPI app: Workfront webhook, manual trigger, healthcheck
  models.py        Pydantic models for payloads, DAM catalog, and results
  config.py        Configuration loaded from .env

dam/
  catalog.json     Product and background catalog
  selector.py      Resolves product_id + season + scope into a full brief
  products/        Local product images
  backgrounds/     Local background images
  generated/       Images generated in sd/live modes

orchestrator/
  weave_simulator.py  Main pipeline

prompts/
  builder.py       Firefly/SD prompt builder + optional OpenAI enrichment

firefly/
  client.py        Image client: demo, local Stable Diffusion, or Firefly

workfront_mock/
  client.py        Mock/live upload to Workfront

frontend/
  streamlit_app.py Streamlit demo UI with generation and history views
```

## Generation Modes

`APP_MODE=demo`
: Does not call external services. Returns a placeholder image from `picsum.photos`.

`APP_MODE=sd`
: Calls a local AUTOMATIC1111 instance through `SD_API_URL` and saves the PNG to `dam/generated/`.

`APP_MODE=live`
: Calls Adobe Firefly and then Workfront using credentials from `.env`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create or update `.env`:

```env
APP_MODE=demo
WEBHOOK_SECRET=changeme
LOG_LEVEL=INFO

# Local Stable Diffusion, only for APP_MODE=sd
SD_API_URL=http://localhost:7860

# Adobe Firefly, only for APP_MODE=live
ADOBE_FIREFLY_CLIENT_ID=
ADOBE_FIREFLY_API_KEY=
ADOBE_IMS_TOKEN=

# Workfront live, only for APP_MODE=live
WORKFRONT_BASE_URL=
WORKFRONT_API_KEY=

# Optional prompt enrichment
OPENAI_API_KEY=
```

## Run The API

```bash
uvicorn app.main:app --reload
```

Healthcheck:

```bash
curl http://127.0.0.1:8000/health
```

Manual trigger:

```bash
curl -X POST http://127.0.0.1:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-demo-001",
    "project_id": "proj-demo",
    "status": "Content Generation",
    "product_id": "PROD_001",
    "season": "spring",
    "scope": "email"
  }'
```

Workfront webhook:

```bash
curl -X POST http://127.0.0.1:8000/webhook/workfront \
  -H "Content-Type: application/json" \
  -H "x-webhook-secret: changeme" \
  -d '{
    "task_id": "task-wf-001",
    "project_id": "proj-wf",
    "status": "Content Generation",
    "product_id": "PROD_004",
    "season": "winter",
    "scope": "landing"
  }'
```

## Run The UI

```bash
streamlit run frontend/streamlit_app.py
```

The UI lets you:

- select a product from `dam/catalog.json`;
- choose `season` and `scope`;
- preview the brief resolved from the DAM;
- run the pipeline;
- inspect the image, copy, prompt, and raw JSON result;
- browse the generated image history in `dam/generated/`.

## Payload And Output

Main input:

```json
{
  "task_id": "task-demo-001",
  "project_id": "proj-demo",
  "status": "Content Generation",
  "product_id": "PROD_001",
  "season": "spring",
  "scope": "email"
}
```

Valid values:

- `season`: `spring`, `summer`, `autumn`, `winter`, `evergreen`
- `scope`: `email`, `social`, `landing`, `all`
- `status`: the pipeline only runs for `Content Generation`

Output:

```json
{
  "task_id": "task-demo-001",
  "generated_image_url": "...",
  "generated_copy": "...",
  "prompt_used": "...",
  "product_id": "PROD_001",
  "background_id": "BG_001",
  "season": "spring",
  "scope": "email",
  "status": "ready_for_review"
}
```

## Background Selection

`dam/selector.py` loads `dam/catalog.json`, finds the product by exact `product_id`, then scores backgrounds using:

- season match;
- `evergreen` background fallback;
- scope compatibility;
- affinity between the product `tone` and the background `mood`.

The resolved brief contains the product, background, season, scope, and local image paths.

## Tests

```bash
pytest
```

## Operational Notes

- `APP_MODE=demo` does not save local images.
- `APP_MODE=sd` requires AUTOMATIC1111 with API access enabled.
- `APP_MODE=live` requires Adobe Firefly and Workfront credentials.
- `OPENAI_API_KEY` is optional. Without it, the prompt builder uses the base prompt.
