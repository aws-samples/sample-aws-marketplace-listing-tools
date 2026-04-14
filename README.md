# AWS Marketplace SaaS Integration Tester

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

A self-service tool for AWS Marketplace SaaS sellers to validate listing integrations and listing effectiveness before MCO (Marketplace Channel Operations) review. Deploys into the seller's own AWS account via CloudFormation.

## Features

### Integration Tests
Validates all required SaaS integrations against a live Limited listing:

| Test | Description |
|------|-------------|
| Registration Page (POST) | Page accepts POST with marketplace token in form body |
| ResolveCustomer | Token exchange returns a valid customer identifier |
| ResolveCustomer Causality | Verifies your registration page triggers a ResolveCustomer call via CloudTrail |
| ResolveCustomer History | Checks CloudTrail for ResolveCustomer calls from your application in the last 7 days |
| Error Handling | Sends an invalid token to verify graceful error handling (no stack traces) |
| GetEntitlements | Active entitlements exist (contract-based listings) |
| BatchMeterUsage | Usage records can be submitted (metering listings) |
| Metering History | Checks CloudTrail for BatchMeterUsage calls from your application |
| Listing Completeness | Required listing fields are present (logo, support, categories, media) |
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
- AWS CLI configured with credentials for your AWS Marketplace seller account
- Python 3 and pip3
- Account registered as an [AWS Marketplace seller](https://docs.aws.amazon.com/marketplace/latest/userguide/seller-registration-process.html)
- Amazon Bedrock model access enabled for **Claude 3 Haiku** in **us-east-1** (used by the Listing Effectiveness Scorer). Enable via the [Bedrock console](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess)
- A SaaS listing in **Limited** state (required to run integration tests)

> All resources deploy to **us-east-1**. AWS Marketplace APIs are only available in this region.

### Steps

1. Clone this repository
2. Package the Lambda function:

```bash
cd backend
pip3 install -r requirements.txt -t package/
cp handler.py package/
cd package && zip -r ../function.zip . && cd ..
rm -rf package
cd ..
```

3. Deploy the CloudFormation stack:

```bash
aws cloudformation deploy \
  --template-file infra/template.yaml \
  --stack-name mp-saas-tester \
  --capabilities CAPABILITY_NAMED_IAM
```

4. Update the Lambda function code:

```bash
aws lambda update-function-code \
  --function-name mp-saas-tester \
  --zip-file fileb://backend/function.zip
```

5. Get the stack outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name mp-saas-tester \
  --query "Stacks[0].Outputs"
```

6. Upload the frontend with the API endpoint injected:

```bash
API_ENDPOINT=$(aws cloudformation describe-stacks \
  --stack-name mp-saas-tester \
  --query "Stacks[0].Outputs[?OutputKey=='ApiEndpoint'].OutputValue" \
  --output text)

FRONTEND_BUCKET=$(aws cloudformation describe-stacks \
  --stack-name mp-saas-tester \
  --query "Stacks[0].Outputs[?OutputKey=='FrontendBucket'].OutputValue" \
  --output text)

sed "s|__API_ENDPOINT__|$API_ENDPOINT|g" frontend/index.html > /tmp/index.html
aws s3 cp /tmp/index.html s3://$FRONTEND_BUCKET/index.html --content-type text/html
```

7. Open the **TestToolUrl** from the stack outputs in your browser.

## Usage

1. Subscribe to your own Limited listing from a test buyer account
2. Open the TestToolUrl from the CloudFormation stack outputs
3. Enter your Product Code (listing type is auto-detected)
4. Paste the full registration redirect URL (includes the marketplace token)
5. Click **Run Integration Tests**
6. Switch to the **Listing Effectiveness** tab, enter your Product ID, click **Score My Listing**

## Cleanup

```bash
aws cloudformation delete-stack --stack-name mp-saas-tester
```

## Project Structure

```
backend/
  handler.py          Lambda function (integration tests + scorer)
  requirements.txt    Python dependencies
frontend/
  index.html          Single-page UI (no build step)
infra/
  template.yaml       CloudFormation template (Lambda, API Gateway, S3, CloudFront, IAM)
ARCHITECTURE.md       Technical walkthrough
API_REFERENCE.md      API endpoint documentation
DESCRIPTION.md        Problem statement and product description
CONTRIBUTING.md       Contribution guidelines
```

## Security

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

This tool deploys resources into your AWS account. Review the IAM permissions in `infra/template.yaml` before deploying.

## License

This project is licensed under the Apache 2.0 License. See [LICENSE](LICENSE).
