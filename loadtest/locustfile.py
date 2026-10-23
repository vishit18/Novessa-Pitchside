"""Load test for the Pitchside gateway, run by Azure Load Testing (docs/LOAD_TEST.md).

Viewers do this all match long: look at the match state, the shape of the match so far, the
spoiler-safe catch-up, the key moments. All of it is deterministic and answered from memory or
the shared cache, so the test costs no model tokens. Recap and Ask are left out on purpose: they
are rate limited per client and the load generators share a few addresses.

Run it locally against a gateway:  locust -f loadtest/locustfile.py --host http://localhost:8000
"""

import os
import random

from locust import HttpUser, between, task

MATCHES = ["derby_01", "derby_02", "derby_03"]
MATCH_SECONDS = 5400
CLIP = "117093_w1890"


def _t() -> int:
    """A viewer's clock somewhere in the match."""
    return random.randint(60, MATCH_SECONDS)


class Viewer(HttpUser):
    """One person with a match open."""

    host = os.environ.get("TARGET_HOST", "http://localhost:8000")
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        self.match = random.choice(MATCHES)

    @task(5)
    def state(self) -> None:
        self.client.get(
            f"/matches/{self.match}/state", params={"t": _t()}, name="/matches/:id/state"
        )

    @task(3)
    def pulse(self) -> None:
        self.client.get(
            f"/matches/{self.match}/pulse", params={"t": _t()}, name="/matches/:id/pulse"
        )

    @task(2)
    def catchup(self) -> None:
        self.client.get(
            f"/matches/{self.match}/catchup", params={"t": _t()}, name="/matches/:id/catchup"
        )

    @task(1)
    def moments(self) -> None:
        self.client.get(f"/matches/{self.match}/moments", name="/matches/:id/moments")

    @task(1)
    def match_info(self) -> None:
        self.client.get(f"/matches/{self.match}", name="/matches/:id")

    @task(2)
    def matches(self) -> None:
        self.client.get("/matches")

    @task(1)
    def health(self) -> None:
        self.client.get("/health")

    @task(1)
    def real_footage_data(self) -> None:
        """The biggest single response: the tracking overlay for the real clip (about 800 kB)."""
        self.client.get(f"/real/{CLIP}/overlay", name="/real/:clip/overlay")
