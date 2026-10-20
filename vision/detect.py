"""Person and ball detection on a 4K panorama, by tiling. Apache-2.0 model, no Ultralytics.

Players are about 60 px tall and the ball under 15 px in a 4096x1080 panorama, so the frame is
cut into overlapping tiles at native resolution (no downscaling) over the band of the image that
holds the pitch. Detections from all tiles are mapped back to frame coordinates and merged with
non-maximum suppression.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from numpy.typing import NDArray
from torchvision.ops import nms
from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

MODEL_ID = "PekingU/rtdetr_r50vd"  # Apache-2.0
COCO_PERSON = 0
COCO_BALL = 32

Frame = NDArray[Any]
Boxes = NDArray[np.float32]  # N x 4, x1 y1 x2 y2 in frame pixels


@dataclass(frozen=True)
class Detections:
    """People and balls found in one frame."""

    person_boxes: Boxes
    person_scores: NDArray[np.float32]
    ball_boxes: Boxes
    ball_scores: NDArray[np.float32]


class TileDetector:
    """RT-DETR over overlapping tiles of a fixed band of the frame."""

    def __init__(
        self,
        *,
        roi: tuple[int, int, int, int] = (0, 130, 4096, 770),
        tile: int = 640,
        overlap: int = 128,
        person_threshold: float = 0.25,
        ball_threshold: float = 0.06,
        device: str | None = None,
    ) -> None:
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.roi, self.tile, self.overlap = roi, tile, overlap
        self.person_threshold, self.ball_threshold = person_threshold, ball_threshold
        self.processor = RTDetrImageProcessor.from_pretrained(MODEL_ID)
        self.model = RTDetrForObjectDetection.from_pretrained(MODEL_ID).to(self.device).eval()  # type: ignore[arg-type]
        if self.device == "cuda":
            self.model.half()
        x0, y0, x1, y1 = roi
        step = tile - overlap
        self.origins = [
            (x, y)
            for y in range(y0, max(y0 + 1, y1 - tile + step), step)
            for x in range(x0, max(x0 + 1, x1 - tile + step), step)
        ]
        # Pull the last tile in so it ends on the ROI edge instead of running past it.
        self.origins = [(min(x, x1 - tile), min(y, y1 - tile)) for x, y in self.origins]
        self.origins = sorted(set(self.origins))

    @torch.inference_mode()
    def detect(self, frame: Frame) -> Detections:
        """Detect people and the ball in one BGR frame."""
        tiles = np.stack([frame[y : y + self.tile, x : x + self.tile] for x, y in self.origins])
        rgb = np.ascontiguousarray(tiles[..., ::-1])
        batch = torch.from_numpy(rgb).to(self.device).permute(0, 3, 1, 2).float() / 255.0
        if self.device == "cuda":
            batch = batch.half()
        out = self.model(pixel_values=batch)  # type: ignore[arg-type]
        sizes = torch.tensor([[self.tile, self.tile]] * len(self.origins))
        results = self.processor.post_process_object_detection(
            out,
            threshold=min(self.person_threshold, self.ball_threshold),
            target_sizes=sizes,  # type: ignore[arg-type]
        )
        people: list[torch.Tensor] = []
        person_scores: list[torch.Tensor] = []
        balls: list[torch.Tensor] = []
        ball_scores: list[torch.Tensor] = []
        for (ox, oy), r in zip(self.origins, results, strict=True):
            boxes = r["boxes"].float().cpu() + torch.tensor([ox, oy, ox, oy])
            scores, labels = r["scores"].float().cpu(), r["labels"].cpu()
            p = (labels == COCO_PERSON) & (scores >= self.person_threshold)
            b = (labels == COCO_BALL) & (scores >= self.ball_threshold)
            people.append(boxes[p])
            person_scores.append(scores[p])
            balls.append(boxes[b])
            ball_scores.append(scores[b])
        pb, ps = _merge(people, person_scores, iou=0.5)
        bb, bs = _merge(balls, ball_scores, iou=0.4)
        return Detections(pb, ps, bb, bs)


def _merge(
    boxes: list[torch.Tensor], scores: list[torch.Tensor], iou: float
) -> tuple[Boxes, NDArray[np.float32]]:
    b = torch.cat(boxes) if boxes else torch.zeros((0, 4))
    s = torch.cat(scores) if scores else torch.zeros(0)
    if len(b) == 0:
        return np.zeros((0, 4), np.float32), np.zeros(0, np.float32)
    keep = nms(b, s, iou)
    return b[keep].numpy().astype(np.float32), s[keep].numpy().astype(np.float32)
