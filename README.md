# AWS Marketplace Seller Toolkit

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

> This is a sample solution and is not intended for production use. It is provided as-is and should be thoroughly reviewed and tested before use in any environment. Use at your own risk.

A self-service tool for AWS Marketplace SaaS sellers to validate listing integrations and score listing effectiveness. Deploys into the seller's own AWS account via AWS SAM.

## Problem

Sellers submitting SaaS listings for review often discover integration issues only after submission, adding days or weeks to time-to-live. Common failures include registration pages not accepting POST tokens, missing ResolveCustomer calls, metering dimension mismatches, and missing EventBridge configuration. This toolkit lets sellers find and fix these issues before submission.

## Features

### Integration Tests
Validates all required SaaS integrations against a live Limited listing:

| Test | Description |
|------|-------------|
| Registration Page (POST) | Page accepts POST with marketplace token in form body |
| ResolveCustomer | Token exchange returns a valid customer identifier |
| ResolveCustomer History | Checks CloudTrail for ResolveCustomer calls from your application in the last 7 days |
| Error Handling | Sends an invalid token to verify graceful error handling (no stack traces) |
| GetEntitlements (Guidance) | Code examples and guidance for calling GetEntitlements (MCO verifies via internal logs) |
| BatchMeterUsage (Guidance) | Code examples and guidance for calling BatchMeterUsage (metering listings) |
| Metering History | Checks CloudTrail for BatchMeterUsage calls from your application |
| Notification Endpoint | EventBridge rules or SNS subscription configured for lifecycle events |
| Concurrent Agreements | Enabled on listing (required for new SaaS products from June 1, 2026) |
| EventBridge | Rules configured for aws.agreement-marketplace events |

### Listing Effectiveness Scorer
AI-powered scoring across 12 weighted categories with Amazon Bedrock (Claude):
- Content quality: Title, Short Description, Highlights (scored against a structured rubric with 4 bands)
- Discoverability: Search Keywords, Title SEO, Categories
- Media: Screenshots and videos
- Pricing: Free Trial, Pay-As-You-Go, Contract Pricing
- Support information completeness
- Product-aware evaluation tailored to your listing's industry and audience
- Per-highlight feedback identifying which bullet points need improvement
- AI-generated executive summary and rewrite suggestions per field

> **Note:** Scores are AI-generated guidance for improving listing discoverability and conversion. Recommendations are based on AWS Marketplace listing guidelines and PLG best practices. AI-generated rewrites (powered by Amazon Bedrock) should be reviewed before use.

## Architecture

```
Browser (CloudFront)
    |  HTTP POST
    v
API Gateway -> Lambda (Python 3.12)
                 |-- AWS Marketplace Catalog API
                 |-- Marketplace Metering/Entitlement APIs
                 |-- Amazon Bedrock (Claude 3 Haiku)
                 |-- Amazon EventBridge
                 |-- AWS CloudTrail
```

All API calls run within the seller's own AWS account. No credentials leave their environment.

## Deploy

### Prerequisites
- AWS CLI and [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) installed
- Python 3 and pip3
- AWS CLI configured with credentials for your AWS Marketplace seller account
- Account registered as an [AWS Marketplace seller](https://docs.aws.amazon.com/marketplace/latest/userguide/seller-registration-process.html)
- Amazon Bedrock model access enabled for **Claude 3 Haiku** in **us-east-1** (used by the Listing Effectiveness Scorer). Enable via the [Bedrock console](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess)
- A SaaS listing in **Limited** state (required to run integration tests)

> All resources deploy to **us-east-1**. AWS Marketplace APIs are only available in this region.

### Steps

1. Clone this repository
2. Build and deploy:

```bash
make deploy
```

This copies the frontend into the Lambda package, builds with SAM, and deploys. When prompted, confirm the changeset.

4. Open the **TestToolUrl** in your browser.

## Usage

1. Subscribe to your own Limited listing from a test buyer account
2. Open the TestToolUrl from the CloudFormation stack outputs
3. Enter your Product Code (listing type is auto-detected)
4. Paste the full registration redirect URL (includes the marketplace token)
5. Click **Run Integration Tests**
6. Switch to the **Listing Effectiveness** tab, enter your Product ID, click **Score My Listing**

## Cleanup

```bash
make clean
```

## Cost Estimate

This tool deploys into the seller's AWS account. With typical usage (a few test runs per day during integration development), costs are minimal:

| Service | Usage | Estimated Cost |
|---------|-------|---------------|
| AWS Lambda | ~10-20 invocations/day, 256 MB, <60s each | Free tier (1M requests/month free) |
| Amazon API Gateway (HTTP API) | ~10-20 requests/day | Free tier (1M requests/month free for 12 months) |
| Amazon S3 | 1 HTML file (~50 KB) | < $0.01/month |
| Amazon CloudFront | Low traffic (single user) | < $0.01/month |
| Amazon Bedrock (Claude 3 Haiku) | ~2-3 calls per scoring run (input ~2K tokens, output ~1K tokens) | ~$0.01 per scoring run |
| AWS CloudTrail | LookupEvents API calls (read-only) | Free (included with default trail) |

Estimated total: under $1/month for typical development usage. The primary variable cost is Bedrock — each listing score uses 2-3 Haiku invocations. Delete the stack when not in use to avoid any ongoing charges.

## Project Structure

```
backend/
  handler.py          Lambda function (integration tests + scorer)
  requirements.txt    Python dependencies
frontend/
  index.html          Single-page UI (no build step)
infra/
  template.yaml       SAM template (Lambda, API Gateway, S3, CloudFront, IAM)
samconfig.toml        SAM deploy defaults (stack name, region, capabilities)
ARCHITECTURE.md       Technical walkthrough
API_REFERENCE.md      API endpoint documentation
CONTRIBUTING.md       Contribution guidelines
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

This tool deploys resources into your AWS account. Review the IAM permissions in `infra/template.yaml` before deploying.

## License

This library is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file.
