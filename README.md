# Lumen — Agentic Picture Editing

<p align="center">
  <img alt="Python"     src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI"    src="https://img.shields.io/badge/FastAPI-0.141-009688?logo=fastapi&logoColor=white">
  <img alt="LangGraph"  src="https://img.shields.io/badge/LangGraph-1.2-1C3C3C?logo=langchain&logoColor=white">
  <img alt="OpenAI"     src="https://img.shields.io/badge/LLM-gpt--5--mini%20%C2%B7%20gpt--image--2-412991?logo=openai&logoColor=white">
  <img alt="React"      src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-6.0-3178C6?logo=typescript&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-17-4169E1?logo=postgresql&logoColor=white">
  <img alt="Docker"     src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
</p>

> Lumen is an AI editor for product photos. Type what you want, like *"remove the background and put the mug on a marble counter"*, and an agent plans the edit, shows you the steps, and applies them to a layered canvas you can keep editing by hand.

## Try it live

**<https://lumen.zxuhan.me/>**

Sign up with any username, upload a photo, and describe the edit in the chat.

---

## Architecture

<p align="center">
  <img src="docs/architecture.svg" alt="Lumen architecture: React editor, FastAPI with the planner, Redis queue, ARQ worker, OpenAI models, PostgreSQL and object storage" width="560">
</p>

The API plans each instruction and queues its steps. A separate ARQ worker runs them and publishes progress to Redis, which the API streams to the browser over SSE.

---

## The agent

The agent plans with the same 22 tools as the toolbar. Each tool is one `ToolSpec`: a Pydantic parameter model, a description written for the model, and an executor.

**What it can do**

- **Generate** (gpt-image-2): product images from a prompt, plus marketing shots (product, scene, model, poster).
- **AI edits** (gpt-image-2): replace the background, expand the canvas, upscale, and erase or replace a selected region.
- **Local vision** (ONNX models on the worker): remove the background (rembg), split an image into editable layers (rembg + RapidOCR), and extract the selected object to its own layer.
- **Pixels** (Pillow): adjust colors with 11 parameters, crop, and export 1:1 / 4:5 / 9:16 ad sizes without cropping the subject.
- **Layers:** move, scale, rotate, flip, reorder, set opacity and visibility, and edit text layers.
- **Batch:** apply one edit to many images at once.

**How a request becomes a plan**

| Stage | What it does |
|---|---|
| **Context** (`services/agent.describe`) | Summarizes the canvas for the model: size, layers from bottom to top, and the current selection. |
| **Planner** (`agent/llm.py`, `agent/graph.py`) | gpt-5-mini with all 22 tool schemas bound, generated from the tools' Pydantic models. The system prompt holds the editing rules, such as one step per layer, `replace_region` to recolor, and `adjust_image` only for brightness and color temperature. Runs as a LangGraph `plan → verify` graph. |
| **Verifier** (`agent/plan.py`) | Never runs the model's output as-is: rejects unknown tools, validates every parameter with the toolbar's Pydantic model, orders steps by their dependencies, and rejects cycles and plans over 8 steps. |
| **Confirmation** | Single steps run right away; multi-step plans wait for the user. An active selection is pinned to the region tools, so the plan edits what the user selected. |
| **Executor** (`tasks/tools.py`) | Queues each step whose dependencies have succeeded as a tool run on the worker, and advances the plan as runs finish. |

---

## Agent lifecycle

<p align="center">
  <img src="docs/agent-lifecycle.svg" alt="Agent lifecycle: planning, confirmation for multi-step plans, running, then succeeded, failed (retryable), or canceled" width="340">
</p>

A failed step can be retried, and cancelling stops every step that hasn't started.

---

## Highlights

- **Edits stay inside the selection:** region edits are composited back through the selection mask, so pixels outside it never change.
- **Any aspect ratio:** gpt-image-2 renders exact sizes, and fixed-size models get a padded input that is cropped back, so nothing is stretched. Outpainting paints only the new border.
- **Fast click-to-select:** SAM caches the image embedding, so later clicks only run the small decoder.
- **Tests that cost nothing:** 175 tests, mostly against real PostgreSQL, Redis, and MinIO, with a fake planner and a mock image provider. `app/eval` scores the image pipeline by alpha IoU, PSNR, or MAE.

