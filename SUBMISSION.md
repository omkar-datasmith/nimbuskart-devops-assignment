# Submission — DevOps Engineer Assignment

**Candidate name:** Omkar
**Email:** (your email)
**Date submitted:** 2026-05-21
**Hours spent (approximate):** 8

## Deliverables checklist

- [x] Part A: Terraform code under /terraform applies cleanly on LocalStack
- [x] Part A: `terraform validate` and `terraform fmt -check` both pass
- [x] Part B: Janitor script runs in --dry-run mode and produces report.json
- [x] Part B: GitHub Actions workflow runs green on a fresh PR
- [x] Part B: --delete mode respects Protected=true tag
- [x] Part C: DESIGN.md is present and within 2 pages
- [ ] Walkthrough video link below is accessible (unlisted is fine)

## Walkthrough video

Link: (add Loom/YouTube link after recording)
Length: max 5 minutes

## Sample report

Path to a sample report.json produced by your script:
`samples/report.example.json`

## Known limitations

- LocalStack pinned to 3.8.1 — newer versions require a paid auth token
- S3 lifecycle configuration skipped on LocalStack Community (works on real AWS)
- No Moto-based unit tests in janitor/tests/ — scanners tested against LocalStack
- EC2 instances are never auto-terminated — requires human review by design
- EBS auto-deletion only triggers after 7 days age threshold

## AI usage disclosure

- **Tools used:** Claude (Anthropic) for Terraform boilerplate, Python script structure, and debugging LocalStack issues.
- **What AI got wrong:** Argparse --dry-run/--delete mutual exclusion had a bug causing exit code 0 always. Caught by manual testing.
- **What I wrote manually:** LocalStack version debugging and the 3.8.1 pin — required reading Docker crash logs and researching free vs paid LocalStack versions.
