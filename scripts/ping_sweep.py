import ipaddress
import asyncio
from appicm.models import *
import requests
import urllib3
urllib3.disable_warnings()
from asgiref.sync import sync_to_async


async def ping(host, sn):                               # add the "async" keyword to make a function asynchronous
    host = str(host)                                    # turn ip address object to string
    proc = await asyncio.create_subprocess_shell(       # asyncio can smoothly call subprocess for you
            f'ping {host} -c 1',                   # ping command
            stderr=asyncio.subprocess.DEVNULL,          # silence ping errors
            stdout=asyncio.subprocess.DEVNULL           # silence ping output
            )
    stdout,stderr = await proc.communicate()            # get info from ping process
    if proc.returncode == 0:                            # if process code was 0
        print(f'{host} is alive!')                      # say it's alive!
        # res = await Address.objects.acreate(tenant=sn.tenant, subnet=sn, address=host)
        # async_function = sync_to_async(Address.objects.create(tenant=sn.tenant, subnet=sn, address=host), thread_sensitive=True)
        await create_address(sn, host)


@sync_to_async
def create_address(sn, host):
    Address.objects.update_or_create(tenant=sn.tenant, subnet=sn, address=host, defaults={"status": 2})


def run():
    subnets = Subnet.objects.filter(autoscan=True)
    loop = asyncio.get_event_loop()  # create an async loop
    for subnet in subnets:
        tasks = []  # list to hold ping tasks
        mynet = ipaddress.ip_network(subnet.subnet)  # ip address module
        for host in mynet.hosts():  # loop through subnet hosts
            task = ping(host, subnet)  # create async task from function we defined above
            tasks.append(task)  # add task to list of tasks
        tasks = asyncio.gather(*tasks)  # some magic to assemble the tasks
        loop.run_until_complete(tasks)  # run all tasks (basically) at once

#
# import time
# # import netbox
# import requests
# import ipcalc
# import networkscan
# #import nest_asyncio
#
# API_TOKEN = "62923899c496584405bbc96d4fa4f758195788d2"
# HEADERS = {'Authorization': f'Token {API_TOKEN}', 'Content-Type' : 'application/json' , 'Accept' : 'application/json'}
# NB_URL = "https://netbox.undocumentedsanity.com"
# auth_token=API_TOKEN
# netbox = NetBoxClient(base_url="netbox.undocumentedsanity.com", token=API_TOKEN)
#
# if __name__ == '__main__':
#     # Define the network to scan
#     my_network = "10.101.10.0/24"
#     # Create the object
#     my_scan = networkscan.Networkscan(my_network)
#     # Run the scan of hosts using pings
#     my_scan.run()
#     # nest_asyncio.apply()
#     # Here we define exists ip address in our network and write it to list
#     found_ip_in_network = []
#     for address1 in my_scan.list_of_hosts_found:
#         found_ip_in_network.append(str(address1))
#         # Get all ip from prefix
#         for ipaddress in ipcalc.Network(my_network):
#             # Doing get request to netbox
#             request_url = f"{NB_URL}/api/ipam/ip-addresses/?q={ipaddress}/"
#             ipaddress1 = requests.get(request_url, headers = HEADERS)
#             netboxip = ipaddress1.json()
#             print(ipaddress)
#             print(netboxip)
#             print(netboxip['count'])
#             # If not in netbox
#             if netboxip['count'] == 0:
#                 # Check if in network exists and not exist in netbox
#                 if ipaddress in found_ip_in_network:
#                     # Adding in IP netbox
#                     netbox.ipam.create_ip_address(str(ipaddress))
#                 else:
#                     pass
#             else:
#                 #If not exists in netbox and network
#                 if ipaddress in found_ip_in_network:
#                     netbox.ipam.update_ip(str(ipaddress),status="active")
#                 else:
#                     # If not exists in network but exists in netbox then delete from netbox
#                     #netbox.ipam.delete_ip_address(str(ipaddress))
#                     netbox.ipam.update_ip(str(ipaddress),status="deprecated")

# req = requests.get(IP_ADDR_URL + "?address=" + host, headers=HEADERS, verify=False)
# if req.ok:
#     rjson = req.json()
#     if len(rjson.get("results", [])) == 1:
#         addr_id = rjson.get("results", [{}])[0].get("id")
#         if addr_id:
#             data = {
#                 "status": "reserved"
#             }
#
#             req2 = requests.patch(IP_ADDR_URL + str(addr_id) + "/", headers=HEADERS, json=data, verify=False)
#             print(req2.status_code)
# else:
#     print("error", req.status_code)