
from legacy.paths import ROOT
from PIL import Image
from legacy.ui.ocr import ocr_line_boxes

img = Image.open(ROOT / "artifacts" / "qn-sess-left-now.png")
print("size", img.size)
for b in ocr_line_boxes(img)[:50]:
    print(f"y={b['y']:6.0f} x={b['x']:6.0f} {b['text']!r}")
