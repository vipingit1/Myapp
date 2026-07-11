"""
handicraft_showcase.py  ─  Animated Handicraft Showcase Video Generator
========================================================================
Creates a captivating animated portrait video (9:16) in which a female
model showcases your handicraft products — with Ken Burns zoom, product
card slide-in, typewriter text, gold sparkle particles, and cross-fade
transitions.

SETUP
─────
  pip install moviepy imageio-ffmpeg pillow numpy

FOLDER STRUCTURE (relative to this script)
───────────────────────────────────────────
  model/        ← model photos   (.jpg / .png / .webp)
  products/     ← product images (.jpg / .png / .webp)
                   ✦ rename files like  "01_Silk Dupatta.jpg"
                     (text after first underscore → on-screen caption)
  music/        ← optional background music (.mp3 / .wav / .m4a)
  output/       ← generated video saved here as  showcase.mp4

USAGE
─────
  python handicraft_showcase.py

TIPS
────
  • Portrait  1080×1920  →  ideal for Instagram Reels, YouTube Shorts, TikTok
  • Landscape 1920×1080  →  change  W, H = 1920, 1080  in CONFIG
  • Each model image is reused in rotation if you have fewer models than products
  • Drop MP3 files in music/ for an automatic soundtrack
"""

import math
import random
import re
import sys
from pathlib import Path

# Fix Windows console encoding so Unicode characters print without crashing
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# ── moviepy 2.x ──────────────────────────────────────────────────────────────
try:
    import moviepy.audio.fx as afx
    import moviepy.video.fx as vfx
    from moviepy import (
        AudioFileClip,
        VideoClip,
        concatenate_videoclips,
    )
except ImportError:
    sys.exit("❌  Run:  pip install moviepy imageio-ffmpeg")


# ══════════════════════════════  CONFIG  ═════════════════════════════════════

BASE_DIR    = Path(__file__).parent
MODEL_DIR   = BASE_DIR / "model"
PROD_DIR    = BASE_DIR / "products"
MUSIC_DIR   = BASE_DIR / "music"
OUT_DIR     = BASE_DIR / "output"
OUTPUT_FILE = OUT_DIR  / "showcase.mp4"

# ── Video dimensions ─────────────────────────────────────────────────────────
#   Portrait  (Reels / Shorts / TikTok) : W, H = 1080, 1920
#   Landscape (YouTube)                 : W, H = 1920, 1080
W, H = 1080, 1920

FPS         = 30
INTRO_DUR   = 4.0   # seconds — animated brand intro
SCENE_DUR   = 5.0   # seconds — per product scene
OUTRO_DUR   = 4.0   # seconds — call-to-action outro
XFADE       = 0.50  # seconds — cross-fade between scenes

# ── Product cap ───────────────────────────────────────────────────────────────
#   Set to None to render ALL products (full catalog video)
#   40 products × 5 s ≈ 4-min reel
MAX_PRODUCTS = 40

# ── Branding ─────────────────────────────────────────────────────────────────
BRAND_NAME = "PADMA IMPEX"             # ← your shop / brand name
TAGLINE    = "Handcrafted with Love"
CTA_TEXT   = "Shop Now  ›"            # outro call-to-action text

# ── Colours ──────────────────────────────────────────────────────────────────
ACCENT     = (220, 165,  50)          # warm gold
BG_DARK    = ( 12,   6,  22)          # deep indigo-black
TEXT_WHITE = (255, 255, 255)
CARD_BG    = ( 22,  14,  38)          # card background

# ── Misc ─────────────────────────────────────────────────────────────────────
SHUFFLE_MODELS = True              # randomise model image order

# ═════════════════════════════════════════════════════════════════════════════

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff"}


# ─── Font helper ──────────────────────────────────────────────────────────────

def find_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Return a TrueType font at *size*, falling back to PIL bitmap font."""
    candidates = (
        [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/calibrib.ttf",
            "C:/Windows/Fonts/trebucbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "C:/Windows/Fonts/trebuc.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    # PIL's built-in bitmap font (tiny but always available)
    return ImageFont.load_default()


# ─── Image utilities ──────────────────────────────────────────────────────────

def load_images(folder: Path) -> list:
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMG_EXTS)


def product_name(path: Path) -> str:
    """'02_Silk Dupatta.jpg'  →  'Silk Dupatta'"""
    stem = path.stem
    stem = re.sub(r"^\d+[_\-\.]?\s*", "", stem)
    return stem.replace("_", " ").strip()


def fit_fill(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize + centre-crop so the image fills exactly tw×th."""
    r = max(tw / img.width, th / img.height)
    nw, nh = int(img.width * r + 0.5), int(img.height * r + 0.5)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - tw) // 2
    y = (nh - th) // 2
    return img.crop((x, y, x + tw, y + th))


