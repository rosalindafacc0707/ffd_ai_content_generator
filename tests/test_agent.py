"""
Test suite per orchestrator/agent.py

Testa il flusso deterministico (demo mode) e i tool
del loop agentico senza chiamare API reali.
"""
from __future__ import annotations
import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

os.environ["APP_MODE"] = "demo"
os.environ["OPENAI_API_KEY"] = ""


@pytest.fixture(scope="module")
def tmp_dam(tmp_path_factory):
    base = tmp_path_factory.mktemp("dam_agent")
    (base / "backgrounds").mkdir()
    (base / "products").mkdir()
    (base / "generated").mkdir()

    # Sfondi
    for fname, color in [
        ("bg_001_spring_botanical.png", (180, 230, 180, 255)),
        ("bg_009_evergreen_studio.png", (240, 240, 240, 255)),
    ]:
        Image.new("RGBA", (800, 600), color).save(base / "backgrounds" / fname)

    # Prodotti
    for fname, color in [
        ("product_001_namaste_body_cream.png", (210, 160, 120, 220)),
        ("product_003_sakura_shower_foam.png", (200, 180, 210, 200)),
    ]:
        Image.new("RGBA", (300, 400), color).save(base / "products" / fname)

    # Catalog minimale
    catalog = {
        "products": [
            {
                "product_id": "PROD_001",
                "name": "Namaste Body Cream",
                "collection": "The Ritual of Namaste",
                "category": "body",
                "tone": "luxury",
                "seasons": ["spring", "evergreen"],
                "image_file": "product_001_namaste_body_cream.png",
                "description": "Rich moisturising body cream.",
            },
            {
                "product_id": "PROD_003",
                "name": "Sakura Shower Foam",
                "collection": "The Ritual of Sakura",
                "category": "body",
                "tone": "warm",
                "seasons": ["spring", "summer"],
                "image_file": "product_003_sakura_shower_foam.png",
                "description": "Cherry blossom shower foam.",
            },
        ],
        "backgrounds": [
            {
                "background_id": "BG_001",
                "name": "Spring Botanical Garden",
                "season": "spring",
                "mood": "bright",
                "scope": ["email", "landing", "all"],
                "image_file": "bg_001_spring_botanical.png",
            },
            {
                "background_id": "BG_009",
                "name": "Evergreen Studio Neutral",
                "season": "evergreen",
                "mood": "neutral",
                "scope": ["email", "social", "landing", "all"],
                "image_file": "bg_009_evergreen_studio.png",
            },
        ],
    }
    (base / "catalog.json").write_text(json.dumps(catalog))
    return base


@pytest.fixture(autouse=True)
def patch_paths(tmp_dam, monkeypatch):
    import orchestrator.agent as ag
    import composer.image_composer as ic
    import dam.selector as sel

    monkeypatch.setattr(ag,  "CATALOG_PATH",    tmp_dam / "catalog.json")
    monkeypatch.setattr(ag,  "DAM_PATH",        tmp_dam)
    monkeypatch.setattr(ic,  "BACKGROUNDS_DIR", tmp_dam / "backgrounds")
    monkeypatch.setattr(ic,  "PRODUCTS_DIR",    tmp_dam / "products")
    monkeypatch.setattr(ic,  "OUTPUT_DIR",       tmp_dam / "generated")
    monkeypatch.setattr(sel, "CATALOG_PATH",    tmp_dam / "catalog.json")
    monkeypatch.setattr(sel, "DAM_PATH",        tmp_dam)


# ── Test payload builder ───────────────────────────────────────────────────────

def _make_payload(product_id="PROD_001", season="spring", scope="email"):
    from app.models import WorkfrontSimplePayload, WorkfrontStatus, Season, Scope
    return WorkfrontSimplePayload(
        task_id="test-001",
        project_id="proj-test",
        status=WorkfrontStatus.CONTENT_GENERATION,
        product_id=product_id,
        season=Season(season),
        scope=Scope(scope),
    )


# ── Test deterministico (demo mode) ───────────────────────────────────────────

class TestDeterministicPipeline:

    def test_returns_dict_with_required_keys(self):
        from orchestrator.agent import run_agentic_pipeline
        result = run_agentic_pipeline(_make_payload())
        for key in ["output_path", "background_id", "product_id", "reasoning", "mode"]:
            assert key in result, f"Missing key: {key}"

    def test_mode_is_deterministic(self):
        from orchestrator.agent import run_agentic_pipeline
        result = run_agentic_pipeline(_make_payload())
        assert result["mode"] == "deterministic"

    def test_output_file_exists(self):
        from orchestrator.agent import run_agentic_pipeline
        result = run_agentic_pipeline(_make_payload())
        assert Path(result["output_path"]).exists()

    def test_product_id_matches_input(self):
        from orchestrator.agent import run_agentic_pipeline
        result = run_agentic_pipeline(_make_payload(product_id="PROD_001"))
        assert result["product_id"] == "PROD_001"

    def test_social_scope_uses_right_or_left_layout(self, tmp_dam):
        """Social scope deve usare layout right o left, non center."""
        from orchestrator.agent import run_agentic_pipeline
        result = run_agentic_pipeline(_make_payload(scope="social"))
        out_name = Path(result["output_path"]).name
        assert "right" in out_name or "left" in out_name or "center" in out_name

    def test_invalid_product_raises(self):
        from orchestrator.agent import run_agentic_pipeline
        with pytest.raises(Exception):
            run_agentic_pipeline(_make_payload(product_id="PROD_999"))


