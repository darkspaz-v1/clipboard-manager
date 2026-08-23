from PIL import Image, ImageDraw

_SIZE = 128  # drawn at 2x and downsampled for crisp anti-aliased edges


def _rounded_badge(color_top, color_bottom, size=_SIZE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * t)
        grad.putpixel((0, y), (r, g, b))
    grad = grad.resize((size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=int(size * 0.22), fill=255)
    img.paste(grad, (0, 0), mask)
    return img


def app_icon():
    """Signal-blue badge, clipboard glyph."""
    img = _rounded_badge((110, 148, 245), (58, 95, 217))
    d = ImageDraw.Draw(img)
    w = (255, 255, 255, 255)
    d.rounded_rectangle((38, 30, 90, 100), radius=8, outline=w, width=6)
    d.rounded_rectangle((52, 20, 76, 36), radius=6, fill=w)
    for y in (56, 76):
        d.line((48, y, 80, y), fill=w, width=6)
    return img.resize((64, 64), Image.LANCZOS)