def fit_contain(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize so the image fits within tw×th (letterbox, transparent bg)."""
    r = min(tw / img.width, th / img.height)
    nw, nh = int(img.width * r), int(img.height * r)
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    canvas.paste(img.convert("RGBA"), ((tw - nw) // 2, (th - nh) // 2))
    return canvas


# ─── Easing ───────────────────────────────────────────────────────────────────

def ease_out_cubic(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def ease_out_back(t: float, s: float = 1.35) -> float:
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


# ─── Visual layer helpers ────────────────────────────────────────────────────

def bottom_gradient(w: int, h: int, grad_h: int,
                    color: tuple = BG_DARK) -> Image.Image:
    """Tall gradient that fades from transparent to *color* at the bottom."""
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw  = ImageDraw.Draw(layer)
    for i in range(grad_h):
        alpha = int(210 * (i / grad_h) ** 1.6)
        y = h - grad_h + i
        draw.line([(0, y), (w - 1, y)], fill=(*color, alpha))
    return layer


def vignette(w: int, h: int, strength: float = 0.50) -> np.ndarray:
    """Radial black vignette as RGBA numpy array."""
    cx, cy = w / 2.0, h / 2.0
    Y, X = np.ogrid[:h, :w]
    d = np.sqrt(((X - cx) / cx) ** 2 + ((Y - cy) / cy) ** 2)
    a = (np.clip(d * strength, 0, 1) * 180).astype(np.uint8)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    rgba[..., 3] = a
    return rgba


def draw_rounded_rect(draw: ImageDraw.ImageDraw,
                      xy, radius: int, fill=None, outline=None, width: int = 1):
    """PIL ≥9 has rounded_rectangle; this wrapper ensures compatibility."""
    x0, y0, x1, y1 = xy[0][0], xy[0][1], xy[1][0], xy[1][1]
    try:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=radius,
                                fill=fill, outline=outline, width=width)
    except AttributeError:
        # Fallback for older PIL
        draw.rectangle([x0, y0, x1, y1], fill=fill, outline=outline)


# ─── Sparkle particles ───────────────────────────────────────────────────────

class Sparkles:
    def __init__(self, n: int = 20, x0: int = 0, y0: int = 0,
                 area_w: int = W, area_h: int = 300):
        rng = random.Random(7)
        self.parts = [
            {
                "x":     x0 + rng.uniform(0.05, 0.95) * area_w,
                "y":     y0 + rng.uniform(0.05, 0.95) * area_h,
                "phase": rng.uniform(0, 2 * math.pi),
                "size":  rng.uniform(2.5, 8.0),
                "speed": rng.uniform(1.6, 3.2),
            }
            for _ in range(n)
        ]

    def draw(self, canvas: ImageDraw.ImageDraw, t: float):
        for p in self.parts:
            pulse = 0.45 + 0.55 * math.sin(t * p["speed"] + p["phase"])
            alpha = int(200 * pulse)
            r = p["size"] * pulse
            if r < 1.0:
                continue
            x, y = p["x"], p["y"]
            c = (*ACCENT, alpha)
            canvas.ellipse([x - r, y - r, x + r, y + r], fill=c)
            arm = r * 2.2
            if arm >= 1.0:
                canvas.line([int(x - arm), int(y), int(x + arm), int(y)],
                            fill=c, width=1)
                canvas.line([int(x), int(y - arm), int(x), int(y + arm)],
                            fill=c, width=1)


# ─── Ken Burns effect ─────────────────────────────────────────────────────────

def ken_burns_frame(src: np.ndarray, t: float, dur: float,
                    zoom: tuple = (1.0, 1.08),
                    pan_x: float = 0.0, pan_y: float = 0.0) -> np.ndarray:
    """Slowly zoom + pan an image frame-by-frame (numpy in/out)."""
    p  = t / dur
    z  = zoom[0] + (zoom[1] - zoom[0]) * p
    h, w = src.shape[:2]
    nw = int(w / z)
    nh = int(h / z)
    cx = int(w / 2.0 + pan_x * w * p)
    cy = int(h / 2.0 + pan_y * h * p)
    x1 = max(0, cx - nw // 2);  x2 = min(w, x1 + nw)
    y1 = max(0, cy - nh // 2);  y2 = min(h, y1 + nh)
    cropped = src[y1:y2, x1:x2]
    return np.array(Image.fromarray(cropped).resize((w, h), Image.LANCZOS))


# ─── Pre-rendered static layers ──────────────────────────────────────────────

_grad_layer   = bottom_gradient(W, H, int(H * 0.48))
_vign_layer   = Image.fromarray(vignette(W, H)).convert("RGBA")
_fnt_brand_sm = None
_fnt_prod     = None
_fnt_tag      = None
_fnt_cta      = None


def _init_fonts():
    global _fnt_brand_sm, _fnt_prod, _fnt_tag, _fnt_cta
    _fnt_brand_sm = find_font(34, bold=True)
    _fnt_prod     = find_font(54, bold=True)
    _fnt_tag      = find_font(34)
    _fnt_cta      = find_font(74, bold=True)


# ─── Clip builders ───────────────────────────────────────────────────────────

def make_intro_clip() -> VideoClip:
    """Animated brand intro: expanding gold lines + title fade-in."""
    fnt_big  = find_font(80, bold=True)
    fnt_tag  = find_font(38)
    fnt_sub  = find_font(28)

    def frame(t: float) -> np.ndarray:
        canvas = Image.new("RGBA", (W, H), (*BG_DARK, 255))
        d = ImageDraw.Draw(canvas)

        # Expanding horizontal gold lines
        lp  = min(1.0, t / 1.4)
        lw  = int(W * 0.70 * ease_out_cubic(lp))
        lx  = (W - lw) // 2
        mid = H // 2 - 70
        if lw > 4:
            d.line([(lx, mid), (lx + lw, mid)], fill=(*ACCENT, 255), width=3)
            d.line([(lx, mid + 10), (lx + lw, mid + 10)],
                   fill=(*ACCENT, 80), width=1)

        # Decorative dots along the line
        for i in range(9):
            fx_ = lx + int(lw * i / 8) if lw > 0 else W // 2
            pulse = 0.5 + 0.5 * math.sin(t * 3 + i * 0.7)
            r = int(4 * pulse)
            d.ellipse([fx_ - r, mid + 5 - r, fx_ + r, mid + 5 + r],
                       fill=ACCENT)

        # Brand name: fade + slide up
        a_brand = int(min(255, max(0, (t - 0.35) / 0.9) * 255))
        if a_brand > 0:
            bb  = d.textbbox((0, 0), BRAND_NAME, font=fnt_big)
            bw  = bb[2] - bb[0]
            bh  = bb[3] - bb[1]
            bx  = (W - bw) // 2
            by  = mid - bh - 30
            sl  = int(18 * (1 - min(1.0, (t - 0.35) / 0.65)))
            d.text((bx + 3, by + sl + 4), BRAND_NAME, font=fnt_big,
                   fill=(0, 0, 0, a_brand // 2))
            d.text((bx, by + sl), BRAND_NAME, font=fnt_big,
                   fill=(*ACCENT, a_brand))

        # Tagline
        a_tag = int(min(255, max(0, (t - 1.1) / 0.8) * 255))
        if a_tag > 0:
            tb = d.textbbox((0, 0), TAGLINE, font=fnt_tag)
            d.text(((W - (tb[2] - tb[0])) // 2, mid + 30),
                   TAGLINE, font=fnt_tag, fill=(*TEXT_WHITE, a_tag))

        # Sub-line
        sub = "✦  New Collection  ✦"
        a_sub = int(min(255, max(0, (t - 1.7) / 0.7) * 255))
        if a_sub > 0:
            sb = d.textbbox((0, 0), sub, font=fnt_sub)
            d.text(((W - (sb[2] - sb[0])) // 2, mid + 90),
                   sub, font=fnt_sub, fill=(*ACCENT, a_sub))

        # Fade-out last 0.5 s
        if t > INTRO_DUR - XFADE:
            fade_a = int(255 * (t - (INTRO_DUR - XFADE)) / XFADE)
            fade_layer = Image.new("RGBA", (W, H), (0, 0, 0, fade_a))
            canvas = Image.alpha_composite(canvas, fade_layer)

        return np.array(canvas.convert("RGB"))

    return VideoClip(frame, duration=INTRO_DUR)


def make_product_scene(model_arr: np.ndarray,
                       prod_path: Path,
                       scene_idx: int,
                       dur: float = SCENE_DUR) -> VideoClip:
    """
    One product scene:
      • Full-frame model with Ken Burns zoom
      • Cinematic gradient + vignette
      • Slide-up product card with image + gold border
      • Typewriter product-name reveal
      • Twinkling gold sparkles
    """
    caption = product_name(prod_path)

    # ── Card geometry ──────────────────────────────────────────────────────
    card_w    = int(W * 0.80)
    card_h    = int(H * 0.37)
    card_x    = (W - card_w) // 2
    card_y    = int(H * 0.54)          # settled position
    img_pad   = 14
    img_area_h = card_h - 90           # space for product image inside card
    img_area_w = card_w - img_pad * 2

    # Pre-render product image (fitted inside card)
    prod_pil = Image.open(prod_path).convert("RGB")
    prod_fit = fit_contain(prod_pil, img_area_w, img_area_h)

    # Pre-render card background (RGBA)
    card_img = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card_img)
    draw_rounded_rect(cd, [(0, 0), (card_w - 1, card_h - 1)],
                      radius=30, fill=(*CARD_BG, 235))
    draw_rounded_rect(cd, [(1, 1), (card_w - 2, card_h - 2)],
                      radius=30, outline=(*ACCENT, 180), width=2)
    # Paste product image centred in top portion of card
    px = (card_w - prod_fit.width) // 2
    py = img_pad
    card_img.paste(prod_fit, (px, py), prod_fit)

    # Sparkles near the card area
    sparkles = Sparkles(n=18, x0=card_x, y0=card_y - 40,
                        area_w=card_w, area_h=card_h + 80)

    # Alternate Ken Burns direction per scene
    pan_x = 0.035 * (1 if scene_idx % 2 == 0 else -1)
    pan_y = 0.018 * (1 if scene_idx % 3 != 2 else -1)

    def frame(t: float) -> np.ndarray:
        # 1. Ken Burns background
        kb   = ken_burns_frame(model_arr, t, dur,
                               zoom=(1.0, 1.08), pan_x=pan_x, pan_y=pan_y)
        base = Image.fromarray(kb).convert("RGBA")
        base = ImageEnhance.Brightness(base).enhance(0.68)

        # 2. Gradient + vignette
        canvas = Image.alpha_composite(base, _grad_layer)
        canvas = Image.alpha_composite(canvas, _vign_layer)

        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(overlay)

        # 3. Brand watermark (top centre)
        brand_a = min(255, int(255 * min(1.0, t / 0.7)))
        bb = od.textbbox((0, 0), BRAND_NAME, font=_fnt_brand_sm)
        bw = bb[2] - bb[0]
        bh = bb[3] - bb[1]
        bx = (W - bw) // 2
        by = 52
        od.text((bx, by), BRAND_NAME, font=_fnt_brand_sm,
                fill=(*ACCENT, brand_a))
        line_len = 180
        lly = by + bh + 6
        od.line([(W // 2 - line_len // 2, lly),
                  (W // 2 + line_len // 2, lly)],
                 fill=(*ACCENT, brand_a), width=1)

        canvas = Image.alpha_composite(canvas, overlay)

        # 4. Product card slide-up
        CARD_START = 0.45
        if t >= CARD_START:
            slide_p = min(1.0, (t - CARD_START) / 0.65)
            ease_p  = ease_out_back(slide_p, s=1.30)
            off     = H + 60
            cy      = int(off + (card_y - off) * ease_p)
            canvas.paste(card_img, (card_x, cy), card_img)

        # 5. Sparkles (appear after card settles)
        if t >= 1.4:
            sp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sparkles.draw(ImageDraw.Draw(sp), t)
            canvas = Image.alpha_composite(canvas, sp)

        # 6. Product name typewriter
        TEXT_START = 1.2
        if t >= TEXT_START:
            type_p  = min(1.0, (t - TEXT_START) / 1.1)
            n_chars = max(1, int(len(caption) * type_p))
            partial = caption[:n_chars]

            txt_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            td = ImageDraw.Draw(txt_layer)
            pb  = td.textbbox((0, 0), partial, font=_fnt_prod)
            pw  = pb[2] - pb[0]
            tx  = (W - pw) // 2
            ty  = card_y + card_h + 16

            # Shadow
            td.text((tx + 2, ty + 3), partial, font=_fnt_prod,
                    fill=(0, 0, 0, 200))
            td.text((tx, ty), partial, font=_fnt_prod,
                    fill=(*TEXT_WHITE, 255))

            # Blinking cursor while typing
            if type_p < 1.0 and int(t * 2) % 2 == 0:
                td.text((tx + pw, ty), "│", font=_fnt_prod,
                        fill=(*ACCENT, 255))

            canvas = Image.alpha_composite(canvas, txt_layer)

        # 7. Fade-out tail (for cross-fade)
        if t > dur - XFADE:
            fade_a = int(255 * (t - (dur - XFADE)) / XFADE)
            fl = Image.new("RGBA", (W, H), (0, 0, 0, fade_a))
            canvas = Image.alpha_composite(canvas, fl)

        return np.array(canvas.convert("RGB"))

    return VideoClip(frame, duration=dur)


def make_outro_clip(model_arr: np.ndarray) -> VideoClip:
    """Outro: animated ring + 'Shop Now' CTA + brand."""
    def frame(t: float) -> np.ndarray:
        kb   = ken_burns_frame(model_arr, t, OUTRO_DUR,
                               zoom=(1.0, 1.05), pan_x=0.02, pan_y=0.01)
        base = Image.fromarray(kb).convert("RGBA")
        base = ImageEnhance.Brightness(base).enhance(0.55)

        canvas = Image.alpha_composite(base, _grad_layer)
        canvas = Image.alpha_composite(canvas, _vign_layer)

        ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        od = ImageDraw.Draw(ov)

        # Animated expanding ring
        ring_p = min(1.0, t / 1.1)
        ring_r = int(W * 0.30 * ease_out_cubic(ring_p))
        rx, ry = W // 2, int(H * 0.35)
        if ring_r > 0:
            alpha_ring = int(220 * ease_in_out(ring_p))
            od.ellipse([rx - ring_r, ry - ring_r,
                         rx + ring_r, ry + ring_r],
                        outline=(*ACCENT, alpha_ring), width=3)
            # Inner ring
            r2 = int(ring_r * 0.75)
            od.ellipse([rx - r2, ry - r2, rx + r2, ry + r2],
                        outline=(*ACCENT, alpha_ring // 2), width=1)

        # CTA text
        a_cta = int(min(255, max(0, (t - 0.5) / 0.7) * 255))
        if a_cta > 0:
            cb  = od.textbbox((0, 0), CTA_TEXT, font=_fnt_cta)
            cw, ch = cb[2] - cb[0], cb[3] - cb[1]
            ctx = (W - cw) // 2
            cty = int(H * 0.60)
            od.text((ctx + 3, cty + 4), CTA_TEXT, font=_fnt_cta,
                    fill=(0, 0, 0, a_cta // 2))
            od.text((ctx, cty), CTA_TEXT, font=_fnt_cta,
                    fill=(*ACCENT, a_cta))
            # Underline
            od.line([(ctx, cty + ch + 4), (ctx + cw, cty + ch + 4)],
                     fill=(*ACCENT, a_cta), width=2)

        # Brand name
        a_brand = int(min(255, max(0, (t - 1.1) / 0.7) * 255))
        if a_brand > 0:
            bb  = od.textbbox((0, 0), BRAND_NAME, font=_fnt_brand_sm)
            bx  = (W - (bb[2] - bb[0])) // 2
            od.text((bx, int(H * 0.74)), BRAND_NAME, font=_fnt_brand_sm,
                    fill=(*TEXT_WHITE, a_brand))
            tb  = od.textbbox((0, 0), TAGLINE, font=_fnt_tag)
            od.text(((W - (tb[2] - tb[0])) // 2, int(H * 0.74) + 52),
                    TAGLINE, font=_fnt_tag,
                    fill=(*TEXT_WHITE, int(a_brand * 0.65)))

        canvas = Image.alpha_composite(canvas, ov)

        # Fade in from black at scene start
        if t < XFADE:
            fade_a = int(255 * (1 - t / XFADE))
            fl = Image.new("RGBA", (W, H), (0, 0, 0, fade_a))
            canvas = Image.alpha_composite(canvas, fl)

        return np.array(canvas.convert("RGB"))

    return VideoClip(frame, duration=OUTRO_DUR)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    OUT_DIR.mkdir(exist_ok=True)
    _init_fonts()

    # ── Validate inputs ──────────────────────────────────────────────────────
    for folder, label in [(MODEL_DIR, "model/"), (PROD_DIR, "products/")]:
        if not folder.exists():
            sys.exit(f"❌  Folder not found: {folder}\n"
                     f"   Create '{label}' and add your images there.")

    model_paths = load_images(MODEL_DIR)
    prod_paths  = load_images(PROD_DIR)

    if not model_paths:
        sys.exit(f"❌  No images found in {MODEL_DIR}\n"
                 "   Add model photos (jpg/png/webp).")
    if not prod_paths:
        sys.exit(f"❌  No images found in {PROD_DIR}\n"
                 "   Add product photos (jpg/png/webp).\n"
                 "   Tip: rename them like  '01_Silk Dupatta.jpg'")

    # Honour the cap
    if MAX_PRODUCTS and len(prod_paths) > MAX_PRODUCTS:
        print(f"ℹ️   {len(prod_paths)} products found — using first {MAX_PRODUCTS} "
              f"(set MAX_PRODUCTS=None for full catalog).")
        prod_paths = prod_paths[:MAX_PRODUCTS]

    print(f"✔  {len(model_paths)} model image(s)  |  "
          f"{len(prod_paths)} product(s)  |  "
          f"{W}×{H} @ {FPS}fps")

    # ── Pre-load model images ─────────────────────────────────────────────────
    model_arrs = []
    for p in model_paths:
        arr = np.array(fit_fill(Image.open(p).convert("RGB"), W, H))
        model_arrs.append(arr)

    if SHUFFLE_MODELS:
        random.shuffle(model_arrs)

    def get_model(i: int) -> np.ndarray:
        return model_arrs[i % len(model_arrs)]

    # ── Build clips ───────────────────────────────────────────────────────────
    clips = []

    print("🎬  Intro ...")
    clips.append(make_intro_clip())

    for i, prod in enumerate(prod_paths):
        name = product_name(prod)
        print(f"🎬  Scene {i + 1}/{len(prod_paths)}: {name}")
        clips.append(make_product_scene(get_model(i), prod, scene_idx=i))

    print("🎬  Outro ...")
    clips.append(make_outro_clip(model_arrs[0]))

    # ── Concatenate with cross-fade ───────────────────────────────────────────
    print("🔗  Concatenating ...")
    final = concatenate_videoclips(clips, method="compose",
                                   padding=-XFADE, bg_color=BG_DARK)

    # ── Background music ──────────────────────────────────────────────────────
    music_files: list[Path] = []
    if MUSIC_DIR.exists():
        for ext in ("*.mp3", "*.wav", "*.m4a", "*.ogg", "*.aac", "*.webm"):
            music_files.extend(MUSIC_DIR.rglob(ext))

    if music_files:
        music_path = music_files[0]
        print(f"🎵  Music: {music_path.name}")
        audio = AudioFileClip(str(music_path))
        # Loop or trim to match video
        if audio.duration < final.duration:
            loops = int(final.duration / audio.duration) + 1
            from moviepy import concatenate_audioclips
            audio = concatenate_audioclips([audio] * loops)
        audio = audio.subclipped(0, final.duration)
        audio = audio.with_volume_scaled(0.72)
        audio = audio.with_effects([
            afx.AudioFadeIn(1.5),
            afx.AudioFadeOut(2.0),
        ])
        final = final.with_audio(audio)
    else:
        print("ℹ️   No music found — add MP3 files to music/ for a soundtrack.")

    # ── Export ────────────────────────────────────────────────────────────────
    total = final.duration
    print(f"\n🚀  Rendering → {OUTPUT_FILE}")
    print(f"    {len(prod_paths)} products · {total:.1f}s total · {W}×{H}")

    final.write_videofile(
        str(OUTPUT_FILE),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        ffmpeg_params=["-pix_fmt", "yuv420p"],
        logger="bar",
    )

    print(f"\n✅  Done!  Open  {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
