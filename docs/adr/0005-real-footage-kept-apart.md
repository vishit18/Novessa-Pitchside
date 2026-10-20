# 0005. Real footage never touches the synthetic engine

Status: accepted

## Context

The brief wants a synthetic dataset, and also real footage to show that auto-eventing works. Mixing them would make the synthetic claim worthless.

## Decision

SoccerTrack v2 (CC BY 4.0) lives only in `vision/`. It is used for two things: showing that the pipeline works on video, and scoring the output against the dataset's own labels. It is never used to build, train, tune or calibrate the synthetic engine, never mixed into synthetic matches, and never given to the agents as if it were synthetic. Everything it produces is tagged `source: "vision"` and shown only in Real footage mode, with the credit visible. The engine is calibrated against general football ranges written down in `docs/03`.

## Consequences

- The synthetic data has a clean story: nothing in it came from real data.
- The synthetic engine cannot borrow realism from the real footage, so some of it is only as good as the reference ranges.
