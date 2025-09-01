import os, json, time, random, string, datetime as dt, requests
PD_API="https://api.pagerduty.com"
EVENTS_ALERT_URL="https://events.pagerduty.com/v2/enqueue"
EVENTS_CHANGE_URL="https://events.pagerduty.com/v2/change/enqueue"
def env(name, default=None):
    v=os.getenv(name)
    return v if (v is not None and v!="") else default
def headers():
    h={"Accept":"application/vnd.pagerduty+json;version=2",
       "Authorization":"Token token="+env("PD_API_TOKEN",""),
       "Content-Type":"application/json"}
    if env("PD_FROM_EMAIL"): h["From"]=env("PD_FROM_EMAIL")
    return h
def pd_get(path, params=None):
    r=requests.get(PD_API+path, headers=headers(), params=params or {})
    if r.status_code>=400: raise RuntimeError(f"GET {path} -> {r.status_code} {r.text}")
    return r.json()
def pd_post(path, body):
    r=requests.post(PD_API+path, headers=headers(), json=body)
    if r.status_code>=400: raise RuntimeError(f"POST {path} -> {r.status_code} {r.text}")
    return r.json()
def events_post(url, body):
    r=requests.post(url, headers={"Content-Type":"application/json"}, json=body)
    if r.status_code>=400: raise RuntimeError(f"POST {url} -> {r.status_code} {r.text}")
    return r.json()
def paginate(path, key, params=None, limit=100, max_pages=100):
    params=params.copy() if params else {}
    params["limit"]=limit; offset=0
    while True:
        params["offset"]=offset
        data=pd_get(path, params=params)
        for item in data.get(key, []): yield item
        if not data.get("more"): break
        offset += limit
        if offset>limit*max_pages: break
