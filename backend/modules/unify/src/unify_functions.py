import requests, os
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from datetime import timedelta
from src.globals import TIMEDELTA
session = requests.Session()
session.verify = False

# --- UniFi API Konfiguration ---
UNIFY_BASE_URL = os.getenv("UNIFY_BASE_URL", "https://192.168.200.5:8443")
USERNAME = os.getenv("UNIFY_USERNAME", "api-user2")
PASSWORD = os.getenv("UNIFY_PASSWORD", "^Yvr*SYs,6YGr+;")
SITE = os.getenv("UNIFY_SITE", "mdg1")


def login():
    resp = session.post(f"{UNIFY_BASE_URL}/api/login", json={"username": USERNAME, "password": PASSWORD})
    #print(f"StatusCode Unify: {resp.status_code}")
    return resp.status_code == 200

def fetch_client_locations():
    if not login():
        print("Login fehlgeschlagen")
        return {}

    clients_url = f"{UNIFY_BASE_URL}/api/s/{SITE}/stat/sta"
    aps_url = f"{UNIFY_BASE_URL}/api/s/{SITE}/stat/device"

    clients = session.get(clients_url).json()["data"]
    #print(clients)
    aps = session.get(aps_url).json()["data"]
    ap_lookup = {ap["mac"]: ap.get("name", ap["mac"]) for ap in aps}

    result = {}
    for client in clients:
        mac = client["mac"]
        ap_mac = client.get("ap_mac")
        ap_name = ap_lookup.get(ap_mac, "Unbekannter AP")
        result[mac] = (ap_mac, ap_name)
    return result

def fetch_client(mac=None, ip=None, hostname=None):
    if not login():
        print("Login fehlgeschlagen")
        return {}

    clients_url = f"{UNIFY_BASE_URL}/api/s/{SITE}/stat/sta"
   
    clients = session.get(clients_url).json()["data"]

    result = {}
    for client in clients:
        if mac:
            if client.get("mac", None) == mac:
                result = {'ip' : client.get("last_ip", ip), 'mac' : client["mac"], 'name': client.get("hostname", hostname)}
                break
        if ip:
            if client.get("last_ip", None) == ip:
                result = {'ip' : client.get("last_ip", ip), 'mac' : client["mac"], 'name': client.get("hostname", hostname)}
                break
        if hostname:
            if client.get("hostname", None) == hostname:
                result = {'ip' : client.get("last_ip", ip), 'mac' : client["mac"], 'name': client.get("hostname", hostname)}
                break                    
    return result

def group_locations_lueckenlos(locations):
    delta = timedelta(hours=TIMEDELTA)
    grouped = []
    if not locations:
        return grouped

    current_ap = locations[0].ap_name
    start_time = end_time = locations[0].timestamp + delta

    for loc in locations[1:]:
        if loc.ap_name == current_ap:
            start_time = loc.timestamp + delta
        else:
            # neuer AP → Block abschließen
            grouped.append({
                "ap_name": current_ap,
                "start": start_time,
                "end": end_time
            })
            # neuen Block starten
            current_ap = loc.ap_name
            start_time = end_time = loc.timestamp + delta

    # letzten Block hinzufügen
    grouped.append({
        "ap_name": current_ap,
        "start": start_time,
        "end": end_time
    })

    return grouped

