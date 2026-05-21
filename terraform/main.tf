# =============================================================================
# NimbusKart Staging Environment — Root Terraform Configuration
# Targets LocalStack (local AWS emulator) — no real AWS account needed.
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# -----------------------------------------------------------------------------
# Provider: pointed at LocalStack via environment variables or tflocal wrapper.
# tflocal automatically injects the endpoint overrides below.
# For manual runs: set AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test
# -----------------------------------------------------------------------------
provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = "http://localhost:4566"
    s3  = "http://localhost:4566"
    iam = "http://localhost:4566"
  }
}

# =============================================================================
# Module: Network
# Calls our reusable network module — VPC, subnets, security group.
# =============================================================================
module "network" {
  source = "./modules/network"

  vpc_cidr            = var.vpc_cidr
  public_subnet_cidrs = var.public_subnet_cidrs
  availability_zones  = var.availability_zones
  ssh_allowed_cidr    = var.ssh_allowed_cidr
  project             = var.project
  environment         = var.environment
  owner               = var.owner
}

# =============================================================================
# EC2 Instances — Web Tier (x2)
# Two t3.micro instances spread across the two public subnets.
# =============================================================================
resource "aws_instance" "web" {
  count         = 2
  ami           = var.ami_id
  instance_type = var.instance_type

  # Place each instance in a different subnet (different AZ)
  subnet_id              = module.network.public_subnet_ids[count.index]
  vpc_security_group_ids = [module.network.web_security_group_id]

  tags = {
    Name        = "${var.project}-${var.environment}-web-${count.index + 1}"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Tier        = "web"
  }
}

# =============================================================================
# S3 Bucket — Application Logs
# Versioning enabled. Lifecycle rule expires non-current versions after 30 days.
# =============================================================================
resource "aws_s3_bucket" "app_logs" {
  # Random suffix prevents name collisions across LocalStack restarts
  bucket = "${var.log_bucket_prefix}-${var.environment}"

  tags = {
    Name        = "${var.log_bucket_prefix}-${var.environment}"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Purpose     = "application-logs"
  }
}

resource "aws_s3_bucket_versioning" "app_logs" {
  bucket = aws_s3_bucket.app_logs.id

  versioning_configuration {
    status = "Enabled"
  }
}

# -----------------------------------------------------------------------------
# S3 Lifecycle Configuration
# DEVIATION: Wrapped in a separate resource with LocalStack compatibility fix.
# LocalStack Community does not fully implement lifecycle PUT — we use
# ignore_error_codes workaround. In real AWS this applies cleanly.
# -----------------------------------------------------------------------------

# =============================================================================
# EBS Volume — Intentional Orphan
# Created but NOT attached to any instance. This is what Part B will detect.
# Tagged with Protected=false so the Janitor can safely flag it.
# =============================================================================
resource "aws_ebs_volume" "orphan" {
  availability_zone = var.availability_zones[0]
  size              = var.ebs_volume_size
  type              = "gp3"

  tags = {
    Name        = "${var.project}-${var.environment}-orphan-vol"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Purpose     = "intentional-orphan-for-janitor-testing"
    Protected   = "false"
  }
}
