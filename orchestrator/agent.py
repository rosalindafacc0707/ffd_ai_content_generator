"""
AgenticOrchestrator — sistema agentico con tool calling.

L'LLM (GPT-4o) riceve il brief e ha accesso a 3 tool:
  1. get_available_backgrounds → lista sfondi filtrati per season/scope
  2. get_product_info          → info e filename del prodotto richiesto
  3. compose_image             → compone sfondo + prodotto e restituisce il path

Il loop agentico continua finché l'LLM chiama compose_image
(o fino a max_iterations come safety net).

In APP_MODE=demo: salta l'LLM e usa la selezione deterministica dal DAM selector.
"""
from __future__ import annotations
import json
import logging
import os
from pathlib import Path
from typing import Any

from app.config import settings
from app.models import WorkfrontSimplePayload, Season, Scope
from dam.selector import resolve_brief
from composer.image_composer import compose

logger = logging.getLogger(__name__)

DAM_PATH     = Path(os.getenv("DAM_LOCAL_PATH", "./dam"))
CATALOG_PATH = DAM_PATH / "catalog.json"


def _load_catalog() -> dict:
    with open(CATALOG_PATH) as f:
        return json.load(f)


def _config_value(env_name: str, settings_name: str, default: str = "") -> str:
    if env_name in os.environ:
        return os.environ[env_name]
    return str(getattr(settings, settings_name, default) or default)


# ── Tool definitions (OpenAI function calling format) ─────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_available_backgrounds",
            "description": (
                "Returns a list of available background images from the DAM, "
                "filtered by season and scope. Use this to see what backgrounds "
                "are available before deciding which one to use."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "season": {
                        "type": "string",
                        "enum": ["spring", "summer", "autumn", "winter", "evergreen"],
                        "description": "The campaign season",
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["email", "social", "landing", "all"],
                        "description": "The output channel",
                    },
                },
                "required": ["season", "scope"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_product_info",
            "description": (
                "Returns metadata and the image filename for a specific product "
                "from the DAM catalog. Use this to confirm the product exists "
                "before composing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID, e.g. PROD_001",
                    },
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compose_image",
            "description": (
                "Composes the final campaign image by combining a background "
                "and a product image from the DAM. Returns the local path of "
                "the composed PNG. Call this once you have decided which "
                "background and product to use."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "background_id": {
                        "type": "string",
                        "description": "The background_id from the DAM, e.g. BG_001",
                    },
                    "product_id": {
                        "type": "string",
                        "description": "The product_id from the DAM, e.g. PROD_001",
                    },
                    "layout": {
                        "type": "string",
                        "enum": ["center", "bottom_center", "left", "right"],
                        "description": (
                            "Layout of the product on the background. "
                            "bottom_center for email/landing, "
                            "right or left for social."
                        ),
                    },
                    "brightness": {
                        "type": "number",
                        "description": (
                            "Background brightness adjustment: "
                            "0.8=darker, 1.0=neutral, 1.2=brighter. "
                            "Use darker for luxury/winter, brighter for spring/summer."
                        ),
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Brief explanation of why you chose this combination.",
                    },
                },
                "required": ["background_id", "product_id", "layout", "brightness", "reasoning"],
            },
        },
    },
]


# ── Tool execution ─────────────────────────────────────────────────────────────

def _tool_get_available_backgrounds(season: str, scope: str) -> list[dict]:
    catalog = _load_catalog()
    results = []
    for bg in catalog["backgrounds"]:
        if bg["season"] in (season, "evergreen") and (
            scope in bg["scope"] or "all" in bg["scope"]
        ):
            results.append({
                "background_id": bg["background_id"],
                "name": bg["name"],
                "season": bg["season"],
                "mood": bg["mood"],
                "image_file": bg["image_file"],
            })
    return results


def _tool_get_product_info(product_id: str) -> dict:
    catalog = _load_catalog()
    for p in catalog["products"]:
        if p["product_id"] == product_id:
            return {
                "product_id": p["product_id"],
                "name": p["name"],
                "collection": p["collection"],
                "tone": p["tone"],
                "category": p["category"],
                "description": p["description"],
                "image_file": p["image_file"],
                "seasons": p["seasons"],
            }
    return {"error": f"Product {product_id} not found"}


def _tool_compose_image(
    background_id: str,
    product_id: str,
    layout: str,
    brightness: float,
    reasoning: str,
    scope: str,
) -> dict:
    catalog = _load_catalog()

    bg_file = next(
        (b["image_file"] for b in catalog["backgrounds"] if b["background_id"] == background_id),
        None,
    )
    prod_file = next(
        (p["image_file"] for p in catalog["products"] if p["product_id"] == product_id),
        None,
    )

    if not bg_file:
        return {"error": f"Background {background_id} not found"}
    if not prod_file:
        return {"error": f"Product {product_id} not found"}

    out_path = compose(
        bg_file=bg_file,
        product_file=prod_file,
        scope=scope,
        layout=layout,
        brightness=brightness,
    )

    return {
        "success": True,
        "output_path": out_path,
        "background_id": background_id,
        "product_id": product_id,
        "layout": layout,
        "brightness": brightness,
        "reasoning": reasoning,
    }


