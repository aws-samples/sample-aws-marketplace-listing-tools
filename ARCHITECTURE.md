# Architecture

## Overview

```
Browser (CloudFront)
    |  HTTP POST /test
    v
API Gateway (HTTP API)
    |
    v
Lambda (Python 3.12)
    |-- AWS Marketplace Catalog API (DescribeEntity, ListEntities)
    |-- Marketplace Metering API (ResolveCustomer)
    |-- Amazon Bedrock (Claude 3 Haiku)
    |-- Amazon EventBridge (ListRules)
    |-- AWS CloudTrail (LookupEvents)
```

All API calls run within the seller's own AWS account. No credentials leave their environment.

## Components

| Component | Resource | Purpose |
|-----------|----------|---------|
| Frontend | S3 + CloudFront | Single-page HTML UI, no build step |
| API | API Gateway HTTP API | Routes POST /test to Lambda |
| Backend | Lambda (Python 3.12) | Integration tests, listing scorer, AI rewrites |
| AI | Amazon Bedrock (Claude 3 Haiku) | Listing quality scoring and rewrite suggestions |

## How it works

1. The seller opens the CloudFront URL in their browser
2. The frontend sends POST requests to API Gateway with the test action and parameters
3. Lambda routes each action to the appropriate handler function
4. Handler functions call AWS Marketplace APIs, Bedrock, CloudTrail, and EventBridge as needed
5. Results are returned to the frontend and displayed

The custom resource in the SAM template automatically deploys the frontend: on stack creation, the Lambda reads `index.html` from its own package, injects the API Gateway endpoint, and uploads it to the S3 bucket.

## IAM Permissions

### Deploying user/role

The user or role running `sam deploy` needs the following least-privilege policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFormation",
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:UpdateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:DescribeStackResource",
        "cloudformation:GetTemplate",
        "cloudformation:ListStackResources",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet"
      ],
      "Resource": "arn:aws:cloudformation:us-east-1:*:stack/aws-marketplace-seller-toolkit*/*"
    },
    {
      "Sid": "Lambda",
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:UpdateFunctionCode",
        "lambda:UpdateFunctionConfiguration",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:GetFunctionConfiguration",
        "lambda:AddPermission",
        "lambda:RemovePermission",
        "lambda:InvokeFunction",
        "lambda:TagResource",
        "lambda:ListTags"
      ],
      "Resource": "arn:aws:lambda:us-east-1:*:function:aws-marketplace-seller-toolkit*"
    },
    {
      "Sid": "APIGateway",
      "Effect": "Allow",
      "Action": [
        "apigateway:POST",
        "apigateway:GET",
        "apigateway:PATCH",
        "apigateway:DELETE",
        "apigateway:PUT"
      ],
      "Resource": "arn:aws:apigateway:us-east-1::*"
    },
    {
      "Sid": "S3",
      "Effect": "Allow",
      "Action": [
        "s3:CreateBucket",
        "s3:DeleteBucket",
        "s3:PutBucketPolicy",
        "s3:DeleteBucketPolicy",
        "s3:GetBucketPolicy",
        "s3:PutBucketPublicAccessBlock",
        "s3:GetBucketPublicAccessBlock",
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::aws-marketplace-seller-toolkit*",
        "arn:aws:s3:::aws-marketplace-seller-toolkit*/*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*",
        "arn:aws:s3:::aws-sam-cli-managed-default-*/*"
      ]
    },
    {
      "Sid": "CloudFront",
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateDistribution",
        "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution",
        "cloudfront:GetDistribution",
        "cloudfront:TagResource",
        "cloudfront:CreateOriginAccessControl",
        "cloudfront:UpdateOriginAccessControl",
        "cloudfront:DeleteOriginAccessControl",
        "cloudfront:GetOriginAccessControl"
      ],
      "Resource": "*"
    },
    {
      "Sid": "IAM",
      "Effect": "Allow",
      "Action": [
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:GetRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy",
        "iam:PassRole",
        "iam:TagRole"
      ],
      "Resource": "arn:aws:iam::*:role/aws-marketplace-seller-toolkit*"
    },
    {
      "Sid": "SAMBucketManagement",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation",
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::aws-sam-cli-managed-default-*"
    }
  ]
}
```

### Lambda execution role (created by the template)

The template creates a Lambda execution role with these permissions:

| Action | Purpose |
|--------|---------|
| `aws-marketplace:ResolveCustomer` | Exchange registration token for customer identifier |
| `aws-marketplace:GetEntitlements` | Check buyer entitlements (guidance step) |
| `aws-marketplace:BatchMeterUsage` | Submit usage records (guidance step) |
| `aws-marketplace:DescribeEntity` | Fetch listing details for scoring |
| `aws-marketplace:ListEntities` | List offers for pricing detection |
| `bedrock:InvokeModel` | AI scoring and rewrite suggestions |
| `events:ListRules` | Check EventBridge configuration |
| `cloudtrail:LookupEvents` | Verify ResolveCustomer/metering history |
| `sts:GetCallerIdentity` | Self-identify for CloudTrail filtering |
| `s3:PutObject`, `s3:GetObject` | Upload frontend to S3 bucket |