---

## Tech stack

| Layer    | Stack |
|----------|-------|
| Backend  | Python 3.13 · FastAPI 0.141 · SQLAlchemy 2.0 (async, asyncpg) · Alembic · ARQ · Pydantic 2 · LangGraph 1.2 · LangChain (core + OpenAI) · boto3 · Pillow · OpenCV |
| AI       | OpenAI gpt-5-mini (planner, tool calling) and gpt-image-2 (generation and edits) · local ONNX models: rembg, SAM ViT-B (quantized), RapidOCR |
| Storage  | PostgreSQL 17 · Redis 7 (job queue and pub/sub) · Cloudflare R2 / MinIO (S3 API) |
| Frontend | React 19 · TypeScript 6 · Vite 8 · Konva 10 + react-konva · TanStack Query 5 · Zustand 5 · React Router 7 · Tailwind CSS 4 |
| Infra    | Multi-stage Docker build · Docker Compose profiles · Caddy (automatic HTTPS) · GitHub Actions CI/CD |

---

## Quickstart

### Prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- **Python 3.13+** with [uv](https://docs.astral.sh/uv/), and **Node 20+**
- An **OpenAI API key** (optional): without one, images are placeholders and the chat is off

### Run locally

```bash
git clone https://github.com/zxuhan/lumen.git
cd lumen
cp .env.example .env
# Set OPENAI_API_KEY and IMAGE_PROVIDER=openai for real AI; the defaults run free in mock mode
docker compose up -d                                # PostgreSQL, Redis, MinIO

cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 7302   # terminal 1: API
uv run arq app.worker.WorkerSettings               # terminal 2: worker

cd frontend && npm install && npm run dev          # terminal 3, from the repo root: frontend
```

| Service       | URL                                       |
|---------------|-------------------------------------------|
| Frontend      | <http://localhost:7301>                   |
| API health    | <http://localhost:7302/api/health>        |
| API docs      | <http://localhost:7302/api/docs>          |
| MinIO console | <http://localhost:7314> (`lumen` / `lumen_dev`) |

> **Costs and first run.** Chat planning needs `OPENAI_API_KEY` even in mock mode. With `IMAGE_PROVIDER=openai`, a medium-quality image costs a few cents. The first background removal or click-to-select downloads the local models (about 1 GB). To check the key and models without the rest of the stack: `uv run python -m scripts.smoke_openai`.

### Tests

```bash
cd backend
uv run pytest        # needs the Docker services above; no API calls
```

---

## Project layout

```
backend/
├── app/
│   ├── agent/            # llm.py (tool binding) · graph.py (plan → verify) · plan.py (validation, ordering)
│   ├── tools/            # 22 ToolSpecs shared by the toolbar and the agent
│   ├── services/         # agent turns, tool runs, sessions, assets, batches, exports
│   ├── edits/            # pixel pipeline: masks, layer rendering, SAM, OCR, layer splitting
│   ├── providers/        # image providers: mock · openai_images
│   ├── routers/          # REST and SSE endpoints
│   ├── models/ schemas/  # SQLAlchemy models · Pydantic schemas
│   ├── tasks/ worker.py  # ARQ worker and the tool-run task
│   ├── eval/             # image-pipeline regression harness
│   └── events.py · storage.py · security.py · config.py
├── migrations/           # Alembic
├── scripts/              # smoke and end-to-end checks
└── tests/
frontend/src/
├── components/editor/    # canvas stage, toolbar, layer panel, chat
└── pages/ hooks/ stores/ lib/ api/
.github/workflows/ci.yml  # CI and deploy
docs/                     # D2 diagram sources and rendered SVGs
Caddyfile · Dockerfile · docker-compose.yml
```
