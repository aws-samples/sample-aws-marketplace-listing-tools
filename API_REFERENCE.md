# API Reference

This document describes every AWS API call made by the tool, grouped by feature.

---

## Integration Tests

### Registration Page Check
**Type:** HTTP (not an AWS API)
| Detail | Value |
|--------|-------|
| Call | `POST {registration_page_url}` with `x-amzn-marketplace-token` in form body |
| Purpose | Verifies the seller's registration page accepts POST requests with the marketplace token, matching the real Marketplace redirect flow |
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

### Error Handling Check
**Type:** HTTP (not an AWS API)
| Detail | Value |
|--------|-------|
| Call | `POST {registration_page_url}` with invalid token `test-invalid-token-00000` |
| Purpose | Verifies the registration page handles invalid tokens gracefully without crashing or exposing stack traces |
| Pass condition | HTTP status < 500 and no stack trace patterns detected |

---

### HTTPS Certificate Check
**Type:** SSL/TLS
| Detail | Value |
|--------|-------|
| Call | SSL handshake to registration page hostname |
| Purpose | Validates the HTTPS certificate is valid, trusted, and not expiring soon |
| Pass condition | Certificate is not expired, not self-signed, and not expiring within 30 days |

---

### FulfillmentUrl Match Check
**Service:** `marketplace-catalog` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)` |
| Purpose | Compares the provided registration URL with the FulfillmentUrl configured in the listing |
| Pass condition | URLs match after normalisation |
| IAM permission | `aws-marketplace:DescribeEntity` |

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
| Result if not found | Warning (not hard fail) |
| Docs | [EventBridge integration](https://docs.aws.amazon.com/marketplace/latest/userguide/saas-eventbridge-integration.html) |

---

### CloudTrail History Checks
**Service:** `cloudtrail` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `lookup_events(LookupAttributes=[{EventName: "ResolveCustomer"}])` |
| Purpose | Verifies the seller's application has been calling ResolveCustomer/BatchMeterUsage in the last 7 days |
| IAM permission | `cloudtrail:LookupEvents` |

---

## Listing Type Detection

**Service:** `marketplace-catalog` (us-east-1)
| Detail | Value |
|--------|-------|
| Call 1 | `list_entities(Catalog="AWSMarketplace", EntityType="SaaSProduct")` |
| Call 2 | `describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)` |
| Purpose | Identifies the listing's pricing model from `Dimensions[].Types` |
| Detection logic | `ExternallyMetered` = Usage-Based, `Entitled` = Contract-Based, both = Contract with Consumption |
| IAM permission | `aws-marketplace:ListEntities`, `aws-marketplace:DescribeEntity` |

---

## Listing Effectiveness Scorer

### Fetch Listing Data
**Service:** `marketplace-catalog` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)` |
| Purpose | Retrieves full listing details for scoring |
| IAM permission | `aws-marketplace:DescribeEntity` |

---

### AI Quality Scoring
**Service:** `bedrock-runtime` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0")` |
| Purpose | Scores title, short description, and highlights 0-100 against a structured rubric |
| IAM permission | `bedrock:InvokeModel` |
| Fallback | Rule-based scoring if Bedrock call fails |

---

### AI Executive Summary
**Service:** `bedrock-runtime` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0")` |
| Purpose | Generates a prioritised action summary based on all category scores |
| IAM permission | `bedrock:InvokeModel` |

---

### AI Rewrite Suggestions
**Service:** `bedrock-runtime` (us-east-1)
| Detail | Value |
|--------|-------|
| Call | `invoke_model(modelId="anthropic.claude-3-haiku-20240307-v1:0")` |
| Purpose | Generates improved rewrites for listing fields |
| Supported fields | Title, Short Description, Highlights, Long Description, Search Keywords |
| IAM permission | `bedrock:InvokeModel` |
