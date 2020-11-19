import subprocess
import os
import signal


def start_tunnel(inportnum, portnum, tunnel_client):
    cmd = "pproxy -l tunnel://:" + inportnum + " -r tunnel+in://:" + portnum + " -v"
    # print(cmd)
    sp = subprocess.Popen(cmd.split(" "), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    # s = subprocess.check_output([cmd], stderr=subprocess.STDOUT)
    # print(p)
    out, err = sp.communicate()
    tunnel_client.pid = sp.pid
    tunnel_client.log = cmd + "\n" + str(out) + "\n" + str(err) + "\n" + str(sp.returncode)
    tunnel_client.save()
    return sp


def stop_tunnel(pid):
    try:
        os.kill(pid, signal.SIGTERM)  # or signal.SIGKILL
    except Exception:
        print("Exception attempting to end process", pid)
