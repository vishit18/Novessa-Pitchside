"""Pixel to pitch calibration for SoccerTrack v2 footage (real footage only, see docs/06).

The panorama is lens-distorted. The dataset ships OpenCV undistortion maps and 65 hand-annotated
pitch keypoints per match, so no manual clicking is needed. A pixel on the original frame is
undistorted first, then mapped to the pitch with a homography fitted to the keypoints.

Coordinates: the dataset's keypoints use a corner origin (0..105 by 0..68). Our own schema, and
the rest of this repo, uses metres with the origin bottom-left, so `to_pitch` returns that.
The dataset's labels use a centre origin; `from_dataset_centre` converts them for evaluation only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray
from scipy.spatial import cKDTree

Array = NDArray[np.float64]

PITCH_LENGTH = 105.0
PITCH_WIDTH = 68.0


def from_dataset_centre(xy: Array) -> Array:
    """Dataset label coordinates (centre origin, y towards the near touchline) to ours.

    Ours: origin bottom-left, y up the pitch. The near touchline is at the bottom of the image,
    so y flips.
    """
    out = np.asarray(xy, dtype=np.float64).copy()
    out[..., 0] += PITCH_LENGTH / 2
    out[..., 1] = PITCH_WIDTH / 2 - out[..., 1]
    return out


def _fit_homography(src: Array, dst: Array) -> tuple[Array, Array]:
    """RANSAC homography and its inlier mask."""
    h, mask = cv2.findHomography(src, dst, cv2.RANSAC, 6.0)
    if h is None:
        raise ValueError("could not fit a homography to the keypoints")
    return h.astype(np.float64), mask.ravel().astype(bool)


@dataclass
class PitchCalibration:
    """Maps pixels of the original (distorted) frame to pitch metres and back."""

    map_x: NDArray[np.float32]  # undistorted (u, v) -> source x on the distorted frame
    map_y: NDArray[np.float32]
    tree: cKDTree
    h_pixel_to_pitch: Array  # undistorted pixel -> pitch (corner origin)
    h_pitch_to_pixel: Array
    keypoint_residual_m: float
    inliers: int

    @classmethod
    def load(cls, raw_dir: Path, match: str = "117093") -> PitchCalibration:
        """Read the dataset's maps and keypoints from `raw_dir` (footage/raw/raw/<match>)."""
        d = raw_dir
        map1 = np.load(d / f"{match}_mapx.npy", allow_pickle=False)
        map2 = np.load(d / f"{match}_mapy.npy", allow_pickle=False)
        map_x, map_y = cv2.convertMaps(map1, map2, cv2.CV_32FC1)
        # Inverse lookup: for a point on the distorted frame, which undistorted pixel is it?
        tree = cKDTree(np.c_[map_x.ravel(), map_y.ravel()])
        keypoints = json.loads((d / f"{match}_keypoints.json").read_text("utf-8"))
        pitch = np.array([[float(v) for v in k.strip("()").split(",")] for k in keypoints])
        distorted = np.array(list(keypoints.values()), dtype=np.float64)
        cal = cls(map_x, map_y, tree, np.eye(3), np.eye(3), 0.0, 0)
        undistorted = cal.undistort_points(distorted)
        h_p2px, mask = _fit_homography(pitch, undistorted)
        h_px2p = np.linalg.inv(h_p2px)
        cal.h_pitch_to_pixel = h_p2px
        cal.h_pixel_to_pitch = h_px2p
        back = _apply(h_px2p, undistorted)
        cal.keypoint_residual_m = float(np.median(np.linalg.norm(back - pitch, axis=1)[mask]))
        cal.inliers = int(mask.sum())
        return cal

    def undistort_points(self, pts: Array) -> Array:
        """Points on the original frame to undistorted pixel coordinates."""
        pts = np.asarray(pts, dtype=np.float64).reshape(-1, 2)
        dist, idx = self.tree.query(pts, k=4)
        # Weight the four nearest map entries by closeness for sub-pixel accuracy.
        w = 1.0 / (dist + 1e-6)
        w /= w.sum(axis=1, keepdims=True)
        width = self.map_x.shape[1]
        v, u = np.divmod(idx, width)
        return np.c_[(u * w).sum(axis=1), (v * w).sum(axis=1)]

    def to_pitch(self, pts: Array) -> Array:
        """Foot points on the original frame to pitch metres, origin bottom-left."""
        corner = _apply(self.h_pixel_to_pitch, self.undistort_points(pts))
        # The near touchline (y = 68 in keypoints) is the bottom of the image. Ours has y up.
        return np.c_[corner[:, 0], PITCH_WIDTH - corner[:, 1]]

    def to_pixel(self, pitch: Array) -> Array:
        """Pitch metres (origin bottom-left) to undistorted pixel coordinates."""
        p = np.asarray(pitch, dtype=np.float64).reshape(-1, 2)
        corner = np.c_[p[:, 0], PITCH_WIDTH - p[:, 1]]
        return _apply(self.h_pitch_to_pixel, corner)


def _apply(h: Array, pts: Array) -> Array:
    q = np.c_[pts, np.ones(len(pts))] @ h.T
    return q[:, :2] / q[:, 2:3]
