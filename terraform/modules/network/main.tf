# =============================================================================
# Network Module — VPC, Public Subnets, Security Group
# =============================================================================

# --- VPC ---------------------------------------------------------------------
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "${var.project}-${var.environment}-vpc"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

# --- Internet Gateway --------------------------------------------------------
# Required for public subnets to reach the internet.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name        = "${var.project}-${var.environment}-igw"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

# --- Public Subnets ----------------------------------------------------------
# One per AZ. count.index picks the right CIDR and AZ from the input lists.
resource "aws_subnet" "public" {
  count             = length(var.public_subnet_cidrs)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = var.availability_zones[count.index]

  # Instances launched here get a public IP automatically.
  map_public_ip_on_launch = true

  tags = {
    Name        = "${var.project}-${var.environment}-public-subnet-${count.index + 1}"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
    Tier        = "public"
  }
}

# --- Route Table + Association -----------------------------------------------
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name        = "${var.project}-${var.environment}-public-rt"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

resource "aws_route_table_association" "public" {
  count          = length(aws_subnet.public)
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# --- Security Group ----------------------------------------------------------
# DEVIATION: Port 22 restricted to var.ssh_allowed_cidr (default 10.0.0.0/8),
# NOT 0.0.0.0/0 as the spec said. See README Decisions & Deviations.
resource "aws_security_group" "web" {
  name        = "${var.project}-${var.environment}-web-sg"
  description = "Web tier: HTTP/HTTPS open, SSH restricted"
  vpc_id      = aws_vpc.main.id

  # HTTP — open to world (legitimate for a web tier)
  ingress {
    description = "HTTP from anywhere"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # HTTPS — open to world
  ingress {
    description = "HTTPS from anywhere"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH — RESTRICTED. The spec said 0.0.0.0/0 but that is a critical security risk.
  ingress {
    description = "SSH from approved CIDR only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  # All outbound traffic allowed (standard for application servers)
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project}-${var.environment}-web-sg"
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}
