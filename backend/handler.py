import json
import boto3
import requests
from botocore.exceptions import ClientError

def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    action = body.get("action")

    handlers = {
        "resolve_customer": resolve_customer,
        "get_entitlements": get_entitlements,
        "meter_usage": meter_usage,
        "check_registration_page": check_registration_page,
        "score_listing": score_listing,
        "rewrite_field": rewrite_field,
        "detect_listing_type": detect_listing_type,
        "check_concurrent_agreements": check_concurrent_agreements,
        "check_eventbridge": check_eventbridge,
    }

    if action not in handlers:
        return respond(400, {"error": f"Unknown action: {action}"})

    try:
        result = handlers[action](body)
        return respond(200, result)
    except ClientError as e:
        return respond(200, {"pass": False, "error": e.response["Error"]["Message"]})
    except Exception as e:
        return respond(200, {"pass": False, "error": str(e)})


def resolve_customer(body):
    token = body.get("registration_token")
    if not token:
        return {"pass": False, "error": "registration_token is required"}

    mp = boto3.client("meteringmarketplace", region_name="us-east-1")
    resp = mp.resolve_customer(RegistrationToken=token)
    return {
        "pass": True,
        "customer_identifier": resp.get("CustomerIdentifier"),
        "customer_aws_account_id": resp.get("CustomerAWSAccountId"),
        "product_code": resp.get("ProductCode"),
        "license_arn": resp.get("LicenseArn"),
    }


