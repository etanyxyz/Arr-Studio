"""Generate brand assets for Arr Studio. Deterministic PIL icon and logo generator."""

from __future__ import annotations

from PIL import Image


def generate_icon() -> None:
    """Generate 256x256 icon PNG."""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    # Draw a simple filmstrip icon
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Background rectangle
    draw.rectangle([0, 0, 255, 255], fill=(255, 255, 255, 255), outline=(200, 200, 200, 255))
    # Filmstrip stripes
    for i in range(6):
        draw.rectangle([i * 42 + 4, 40, i * 42 + 38, 216], fill=(100, 100, 100, 255))
    # Arrows
    draw.polygon([(128, 30), (100, 70), (156, 70)], fill=(100, 100, 100, 255))
    draw.polygon([(128, 226), (100, 186), (156, 186)], fill=(100, 100, 100, 255))
    # Logo text
    draw.text((100, 120), "Arr Studio", fill=(50, 50, 50, 255))
    img.save("custom_components/arr_studio/brand/icon.png")
    print("Generated icon.png")


def generate_logo() -> None:
    """Generate 512x256 logo PNG."""
    img = Image.new("RGBA", (512, 256), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)
    # Background
    draw.rectangle([0, 0, 511, 255], fill=(255, 255, 255, 255), outline=(200, 200, 200, 255))
    # Center circle
    draw.ellipse([150, 150, 362, 362], fill=(200, 200, 200, 255), outline=(100, 100, 100, 255))
    # Arrows around the circle
    for i in range(12):
        angle = (i * 30) * 3.14159 / 180
        x1 = int(256 + 140 * __import__('math').cos(angle))
        y1 = int(256 + 140 * __import__('math').sin(angle))
        x2 = int(256 + 140 * __import__('math').cos(angle + 0.05))
        y2 = int(256 + 140 * __import__('math').sin(angle + 0.05))
        draw.line([(x1, y1), (x2, y2)], fill=(100, 100, 100, 255), width=2)
    # Logo text
    draw.text((220, 120), "Arr Studio", fill=(100, 100, 100, 255))
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
