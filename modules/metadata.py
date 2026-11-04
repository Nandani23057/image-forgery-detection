
from PIL import ExifTags

def extract_metadata(image):
    metadata = {
        "Format": image.format or "Unknown",
        "Width": image.width,
        "Height": image.height,
        "Mode": image.mode
    }

    exif = image.getexif()

    for tag_id, value in exif.items():
        tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
        metadata[str(tag_name)] = str(value)[:300]

    return metadata
