# HW3 Terraform Scaffold

This scaffold mirrors the App Runner deployment used for HW3 while keeping secrets out of the repository.

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

For the real deployment, use the shared infra repository listed in the root README. This local scaffold
exists so reviewers can see the expected AWS resources from this application repository.
