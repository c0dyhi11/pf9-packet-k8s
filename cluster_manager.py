"""This is a script to create k8s clusters using Platform9 Qbert and Packet Baremetal."""
import openstack
import qbert
import uuid
import re
import os
import json
from python_terraform import Terraform, IsFlagged
from async_tasks import app, create_terraform_stack, delete_terraform_stack


def delete_cluster(endpoint, user, pw, tenant, region, cluster_id):
    token, catalog, project_id = qbert.get_token_v3(endpoint, user, pw, tenant)
    qbert_url = "{0}/{1}".format(qbert.get_service_url('qbert', catalog, region), project_id)
    delete_cluster = qbert.delete_request(qbert_url, token, "clusters/{}".format(cluster_id))

    return delete_cluster


def delete_user(conn, cluster_id):
    user_email = "{}@pf9.in".format(cluster_id)
    os_user = conn.get_user(user_email)
    if os_user:
        conn.delete_user(os_user, domain_id="default")
    else:
        print("User doesn't exist. Skipping deletion...")

    return os_user


def delete_project(conn, endpoint, user, pw, tenant, region):
    os_admin = conn.get_user(user)
    os_project = conn.get_project(tenant)
    if os_project:
        params = dict(project=os_project)
        role_mappings = conn.list_role_assignments(filters=params)
        for mapping in role_mappings:
            if mapping['user'] != os_admin['id']:
                print("Project still has users. Skipping project deletion...")
                return False
        token, catalog, project_id = qbert.get_token_v3(endpoint, user, pw, tenant)
        qbert_url = "{0}/{1}".format(qbert.get_service_url('qbert', catalog, region), project_id)
        clusters = qbert.get_request(qbert_url, token, "clusters")
        if len(clusters) != 0:
            print("Cluster(s) still exist. Skipping project deletion...")
            return False
        conn.delete_project(os_project, domain_id="default")
        return True
    else:
        print("Project doesn't exists. Skipping deletion...")
        return False


def create_cluster(endpoint, user, pw, tenant, region, cluster_name, dnz_zone_name, privileged_mode_enabled=True,
                   app_catalog_enabled=False, runtime_config='', allow_workloads_on_master=False,
                   networkPlugin='calico', container_cidr='172.30.0.0/16', services_cidr='172.31.0.0/16',
                   debug_flag=True):

    token, catalog, project_id = qbert.get_token_v3(endpoint, user, pw, tenant)
    qbert_url = "{0}/{1}".format(qbert.get_service_url('qbert', catalog, region), project_id)
    node_pool_uuid = qbert.get_node_pool(qbert_url, token)
    new_cluster = qbert.create_cluster(qbert_url, token, cluster_name, container_cidr, services_cidr,
                                       "", privileged_mode_enabled, app_catalog_enabled,
                                       allow_workloads_on_master, runtime_config, node_pool_uuid,
                                       networkPlugin, debug_flag)
    put_body = {"externalDnsName": "{}-api.{}".format(new_cluster, dnz_zone_name)}
    dns_update = qbert.put_request(qbert_url, token, "clusters/{}".format(new_cluster), put_body)

    return new_cluster, node_pool_uuid


def create_project(conn, project_name, os_admin_username):

    os_project = conn.get_project(project_name)
    if os_project:
        print("Project already exists. Skipping creation...")
    else:
        os_project = conn.create_project(project_name, domain_id="default")
    os_admin = conn.get_user(os_admin_username)
    conn.grant_role('admin', user=os_admin, project=os_project)
    return os_project


def create_user(conn, cluster_id, os_project):

    user_email = "{}@pf9.in".format(cluster_id)
    os_user = conn.get_user(user_email)
    if os_user:
        print("User already exists. Skipping creation...")
    else:
        user_password = str(uuid.uuid4())
        os_user = conn.create_user(name=user_email, password=user_password, email=user_email, domain_id="default")
    conn.grant_role('_member_', user=os_user, project=os_project)
    return os_user, user_password


def create_tf_vars_file(state_path, tf_vars):
    tf_vars_file = "{}/vars.tf".format(state_path)
    f = open(tf_vars_file, "w")
    for key, value in tf_vars.items():
        f.write('{} = "{}"\n'.format(key, value))
    return tf_vars_file


def do_delete_stack(secrets):
    account_endpoint = re.search("(?:http.*://)?(?P<host>[^:/ ]+)", secrets['OS_AUTH_URL']).group('host')
    conn = openstack.connect(cloud='cloud')
    cluster_id = secrets['CLUSTER_ID']
    cluster_deleted = delete_cluster(account_endpoint, secrets['OS_USERNAME'], secrets['OS_PASSWORD'], 
                                     secrets['PACKET_PROJECT_ID'], secrets['OS_REGION_NAME'], cluster_id)
    user_deleted = delete_user(conn, cluster_id)
    project_deleted = delete_project(conn, account_endpoint, secrets['OS_USERNAME'], secrets['OS_PASSWORD'], 
                                     secrets['PACKET_PROJECT_ID'], secrets['OS_REGION_NAME'])
    dir_path = "{}/{}".format(os.path.dirname(os.path.realpath(__file__)), "terraform")
    celery_task = delete_terraform_stack.delay(cluster_id, secrets['PACKET_PROJECT_ID'], dir_path)
    return ({'cluster_id': cluster_id, 'delete_resource_status': celery_task.status,
             'delete_resources_task_id': celery_task.id})


def do_create_stack(secrets):
    account_endpoint = re.search("(?:http.*://)?(?P<host>[^:/ ]+)", secrets['OS_AUTH_URL']).group('host')
    conn = openstack.connect(cloud='cloud')
    os_project = create_project(conn, secrets['PACKET_PROJECT_ID'], secrets['OS_USERNAME'])
    cluster_id, node_pool_uuid = create_cluster(account_endpoint, secrets['OS_USERNAME'], secrets['OS_PASSWORD'],
                                                os_project['name'], secrets['OS_REGION_NAME'], secrets['CLUSTER_NAME'],
                                                secrets['R53_ZONE_NAME'][:-1])
    os_user, user_password = create_user(conn, cluster_id, os_project)
    dir_path = "{}/{}".format(os.path.dirname(os.path.realpath(__file__)), "terraform")
    tags = ["cluster_name={}".format(secrets['CLUSTER_NAME']), "cluster_id={}".format(cluster_id)]
    tf_vars = {
                'auth_token': secrets['AUTH_TOKEN'], 
                'project_id': secrets['PACKET_PROJECT_ID'], 
                'master_size': secrets['MASTER_SIZE'],
                'worker_size': secrets['WORKER_SIZE'],
                'facility': secrets['FACILITY'],
                'master_count': secrets['MASTER_COUNT'],
                'worker_count': secrets['WORKER_COUNT'],
                'du_fqdn': account_endpoint,
                'keystone_user': secrets['OS_USERNAME'],
                'keystone_password': secrets['OS_PASSWORD'],
                'cluster_uuid': cluster_id,
                'node_pool_uuid': node_pool_uuid,
                'zone_name': secrets['R53_ZONE_NAME'], 
                'aws_access_key': secrets['AWS_ACCESS_KEY'],
                'aws_secret_key': secrets['AWS_SECRET_KEY'],
                'aws_region': secrets['AWS_REGION']
              }
    print(dir_path)
    celery_task = create_terraform_stack.delay(secrets['CLUSTER_NAME'], tf_vars, dir_path)

    return ({'cluster_id': cluster_id, 'create_resource_status': celery_task.status,
             'create_resources_task_id': celery_task.id})
