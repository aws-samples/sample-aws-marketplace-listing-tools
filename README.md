# AWS Marketplace Seller Readiness Tool

A self-service tool for AWS Marketplace sellers to validate their SaaS listing integrations and listing effectiveness before MCO review.

## What it does

### Tab 1 — Integration Tests
Runs end-to-end integration checks against your live Limited listing:

| Test | Description |
|------|-------------|
| Registration Page | Verifies your page loads and accepts the marketplace token |
| ResolveCustomer | Validates token exchange returns a customer identifier |
| GetEntitlements | Confirms active entitlements (contract-based listings) |
| BatchMeterUsage | Validates usage records can be submitted (metering listings) |
| Concurrent Agreements | Checks if enabled (required for new listings from June 1, 2026) |
| EventBridge Integration | Checks if EventBridge rules exist for subscription events |

### Tab 2 — Listing Effectiveness Scorer
AI-powered scoring of your listing content across 15+ categories:
- Title, Short Description, Highlights, Long Description
- SEO / Search Keywords, Categories, Media
- Product-Led Growth: Free Trial, PAYG Pricing, Contract Pricing
- Procurement: Vendor Insights, SCMP, Quick Launch
- Social Proof: G2/Peerspot Reviews

Features:
- AI-generated executive summary (Amazon Bedrock / Claude)
- AI rewrite suggestions for each underperforming field
- Export report as text file
- Copy report to clipboard
- Progress tracker (checkboxes persist in localStorage)
- Direct links to fix each item in AWS Partner Central

## Prerequisites

- AWS CLI configured with credentials for the seller account
- A SaaS listing in **Limited** state in AWS Partner Central
- Subscribed to your own listing at least once (to get a registration token)

## Deploy

```bash
chmod +x build.sh
./build.sh
```

Deploys to your AWS account:
- Lambda function (Python 3.12)
- API Gateway (HTTP API)
- S3 bucket + CloudFront distribution (frontend)
- IAM role with Marketplace, Bedrock, and EventBridge permissions

Prints the **TestToolUrl** when complete — open that URL in your browser.

## Getting your registration token

1. Go to your listing on [AWS Marketplace](https://aws.amazon.com/marketplace)
2. Subscribe using a test buyer account
3. Click **Set Up Your Account** — your browser redirects to your registration page with a token:
   ```
   https://yourapp.com/register?x-amzn-marketplace-token=eyJ...
   ```
4. Copy the full URL and paste it into the tool

## Publish for workshop use

```bash
export MP_ASSETS_BUCKET=your-team-bucket-name
./publish.sh
```

Uploads assets to S3 and generates a Launch Stack URL for the workshop lab.

## Cleanup

```bash
aws cloudformation delete-stack --stack-name mp-saas-tester
```

## Project structure

```
mp-seller-readiness-tool/
  backend/
    handler.py          Lambda function — all API actions
    requirements.txt    Python dependencies (requests)
  frontend/
    index.html          Single-page web UI
  infra/
    template.yaml       CloudFormation template
  workshop/
    content/            Workshop lab markdown content
  build.sh              Build and deploy script
  serve.sh              Local frontend server (dev only)
  publish.sh            Publish assets to S3 for workshop
  README.md             This file
  ARCHITECTURE.md       Code walkthrough and technical details
  DESCRIPTION.md        Product description and problem statement
```
