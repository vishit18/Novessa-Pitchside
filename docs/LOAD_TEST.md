# Load test

One run against the live gateway on 23 Oct, from Azure Load Testing (`lt-uirzml34ufpge`, Sweden Central, the same region as the API). The test is `loadtest/locustfile.py`, the settings are in `loadtest/config.yaml`.

## What it does

Each virtual viewer opens one of the three demo matches and keeps asking what a person watching asks: the match state at their clock, the shape of the match so far, the spoiler-safe catch-up, the key moments. A few also fetch the real-footage tracking data, the largest single response (about 800 kB). Everything is deterministic and answered from memory or the shared cache, so the run costs no model tokens. Recap and Ask are left out on purpose: they are rate limited per client, and the load generators share two addresses.

Load: 150 viewers across two engines, 5 more a second, for 300 seconds. Pass criteria: error rate under 2%, p95 response time under 1,500 ms.

## Result

| | |
|---|---|
| Requests | 32,120 |
| Errors | 0 (every response was a 200) |
| Throughput | about 107 requests a second, steady for the last three minutes |
| Median response | 5 ms |
| p90 / p95 / p99 | 9 ms / 11 ms / 271 ms |
| Slowest | 18.3 s (see below) |
| Data sent | about 1.75 GB |
| API replicas | 1 at the start, 3 from 18:22, 0 after the run (scale to zero) |

By request, the slowest typical response was the real-footage data (p50 11 ms, p95 19 ms). Match state, pulse, catch-up and moments were all under 12 ms at p95.

Numbers were computed from the raw per-request results the service saves (`engine1_results.csv`, `engine2_results.csv`), 32,120 rows. The run summary in the portal was not populated when we looked, so these are not from its dashboard.

## What the run showed

The first minute was fine (p95 12 ms). In the second minute, with all 150 viewers on one replica, p95 rose to 2.1 s while the app scaled out. From the third minute, with three replicas, p95 was 10 ms and stayed there. That spike is the whole of the p99 and the 18 s maximum: requests that landed on a replica that was still starting and building the match timelines.

So the limit is not capacity. Three replicas serve 150 viewers at about 107 requests a second with the CPU at 71% on the busiest replica. The limit is the first minute of a sudden crowd. For judging we set `API_MIN_REPLICAS` to 2 on 23 Oct, after this run, so two replicas are always up. The run above was made with 1 and has not been repeated with 2, so we have not shown that the spike is gone.

## Publish-to-overlay latency (the 150 ms budget)

Locust cannot drive the WebSocket feed, so the live path was measured separately with `scripts/measure_live.py`, run as a one-off Container Apps Job in the same region and environment as the API, through the real Event Hub with the managed identity. It streams a match onto the bus at replay speed and times every message from the moment it was wrapped for publishing to the moment its instant overlay was ready. Publisher and consumer are in one process, so there is no clock skew.

| Run | Messages | Overlays | Overlay p50 | p95 | Slowest | Result |
|---|---|---|---|---|---|---|
| Event Hubs, 4x replay, first 900 match seconds | 4,966, none lost | 56 | 75 ms | 140 ms | 147 ms | inside the 150 ms budget |
| Event Hubs, 30x, first 2,700 match seconds | 14,864, none lost | 202 | 70 ms | 115 ms | 294 ms | p95 inside budget, one slow tail |
| In memory, same host, 4x and 30x (for comparison) | 3,320 and 14,864 | 36 and 202 | 15 to 50 ms | 51 to 54 ms | 55 ms | |

Read it plainly. Event Hubs adds about 25 ms at the median and about 90 ms at the tail over the in-memory bus. The 4x pass is the speed the app replays at, and its p95 of 140 ms is close to the line, so there is little room. From a laptop the same hop was 177 ms at p95 on 20 Oct, so the earlier miss was most likely the distance between the laptop and Sweden Central; a short laptop run the same day was slower still (p95 about 600 ms on 2 overlays, too few to rely on).

Numbers come from the job's own log output. A first attempt reported the in-memory bus under an Event Hubs label because the job's settings had been overridden and the code fell back silently; the script now refuses to run if it does not get the bus it was asked for. A second attempt hung for 15 minutes with no output and was stopped; the script now prints progress and gives up a pass after its expected time plus two minutes. The later runs finished in 6 minutes and the cause of that one hang is not known.

## What this does not measure

- The last hop: the WebSocket from the gateway to a browser, and drawing the overlay. The budget here covers the bus and the overlay builder, which is the part the server controls.
- Anything that calls a model. Agent answers are slower than 4 s at the 95th percentile; that is in the Control Room, not here.
- A crowd larger than 150, or many live matches at once. The engines and the replica limit (3) are sized for the demo, not for a stadium.

## Cost

The service bills by virtual-user hour: about 13 for this run (150 users for 5 minutes, plus ramp). At the usual rate of around 15 cents an hour that is about $2; we have not checked it against the bill. The latency jobs ran about 25 minutes in all on one core and 2 GiB, plus a few image builds in the registry, pennies. A first load-test run with the run time in minutes instead of seconds lasted 5 seconds.

## Run it again

```bash
az load test-run create --load-test-resource lt-uirzml34ufpge -g pitchside \
  --test-id pitchside-gateway --test-run-id run-2 --display-name "150 viewers, 300 seconds"
```

Locally, against any gateway: `uvx locust -f loadtest/locustfile.py --host http://localhost:8000`.
