"""
Image Composer — compone sfondo + prodotto in una singola immagine finale.
Usa esclusivamente immagini dal DAM locale (dam/backgrounds/ e dam/products/).

Layout supportati:
  center        → prodotto centrato sullo sfondo
  bottom_center → prodotto in basso al centro (tipico email/landing)
  left          → prodotto a sinistra
  right         → prodotto a destra (tipico social)
"""
from __future__ import annotations
import time
import logging
from pathlib import Path
from typing import Literal

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

DAM_PATH        = Path("./dam")
BACKGROUNDS_DIR = DAM_PATH / "backgrounds"
PRODUCTS_DIR    = DAM_PATH / "products"
OUTPUT_DIR      = DAM_PATH / "generated"

Layout = Literal["center", "bottom_center", "left", "right"]

# Dimensioni output finali per canale
CANVAS_SIZES = {
    "email":   (1200, 628),
    "social":  (1080, 1080),
    "landing": (1440, 810),
    "all":     (1200, 628),
}

# Quanto grande è il prodotto rispetto al canvas (percentuale altezza)
PRODUCT_SCALE = {
    "center":        0.55,
    "bottom_center": 0.50,
    "left":          0.55,
    "right":         0.55,
}

# Posizione centro prodotto come frazione del canvas (x%, y%)
LAYOUT_POSITIONS = {
    "center":        (0.50, 0.50),
    "bottom_center": (0.50, 0.78),
    "left":          (0.28, 0.55),
    "right":         (0.72, 0.55),
}


def _load_and_resize_bg(bg_file: str, canvas_w: int, canvas_h: int) -> Image.Image:
    path = BACKGROUNDS_DIR / bg_file
    img = Image.open(path).convert("RGB")   # ← RGB, non RGBA
    img_ratio    = img.width / img.height
    canvas_ratio = canvas_w / canvas_h
    if img_ratio > canvas_ratio:
        new_h = canvas_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = canvas_w
        new_h = int(new_w / img_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - canvas_w) // 2
    top  = (new_h - canvas_h) // 2
    return img.crop((left, top, left + canvas_w, top + canvas_h))


def _load_and_scale_product(
    product_file: str,
    canvas_h: int,
    scale: float,
) -> Image.Image:
    path = PRODUCTS_DIR / product_file
    img = Image.open(path).convert("RGBA")
    target_h = int(canvas_h * scale)
    ratio    = target_h / img.height
    target_w = int(img.width * ratio)
    return img.resize((target_w, target_h), Image.LANCZOS)


def _add_soft_shadow(product_img: Image.Image) -> Image.Image:
    """Aggiunge un'ombra morbida sotto il prodotto per renderlo più realistico."""
    shadow = Image.new("RGBA", product_img.size, (0, 0, 0, 0))
    shadow_layer = Image.new(
        "RGBA",
        (product_img.width, product_img.height),
        (0, 0, 0, 60),
    )
    # Maschera dall'alpha del prodotto
    mask = product_img.split()[3]
    shadow.paste(shadow_layer, mask=mask)
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=15))
    result = Image.new("RGBA", product_img.size, (0, 0, 0, 0))
    result.paste(shadow, (0, 8))
    result.paste(product_img, (0, 0), product_img)
    return result


def compose(
    bg_file: str,
    product_file: str,
    scope: str = "email",
    layout: Layout = "bottom_center",
    brightness: float = 1.0,
) -> str:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    canvas_w, canvas_h = CANVAS_SIZES.get(scope, (1200, 628))

    logger.info(
        f"[Composer] bg={bg_file} product={product_file} "
        f"scope={scope} layout={layout} brightness={brightness}"
    )

    # 1. Sfondo in RGB
    bg = _load_and_resize_bg(bg_file, canvas_w, canvas_h)

    # 2. Applica brightness sullo sfondo RGB (funziona correttamente)
    if brightness != 1.0:
        bg = ImageEnhance.Brightness(bg).enhance(brightness)

    # 3. Converti sfondo in RGBA per supportare paste con alpha mask
    canvas = bg.convert("RGBA")

    # 4. Prodotto
    scale   = PRODUCT_SCALE.get(layout, 0.50)
    product = _load_and_scale_product(product_file, canvas_h, scale)
    product = _add_soft_shadow(product)

    # 5. Posizione
    pos_x_frac, pos_y_frac = LAYOUT_POSITIONS.get(layout, (0.5, 0.5))
    paste_x = int(canvas_w * pos_x_frac - product.width  / 2)
    paste_y = int(canvas_h * pos_y_frac - product.height / 2)
    paste_x = max(0, min(paste_x, canvas_w - product.width))
    paste_y = max(0, min(paste_y, canvas_h - product.height))

    # 6. Componi e salva
    canvas.paste(product, (paste_x, paste_y), product)

    timestamp = int(time.time())
    out_name  = f"composed_{timestamp}_{scope}_{layout}.png"
    out_path  = OUTPUT_DIR / out_name
    canvas.convert("RGB").save(out_path, "PNG", optimize=True)

    logger.info(f"[Composer] Saved → {out_path}")
    return str(out_path)