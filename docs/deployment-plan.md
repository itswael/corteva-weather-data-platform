# Deployment Plan and CI/CD Outline

## Purpose

This document defines a production-ready AWS deployment plan for the weather platform and a GitHub Actions delivery pipeline with explicit quality gates for linting, testing, build validation, and deployment.

## Target AWS Architecture

### Core Runtime

- **Route 53 + ACM**: Public DNS and TLS certificates for the application domain.
- **Application Load Balancer (ALB)**: Public entry point for the API.
- **ECS Fargate API service**: Runs the FastAPI application in private subnets.
- **ECS Fargate ingestion task**: Runs on a schedule to process raw weather files and refresh yearly statistics.
- **RDS PostgreSQL (Multi-AZ)**: Primary relational datastore for observations and yearly statistics.
- **S3 raw data bucket**: Stores raw weather text files and ingestion manifests.
- **EventBridge schedule**: Triggers the ingestion task on a cron schedule.
- **CloudWatch Logs and Metrics**: Central logging, metrics, dashboards, and alarms.

### Supporting Services

- **ECR**: Stores versioned Docker images for the API and ingestion task.
- **Secrets Manager or SSM Parameter Store**: Stores database credentials, app secrets, and environment-specific configuration.
- **KMS**: Encrypts S3 objects, RDS storage, secrets, and logs.
- **IAM roles**: Separate execution roles for API and ingestion tasks with least privilege.
- **AWS Backup / automated snapshots**: Point-in-time recovery for RDS.
- **Optional SQS dead-letter queue**: Captures ingestion failures for later replay if the ingestion volume grows.

## Network and Security Layout

- Place the ALB in public subnets.
- Place ECS tasks and RDS in private subnets.
- Restrict inbound database access to the ECS security group only.
- Use outbound egress only where needed for AWS APIs and package retrieval.
- Use OIDC-based GitHub Actions authentication to AWS instead of long-lived credentials.
- Enable security group egress and inbound rules by least privilege.
- Enforce HTTPS at the ALB and application level.
- Keep production docs and debug settings disabled in the production environment.

## Data Flow

1. Raw data files are uploaded to S3 under a controlled prefix such as `raw/`.
2. EventBridge triggers an ECS Fargate ingestion task on schedule.
3. The ingestion task reads new S3 objects, writes observations to PostgreSQL, and recomputes yearly statistics for affected station-years.
4. The API service reads from PostgreSQL and serves operational and analytical requests.
5. CloudWatch receives logs and metrics from both workloads.

## Failure-Resilient Design

- **RDS Multi-AZ** for database availability.
- **Idempotent ingestion** using station/date uniqueness so reruns do not duplicate data.
- **Chunked ingestion commits** to avoid large transaction failures.
- **Retry policy** for transient AWS or database failures.
- **Failure isolation**: ingestion runs in a separate task from the API.
- **S3 versioning** for raw files so corrupted uploads can be traced or recovered.
- **CloudWatch alarms** for API 5xx rate, ingestion failures, ECS task restarts, and RDS storage or connection pressure.
- **Backups and retention** for both database and raw files.

## Infrastructure as Code Recommendation

Use one of the following approaches:

- **Terraform** for explicit environment provisioning, remote state, and plan/apply gates.
- **AWS CDK** if you prefer higher-level AWS constructs in TypeScript or Python.

For a deployment-ready baseline, Terraform is the simpler operational choice because it maps cleanly to GitHub Actions plan/apply stages.

### Suggested Terraform Modules

- `vpc` for subnets, route tables, NAT gateways, and endpoints.
- `security` for security groups and IAM roles.
- `ecr` for application images.
- `rds` for PostgreSQL, subnet group, parameter group, backup policy.
- `s3` for raw files, versioning, lifecycle, encryption.
- `ecs-api` for the API task definition, service, autoscaling, ALB, target groups.
- `ecs-ingestion` for the scheduled task definition and task role.
- `events` for EventBridge schedules and task invocation.
- `observability` for log groups, dashboards, and alarms.

## Environment Strategy

- **dev**: Fast feedback, smaller instance sizes, shorter retention.
- **staging**: Production-like topology, gated deployment, smoke tests.
- **production**: Locked down secrets, required approvals, rollback ready.

## CI/CD Pipeline Overview

The GitHub Actions pipeline should enforce quality gates before any deployment.

### Pull Request Gates

1. **Lint**
   - Run `ruff check src tests`.
   - Run `ruff format --check src tests` if you want format enforcement.
2. **Tests**
   - Run unit tests with `pytest`.
   - Run integration tests with markers where needed.
3. **Build**
   - Build the Docker image.
   - Verify the image starts and basic health checks pass.
4. **Optional security checks**
   - Dependency audit or secret scanning if added later.

### Main Branch Gates

1. Re-run lint, tests, and build.
2. Build and push a versioned image to ECR.
3. Deploy to staging.
4. Run smoke tests against staging.
5. Require manual approval for production via GitHub Environment protection.
6. Deploy to production only after staging succeeds and approval is granted.

## GitHub Actions Workflow Outline

Use a single workflow with separate jobs for validation and deployment.

### Triggers

- `pull_request` for lint, tests, and build validation.
- `push` to `main` for staging and production delivery.
- Optional `workflow_dispatch` for manual releases.

### Jobs

- `lint`: runs Ruff checks.
- `test`: runs pytest with coverage and integration markers as needed.
- `build`: builds the Docker image and optionally publishes a release artifact.
- `deploy-staging`: pushes image to ECR and updates ECS staging service.
- `smoke-test`: exercises staging health and key API endpoints.
- `deploy-production`: requires approval through the GitHub `production` environment before ECS update.

### Deployment Gates

- Use GitHub Environments with required reviewers for `production`.
- Require `deploy-staging` success before `deploy-production`.
- Require smoke tests to pass before production approval.
- Block production deploys when the workflow is triggered from a feature branch.

## Suggested Repository Layout Additions

- `.github/workflows/ci-cd.yml`
- `infra/terraform/` or `infra/cdk/`
- `infra/terraform/modules/`
- `infra/terraform/envs/dev/`
- `infra/terraform/envs/staging/`
- `infra/terraform/envs/prod/`

## Operational Notes

- Keep raw data immutable in S3.
- Store only derived state in PostgreSQL.
- Tag all deployed images with commit SHA and environment alias.
- Log the deployed commit in ECS task metadata and CloudWatch.
- Keep a rollback path by redeploying the last known good image and, if needed, reverting Terraform state changes.

## Acceptance Criteria

A deployment is considered ready when the following are true:

- Infrastructure is defined as code.
- The API runs on ECS Fargate behind an ALB.
- PostgreSQL runs on RDS Multi-AZ with backups enabled.
- Raw files land in S3 with versioning and encryption.
- EventBridge triggers scheduled ingestion.
- CloudWatch collects logs and alarms.
- GitHub Actions blocks merges unless lint, tests, and build succeed.
- Production deploys require staging success and manual approval.
