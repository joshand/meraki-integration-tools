from subprocess import Popen


def start_tunnel(inportnum, portnum):
    cmd = "pproxy -l tunnel://:" + inportnum + " -r tunnel+in://:" + portnum + " -v"
    print(cmd)
    p = Popen(cmd.split(" "))
    # s = subprocess.check_output([cmd], stderr=subprocess.STDOUT)
    print(p)
    return p
