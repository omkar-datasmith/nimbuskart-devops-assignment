"""
Pricing constants for Cost Janitor waste estimation.

Sources:
  EBS:          https://aws.amazon.com/ebs/pricing/ (us-east-1, 2024-01)
  EC2 t3.micro: https://aws.amazon.com/ec2/pricing/on-demand/ (us-east-1, Linux)
  Elastic IP:   https://aws.amazon.com/vpc/pricing/ (idle EIP)
"""

EBS_PRICE_PER_GB_MONTH = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}

EBS_DEFAULT_TYPE = "gp3"

EC2_HOURS_PER_MONTH = 730

EIP_IDLE_PRICE_PER_HOUR = 0.005
EIP_IDLE_PRICE_PER_MONTH = EIP_IDLE_PRICE_PER_HOUR * EC2_HOURS_PER_MONTH

REQUIRED_TAGS = ["Project", "Environment", "Owner"]

DEFAULT_STOPPED_DAYS_THRESHOLD = 14

PROTECTED_TAG_KEY = "Protected"
PROTECTED_TAG_VALUE = "true"

LOCALSTACK_ACCOUNT_ID = "000000000000"
