#!/usr/bin/env python3
"""
Cost Janitor - NimbusKart AWS Waste Detection Script
Detects: unattached EBS, stopped EC2, unused EIPs, missing tags
"""

import json
import sys
import os
import argparse
import logging
from datetime import datetime, timezone
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from constants import (
    EBS_PRICE_PER_GB_MONTH,
    EBS_DEFAULT_TYPE,
    EIP_IDLE_PRICE_PER_MONTH,
    REQUIRED_TAGS,
    DEFAULT_STOPPED_DAYS_THRESHOLD,
    PROTECTED_TAG_KEY,
    PROTECTED_TAG_VALUE,
    LOCALSTACK_ACCOUNT_ID,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("janitor")


def get_tag_value(tags, key):
    for tag in (tags or []):
        if tag.get("Key") == key:
            return tag.get("Value")
    return None


def is_protected(tags):
    value = get_tag_value(tags, PROTECTED_TAG_KEY)
    return value is not None and value.strip().lower() == PROTECTED_TAG_VALUE.lower()


def tags_as_dict(tags):
    return {t["Key"]: t["Value"] for t in (tags or [])}


def missing_required_tags(tags):
    present = {t["Key"] for t in (tags or [])}
    return [r for r in REQUIRED_TAGS if r not in present]


def age_in_days(dt):
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days


def ebs_monthly_cost(size_gb, volume_type):
    rate = EBS_PRICE_PER_GB_MONTH.get(volume_type, EBS_PRICE_PER_GB_MONTH[EBS_DEFAULT_TYPE])
    return round(size_gb * rate, 2)


def build_finding(resource_id, resource_type, reason, age_days,
                  estimated_monthly_cost_usd, tags, suggested_action, safe_to_auto_delete):
    return {
        "resource_id": resource_id,
        "resource_type": resource_type,
        "reason": reason,
        "age_days": age_days,
        "estimated_monthly_cost_usd": estimated_monthly_cost_usd,
        "tags": tags_as_dict(tags),
        "suggested_action": suggested_action,
        "safe_to_auto_delete": safe_to_auto_delete,
    }


def scan_unattached_ebs(ec2_client):
    log.info("Scanning for unattached EBS volumes...")
    findings = []
    try:
        paginator = ec2_client.get_paginator("describe_volumes")
        pages = paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}])
        for page in pages:
            for vol in page["Volumes"]:
                vol_id    = vol["VolumeId"]
                size_gb   = vol.get("Size", 0)
                vol_type  = vol.get("VolumeType", EBS_DEFAULT_TYPE)
                tags      = vol.get("Tags", [])
                created   = vol.get("CreateTime", datetime.now(timezone.utc))
                age       = age_in_days(created)
                cost      = ebs_monthly_cost(size_gb, vol_type)
                protected = is_protected(tags)
                log.info(f"  Unattached: {vol_id} | {size_gb}GB | {age}d | protected={protected}")
                findings.append(build_finding(
                    resource_id=vol_id,
                    resource_type="ebs_volume",
                    reason="unattached — volume in 'available' state with no EC2 attachment",
                    age_days=age,
                    estimated_monthly_cost_usd=cost,
                    tags=tags,
                    suggested_action="delete",
                    safe_to_auto_delete=(not protected and age >= 7),
                ))
    except ClientError as e:
        log.error(f"EBS scan failed: {e}")
    log.info(f"  EBS scan done: {len(findings)} found.")
    return findings


def scan_stopped_ec2(ec2_client, stopped_days_threshold):
    log.info(f"Scanning for EC2 stopped > {stopped_days_threshold} days...")
    findings = []
    try:
        paginator = ec2_client.get_paginator("describe_instances")
        pages = paginator.paginate(
            Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
        )
        for page in pages:
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    inst_id   = inst["InstanceId"]
                    tags      = inst.get("Tags", [])
                    protected = is_protected(tags)
                    launch    = inst.get("LaunchTime", datetime.now(timezone.utc))
                    age       = age_in_days(launch)
                    if age < stopped_days_threshold:
                        continue
                    attached = inst.get("BlockDeviceMappings", [])
                    cost     = len(attached) * ebs_monthly_cost(8, "gp3")
                    log.info(f"  Stopped: {inst_id} | {age}d | protected={protected}")
                    findings.append(build_finding(
                        resource_id=inst_id,
                        resource_type="ec2_instance",
                        reason=f"stopped for {age} days (threshold: {stopped_days_threshold})",
                        age_days=age,
                        estimated_monthly_cost_usd=cost,
                        tags=tags,
                        suggested_action="terminate",
                        safe_to_auto_delete=False,
                    ))
    except ClientError as e:
        log.error(f"EC2 scan failed: {e}")
    log.info(f"  EC2 scan done: {len(findings)} found.")
    return findings


