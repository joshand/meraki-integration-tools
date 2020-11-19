from subprocess import Popen


def start_tunnel(inportnum, portnum, tunnel_client):
    cmd = "pproxy -l tunnel://:" + inportnum + " -r tunnel+in://:" + portnum + " -v"
    # print(cmd)
    p = Popen(cmd.split(" "))
    # s = subprocess.check_output([cmd], stderr=subprocess.STDOUT)
    # print(p)
    tunnel_client.pid = p.pid
    tunnel_client.log = cmd + "\n" + str(p)
    return p
