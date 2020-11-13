import json
import time
from random import randint
from http_automate import ObjHTTP


class MerakiHTTP(ObjHTTP):
    def __init__(self):
        super(MerakiHTTP, self).__init__()
        self.baseheaders = self.headers
        self.orgurl = None
        self.xhrtoken = None
        self.baseurl = None
        self.netintid = None
        self.xpid = None
        self.pageloadid = None
        self.lasturl = None

    def meraki_www_get_settings(self, strcontent, settingval, settingfull=None, settingfullend=None):
        '''
        In the dashboard, there are a large number of settings hidden in the code. This function will parse and retrieve
        the value of a specific setting

        :param strcontent: String. Raw HTML of the page.
        :param settingval: String. If the setting is in the "Mkiconf.setting = " format, pass "setting" here. Otherwise...
        :param settingfull: String. If the setting is named or punctuated differently, pass the exact string here.
        :return: String. The value of the requested setting
        '''

        # Determine whether this is a standard setting or not, and set tokenident to the exact name of the setting
        if settingfull != "" and settingfull is not None:
            tokenident = settingfull
        else:
            tokenident = 'Mkiconf.' + settingval + ' = "'
        tokenstart = strcontent.find(tokenident)
        if tokenstart < 0:
            return ""
        tokenval = strcontent[tokenstart + len(tokenident):]

        if settingfull == "" or settingfull is None:
            tokenend = tokenval.find('";')
        else:
            if settingfullend == "" or settingfullend is None:
                tokenend = tokenval.find(';')
            else:
                tokenend = tokenval.find(settingfullend)
        tokenval = tokenval[:tokenend]
        return tokenval

    def gettoken(self, logincontent):
        """
        When logging into the dashboard, there is an "authenticity_token" hidden field. If this field is not included in
        the login POST, login will fail. Scrape this from the HTML and return so it can be POST'ed to login.

        :param logincontent: String. Raw HTML of base login page.
        :return: String. Authenticity Token.
        """

        tokenident = '<input name="authenticity_token" type="hidden" value="'
        tokenstart = logincontent.find(tokenident)
        tokenval = logincontent[tokenstart + len(tokenident):]

        tokenend = tokenval.find('" />')
        tokenval = tokenval[:tokenend]
        return tokenval

    def get_meraki_org_url(self, pagecontent, orgname):
        """
        This function will take the Dictionary of organizations coming from meraki_www_get_org_list, and search that for
        the name of the organization from get_meraki_org_name. When it has found a match, it will return the full URL
        for that organization.

        :param pagecontent: String. Raw HTML of the organization page.
        :return: String. URL of the organization to load.
        """

        orgurl = ""
        olist = json.loads(self.meraki_www_get_org_list(pagecontent))

        for onum in olist:
            if olist[onum]["name"] == orgname:
                orgurl = "https://dashboard.meraki.com/login/org_choose?eid=" + olist[onum]["id"]
                return orgurl

        return orgurl

    def meraki_www_get_org_list(self, strcontent):
        """
        When logging in, there is a page that lists the organizations that you have access to. This function will parse
        this page and return a dictionary of the organizations.

        :param strcontent: String. Raw HTML content of the org selection page
        :return: Dictionary. All of the organizations including id and name.
        """

        orgident = '<a href="/login/org_choose?eid='
        orgarr = strcontent.split(orgident)
        retarr = {}

        for x in range(1, len(orgarr)):
            orgend = orgarr[x].find('</a>')
            orgdata = orgarr[x][:orgend]
            orgdarr = orgdata.split('">')
            xst = str(x)
            retarr[xst] = {"id": orgdarr[0].split('"')[0], "name": orgdarr[1]}
        return json.dumps(retarr)

    def meraki_www_login_and_choose_org(self, http_un, http_pw, org_name):
        token = self.gettoken(self.doget("https://dashboard.meraki.com/login/login"))
        logindata = {'utf8': '&#x2713;', 'email': http_un, 'password': http_pw,
                     'authenticity_token': token, 'commit': 'Log+in', 'goto': 'manage'}
        rcontent = self.dopost("https://dashboard.meraki.com/login/login", logindata)
        self.orgurl = self.lasturl
        if rcontent.lower().find("enter verification code") >= 0:
            # print("Error. Unable to automate Org that has SMS enabled.")
            token = self.gettoken(rcontent)
            smscode = input("Enter SMS Verification code: ")
            smsdata = {'utf8': '&#x2713;', 'code': smscode, 'remember_user': '', 'remember': '1',
                       'authenticity_token': token, 'goto': 'manage', 'go': "/"}
            rcontent = self.dopost("https://account.meraki.com/login/do_sms_auth", smsdata)

        if rcontent.lower().find("accounts for " + http_un.lower()):
            ourl = self.get_meraki_org_url(rcontent, org_name)
            if ourl:
                self.orgurl = ourl
            return True
        else:
            print("No Account Selection found. Unable to proceed.")
            return False

    def meraki_www_check_errors(self, content):
        errors = ["This account has access to multiple Meraki Dashboard organizations. For security purposes, please set the password which should be used to access all of those organizations."]
        for e in errors:
            # print("checking for error", e, content)
            if e in content:
                return e

        return False

    def meraki_www_get(self, url):
        self.headers["Referer"] = self.lasturl
        if "X-CSRF-Token" in self.headers: del self.headers["X-CSRF-Token"]
        if "X-Requested-With" in self.headers: del self.headers["X-Requested-With"]
        rcontent = self.doget(url)
        self.lasturl = url
        err = self.meraki_www_check_errors(rcontent)
        # print(url, rcontent)
        if err:
            print(err)
            return False
        elif url == "https://dashboard.meraki.com/login/login":
            print("* There was an error getting the login URL.")
            return False
        else:
            self.xhrtoken = self.meraki_www_get_settings(rcontent, "authenticity_token")
            self.baseurl = self.meraki_www_get_settings(rcontent, "base_url")
            self.netintid = self.meraki_www_get_settings(rcontent, "", "flux.actions.networks.reset(")[:-1]
            self.xpid = self.meraki_www_get_settings(rcontent, "", ".loader_config={xpid:")[:-1].replace('"', "").strip()
            self.pageloadid = self.meraki_www_get_settings(rcontent, "", "Mkiconf.pageload_request_id ||").replace('"', "").strip()
            return rcontent

    def meraki_www_get_xhr(self, url):
        self.headers = self.baseheaders
        self.headers["Referer"] = self.lasturl
        self.headers["X-CSRF-Token"] = self.xhrtoken
        self.headers["X-Requested-With"] = "XMLHttpRequest"
        rcontent = self.doget(url)
        return rcontent

    def meraki_www_get_org_json(self):
        tms = str(int(time.time() * 1000))
        ts = str(int(time.time())) + ".000"
        rnd = ''.join(["{}".format(randint(0, 9)) for num in range(0, 20)])
        try:
            rcontent = self.meraki_www_get_xhr(self.geturldomain() + self.baseurl + "manage/organization/org_json?jsonp=jQuery" + rnd + "_" + tms + "&t0=" + ts + "&t1=" + ts + ".000" + "&primary_load=true&_=" + tms)
        except Exception as e:
            print("* An exception occurred trying to load your organization in Dashboard.\nDomain:", self.geturldomain(), "\nBase URL:", self.baseurl)
            rcontent = None

        return rcontent

    def meraki_www_get_admin_org_json(self):
        try:
            rcontent = json.loads(self.meraki_www_get_xhr(self.geturldomain() + self.baseurl + "manage/organization/administered_orgs"))
        except Exception as e:
            print("* An exception occurred trying to load your organization in Dashboard.\nDomain:", self.geturldomain(), "\nBase URL:", self.baseurl)
            rcontent = None

        return rcontent

    def meraki_www_find_in_org_json(self, network_id=None, org_id=None):
        # try:
        if network_id:
            r = self.meraki_www_get_org_json()

            if r:
                newr = r[r.find("(")+1:-1]
                rj = json.loads(newr)
                rk = None
                if network_id[0:1] == "N":
                    rk = "networks"
                elif network_id[0:1] == "L":
                    rk = "locales"

                if rk:
                    if network_id[2:] in rj[rk]:
                        jb = rj[rk][network_id[2:]]
                        return {"data": jb, "baseurl": self.geturldomain() + "/" + jb["tag"] + "/n/" + jb["eid"]}
                return False
        elif org_id:
            rj = self.meraki_www_get_admin_org_json()
            orj = rj.get(org_id, {})
            return {"data": orj, "baseurl": self.geturldomain() + "/o/" + orj["eid"]}
        else:
            return False
        #     print("meraki_www_find_net_in_org_json: Exception Occurred")
        #     return False

    def meraki_www_post(self, url, content):
        self.headers = self.baseheaders
        self.headers["Accept"] = "*/*"
        self.headers["Accept-Encoding"] = "gzip, deflate, br"
        self.headers["Cache-Control"] = "no-cache"
        self.headers["Connection"] = "keep-alive"
        # self.headers["Content-Length"] = len(content)
        self.headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        self.headers["Host"] = self.gethost()
        self.headers["Pragma"] = "no-cache"
        self.headers["Referer"] = self.lasturl
        self.headers["X-CSRF-Token"] = self.xhrtoken
        self.headers["X-NewRelic-ID"] = self.xpid
        self.headers["X-Pageload-Request-Id"] = self.pageloadid
        self.headers["X-Requested-With"] = "XMLHttpRequest"
        return self.dopost(url, content)