def scan_unused_eips(ec2_client):
    log.info("Scanning for unused Elastic IPs...")
    findings = []
    try:
        response = ec2_client.describe_addresses()
        for addr in response.get("Addresses", []):
            if addr.get("AssociationId"):
                continue
            alloc_id  = addr.get("AllocationId", addr.get("PublicIp", "unknown"))
            public_ip = addr.get("PublicIp", "unknown")
            tags      = addr.get("Tags", [])
            protected = is_protected(tags)
            log.info(f"  Unused EIP: {public_ip} | protected={protected}")
            findings.append(build_finding(
                resource_id=alloc_id,
                resource_type="elastic_ip",
                reason=f"EIP {public_ip} allocated but not associated with any instance",
                age_days=0,
                estimated_monthly_cost_usd=round(EIP_IDLE_PRICE_PER_MONTH, 2),
                tags=tags,
                suggested_action="release",
                safe_to_auto_delete=(not protected),
            ))
    except ClientError as e:
        log.error(f"EIP scan failed: {e}")
    log.info(f"  EIP scan done: {len(findings)} found.")
    return findings


def scan_missing_tags(ec2_client):
    log.info("Scanning for resources with missing required tags...")
    findings = []
    try:
        paginator = ec2_client.get_paginator("describe_instances")
        pages = paginator.paginate(
            Filters=[{"Name": "instance-state-name",
                      "Values": ["pending", "running", "stopping", "stopped", "shutting-down"]}]
        )
        for page in pages:
            for reservation in page["Reservations"]:
                for inst in reservation["Instances"]:
                    inst_id = inst["InstanceId"]
                    tags    = inst.get("Tags", [])
                    missing = missing_required_tags(tags)
                    if not missing:
                        continue
                    log.info(f"  EC2 {inst_id} missing: {missing}")
                    findings.append(build_finding(
                        resource_id=inst_id,
                        resource_type="ec2_instance",
                        reason=f"missing required tags: {', '.join(missing)}",
                        age_days=age_in_days(inst.get("LaunchTime", datetime.now(timezone.utc))),
                        estimated_monthly_cost_usd=0.0,
                        tags=tags,
                        suggested_action="tag",
                        safe_to_auto_delete=False,
                    ))
    except ClientError as e:
        log.error(f"EC2 tag scan failed: {e}")
    try:
        paginator = ec2_client.get_paginator("describe_volumes")
        pages = paginator.paginate()
        for page in pages:
            for vol in page["Volumes"]:
                vol_id  = vol["VolumeId"]
                tags    = vol.get("Tags", [])
                missing = missing_required_tags(tags)
                if not missing:
                    continue
                log.info(f"  EBS {vol_id} missing: {missing}")
                findings.append(build_finding(
                    resource_id=vol_id,
                    resource_type="ebs_volume",
                    reason=f"missing required tags: {', '.join(missing)}",
                    age_days=age_in_days(vol.get("CreateTime", datetime.now(timezone.utc))),
                    estimated_monthly_cost_usd=0.0,
                    tags=tags,
                    suggested_action="tag",
                    safe_to_auto_delete=False,
                ))
    except ClientError as e:
        log.error(f"EBS tag scan failed: {e}")
    log.info(f"  Tag scan done: {len(findings)} found.")
    return findings


def delete_findings(ec2_client, findings, dry_run):
    for finding in findings:
        rid   = finding["resource_id"]
        rtype = finding["resource_type"]
        safe  = finding["safe_to_auto_delete"]
        tags  = finding.get("tags", {})
        if tags.get(PROTECTED_TAG_KEY, "").lower() == PROTECTED_TAG_VALUE:
            log.warning(f"  SKIP Protected=true: {rid}")
            continue
        if not safe:
            log.info(f"  SKIP not safe: {rid}")
            continue
        if dry_run:
            log.info(f"  [DRY RUN] Would delete: {rid}")
            continue
        try:
            if rtype == "ebs_volume":
                ec2_client.delete_volume(VolumeId=rid)
                log.info(f"  DELETED: {rid}")
            elif rtype == "elastic_ip":
                ec2_client.release_address(AllocationId=rid)
                log.info(f"  RELEASED: {rid}")
            elif rtype == "ec2_instance":
                log.warning(f"  REFUSED auto-terminate EC2: {rid}")
        except ClientError as e:
            log.error(f"  Failed {rid}: {e}")


