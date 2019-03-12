from python_terraform import Terraform, IsFlagged
import os
import re
from celery_config import app


def create_tf_vars_file(state_path, tf_vars):
    tf_vars_file = "{}/vars.tf".format(state_path)
    f = open(tf_vars_file, "w")
    for key, value in tf_vars.items():
        f.write('{} = "{}"\n'.format(key, value))
    return tf_vars_file


@app.task
def delete_terraform_stack(cluster_uuid, project_id, dir_path):
    state_path = "{}/states/{}/{}".format(dir_path, project_id, cluster_uuid)
    state_file = "{}/{}.tfstate".format(state_path, cluster_uuid)
    tf_vars_file = "{}/vars.tf".format(state_path)
    tf = Terraform(dir_path)
    return_code, stdout, stderr = tf.get(capture_output=False)
    return_code, stdout, stderr = tf.init(capture_output=False)
    return_code, stdout, stderr = tf.destroy(var_file=tf_vars_file, auto_approve=IsFlagged, capture_output=False,
                                             state=state_file)
    os.rmdir(state_path)
    return return_code, stdout, stderr


@app.task
def create_terraform_stack(cluster_name, tf_vars, dir_path):
    hostname = re.sub(r"[^a-zA-Z0-9]+", '-', cluster_name).lower()
    tf_vars['hostname'] = hostname
    state_path = "{}/states/{}/{}".format(dir_path, tf_vars['project_id'], tf_vars['cluster_uuid'])
    state_file = "{}/{}.tfstate".format(state_path, tf_vars['cluster_uuid'])
    os.makedirs(state_path, exist_ok=True)
    tf_vars_file = create_tf_vars_file(state_path, tf_vars)
    tf = Terraform(dir_path)
    return_code, stdout, stderr = tf.get(capture_output=False)
    return_code, stdout, stderr = tf.init(capture_output=False)
    return_code, stdout, stderr = tf.apply(var_file=tf_vars_file, skip_plan=True, auto_approve=IsFlagged,
                                           capture_output=False, state=state_file)
    return return_code, stdout, stderr
