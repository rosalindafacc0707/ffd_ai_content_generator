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
      mode          → 'agent' or 'deterministic' or 'ollama'
    """
    app_mode = _config_value("APP_MODE", "app_mode", "demo")
    llm_provider = _config_value("LLM_PROVIDER", "llm_provider", "ollama").lower()
    openai_api_key = _config_value("OPENAI_API_KEY", "openai_api_key")

    # ── DEMO / NO API KEY → deterministic DAM selection ──────────────────────
    if app_mode == "demo":
        return _run_deterministic_pipeline(payload)

    # ── OLLAMA MODE (LLaVA / local multimodal) ───────────────────────────────
    if llm_provider == "ollama":
        return _run_ollama_pipeline(payload)

    # ── AGENT MODE (GPT-4o with tool calling) ────────────────────────────────
    if llm_provider == "openai" and openai_api_key:
        return _run_openai_pipeline(payload)

    # ── FALLBACK ──────────────────────────────────────────────────────────────
    logger.warning(
        f"[Agent] No valid LLM provider configured (provider={llm_provider}, "
        f"has_key={bool(openai_api_key)}). Falling back to deterministic."
    )
    return _run_deterministic_pipeline(payload)


def _run_ollama_pipeline(payload: WorkfrontSimplePayload) -> dict:
    """
    Uses local Ollama (LLaVA or other multimodal model) to decide composition.
    Faster than OpenAI, runs locally, free.
    """
    import httpx

    logger.info(f"[Agent] Using Ollama for task={payload.task_id}")
    ollama_url = _config_value("OLLAMA_API_URL", "ollama_api_url", "http://localhost:11434")
    llm_model = _config_value("LLM_MODEL", "llm_model", "llava")

    catalog = _load_catalog()
    product_info = _tool_get_product_info(payload.product_id)

    # ── Get available backgrounds ─────────────────────────────────────────────
    available_bgs = _tool_get_available_backgrounds(payload.season.value, payload.scope.value)
    bg_list = "\n".join([
        f"- {bg['background_id']}: {bg['name']} ({bg['mood']}, season={bg['season']})"
        for bg in available_bgs
    ])

    prompt = f"""You are a creative director. Choose the best background for this campaign.

Product: {product_info.get('name')} ({product_info.get('tone')} tone)
Collection: {product_info.get('collection')}
Season: {payload.season.value}
Scope: {payload.scope.value}

Available backgrounds:
{bg_list}

RESPOND ONLY with:
BACKGROUND: <background_id>
LAYOUT: <center|bottom_center|left|right>
BRIGHTNESS: <0.8|0.9|1.0|1.1|1.2>
REASONING: <one sentence why>

Example:
BACKGROUND: BG_005
LAYOUT: bottom_center
BRIGHTNESS: 0.9
REASONING: Soft autumn vibes complement the luxury tone perfectly."""

    try:
        logger.info(f"[Agent] Calling Ollama at {ollama_url}...")
        response = httpx.post(
            f"{ollama_url}/api/generate",
            json={
                "model": llm_model,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.3,
            },
            timeout=120.0,
        )
        response.raise_for_status()
        result_text = response.json().get("response", "").strip()
        logger.info(f"[Agent] Ollama response:\n{result_text}")

        # Parse the structured response
        lines = result_text.split("\n")
        bg_id = None
        layout = "bottom_center"
        brightness = 1.0
        reasoning = "Selected by Ollama LLaVA"

        for line in lines:
            if line.startswith("BACKGROUND:"):
                bg_id = line.split(":", 1)[1].strip()
            elif line.startswith("LAYOUT:"):
                layout = line.split(":", 1)[1].strip()
            elif line.startswith("BRIGHTNESS:"):
                try:
                    brightness = float(line.split(":", 1)[1].strip())
                except:
                    brightness = 1.0
            elif line.startswith("REASONING:"):
                reasoning = line.split(":", 1)[1].strip()

        # Validate and fallback
        if not bg_id or bg_id not in [b["background_id"] for b in available_bgs]:
            logger.warning(f"[Agent] Invalid background {bg_id} from Ollama — using fallback")
            bg_id = available_bgs[0]["background_id"] if available_bgs else "BG_001"

        # Compose the image
        result = _tool_compose_image(
            background_id=bg_id,
            product_id=payload.product_id,
            layout=layout,
            brightness=brightness,
            reasoning=reasoning,
            scope=payload.scope.value,
        )

        if result.get("success"):
            result["prompt_used"] = prompt
            result["mode"] = "ollama"
            logger.info(f"[Agent] Ollama pipeline done → {result['output_path']}")
            return result

    except Exception as e:
        logger.error(f"[Agent] Ollama error: {e} — falling back to deterministic")

    return _run_deterministic_pipeline(payload)


def _run_openai_pipeline(payload: WorkfrontSimplePayload) -> dict:
    """OpenAI agent with tool calling (original implementation)."""
    from openai import OpenAI
    openai_api_key = _config_value("OPENAI_API_KEY", "openai_api_key")
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
