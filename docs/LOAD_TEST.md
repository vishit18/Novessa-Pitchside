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

So the limit is not capacity. Three replicas serve 150 viewers at about 107 requests a second with the CPU at 71% on the busiest replica. The limit is the first minute of a sudden crowd. For judging, `API_MIN_REPLICAS` is 1 from 26 Oct; setting it to 2 would remove most of that window for a few dollars more. We have not changed it.

## What this does not measure

- The WebSocket feed. Locust does not drive it. The publish-to-overlay latency (budget 150 ms) is measured by the gateway itself and reported at `/live/health`; the last measurement from a laptop was p95 177 ms, and it has not been repeated from inside Azure.
- Anything that calls a model. Agent answers are slower than 4 s at the 95th percentile; that is in the Control Room, not here.
- A crowd larger than 150. The engines and the replica limit (3) are sized for the demo, not for a stadium.

## Cost

The service bills by virtual-user hour: about 6 for this run (150 users for 5 minutes, plus ramp), well under a dollar. A mistake on the first run (a run time in minutes where seconds were meant) lasted 5 seconds and cost nothing.

## Run it again

```bash
az load test-run create --load-test-resource lt-uirzml34ufpge -g pitchside \
  --test-id pitchside-gateway --test-run-id run-2 --display-name "150 viewers, 300 seconds"
```

Locally, against any gateway: `uvx locust -f loadtest/locustfile.py --host http://localhost:8000`.
