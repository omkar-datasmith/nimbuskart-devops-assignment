# =============================================================================
# Network Module — Input Variables
# =============================================================================

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "public_subnet_cidrs" {
  description = "List of CIDR blocks for public subnets"
  type        = list(string)
}

variable "availability_zones" {
  description = "List of AZs for subnet placement"
  type        = list(string)
}

variable "ssh_allowed_cidr" {
  description = "CIDR allowed inbound on port 22"
  type        = string
}

variable "project" {
  description = "Project tag value"
  type        = string
}

variable "environment" {
  description = "Environment tag value"
  type        = string
}

variable "owner" {
  description = "Owner tag value"
  type        = string
}
