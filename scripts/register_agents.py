"""Publish our seven prompts as prompt agents in Foundry Agent Service.

    uv run python -m scripts.register_agents --dry-run   # show what would change
    uv run python -m scripts.register_agents             # create new versions where needed

Needs FOUNDRY_PROJECT_ENDPOINT and the Azure AI User role on the Foundry project for your
`az login` identity (keyless). An agent only gets a new version when its prompt or model
changed, so re-running is cheap and safe. Run it after editing anything in
backend/agents/prompts/; with FOUNDRY_AGENT_SERVICE=true the app refuses to call an agent
whose latest version does not match the prompt in the checkout, and calls the model directly.
"""

from __future__ import annotations

import argparse
import os

import httpx
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

from backend.agents.foundry_agents import AI_SCOPE, API_VERSION, agent_specs, matches


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true", help="look, change nothing")
    args = parser.parse_args()

    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
    if not endpoint:
        raise SystemExit(
            "set FOUNDRY_PROJECT_ENDPOINT (https://<res>.services.ai.azure.com/api/projects/<p>)"
        )
    token = DefaultAzureCredential().get_token(AI_SCOPE).token
    with httpx.Client(
        headers={"Authorization": f"Bearer {token}"},
        params={"api-version": API_VERSION},
        timeout=30,
    ) as client:
        for spec in agent_specs():
            resp = client.get(f"{endpoint}/agents/{spec.name}")
            if resp.status_code == 200 and matches(spec, resp.json()):
                version = resp.json()["versions"]["latest"]["version"]
                print(f"{spec.name:22} up to date (version {version}, {spec.model})")
                continue
            if resp.status_code not in (200, 404):
                raise SystemExit(f"{spec.name}: {resp.status_code} {resp.text}")
            what = "new agent" if resp.status_code == 404 else "prompt or model changed"
            if args.dry_run:
                print(f"{spec.name:22} would publish ({what})")
                continue
            made = client.post(
                f"{endpoint}/agents/{spec.name}/versions", json=spec.version_request()
            )
            if made.status_code >= 400:
                raise SystemExit(f"{spec.name}: {made.status_code} {made.text}")
            print(f"{spec.name:22} published version {made.json()['version']} ({what})")


if __name__ == "__main__":
    main()
