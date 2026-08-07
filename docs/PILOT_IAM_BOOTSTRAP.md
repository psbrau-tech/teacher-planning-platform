# TPP Pilot Deployment IAM Bootstrap

## Root cause

The original pilot preflight role could assume through GitHub OIDC and read protected configuration, but it did not have deployment permissions. The first bootstrap attempt therefore failed at `cloudformation:DescribeStacks` before any infrastructure mutation occurred.

The correction does not turn the GitHub role into an infrastructure administrator. It separates responsibilities:

- `TeacherPlanningPlatformPilotGitHubOidc` manages only the named TPP stack, pushes the exact application image, requests or reads the pilot certificate, and reads deployment state.
- `TeacherPlanningPlatformPilotCloudFormationExecution` is assumed only by CloudFormation and performs the resource operations represented in `infra/pilot-stack.yml`.
- the GitHub role may pass only that exact execution role, and only to `cloudformation.amazonaws.com`.

## Governed policy files

- `infra/iam/tpp-cloudformation-execution-trust.json`
- `infra/iam/tpp-cloudformation-execution-policy.json`
- `infra/iam/tpp-github-oidc-deployment-policy.json`

The policies are specific to AWS account `697091778129`, Region `us-east-2`, stack `TeacherPlanningPlatformPilot`, ECR repository `teacher-planning-platform-pilot`, and the two task roles declared by the pilot template.

## Required manual IAM action

Run the repository script only from an authenticated administrator session in AWS account `697091778129`.

Review-only:

```bash
export AWS_REGION=us-east-2
bash scripts/configure_pilot_deployment_roles.sh
```

Apply after reviewing the three policy files:

```bash
export AWS_REGION=us-east-2
bash scripts/configure_pilot_deployment_roles.sh --apply
```

The script:

1. verifies the AWS account and Region;
2. verifies the existing GitHub OIDC role;
3. creates or updates `TeacherPlanningPlatformPilotCloudFormationExecution`;
4. installs the bounded execution policy on that role;
5. adds the bounded deployment policy to the existing OIDC role;
6. does not modify the OIDC trust relationship;
7. prints the execution-role ARN required by GitHub.

## GitHub environment update

In repository environment `tpp-pilot`, add this variable:

```text
TPP_CLOUDFORMATION_ROLE_ARN=arn:aws:iam::697091778129:role/TeacherPlanningPlatformPilotCloudFormationExecution
```

Do not replace `TPP_AWS_ROLE_ARN`. The two roles have different responsibilities.

## Read-only validation

After the IAM role and GitHub variable exist, run:

**Verify TPP Pilot Deployment IAM**

```text
Branch: main
Reason: Verify bounded TPP pilot deployment roles
```

Expected result:

- GitHub OIDC role assumed;
- CloudFormation execution role present;
- named stack read boundary verified;
- exact ECR repository read boundary verified;
- ACM and runtime-secret metadata reads verified;
- no AWS mutation.

## Bootstrap retry

Only after the read-only IAM verification passes, run:

**Bootstrap TPP Pilot**

```text
Branch: main
Reason: Bootstrap isolated TPP pilot infrastructure through execution role
request_certificate: true
```

The bootstrap script passes the dedicated execution-role ARN to CloudFormation on both initial stack deployments. No Cloudflare, Route 53, Supabase redirect, or Google sign-in setting is changed by this workflow.

## Safety boundary

- teacher and curriculum data only;
- no student data;
- no change to the existing GitHub OIDC trust relationship;
- no broad administrator policy attached to the GitHub role;
- no high-privilege database or application credential injected into ECS;
- CloudFormation execution permissions are limited to the services and named IAM roles required by `infra/pilot-stack.yml`.
