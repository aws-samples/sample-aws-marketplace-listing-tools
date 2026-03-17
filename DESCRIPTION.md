# AWS Marketplace SaaS Listing Tester — Product Description

## What it is

The AWS Marketplace SaaS Listing Tester is a self-service tool that helps sellers validate their SaaS listing integrations and listing quality before submitting for MCO (Marketplace Channel Operations) review. It is delivered as a lab within the AWS Marketplace Seller Workshop and deploys directly into the seller's own AWS account via a one-click CloudFormation template.

---

## The problem it solves

When a seller submits a SaaS listing for MCO review, the review process validates that all required technical integrations are working correctly — registration page, customer resolution, entitlements, metering, and subscription notifications. If any of these fail, MCO rejects the submission and the seller must fix the issue and resubmit, adding days or weeks to the time-to-live.

Common failure points include:
- Registration page not accessible or not accepting the marketplace token
- `ResolveCustomer` API not being called correctly after buyer redirect
- Metering dimensions not matching the listing configuration
- Missing EventBridge integration for subscription notifications
- Concurrent Agreements not enabled (required for new listings from June 1, 2026)

Sellers often don't discover these issues until MCO review, because there was no way to test the full integration end-to-end before submission.

---

## How it helps MCO

The tool replicates what MCO tests, allowing sellers to find and fix issues before they submit. This means:

- **Fewer failed submissions** — sellers arrive at MCO review with integrations already validated
- **Faster time-to-live** — less back-and-forth between sellers and MCO on technical issues
- **Reduced MCO workload** — MCO spends less time on basic integration failures and more time on substantive review
- **Better seller experience** — sellers have confidence their listing will pass before they submit

---

## What it tests

### Integration Tests
Runs against the seller's real Limited listing using actual AWS Marketplace APIs:

| Test | What it validates |
|------|------------------|
| Registration Page | Page is publicly accessible via HTTPS and accepts the marketplace token parameter |
| ResolveCustomer | Token exchange returns a valid customer identifier |
| GetEntitlements | Active entitlements exist for the subscribed customer (contract listings) |
| BatchMeterUsage | Usage records can be submitted with the correct dimension (metering listings) |
| Concurrent Agreements | Listing is opted in to support multiple purchases per account |
| EventBridge | Subscription lifecycle events are configured to route via EventBridge |

The listing type (Usage-Based, Contract-Based, Contract with Consumption) is auto-detected from the listing configuration so sellers don't need to know which tests apply to them.

### Listing Effectiveness Scorer
AI-powered analysis of listing content quality across 15+ categories, scored 0–100:

- **Discoverability** — title, keywords, highlights optimised for AWS Marketplace search rankings
- **Evaluation** — long description, screenshots/videos, G2/Peerspot reviews
- **Pricing** — free trial, PAYG pricing, contract pricing configured for maximum conversion
- **Procurement** — Vendor Insights, Standard Contract (SCMP), Quick Launch enabled

For each underperforming area, the tool provides:
- A specific recommendation with a concrete example of what good looks like
- An AI-generated rewrite suggestion (powered by Amazon Bedrock / Claude)
- A direct link to fix the item in AWS Partner Central

An AI-generated executive summary (also powered by Bedrock) gives sellers a prioritised plain-English action plan.

---

## How it works

The tool deploys a Lambda function and API Gateway into the seller's own AWS account. All API calls to AWS Marketplace are made from within the seller's account using their own IAM credentials — no credentials are shared or transmitted externally. The frontend is a single HTML page served from CloudFront.

The seller's workflow:
1. Subscribe to their own listing to generate a test token
2. Deploy the tool via Launch Stack in the workshop (one click, ~3 minutes)
3. Open the CloudFront URL from the CloudFormation outputs
4. Enter their product code and registration redirect URL
5. Run integration tests — each step shows pass/fail with a plain-English explanation
6. Switch to the Listing Effectiveness tab, enter their Product ID, and score their listing
7. Use AI rewrite suggestions to improve underperforming fields
8. Re-score to confirm improvements before submitting for MCO review
