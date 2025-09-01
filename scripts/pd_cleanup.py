#!/usr/bin/env python3
import os, requests
from common import pd_get
def delete(path, id_):
    r=requests.delete("https://api.pagerduty.com"+path+"/"+id_,
        headers={"Accept":"application/vnd.pagerduty+json;version=2",
                 "Authorization":"Token token="+os.getenv("PD_API_TOKEN",""),
                 "From": os.getenv("PD_FROM_EMAIL","")})
    print("DELETE", path, id_, r.status_code)
def main():
    for s in pd_get("/services").get("services",[]):
        if "demo=true" in (s.get("description") or ""): delete("/services", s["id"])
    for ep in pd_get("/escalation_policies").get("escalation_policies",[]):
        if "demo=true" in (ep.get("description") or ""): delete("/escalation_policies", ep["id"])
    for sch in pd_get("/schedules").get("schedules",[]):
        if "demo=true" in (sch.get("description") or ""): delete("/schedules", sch["id"])
    for t in pd_get("/teams").get("teams",[]):
        if "demo=true" in (t.get("description") or ""): delete("/teams", t["id"])
if __name__=="__main__": main()
