"""
Prompt Builder v2
"""
from __future__ import annotations
import os


def build_firefly_prompt_v2(brief) -> str:
    TEMPLATE = """Generate a high-quality marketing image for a premium beauty and wellness brand.

Product:
- Name: {product_name}
- Collection: {collection}
- Category: {category}
- Description: {description}

Visual context:
- Season: {season}
- Background style: {bg_name} — mood: {bg_mood}
- Channel / scope: {scope}
- Tone: {tone}

Composition instructions:
- Place the product prominently in the foreground
- Background should evoke {season} atmosphere: {bg_name}
- Style: premium, editorial, {tone}
- Lighting: natural, soft, coherent with {bg_mood} mood
- Do NOT include any text, logo or watermark
- Photorealistic, brand-safe"""

    return TEMPLATE.format(
        product_name=brief.product.name,
        collection=brief.product.collection,
        category=brief.product.category,
        description=brief.product.description,
        season=brief.season.value,
        bg_name=brief.background.name,
        bg_mood=brief.background.mood,
        scope=brief.scope.value,
        tone=brief.product.tone,
    )


def enrich_prompt_with_llm(base_prompt: str, model: str = "gpt-4o") -> str:
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
                        "Refine the following prompt to be more precise and vivid. "
                        "Keep it under 400 words. No brand names or text overlays."
                    ),
                },
                {"role": "user", "content": base_prompt},
            ],
            temperature=0.4,
            max_tokens=600,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[PromptBuilder] LLM enrichment failed: {e}")
        return base_prompt