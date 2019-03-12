import re
import packet
import json
import qbert
from flask import Flask
from flask import jsonify
from flask import request
from cluster_manager import do_create_stack, do_delete_stack


app = Flask(__name__)

with open('secrets.json') as f:
    SECRETS = json.load(f)


def packet_auth(auth_token, project_id):
    pattern = re.compile("([A-z0-9-])")
    if not pattern.match(auth_token) or not pattern.match(project_id):
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
        print("project_id: {}\nqbert_url: {}\ntoken: {}".format(project_id, qbert_url, token))
        cluster = qbert.get_request(qbert_url, token, "clusters/{}".format(cluster_id))
        status_code = 200
    except:
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


@app.route('/')
def api_versions():
    versions = {"tikube": "v0"}
    return jsonify(versions)


@app.route('/v0/clusters/')
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
        create_cluster = do_create_stack(SECRETS)
        return jsonify(create_cluster)


@app.route('/v0/<project_id>/clusters/<cluster_id>', methods=['GET', 'DELETE'])
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
        delete_cluster = do_delete_stack(SECRETS)
        return jsonify(delete_cluster)

    else:
        return jsonify({"error": "Invalid Method: {}".format(request.method)}), 401
