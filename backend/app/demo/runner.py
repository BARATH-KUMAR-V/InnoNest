from app.demo.scenarios import ALL_CONSENTS, SCENARIOS, Scenario, generate_documents

API = "/api/v1"


def login(client, email: str, password: str) -> dict:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    response.raise_for_status()
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def upload(client, headers: dict, application_id: int, applicant_ids: list[int], item: dict) -> dict:
    response = client.post(f"{API}/applications/{application_id}/documents", headers=headers, data={"doc_type": item["doc_type"], "applicant_id": str(applicant_ids[item["applicant_index"]])},
                           files={"file": (item["filename"], item["content"], "application/pdf")})
    response.raise_for_status()
    return response.json()


def create_draft(client, headers: dict, scenario: Scenario) -> dict:
    response = client.post(f"{API}/applications", headers=headers, json=scenario.application)
    response.raise_for_status()
    application = response.json()
    consent = client.post(f"{API}/applications/{application['id']}/consents", headers=headers, json={"scopes": ALL_CONSENTS})
    consent.raise_for_status()
    return consent.json()


def run_scenario(client, headers: dict, key: str, submit: bool = True) -> dict:
    return run_scenario_object(client, headers, SCENARIOS[key], submit)


def run_scenario_object(client, headers: dict, scenario: Scenario, submit: bool = True) -> dict:
    application = create_draft(client, headers, scenario)
    ids = [a["id"] for a in application["applicants"]]
    for item in generate_documents(scenario):
        upload(client, headers, application["id"], ids, item)
    if submit:
        response = client.post(f"{API}/applications/{application['id']}/submit", headers=headers)
        response.raise_for_status()
        return response.json()
    return application
