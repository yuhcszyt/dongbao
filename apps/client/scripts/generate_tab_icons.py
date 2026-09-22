"""生成原生 tabBar 图标；颜色取 pages.json。仅重新生成素材时需要 Pillow。"""
import json
from pathlib import Path
from PIL import Image, ImageDraw

root = Path(__file__).resolve().parents[1] / "src"
theme = json.loads((root / "pages.json").read_text())["tabBar"]
scale = 3

for name in ("home", "record", "ai", "profile"):
    for selected in (False, True):
        image = Image.new("RGBA", (72 * scale, 72 * scale))
        draw = ImageDraw.Draw(image)
        color = theme["selectedColor" if selected else "color"]

        def line(points):
            draw.line([(x * scale, y * scale) for x, y in points], fill=color, width=4 * scale, joint="curve")

        def ellipse(box, fill=False):
            draw.ellipse(tuple(v * scale for v in box), outline=color, fill=color if fill else None, width=4 * scale)

        if name == "home":
            line([(9, 33), (36, 10), (63, 33)])
            line([(17, 29), (17, 61), (29, 61), (29, 43), (43, 43), (43, 61), (55, 61), (55, 29)])
        elif name == "record":
            draw.rounded_rectangle((16 * scale, 9 * scale, 56 * scale, 63 * scale), radius=5 * scale, outline=color, width=4 * scale)
            for y in (25, 36, 47): line([(26, y), (46, y)])
        elif name == "ai":
            draw.rounded_rectangle((10 * scale, 20 * scale, 62 * scale, 59 * scale), radius=12 * scale, outline=color, width=4 * scale)
            line([(36, 20), (36, 11)])
            ellipse((33, 6, 39, 12), True)
            ellipse((23, 32, 28, 37), True)
            ellipse((44, 32, 49, 37), True)
            line([(27, 46), (36, 49), (45, 46)])
        else:
            ellipse((24, 8, 48, 32))
            draw.arc((12 * scale, 38 * scale, 60 * scale, 82 * scale), 180, 360, fill=color, width=4 * scale)
            line([(12, 60), (60, 60)])
        image.resize((72, 72), Image.Resampling.LANCZOS).save(root / "static" / "tab" / f"{name}{'-active' if selected else ''}.png")
