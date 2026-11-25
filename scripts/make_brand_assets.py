"""Generate brand assets for Arr Studio. Deterministic PIL icon and logo generator.

Both assets share the poster-grid motif of the panel: rounded poster cards
in the UI palette on a dark tile.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

# UI palette (docs/UI.md)
DARK = (26, 26, 26, 255)  # #1a1a1a background
BLUE = (66, 133, 244, 255)  # #4285f4
GREEN = (76, 175, 80, 255)  # #4caf50
RED = (244, 67, 54, 255)  # #f44336
GRAY = (86, 86, 86, 255)  # muted poster
WHITE = (255, 255, 255, 255)

CARD_W = 72
CARD_H = 96  # ~3:2 portrait, like the panel posters
CARD_RADIUS = 10


def _poster(draw: ImageDraw.ImageDraw, x: int, y: int, fill: tuple[int, int, int, int]) -> None:
    """Draw one rounded poster card at (x, y)."""
    draw.rounded_rectangle(
        [x, y, x + CARD_W - 1, y + CARD_H - 1], radius=CARD_RADIUS, fill=fill
    )


def _play_mark(draw: ImageDraw.ImageDraw, cx: int, cy: int) -> None:
    """Draw a white play triangle centred on (cx, cy)."""
    draw.polygon([(cx - 8, cy - 14), (cx - 8, cy + 14), (cx + 18, cy)], fill=WHITE)


def generate_icon() -> None:
    """Generate the 256x256 marketplace icon: a 2x2 poster grid."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 255, 255], radius=56, fill=DARK)

    gap = 12
    grid_w = 2 * CARD_W + gap
    grid_h = 2 * CARD_H + gap
    x0 = (256 - grid_w) // 2
    y0 = (256 - grid_h) // 2

    _poster(draw, x0, y0, BLUE)
    _play_mark(draw, x0 + CARD_W // 2, y0 + CARD_H // 2)
    _poster(draw, x0 + CARD_W + gap, y0, GREEN)
    _poster(draw, x0, y0 + CARD_H + gap, RED)
    _poster(draw, x0 + CARD_W + gap, y0 + CARD_H + gap, GRAY)

    img.save("custom_components/arr_studio/brand/icon.png")
    print("Generated icon.png")


def generate_logo() -> None:
    """Generate the 512x256 logo: a horizontal poster strip."""
    img = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, 511, 255], radius=48, fill=DARK)

    gap = 24
    count = 5
    strip_w = count * CARD_W + (count - 1) * gap
    x0 = (512 - strip_w) // 2
    y0 = (256 - CARD_H) // 2

    colours = [BLUE, GREEN, RED, GRAY, BLUE]
    for i, colour in enumerate(colours):
        x = x0 + i * (CARD_W + gap)
        _poster(draw, x, y0, colour)
        if i == 0:
            _play_mark(draw, x + CARD_W // 2, y0 + CARD_H // 2)

    img.save("custom_components/arr_studio/brand/logo.png")
    print("Generated logo.png")


def main() -> None:
    """Generate brand assets."""
    print("Generating brand assets...")
    generate_icon()
    generate_logo()
    print("Done.")


if __name__ == "__main__":
    main()
