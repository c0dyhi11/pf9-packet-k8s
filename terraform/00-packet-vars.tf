variable "hostname" {
}

variable "auth_token" {
}

variable "project_id" {
}

variable "master_size"{
  default = "c2.medium.x86"
}

variable "worker_size"{
  default = "c2.medium.x86"
}

variable "facility"{
  default = "sjc1"
}

variable "operating_system"{
  default = "ubuntu_16_04"
}

variable "billing_cycle"{
  default = "hourly"
}

variable "master_count"{
  default = 1
}

variable "worker_count"{
  default = 1
}
