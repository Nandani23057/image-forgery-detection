
import cv2
import numpy as np
from PIL import Image, ImageOps


def detect_copy_move(image):
    """Find possible unrotated copy-move patterns."""

    rgb = np.array(
        ImageOps.exif_transpose(image).convert("RGB")
    )
    height, width = rgb.shape[:2]

    # Resize large images for faster analysis
    scale = min(1.0, 1400 / max(height, width))
    if scale < 1:
        rgb = cv2.resize(
            rgb,
            (round(width * scale), round(height * scale)),
            interpolation=cv2.INTER_AREA
        )

    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

    orb = cv2.ORB_create(
        nfeatures=3500,
        fastThreshold=12
    )

    keypoints, descriptors = orb.detectAndCompute(
        gray, None
    )

    stats = {
        "detected": False,
        "keypoints": len(keypoints),
        "candidate_pairs": 0,
        "consistent_pairs": 0
    }

    if descriptors is None or len(keypoints) < 20:
        return Image.fromarray(rgb), stats

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    neighbors = matcher.knnMatch(
        descriptors,
        descriptors,
        k=min(15, len(descriptors))
    )

    minimum_separation = max(
        40, 0.045 * np.hypot(width, height)
    )

    pairs = []
    seen = set()

    for nearby in neighbors:
        for match in nearby:
            if match.queryIdx == match.trainIdx:
                continue

            if match.distance > 48:
                break

            a, b = match.queryIdx, match.trainIdx

            point_a = np.array(keypoints[a].pt)
            point_b = np.array(keypoints[b].pt)

            if np.linalg.norm(
                point_a - point_b
            ) < minimum_separation:
                continue

            if tuple(point_a) > tuple(point_b):
                a, b = b, a

            if (a, b) not in seen:
                seen.add((a, b))
                pairs.append((a, b, match.distance))

            break

    stats["candidate_pairs"] = len(pairs)

    if len(pairs) < 12:
        return Image.fromarray(rgb), stats

    pairs = sorted(
        pairs, key=lambda item: item[2]
    )[:1200]

    # Find matches with similar displacement
    shifts = np.array([
        np.subtract(keypoints[b].pt, keypoints[a].pt)
        for a, b, _ in pairs
    ], dtype=np.float32)

    tolerance = max(
        8, 0.01 * np.hypot(width, height)
    )

    dx = shifts[:, None, 0] - shifts[None, :, 0]
    dy = shifts[:, None, 1] - shifts[None, :, 1]

    counts = np.count_nonzero(
        dx * dx + dy * dy <= tolerance ** 2,
        axis=1
    )

    center = shifts[int(np.argmax(counts))]

    good = (
        np.linalg.norm(shifts - center, axis=1)
        <= tolerance
    )

    center = np.median(shifts[good], axis=0)

    good = (
        np.linalg.norm(shifts - center, axis=1)
        <= tolerance
    )

    inliers = [
        pair for i, pair in enumerate(pairs)
        if good[i]
    ]

    stats["consistent_pairs"] = len(inliers)

    needed = max(
        12, int(np.ceil(0.05 * len(pairs)))
    )

    if len(inliers) < needed:
        return Image.fromarray(rgb), stats

    source = np.array([
        keypoints[a].pt for a, b, _ in inliers
    ])

    target = np.array([
        keypoints[b].pt for a, b, _ in inliers
    ])

    # Reject matches concentrated in tiny areas
    if (
        np.min(np.ptp(source, axis=0)) < 22
        or np.min(np.ptp(target, axis=0)) < 22
    ):
        return Image.fromarray(rgb), stats

    stats["detected"] = True

    visual = rgb.copy()
    overlay = visual.copy()

    regions = [
        (source, (255, 80, 80)),
        (target, (60, 220, 140))
    ]

    for points, color in regions:
        x1, y1 = np.maximum(
            np.min(points, axis=0).astype(int) - 15, 0
        )

        x2, y2 = np.minimum(
            np.max(points, axis=0).astype(int) + 15,
            [width - 1, height - 1]
        )

        cv2.rectangle(
            overlay, (x1, y1), (x2, y2), color, -1
        )

    visual = cv2.addWeighted(
        overlay, 0.18, visual, 0.82, 0
    )

    # Draw feature correspondence lines
    for a, b, _ in inliers[:35]:
        p = tuple(map(int, keypoints[a].pt))
        q = tuple(map(int, keypoints[b].pt))

        cv2.line(
            visual, p, q,
            (255, 215, 75), 1, cv2.LINE_AA
        )

        cv2.circle(
            visual, p, 4, (255, 80, 80), -1
        )

        cv2.circle(
            visual, q, 4, (60, 220, 140), -1
        )

    # Highlight suspected regions
    for points, color in regions:
        x1, y1 = np.maximum(
            np.min(points, axis=0).astype(int) - 15, 0
        )

        x2, y2 = np.minimum(
            np.max(points, axis=0).astype(int) + 15,
            [width - 1, height - 1]
        )

        cv2.rectangle(
            visual, (x1, y1), (x2, y2), color, 3
        )

    return Image.fromarray(visual), stats
