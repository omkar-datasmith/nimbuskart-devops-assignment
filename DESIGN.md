# DESIGN.md — Cost Janitor: Hardening, Scale & Productionisation

## Multi-cloud reality

To add GCP without rewriting the core, the Janitor would adopt a provider abstraction pattern:
janitor/
├── core/
│   ├── base_scanner.py      # Abstract base class: scan(), build_finding()
│   ├── report.py            # Schema-agnostic report generation
│   └── constants.py         # Shared pricing and tag constants
├── providers/
│   ├── aws/
│   │   ├── ebs_scanner.py   # Implements base_scanner for EBS
│   │   ├── ec2_scanner.py
│   │   └── eip_scanner.py
│   └── gcp/
│       ├── disk_scanner.py  # GCP persistent disk orphans
│       ├── vm_scanner.py    # GCP Compute Engine stopped VMs
│       └── ip_scanner.py    # GCP unused external IPs
└── janitor.py               # CLI: loads providers, merges findings

Each provider implements the same `scan() → List[Finding]` interface.
Adding Azure means adding `providers/azure/` with no changes to core or CLI.

## Permissions

**Dry-run mode** (read-only) minimal IAM policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "JanitorReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVolumes",
        "ec2:DescribeInstances",
        "ec2:DescribeAddresses",
        "ec2:DescribeTags",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
```

**Delete mode** adds:
- `ec2:DeleteVolume` (scoped to volumes tagged `Protected!=true`)
- `ec2:ReleaseAddress`
- Never includes `ec2:TerminateInstances` — EC2 termination always requires human approval via a separate break-glass role.

## Safety net

**Failure mode 1 — Deleting a volume detached during a deployment:**
A deployment pipeline detaches a volume to resize it, then reattaches. If the Janitor runs
during that window, the volume appears orphaned and gets deleted, causing data loss.
Guardrail: enforce a minimum age threshold of 7 days before any auto-deletion, and require
a `Janitor-Safe=true` tag to be explicitly set by the owning team before auto-deletion is
permitted.

**Failure mode 2 — Stopping an EC2 that serves traffic via an untagged EIP:**
An instance missing tags gets flagged. If auto-termination were enabled, it could kill a
production instance. Guardrail: EC2 instances are never auto-terminated (safe_to_auto_delete
is hardcoded to False). All EC2 actions produce a finding with suggested_action=terminate
but require a human to action it via the AWS console or a separate approved pipeline.

## Observability

| Metric | Source | Alert threshold |
|--------|--------|-----------------|
| `janitor.orphans.total` | report.json summary, published to CloudWatch custom metrics | > 10 orphans triggers PagerDuty P3 |
| `janitor.waste.monthly_usd` | report.json summary | > $500/month triggers FinOps team Slack alert |
| `janitor.scan.duration_seconds` | Janitor script timing, CloudWatch | > 300s suggests API throttling |
| `janitor.scan.errors` | CloudWatch Logs metric filter on [ERROR] | Any error triggers immediate alert |
| `janitor.resources.untagged_pct` | Tag scan findings / total resources | > 20% untagged triggers team leads notification |

Published via `boto3.client('cloudwatch').put_metric_data()` at end of each scan run.
Dashboard in CloudWatch or Grafana (CloudWatch datasource) shows 30-day trend.

## What I did not build

I consciously left out a Moto-based unit test suite (janitor/tests/) due to time constraints
— the scanners work correctly against LocalStack but lack isolated unit tests with mocked
responses. I also did not implement remote Terraform state (S3 + DynamoDB locking), multi-account
IAM role assumption, or the GCP provider module. These are the highest-priority items for a
production hardening sprint and are documented in the README trade-offs section.
