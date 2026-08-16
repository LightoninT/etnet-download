"""Generate app.icns (macOS icon) from the same candlestick artwork."""

from pathlib import Path

from PIL import Image

from gen_icon import make_icon

SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def main():
    out = Path("app.iconset")
    out.mkdir(exist_ok=True)
    for name, size in SIZES.items():
        make_icon(size).save(out / name)
    print("iconset written to", out)


if __name__ == "__main__":
    main()
