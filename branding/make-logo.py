"""DEEPoS boot wordmark generator.

Builds a 640x480 boot splash (PNG preview + 24-bit BMP for U-Boot/kernel),
plus a 128x128 icon and a 32x32 favicon-style mark. Pure Pillow + numpy.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

W, H = 640, 480
BG = (5, 7, 12)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeuib.ttf",  # Segoe UI Bold
    r"C:\Windows\Fonts\segoeuib.ttf",  # Segoe UI Bold
    r"C:\Windows\Fonts\arialbd.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def radial_glow() -> Image.Image:
    """Soft blue radial glow + horizontal light streak, as RGB layer."""
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = W * 0.5, H * 0.50
    d = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 1.15) ** 2)
    glow = np.clip(1.0 - d / 300.0, 0.0, 1.0) ** 2.2

    streak_sigma = 26.0
    streak = np.exp(-((yy - cy) ** 2) / (2 * streak_sigma ** 2))
    streak *= np.clip(1.0 - np.abs(xx - cx) / (W * 0.62), 0.0, 1.0) ** 1.4

    deep = np.array([10, 42, 110], dtype=np.float32)
    mid = np.array([30, 107, 255], dtype=np.float32)
    hot = np.array([121, 216, 255], dtype=np.float32)

    rgb = deep[None, None, :] * glow[..., None]
    rgb += mid[None, None, :] * (glow ** 2.1)[..., None] * 0.85
    rgb += hot[None, None, :] * (streak * 0.55)[..., None]
    rgb += np.array(BG, dtype=np.float32)[None, None, :]
    return Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")


def draw_wordmark(size: int, tracking: int, text: str = "DEEPoS") -> Image.Image:
    """Render text into an L mask with letter tracking."""
    font = load_font(size)
    widths = [font.getbbox(ch)[2] - font.getbbox(ch)[0] for ch in text]
    total = sum(widths) + tracking * (len(text) - 1)
    asc, desc = font.getmetrics()
    mask = Image.new("L", (total + 8, asc + desc + 8), 0)
    d = ImageDraw.Draw(mask)
    x = 4
    for ch, w in zip(text, widths):
        d.text((x, 4), ch, font=font, fill=255)
        x += w + tracking
    return mask


def gradient_fill(mask: Image.Image, top=(20, 88, 235), bottom=(150, 226, 255)) -> Image.Image:
    w, h = mask.size
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    top_a = np.array(top, dtype=np.float32)[None, None, :]
    bot_a = np.array(bottom, dtype=np.float32)[None, None, :]
    grad = np.repeat(top_a * (1 - t) + bot_a * t, w, axis=1)
    fill = Image.fromarray(np.clip(grad, 0, 255).astype(np.uint8)[:, :, :3] if grad.shape[2] > 3 else np.clip(grad, 0, 255).astype(np.uint8), "RGB")
    layer = Image.new("RGB", mask.size, (0, 0, 0))
    layer.paste(fill, (0, 0), mask)
    return layer


def build_splash() -> Image.Image:
    base = radial_glow().convert("RGB")

    mask = draw_wordmark(size=92, tracking=9)
    fill = gradient_fill(mask)

    # outer glow of the wordmark
    glow_alpha = mask.filter(ImageFilter.GaussianBlur(14))
    glow_layer = Image.new("RGB", mask.size, (24, 96, 220))
    px, py = (W - mask.width) // 2, int(H * 0.5) - mask.height // 2 - 12
    base.paste(glow_layer, (px, py), glow_alpha.point(lambda v: int(v * 0.32)))
    base.paste(fill, (px, py), mask)

    d = ImageDraw.Draw(base)

    # thin underline
    line_w = int(mask.width * 0.86)
    lx = (W - line_w) // 2
    ly = py + mask.height + 10
    d.rectangle([lx, ly, lx + line_w, ly + 1], fill=(38, 96, 190))

    # tagline
    small = load_font(15)
    tag = "OPEN HANDHELD SYSTEM"
    tw = d.textlength(tag, font=small)
    color = (108, 168, 240)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                d.text(((W - tw) / 2 + dx, ly + 16 + dy), tag, font=small, fill=(14, 34, 70))
    d.text(((W - tw) / 2, ly + 16), tag, font=small, fill=color)

    # version chip, bottom-right
    tiny = load_font(12)
    ver = "v 0 . 1"
    vw = d.textlength(ver, font=tiny)
    d.text((W - vw - 26, H - 30), ver, font=tiny, fill=(70, 118, 178))

    return base


def save_outputs(img: Image.Image) -> None:
    img.save(OUT / "deepos-logo.png", "PNG")
    # 24-bit BMP is what U-Boot splash parsers expect
    img.convert("RGB").save(OUT / "deepos-boot.bmp", "BMP")

    # icon (transparent), wordmark "D" tile
    icon = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    dd = ImageDraw.Draw(icon)
    dd.rounded_rectangle([8, 8, 248, 248], radius=52, fill=(9, 16, 30, 255), outline=(46, 118, 232, 255), width=3)
    mask = draw_wordmark(size=170, tracking=0, text="D")
    bbox = mask.getbbox()
    mask = mask.crop(bbox)
    fill = gradient_fill(mask).convert("RGB")
    gx = (256 - mask.width) // 2
    gy = (256 - mask.height) // 2 - 2
    glow_alpha = mask.filter(ImageFilter.GaussianBlur(10))
    icon.paste(Image.new("RGB", mask.size, (30, 110, 235)), (gx, gy), glow_alpha.point(lambda v: int(v * 0.6)))
    icon.paste(fill, (gx, gy), mask)
    icon.resize((128, 128), Image.LANCZOS).save(OUT / "deepos-icon-128.png", "PNG")
    icon.resize((64, 64), Image.LANCZOS).save(OUT / "deepos-icon-64.png", "PNG")


def main() -> None:
    img = build_splash()
    save_outputs(img)
    for name in ("deepos-logo.png", "deepos-boot.bmp", "deepos-icon-128.png"):
        p = OUT / name
        print(f"{p}  {p.stat().st_size} bytes")
    with Image.open(OUT / "deepos-boot.bmp") as bmp:
        print("bmp:", bmp.size, bmp.mode)


if __name__ == "__main__":
    main()
