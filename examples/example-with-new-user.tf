provider "aws" {
  region = "eu-central-1"
}

resource "aws_iam_user" "iam_cred_rot_testing" {
  name = "iam-cred-rot-testing"
}

module "iam_key_rotation" {
  source            = "../"
  iam_user          = aws_iam_user.iam_cred_rot_testing.name
  max_age_days      = 1
  delete_after_days = 1
  deletion_window   = 7
}

output "my_module_iam_key" {
  value     = module.iam_key_rotation.updated_iam_key
  sensitive = true
}

output "my_module_iam_secret" {
  value     = module.iam_key_rotation.updated_iam_secret
  sensitive = true
}