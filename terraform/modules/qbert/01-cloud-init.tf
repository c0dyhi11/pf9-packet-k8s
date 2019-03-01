data "template_file" "cloud_init" {
  template = "${file("modules/packet/configs/cloud_init.conf")}"
  vars {  
    is_master                             =   "${var.is_master}"
    du_fqdn                               =   "${var.du_fqdn}"
    keystone_user                         =   "${var.keystone_user}"
    keystone_password                     =   "${var.keystone_password}"
    cluster_uuid                          =   "${var.cluster_uuid}"
    node_pool_uuid                        =   "${var.node_pool_uuid}"
    http_proxy                            =   "${var.http_proxy}"
    is_spot_instance                      =   "${var.is_spot_instance}"
    hostagent_installer_type              =   "${var.hostagent_installer_type}"
    hostagent_install_failure_webhook     =   "${var.hostagent_install_failure_webhook}"
    hostagent_install_options             =   "${var.hostagent_install_options}"
  }
}

output "bootstrap" {
  value = "${data.template_file.cloud_init.rendered}"
}
