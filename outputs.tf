output "updated_iam_key" {
  value = jsondecode(data.local_sensitive_file.iam_creds_file.content)["iam_key"]
}

output "updated_iam_secret" {
  value     = jsondecode(data.local_sensitive_file.iam_creds_file.content)["iam_secret"]
  sensitive = true
}