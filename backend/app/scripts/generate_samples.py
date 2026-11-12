import argparse
import json
from pathlib import Path

from app.core.config import settings
from app.demo.scenarios import SCENARIOS, generate_documents
from app.services import docgen


def main() -> None:
    parser = argparse.ArgumentParser(description="Write synthetic specimen documents for every demo scenario")
    parser.add_argument("--out", type=Path, default=settings.sample_dir)
    args = parser.parse_args()
    index = []
    for key, scenario in SCENARIOS.items():
        folder = args.out / key
        folder.mkdir(parents=True, exist_ok=True)
        files = []
        for item in generate_documents(scenario):
            (folder / item["filename"]).write_bytes(item["content"])
            files.append(item["filename"])
            if item["doc_type"] == "SALARY_SLIP" and key == "clean_home_loan":
                (folder / "salary_slip_scanned.png").write_bytes(docgen.to_scan(item["content"]))
                files.append("salary_slip_scanned.png")
        index.append({"scenario": key, "title": scenario.title, "expected_outcome": scenario.expected, "files": files})
        if scenario.omit:
            held = generate_documents(scenario, only=scenario.omit)
            extra = folder / "to_upload_later"
            extra.mkdir(exist_ok=True)
            for item in held:
                (extra / item["filename"]).write_bytes(item["content"])
    (args.out / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"Wrote samples for {len(index)} scenarios to {args.out}")


if __name__ == "__main__":
    main()
