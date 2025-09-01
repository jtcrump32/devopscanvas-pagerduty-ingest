#!/usr/bin/env python3
import os, json, time, datetime as dt
from flask import Flask, jsonify
from dotenv import load_dotenv
from scripts.common import env, pd_get, paginate
from ingestion.broker import kafka_producer, kafka_send, clickhouse_client, ch_ensure_tables, ch_insert_incidents, ch_insert_alerts, ch_insert_changes
load_dotenv()
app = Flask(__name__)
CACHE={"snapshot":{}, "ts":0}; KAFKA_PRODUCER=None; CLICKHOUSE=None
def since_until(days):
    until = dt.datetime.utcnow(); since = until - dt.timedelta(days=int(env("INGEST_SINCE_DAYS","7")))
    return since.replace(microsecond=0).isoformat()+"Z", until.replace(microsecond=0).isoformat()+"Z"
def list_incidents(since, until):
    return list(paginate("/incidents","incidents",params={"since":since,"until":until,"limit":100,"statuses[]":["triggered","acknowledged","resolved"]}))
def list_alerts_for_incident(incident_id):
    return list(paginate(f"/incidents/{incident_id}/alerts","alerts",params={"limit":100}))
def list_log_entries_for_incident(incident_id):
    return list(paginate(f"/incidents/{incident_id}/log_entries","log_entries",params={"limit":100,"include[]":["channels","actors"]}))
def list_services():
    return list(paginate("/services","services",params={"limit":100}))
def list_schedules():
    return list(paginate("/schedules","schedules",params={"limit":100}))
def list_oncalls(since, until):
    return list(paginate("/oncalls","oncalls",params={"limit":100,"since":since,"until":until}))
def list_change_events(since, until):
    try:
        return list(paginate("/change_events","change_events",params={"since":since,"until":until,"limit":100}))
    except Exception:
        return []
def compute_metrics(snapshot):
    inc = snapshot.get("incidents",[])
    by_status={"triggered":0,"acknowledged":0,"resolved":0}; by_urgency={"high":0,"low":0}
    ack_durs=[]; res_durs=[]; per_service={}
    def median(a): 
        if not a: return None
        a=sorted(a); m=len(a)//2
        return a[m] if len(a)%2 else (a[m-1]+a[m])/2
    for i in inc:
        st=i.get("status"); urg=i.get("urgency")
        if st in by_status: by_status[st]+=1
        if urg in by_urgency: by_urgency[urg]+=1
        svc=(i.get("service") or {}); svc_name=svc.get("summary") or svc.get("name") or "unknown"
        b=per_service.setdefault(svc_name,{"_acks":[],"_ress":[],"counts":{"total":0,"triggered":0,"acknowledged":0,"resolved":0}})
        b["counts"]["total"]+=1
        if st in b["counts"]: b["counts"][st]+=1
        created = dt.datetime.fromisoformat(i["created_at"].replace("Z","+00:00"))
        if i.get("acknowledged_at"):
            ad=(dt.datetime.fromisoformat(i["acknowledged_at"].replace("Z","+00:00"))-created).total_seconds()
            ack_durs.append(ad); b["_acks"].append(ad)
        if i.get("status")=="resolved" and i.get("resolved_at"):
            rd=(dt.datetime.fromisoformat(i["resolved_at"].replace("Z","+00:00"))-created).total_seconds()
            res_durs.append(rd); b["_ress"].append(rd)
    for s,b in per_service.items():
        b["mtta_median"]=median(b.pop("_acks"))
        b["mttr_median"]=median(b.pop("_ress"))
    return {"counts":{"incidents_total":len(inc),"by_status":by_status,"by_urgency":by_urgency},
            "mtta_seconds_median":median(ack_durs),"mttr_seconds_median":median(res_durs),"per_service":per_service}
def refresh():
    since, until = since_until(int(env("INGEST_SINCE_DAYS","7")))
    data={}
    data["services"]=list_services(); data["schedules"]=list_schedules(); data["oncalls"]=list_oncalls(since, until)
    data["incidents"]=list_incidents(since, until)
    alerts_map={}; logs_map={}
    for inc in data["incidents"][:50]:
        iid=inc["id"]; alerts_map[iid]=list_alerts_for_incident(iid); logs_map[iid]=list_log_entries_for_incident(iid)
    data["alerts_by_incident"]=alerts_map; data["log_entries_by_incident"]=logs_map
    data["change_events"]=list_change_events(since, until)
    data["metrics"]=compute_metrics(data)
    CACHE["snapshot"]=data; CACHE["ts"]=time.time()
    try: publish(data)
    except Exception as e: print("[broker] publish error", e)
def publish(snapshot):
    global KAFKA_PRODUCER, CLICKHOUSE
    if KAFKA_PRODUCER is None: KAFKA_PRODUCER,_ = kafka_producer()
    if CLICKHOUSE is None:
        CLICKHOUSE,_ = clickhouse_client()
        if CLICKHOUSE: ch_ensure_tables(CLICKHOUSE)
    t_snap=env('KAFKA_TOPIC_PD_SNAPSHOT'); t_inc=env('KAFKA_TOPIC_PD_INCIDENTS'); t_alt=env('KAFKA_TOPIC_PD_ALERTS'); t_chg=env('KAFKA_TOPIC_PD_CHANGES')
    if snapshot and t_snap and KAFKA_PRODUCER: kafka_send(KAFKA_PRODUCER, t_snap, key='pagerduty-snapshot', value={'ts': time.time(), 'data': snapshot})
    inc=snapshot.get('incidents',[]); alerts_map=snapshot.get('alerts_by_incident',{}); changes=snapshot.get('change_events',[])
    if KAFKA_PRODUCER and t_inc:
        for i in inc: kafka_send(KAFKA_PRODUCER, t_inc, key=i.get('id',''), value=i)
    if KAFKA_PRODUCER and t_alt:
        for iid, al in alerts_map.items():
            for a in al: kafka_send(KAFKA_PRODUCER, t_alt, key=a.get('id',''), value={'incident_id':iid, **a})
    if KAFKA_PRODUCER and t_chg:
        for c in changes: kafka_send(KAFKA_PRODUCER, t_chg, key=c.get('id',''), value=c)
    if CLICKHOUSE:
        ch_insert_incidents(CLICKHOUSE, inc); ch_insert_alerts(CLICKHOUSE, alerts_map); ch_insert_changes(CLICKHOUSE, changes)
@app.route("/snapshot")
def snapshot():
    if time.time()-CACHE.get("ts",0)>60:
        try: refresh()
        except Exception as e: return jsonify({"ok":False,"error":str(e)}), 500
    return jsonify({"ok":True, "data":CACHE["snapshot"]})
@app.route("/metrics")
def metrics():
    if not CACHE.get("snapshot"): refresh()
    return jsonify({"ok":True, "metrics":CACHE["snapshot"].get("metrics",{})})
@app.route("/export")
def export():
    if not CACHE.get("snapshot"): refresh()
    os.makedirs("data/export", exist_ok=True)
    with open("data/export/pagerduty_snapshot.json","w") as f: json.dump(CACHE["snapshot"], f, indent=2)
    return jsonify({"ok":True, "path":"data/export/pagerduty_snapshot.json"})
@app.route("/publish")
def publish_now():
    if not CACHE.get("snapshot"): refresh()
    try: publish(CACHE["snapshot"]); return jsonify({"ok":True, "published":True})
    except Exception as e: return jsonify({"ok":False,"error":str(e)}), 500
if __name__=="__main__":
    print("Starting PD ingester on :8000"); refresh(); app.run(host="0.0.0.0", port=8000)
