# AWS Marketplace Seller Readiness Tool — API Reference

This document describes every AWS API call made by the tool, grouped by feature.

---

## Integration Tests

### Registration Page Check
**Type:** HTTP (not an AWS API)
| Detail | Value |
|--------|-------|
| Call | `GET {registration_page_url}?x-amzn-marketplace-token={token}` |
| Purpose | Verifies the seller's registration page is publicly accessible and accepts the marketplace token |
| Pass condition | HTTP status < 500 |
| Docs | [Registration page requirements](https://docs.aws.amazon.com/marketplace/latest/userguide/saas-integrate-registration.html) |

---

### ResolveCustomer
**Service:** `meteringmarketplace` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `resolve_customer(RegistrationToken=token)` |
| Purpose | Exchanges the buyer's registration token for customer identifiers |
| Returns | `CustomerIdentifier`, `CustomerAWSAccountId`, `ProductCode`, `LicenseArn` |
| Pass condition | API returns a valid `CustomerIdentifier` |
| IAM permission | `aws-marketplace:ResolveCustomer` |
| Docs | [ResolveCustomer API](https://docs.aws.amazon.com/marketplacemetering/latest/APIReference/API_ResolveCustomer.html) |

**Note:** Must be called from the seller account that owns the listing. Token expires after 60 minutes.

---

### GetEntitlements
**Service:** `marketplace-entitlement` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `get_entitlements(ProductCode, Filter={"CUSTOMER_IDENTIFIER": [customer_id]})` |
| Purpose | Confirms the buyer has an active entitlement for the product |
| Returns | List of active entitlements with dimension, value, and expiry |
| Pass condition | At least one active entitlement returned |
| IAM permission | `aws-marketplace:GetEntitlements` |
| Applicable to | Contract-based listings only (skipped for metering-only) |
| Docs | [GetEntitlements API](https://docs.aws.amazon.com/marketplaceentitlement/latest/APIReference/API_GetEntitlements.html) |

**Note:** Falls back to unfiltered call if filtered response is empty, then matches client-side by `CustomerIdentifier`.

---

### BatchMeterUsage
**Service:** `meteringmarketplace` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `batch_meter_usage(ProductCode, UsageRecords=[{CustomerAWSAccountId, Dimension, Quantity, Timestamp}])` |
| Purpose | Validates that usage records can be submitted for billing |
| Returns | `MeteringRecordId`, `Status` (Success / DuplicateRecord) |
| Pass condition | Status is `Success` or `DuplicateRecord` |
| IAM permission | `aws-marketplace:BatchMeterUsage` |
| Applicable to | Metering-based listings only |
| Docs | [BatchMeterUsage API](https://docs.aws.amazon.com/marketplacemetering/latest/APIReference/API_BatchMeterUsage.html) |

**Note:** `DuplicateRecord` is treated as a pass — it means metering is working but the same record was already submitted within the hour.

---

### Concurrent Agreements Check
**Service:** `marketplace-catalog` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)` |
| Purpose | Checks if Concurrent Agreements is enabled on the listing |
| Pass condition | Concurrent agreement configuration present in listing details |
| IAM permission | `aws-marketplace:DescribeEntity` |
| Required from | June 1, 2026 for all new SaaS listings |
| Docs | [Concurrent Agreements integration lab](https://catalog.workshops.aws/mpseller/en-US/saas/integration-for-concurrent-agreements) |

---

### EventBridge Integration Check
**Service:** `events` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `list_rules(EventBusName="default")` |
| Purpose | Checks if EventBridge rules exist for AWS Marketplace subscription events |
| Pass condition | At least one rule matching `aws.agreement-marketplace` source found |
| IAM permission | `events:ListRules` |
| Result if not found | Warning (not hard fail) — SNS still works for existing listings |
| Docs | [EventBridge integration](https://docs.aws.amazon.com/marketplace/latest/userguide/saas-eventbridge-integration.html) |

---

## Listing Type Detection

**Service:** `marketplace-catalog` (us-east-1)
| Detail | Value |
|--------|-------|
| Call 1 | `list_entities(Catalog="AWSMarketplace", EntityType="SaaSProduct")` |
| Call 2 | `describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)` |
| Purpose | Identifies the listing's pricing model from `Dimensions[].Types` |
| Detection logic | `ExternallyMetered` → Usage-Based; `Entitled` → Contract-Based; both → Contract with Consumption |
| IAM permission | `aws-marketplace:ListEntities`, `aws-marketplace:DescribeEntity` |

---

## Listing Effectiveness Scorer

### Fetch Listing Data
**Service:** `marketplace-catalog` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)` |
| Purpose | Retrieves full listing details for scoring (title, description, highlights, keywords, categories, media, pricing, support) |
| IAM permission | `aws-marketplace:DescribeEntity` |

---

### AI Quality Scoring
**Service:** `bedrock-runtime` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0")` |
| Purpose | Scores title, short description, and highlights 0–100 with specific improvement tips and examples |
| Input | Title, short description, highlights |
| Output | Score + tip + example per field |
| IAM permission | `bedrock:InvokeModel` |
| Fallback | Rule-based scoring used if Bedrock call fails |

---

### AI Executive Summary
**Service:** `bedrock-runtime` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0")` |
| Purpose | Generates a 3–4 sentence prioritised action summary based on all category scores |
| Input | All category scores and top recommendations |
| Output | Plain-English executive summary |
| IAM permission | `bedrock:InvokeModel` |

---

### AI Rewrite Suggestions
**Service:** `bedrock-runtime` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0")` |
| Purpose | Generates an improved rewrite for a specific listing field |
| Supported fields | Title, Short Description, Highlights, Long Description, Search Keywords |
| Input | Field name, current content, product context |
| Output | Rewritten field content ready to copy into Partner Central |
| IAM permission | `bedrock:InvokeModel` |
| Guard | Returns error if current content is empty or < 10 characters |

---

## IAM Permissions Summary

All permissions are granted to the Lambda execution role deployed by the CloudFormation template:

```json
{
  "Action": [
    "aws-marketplace:ResolveCustomer",
    "aws-marketplace:GetEntitlements",
    "aws-marketplace:MeterUsage",
    "aws-marketplace:BatchMeterUsage",
    "aws-marketplace:DescribeEntity",
    "aws-marketplace:ListEntities",
    "bedrock:InvokeModel",
    "events:ListRules",
    "s3:PutObject",
    "s3:GetObject"
  ],
  "Resource": "*"
}
```
