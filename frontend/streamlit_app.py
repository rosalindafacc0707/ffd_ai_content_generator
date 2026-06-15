import streamlit as st
import asyncio
from app.models import WorkfrontTaskPayload, WorkfrontStatus, Channel, Audience, AgeSegment
from orchestrator.weave_simulator import run_pipeline

st.set_page_config(page_title="FullForce Content Gen PoC", layout="wide")
st.title("🎨 FullForce Content Generation — PoC Demo")

with st.sidebar:
    st.header("Campaign Brief")
    collection = st.selectbox("Collection", ["The Ritual of Namaste","The Ritual of Sakura","The Ritual of Ayurveda"])
    product    = st.text_input("Product", "Body Cream")
    channel    = st.selectbox("Channel", ["email","social","landing","all"])
    audience   = st.selectbox("Audience", ["loyalty","new","reactivation","all"])
    age_seg    = st.selectbox("Age Segment", ["young","mature","family","all"])
    market     = st.selectbox("Market", ["NL","DE","UK","all"])
    objective  = st.text_area("Objective", "Drive replenishment for loyalty customers")
    mood       = st.selectbox("Visual Mood", ["luxury","energetic","warm","playful","informative"])

if st.button("🚀 Generate Content", type="primary"):
    task = WorkfrontTaskPayload(
        task_id="demo-001",
        project_id="proj-001",
        status=WorkfrontStatus.CONTENT_GENERATION,
        collection=collection,
        product=product,
        channel=Channel(channel),
        audience=Audience(audience),
        age_segment=AgeSegment(age_seg),
        market=market,
        objective=objective,
        visual_mood=mood,
    )
    with st.spinner("Orchestrating pipeline..."):
        result = asyncio.run(run_pipeline(task))

    col1, col2 = st.columns(2)
    with col1:
        st.image(result.generated_image_url, caption="Generated Image", use_column_width=True)
    with col2:
        st.subheader("Generated Copy")
        st.write(result.generated_copy)
        st.subheader("Prompt Used")
        st.code(result.prompt_used, language="text")
        st.subheader("Assets Used")
        st.write("Images:", result.images_used)
        st.write("Copy:", result.assets_used)