def generate_report(findings, account_id, region):
    total_cost = sum(f["estimated_monthly_cost_usd"] for f in findings)
    return {
        "scan_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "account_id": account_id,
        "region": region,
        "summary": {
            "total_orphans": len(findings),
            "estimated_monthly_waste_usd": round(total_cost, 2),
        },
        "findings": findings,
    }


def write_report_json(report, output_path="report.json"):
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    log.info(f"Report written: {output_path}")


def write_markdown_summary(report, output_path="summary.md"):
    findings = report["findings"]
    total    = report["summary"]["total_orphans"]
    cost     = report["summary"]["estimated_monthly_waste_usd"]

    lines = [
        "# Cost Janitor Report",
        "",
        f"**Scan time:** {report['scan_timestamp']}  ",
        f"**Region:** {report['region']}  ",
        f"**Account:** {report['account_id']}  ",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total orphans found | **{total}** |",
        f"| Estimated monthly waste | **${cost:.2f}** |",
        "",
    ]

    if not findings:
        lines.append("No orphaned resources found.")
    else:
        lines += [
            "## Findings",
            "",
            "| Resource ID | Type | Reason | Age (days) | Est. Cost/mo | Safe to Delete |",
            "|-------------|------|--------|------------|--------------|----------------|",
        ]
        for f in findings:
            safe = "Yes" if f["safe_to_auto_delete"] else "No"
            lines.append(
                f"| `{f['resource_id']}` | {f['resource_type']} | "
                f"{f['reason'][:50]} | {f['age_days']} | "
                f"${f['estimated_monthly_cost_usd']:.2f} | {safe} |"
            )
        lines += ["", "## Actions", ""]
        for f in findings:
            lines.append(f"- **{f['suggested_action'].upper()}** `{f['resource_id']}` — {f['reason'][:80]}")

    lines += ["", "---", "*Generated by Cost Janitor*"]

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    log.info(f"Summary written: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Cost Janitor — AWS orphan detector")
    parser.add_argument("--delete", action="store_true", default=False,
                        help="Delete safe orphans. Skips Protected=true.")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--endpoint-url", default="http://localhost:4566")
    parser.add_argument("--stopped-days", type=int, default=DEFAULT_STOPPED_DAYS_THRESHOLD)
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--account-id", default=LOCALSTACK_ACCOUNT_ID)
    args = parser.parse_args()

    delete_mode = args.delete
    dry_run     = not delete_mode
    mode_label  = "DELETE" if delete_mode else "DRY-RUN"

    log.info(f"Cost Janitor starting | mode={mode_label} | region={args.region}")
    log.info(f"Endpoint: {args.endpoint_url}")

    ec2_client = boto3.client(
        "ec2",
        region_name=args.region,
        endpoint_url=args.endpoint_url,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
    )

    account_id = args.account_id
    try:
        sts = boto3.client(
            "sts",
            region_name=args.region,
            endpoint_url=args.endpoint_url,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        )
        account_id = sts.get_caller_identity()["Account"]
    except Exception:
        log.info("STS unavailable — using default account ID.")

    all_findings = []
    all_findings.extend(scan_unattached_ebs(ec2_client))
    all_findings.extend(scan_stopped_ec2(ec2_client, args.stopped_days))
    all_findings.extend(scan_unused_eips(ec2_client))
    all_findings.extend(scan_missing_tags(ec2_client))

    seen, unique = set(), []
    for f in all_findings:
        key = (f["resource_id"], f["reason"])
        if key not in seen:
            seen.add(key)
            unique.append(f)

    log.info(f"Total unique findings: {len(unique)}")

    if delete_mode:
        log.warning("DELETE MODE — removing safe orphans.")
        delete_findings(ec2_client, unique, dry_run=False)
    elif unique:
        delete_findings(ec2_client, unique, dry_run=True)

    os.makedirs(args.output_dir, exist_ok=True)
    report = generate_report(unique, account_id, args.region)
    write_report_json(report, os.path.join(args.output_dir, "report.json"))
    write_markdown_summary(report, os.path.join(args.output_dir, "summary.md"))

    if unique:
        log.warning(f"Exiting 1 — {len(unique)} orphan(s) found.")
        sys.exit(1)

    log.info("Exiting 0 — clean.")
    sys.exit(0)


if __name__ == "__main__":
    main()
