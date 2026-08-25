"""
make_icon.py — Converts a PNG logo into aria.ico (multi-resolution),
which build_exe.bat then embeds as the .exe's icon and taskbar icon.

    pip install pillow
    python make_icon.py your_logo.png

Use a square, high-res source image (512x512 or bigger) for best
results — Windows needs several sizes baked into one .ico file.
"""

import sys
from PIL import Image


def main():
    if len(sys.argv) != 2:
        print("Usage: python make_icon.py your_logo.png")
        sys.exit(1)

    src = sys.argv[1]
    img = Image.open(src).convert("RGBA")

    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save("aria.ico", format="ICO", sizes=sizes)
    print("Wrote aria.ico — place it next to build_exe.bat and rebuild.")


if __name__ == "__main__":
    main()
