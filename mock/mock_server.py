#!/usr/bin/env python3
import json, os
from flask import Flask, jsonify
app=Flask(__name__)
MOCK={
  "services":[{"id":"SVC1","name":"Payments API"},{"id":"SVC2","name":"Orders API"}],
  "schedules":[{"id":"SCH1","name":"Demo Primary On-Call"}],
  "oncalls":[{"user":{"summary":"Alice Oncall"},"schedule":{"summary":"Demo Primary On-Call"}}],
  "incidents":[
    {"id":"INC1","summary":"Payments latency spike #1","status":"resolved","urgency":"high","created_at":"2025-08-30T18:00:00Z","acknowledged_at":"2025-08-30T18:02:00Z","resolved_at":"2025-08-30T18:10:00Z","service":{"id":"SVC1","summary":"Payments API"}},
    {"id":"INC2","summary":"Orders error rate","status":"acknowledged","urgency":"low","created_at":"2025-08-31T00:00:00Z","acknowledged_at":"2025-08-31T00:03:00Z","service":{"id":"SVC2","summary":"Orders API"}}
  ],
  "alerts_by_incident":{"INC1":[{"id":"AL1","created_at":"2025-08-30T18:00:05Z"}],"INC2":[{"id":"AL2","created_at":"2025-08-31T00:00:10Z"}]},
  "log_entries_by_incident":{"INC1":[{"type":"acknowledge_log_entry"}]},
  "change_events":[{"id":"CH1","summary":"Payments deploy 1","created_at":"2025-08-30T17:55:00Z"}]
}
@app.route("/snapshot")
def snapshot():
    return jsonify({"ok":True,"data": {"metrics":{}, **MOCK}})
@app.route("/metrics")
def metrics():
    return jsonify({"ok":True,"metrics":{"counts":{"incidents_total":2,"by_status":{"triggered":0,"acknowledged":1,"resolved":1},"by_urgency":{"high":1,"low":1}},"mttr_seconds_median":600,"mtta_seconds_median":150,"per_service":{"Payments API":{"counts":{"total":1,"triggered":0,"acknowledged":0,"resolved":1},"mtta_median":120,"mttr_median":600},"Orders API":{"counts":{"total":1,"triggered":0,"acknowledged":1,"resolved":0},"mtta_median":180,"mttr_median":null}}}})
@app.route("/export")
def export():
    os.makedirs("data/export", exist_ok=True)
    with open("data/export/pagerduty_snapshot.mock.json","w") as f:
        json.dump(MOCK,f,indent=2)
    return jsonify({"ok":True,"path":"data/export/pagerduty_snapshot.mock.json"})
if __name__=="__main__":
    print("Starting mock server on :9000"); app.run(host="0.0.0.0", port=9000)
