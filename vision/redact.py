"""Remove third-party marks from real footage before it is shown (docs/06).

The SoccerTrack v2 pitch for match 117093 has a university name and crest painted on the turf in
the foreground. The camera is fixed, so the marks sit in the same place in every frame. We find
the white paint inside a fixed region and fill it from the surrounding turf. Detection and
tracking run on the original frames; only what a viewer sees is redacted.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Frame = NDArray[Any]  # BGR image of any numeric dtype, as OpenCV hands them out

# Polygon around the painted wordmark and crest, as fractions of the frame (x / width, y / height).
# Drawn generously: only bright, low-saturation pixels inside it are treated as paint, so the turf
# stripes and the shadows are left alone.
MARK_REGION = np.array(
    [
        (0.125, 0.640), (0.175, 0.628), (0.255, 0.652), (0.400, 0.690), (0.530, 0.700),
        (0.600, 0.685), (0.640, 0.660), (0.690, 0.690), (0.820, 0.640), (0.880, 0.585),
        (0.885, 0.700), (0.800, 0.790), (0.700, 0.880), (0.560, 0.935), (0.420, 0.915),
        (0.300, 0.870), (0.200, 0.825), (0.130, 0.790),
    ],
    dtype=np.float64,
)  # fmt: skip


def mark_mask(shape: tuple[int, ...], paint_only: bool = True, frame: Frame | None = None) -> Frame:
    """Boolean-style mask (255 = redact) for a frame of `shape` (h, w, ...)."""
    h, w = shape[:2]
    region = np.zeros((h, w), np.uint8)
    pts = (MARK_REGION * np.array([w, h])).astype(np.int32)
    cv2.fillPoly(region, [pts], 255)
    if not paint_only or frame is None:
        return region
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # Paint is pale: low saturation and bright. Turf is saturated green.
    paint = ((hsv[..., 1] < 70) & (hsv[..., 2] > 150)).astype(np.uint8) * 255
    mask = cv2.bitwise_and(paint, region)
    # Grow it so anti-aliased edges are covered too.
    return cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)), iterations=1)


def redact(frame: Frame) -> Frame:
    """The frame with the painted marks filled in from the turf around them."""
    mask = mark_mask(frame.shape, frame=frame)
    if not mask.any():
        return frame
    radius = max(3, round(frame.shape[1] / 600))
    return cv2.inpaint(frame, mask, radius, cv2.INPAINT_TELEA)
