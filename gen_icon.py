"""Generate app.ico: dark blue rounded square with candlesticks + arrows."""

from PIL import Image, ImageDraw

SIZE = 256


def make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 256.0  # scale factor

    def rr(box, r):
        return d.rounded_rectangle(
            [box[0] * s, box[1] * s, box[2] * s, box[3] * s], radius=r * s
        )

    # background
    rr((8, 8, 248, 248), 48)
    # draw gradient-ish base
    d.rectangle([8 * s, 180 * s, 248 * s, 248 * s], fill=(16, 56, 110, 255))
    d.rounded_rectangle(
        [8 * s, 8 * s, 248 * s, 248 * s], radius=48 * s,
        outline=(90, 160, 255, 255), width=max(2, int(3 * s)),
    )

    # candlesticks (x_center, body_top, body_bottom, wick_top, wick_bottom, color)
    candles = [
        (70, 120, 165, 108, 178, (46, 204, 113)),   # green up
        (128, 100, 155, 92, 162, (46, 204, 113)),   # green up
        (186, 130, 175, 122, 182, (231, 76, 60)),   # red down
    ]
    for cx, bt, bb, wt, wb, color in candles:
        wick_w = max(3, int(5 * s))
        d.line([cx * s, wt * s, cx * s, wb * s], fill=color, width=wick_w)
        body_w = max(12, int(26 * s))
        d.rectangle(
            [(cx - body_w / 2) * s, bt * s, (cx + body_w / 2) * s, bb * s],
            fill=color,
        )

    # sparkline
    pts = [(36, 210), (70, 196), (100, 203), (128, 186), (160, 192),
           (186, 178), (220, 182)]
    d.line([(x * s, y * s) for x, y in pts], fill=(255, 255, 255, 230), width=max(3, int(6 * s)))

    # corner up-right arrow (export)
    ax0, ay0, ax1, ay1 = 168, 36, 214, 80
    d.line([ax0 * s, ay1 * s, ax1 * s, ay0 * s], fill=(255, 255, 255, 255), width=max(3, int(7 * s)))
    d.line([(ax1 - 18) * s, ay0 * s, ax1 * s, ay0 * s, ax1 * s, (ay0 + 18) * s],
           fill=(255, 255, 255, 255), width=max(3, int(7 * s)))

    return img


def main():
    base = make_icon(256)
    base.save("app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                                (64, 64), (128, 128), (256, 256)])
    print("app.ico written")


if __name__ == "__main__":
    main()
