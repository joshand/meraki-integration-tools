from flask import Flask, request, redirect, session, url_for, render_template, jsonify
import sys
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import json
import requests


app = Flask(__name__)

# Enable the job scheduler to run for expired lab sessions
cron = BackgroundScheduler()

# Explicitly kick off the background thread
cron.start()

# Shutdown your cron thread if the web process is stopped
atexit.register(lambda: cron.shutdown(wait=False))


app_version = "0.0.1"
sver = sys.version_info
app_name = "Python" + str(sver[0]) + "." + str(sver[1]) + ":tunnel_client.py"
myuuid = "74886f7a-8247-4cc5-9e46-9cebf3fec1e4"
gateway = "demo.sigraki.com"
controller = "http://" + gateway
internal_port = "8000"
HTTP_METHODS = ['GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'CONNECT', 'OPTIONS', 'TRACE', 'PATCH']


def job_function(portnum):
    cmd = "pproxy -l tunnel+in://" + gateway + ":" + str(portnum) + " -r tunnel://127.0.0.1:" + internal_port
    print(cmd)
    p = subprocess.Popen(cmd.split(" "))
    return p


def start_tunnel(portnum):
    job = cron.add_job(job_function, args=[str(portnum)])
    return job


# handled incoming requests over tunnel
@app.route('/', methods=HTTP_METHODS)
def default_route():
    injson = request.get_json(force=True)
    # url = injson.get("url", "")
    # headers = injson.get("headers", {})
    # method = injson.get("method", "")
    # auth = injson.get("auth", "")
    # auth_un = injson.get("auth_username", "")
    # auth_pw = injson.get("auth_password", "")
    # https_verify = injson.get("https_verify", "")
    # body = injson.get("body", "")
    url = request.headers.get("X-Local-URL")
    headers = json.loads(request.headers.get("X-Local-Headers", "{}"))
    insecure = request.headers.get("X-Local-Allow-Insecure", "false").lower()
    if insecure == "true":
        https_verify = False
    else:
        https_verify = True
    auth = request.headers.get("X-Local-Auth-Basic", None)
    method = request.method
    if method.upper() == "GET" or method.upper() == "DELETE":
        body = None
    else:
        body = request.get_data()

    if not url:
        return "You must specifiy at a minimum the X-Local-URL with the local URL to call."

    if auth:
        auth_un, auth_pw = auth.split(":")
        print("doing request with basic auth")
        try:
            if body:
                r = requests.request(method, url, headers=headers, auth=(auth_un, auth_pw), verify=https_verify,
                                     timeout=5, body=body)
            else:
                r = requests.request(method, url, headers=headers, auth=(auth_un, auth_pw), verify=https_verify, timeout=5)
            resp = str(r.content.decode("UTF-8"))
        except:
            resp = "error"
    else:
        print("doing request with no auth")
        try:
            if body:
                r = requests.request(method, url, headers=headers, verify=https_verify, timeout=5, body=body)
            else:
                r = requests.request(method, url, headers=headers, verify=https_verify, timeout=5)
            resp = str(r.content.decode("UTF-8"))
        except:
            resp = "error"

    return resp


def run():
    reg_url = controller + "/api/v0/tunnels/" + myuuid + "/register"
    data = {"app": app_name, "ver": app_version}
    r = requests.post(reg_url, json=data)
    # print(r.content.decode("utf-8"))
    rj = r.json()
    if "portnum" in rj:
        start_tunnel(rj["portnum"])
        app.run(host="0.0.0.0", port=8000, debug=False)
    else:
        print("Error; no port returned", str(rj))
