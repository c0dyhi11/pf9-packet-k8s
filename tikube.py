import re
import packet
import json
import qbert
import cluster_manager as cm
from flask import Flask
from flask import jsonify
from flask import request
from flask import Response


app = Flask(__name__)

with open('secrets.json') as f:
    SECRETS = json.load(f)


def packet_auth(auth_token, project_id):
    pattern = re.compile("([A-z0-9-])")
    print(not project_id)
    print(not auth_token)
    if not auth_token or not project_id or not pattern.match(auth_token) or not pattern.match(project_id):
        return False
    manager = packet.Manager(auth_token=auth_token)
    try:
        projects = manager.list_projects()
        for project in projects:
            if project.id == project_id:
                return True
    except packet.baseapi.Error:
        return False

    return False


def get_clusters(project_name, SECRETS):
    endpoint = re.search("(?:http.*://)?(?P<host>[^:/ ]+)", SECRETS['OS_AUTH_URL']).group('host')

    try:
        token, catalog, project_id = qbert.get_token_v3(endpoint, SECRETS['OS_USERNAME'], SECRETS['OS_PASSWORD'],
                                                        project_name)
        qbert_url = "{0}/{1}".format(qbert.get_service_url('qbert', catalog, SECRETS['OS_REGION_NAME']), project_id)
        clusters = qbert.get_request(qbert_url, token, "clusters")
        status_code = 200
    except:
        print("Something went wrong.")
        clusters = []
        status_code = 200
    return clusters, status_code


def get_cluster(project_name, cluster_id, SECRETS):
    endpoint = re.search("(?:http.*://)?(?P<host>[^:/ ]+)", SECRETS['OS_AUTH_URL']).group('host')

    try:
        token, catalog, project_id = qbert.get_token_v3(endpoint, SECRETS['OS_USERNAME'], SECRETS['OS_PASSWORD'],
                                                        project_name)
        qbert_url = "{0}/{1}".format(qbert.get_service_url('qbert', catalog, SECRETS['OS_REGION_NAME']), project_id)

        cluster = qbert.get_request(qbert_url, token, "clusters/{}".format(cluster_id))
        status_code = 200
    except:
        print("Something went wrong.")
        cluster = {'error': {'message': "Error: table clusters does not have object {}".format(cluster_id),
                             'code': 400}}
        status_code = 400

    if not isinstance(cluster, dict):
        print("Something went wrong.")
        cluster = {'error': {'message': "Error: table clusters does not have object {}".format(cluster_id),
                             'code': 400}}
        status_code = 400

    return cluster, status_code


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({'error': '405 Method Not Allowed'}), 405


@app.errorhandler(500)
def internal_server_error(e):
    return jsonify({'error': '500 Internal Server Error'}), 500



@app.route('/', strict_slashes=False)
def api_versions():
    versions = {"tikube": "v0"}
    return jsonify(versions)



@app.route('/v0/clusters', strict_slashes=False)
def cluster_error():
    return jsonify({"ERROR": "No project id detected in URL /v0/<project_id>/clusters/"}), 403


@app.route('/v0/<project_id>/clusters', methods=['GET', 'POST'], strict_slashes=False)
def clusters(project_id):
    auth_token = request.headers.get('X-Auth-Token')
    if not packet_auth(auth_token, project_id):
        return jsonify({'error': 'Invalid authentication token or project id.'}), 401

    if request.method == 'GET':
        clusters, status_code = get_clusters(project_id, SECRETS)
        return jsonify(clusters), status_code

    elif request.method == 'POST':
        body = request.get_json()
        if body['multi_master']:
            SECRETS['MASTER_COUNT'] = 3
        else:
            SECRETS['MASTER_COUNT'] = 1
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_NAME'] = body['cluster_name']
        SECRETS['FACILITY'] = body['facility']
        SECRETS['MASTER_SIZE'] = body['master_plan']
        SECRETS['WORKER_SIZE'] = body['worker_plan']
        SECRETS['WORKER_COUNT'] = body['worker_count']
        create_cluster = cm.do_create_stack(SECRETS)
        return jsonify(create_cluster), 200


