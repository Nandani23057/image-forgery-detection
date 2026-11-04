
import cv2
import numpy as np
from PIL import Image, ImageOps


def analyze_noise(image, tile_size=64):
    # 1. Convert image to RGB
    rgb = np.array(
        ImageOps.exif_transpose(image).convert("RGB")
    )

    h, w = rgb.shape[:2]

    # Resize large images for faster processing
    scale = min(1.0, 1200 / max(h, w))

    if scale < 1:
        rgb = cv2.resize(
            rgb,
            (round(w * scale), round(h * scale)),
            interpolation=cv2.INTER_AREA
        )

    h, w = rgb.shape[:2]

    # 2. Convert to grayscale
    gray = cv2.cvtColor(
        rgb, cv2.COLOR_RGB2GRAY
    ).astype(np.float32)

    # 3. Estimate high-frequency residual
    smooth = cv2.GaussianBlur(gray, (5, 5), 1.0)
    residual = gray - smooth

    # 4. Find edges to reduce texture interference
    gx = cv2.Sobel(
        smooth, cv2.CV_32F, 1, 0, ksize=3
    )
    gy = cv2.Sobel(
        smooth, cv2.CV_32F, 0, 1, ksize=3
    )

    gradient = cv2.magnitude(gx, gy)

    tiles = []

    # 5. Analyze image blocks
    for y in range(0, h - tile_size + 1, tile_size):
        for x in range(0, w - tile_size + 1, tile_size):

            area = gray[
                y:y + tile_size,
                x:x + tile_size
            ]

            edges = gradient[
                y:y + tile_size,
                x:x + tile_size
            ]

            local_residual = residual[
                y:y + tile_size,
                x:x + tile_size
            ]

            # Prefer relatively smooth, unsaturated pixels
            flat = (
                (edges <= np.percentile(edges, 60))
                & (area > 12)
                & (area < 243)
            )

            if np.count_nonzero(flat) < tile_size * tile_size * 0.2:
                continue

            values = local_residual[flat]

            # Robust variability estimate using MAD
            median = np.median(values)

            sigma = 1.4826 * np.median(
                np.abs(values - median)
            )

            tiles.append((x, y, float(sigma)))

    # 6. Prepare output images
    heatmap = np.full(
        (h, w, 3), 45, dtype=np.uint8
    )

    overlay = rgb.copy()

    stats = {
        "analyzed_tiles": len(tiles),
        "flagged_tiles": 0,
        "median_residual": None,
        "sufficient_data": len(tiles) >= 8
    }

    if len(tiles) < 8:
        return (
            Image.fromarray(heatmap),
            Image.fromarray(overlay),
            stats
        )

    # 7. Calculate baseline noise variability
    values = np.array([tile[2] for tile in tiles])

    baseline = float(np.median(values))

    spread = 1.4826 * float(
        np.median(np.abs(values - baseline))
    )

    # Heuristic threshold, not a trained classifier
    threshold = max(
        1.5,
        3 * spread,
        0.4 * baseline
    )

    stats["median_residual"] = round(baseline, 2)

    flagged = 0

    # 8. Create heatmap and mark unusual blocks
    for x, y, sigma in tiles:

        deviation = abs(sigma - baseline)

        level = int(
            np.clip(
                255 * deviation / (2 * threshold),
                0,
                255
            )
        )

        color = cv2.applyColorMap(
            np.array([[level]], dtype=np.uint8),
            cv2.COLORMAP_TURBO
        )[0, 0, ::-1]

        heatmap[
            y:y + tile_size,
            x:x + tile_size
        ] = color

        if deviation >= threshold:
            flagged += 1

            cv2.rectangle(
                overlay,
                (x, y),
                (x + tile_size - 1,
                 y + tile_size - 1),
                (255, 65, 65),
                3
            )

    stats["flagged_tiles"] = flagged

    return (
        Image.fromarray(heatmap),
        Image.fromarray(overlay),
        stats
    )
