import json
import base64
from http import client as httplib
from urllib import parse as urlparse


def do_request(action, host, relative_url, headers, body):
    """Simple helper function to run REST calls."""
    conn = httplib.HTTPSConnection(host)
    body_json = json.JSONEncoder().encode(body)
    conn.request(action, relative_url, body_json, headers)
    response = conn.getresponse()
    return conn, response


def get_service_url(service_name, catalog, region):
    """Loop through the catalog and return the url for a service in a region."""
    for service in catalog:
        if service['name'] == service_name:
            for endpoint in service['endpoints']:
                if endpoint['region'] == region and endpoint['interface'] == "public":
                    return endpoint['url']


def put_request(url, token, url_path, body):
    """Small helper function to do PUT requests."""
    headers = {"Content-Type": "application/json", "Accept": "application/json", "X-Auth-Token": token}
    _, net_location, path, _, _ = urlparse.urlsplit(url)
    full_path = "{0}/{1}".format(path, url_path)

    conn, response = do_request("PUT", net_location, full_path, headers, body)

    if response.status != 200:
        print("URL: {}\n STATUS: {}\n MESSAGE: {}".format(full_path, response.status, response.reason))
        exit(1)
   
    try:
        response_body = json.loads(response.read())
    except ValueError:
        print("Cannot load JSON. Maybe this API doesn't return JSON")
        response_body = response.read()

    return response_body


def get_request(url, token, url_path, type="JSON"):
    """Small helper function to do GET requests."""
    headers = {"Accept": "application/json", "X-Auth-Token": token}
    body = ""
    _, net_location, path, _, _ = urlparse.urlsplit(url)
    full_path = "{0}/{1}".format(path, url_path)

    conn, response = do_request("GET", net_location, full_path, headers, body)

    if response.status != 200:
        print("URL: {}\n STATUS: {}\n MESSAGE: {}".format(full_path, response.status, response.reason))
        exit(1)

    if type == "JSON":
        response_body = json.loads(response.read())
    else:
        response_body = response.read()
    return response_body


def get_node_pool(url, token):
    """Grabbing Node Pool ID."""
    response_body = get_request(url, token, "cloudproviders")
    for node_pool in response_body:
        if node_pool['name'] == 'platform9':
            return node_pool['nodePoolUuid']


def create_cluster(qbert_url, token, cluster_name, containers_cidr, services_cidr,
                   externalDnsName, privileged, appCatalogEnabled, allowWorkloadsOnMaster,
                   runtimeConfig, nodePoolUuid, networkPlugin, debug_flag):
    """Create a Kubernetes Cluster via Qbert."""
    print("Creating Cluster.")
    headers = {"Content-Type": "application/json", "Accept": "application/json",
               "X-Auth-Token": token}
    body = {
        "name": cluster_name,
        "containersCidr": containers_cidr,
        "servicesCidr": services_cidr,
        "externalDnsName": externalDnsName,
        "privileged": privileged,
        "appCatalogEnabled": appCatalogEnabled,
        "allowWorkloadsOnMaster": allowWorkloadsOnMaster,
        "runtimeConfig": runtimeConfig,
        "nodePoolUuid": nodePoolUuid,
        "networkPlugin": networkPlugin,
        "debug": debug_flag
    }
    _, net_location, path, _, _ = urlparse.urlsplit(qbert_url)
    node_pool_path = "{0}/{1}".format(path, "clusters")

    conn, response = do_request("POST", net_location, node_pool_path, headers, body)

    if response.status != 200:
        print("{0}: {1}".format(response.status, response.reason))
        exit(1)

    response_body = json.loads(response.read())
    return response_body['uuid']


def get_qbert_v3_url(qbert_url, project_id):
    """Keystone only hands out a v1 url I need v3."""
    qbert_v3_url = "{0}/v3/{1}".format(qbert_url[0:-3], project_id)
    return qbert_v3_url


def get_token_v3(host, username, password, tenant):
    """Connect to Keystone and get a token."""
    print("Getting a valid keystone token.")
    headers = {"Content-Type": "application/json"}
    body = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": username,
                        "domain": {"id": "default"},
                        "password": password
                    }
                }
            },
            "scope": {
                "project": {
                    "name": tenant,
                    "domain": {"id": "default"}
                }
            }
        }
    }
    conn, response = do_request("POST", host, "/keystone/v3/auth/tokens",
                                headers, body)

    if response.status not in (200, 201):
        print("STATUS: {0}\n MESSAGE: {1}".format(response.status, response.reason))
        exit(1)

    token = response.getheader('X-Subject-Token')
    response_body = json.loads(response.read())
    catalog = response_body['token']['catalog']
    project_id = response_body['token']['project']['id']
    conn.close()
    return token, catalog, project_id


def get_kube_config(qbert_url, token, cluster_id, user, pw):
    """Download kubeconfig for our cluster."""
    response_body = get_request(qbert_url, token, "kubeconfig/{0}".format(cluster_id), "RAW")
    # Hash credentials and store with kubeconfig
    credentials = {
        "username": user,
        "password": pw
    }
    credential_string = json.dumps(credentials)
    bearer_token = base64.b64encode(credential_string)
    raw_kubeconfig = response_body.replace("__INSERT_BEARER_TOKEN_HERE__", bearer_token)
    f = open("/root/kubeconfig", "w")
    f.write(raw_kubeconfig)
    return raw_kubeconfig
