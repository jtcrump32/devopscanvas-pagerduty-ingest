SHELL := /bin/bash
.PHONY: bootstrap seed-alerts seed-changes seed-all ingest mock cleanup export docker-build compose-up compose-down

bootstrap:
	python3 scripts/pd_bootstrap.py

seed-alerts:
	python3 scripts/pd_seed_events.py --alerts

seed-changes:
	python3 scripts/pd_seed_events.py --changes

seed-all:
	python3 scripts/pd_seed_events.py --alerts --changes

ingest:
	PYTHONUNBUFFERED=1 python3 ingestion/ingester.py

mock:
	PYTHONUNBUFFERED=1 python3 mock/mock_server.py

cleanup:
	python3 scripts/pd_cleanup.py

export:
	curl -sS http://127.0.0.1:8000/export | jq '.' || true

docker-build:
	docker build -t devopscanvas/pagerduty-ingester:local .

compose-up:
	docker compose up --build -d clickhouse zookeeper kafka
	docker compose up --build ingester

compose-down:
	docker compose down -v
