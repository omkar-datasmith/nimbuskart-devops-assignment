locals {
  common_tags = {
    Project     = "NimbusKart"
    Environment = var.environment
    Owner       = "DevOps"
    ManagedBy   = "terraform"
  }
}

module "network" {
  source = "./modules/network"

  vpc_cidr             = "10.20.0.0/16"
  public_subnet_1_cidr = "10.20.1.0/24"
  public_subnet_2_cidr = "10.20.2.0/24"

  environment = var.environment
  common_tags = local.common_tags
}terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region     = var.aws_region
  access_key = "test"
  secret_key = "test"

  s3_use_path_style           = true
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true

  endpoints {
    ec2 = "http://localhost:4566"
    s3  = "http://localhost:4566"
  }
}
