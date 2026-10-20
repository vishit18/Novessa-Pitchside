# 0007. RT-DETR for detection, not Ultralytics YOLO

Status: accepted

## Context

The vision pipeline needs a person and ball detector. The repo is MIT, and Ultralytics YOLO is AGPL, which would pull the repo's licence toward AGPL.

## Decision

Use RT-DETR (`PekingU/rtdetr_r50vd`, Apache 2.0) through Hugging Face Transformers.

## Consequences

- The licence stays compatible with the MIT repo.
- The ball is the weak spot: it is followed in about half of the frames. A dedicated small-object ball detector would help, and is the next step.
