#!/usr/bin/env python3
import os, sys, json, time, random, argparse, datetime as dt
from common import env, events_post, EVENTS_ALERT_URL, EVENTS_CHANGE_URL
SEVERITIES=["critical","error","warning","info"]
def load_routing_keys():
    rk_pay = env("PD_ROUTING_KEY_PAYMENTS"); rk_ord = env("PD_ROUTING_KEY_ORDERS")
    try:
        with open("data/bootstrap_output.json") as f:
            boot=json.load(f)
            rk_pay = rk_pay or boot["routing_keys"]["payments"]
            rk_ord = rk_ord or boot["routing_keys"]["orders"]
    except Exception: pass
    if not rk_pay or not rk_ord:
        print("ERROR: routing keys not found. Run bootstrap or set env PD_ROUTING_KEY_*", file=sys.stderr); sys.exit(2)
    return {"Payments API":rk_pay, "Orders API":rk_ord}
def trigger_alert(routing_key, summary, source, severity):
    dedup=f"demo-{int(time.time())}-{random.randint(1000,9999)}"
    body={"routing_key":routing_key,"event_action":"trigger","dedup_key":dedup,
          "client":"DevOpsCanvas Demo",
          "payload":{"summary":summary,"source":source,"severity":severity,"class":"demo.synthetic",
                     "timestamp":dt.datetime.utcnow().isoformat()+"Z"}}
    return events_post(EVENTS_ALERT_URL, body), dedup
def event_action(routing_key, dedup_key, action):
    body={"routing_key":routing_key,"event_action":action,"dedup_key":dedup_key}
    return events_post(EVENTS_ALERT_URL, body)
def change_event(routing_key, summary, source):
    body={"routing_key":routing_key,"payload":{"summary":summary,"timestamp":dt.datetime.utcnow().isoformat()+"Z","source":source}}
    return events_post(EVENTS_CHANGE_URL, body)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--alerts",action="store_true"); ap.add_argument("--changes",action="store_true"); args=ap.parse_args()
    if not (args.alerts or args.changes): args.alerts=True; args.changes=True
    rks=load_routing_keys(); alert_n=int(env("SEED_ALERT_COUNT","5")); change_n=int(env("SEED_CHANGE_COUNT","3"))
    if args.alerts:
        for svc,rk in rks.items():
            for i in range(alert_n):
                _, dedup = trigger_alert(rk, f"{svc} latency spike #{i+1}", f"{svc.lower().replace(' ','-')}.prod", random.choice(SEVERITIES))
                if random.random()<0.8: event_action(rk, dedup, "acknowledge")
                if random.random()<0.6: event_action(rk, dedup, "resolve")
    if args.changes:
        for svc,rk in rks.items():
            for i in range(change_n): change_event(rk, f"{svc} deploy {i+1}", f"gha-{svc.lower().split()[0]}")
    print(json.dumps({"ok":True}, indent=2))
if __name__=="__main__": main()
