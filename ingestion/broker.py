import os, json
def _env(name, default=None):
    v=os.getenv(name)
    return v if (v is not None and v!='') else default
def kafka_producer():
    try:
        from confluent_kafka import Producer
    except Exception as e:
        return None, f"kafka disabled: {e}"
    brokers=_env('KAFKA_BROKERS')
    if not brokers: return None, "kafka disabled: KAFKA_BROKERS empty"
    conf={'bootstrap.servers':brokers}
    if _env('KAFKA_SECURITY_PROTOCOL'): conf['security.protocol']=_env('KAFKA_SECURITY_PROTOCOL')
    if _env('KAFKA_SASL_MECHANISM'): conf['sasl.mechanisms']=_env('KAFKA_SASL_MECHANISM')
    if _env('KAFKA_SASL_USERNAME'): conf['sasl.username']=_env('KAFKA_SASL_USERNAME')
    if _env('KAFKA_SASL_PASSWORD'): conf['sasl.password']=_env('KAFKA_SASL_PASSWORD')
    if _env('KAFKA_SSL_CA_LOCATION'): conf['ssl.ca.location']=_env('KAFKA_SSL_CA_LOCATION')
    try:
        return Producer(conf), None
    except Exception as e:
        return None, f'kafka init error: {e}'
def kafka_send(producer, topic: str, key: str, value: dict):
    if not producer or not topic: return False
    try:
        payload=json.dumps(value, separators=(',',':')).encode('utf-8')
        producer.produce(topic, value=payload, key=key); producer.poll(0); return True
    except Exception as e:
        print('[kafka] send failed', e); return False
def clickhouse_client():
    try:
        import clickhouse_connect
    except Exception as e:
        return None, f'clickhouse disabled: {e}'
    url=_env('CLICKHOUSE_URL')
    if not url: return None, 'clickhouse disabled: CLICKHOUSE_URL empty'
    host=url.split('://')[-1].split(':')[0]
    port=int(url.split(':')[-1]) if ':' in url.split('://')[-1] else 8123
    user=_env('CLICKHOUSE_USERNAME','default'); pwd=_env('CLICKHOUSE_PASSWORD','')
    try:
        client = clickhouse_connect.get_client(host=host, port=port, username=user, password=pwd)
        db=_env('CLICKHOUSE_DATABASE','devopscanvas')
        client.command('CREATE DATABASE IF NOT EXISTS '+db); client.command('USE '+db); return client, None
    except Exception as e:
        return None, f'clickhouse init error: {e}'
def ch_ensure_tables(client):
    if not client: return
    db=_env('CLICKHOUSE_DATABASE','devopscanvas')
    tbl_inc=_env('CLICKHOUSE_TABLE_PD_INCIDENTS','pd_incidents')
    tbl_alt=_env('CLICKHOUSE_TABLE_PD_ALERTS','pd_alerts')
    tbl_chg=_env('CLICKHOUSE_TABLE_PD_CHANGES','pd_changes')
    q1='CREATE TABLE IF NOT EXISTS '+db+'.'+tbl_inc+' (id String, status String, urgency String, created_at DateTime, acknowledged_at Nullable(DateTime), resolved_at Nullable(DateTime), service_id String, service_name String) ENGINE = MergeTree ORDER BY (created_at, id)'
    q2='CREATE TABLE IF NOT EXISTS '+db+'.'+tbl_alt+' (incident_id String, alert_id String, created_at DateTime) ENGINE = MergeTree ORDER BY (created_at, alert_id)'
    q3='CREATE TABLE IF NOT EXISTS '+db+'.'+tbl_chg+' (id String, summary String, created_at DateTime) ENGINE = MergeTree ORDER BY (created_at, id)'
    client.command(q1); client.command(q2); client.command(q3)
def ch_insert_incidents(client, incidents):
    if not client: return
    db=_env('CLICKHOUSE_DATABASE','devopscanvas'); tbl=_env('CLICKHOUSE_TABLE_PD_INCIDENTS','pd_incidents')
    rows=[]; 
    for i in incidents:
        svc=(i.get('service') or {})
        rows.append([i.get('id',''),i.get('status',''),i.get('urgency',''),(i.get('created_at','') or '').replace('Z','').replace('T',' '),(i.get('acknowledged_at') or '').replace('Z','').replace('T',' ') or None,(i.get('resolved_at') or '').replace('Z','').replace('T',' ') or None,svc.get('id',''),svc.get('summary') or svc.get('name','')])
    if rows:
        client.insert(db+'.'+tbl, rows, column_names=['id','status','urgency','created_at','acknowledged_at','resolved_at','service_id','service_name'])
def ch_insert_alerts(client, alerts_map):
    if not client: return
    db=_env('CLICKHOUSE_DATABASE','devopscanvas'); tbl=_env('CLICKHOUSE_TABLE_PD_ALERTS','pd_alerts')
    rows=[]
    for inc_id, alerts in alerts_map.items():
        for a in alerts:
            rows.append([inc_id, a.get('id',''), (a.get('created_at') or '').replace('Z','').replace('T',' ')])
    if rows:
        client.insert(db+'.'+tbl, rows, column_names=['incident_id','alert_id','created_at'])
def ch_insert_changes(client, changes):
    if not client: return
    db=_env('CLICKHOUSE_DATABASE','devopscanvas'); tbl=_env('CLICKHOUSE_TABLE_PD_CHANGES','pd_changes')
    rows=[]
    for c in changes:
        rows.append([c.get('id',''), c.get('summary',''), (c.get('created_at') or '').replace('Z','').replace('T',' ')])
    if rows:
        client.insert(db+'.'+tbl, rows, column_names=['id','summary','created_at'])
