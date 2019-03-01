variable "du_fqdn" {
}

variable "keystone_user" {
}

variable "keystone_password" {
}

variable "cluster_uuid" {
}

variable "node_pool_uuid" {
}

variable "hostagent_installer_type" {
  default = "legacy"
}

variable "hostagent_install_failure_webhook" {
  default = ""
}

variable "hostagent_install_options" {
  default = ""
}

variable "http_proxy" {
  default = ""
}

variable "is_spot_instance" {
  default = false
}
