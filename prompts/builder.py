"""
Prompt Builder — costruisce il prompt arricchito da mandare ad Adobe Firefly.

Combina:
  - metadati del brief (collection, product, channel, mood)
  - visual description delle immagini selezionate dal DAM
  - tone dei copy asset selezionati

Output: una stringa prompt ottimizzata per Firefly Image Generation API.
"""
from __future__ import annotations
import os

from app.models import WorkfrontTaskPayload, SelectedImage, SelectedAsset


FIREFLY_PROMPT_TEMPLATE = """
Generate a high-quality marketing image for a premium beauty and wellness brand.

Brand context:
- Collection: {collection}
- Product: {product}
- Campaign objective: {objective}
- Channel: {channel}
- Target audience: {audience} ({age_segment})
- Market: {market}
- Visual mood / tone: {visual_mood}

Visual reference (from approved DAM assets):
{visual_references}

Copy tone guidance (from approved content fragments):
{copy_tone}

Image requirements:
- Style: premium, editorial, {visual_mood}
- Composition: optimized for {channel} placement ({placement_hints})
- Do NOT include any text overlay or logo
- Photorealistic, brand-safe, no faces unless described
""".strip()


def build_firefly_prompt(
    task: WorkfrontTaskPayload,
    images: list[SelectedImage],
    assets: list[SelectedAsset],
) -> str:
    """Assemble a structured prompt for Adobe Firefly from brief + DAM selections."""

    # Build visual reference block from top images
    visual_refs = "\n".join([
        f"- [{img.placement_hint}] {img.visual_description}"
        for img in images[:2]
    ]) or "No specific visual reference — use brand defaults."

    # Build copy tone block
    copy_tones = list({a.tone for a in assets if a.tone})
    copy_tone_str = ", ".join(copy_tones) if copy_tones else "luxury, premium"

    # Placement hints from images
    placements = list({img.placement_hint for img in images})
    placement_str = ", ".join(placements) if placements else task.channel.value

    prompt = FIREFLY_PROMPT_TEMPLATE.format(
        collection=task.collection,
        product=task.product or "hero product",
        objective=task.objective,
        channel=task.channel.value,
        audience=task.audience.value,
        age_segment=task.age_segment.value,
        market=task.market,
        visual_mood=task.visual_mood or "luxury",
        visual_references=visual_refs,
        copy_tone=copy_tone_str,
        placement_hints=placement_str,
    )
    return prompt


def enrich_prompt_with_llm(base_prompt: str, model: str = "gpt-4o") -> str:
    """
    Optional: call OpenAI to refine/expand the Firefly prompt.
    Falls back to base_prompt if OPENAI_API_KEY is not set or APP_MODE=demo.
    """
    if os.getenv("APP_MODE", "demo") == "demo":
        return base_prompt

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return base_prompt

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert Adobe Firefly prompt engineer for premium beauty brands. "
                        "Refine the following image generation prompt to be more precise, vivid, and "
                        "brand-safe. Keep it under 400 words. Do not add brand names or text overlays."
                    ),
                },
                {"role": "user", "content": base_prompt},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[PromptBuilder] LLM enrichment failed, using base prompt. Error: {e}")
        return base_prompt