# NimbusKart DevOps Assignment
## Multi-Cloud Cost Hygiene & Automation

## Overview

This repository implements a cost hygiene automation system for NimbusKart, an e-commerce
startup whose AWS bill grew from $400 to $2,100/month due to orphaned resources. It
provisions a baseline AWS staging environment using Terraform on LocalStack, detects
wasteful resources using a Python-based Cost Janitor script, and enforces cost hygiene
continuously via GitHub Actions CI/CD on every pull request.

## How to run locally

```bash
# 1. Clone the repository
git clone https://github.com/omkar-datasmith/nimbuskart-devops-assignment.git
cd nimbuskart-devops-assignment

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r janitor/requirements.txt
pip install terraform-local awscli-local

# 4. Start LocalStack
docker run -d \
  -p 4566:4566 \
  -v /var/run/docker.sock:/var/run/docker.sock \
  --name localstack \
  localstack/localstack:3.8.1

# 5. Wait for LocalStack to be ready (~20 seconds)
sleep 20
curl http://localhost:4566/_localstack/health | python3 -m json.tool

# 6. Apply Terraform
cd terraform
tflocal init
tflocal apply -auto-approve
cd ..

# 7. Run the Cost Janitor
cd janitor
python janitor.py --dry-run
# View reports
cat report.json
cat summary.md
```

## Architecture
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions CI/CD                      │
│                                                             │
│  PR opened → LocalStack → Terraform Apply → Cost Janitor   │
│                                ↓                            │
│              report.json + summary.md artifacts             │
│                                ↓                            │
│              PR comment (if orphans found)                  │
│                                ↓                            │
│              Exit 1 (blocks merge if orphans exist)         │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Terraform (LocalStack)                    │
│                                                             │
│  VPC (10.20.0.0/16)                                        │
│  ├── Public Subnet AZ-1 ── EC2 web-1 (t3.micro)           │
│  ├── Public Subnet AZ-2 ── EC2 web-2 (t3.micro)           │
│  ├── Security Group (80/443 open, 22 restricted)           │
│  └── Internet Gateway                                       │
│                                                             │
│  S3 Bucket (app-logs, versioning enabled)                  │
│  EBS Volume (intentional orphan for Janitor testing)       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│                    Cost Janitor (Python)                     │
│                                                             │
│  scan_unattached_ebs()   → EBS in 'available' state        │
│  scan_stopped_ec2()      → stopped > N days                 │
│  scan_unused_eips()      → EIPs with no association        │
│  scan_missing_tags()     → missing Project/Env/Owner       │
│                                                             │
│  Output: report.json + summary.md                          │
│  --dry-run (default) | --delete (respects Protected=true)  │
└─────────────────────────────────────────────────────────────┘## Decisions & deviations

- **Port 22 restricted to 10.0.0.0/8** — spec said 0.0.0.0/0 but that exposes SSH to the entire internet; changed to a configurable variable with a safe private-range default.
- **No remote state backend** — spec did not mention it but local tfstate breaks team collaboration; documented as a known gap (would use S3 + DynamoDB locking in production).
- **S3 lifecycle configuration removed** — LocalStack Community 3.8.1 does not implement the S3 lifecycle PUT API and times out; the rule is documented here and would apply cleanly on real AWS.
- **LocalStack pinned to 3.8.1** — latest LocalStack requires a paid auth token; pinned to last free community version for reproducibility.
- **EC2 instances never auto-deleted** — safe_to_auto_delete is always false for EC2; terminating an instance is irreversible and requires human review.
- **EBS orphan age threshold set to 7 days** — newly created unattached volumes (age 0) are flagged but not auto-deleted; gives engineers a grace period after detachment.

## Trade-offs

Given one more week I would:
- Add a Moto-based test suite in janitor/tests/ with 100% scanner coverage
- Implement remote Terraform state using LocalStack S3 + DynamoDB
- Add GCP scanner module to demonstrate multi-cloud architecture
- Build a cost trend dashboard using CloudWatch metrics
- Add Slack notification integration for the CI report
- Implement tag enforcement via AWS Config rules

## AI usage disclosure

- **Tools used:** Claude (Anthropic) for code structure guidance, boilerplate Terraform, and debugging LocalStack compatibility issues.
- **What AI got wrong:** The initial argparse implementation used a mutually exclusive group with conflicting defaults for --dry-run and --delete, causing the janitor to always exit 0. I caught this by running the script manually and seeing no findings despite a known orphan volume existing. Fixed by simplifying to a single --delete flag.
- **What I wrote manually:** The LocalStack debugging and version pinning (3.8.1) was done entirely without AI help — I had to read Docker logs, understand the auth token error, and research which LocalStack version was the last free community release.
