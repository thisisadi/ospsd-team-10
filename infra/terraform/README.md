# HW3 Terraform Scaffold

This scaffold mirrors the App Runner deployment used for HW3 while keeping secrets out of the repository.
It is intentionally small: reviewers can see the expected AWS resources without needing access to the
private production Terraform state.

It expects an existing container image in ECR. Runtime secrets such as `OPENAI_API_KEY`,
`SESSION_SECRET_KEY`, OAuth credentials, and chat session tokens should be configured in the
deployment platform or a secrets manager, not in `.tfvars` committed to git.

```bash
cd infra/terraform
terraform init
terraform plan \
  -var='aws_region=us-east-1' \
  -var='service_name=ospsd-team-10-hw3' \
  -var='image_identifier=396608794887.dkr.ecr.us-east-1.amazonaws.com/ospsd-cloud-service:latest'
```

## Variables

| Variable | Required | Description |
| --- | --- | --- |
| `aws_region` | No | AWS region for App Runner and ECR. Defaults to `us-east-1`. |
| `service_name` | No | App Runner service name. Defaults to `ospsd-team-10-hw3`. |
| `image_identifier` | Yes | Fully qualified ECR image URI with tag. |
| `storage_provider` | No | Runtime provider selector: `s3`, `gcp`, or `mock`. |

## Secret Handling

Do not put these values in committed `.tfvars` files:

- `OPENAI_API_KEY`
- `SESSION_SECRET_KEY`
- OAuth client ids/secrets
- AWS access keys
- Team 9 chat session ids
- GCP service account JSON

Production should wire those values through App Runner environment secrets or AWS Secrets Manager.
TODO for production hardening: replace plain `runtime_environment_variables` with
`runtime_environment_secrets` references for every secret-bearing value.

For the real deployment, use the shared infra repository listed in the root README. This local scaffold
exists so reviewers can see the expected AWS resources from this application repository.
