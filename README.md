# AWS Marketplace Seller Readiness Tool

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

A self-service tool for AWS Marketplace SaaS sellers to validate listing integrations and listing effectiveness before MCO (Marketplace Channel Operations) review. Deploys into the seller's own AWS account via CloudFormation.

## Features

### Integration Tests
Validates all required SaaS integrations against a live Limited listing:

| Test | Description |
|------|-------------|
| Registration Page | Page loads and accepts the marketplace token |
| ResolveCustomer | Token exchange returns a valid customer identifier |
| GetEntitlements | Active entitlements exist (contract-based listings) |
| BatchMeterUsage | Usage records can be submitted (metering listings) |
| Concurrent Agreements | Enabled on listing (required for new listings from June 1, 2026) |
| EventBridge | Rules configured for subscription lifecycle events |

### Listing Effectiveness Scorer
AI-powered scoring across 15+ categories with Amazon Bedrock (Claude):
- Discoverability — title, keywords, highlights
- Evaluation — media, reviews, long description
- Pricing — free trial, PAYG, contract pricing
- Procurement — Vendor Insights, SCMP, Quick Launch
- AI-generated executive summary and rewrite suggestions per field

## Architecture

```
Browser (CloudFront)
    │  HTTP POST
    ▼
API Gateway → Lambda (Python 3.12)
                 ├── AWS Marketplace Catalog API
                 ├── Marketplace Metering/Entitlement APIs
                 ├── Amazon Bedrock (Claude 3 Haiku)
                 └── Amazon EventBridge
```

All API calls run within the seller's own AWS account. No credentials leave their environment.

## Deploy

### Prerequisites
- AWS CLI configured
- Python 3 and pip3

### One command deploy

```bash
chmod +x build.sh
./build.sh
```

Creates:
- Lambda function + API Gateway
- S3 bucket + CloudFront distribution (frontend)
- IAM role with least-privilege Marketplace, Bedrock, and EventBridge permissions

Prints the **TestToolUrl** on completion — open it in your browser.

## Usage

1. Subscribe to your own Limited listing to get a registration token
2. Open the TestToolUrl
3. Enter your Product Code — listing type is auto-detected
4. Paste the full registration redirect URL (includes the marketplace token)
5. Click **Run Integration Tests**
6. Switch to **Listing Effectiveness** tab, enter your Product ID, click **Score My Listing**

## Cleanup

```bash
aws cloudformation delete-stack --stack-name mp-saas-tester
```

## Project Structure

```
├── backend/
│   ├── handler.py        Lambda function
│   └── requirements.txt
├── frontend/
│   └── index.html        Single-page UI (no build step)
├── infra/
│   └── template.yaml     CloudFormation template
├── build.sh              Build and deploy
├── serve.sh              Local dev server
├── publish.sh            Publish assets to S3 for workshop distribution
├── ARCHITECTURE.md       Technical walkthrough
└── DESCRIPTION.md        Problem statement and product description
```

## Security

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

This tool deploys resources into your AWS account. Review the IAM permissions in `infra/template.yaml` before deploying.

## License

This project is licensed under the Apache 2.0 License — see [LICENSE](LICENSE).