@app.route('/v0/<project_id>/clusters/<cluster_id>', methods=['GET', 'DELETE'], strict_slashes=False)
def cluster(project_id, cluster_id):
    auth_token = request.headers.get('X-Auth-Token')
    if not packet_auth(auth_token, project_id):
        return jsonify({'error': 'Invalid authentication token or project id.'}), 401

    if request.method == 'GET':
        clusters, status_code = get_cluster(project_id, cluster_id, SECRETS)
        return jsonify(clusters), status_code

    elif request.method == 'DELETE':
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_ID'] = cluster_id
        delete_cluster = cm.do_delete_stack(SECRETS)
        return jsonify(delete_cluster), 200

    else:
        return jsonify({"error": "Invalid Method: {}".format(request.method)}), 401


@app.route('/v0/<project_id>/clusters/<cluster_id>/kubeconfig', methods=['POST'], strict_slashes=False)
def kubeconfig(project_id, cluster_id):
    auth_token = request.headers.get('X-Auth-Token')
    if not packet_auth(auth_token, project_id):
        return jsonify({'error': 'Invalid authentication token or project id.'}), 401

    if request.method == 'POST':
        body = request.get_json()
        SECRETS['user_id'] = body['user_id']
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_ID'] = cluster_id
        cluster, status_code = get_cluster(project_id, cluster_id, SECRETS)
        json.dumps(cluster)
        if status_code != 200:
            return jsonify(cluster), status_code
        if cluster['status'] != 'ok' or not cluster['lastOk'] or not cluster['lastOp']:
            return jsonify({'Not Ready': 'The cluster is not ready to serve a kubeconfig. Check back later'}), 409
        kubeconfig = cm.do_get_kubeconfig(SECRETS)
        if not isinstance(kubeconfig, dict):
            resp = Response(kubeconfig)
            resp.headers['Content-Type'] = 'application/octet-stream'
            resp.headers['Content-disposition'] = 'attachment; filename={}.yaml'.format(cluster_id)
            return resp
        else:
            return jsonify(kubeconfig), 400
    else:
        return jsonify({"error": "Invalid Method: {}".format(request.method)}), 401


@app.route('/v0/<project_id>/clusters/<cluster_id>/users', methods=['GET', 'POST'], strict_slashes=False)
def users(project_id, cluster_id):
    auth_token = request.headers.get('X-Auth-Token')
    if not packet_auth(auth_token, project_id):
        return jsonify({'error': 'Invalid authentication token or project id.'}), 401

    if request.method == 'GET':
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_ID'] = cluster_id
        get_users = cm.do_get_users(SECRETS)
        return jsonify(get_users), 200
    if request.method == 'POST':
        body = request.get_json()
        SECRETS['username'] = body['username']
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_ID'] = cluster_id
        new_user = cm.do_create_user(SECRETS)
        if 'Error' in new_user:
            return jsonify(new_user), 400
        else:
            return jsonify(new_user), 200
    else:
        return jsonify({"error": "Invalid Method: {}".format(request.method)}), 401


@app.route('/v0/<project_id>/clusters/<cluster_id>/users/<user_id>', methods=['GET', 'DELETE'], strict_slashes=False)
def user(project_id, cluster_id, user_id):
    auth_token = request.headers.get('X-Auth-Token')
    if not packet_auth(auth_token, project_id):
        return jsonify({'error': 'Invalid authentication token or project id.'}), 401

    if request.method == 'GET':
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_ID'] = cluster_id
        SECRETS['user_id'] = user_id
        delete_user = cm.do_get_users(SECRETS, user_id)
        return jsonify(delete_user), 200
    elif request.method == 'DELETE':
        SECRETS['AUTH_TOKEN'] = auth_token
        SECRETS['PACKET_PROJECT_ID'] = project_id
        SECRETS['CLUSTER_ID'] = cluster_id
        SECRETS['user_id'] = user_id
        delete_user = cm.do_delete_user(SECRETS)
        if 'Error' in delete_user:
            return jsonify(delete_user), 400
        else:
            return jsonify(delete_user), 200

    else:
        return jsonify({"error": "Invalid Method: {}".format(request.method)}), 401