def _dispatch_tool(name: str, args: dict, scope: str) -> Any:
    if name == "get_available_backgrounds":
        return _tool_get_available_backgrounds(**args)
    elif name == "get_product_info":
        return _tool_get_product_info(**args)
    elif name == "compose_image":
        return _tool_compose_image(**args, scope=scope)
    else:
        return {"error": f"Unknown tool: {name}"}


# ── Agentic loop ───────────────────────────────────────────────────────────────

def _run_deterministic_pipeline(payload: WorkfrontSimplePayload) -> dict:
    logger.info("[Agent] Demo/no-key/fallback mode → deterministic DAM selection")
    brief = resolve_brief(payload)
    catalog = _load_catalog()

    bg_file = next(
        b["image_file"] for b in catalog["backgrounds"]
        if b["background_id"] == brief.background.background_id
    )
    prod_file = next(
        p["image_file"] for p in catalog["products"]
        if p["product_id"] == brief.product.product_id
    )

    layout = "bottom_center" if payload.scope.value in ("email", "landing") else "right"
    brightness = 0.85 if payload.season.value in ("winter", "autumn") else 1.0

    out_path = compose(
        bg_file=bg_file,
        product_file=prod_file,
        scope=payload.scope.value,
        layout=layout,
        brightness=brightness,
    )

    return {
        "output_path": out_path,
        "background_id": brief.background.background_id,
        "product_id": brief.product.product_id,
        "reasoning": (
            f"Deterministic selection: best background for {payload.season.value} "
            f"+ {payload.scope.value} scope with {brief.product.tone} tone."
        ),
        "prompt_used": "deterministic — no LLM called in demo/fallback mode",
        "mode": "deterministic",
    }


def run_agentic_pipeline(payload: WorkfrontSimplePayload) -> dict:
    """
    Runs the agentic loop.

    Returns dict with:
      output_path   → local path of the composed PNG
      background_id → chosen background
      product_id    → product used
      reasoning     → LLM explanation
      prompt_used   → full system prompt sent to LLM
      mode          → 'agent' or 'deterministic'
    """
    app_mode = _config_value("APP_MODE", "app_mode", "demo")
    openai_api_key = _config_value("OPENAI_API_KEY", "openai_api_key")

    # ── DEMO / NO API KEY → deterministic DAM selection ──────────────────────
    if app_mode == "demo" or not openai_api_key:
        return _run_deterministic_pipeline(payload)

    # ── AGENT MODE (GPT-4o with tool calling) ────────────────────────────────
    from openai import OpenAI
    client = OpenAI(api_key=openai_api_key)

    catalog = _load_catalog()
    product_info = _tool_get_product_info(payload.product_id)

    system_prompt = f"""You are a creative director AI for a premium beauty brand.
Your task is to compose a campaign image for a specific product by selecting
the best background from the DAM library and composing the final image.

STRICT RULES:
- You MUST use ONLY images available in the DAM (use the tools to check).
- You MUST call compose_image exactly once as your final action.
- Do NOT generate or describe images — only select and compose from the DAM.
- Choose the background that best matches the season, scope and product tone.

Campaign brief:
- Product ID: {payload.product_id}
- Product name: {product_info.get('name', 'unknown')}
- Collection: {product_info.get('collection', 'unknown')}
- Tone: {product_info.get('tone', 'luxury')}
- Season: {payload.season.value}
- Scope / Channel: {payload.scope.value}
- Task ID: {payload.task_id}

Start by calling get_available_backgrounds to see what is available,
then call get_product_info to confirm the product, then call compose_image."""

    messages = [{"role": "system", "content": system_prompt}]
    logger.info(f"[Agent] Starting agentic loop — task={payload.task_id}")

    max_iterations = 6
    final_result = None

    for iteration in range(max_iterations):
        logger.info(f"[Agent] Iteration {iteration + 1}/{max_iterations}")

        response = client.chat.completions.create(
            model=_config_value("LLM_MODEL", "llm_model", "gpt-4o"),
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3,
        )

        msg = response.choices[0].message
        messages.append(msg)

        # Se non ci sono tool calls → risposta finale testo (non dovrebbe succedere)
        if not msg.tool_calls:
            logger.warning(f"[Agent] No tool calls at iteration {iteration + 1} — stopping")
            break

        # Esegui ogni tool call
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments)

            logger.info(f"[Agent] Tool call → {tool_name}({tool_args})")
            result = _dispatch_tool(tool_name, tool_args, payload.scope.value)
            logger.info(f"[Agent] Tool result → {json.dumps(result)[:200]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(result),
            })

            # compose_image è l'azione finale
            if tool_name == "compose_image" and result.get("success"):
                final_result = result
                final_result["prompt_used"] = system_prompt
                final_result["mode"] = "agent"
                break

        if final_result:
            break

    if not final_result:
        logger.error("[Agent] compose_image never called — falling back to deterministic")
        return _run_deterministic_pipeline(payload)

    logger.info(f"[Agent] Done — output={final_result['output_path']}")
    return final_result
