variable "iam_user" {
  type = string
}

variable "iam_key" {
  type      = string
  sensitive = true
  default   = "-1"
}

variable "iam_secret" {
  type      = string
  sensitive = true
  default   = "-1"
}

variable "max_age_days" {
  type    = number
  default = 60
}

variable "delete_after_days" {
  type    = number
  default = 10
}

variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "customer_master_key_spec" {
  type    = string
  default = "SYMMETRIC_DEFAULT"
}

variable "deletion_window" {
  type    = number
  default = 30
}

variable "enable_key_rotation" {
  type    = bool
  default = true
}