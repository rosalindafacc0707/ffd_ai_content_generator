"""
Script di inizializzazione DAM locale.
Crea le cartelle dam/products/ e dam/backgrounds/ e scarica
immagini placeholder da picsum.photos per tutti i 20 asset.

Esegui una sola volta:
    python dam/init_dam.py
"""
import json
import urllib.request
from pathlib import Path

DAM_PATH     = Path(__file__).parent
PRODUCTS_DIR = DAM_PATH / "products"
BG_DIR       = DAM_PATH / "backgrounds"

PRODUCTS_DIR.mkdir(exist_ok=True)
BG_DIR.mkdir(exist_ok=True)

with open(DAM_PATH / "catalog.json") as f:
    catalog = json.load(f)

# Seed map per avere immagini diverse e coerenti per ogni asset
PRODUCT_SEEDS = {
    "product_001_namaste_body_cream.png":  ("rituals-namaste-cream",  600, 600),
    "product_002_namaste_shower_foam.png": ("rituals-namaste-foam",   600, 600),
    "product_003_sakura_shower_foam.png":  ("rituals-sakura-foam",    600, 600),
    "product_004_sakura_candle.png":       ("rituals-sakura-candle",  600, 600),
    "product_005_ayurveda_face_oil.png":   ("rituals-ayurveda-oil",   600, 600),
    "product_006_ayurveda_body_cream.png": ("rituals-ayurveda-cream", 600, 600),
    "product_007_namaste_bath_salt.png":   ("rituals-namaste-salt",   600, 600),
    "product_008_sakura_body_scrub.png":   ("rituals-sakura-scrub",   600, 600),
    "product_009_ayurveda_bath_foam.png":  ("rituals-ayurveda-foam",  600, 600),
    "product_010_namaste_dry_oil.png":     ("rituals-namaste-oil",    600, 600),
}

BG_SEEDS = {
    "bg_001_spring_botanical.png":   ("spring-botanical",  1200, 800),
    "bg_002_spring_cherry.png":      ("spring-cherry",     1200, 800),
    "bg_003_summer_marble.png":      ("summer-marble",     1200, 800),
    "bg_004_summer_coastal.png":     ("summer-coastal",    1200, 800),
    "bg_005_autumn_linen.png":       ("autumn-linen",      1200, 800),
    "bg_006_autumn_wood.png":        ("autumn-wood",       1200, 800),
    "bg_007_winter_candle.png":      ("winter-candle",     1200, 800),
    "bg_008_winter_white.png":       ("winter-white",      1200, 800),
    "bg_009_evergreen_studio.png":   ("evergreen-studio",  1200, 800),
    "bg_010_evergreen_botanical.png":("evergreen-botanical",1200, 800),
}

def download(dest: Path, seed: str, w: int, h: int):
    if dest.exists():
        print(f"  [skip] {dest.name} already exists")
        return
    url = f"https://picsum.photos/seed/{seed}/{w}/{h}"
    print(f"  [download] {dest.name} ← {url}")
    urllib.request.urlretrieve(url, dest)

print("=== Initialising DAM — Products ===")
for fname, (seed, w, h) in PRODUCT_SEEDS.items():
    download(PRODUCTS_DIR / fname, seed, w, h)

print("\n=== Initialising DAM — Backgrounds ===")
for fname, (seed, w, h) in BG_SEEDS.items():
    download(BG_DIR / fname, seed, w, h)

print(f"\n✅ DAM ready — {len(PRODUCT_SEEDS)} products, {len(BG_SEEDS)} backgrounds")
print(f"   Products:    {PRODUCTS_DIR}")
print(f"   Backgrounds: {BG_DIR}")