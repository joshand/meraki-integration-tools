# meraki-integration-tools<a name="top"/>

## Getting Started
1) [Set up your environment](#setup)
    - [Cisco Meraki Dashboard](#configure-dashboard)
    - [Cisco Umbrella](#cisco-umbrella)
2) [Deploy the Application](#deploy)
    - [Clone the Github repo and run locally](#deploy-local)
3) [Configure Adaptive Policy Sync](#configure)
    - [Using the UI](#configure-ui)
    - [Using the API](#configure-api)
4) [Backup/Restore](#backup-restore)
    - [Using the UI](#ui-backup-restore)
    - [Using the API](#api-backup-restore)
5) [Troubleshooting](#troubleshooting)

### Set up your environment<a name="setup"/> ([^ Top](#top))

#### Meraki Dashboard<a name="configure-dashboard"/> ([^ Top](#top))
1) Enable API access in your Meraki dashboard organization and obtain an API key ([instructions](https://documentation.meraki.com/zGeneral_Administration/Other_Topics/The_Cisco_Meraki_Dashboard_API))
2) Keep your API key safe and secure, as it is similar to a password for your dashboard. You will supply this API key to Adaptive Policy Sync later.

#### Cisco Umbrella<a name="cisco-umbrella"/> ([^ Top](#top))
1) Create Management API Key
2) Create Network Devices API Key

### Deploy the Application<a name="deploy"/> ([^ Top](#top))

#### Clone the Github repo and run locally<a name="deploy-local"/> ([^ Top](#top))
```
git clone https://github.com/joshand/meraki-integration-tools.git
cd meraki-integration-tools/
virtualenv venv --python=python3
source venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
Username (leave blank to use 'username'): admin
Email address: email@domain.com
Password: 
Password (again): 
Superuser created successfully.

python manage.py drf_create_token admin
Generated token 1234567890abcdefghijklmnopqrstuvwxyz1234 for user admin

python manage.py loaddata default.json

python manage.py runserver 8000
```

## Configure Meraki Integration Tools<a name="configure"/>

### Using the UI<a name="configure-ui"/> ([^ Top](#top))
1. Access your Meraki Integration Tools Instance using the port that you've configured (http://127.0.0.1:8000 if you used the examples above)

2. Enter the Username and Password that you configured above (using 'createsuperuser'). Then click "Log In".
    ![mit-login](images/000-login.png)

3. In a new installation, you will have only a single tenant, which will be named with the e-mail address you entered. Click on that tenant to launch it.
    ![mit-tenant](images/001-select_tenant.png)

4. In the left navigation pane, select "Packages". Then click the "Upload Package" icon.
    ![mit-packages](images/010-packages.png)

5. Select the "Global" Tenant (this will give all tenants access to the package), then click the "Browse..." button.
    ![mit-package-tenant](images/011-package-tenant.png)

6. Navigate to the 'packages' directory, select the package named "meraki.zip", then click Open.
    ![mit-package-select](images/012-package-select.png)

7. Click the Upload button. Repeat steps 4-7 for the remaining packages.
    ![mit-package-upload](images/013-package-upload.png)

8. Using the left navigation pane, expand the Connect menu, then select "Meraki Dashboard".
    ![mit-connect-meraki](images/020-connect_meraki.png)

9. Click the "New Organization" icon.
    ![mit-add-meraki-org](images/021-add_meraki_org.png)

10. Enter a description for your Organzation. Then enter your Meraki API Key. Press tab or click on an empty space in the dialog box, and the tool will retrieve a list of Organzations that you have access to. Once the list is loaded, click the Dropdown box, then click the name of the Organization you want to connect. Then click the "OK" button.
    ![mit-meraki-org-settings1](images/022-new_org_settings.png)

    ![mit-meraki-org-settings2](images/023-new_org_settings2.png)

11. In the left navigation pane, select "Cisco Umbrella".
    ![mit-connect-umbrella](images/030-connect_umbrella.png)

12. Click the "New Organization" icon.
    ![mit-add-umbrella-org](images/031-add_umbrella_org.png)

13. Enter a description for your Organzation. Then enter your Umbrella Management API Key & Secret, and your Umbrella Network Devices API Key & Secret. Press tab or click on an empty space in the dialog box, and the tool will retrieve a list of Organzations that you have access to. Once the list is loaded, click the Dropdown box, then click the name of the Organization you want to connect. Then click the "OK" button.
    ![mit-umbrella-org-settings](images/032-umbrella_org_settings.png)

14. In the left navigation pane, select "Integrate". Locate the "Meraki Auto Tunnel (Umbrella SIG)" entry, and click the "+" icon to add the integration.
    ![mit-integrations-list](images/040-integrations.png)

15. Select the Meraki Organization and the Umbrella organization that you want to integrate, then click the "Save Changes" button.
    ![mit-integrations-configure](images/041-configure_integration.png)

### Using the API<a name="configure-api"/> ([^ Top](#top))
* Above, you generated a new API token. You can use it with the API by passing it as an Authorization header as a Bearer token (Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234).

#### Uploading Packages
1) Upload the meraki package
```
curl -L -H "Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234" -F "file=@packages/meraki.zip" -X POST http://127.0.0.1:8000/api/v0/uploadzip/
scripts dashboard.py
database meraki.json
Installed 129 object(s) from 1 fixture(s)
{"id":"801a9979-9430-419d-b0d4-a811e605686a","url":"http://127.0.0.1:8000/api/v0/uploadzip/801a9979-9430-419d-b0d4-a811e605686a/","description":"meraki","file":"http://127.0.0.1:8000/upload/k0rzzrt0.zip","tenant":"00000000-0000-0000-0000-000000000000","uploaded_at":"2020-09-25T21:07:29.724189Z"}
```

2) Upload the umbrella package
```
curl -L -H "Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234" -F "file=@packages/umbrella.zip" -X POST http://127.0.0.1:8000/api/v0/uploadzip/
scripts umbrella.py
database umbrella.json
Installed 2 object(s) from 1 fixture(s)
{"id":"8f0449c0-990f-46d6-bd7e-53b01c5a2c04","url":"http://127.0.0.1:8000/api/v0/uploadzip/8f0449c0-990f-46d6-bd7e-53b01c5a2c04/","description":"umbrella","file":"http://127.0.0.1:8000/upload/465bzz4r.zip","tenant":"00000000-0000-0000-0000-000000000000","uploaded_at":"2020-09-25T21:07:29.915069Z"}
```

3) Upload the auto-tunnel-meraki package
```
curl -L -H "Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234" -F "file=@packages/auto-tunnel-meraki.zip" -X POST http://127.0.0.1:8000/api/v0/uploadzip/
scripts auto_tunnel_meraki.py
database db.json
Installed 1 object(s) from 1 fixture(s)
{"id":"bafb8506-1f44-42d3-bb66-0f043bf471d0","url":"http://127.0.0.1:8000/api/v0/uploadzip/bafb8506-1f44-42d3-bb66-0f043bf471d0/","description":"auto_tunnel_meraki","file":"http://127.0.0.1:8000/upload/wcd68zjl.zip","tenant":"00000000-0000-0000-0000-000000000000","uploaded_at":"2020-09-25T21:07:30.709502Z"}
```

#### Connecting Meraki Dashboard
1) Add your Meraki Dashboard Organization to Meraki Integration Tools using the following API call. You will need to provide your Meraki Dashboard API key and the [Organization ID](https://dashboard.meraki.com/api_docs/v0#list-the-organizations-that-the-user-has-privileges-on) that you would like to connect to Meraki Integration Tools.
    ```
    curl -L -H "Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234" -H 'Content-Type: application/json' -X POST --data-binary '{"name":"My Meraki Dashboard","authparm":{"api":{"baseurl":"https://api.meraki.com/api/v1","key":"1234567890abcdefghijklmnopqrstuvwxyz1234","orgid":"1234567890"}},"devicetype":"Meraki"}' http://127.0.0.1:8000/api/v0/controllers/?detail=false
    {"id":"11112222-3333-4444-5555-666677778888","url":"http://127.0.0.1:8000/api/v0/controllers/11112222-3333-4444-5555-666677778888/","name":"Josh Anderson","authparm":{"api":{"baseurl":"https://api.meraki.com/api/v1","key":"1234567890abcdefghijklmnopqrstuvwxyz1234","orgid":"1234567890"}},"mgmtaddress":"","tenant":{"id":"11112222-3333-4444-5555-666677778888","name":"joshand@cisco.com"},"devicetype":"Meraki"}
    ```

#### Connecting Umbrella Dashboard
1) Add your Umbrella Dashboard Organization to Meraki Integration Tools using the following API call. You will need to provide your Meraki Dashboard API key and the [Organization ID](https://dashboard.meraki.com/api_docs/v0#list-the-organizations-that-the-user-has-privileges-on) that you would like to connect to Meraki Integration Tools.
    ```
    curl -L -H "Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234" -H 'Content-Type: application/json' -X POST --data-binary '{"name":"My Umbrella Dashboard","authparm":{"api":{"baseurl":"https://management.api.umbrella.com/v1","orgid":"1234567890","mgmtkey":"1234567890abcdefghijklmnopqrstuvwxyz1234","mgmtsecret":"1234567890abcdefghijklmnopqrstuvwxyz1234","netkey":"1234567890abcdefghijklmnopqrstuvwxyz1234","netsecret":"1234567890abcdefghijklmnopqrstuvwxyz1234"}},"devicetype":"Umbrella"}' http://127.0.0.1:8000/api/v0/controllers/?detail=false
    {"id":"11112222-4444-3333-5555-666677778888","url":"http://127.0.0.1:8000/api/v0/controllers/11112222-3333-4444-5555-666677778888/","name":"Josh","authparm":{"api":{"baseurl":"https://management.api.umbrella.com/v1","orgid":"1234567890","mgmtkey":"1234567890abcdefghijklmnopqrstuvwxyz1234","mgmtsecret":"1234567890abcdefghijklmnopqrstuvwxyz1234","netkey":"1234567890abcdefghijklmnopqrstuvwxyz1234","netsecret":"1234567890abcdefghijklmnopqrstuvwxyz1234"}},"mgmtaddress":"","tenant":{"id":"11112222-3333-4444-5555-666677778888","name":"joshand@cisco.com"},"devicetype":"Umbrella"}
    ```

#### Configuring an Integration
1) Establish an integration between the two dashboards using the 'auto-tunnel-meraki' module.
    ```
    curl -L -H "Authorization: Bearer 1234567890abcdefghijklmnopqrstuvwxyz1234" -H 'Content-Type: application/json' -X POST --data-binary '{"integrationmodule":"auto-tunnel-meraki","pm1":["11112222-3333-4444-5555-666677778888"],"pm2":["11112222-4444-3333-5555-666677778888"]}' http://127.0.0.1:8000/api/v0/integrationconfigurations/?detail=false
    {"id":"11112222-3333-4444-5555-666677778888","url":"http://127.0.0.1:8000/api/v0/integrationconfigurations/11112222-3333-4444-5555-666677778888/","tenant":"11112222-3333-4444-5555-666677778888","integrationmodule":"11112222-3333-4444-5555-666677778888","pm1":["11112222-3333-4444-5555-666677778888"],"pm2":["11112222-4444-3333-5555-666677778888"]}
    ```

#### Troubleshooting<a name="troubleshooting"/> ([^ Top](#top))
1. Using the left navigation pane, expand the Status menu, then select "Task Results".
    ![mit-task-list](images/050-task_results.png)

2. For details about a specific task, click the "Details" icon and review the logs. Click "OK" when finished.
    ![mit-task-details](images/051-task_details.png)

3. Database Access
    - In the event that there is a database-related problem, you can access the built-in database using http://127.0.0.1:8000/admin (if you used the examples above). Log in using the same credentials you use for the UI itself.
        
