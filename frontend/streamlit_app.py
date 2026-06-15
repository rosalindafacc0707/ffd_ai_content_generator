import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import json
import time
import streamlit as st
from PIL import Image

from app.models import (
    WorkfrontSimplePayload, WorkfrontStatus,
    Season, Scope
)
from dam.selector import resolve_brief
from orchestrator.weave_simulator import run_pipeline

CATALOG_PATH  = Path(__file__).parent.parent / "dam" / "catalog.json"
GENERATED_DIR = Path(__file__).parent.parent / "dam" / "generated"

st.set_page_config(
    page_title="FullForce — Content Gen PoC",
    page_icon="🎨",
    layout="wide",
)

# ── Tabs principali ───────────────────────────────────────────────────────────
tab_gen, tab_history = st.tabs(["🚀 Generate", "🗂️ History"])


# ── Carica lista prodotti ─────────────────────────────────────────────────────
@st.cache_data
def load_product_ids():
    with open(CATALOG_PATH) as f:
        cat = json.load(f)
    return {f"{p['product_id']} — {p['name']}": p['product_id'] for p in cat["products"]}


@st.cache_data
def load_catalog_raw():
    with open(CATALOG_PATH) as f:
        return json.load(f)


product_map = load_product_ids()
catalog_raw = load_catalog_raw()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — GENERATE
# ══════════════════════════════════════════════════════════════════════════════
with tab_gen:
    st.title("🎨 FullForce Content Generation PoC")
    st.caption(
        "Workfront invia `product_id + season + scope` → "
        "DAM risolve prodotto + sfondo → motore AI genera l'immagine"
    )
    st.divider()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.header("📋 Workfront Payload")
        st.markdown("_Simula il payload semplificato da Workfront_")

        task_id       = st.text_input("Task ID", value=f"task-{int(time.time())}")
        product_label = st.selectbox("Product", list(product_map.keys()))
        product_id    = product_map[product_label]
        season        = st.selectbox("Season", ["spring", "summer", "autumn", "winter", "evergreen"])
        scope         = st.selectbox("Scope / Channel", ["email", "social", "landing", "all"])

        st.divider()
        app_mode = st.radio(
            "🔧 Generation mode",
            ["demo", "sd", "live"],
            help="demo=placeholder | sd=Stable Diffusion locale | live=Adobe Firefly",
        )
        import os
        os.environ["APP_MODE"] = app_mode

        run_btn = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

        # Preview brief risolto
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
            st.divider()
            st.markdown("**🔍 Brief risolto dal DAM**")
            st.markdown(f"- **Prodotto**: {brief.product.name}")
            st.markdown(f"- **Collezione**: {brief.product.collection}")
            st.markdown(f"- **Sfondo**: {brief.background.name}")
            st.markdown(f"- **Mood**: {brief.background.mood}")
            st.markdown(f"- **Tone**: {brief.product.tone}")
        except Exception as e:
            st.warning(f"Preview non disponibile: {e}")

    # ── Main generate ─────────────────────────────────────────────────────────
    if run_btn:
        payload = WorkfrontSimplePayload(
            task_id=task_id,
            project_id="proj-demo",
            status=WorkfrontStatus.CONTENT_GENERATION,
            product_id=product_id,
            season=Season(season),
            scope=Scope(scope),
        )

        with st.spinner(f"⚙️ Running pipeline in **{app_mode}** mode..."):
            try:
                result = asyncio.run(run_pipeline(payload))
            except Exception as e:
                st.error(f"❌ Pipeline error: {e}")
                st.stop()

        st.success("✅ Pipeline complete — ready for Workfront Review")
        st.divider()

        col_img, col_copy = st.columns([1, 1])

        with col_img:
            st.subheader("🖼️ Generated Image")
            img_url = result.generated_image_url
            if img_url.startswith("file://"):
                local_path = img_url.replace("file://", "")
                st.image(local_path, use_column_width=True)
                st.caption(f"📁 Saved: `{local_path}`")
            else:
                st.image(img_url, use_column_width=True)
                st.caption(f"🔗 URL: `{img_url[:80]}...`")

        with col_copy:
            st.subheader("✍️ Generated Copy")
            st.info(result.generated_copy)
            st.markdown(f"**Product**: `{result.product_id}`")
            st.markdown(f"**Background**: `{result.background_id}`")
            st.markdown(f"**Season**: `{result.season}` | **Scope**: `{result.scope}`")
            st.markdown(f"**Mode**: `{app_mode}`")

        with st.expander("🔍 Firefly / SD Prompt", expanded=False):
            st.code(result.prompt_used, language="text")

        with st.expander("📦 Raw JSON Result", expanded=False):
            st.json(result.model_dump())

    else:
        st.info("👈 Configura il payload nella sidebar e clicca **Run Pipeline**")
        st.markdown("""
        ### Flusso v2
        ```
        Workfront { product_id, season, scope }
                │
                ▼
        DAM catalog.json
        ├── lookup prodotto
        └── scoring sfondo (season + scope + tone affinity)
                │
                ▼
        Prompt builder → testo strutturato
                │
                ▼
        Image engine (demo | SD locale | Firefly)
                │
                ▼
        dam/generated/<timestamp>.png  ←  salvato sul tuo Mac
                │
                ▼
        Workfront → stato Review
        ```
        """)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — HISTORY VIEWER
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.title("🗂️ Generated Images History")
    st.caption(f"Immagini salvate in `{GENERATED_DIR}`")

    col_refresh, col_sort, col_filter = st.columns([1, 1, 2])
    with col_refresh:
        refresh = st.button("🔄 Refresh", use_container_width=True)
    with col_sort:
        sort_order = st.selectbox("Sort", ["Newest first", "Oldest first"], label_visibility="collapsed")
    with col_filter:
        filter_text = st.text_input("🔍 Filter by filename", placeholder="e.g. generated_17...")

    st.divider()

    # Carica immagini dalla cartella generated
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    image_files = sorted(
        GENERATED_DIR.glob("*.png"),
        key=lambda f: f.stat().st_mtime,
        reverse=(sort_order == "Newest first"),
    )

    # Applica filtro
    if filter_text:
        image_files = [f for f in image_files if filter_text.lower() in f.name.lower()]

    if not image_files:
        st.info(
            "Nessuna immagine trovata in `dam/generated/`.\n\n"
            "Genera almeno un'immagine con il tab **🚀 Generate** "
            "usando **APP_MODE=sd** o **APP_MODE=live**.\n\n"
            "In modalità **demo** le immagini sono URL remoti e non vengono salvate localmente."
        )
    else:
        st.markdown(f"**{len(image_files)} immagini** trovate")
        st.divider()

        # Griglia 3 colonne
        cols_per_row = 3
        for i in range(0, len(image_files), cols_per_row):
            row_files = image_files[i : i + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, fpath in zip(cols, row_files):
                with col:
                    try:
                        img = Image.open(fpath)
                        st.image(img, use_column_width=True)
                    except Exception:
                        st.warning(f"Cannot open {fpath.name}")

                    # Metadati sotto ogni immagine
                    mtime = fpath.stat().st_mtime
                    mtime_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
                    size_kb = fpath.stat().st_size / 1024

                    st.caption(f"📁 `{fpath.name}`")
                    st.caption(f"🕐 {mtime_str} · 💾 {size_kb:.0f} KB")

                    # Bottone download
                    with open(fpath, "rb") as f:
                        st.download_button(
                            label="⬇️ Download",
                            data=f,
                            file_name=fpath.name,
                            mime="image/png",
                            key=f"dl_{fpath.name}_{i}",
                            use_container_width=True,
                        )

        # Statistiche in fondo
        st.divider()
        total_size = sum(f.stat().st_size for f in image_files) / (1024 * 1024)
        st.markdown(
            f"📊 **Totale**: {len(image_files)} immagini · "
            f"💾 {total_size:.1f} MB occupati in `dam/generated/`"
        )