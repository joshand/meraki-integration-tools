import subprocess
import os
import signal
import requests


def start_tunnel(tunnel_client):
    sp = None
    while True:
        if not tunnel_client.tunnelport:
            tunnel_client.tunnelport = tunnel_client.find_open_port()
            tunnel_client.save()
            if not tunnel_client.tunnelport:
                print("unable to find a tunnel port")
                break

        inportnum = str(tunnel_client.get_internal_port())
        outportnum = str(tunnel_client.tunnelport.portnumber)

        cmd = "pproxy -l tunnel://:" + inportnum + " -r tunnel+in://:" + outportnum + " -v"
        # print(cmd)
        sp = subprocess.Popen(cmd.split(" "))
        # s = subprocess.check_output([cmd], stderr=subprocess.STDOUT)
        # print(p)
        tunnel_client.pid = sp.pid
        tunnel_client.log = ""
        tunnel_client.save()

        out_txt = str(sp.stdout)
        err_txt = str(sp.stderr)

        # out, err = sp.communicate()
        # out_txt = str(out.decode("utf-8"))
        # err_txt = str(err.decode("utf-8"))
        if "address already in use" in out_txt or "address already in use" in err_txt:
            tunnel_client.log = cmd + "\nPort in use... relaunching..."
            tunnel_client.tunnelport = tunnel_client.find_open_port()
            tunnel_client.save()
        else:
            tunnel_client.log = cmd + "\n" + out_txt + "\n" + err_txt + "\n" + str(sp.returncode)
            tunnel_client.save()
            break

    return sp


def stop_tunnel(pid):
    try:
        os.kill(pid, signal.SIGTERM)  # or signal.SIGKILL
    except Exception:
        print("Exception attempting to end process", pid)


def health_check(port_num, timeout=30):
    req = ""
    try:
        url = "http://127.0.0.1:" + str(port_num) + "/health"
        req = requests.get(url, timeout=timeout)
        rjson = req.json()
        if rjson.get("status") != "ok":
            return False, req
        return True, req
    except Exception:
        return False, req
