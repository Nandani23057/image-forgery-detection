from io import BytesIO
from PIL import Image, ImageChops, ImageEnhance

def analyze_ela(image):
    original = image.convert("RGB")

    buffer = BytesIO()
    original.save(buffer, format="JPEG", quality=90)
    buffer.seek(0)

    compressed = Image.open(buffer).convert("RGB")
    difference = ImageChops.difference(original, compressed)

    extrema = difference.getextrema()
    maximum = max(channel[1] for channel in extrema)

    if maximum == 0:
        return Image.new("RGB", original.size, "black")

    scale = 255.0 / maximum
    return ImageEnhance.Brightness(difference).enhance(scale)

