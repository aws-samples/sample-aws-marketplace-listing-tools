---
title: Test Your SaaS Listing Before MCO Review
weight: 10
---

## Overview

Before your SaaS listing can go live on AWS Marketplace, it must pass a technical review by the Marketplace Channel Operations (MCO) team. This lab provides a self-service tool to validate all required integrations and listing quality **before** submitting for review, so you can identify and fix issues early.

The tool has two parts:

| Tab | What it does |
|-----|-------------|
| **Integration Tests** | Validates your SaaS backend integrations against your live Limited listing |
| **Listing Effectiveness** | AI-powered scoring of your listing content with recommendations to improve discoverability and conversion |

### Integration tests covered

| Test | Why it matters |
|------|---------------|
| Registration Page | Buyers are redirected here after subscribing. MCO verifies it loads and accepts the marketplace token |
| ResolveCustomer | Your backend must exchange the token for a customer identifier immediately on buyer redirect |
| GetEntitlements | Confirms active entitlements exist for the subscribed customer (contract-based listings) |
| BatchMeterUsage | Validates usage records can be submitted for billing (metering listings) |
| Concurrent Agreements | Required for all new SaaS listings from June 1, 2026 |
| EventBridge | Subscription lifecycle events must route via EventBridge for new listings |

### Prerequisites

- A SaaS listing in **Limited** state in [AWS Partner Central](https://partnercentral.awspartner.com/partnercentral2/s/manage-products)
- Your registration page deployed and accessible via HTTPS
- An AWS account with permissions to deploy CloudFormation stacks
- Subscribed to your own listing at least once (to generate a test token)

---

## Step 1 — Subscribe to your own listing

You need a real marketplace token to test the registration flow. Get one by subscribing to your own listing.

1. Go to your listing on [AWS Marketplace](https://aws.amazon.com/marketplace)
2. Sign in with a test buyer account (can be the same account that owns the listing)
3. On your listing page, click **Subscribe**
4. Complete the subscription steps
5. Click **Set Up Your Account** — your browser redirects to your registration page with a token in the URL:

```
https://yourapp.com/register?x-amzn-marketplace-token=eyJ...
```

6. **Copy the full URL** from your browser's address bar — you will need this in Step 3

{{% notice tip %}}
If your registration page redirects immediately, check your browser history or network tab to find the original redirect URL containing the token.
{{% /notice %}}

---

## Step 2 — Deploy the test tool

1. Click the **Launch Stack** button below
2. The AWS CloudFormation console will open with the template pre-loaded
3. Click **Next** through the configuration pages (no changes needed)
4. Check the box to acknowledge IAM resource creation
5. Click **Create stack**
6. Wait for the stack status to show **CREATE_COMPLETE** (~3 minutes)

[![Launch Stack](https://s3.amazonaws.com/cloudformation-examples/cloudformation-launch-stack.png)](https://console.aws.amazon.com/cloudformation/home#/stacks/create/review?templateURL=TEMPLATE_S3_URL&stackName=mp-saas-tester)

7. Go to the **Outputs** tab of the stack and copy the **TestToolUrl** value — this is the URL for the test tool

{{% notice note %}}
The stack creates an IAM role, Lambda function, API Gateway, S3 bucket, and CloudFront distribution in your account. All Marketplace API calls are made from within your account — no credentials are shared externally.
{{% /notice %}}

---

## Step 3 — Run the integration tests

1. Open the **TestToolUrl** from the CloudFormation outputs in your browser
2. Enter your **Product Code** (found in Partner Central under your listing → Product overview)
3. The listing type will be **auto-detected** when you tab out of the Product Code field
4. Paste the full **Registration Redirect URL** you copied in Step 1
5. If your listing uses metering, enter your **Metering Dimension** name
6. Click **Run Integration Tests**

Each test shows pass ✓, fail ✗, or warning ⚠ with a plain-English explanation.

---

## Step 4 — Review results and fix issues

### Registration Page fails
- Ensure your page is publicly accessible via HTTPS
- Verify it accepts the `x-amzn-marketplace-token` query parameter
- Check there are no authentication walls blocking the initial redirect

### ResolveCustomer fails
- Confirm your backend calls `ResolveCustomer` in `us-east-1` immediately on buyer redirect
- Tokens expire after **60 minutes** — re-subscribe to get a fresh token
- Ensure the IAM role has `aws-marketplace:ResolveCustomer` permission

### GetEntitlements fails
- Only applicable to contract-based listings — verify you selected the correct listing type
- Confirm the subscription shows as **Active** in Partner Central
- Allow a few minutes after subscribing for entitlements to propagate

### BatchMeterUsage fails
- Verify the dimension name matches exactly what is defined in your listing
- Ensure your listing is in **Limited** or **Live** state (not Draft)
- Check the IAM role has `aws-marketplace:BatchMeterUsage` permission

### Concurrent Agreements not enabled
- Complete the Concurrent Agreements integration (see the [integration lab](https://catalog.workshops.aws/mpseller/en-US/saas/integration-for-concurrent-agreements))
- Opt in via Partner Central once integration is complete
- **Required for all new SaaS listings from June 1, 2026**

### EventBridge warning
- Configure EventBridge rules for `aws.agreement-marketplace` events in your account
- SNS continues to work for existing listings but EventBridge is required for new listings
- See [Managing SaaS subscription events with Amazon EventBridge](https://docs.aws.amazon.com/marketplace/latest/userguide/saas-eventbridge-integration.html)

---

## Step 5 — Score your listing effectiveness

Switch to the **Listing Effectiveness** tab to get an AI-powered score of your listing content.

1. Switch to the **Listing Effectiveness** tab
2. Enter your **Product ID** (the `prod-xxx` ID from Partner Central — found in the URL when viewing your listing)
3. Click **Score My Listing**

The scorer evaluates your listing across 15+ categories and provides:
- An overall score (0–100) with an AI-generated executive summary
- Per-category bar chart showing where you're strong and where to improve
- Specific recommendations with examples of what good looks like
- **✨ Suggest rewrite** buttons for title, description, highlights, long description, and keywords — powered by Amazon Bedrock

{{% notice tip %}}
Run the Listing Effectiveness scorer before submitting for MCO review. A well-optimised listing improves discoverability, conversion, and buyer confidence — listings with free trial + PAYG pricing show 3x higher conversion rates.
{{% /notice %}}

---

## Step 6 — Submit for MCO review

Once all integration tests pass:

1. Go to [AWS Partner Central](https://partnercentral.awspartner.com/partnercentral2/s/manage-products) and open your listing
2. Verify all listing details are complete — title, description, highlights, pricing, and support information
3. Click **Submit for review**
4. MCO will review your submission — typical turnaround is **3–5 business days**
5. You will receive an email notification when approved or if changes are required
6. Once approved, your listing status changes from **Limited** to **Live**

---

## Step 7 — Clean up

Delete the CloudFormation stack to remove all resources:

```bash
aws cloudformation delete-stack --stack-name mp-saas-tester
```

Or go to **CloudFormation → Stacks → mp-saas-tester → Delete**.
