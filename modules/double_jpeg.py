
"""Exploratory JPEG double-quantization analysis.

This is an indicator, not a validated authenticity classifier.
Input: original JPEG file bytes (not a re-exported Pillow image).
"""

from io import BytesIO

import cv2
import numpy as np
from PIL import Image


def analyze_double_jpeg(file_bytes, max_blocks=10000):
    with Image.open(BytesIO(file_bytes)) as jpeg:
        if jpeg.format != "JPEG":
            return {"supported": False, "reason": "JPEG files only. PNG does not contain JPEG quantization tables."}

        tables = jpeg.quantization or {}
        if not tables:
            return {"supported": False, "reason": "JPEG quantization tables are unavailable."}

        primary_table = tables.get(0)
        if primary_table is None:
            primary_table = next(iter(tables.values()))
        qtable = np.asarray(primary_table, dtype=np.float32).reshape(8, 8)

        luminance = np.asarray(jpeg.convert("YCbCr"), dtype=np.uint8)[:, :, 0]

    block_rows = luminance.shape[0] // 8
    block_cols = luminance.shape[1] // 8
    total_blocks = block_rows * block_cols
    bins = list(range(-14, 15))

    if total_blocks == 0:
        return {"supported": False, "reason": "JPEG is too small for 8x8-block analysis."}

    indices = np.linspace(
        0, total_blocks - 1, min(max_blocks, total_blocks), dtype=int
    )
    quantization_step = max(float(qtable[1, 2]), 1.0)
    coefficients = []

    for index in indices:
        row, col = divmod(int(index), block_cols)
        block = luminance[row * 8:(row + 1) * 8, col * 8:(col + 1) * 8]
        dct = cv2.dct(block.astype(np.float32) - 128.0)
        coefficients.append(int(np.rint(dct[1, 2] / quantization_step)))

    values = np.asarray(coefficients)
    counts = [int(np.count_nonzero(values == k)) for k in bins]

    # Look for mirrored gaps between populated histogram bins.
    # These can occur with double quantization, but are not unique to forgery.
    gaps = []
    for k in range(-12, 13):
        if abs(k) < 3:
            continue
        pos = k + 14
        if (counts[pos - 1] >= 7 and counts[pos + 1] >= 7
                and counts[pos] <= 0.2 * min(counts[pos - 1], counts[pos + 1])):
            gaps.append(k)

    mirror_pairs = [k for k in gaps if k > 0 and -k in gaps]
    enough_signal = len(values) >= 1000 and int(np.count_nonzero(np.abs(values) >= 3)) >= 100
    if not enough_signal:
        status = "Limited evidence"
    elif len(mirror_pairs) >= 2:
        status = "Possible double-quantization pattern"
    else:
        status = "No clear double-quantization pattern"

    return {
        "supported": True,
        "status": status,
        "blocks_analyzed": len(values),
        "quant_tables": len(tables),
        "ac_quant_step": int(qtable[1, 2]),
        "histogram_bins": bins,
        "histogram_counts": counts,
        "gap_bins": gaps,
    }
