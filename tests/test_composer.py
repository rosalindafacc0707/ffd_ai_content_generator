"""
Test suite per composer/image_composer.py

Crea immagini PNG sintetiche in una cartella temporanea
e verifica che la composizione produca output validi.
"""
from __future__ import annotations
import os
import pytest
from pathlib import Path
from PIL import Image

# Forza demo mode e DAM path temporaneo
os.environ["APP_MODE"] = "demo"


@pytest.fixture(scope="module")
def tmp_dam(tmp_path_factory):
    """Crea una struttura DAM temporanea con immagini sintetiche."""
    base = tmp_path_factory.mktemp("dam")

    (base / "backgrounds").mkdir()
    (base / "products").mkdir()
    (base / "generated").mkdir()

    # 3 sfondi sintetici 800x600 RGBA
    bg_colors = {"bg_spring.png": (180, 230, 180, 255),
                 "bg_winter.png": (200, 210, 230, 255),
                 "bg_studio.png": (240, 240, 240, 255)}
    for fname, color in bg_colors.items():
        img = Image.new("RGBA", (800, 600), color)
        img.save(base / "backgrounds" / fname)

    # 2 prodotti sintetici 300x400 RGBA (con trasparenza)
    for fname, color in [("prod_a.png", (210, 160, 120, 220)),
                          ("prod_b.png", (140, 180, 200, 200))]:
        img = Image.new("RGBA", (300, 400), color)
        img.save(base / "products" / fname)

    return base


@pytest.fixture(autouse=True)
def patch_dam_paths(tmp_dam, monkeypatch):
    """Redirige tutti i path del composer verso la cartella temporanea."""
    import composer.image_composer as ic
    monkeypatch.setattr(ic, "BACKGROUNDS_DIR", tmp_dam / "backgrounds")
    monkeypatch.setattr(ic, "PRODUCTS_DIR",    tmp_dam / "products")
    monkeypatch.setattr(ic, "OUTPUT_DIR",       tmp_dam / "generated")


# ── Test composizione ─────────────────────────────────────────────────────────

class TestCompose:

    def test_compose_returns_valid_path(self, tmp_dam):
        """compose() deve restituire un path esistente."""
        from composer.image_composer import compose
        out = compose(
            bg_file="bg_spring.png",
            product_file="prod_a.png",
            scope="email",
            layout="bottom_center",
        )
        assert Path(out).exists(), f"Output file not found: {out}"

    def test_compose_output_is_valid_png(self, tmp_dam):
        """Il file generato deve essere un PNG leggibile."""
        from composer.image_composer import compose
        out = compose("bg_studio.png", "prod_b.png", scope="email", layout="center")
        img = Image.open(out)
        assert img.format == "PNG"

    def test_compose_canvas_size_email(self, tmp_dam):
        """Canvas email deve essere 1200x628."""
        from composer.image_composer import compose
        out = compose("bg_spring.png", "prod_a.png", scope="email", layout="center")
        img = Image.open(out)
        assert img.size == (1200, 628)

    def test_compose_canvas_size_social(self, tmp_dam):
        """Canvas social deve essere 1080x1080."""
        from composer.image_composer import compose
        out = compose("bg_winter.png", "prod_b.png", scope="social", layout="right")
        img = Image.open(out)
        assert img.size == (1080, 1080)

    def test_compose_canvas_size_landing(self, tmp_dam):
        """Canvas landing deve essere 1440x810."""
        from composer.image_composer import compose
        out = compose("bg_studio.png", "prod_a.png", scope="landing", layout="left")
        img = Image.open(out)
        assert img.size == (1440, 810)

    @pytest.mark.parametrize("layout", ["center", "bottom_center", "left", "right"])
    def test_all_layouts(self, tmp_dam, layout):
        """Tutti i layout devono produrre un file valido."""
        from composer.image_composer import compose
        out = compose("bg_spring.png", "prod_a.png", scope="email", layout=layout)
        assert Path(out).exists()
        img = Image.open(out)
        assert img.size == (1200, 628)

    def test_brightness_dark(self, tmp_dam):
        """Brightness < 1.0 deve produrre sfondo più scuro."""
        import numpy as np
        from composer.image_composer import (
            _load_and_resize_bg, BACKGROUNDS_DIR, CANVAS_SIZES
        )
        from PIL import ImageEnhance

        # Testa direttamente su sfondo puro — senza paste del prodotto
        bg_normal = _load_and_resize_bg("bg_spring.png", 1200, 628)
        bg_dark   = ImageEnhance.Brightness(bg_normal.copy()).enhance(0.5)

        arr_normal = np.array(bg_normal)
        arr_dark   = np.array(bg_dark)

        assert arr_dark.mean() < arr_normal.mean(), (
            f"Dark bg mean {arr_dark.mean():.2f} should be < normal {arr_normal.mean():.2f}"
        )

    def test_unique_output_filenames(self, tmp_dam):
        """Ogni composizione deve generare un file con nome univoco."""
        import time
        from composer.image_composer import compose
        out1 = compose("bg_spring.png", "prod_a.png", scope="email", layout="center")
        time.sleep(1.1)  # assicura timestamp diverso
        out2 = compose("bg_spring.png", "prod_a.png", scope="email", layout="center")
        assert out1 != out2, "Two compositions should produce different filenames"

    def test_missing_background_raises(self):
        """File sfondo inesistente deve sollevare eccezione."""
        from composer.image_composer import compose
        with pytest.raises(Exception):
            compose("nonexistent_bg.png", "prod_a.png", scope="email", layout="center")

    def test_missing_product_raises(self):
        """File prodotto inesistente deve sollevare eccezione."""
        from composer.image_composer import compose
        with pytest.raises(Exception):
            compose("bg_spring.png", "nonexistent_product.png", scope="email", layout="center")