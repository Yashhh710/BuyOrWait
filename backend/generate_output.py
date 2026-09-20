"""Generate the official challenge output without modifying official inputs."""
from data_service import get_request_context, list_requests
from financial_engine import calculate_facts
from ai_service import get_dataset_decision
from output_service import write_output


def main() -> None:
    rows = []
    facts_by_request = {}
    for request in list_requests():
        request_id = str(request["request_id"])
        context = get_request_context(request_id)
        if context is None:
            continue
        facts = calculate_facts(context)
        decision, _ = get_dataset_decision(context, facts)
        rows.append(decision)
        facts_by_request[request_id] = facts
    path = write_output(rows, facts_by_request)
    print(f"Wrote {len(rows)} verified predictions to {path}")


if __name__ == "__main__":
    main()
