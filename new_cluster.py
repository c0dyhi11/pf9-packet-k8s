"""This is a script to create k8s clusters using Platform9 Qbert and Packet Baremetal."""
import openstack
import qbert
import uuid
import re
import os
import json
from python_terraform import *


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


def create_terraform_stack(cluster_name, auth_token, project_id, master_size, worker_size, facility, master_count,
                           worker_count, du_fqdn, keystone_user, keystone_password, cluster_uuid, node_pool_uuid,
                           zone_name, aws_access_key, aws_secret_key, aws_region):
  
    hostname = re.sub(r"[^a-zA-Z0-9]+", '-', cluster_name).lower()
    tags = ["cluster_name={}".format(cluster_name), "cluster_id={}".format(cluster_uuid)]
    dir_path = "{}/{}".format(os.path.dirname(os.path.realpath(__file__)), "terraform")
    state_path = "{}/states/{}/{}".format(dir_path, project_id, cluster_uuid)
    os.makedirs(state_path, exist_ok=True)
    tf = Terraform(dir_path)
    return_code, stdout, stderr = tf.get(capture_output=False)
    print("GET Return Code: {}\n\n".format(return_code))
    print("GET STDOUT: {}\n\n".format(stdout))
    print("GET STDERR: {}\n\n".format(stderr))
    return_code, stdout, stderr = tf.init(capture_output=False)
    print("INIT Return Code: {}\n\n".format(return_code))
    print("INIT STDOUT: {}\n\n".format(stdout))
    print("INIT STDERR: {}\n\n".format(stderr))
    approve = {"auto-approve": True}
    plan_file = "{}/plan.tf".format(state_path)
    return_code, stdout, stderr = tf.plan(capture_output=False, out=plan_file, var={'hostname': hostname, 'auth_token': auth_token, 'project_id':
                                                project_id, 'master_size': master_size, 'worker_size': worker_size,
                                                'facility': facility, 'master_count': master_count,
                                                'worker_count': worker_count, 'du_fqdn': du_fqdn,
                                                'keystone_user': keystone_user, 'keystone_password': keystone_password,
                                                'cluster_uuid': cluster_uuid, 'node_pool_uuid': node_pool_uuid,
                                                'zone_name': zone_name, 'aws_access_key': aws_access_key,
                                                'aws_secret_key': aws_secret_key, 'aws_region': aws_region})
    return return_code, stdout, stderr


def main():
    with open('secrets.json') as f:
        secrets = json.load(f)
    account_endpoint = re.search("(?:http.*://)?(?P<host>[^:/ ]+)", secrets['OS_AUTH_URL']).group('host')
    conn = openstack.connect(cloud='cloud')
    os_project = create_project(conn, secrets['PACKET_PROJECT_ID'], secrets['OS_USERNAME'])
    cluster_id, node_pool_uuid = create_cluster(account_endpoint, secrets['OS_USERNAME'], secrets['OS_PASSWORD'],
                                                os_project['name'], secrets['OS_REGION_NAME'], secrets['CLUSTER_NAME'],
                                                secrets['R53_ZONE_NAME'][:-1])
    os_user, user_password = create_user(conn, cluster_id, os_project)
    tf_rc, tf_err, tf_out = create_terraform_stack(secrets['CLUSTER_NAME'], secrets['AUTH_TOKEN'],
                                                   secrets['PACKET_PROJECT_ID'], secrets['MASTER_SIZE'],
                                                   secrets['WORKER_SIZE'], secrets['FACILITY'], secrets['MASTER_COUNT'],
                                                   secrets['WORKER_COUNT'], account_endpoint, secrets['OS_USERNAME'],
                                                   secrets['OS_PASSWORD'], cluster_id, node_pool_uuid,
                                                   secrets['R53_ZONE_NAME'], secrets['AWS_ACCESS_KEY'],
                                                   secrets['AWS_SECRET_KEY'], secrets['AWS_REGION'])
    print("APPLY Return Code: {}\n\n".format(tf_rc))
    print("APPLY STDOUT: {}\n\n".format(tf_err))
    print("APPLY STDERR: {}\n\n".format(tf_out))


if __name__ == '__main__':
    main()
