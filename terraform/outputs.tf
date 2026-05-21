# =============================================================================
# Root Outputs — Required by assignment spec
# =============================================================================

output "vpc_id" {
  description = "VPC ID for NimbusKart staging"
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "IDs of the two public subnets"
  value       = module.network.public_subnet_ids
}

output "log_bucket_name" {
  description = "Name of the S3 application log bucket"
  value       = aws_s3_bucket.app_logs.bucket
}

output "web_instance_ids" {
  description = "IDs of the two web tier EC2 instances"
  value       = aws_instance.web[*].id
}

output "orphan_ebs_volume_id" {
  description = "ID of the intentionally unattached EBS volume (used in Janitor testing)"
  value       = aws_ebs_volume.orphan.id
}
