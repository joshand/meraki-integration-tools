from appicm.models import *
from scripts.tunnels import start_tunnel, stop_tunnel, health_check


def tunnel_health_check():
    tcs = TunnelClient.objects.all()
    for tc in tcs:
        print("health_check on", tc)
        state, result = health_check(tc.get_internal_port(), timeout=10)
        print(state, result)
        if not state:
            stop_tunnel(tc.pid)
            time.sleep(5)
            start_tunnel(tc)


def run():
    tunnel_health_check()
