#!/usr/bin/env python3
import os, json, datetime as dt
from common import env, pd_get, pd_post
def ensure_team(name="DevOpsCanvas Demo Team"):
    for t in pd_get("/teams", params={"query":name}).get("teams",[]):
        if t["name"]==name: return t
    return pd_post("/teams", {"team":{"name":name,"description":"demo=true"}})["team"]
def ensure_user(name, email, role="user"):
    for u in pd_get("/users", params={"query":email}).get("users",[]):
        if u["email"].lower()==email.lower(): return u
    return pd_post("/users", {"user":{"type":"user","name":name,"email":email,"role":role,"description":"demo=true"}})["user"]
def ensure_schedule(name, user_ids, tz):
    for s in pd_get("/schedules").get("schedules",[]): 
        if s["name"]==name: return s
    start=dt.datetime.utcnow().replace(minute=0,second=0,microsecond=0).isoformat()+"Z"
    body={"schedule":{"name":name,"time_zone":tz,"description":"demo=true",
        "schedule_layers":[{"name":"Primary","start":start,"rotation_virtual_start":start,"rotation_turn_length_seconds":86400,
            "users":[{"user":{"id":uid,"type":"user_reference"}} for uid in user_ids]}]}}
    return pd_post("/schedules", body)["schedule"]
def ensure_escalation_policy(name, schedule_id, team_id):
    for ep in pd_get("/escalation_policies", params={"query":name}).get("escalation_policies",[]):
        if ep["name"]==name: return ep
    body={"escalation_policy":{"name":name,"description":"demo=true","num_loops":2,
        "teams":[{"id":team_id,"type":"team_reference"}],
        "escalation_rules":[{"escalation_delay_in_minutes":10,"targets":[{"id":schedule_id,"type":"schedule_reference"}]}]}}
    return pd_post("/escalation_policies", body)["escalation_policy"]
def ensure_service(name, ep_id):
    for s in pd_get("/services", params={"query":name}).get("services",[]):
        if s["name"]==name: return s
    body={"service":{"name":name,"description":"demo=true","acknowledgement_timeout":600,"auto_resolve_timeout":14400,
                     "escalation_policy":{"id":ep_id,"type":"escalation_policy_reference"}}}
    return pd_post("/services", body)["service"]
def ensure_events_integration(service_id, name="API V2"):
    integ = pd_post(f"/services/{service_id}/integrations", {"integration":{"name":name,"type":"events_api_v2_inbound_integration"}})["integration"]
    key = integ.get("integration_key") or integ.get("routing_key")
    return integ, key
def main():
    tz=env("PD_TIMEZONE","America/Chicago"); dom=env("PD_DEMO_EMAIL_DOMAIN","example.com")
    team=ensure_team()
    alice=ensure_user("Alice Oncall", f"alice.oncall@{dom}")
    bob=ensure_user("Bob Backup", f"bob.backup@{dom}")
    mgr=ensure_user("Mandy Manager", f"mandy.manager@{dom}", role="admin")
    sch=ensure_schedule("Demo Primary On-Call", [alice["id"], bob["id"]], tz)
    ep=ensure_escalation_policy("Demo EP (Primary->Backup)", sch["id"], team["id"])
    svc1=ensure_service("Payments API", ep["id"]); svc2=ensure_service("Orders API", ep["id"])
    rk_pay=os.getenv("PD_ROUTING_KEY_PAYMENTS"); rk_ord=os.getenv("PD_ROUTING_KEY_ORDERS"); info={}
    if not rk_pay: integ, rk_pay = ensure_events_integration(svc1["id"], "API V2"); info["payments"]=integ
    if not rk_ord: integ, rk_ord = ensure_events_integration(svc2["id"], "API V2"); info["orders"]=integ
    out={"team":team,"users":[alice,bob,mgr],"schedule":sch,"escalation_policy":ep,"services":[svc1,svc2],
         "routing_keys":{"payments":rk_pay,"orders":rk_ord},"integrations":info}
    os.makedirs("data", exist_ok=True)
    with open("data/bootstrap_output.json","w") as f: f.write(json.dumps(out, indent=2))
    print(json.dumps({"ok":True,"routing_keys":out["routing_keys"]}, indent=2))
if __name__=="__main__": main()
