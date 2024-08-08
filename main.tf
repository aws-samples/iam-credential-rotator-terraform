data "aws_caller_identity" "current" {}

data "template_file" "kms_key_policy" {
  template = file("${path.module}/kms_key_policy.json")

  vars = {
    account_id = data.aws_caller_identity.current.account_id
    region     = var.region
    admin_user = data.aws_caller_identity.current.user_id
  }
}

resource "aws_kms_key" "ssm_key" {
  description              = "Key Used for encrypting for Iam credential rotation module for ${var.iam_user} "
  customer_master_key_spec = var.customer_master_key_spec
  is_enabled               = true
  enable_key_rotation      = var.enable_key_rotation
  deletion_window_in_days  = var.deletion_window
  policy                   = data.template_file.kms_key_policy.rendered
  tags = {
    purpose = "ROTATING IAM KEYS FOR ${var.iam_user}"
  }
}

resource "aws_kms_alias" "this" {
  name          = "alias/ssm-${var.iam_user}"
  target_key_id = aws_kms_key.ssm_key.key_id
}

resource "aws_ssm_parameter" "current_secret_id" {
  name        = "/${var.iam_user}/iam-key"
  description = "ROTATING IAM KEYS FOR ${var.iam_user}  - This updates automatically"
  type        = "SecureString"
  key_id      = aws_kms_key.ssm_key.id
  value       = var.iam_key
  tags = {
    purpose = "ROTATING IAM KEYS FOR ${var.iam_user}"
  }
  lifecycle {
    ignore_changes = [
      # Ignore changes to aws_ssm_parameter secret value, because IAM key rotation module will update it.
      value,
    ]
  }
}

resource "aws_ssm_parameter" "current_secret_key" {
  name        = "/${var.iam_user}/iam-secret"
  description = "ROTATING IAM KEYS FOR ${var.iam_user} - This updates automatically"
  type        = "SecureString"
  key_id      = aws_kms_key.ssm_key.id
  value       = var.iam_secret
  tags = {
    purpose = "ROTATING IAM KEYS FOR ${var.iam_user}"
  }
  lifecycle {
    ignore_changes = [
      # Ignore changes to aws_ssm_parameter secret value, because IAM key rotation module will update it.
      value,
    ]
  }
}

resource "aws_ssm_parameter" "deactivated_key_timestamp" {
  name        = "/${var.iam_user}/deactivated-key-timestamp"
  description = "Timestamp for the deactivated key to be deleted for ${var.iam_user} - This updates automatically"
  type        = "String"
  value       = "-1"
  tags = {
    purpose = "ROTATING IAM KEYS FOR ${var.iam_user}"
  }
  lifecycle {
    ignore_changes = [
      # Ignore changes to aws_ssm_parameter value, because IAM key rotation module will update it.
      value,
    ]
  }
}

resource "null_resource" "iam_creds_rotation_script" {
  triggers = { always_run = "${timestamp()}" }
  provisioner "local-exec" {
    command = "python3 ${path.module}/scripts/iam_creds_rotation_script.py > ./temp-${var.iam_user}.json"
    environment = {
      iam_user             = var.iam_user
      access_key_id        = aws_ssm_parameter.current_secret_id.value
      secret_key           = aws_ssm_parameter.current_secret_key.value
      max_age_in_days      = var.max_age_days
      delete_after_in_days = var.delete_after_days
      region               = var.region
    }
  }
}

data "local_sensitive_file" "iam_creds_file" {
  filename   = "./temp-${var.iam_user}.json"
  depends_on = [null_resource.iam_creds_rotation_script]
}