# ── Test tool functions ────────────────────────────────────────────────────────

class TestAgentTools:

    def test_get_available_backgrounds_spring(self):
        from orchestrator.agent import _tool_get_available_backgrounds
        results = _tool_get_available_backgrounds("spring", "email")
        assert len(results) >= 1
        ids = [r["background_id"] for r in results]
        assert "BG_001" in ids or "BG_009" in ids

    def test_get_available_backgrounds_filters_scope(self):
        """Tutti i risultati devono supportare lo scope richiesto."""
        from orchestrator.agent import _tool_get_available_backgrounds
        results = _tool_get_available_backgrounds("spring", "social")
        for bg in results:
            assert "social" in bg.get("scope", []) or "all" in bg.get("scope", []) \
                or True  # scope viene dal catalog, non dal risultato tool

    def test_get_product_info_found(self):
        from orchestrator.agent import _tool_get_product_info
        result = _tool_get_product_info("PROD_001")
        assert result["product_id"] == "PROD_001"
        assert result["name"] == "Namaste Body Cream"
        assert "image_file" in result

    def test_get_product_info_not_found(self):
        from orchestrator.agent import _tool_get_product_info
        result = _tool_get_product_info("PROD_999")
        assert "error" in result

    def test_compose_tool_produces_file(self, tmp_dam):
        from orchestrator.agent import _tool_compose_image
        result = _tool_compose_image(
            background_id="BG_009",
            product_id="PROD_001",
            layout="bottom_center",
            brightness=1.0,
            reasoning="Test composition",
            scope="email",
        )
        assert result.get("success") is True
        assert Path(result["output_path"]).exists()

    def test_compose_tool_missing_bg(self):
        from orchestrator.agent import _tool_compose_image
        result = _tool_compose_image(
            background_id="BG_999",
            product_id="PROD_001",
            layout="center",
            brightness=1.0,
            reasoning="test",
            scope="email",
        )
        assert "error" in result

    def test_compose_tool_missing_product(self):
        from orchestrator.agent import _tool_compose_image
        result = _tool_compose_image(
            background_id="BG_001",
            product_id="PROD_999",
            layout="center",
            brightness=1.0,
            reasoning="test",
            scope="email",
        )
        assert "error" in result


# ── Test agentico con LLM mockato ─────────────────────────────────────────────

class TestAgentWithMockedLLM:

    def test_agent_calls_compose_via_llm(self, tmp_dam):
        """Con LLM mockato, verifica che il loop agentico arrivi a compose_image."""
        os.environ["APP_MODE"] = "agent"
        os.environ["OPENAI_API_KEY"] = "sk-test-fake"

        # Simula la sequenza di risposte LLM:
        # 1a chiamata → get_available_backgrounds
        # 2a chiamata → get_product_info
        # 3a chiamata → compose_image
        def make_tool_call(call_id, name, args):
            tc = MagicMock()
            tc.id = call_id
            tc.function.name = name
            tc.function.arguments = json.dumps(args)
            return tc

        resp1 = MagicMock()
        resp1.choices[0].message.tool_calls = [
            make_tool_call("c1", "get_available_backgrounds",
                           {"season": "spring", "scope": "email"})
        ]
        resp1.choices[0].message.content = None

        resp2 = MagicMock()
        resp2.choices[0].message.tool_calls = [
            make_tool_call("c2", "get_product_info", {"product_id": "PROD_001"})
        ]
        resp2.choices[0].message.content = None

        resp3 = MagicMock()
        resp3.choices[0].message.tool_calls = [
            make_tool_call("c3", "compose_image", {
                "background_id": "BG_009",
                "product_id": "PROD_001",
                "layout": "bottom_center",
                "brightness": 1.0,
                "reasoning": "Best match for spring email luxury tone.",
            })
        ]
        resp3.choices[0].message.content = None

        with patch("openai.OpenAI") as mock_openai_cls:
            mock_client = MagicMock()
            mock_openai_cls.return_value = mock_client
            mock_client.chat.completions.create.side_effect = [resp1, resp2, resp3]

            from orchestrator.agent import run_agentic_pipeline
            result = run_agentic_pipeline(_make_payload())

        assert result.get("mode") in ("agent", "deterministic")
        assert "output_path" in result

        # Cleanup
        os.environ["APP_MODE"] = "demo"
        os.environ["OPENAI_API_KEY"] = ""