# =============================================================================
# Input Variables — NimbusKart Staging
# All resources reference these; nothing is hardcoded in resource blocks.
# =============================================================================

variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment (staging, production)"
  type        = string
  default     = "staging"
}

variable "project" {
  description = "Project name for cost attribution tagging"
  type        = string
  default     = "nimbuskart"
}

variable "owner" {
  description = "Team or individual who owns these resources"
  type        = string
  default     = "platform-team"
}

# DEVIATION: Changed from 0.0.0.0/0 to a variable with a safer default.
# See README Decisions & Deviations section.
variable "ssh_allowed_cidr" {
  description = "CIDR block allowed to reach port 22. NEVER use 0.0.0.0/0 in real environments."
  type        = string
  default     = "10.0.0.0/8" # Private ranges only by default
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.20.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets (one per AZ)"
  type        = list(string)
  default     = ["10.20.1.0/24", "10.20.2.0/24"]
}

variable "availability_zones" {
  description = "Two AZs to spread subnets across"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "instance_type" {
  description = "EC2 instance type for web tier"
  type        = string
  default     = "t3.micro"
}

variable "ami_id" {
  description = "AMI ID to use for EC2 instances (LocalStack accepts any string)"
  type        = string
  default     = "ami-0c55b159cbfafe1f0" # Amazon Linux 2 — LocalStack doesn't validate
}

variable "ebs_volume_size" {
  description = "Size in GB of the intentionally orphaned EBS volume"
  type        = number
  default     = 20
}

variable "log_bucket_prefix" {
  description = "Prefix for the S3 log bucket name"
  type        = string
  default     = "nimbuskart-app-logs"
}

variable "noncurrent_version_expiry_days" {
  description = "Days after which non-current S3 object versions are expired"
  type        = number
  default     = 30
}
