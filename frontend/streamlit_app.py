import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import streamlit as st

from app.models import (
    WorkfrontSimplePayload, WorkfrontStatus,
    Season, Scope
)
from dam.selector import resolve_brief
from orchestrator.weave_simulator import run_pipeline

CATALOG_PATH = Path(__file__).parent.parent / "dam" / "catalog.json"

st.set_page_config(
    page_title="FullForce — Content Gen PoC",
    page_icon="🎨",
    layout="wide",
)

st.title("🎨 FullForce Content Generation PoC")
st.caption(
    "Workfront invia product_id + season + scope → "
    "DAM risolve prodotto + sfondo → Firefly genera l'immagine"
)
st.divider()

# ── Carica lista prodotti dal catalog ─────────────────────────────────────────
@st.cache_data
def load_product_ids():
    with open(CATALOG_PATH) as f:
        cat = json.load(f)
    return {f"{p['product_id']} — {p['name']}": p['product_id'] for p in cat["products"]}

product_map = load_product_ids()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("📋 Workfront Payload")
    st.markdown("_Simula il payload semplificato che arriva da Workfront_")

    task_id     = st.text_input("Task ID", value="demo-001")
    product_label = st.selectbox("Product", list(product_map.keys()))
    product_id  = product_map[product_label]
    season      = st.selectbox("Season", ["spring", "summer", "autumn", "winter", "evergreen"])
    scope       = st.selectbox("Scope / Channel", ["email", "social", "landing", "all"])

    run_btn = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

# ── Preview brief risolto ─────────────────────────────────────────────────────
if product_id:
    try:
        preview_payload = WorkfrontSimplePayload(
            task_id="preview",
            project_id="proj-preview",
            status=WorkfrontStatus.CONTENT_GENERATION,
            product_id=product_id,
            season=Season(season),
            scope=Scope(scope),
        )
        brief = resolve_brief(preview_payload)
        with st.sidebar:
            st.divider()
            st.markdown("**🔍 Brief risolto dal DAM**")
            st.markdown(f"- **Prodotto**: {brief.product.name}")
            st.markdown(f"- **Collezione**: {brief.product.collection}")
            st.markdown(f"- **Sfondo**: {brief.background.name}")
            st.markdown(f"- **Mood**: {brief.background.mood}")
            st.markdown(f"- **Tone**: {brief.product.tone}")
    except Exception as e:
        with st.sidebar:
            st.warning(f"Preview non disponibile: {e}")

# ── Main ──────────────────────────────────────────────────────────────────────
if run_btn:
    payload = WorkfrontSimplePayload(
        task_id=task_id,
        project_id="proj-demo",
        status=WorkfrontStatus.CONTENT_GENERATION,
        product_id=product_id,
        season=Season(season),
        scope=Scope(scope),
    )

    with st.spinner("⚙️ Orchestrating pipeline..."):
        try:
            result = asyncio.run(run_pipeline(payload))
        except Exception as e:
            st.error(f"Pipeline error: {e}")
            st.stop()

    st.success("✅ Pipeline complete — ready for Workfront Review")
    st.divider()

    col_img, col_copy = st.columns([1, 1])

    with col_img:
        st.subheader("🖼️ Generated Image")
        st.image(result.generated_image_url, use_column_width=True)

    with col_copy:
        st.subheader("✍️ Generated Copy")
        st.info(result.generated_copy)
        st.markdown(f"**Product ID**: `{result.product_id}`")
        st.markdown(f"**Background**: `{result.background_id}`")
        st.markdown(f"**Season**: `{result.season}` | **Scope**: `{result.scope}`")

    with st.expander("🔍 Firefly Prompt", expanded=False):
        st.code(result.prompt_used, language="text")

    with st.expander("📦 Raw JSON", expanded=False):
        st.json(result.model_dump())

else:
    st.info("👈 Seleziona il prodotto, la stagione e lo scope nella sidebar, poi clicca **Run Pipeline**")

    st.markdown("""
    ### Flusso semplificato v2

    ```
    Workfront
    └── POST /webhook/workfront
        { task_id, product_id, season, scope }
              │
              ▼
    dam/selector.py
    ├── Lookup prodotto in catalog.json
    └── Scoring sfondi (season + scope + tone affinity)
              │
              ▼
    prompts/builder.py → Firefly prompt
              │
              ▼
    firefly/client.py → immagine generata
              │
              ▼
    workfront_mock/client.py → upload + stato Review
    ```
    """)