# AWS Marketplace Seller Toolkit

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

> This is a sample solution and is not intended for production use. It is provided as-is and should be thoroughly reviewed and tested before use in any environment. Use at your own risk.

A self-service tool for AWS Marketplace SaaS sellers to validate listing integrations and score listing effectiveness. Deploys into the seller's own AWS account via AWS SAM.

## Problem

Publishing a SaaS product on AWS Marketplace requires a registration page that integrates with the Marketplace APIs (ResolveCustomer, GetEntitlements, BatchMeterUsage). These integrations are reviewed by Marketplace Operations before your listing can go public. Integration issues discovered during review require resubmission, which can delay your listing going live.

This toolkit gives you instant feedback on your integrations so you can find and fix issues before you submit for review. It also scores your listing content against product-led growth (PLG) best practices, helping you improve discoverability and conversion from day one.

- **Integration Tests** — validate your registration page and API integrations against your live Limited listing
- **Listing Effectiveness Scorer** — AI-powered scoring across 12 categories with actionable recommendations to improve search ranking and buyer experience

## Features

### Integration Tests
Run automated checks against your live Limited listing before submitting for MCO review. The toolkit validates your registration page, token exchange, CloudTrail history, error handling, EventBridge configuration, and Concurrent Agreements. Where it can't test directly (GetEntitlements, BatchMeterUsage), it provides code examples and checks CloudTrail to confirm your backend is making the right calls.

### Listing Effectiveness Scorer
Get an AI-generated score for your listing across 12 weighted categories, with specific recommendations to improve discoverability and conversion:
- **Content** — Title, Short Description, Highlights scored on a 4-band scale (Needs Attention → Optimised)
- **Discoverability** — Search Keywords, Title SEO, Categories
- **Media** — Screenshots and video presence
- **Pricing & Trials** — Free Trial, Pay-As-You-Go, Contract options
- **Support** — Contact information completeness
- Per-highlight feedback, product-aware evaluation, and AI-generated rewrites you can copy straight into your listing

> **Note:** Scores are AI-generated guidance for improving listing discoverability and conversion. Recommendations are based on AWS Marketplace listing guidelines and PLG best practices. AI-generated rewrites (powered by Amazon Bedrock) should be reviewed before use.

## Architecture

The toolkit deploys a Lambda function behind API Gateway, with a static frontend on S3/CloudFront. All API calls run within the seller's own AWS account. See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed walkthrough.

## Prerequisites

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) v2 or later
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) v1 or later
- [Python 3.9+](https://www.python.org/downloads/) (required by SAM to build the Lambda)
- An AWS account [registered as a Marketplace seller](https://docs.aws.amazon.com/marketplace/latest/userguide/seller-registration-process.html)
- A SaaS listing in **Limited** state (for integration tests; the scorer works with any listing state)
- Amazon Bedrock model access for **Claude 3 Haiku** in us-east-1 — [enable here](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess)
- IAM permissions to deploy CloudFormation stacks. See [ARCHITECTURE.md](ARCHITECTURE.md#iam-permissions) for the minimum required policy.
- [Authenticated AWS CLI session](https://docs.aws.amazon.com/cli/latest/userguide/cli-chap-authentication.html) for your Marketplace seller account in **us-east-1**

> All resources deploy to **us-east-1**. AWS Marketplace APIs are only available in this region.

## Getting Started

### Step 1: Verify prerequisites

```bash
aws --version          # Requires: aws-cli/2.x
sam --version          # Requires: SAM CLI 1.x
python3 --version      # Requires: Python 3.9+
aws sts get-caller-identity --region us-east-1  # Verify authentication
```

### Step 2: Clone and deploy

```bash
git clone <repository-url>
cd aws-marketplace-seller-toolkit
sam build --template-file infra/template.yaml
sam deploy
```

When prompted, confirm the changeset. SAM packages the Lambda, deploys the stack, and automatically uploads the frontend.

### Step 3: Open the toolkit

The deploy outputs a **TestToolUrl** (CloudFront URL). Open it in your browser.

## Usage

1. Subscribe to your own Limited listing from a test buyer account
2. Open the TestToolUrl from the CloudFormation stack outputs
3. Enter your Product Code (listing type is auto-detected)
4. Paste the full registration redirect URL (includes the marketplace token)
5. Click **Run Integration Tests**
6. Switch to the **Listing Effectiveness** tab, enter your Product ID, click **Score My Listing**

## Cleanup

```bash
sam delete --stack-name your-stack-name --region us-east-1
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
ARCHITECTURE.md       Architecture overview and IAM permissions
API_REFERENCE.md      API calls and service integrations
CONTRIBUTING.md       Contribution guidelines
```

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

This tool deploys resources into your AWS account. Review the IAM permissions in `infra/template.yaml` before deploying.

## License

This library is licensed under the Apache 2.0 License. See the [LICENSE](LICENSE) file.
