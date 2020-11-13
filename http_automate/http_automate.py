import json
import requests
from urllib.parse import urlparse


class ObjHTTP:
    def __init__(self):
        self.httpsession = requests.Session()
        self.headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:51.0) Gecko/20100101 Firefox/51.0'}
        self.cookies = None
        self.url = None
        self.lasturl = None

    def doget(self, url):
        # Get initial login page
        self.url = url
        r = self.httpsession.get(self.url, headers=self.headers)
        self.lasturl = r.url
        self.cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(self.httpsession.cookies))
        rcontent = r.content.decode("UTF-8")
        return rcontent

    def dopost(self, url, data):
        # Get initial login page
        self.url = url
        r = self.httpsession.post(self.url, headers=self.headers, data=data, cookies=self.cookies)
        self.lasturl = r.url
        self.cookies = requests.utils.cookiejar_from_dict(requests.utils.dict_from_cookiejar(self.httpsession.cookies))
        rcontent = r.content.decode("UTF-8")
        return rcontent

    def geturldomain(self):
        u = urlparse(self.lasturl)
        return u.scheme + "://" + u.hostname

    def gethost(self):
        u = urlparse(self.lasturl)
        return u.hostname

    # # Check to see if the org selection page has loaded. I've heard that this doesn't always happen, but I've not yet
    # # found a user to test with that does not hit this page.
    # if rcontent.lower().find("accounts for " + meraki_http_un.lower()):
    #     orgurl = get_meraki_org_url(rcontent)
    #     print(orgurl)
    # else:
    #     print("No Account Selection found. Unable to proceed.")
    #     sys.exit()
    #
    # if orgurl:
    #     # Load redirect page
    #     r = session.get(orgurl, headers=headers, cookies=cookies)
    #     rcontent = r.content.decode("UTF-8")
    #
    #     # Parse content to get auth token and base url. auth token is required for XHR requests, and Base URL is...
    #     # possibly the last network loaded when the user last logged out?
    #     xhrtoken = meraki_www_get_settings(rcontent, "authenticity_token", "")
    #     baseurl = meraki_www_get_settings(rcontent, "base_url", "")
    #
    #     # Search the history to get the most recent FQDN so we can link directly to the appropriate shard.
    #     for resp in r.history:
    #         o = urllib.parse.urlparse(resp.url)
    #         mhost = o.netloc
    #
    #     #"https://%2%%3%manage/organization/overview#t=network"
    #
    #     # Load administered orgs XHR Data
    #     #xhrurl = "https://" + mhost + baseurl + "manage/organization/administered_orgs"
    #     xhrurl = "https://" + mhost + baseurl + "manage/organization/org_json?jsonp=jQuery18307230485578098947_" + str(int(time.time() * 1000)) + "&t0=" + str(int(time.time())) + ".000" + "&t1=" + str(int(time.time())) + ".000" + "&primary_load=true&_=" + str(int(time.time() * 1000))
    #     xhrheader = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.12; rv:51.0) Gecko/20100101 Firefox/51.0',"X-CSRF-Token": xhrtoken,"X-Requested-With": "XMLHttpRequest"}
    #     r = session.get(xhrurl, headers=xhrheader, cookies=cookies)
    #     rcontent = r.content.decode("UTF-8")
    #     rjson = json.loads(rcontent[rcontent.find("({")+1:-1])
    #     #print(rjson)
    #
    #     outjson = {}
    #     mbase = rjson["networks"]
    #     outjson = {"networks": {}, "devices": {}}
    #     # Now, we will iterate the data loaded from the XHR request to generate the mapping data that we need.
    #     for jitem in mbase:
    #         # This generates the link to the network
    #         outjson["networks"][mbase[jitem]["name"]] = {"baseurl": "https://" + mhost + "/" + mbase[jitem]["tag"] + "/n/" + mbase[jitem]["eid"] + meraki_www_get_path(mbase[jitem]["type"], "")}           #, "id": mbase[jitem]["id"]
    #
    #         # This generates the link to the device
    #         for jdev in rjson["nodes"]:
    #             if rjson["nodes"][jdev]["ng_id"] == mbase[jitem]["id"]:
    #                 outjson["devices"][rjson["nodes"][jdev]["mac"]] = {"baseurl": "https://" + mhost + "/" + mbase[jitem]["tag"] + "/n/" + mbase[jitem]["eid"] + meraki_www_get_path(mbase[jitem]["type"], rjson["nodes"][jdev]["id"]), "desc": rjson["nodes"][jdev]["name"]}              #mbase[jitem]["id"]          #rjson["nodes"][jdev]["serial"]
    #
    #     return outjson
    # else:
    #     print("Unable to get org url. Check username and password...")
    #     return {}


