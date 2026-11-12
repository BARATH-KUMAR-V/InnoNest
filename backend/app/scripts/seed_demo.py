import argparse

import httpx

from app.demo.runner import API, login, run_scenario
from app.demo.scenarios import SCENARIOS


def main() -> None:
    parser = argparse.ArgumentParser(description="Create demonstration applications through the running API")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email", default="applicant@example.com")
    parser.add_argument("--password", default="Applicant@123")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=120) as client:
        headers = login(client, args.email, args.password)
        existing = client.get(f"{API}/applications", headers=headers, params={"page_size": 100}).json()["total"]
        if existing:
            print(f"{existing} applications already exist. Nothing was created.")
            return
        for key in SCENARIOS:
            result = run_scenario(client, headers, key)
            print(f"{key}: {result['reference']} -> {result['status']}")


if __name__ == "__main__":
    main()