def get_entitlements(body):
    product_code = body.get("product_code")
    customer_identifier = body.get("customer_identifier")
    listing_type = body.get("listing_type", "entitlement")  # entitlement | metering | both
    if not product_code or not customer_identifier:
        return {"pass": False, "error": "product_code and customer_identifier are required"}

    client = boto3.client("marketplace-entitlement", region_name="us-east-1")

    # For metering-only listings, entitlements are not applicable
    if listing_type == "metering":
        return {
            "pass": True,
            "skipped": True,
            "note": "Entitlement check not applicable for metering-only listings",
            "entitlements": [],
        }

    try:
        # First attempt: filter by CUSTOMER_IDENTIFIER
        resp1 = client.get_entitlements(
            ProductCode=product_code,
            Filter={"CUSTOMER_IDENTIFIER": [customer_identifier]},
        )
        entitlements = resp1.get("Entitlements", [])

        # Second attempt: no filter, match client-side
        resp2 = None
        all_entitlements = []
        if not entitlements:
            resp2 = client.get_entitlements(ProductCode=product_code)
            all_entitlements = resp2.get("Entitlements", [])
            entitlements = [e for e in all_entitlements if e.get("CustomerIdentifier") == customer_identifier]

        return {
            "pass": len(entitlements) > 0,
            "debug": {
                "customer_identifier_used": customer_identifier,
                "product_code_used": product_code,
                "filtered_response_count": len(resp1.get("Entitlements", [])),
                "unfiltered_response_count": len(all_entitlements) if resp2 else "not attempted",
                "unfiltered_customer_identifiers": list({e.get("CustomerIdentifier") for e in all_entitlements}) if resp2 else [],
            },
            "entitlements": [
                {
                    "dimension": e.get("Dimension"),
                    "value": (
                        e.get("Value", {}).get("IntegerValue") or
                        e.get("Value", {}).get("DoubleValue") or
                        e.get("Value", {}).get("BooleanValue")
                    ),
                    "expiration_date": str(e.get("ExpirationDate", "")),
                }
                for e in entitlements
            ],
            "error": None if entitlements else "No active entitlements found",
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def meter_usage(body):
    product_code = body.get("product_code")
    customer_identifier = body.get("customer_identifier")
    customer_aws_account_id = body.get("customer_aws_account_id")
    dimension = body.get("dimension")
    quantity = int(body.get("quantity", 1))

    if not all([product_code, dimension]):
        return {"pass": False, "error": "product_code and dimension are required"}

    import datetime
    mp = boto3.client("meteringmarketplace", region_name="us-east-1")

    usage_record = {
        "Timestamp": datetime.datetime.utcnow(),
        "Dimension": dimension,
        "Quantity": quantity,
    }
    # CustomerAWSAccountId is preferred; fall back to CustomerIdentifier
    if customer_aws_account_id:
        usage_record["CustomerAWSAccountId"] = customer_aws_account_id
    elif customer_identifier:
        usage_record["CustomerIdentifier"] = customer_identifier
    else:
        return {"pass": False, "error": "customer_aws_account_id or customer_identifier is required"}

    resp = mp.batch_meter_usage(
        ProductCode=product_code,
        UsageRecords=[usage_record],
    )
    results = resp.get("Results", [])
    unprocessed = resp.get("UnprocessedRecords", [])

    if unprocessed:
        return {"pass": False, "error": f"Record was not processed: {unprocessed[0].get('MeteringRecordId', 'unknown')}"}

    status = results[0].get("Status") if results else None
    if status == "DuplicateRecord":
        return {"pass": True, "status": status, "note": "Metering integration is working correctly. DuplicateRecord indicates a record was already submitted for this hour — this is expected when testing more than once."}
    return {
        "pass": status == "Success",
        "status": status,
        "metering_record_id": results[0].get("MeteringRecordId") if results else None,
        "note": "BatchMeterUsage submitted successfully" if status == "Success" else f"Unexpected status: {status}",
        "error": None if status == "Success" else f"Status: {status}",
    }


def check_registration_page(body):
    url = body.get("registration_page_url")
    token = body.get("registration_token", "test-token-12345")
    if not url:
        return {"pass": False, "error": "registration_page_url is required"}

    test_url = f"{url}?x-amzn-marketplace-token={token}"
    try:
        resp = requests.get(test_url, timeout=10, allow_redirects=True)
        return {
            "pass": resp.status_code < 500,
            "status_code": resp.status_code,
            "final_url": resp.url,
            "note": "Page loaded successfully" if resp.status_code < 400 else f"Page returned {resp.status_code}",
        }
    except requests.exceptions.Timeout:
        return {"pass": False, "error": "Registration page timed out after 10 seconds"}
    except requests.exceptions.ConnectionError as e:
        return {"pass": False, "error": f"Could not connect to registration page: {str(e)}"}


def check_concurrent_agreements(body):
    entity_id = body.get("entity_id")
    if not entity_id:
        return {"pass": False, "error": "entity_id is required"}
    try:
        mp = boto3.client("marketplace-catalog", region_name="us-east-1")
        resp = mp.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
        raw = resp.get("Details", "{}")
        details = json.loads(raw) if isinstance(raw, str) else raw
        details_str = json.dumps(details).lower()
        enabled = "concurrentagreement" in details_str or "concurrent_agreement" in details_str or details.get("ConcurrentAgreements", {}).get("Enabled")
        return {
            "pass": enabled,
            "enabled": enabled,
            "note": "Concurrent Agreements is enabled on this listing." if enabled
                    else "Concurrent Agreements is not enabled. Required for all new SaaS products from June 1, 2026. Complete the integration then opt in via Partner Central.",
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def check_eventbridge(body):
    try:
        eb = boto3.client("events", region_name="us-east-1")
        rules = eb.list_rules(EventBusName="default").get("Rules", [])
        mp_rules = [r for r in rules if "agreement-marketplace" in json.dumps(r.get("EventPattern", "")).lower()
                    or "marketplace" in r.get("Name", "").lower()]
        return {
            "pass": len(mp_rules) > 0,
            "rules_found": len(mp_rules),
            "rule_names": [r["Name"] for r in mp_rules],
            "note": f"Found {len(mp_rules)} EventBridge rule(s) for AWS Marketplace events." if mp_rules
                    else "No EventBridge rules found for AWS Marketplace events (aws.agreement-marketplace). SNS is being replaced by EventBridge — set up rules to receive subscription notifications.",
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def detect_listing_type(body):
    product_code = body.get("product_code")
    if not product_code:
        return {"pass": False, "error": "product_code is required"}

    try:
        mp = boto3.client("marketplace-catalog", region_name="us-east-1")
        # List all SaaS products and find the one matching the product code
        paginator = mp.get_paginator("list_entities")
        entity_id = None
        for page in paginator.paginate(Catalog="AWSMarketplace", EntityType="SaaSProduct"):
            for entity in page.get("EntitySummaryList", []):
                eid = entity.get("EntityId", "")
                # Check if product code appears in entity ARN or fetch details
                if product_code in eid:
                    entity_id = eid
                    break
            if entity_id:
                break

        # If not found by ID match, fetch details for each and match product code
        if not entity_id:
            for page in paginator.paginate(Catalog="AWSMarketplace", EntityType="SaaSProduct"):
                for entity in page.get("EntitySummaryList", []):
                    eid = entity.get("EntityId", "")
                    try:
                        detail_resp = mp.describe_entity(Catalog="AWSMarketplace", EntityId=eid)
                        raw = detail_resp.get("Details", "{}")
                        details = json.loads(raw) if isinstance(raw, str) else raw
                        if product_code in json.dumps(details):
                            entity_id = eid
                            break
                    except Exception:
                        continue
                if entity_id:
                    break

        if not entity_id:
            return {"pass": False, "error": "Could not find a listing matching this product code in your account."}

        detail_resp = mp.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
        raw = detail_resp.get("Details", "{}")
        details = json.loads(raw) if isinstance(raw, str) else raw

        pricing_str = json.dumps(details).lower()
        dimensions = details.get("Dimensions", [])
        has_metering = any("externallymetered" in json.dumps(d.get("Types", [])).lower() for d in dimensions)
        has_entitlement = any("entitled" in json.dumps(d.get("Types", [])).lower() for d in dimensions)

        # Fallback to string matching if dimensions don't have Types
        if not has_metering and not has_entitlement:
            has_metering = "externallymetered" in pricing_str or "metered" in pricing_str
            has_entitlement = "entitled" in pricing_str or "subscription" in pricing_str

        if has_metering and has_entitlement:
            listing_type = "both"
        elif has_metering:
            listing_type = "metering"
        else:
            listing_type = "entitlement"

        return {
            "pass": True,
            "listing_type": listing_type,
            "entity_id": entity_id,
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def rewrite_field(body):
    field = body.get("field")  # title | description | highlights
    current = body.get("current", "")
    context = body.get("context", "")  # other listing fields for context

    GUIDELINES = """Official AWS Marketplace guidelines:
- Title: Use title case, buyer must identify product by name alone, use brand name, avoid hyperbole, max ~80 chars
- Short Description: Max 350 characters, avoid unnecessary capitalisation/punctuation, no redirects to other platforms, benefit-focused, no hyperbole
- Highlights: Up to 3 bullet points, describe primary selling points, specific and benefit-driven, avoid generic phrases
- Keywords: Up to 3 keywords/phrases, max 250 chars total, use buyer vocabulary, don't duplicate title
- Long Description: Include features, benefits, usage, specific use cases, integration ecosystem, customer outcomes
PLG best practices: Free trial + PAYG = 3x higher conversion; 30% of traffic from search engines; listings with media have 3x higher pricing engagement"""

    prompts = {
        "title": f"""Rewrite this AWS Marketplace product listing title to comply with official guidelines.

{GUIDELINES}

Current title: {current}
Product context: {context}

Requirements:
- Use title case (capitalise first letter of each important word)
- Buyer must be able to identify the product by name alone
- Use the brand or manufacturer name
- Avoid hyperbole and generic words like "Solution", "Platform", "Product", "Test", "AnyCompany"
- Maximum 80 characters

Respond with ONLY the rewritten title, nothing else.""",

        "description": f"""Rewrite this AWS Marketplace short description to comply with official guidelines.

{GUIDELINES}

Current description: {current}
Product context: {context}

Requirements:
- Maximum 350 characters
- Avoid unnecessary capitalisation and punctuation
- Do not redirect to other platforms or include upsell language
- Lead with the problem solved or value delivered (not "We are..." or "Our product...")
- No hyperbole — include only critical, useful information

Respond with ONLY the rewritten description, nothing else.""",

        "highlights": f"""Rewrite these AWS Marketplace product highlights to comply with official guidelines.

{GUIDELINES}

Current highlights: {current}
Product context: {context}

Requirements:
- Provide exactly 3 bullet points
- Each highlight must briefly describe a primary selling point
- Be specific with metrics or concrete outcomes
- Avoid generic phrases like "Easy to use", "Scalable", "Reliable", "Powerful"
- Maximum 150 characters each

Respond with ONLY 3 bullet points, one per line, no numbering or dashes.""",

        "long_description": f"""Rewrite this AWS Marketplace long description to comply with official guidelines.

{GUIDELINES}

Current description: {current}
Product context: {context}

Requirements:
- Lead with the problem solved or value delivered
- Include: key use cases, target personas, integration ecosystem, compliance certifications, customer outcomes with metrics
- Structure clearly: Overview → Use Cases → Key Features → Why Choose Us
- Minimum 300 characters
- Use plain text, no markdown or HTML
- Do not redirect to other platforms or include upsell language

Respond with ONLY the rewritten long description, nothing else.""",

        "keywords": f"""Suggest 3 search keywords for this AWS Marketplace product listing, following official guidelines.

{GUIDELINES}

Product context: {context}
Current keywords: {current}

Requirements:
- Use terms buyers actually search for — not the product or company name (already indexed separately)
- Be specific to the product category and use case
- Choose from buyer vocabulary
- Each keyword can be a single word or short phrase (max 3 words)
- Total must be under 250 characters combined

Respond with ONLY 3 keywords, one per line, no numbering or explanation.""",
    }

    if field not in prompts:
        return {"pass": False, "error": f"Unknown field: {field}"}

    # Require enough context to generate a meaningful rewrite
    if not current or len(current.strip()) < 10:
        return {"pass": False, "error": f"Not enough content to generate a rewrite — your {field.replace('_', ' ')} appears to be empty or too short. Add some content first, then re-score to get suggestions."}

    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 512,
                "messages": [{"role": "user", "content": prompts[field]}]
            }),
            contentType="application/json",
            accept="application/json",
        )
        rewrite = json.loads(resp["body"].read())["content"][0]["text"].strip()
        return {"pass": True, "rewrite": rewrite}
    except Exception as e:
        return {"pass": False, "error": str(e)}


def score_listing(body):
    entity_id = body.get("entity_id")
    if not entity_id:
        return {"pass": False, "error": "entity_id is required"}

    mp = boto3.client("marketplace-catalog", region_name="us-east-1")
    resp = mp.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
    raw = resp.get("Details", "{}")
    details = json.loads(raw) if isinstance(raw, str) else raw

    # Log the top-level keys to help debug field names
    top_keys = list(details.keys())

    scores = []
    tips = []

    def get_nested(d, *keys):
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k, "")
            else:
                return ""
        return d or ""

    # ── Title ────────────────────────────────────────────────────────────────
    title = (get_nested(details, "Description", "ProductTitle") or
             get_nested(details, "Description", "Title") or
             get_nested(details, "ProductTitle") or
             get_nested(details, "Name") or "")
    title_score = 0
    if title:
        title_score += 30
        if len(title) >= 10: title_score += 20
        if title[0].isupper(): title_score += 20
        words = title.split()
        if sum(1 for w in words if w[0].isupper()) >= len(words) * 0.6: title_score += 30
        if title_score < 70:
            tips.append({"category": "Title", "tip": "Use title case and ensure the title clearly identifies what your product does.", "example": "✓ Good: \"Datadog — Cloud Monitoring & Security Platform\"\n✗ Avoid: \"Our Amazing Software v2.0\" or \"datadog monitoring tool\""})
    else:
        tips.append({"category": "Title", "tip": "Product title not found.", "example": "✓ Good: \"Splunk Enterprise Security — SIEM & Threat Detection\""})
    scores.append({"category": "Title", "score": title_score})

    # ── Short Description ────────────────────────────────────────────────────
    desc = (get_nested(details, "Description", "ShortDescription") or
            get_nested(details, "Description", "LongDescription") or
            get_nested(details, "ShortDescription") or "")
    desc_score = 0
    if desc:
        desc_score += 30
        if len(desc) >= 100: desc_score += 20
        if len(desc) <= 350: desc_score += 20
        if not str(desc).startswith(("We ", "Our ", "I ")): desc_score += 30
        if len(desc) > 350:
            tips.append({"category": "Short Description", "tip": f"Description is {len(desc)} chars — trim to 350 or less.", "example": "✓ Keep it under 350 characters and lead with the problem solved, not your company name."})
        elif desc_score < 80:
            tips.append({"category": "Short Description", "tip": "Lead with the problem you solve, not your company name. Focus on buyer benefits.", "example": "✓ Good: \"Automatically detect and respond to cloud threats across AWS, Azure, and GCP — no agents required.\"\n✗ Avoid: \"We are a leading cybersecurity company offering our award-winning platform.\""})
    else:
        tips.append({"category": "Short Description", "tip": "Short description is missing — this is the first thing buyers read.", "example": "✓ Good: \"Automatically detect and respond to cloud threats across AWS, Azure, and GCP — no agents required.\""})
    scores.append({"category": "Short Description", "score": desc_score})

    # ── Highlights ───────────────────────────────────────────────────────────
    highlights = (details.get("Description", {}).get("Highlights") or
                  details.get("Highlights") or [])
    hl_score = 0
    if len(highlights) >= 3:
        hl_score = 70
        if all(len(str(h)) > 30 for h in highlights): hl_score = 100
        if hl_score < 100:
            tips.append({"category": "Highlights", "tip": "Make each highlight specific and benefit-driven. Highlights are a key search ranking field.", "example": "✓ Good: \"Reduce MTTR by 60% with AI-powered root cause analysis across your entire stack\"\n✗ Avoid: \"Easy to use\" or \"Scalable and reliable solution\""})
    elif len(highlights) > 0:
        hl_score = 30
        tips.append({"category": "Highlights", "tip": f"You have {len(highlights)} of 3 highlights. Add all 3 — highlights are a key search ranking field.", "example": "✓ Each highlight should cover a distinct benefit: cost savings, time savings, or risk reduction with a specific metric."})
    else:
        tips.append({"category": "Highlights", "tip": "No highlights found. Add 3 bullet points — highlights are one of 6 key AWS Marketplace search ranking fields.", "example": "✓ \"Cut infrastructure costs by up to 40% with automated rightsizing\"\n✓ \"Deploy in under 5 minutes with one-click Quick Launch\"\n✓ \"SOC 2 Type II certified — meet compliance requirements out of the box\""})
    scores.append({"category": "Highlights", "score": hl_score})

    # ── AI quality assessment (title, description, highlights) ───────────────
    ai_scores = {}
    ai_feedback = {}

    AWS_MP_GUIDELINES = """
AWS MARKETPLACE OFFICIAL LISTING GUIDELINES:

TITLE GUIDELINES:
- Use title case (capitalise first letter of each important word)
- Ensure a buyer can identify the product by the name alone
- Use the name of the brand or manufacturer
- Avoid descriptive data or hyperbole
- GovCloud products must include "GovCloud" in the title
- Supported characters: ASCII 0-126, ©, ®, ™, currency symbols

DESCRIPTION GUIDELINES (max 350 characters):
- Avoid unnecessary capitalisation
- Avoid unnecessary punctuation marks
- Do not include redirect information to other platforms
- Check spelling and grammar
- Include only critical, useful information
- Avoid descriptive data and hyperbole
- Must not contain language redirecting users to other cloud platforms or upsell services

HIGHLIGHTS GUIDELINES (up to 3 bullet points):
- Briefly describe the product's primary selling points
- Each highlight should be specific and benefit-driven
- Avoid generic phrases

SEARCH RANKING FIELDS (in order of importance):
Product title, Vendor name, Keywords, Highlights, Short description, Long description

PLG BEST PRACTICES (from AWS Marketplace field data):
- 30% of AWS Marketplace traffic comes from search engines
- 60% of search queries result in a click on the first page of results
- 95% of SEO traffic lands on product listings
- 20% of customers engage with videos on listing pages
- Customers value specific use cases — engagement with pricing is 3x higher on listings with rich media
- 25% of customers say free trials are essential before purchase
- Free trial to PAYG conversion is 3x higher than free trial to contract only
- Customers spend 3-6 months researching and browse 3-5 listing pages before buying
- Vendor Insights reduces procurement delays of 8-10 weeks caused by security reviews
- SCMP can accelerate sales cycles by up to 80% vs custom EULA
"""

    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        prompt = f"""You are an AWS Marketplace listing quality evaluator. Score each field against the official AWS Marketplace guidelines and PLG best practices provided below.

{AWS_MP_GUIDELINES}

Now evaluate this listing:

Product Title: {title or "(empty)"}
Short Description: {desc or "(empty)"}
Highlights: {json.dumps(highlights) if highlights else "(empty)"}

Score each field 0-100 based on how well it meets the official guidelines above. Provide one specific improvement tip and a concrete example for each.

Respond ONLY with valid JSON in this exact format:
{{
  "title": {{"score": 0-100, "tip": "...", "example": "..."}},
  "description": {{"score": 0-100, "tip": "...", "example": "..."}},
  "highlights": {{"score": 0-100, "tip": "...", "example": "..."}}
}}

Scoring criteria:
- Title: Does it follow AWS title case guidelines? Can a buyer identify the product by name alone? Is it specific and searchable? Penalise generic words like "Solution", "Platform", "Product", "Test", "AnyCompany".
- Description: Does it meet the 350 character limit? Does it avoid unnecessary capitalisation and hyperbole? Does it lead with buyer value rather than company self-promotion? Does it avoid redirecting to other platforms?
- Highlights: Are all 3 present? Are they specific with metrics or concrete outcomes? Do they describe primary selling points? Penalise generic phrases like "Easy to use", "Scalable", "Reliable"."""

        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            }),
            contentType="application/json",
            accept="application/json",
        )
        result_text = json.loads(resp["body"].read())["content"][0]["text"]
        ai_result = json.loads(result_text)
        for field in ["title", "description", "highlights"]:
            ai_scores[field] = ai_result[field]["score"]
            ai_feedback[field] = {"tip": ai_result[field]["tip"], "example": ai_result[field]["example"]}
    except Exception as e:
        ai_scores = {"title": title_score, "description": desc_score, "highlights": hl_score}
        ai_feedback = {}

    # Override rule-based scores with AI scores and replace tips
    for s in scores:
        if s["category"] == "Title": s["score"] = ai_scores.get("title", s["score"])
        if s["category"] == "Short Description": s["score"] = ai_scores.get("description", s["score"])
        if s["category"] == "Highlights": s["score"] = ai_scores.get("highlights", s["score"])
    tips[:] = [t for t in tips if t["category"] not in ("Title", "Short Description", "Highlights")]
    for field, label in [("title", "Title"), ("description", "Short Description"), ("highlights", "Highlights")]:
        if ai_scores.get(field, 100) < 90 and field in ai_feedback:
            tips.insert(0, {"category": label, "tip": ai_feedback[field]["tip"], "example": ai_feedback[field]["example"]})

    # ── Keywords ─────────────────────────────────────────────────────────────
    keywords = (details.get("Description", {}).get("SearchKeywords") or
                details.get("SearchKeywords") or
                details.get("Keywords") or [])
    kw_score = 0
    if len(keywords) >= 3: kw_score = 100
    elif len(keywords) > 0: kw_score = 50
    # tip handled in PLG Discovery section below

    # ── Categories ───────────────────────────────────────────────────────────
    categories = (details.get("Description", {}).get("Categories") or
                  details.get("Categories") or [])
    cat_score = 100 if categories else 0
    if not categories:
        tips.append({"category": "Categories", "tip": "No categories selected. Choose up to 3 relevant categories."})
    scores.append({"category": "Categories", "score": cat_score})

    # ── Media ─────────────────────────────────────────────────────────────────
    media = (details.get("Description", {}).get("AdditionalResources") or
             details.get("AdditionalResources") or
             details.get("Videos") or
             details.get("Screenshots") or [])
    media_score = 100 if media else 0
    if not media:
        tips.append({"category": "Media / Videos", "tip": "No screenshots or videos found. 20% of customers engage with videos on listing pages, and customers value specific use cases. Add demo videos and screenshots — engagement with pricing by subscribers is 3x higher on listings with rich media."})
    scores.append({"category": "Media / Videos", "score": media_score})

    # ── Support ───────────────────────────────────────────────────────────────
    support = (get_nested(details, "SupportInformation", "Short Description") or
               get_nested(details, "Description", "SupportDescription") or
               get_nested(details, "SupportDescription") or "")
    support_score = 100 if support else 0
    if not support:
        tips.append({"category": "Support", "tip": "No support information found. Add a support URL or email."})
    scores.append({"category": "Support", "score": support_score})

    # ── PLG: Discovery ────────────────────────────────────────────────────────
    if not (keywords and len(keywords) >= 3):
        tips.append({"category": "Search Keywords", "tip": "Add all 3 search keywords using buyer-vocabulary terms — 30% of Marketplace traffic comes from search engines and the majority of clicks go to the first 5 results.", "example": "✓ Good: \"cloud monitoring\", \"infrastructure observability\", \"APM tool\"\n✗ Avoid: your product name or company name (already indexed separately)"})
    scores.append({"category": "Search Keywords", "score": 100 if keywords and len(keywords) >= 3 else (50 if keywords else 0)})

    title_seo_score = 0
    if title and len(title.split()) >= 3: title_seo_score = 100
    else:
        title_seo_score = 50 if title else 0
        tips.append({"category": "Title SEO", "tip": "Optimise your title with searchable terms buyers use — title is one of 6 key search ranking fields on AWS Marketplace.", "example": "✓ Good: \"Datadog — Cloud Monitoring & Security Platform\"\n✗ Avoid: \"Datadog\" alone or \"Our Monitoring Tool\""})
    scores.append({"category": "Title SEO", "score": title_seo_score})

    # ── PLG: Evaluation ───────────────────────────────────────────────────────
    reviews = details.get("Reviews") or details.get("ThirdPartyContent")
    review_score = 100 if reviews else 0
    if not reviews:
        tips.append({"category": "Reviews (G2 / Peerspot)", "tip": "Build your G2 and Peerspot profiles — AWS Marketplace automatically ingests reviews from these platforms. Customers spend 3–6 months researching and browse 3–5 listings before buying.", "example": "✓ Action: Create or claim your product profile at g2.com and peerspot.com, then ask existing customers to leave reviews. AWS Marketplace will automatically display them on your listing."})
    scores.append({"category": "Reviews (G2 / Peerspot)", "score": review_score})

    long_desc = (get_nested(details, "Description", "LongDescription") or
                 get_nested(details, "LongDescription") or "")
    long_desc_score = 100 if len(long_desc) >= 300 else (50 if long_desc else 0)
    if len(long_desc) < 300:
        tips.append({"category": "Long Description", "tip": "Expand your long description with specific use cases and features — customers use generative AI-powered comparisons to evaluate listings, so detailed content wins.", "example": "✓ Include: key use cases, target personas, integration ecosystem, compliance certifications, and customer outcomes with metrics.\n✓ Structure with clear sections: Overview → Use Cases → Key Features → Why Choose Us"})
    scores.append({"category": "Long Description", "score": long_desc_score})

    # ── PLG: Pricing ──────────────────────────────────────────────────────────
    pricing = (details.get("Versions", [{}])[0].get("DeliveryOptions", []) if details.get("Versions") else
               details.get("Dimensions", []) or details.get("PricingDimensions", []))
    pricing_str = json.dumps(pricing).lower()
    has_free_trial = "trial" in pricing_str or details.get("FreeTrialTerms")
    has_payg = "payg" in pricing_str or "pay" in pricing_str or "usage" in pricing_str
    has_contract = "contract" in pricing_str or "annual" in pricing_str

    if not has_free_trial:
        tips.append({"category": "Free Trial", "tip": "Add a free trial — 25% of customers say free trials are essential before purchase, and free trial to PAYG conversion is 3x higher than free trial to contract only.", "example": "✓ Set a 14 or 30-day free trial on your listing. Couple it with PAYG pricing for the highest conversion rate."})
    scores.append({"category": "Free Trial", "score": 100 if has_free_trial else 0})

    if not has_payg:
        tips.append({"category": "Pay-As-You-Go Pricing", "tip": "Add PAYG pricing alongside contracts — coupling free trial with PAYG gives the highest conversion rate.", "example": "✓ Example: Add a per-user/month or per-API-call dimension so buyers can start small and scale up before committing to a contract."})
    scores.append({"category": "Pay-As-You-Go Pricing", "score": 100 if has_payg else 0})

    if not has_contract:
        tips.append({"category": "Contract Pricing", "tip": "Consider contract pricing for enterprise buyers — transition customers from PAYG to contract as relationships develop.", "example": "✓ Offer annual contract tiers (e.g. Starter / Pro / Enterprise) with volume discounts to incentivise commitment."})
    scores.append({"category": "Contract Pricing", "score": 100 if has_contract else 0})

    # ── PLG: Procurement ──────────────────────────────────────────────────────
    has_vendor_insights = details.get("VendorInsights") or details.get("SecurityProfile")
    has_scmp = details.get("StandardContractForMarketplace") or "scmp" in json.dumps(details).lower()
    has_quick_launch = "quicklaunch" in json.dumps(details).lower() or "quick_launch" in json.dumps(details).lower()

    if not has_vendor_insights:
        tips.append({"category": "Vendor Insights", "tip": "Enable Vendor Insights — security reviews delay procurement by 8–10 weeks. Vendor Insights gives buyers a dashboard of 125 security and compliance controls to speed up their review.", "example": "✓ Action: Go to AMMP → your listing → Vendor Insights and connect your AWS account. Supports SOC 2, ISO 27001, PCI DSS, FedRAMP, HIPAA, GDPR evidence."})
    scores.append({"category": "Vendor Insights", "score": 100 if has_vendor_insights else 0})

    if not has_scmp:
        tips.append({"category": "Standard Contract (SCMP)", "tip": "Use the Standard Contract for AWS Marketplace (SCMP) instead of a custom EULA — it can accelerate sales cycles by up to 80%.", "example": "✓ Action: Select SCMP when configuring your listing's contract terms. Optional addendum templates are available for enhanced security and regulatory compliance."})
    scores.append({"category": "Standard Contract (SCMP)", "score": 100 if has_scmp else 0})

    if not has_quick_launch:
        tips.append({"category": "Quick Launch", "tip": "Enable Quick Launch for self-service buyers — customers increasingly prefer end-to-end low-touch procurement.", "example": "✓ Action: Configure Quick Launch in AMMP to let buyers deploy your product with a single click, without needing to contact your sales team."})
    scores.append({"category": "Quick Launch", "score": 100 if has_quick_launch else 0})

    overall = round(sum(s["score"] for s in scores) / len(scores))

    # Sort tips by score ascending (worst first)
    score_map = {s["category"]: s["score"] for s in scores}
    tips.sort(key=lambda t: score_map.get(t["category"], 50))

    # ── AI executive summary ──────────────────────────────────────────────────
    summary = ""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        score_summary = "\n".join(f"- {s['category']}: {s['score']}%" for s in scores)
        tip_summary = "\n".join(f"- {t['category']}: {t['tip']}" for t in tips[:6])
        summary_prompt = f"""You are an AWS Marketplace listing advisor. Write a 3-4 sentence executive summary for a seller based on their listing effectiveness scores, benchmarked against official AWS Marketplace guidelines and PLG best practices.

{AWS_MP_GUIDELINES}

Overall score: {overall}%

Category scores:
{score_summary}

Top recommendations:
{tip_summary}

Write a concise, actionable summary that:
1. States the overall listing health relative to AWS Marketplace best practices in one sentence
2. Identifies the 2-3 highest priority areas to fix, referencing specific guidelines where relevant
3. Ends with one specific next action they should take today

Be direct and specific. Do not use bullet points. Do not mention AWS Marketplace by name repeatedly."""

        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": summary_prompt}]
            }),
            contentType="application/json",
            accept="application/json",
        )
        summary = json.loads(resp["body"].read())["content"][0]["text"].strip()
    except Exception:
        pass

    return {
        "pass": True,
        "overall_score": overall,
        "summary": summary,
        "scores": scores,
        "tips": tips,
        "product_title": title,
        "short_description": desc,
        "long_description": long_desc,
        "highlights": highlights,
        "keywords": keywords,
        "debug_keys": top_keys,
    }


def respond(status, body):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }
