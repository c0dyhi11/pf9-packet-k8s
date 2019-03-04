provider "packet" {
  auth_token = "${var.auth_token}"
}

provider "aws" { 
  access_key = "${var.aws_access_key}"
  secret_key = "${var.aws_secret_key}"
  region     = "${var.aws_region}"
}

module "master_config" {
  source = "./modules/qbert"
  is_master = true
  du_fqdn = "${var.du_fqdn}"
  keystone_user = "${var.keystone_user}"
  keystone_password = "${var.keystone_password}"
  cluster_uuid = "${var.cluster_uuid}"
  node_pool_uuid = "${var.node_pool_uuid}"
  hostagent_installer_type = "${var.hostagent_installer_type}"
  hostagent_install_failure_webhook = "${var.hostagent_install_failure_webhook}"
  hostagent_install_options = "${var.hostagent_install_options}"
  http_proxy = "${var.http_proxy}"
  is_spot_instance = "${var.is_spot_instance}"
}

module "worker_config" {
  source = "./modules/qbert"
  is_master = false
  du_fqdn = "${var.du_fqdn}"
  keystone_user = "${var.keystone_user}"
  keystone_password = "${var.keystone_password}"
  cluster_uuid = "${var.cluster_uuid}"
  node_pool_uuid = "${var.node_pool_uuid}"
  hostagent_installer_type = "${var.hostagent_installer_type}"
  hostagent_install_failure_webhook = "${var.hostagent_install_failure_webhook}"
  hostagent_install_options = "${var.hostagent_install_options}"
  http_proxy = "${var.http_proxy}"
  is_spot_instance = "${var.is_spot_instance}"
}

module "master_node" {
  source = "./modules/packet"
  providers = {
    packet = "packet"
  }
  project_id = "${var.project_id}"
  hostname = "${var.hostname}-k8s-master"
  server_count = "${var.master_count}"
  server_size = "${var.master_size}"
  operating_system = "${var.operating_system}"
  facility = "${var.facility}"
  billing_cycle = "${var.billing_cycle}"
  user_data = "${module.worker_config.bootstrap}"
}

module "worker_node" {
  source = "./modules/packet"
  providers = {
    packet = "packet"
  }
  project_id = "${var.project_id}"
  hostname = "${var.hostname}-k8s-worker"
  server_count = "${var.worker_count}"
  server_size = "${var.worker_size}"
  operating_system = "${var.operating_system}"
  facility = "${var.facility}"
  billing_cycle = "${var.billing_cycle}"
  user_data = "${module.worker_config.bootstrap}"
}

module "master_dns_record" {
  source = "./modules/aws"
  providers = {
    aws = "aws"
  }

  zone_name = "${var.zone_name}"
  dns_hostname = "${var.cluster_uuid}-api"
  ips = ["${module.master_node.public_ips}"]
}

module "worker_dns_record" {
  source = "./modules/aws"
  providers = {
    aws = "aws"
  }

  zone_name = "${var.zone_name}"
  dns_hostname = "${var.cluster_uuid}"
  ips = ["${module.worker_node.public_ips}"]
}
