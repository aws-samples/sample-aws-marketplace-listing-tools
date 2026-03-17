# Code Walkthrough

A step-by-step breakdown of how the tool works.

---

## Architecture Overview

```
Browser (index.html)
    │
    │  HTTP POST /test
    ▼
API Gateway (HTTP API)
    │
    ▼
Lambda (handler.py)
    │
    ├── marketplace-catalog  (DescribeEntity, ListEntities)
    ├── meteringmarketplace  (ResolveCustomer, BatchMeterUsage)
    ├── marketplace-entitlement (GetEntitlements)
    ├── bedrock-runtime      (Claude 3 Haiku — scoring + rewrites)
    └── events               (ListRules — EventBridge check)
```

All API calls are made from the Lambda running in the **seller's own AWS account**, so credentials never leave their environment.

---

## Frontend (index.html)

Single HTML file, no build step, no dependencies.

### Tab switching
`switchTab(name)` toggles `.active` class on tab buttons and content divs.

### Integration Tests tab

**Auto-detect listing type** (`detectListingType`)
- Triggered `onblur` when seller tabs out of the Product Code field
- Calls `detect_listing_type` action on the Lambda
- Lambda calls `ListEntities` to find the listing, then `DescribeEntity` to read the `Dimensions[].Types` field
- `ExternallyMetered` → metering, `Entitled` → contract, both → contract with consumption
- Updates the listing type dropdown and shows/hides metering fields
- Also pre-fills the Product ID field in the Listing Effectiveness tab

**Token extraction** (`extractToken`)
- Runs `oninput` on the redirect URL field
- Parses the URL with `new URL()` and extracts `x-amzn-marketplace-token`
- Shows a preview confirming the token was found

**Running tests** (`runTests`)
- Builds the step list based on listing type (entitlement/metering/both)
- Always appends `concurrent_agreements` and `eventbridge` steps
- Renders all steps as "pending" immediately so the seller sees what's coming
- Loops through steps sequentially, updating each to "running" then "pass/fail/warning/skipped"
- After all steps complete, inserts a summary card at the top of results

**Summary card**
- Counts pass/fail/warning/skipped
- If all pass: shows go-live steps with links to Partner Central
- If failures: lists each failed step with a plain-English explanation of what to fix
- Warnings (EventBridge) don't count as failures

### Listing Effectiveness tab

**Scoring** (`scoreListing`)
- Calls `score_listing` action, stores result in `window._lastScoreResult`
- Calls `renderScoreResults` to display

**Rendering results** (`renderScoreResults`)
- Reads `localStorage` for previously completed recommendations (checkboxes)
- Renders score circle, AI summary paragraph, toolbar, bar chart, recommendations
- Each recommendation shows: category, tip, example, optional rewrite button, AMMP link, checkbox

**Rewrite suggestions** (`rewriteField`)
- Calls `rewrite_field` action with the field name and current content
- Displays the AI-generated rewrite with a Copy button

**Export/copy** (`exportReport`, `copyReport`)
- Formats scores + summary + recommendations as plain text
- `exportReport` creates a Blob and triggers a download
- `copyReport` uses `navigator.clipboard.writeText`

**Re-score** (`rescoreListing`)
- Re-calls `score_listing` and re-renders — shows updated scores after seller makes changes

---

## Backend (handler.py)

Single Lambda function. Routes requests by `action` field in the POST body.

### `check_registration_page`
- Constructs the test URL: `{registration_page_url}?x-amzn-marketplace-token={token}`
- Makes a GET request with `requests` library (10s timeout, follows redirects)
- Returns pass if HTTP status < 500, with the final URL and status code

### `resolve_customer`
- Calls `meteringmarketplace.resolve_customer(RegistrationToken=token)`
- Returns the `CustomerIdentifier` and `ProductCode` on success
- This is the most critical MCO check — must succeed for the listing to go live

### `get_entitlements`
- Skipped automatically for metering-only listings
- Calls `marketplace-entitlement.get_entitlements` with `CUSTOMER_IDENTIFIER` filter
- If empty, retries without filter and matches client-side (handles contract listings)
- Returns list of active entitlements with dimension, value, expiry

### `meter_usage`
- Calls `meteringmarketplace.batch_meter_usage` with a single usage record
- `DuplicateRecord` status is treated as a pass — means metering works, just can't submit the same record twice in an hour
- Returns the metering record ID on success

### `check_concurrent_agreements`
- Calls `marketplace-catalog.describe_entity` for the listing
- Checks the Details JSON for concurrent agreement configuration
- Returns pass/fail with a note about the June 1, 2026 deadline if not enabled

### `check_eventbridge`
- Calls `events.list_rules` on the default event bus
- Filters for rules matching `aws.agreement-marketplace` source
- Returns warning (not hard fail) if no rules found — SNS still works for existing listings

### `detect_listing_type`
- Calls `marketplace-catalog.list_entities` to get all SaaS products in the account
- For each entity, calls `describe_entity` and checks `Dimensions[].Types`
- `ExternallyMetered` = metering, `Entitled` = contract, both = contract with consumption
- Returns the listing type and entity ID

### `score_listing`
**Step 1 — Fetch listing data**
- Calls `marketplace-catalog.describe_entity` with the Product ID
- Parses the Details JSON (handles both string and dict formats)

**Step 2 — Rule-based scoring**
Scores each field 0-100:
- Title: title case, length, has descriptive words
- Short Description: length ≤350, doesn't start with "We/Our/I"
- Highlights: count and length of each bullet
- Keywords: count (max 3)
- Categories: present or not
- Media: screenshots/videos present
- Support: support description present
- Search Keywords, Title SEO, Reviews, Long Description, Free Trial, PAYG, Contract, Vendor Insights, SCMP, Quick Launch

**Step 3 — AI scoring (Bedrock)**
- Sends title, short description, and highlights to Claude 3 Haiku
- Prompt instructs Claude to score 0-100 and provide a tip + example for each
- Overrides the rule-based scores for these three fields
- Falls back to rule-based scores if Bedrock call fails

**Step 4 — Sort and summarise**
- Sorts tips by score ascending (worst first)
- Sends all scores and top tips to Claude for an executive summary paragraph
- Returns scores, tips, summary, and raw field values for rewrite context

### `rewrite_field`
- Accepts field name (`title`, `description`, `highlights`, `long_description`, `keywords`) and current content
- Returns error if content is empty or < 10 chars
- Sends field-specific prompt to Claude 3 Haiku
- Returns the rewritten content as plain text

---

## CloudFormation (template.yaml)

Creates:
- **IAM Role** — Lambda execution role with permissions for Marketplace APIs, Bedrock, and EventBridge
- **Lambda Function** — Python 3.12, 60s timeout
- **API Gateway** — HTTP API with CORS enabled for all origins
- **Integration + Route** — POST /test → Lambda
- **Stage** — $default with auto-deploy

---

## Build process (build.sh)

1. `pip3 install -r requirements.txt -t package/` — installs `requests` into a local directory
2. Copies `handler.py` into the package directory
3. Zips everything into `function.zip`
4. `aws cloudformation deploy` — creates/updates the stack
5. `aws lambda update-function-code` — uploads the zip directly to the function
6. Prints the API endpoint from CloudFormation outputs

---

## Publish process (publish.sh)

For workshop distribution:
1. Uploads `function.zip`, `template.yaml`, and `index.html` to a team-owned S3 bucket
2. Patches the Launch Stack URL into the workshop markdown
3. Prints the Launch Stack URL for embedding in the workshop lab page
