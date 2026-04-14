import json
import boto3
import requests
from botocore.exceptions import ClientError

# ── Shared Data Structures ───────────────────────────────────────────────────

GUIDELINES = {
    "title": {
        "rules": [
            "Use title case (capitalise first letter of each important word)",
            "Buyer must identify the product by name alone",
            "Use brand or manufacturer name",
            "Avoid hyperbole and generic words (Solution, Platform, Product)",
            "Max ~80 characters",
        ],
        "search_ranking": "Product title is the #1 search ranking field",
    },
    "short_description": {
        "rules": [
            "Max 350 characters",
            "Avoid unnecessary capitalisation and punctuation",
            "No redirects to other platforms",
            "Lead with problem solved or value delivered",
            "No hyperbole",
        ],
    },
    "highlights": {
        "rules": [
            "Up to 3 bullet points",
            "Each must describe a primary selling point",
            "Be specific with metrics or concrete outcomes",
            "Avoid generic phrases (Easy to use, Scalable, Reliable, Powerful)",
        ],
        "generic_phrases": [
            "easy to use", "scalable", "reliable", "powerful",
            "best-in-class", "world-class", "cutting-edge",
            "next-generation", "innovative", "seamless",
        ],
    },
    "long_description": {
        "rules": [
            "Include features, benefits, usage, specific use cases",
            "Integration ecosystem and customer outcomes",
            "Minimum 300 characters recommended",
        ],
    },
    "keywords": {
        "rules": [
            "Up to 3 keywords/phrases",
            "Max 250 chars total",
            "Use buyer vocabulary",
            "Don't duplicate title",
        ],
    },
    "plg": {
        "stats": {
            "search_traffic_pct": 30,
            "first_page_click_pct": 60,
            "seo_landing_pct": 95,
            "video_engagement_pct": 20,
            "free_trial_essential_pct": 25,
            "free_trial_payg_conversion_multiplier": 3,
            "media_pricing_engagement_multiplier": 3,
        },
    },
}

SCORING_RUBRICS = {
    "title": {
        "bands": [
            {"range": [0, 29], "label": "Needs Attention",
             "criteria": "Missing, generic (e.g. 'Solution', 'Platform'), or not in title case. Buyer cannot identify the product."},
            {"range": [30, 59], "label": "Fair",
             "criteria": "Product identifiable but title case inconsistent, contains hyperbole, or missing brand name. Not optimised for search."},
            {"range": [60, 79], "label": "Good",
             "criteria": "Proper title case, brand name present, product identifiable. Minor issues: could be more specific or searchable."},
            {"range": [80, 100], "label": "Optimised",
             "criteria": "Title case, brand name, product clearly identifiable, includes searchable category terms, no hyperbole, under 80 chars."},
        ],
    },
    "short_description": {
        "bands": [
            {"range": [0, 29], "label": "Needs Attention",
             "criteria": "Missing, over 350 chars, starts with 'We'/'Our', or contains hyperbole and redirect language."},
            {"range": [30, 59], "label": "Fair",
             "criteria": "Present and under 350 chars but leads with company name, lacks specificity, or contains unnecessary capitalisation."},
            {"range": [60, 79], "label": "Good",
             "criteria": "Under 350 chars, leads with value/problem, avoids self-promotion. Could be more specific about outcomes or use cases."},
            {"range": [80, 100], "label": "Optimised",
             "criteria": "Under 350 chars, leads with problem solved, specific outcomes, no hyperbole, no redirects, benefit-focused."},
        ],
    },
    "highlights": {
        "bands": [
            {"range": [0, 29], "label": "Needs Attention",
             "criteria": "Missing or only 1 highlight. Content is generic (e.g. 'Easy to use') with no metrics or specifics."},
            {"range": [30, 59], "label": "Fair",
             "criteria": "2-3 highlights present but mostly generic phrases, lacking metrics, or not aligned with product value proposition."},
            {"range": [60, 79], "label": "Good",
             "criteria": "3 highlights present, mostly specific, some metrics. Minor issues: one or more highlights could be more benefit-driven."},
            {"range": [80, 100], "label": "Optimised",
             "criteria": "3 highlights, each specific with measurable outcomes, aligned to product value proposition, no generic phrases."},
        ],
    },
}

CATEGORY_WEIGHTS = {
    "Title":                 10,
    "Short Description":     10,
    "Highlights":             9,
    "Long Description":       6,
    "Search Keywords":        7,
    "Categories":             3,
    "Media / Videos":         7,
    "Support":                4,
    "Free Trial":             9,
    "Pay-As-You-Go Pricing":  6,
    "Contract Pricing":       4,
    "Title SEO":              5,
}


def get_band_label(field, score):
    """Look up the score band label from SCORING_RUBRICS for a given field and numeric score.
    Returns None if field not in rubrics or no matching band."""
    rubric = SCORING_RUBRICS.get(field)
    if not rubric:
        return None
    for band in rubric["bands"]:
        low, high = band["range"]
        if low <= score <= high:
            return band["label"]
    return None


# ── Graduated Rule-Based Scoring Functions ───────────────────────────────────

def score_media(details):
    """Graduated media scoring: 0=none, 30=screenshots only, 60=multiple screenshots,
    80=has video, 100=video+screenshots."""
    promo = details.get("PromotionalResources", {})
    videos = promo.get("Videos", details.get("Videos", []))
    screenshots = promo.get("Screenshots", details.get("Screenshots", []))
    additional = promo.get("AdditionalResources", details.get("AdditionalResources", []))

    has_video = bool(videos and len(videos) > 0)
    screenshot_count = len(screenshots) if screenshots else 0
    additional_count = len(additional) if additional else 0
    total_images = screenshot_count + additional_count
    has_screenshots = total_images > 0

    if has_video and has_screenshots:
        return 100
    if has_video:
        return 80
    if total_images > 1:
        return 60
    if has_screenshots:
        return 30
    return 0


def score_keywords(keywords):
    """Graduated keyword scoring: 0=none, 30=1 keyword, 60=2 keywords,
    80=3+ keywords with any short ones, 100=3+ keywords all with sufficient length (>=5 chars)."""
    if not keywords:
        return 0
    count = len(keywords)
    if count == 1:
        return 30
    if count == 2:
        return 60
    # 3 or more keywords
    all_sufficient = all(len(kw.strip()) >= 5 for kw in keywords)
    if all_sufficient:
        return 100
    return 80


def score_long_description(text):
    """Graduated long description scoring: 0=empty, 30=under 150 chars, 50=under 300 chars,
    70=300+ basic, 85=300+ with structure indicators, 100=300+ with multiple structure indicators."""
    if not text or not text.strip():
        return 0
    length = len(text.strip())
    if length < 150:
        return 30
    if length < 300:
        return 50
    # 300+ characters — check for structure indicators
    lower_text = text.lower()
    structure_indicators = ["use case", "feature", "integration", "compliance"]
    matches = sum(1 for indicator in structure_indicators if indicator in lower_text)
    if matches >= 2:
        return 100
    if matches >= 1:
        return 85
    return 70


def score_support(details):
    """Graduated support scoring: 0=none, 40=description only,
    70=description+URL or email, 100=description+URL+email."""
    support_info = details.get("SupportInformation", {})
    description = support_info.get("Description", "")
    if not description or not description.strip():
        return 0
    text = description.strip()
    has_url = "http://" in text or "https://" in text
    has_email = "@" in text
    if has_url and has_email:
        return 100
    if has_url or has_email:
        return 70
    return 40


def score_free_trial(has_trial, has_payg):
    """Free trial scoring: 0=no trial, 70=trial only, 100=trial+PAYG."""
    if not has_trial:
        return 0
    if has_payg:
        return 100
    return 70


def score_payg(has_payg, has_contract):
    """PAYG scoring: 0=no PAYG, 70=PAYG only, 100=PAYG+contract."""
    if not has_payg:
        return 0
    if has_contract:
        return 100
    return 70


def score_contract(has_contract):
    """Contract scoring: 0=no contract, 100=has contract."""
    if has_contract:
        return 100
    return 0


# ── Product Context Derivation ───────────────────────────────────────────────

# Mapping of common AWS Marketplace categories to industry and product type
_CATEGORY_INDUSTRY_MAP = {
    "security": {"industry": "Cybersecurity", "product_type": "Security Software"},
    "monitoring": {"industry": "IT Operations", "product_type": "Monitoring & Observability"},
    "business intelligence": {"industry": "Analytics", "product_type": "BI / Analytics"},
    "analytics": {"industry": "Analytics", "product_type": "Data Analytics"},
    "machine learning": {"industry": "Artificial Intelligence", "product_type": "ML / AI Platform"},
    "artificial intelligence": {"industry": "Artificial Intelligence", "product_type": "AI Software"},
    "devops": {"industry": "Software Development", "product_type": "DevOps Tooling"},
    "developer tools": {"industry": "Software Development", "product_type": "Developer Tools"},
    "networking": {"industry": "Networking", "product_type": "Network Software"},
    "storage": {"industry": "Data Management", "product_type": "Storage Solution"},
    "database": {"industry": "Data Management", "product_type": "Database"},
    "data protection": {"industry": "Cybersecurity", "product_type": "Data Protection"},
    "compliance": {"industry": "Governance & Compliance", "product_type": "Compliance Software"},
    "migration": {"industry": "Cloud Infrastructure", "product_type": "Migration Tooling"},
    "infrastructure software": {"industry": "Cloud Infrastructure", "product_type": "Infrastructure Software"},
    "iot": {"industry": "Internet of Things", "product_type": "IoT Platform"},
    "financial services": {"industry": "Financial Services", "product_type": "FinTech Software"},
    "healthcare": {"industry": "Healthcare", "product_type": "HealthTech Software"},
    "media": {"industry": "Media & Entertainment", "product_type": "Media Software"},
    "education": {"industry": "Education", "product_type": "EdTech Software"},
    "operating systems": {"industry": "Cloud Infrastructure", "product_type": "Operating System"},
    "content management": {"industry": "Content Management", "product_type": "CMS"},
    "ecommerce": {"industry": "Retail & Commerce", "product_type": "eCommerce Platform"},
    "crm": {"industry": "Business Applications", "product_type": "CRM Software"},
    "erp": {"industry": "Business Applications", "product_type": "ERP Software"},
    "high performance computing": {"industry": "Scientific Computing", "product_type": "HPC Software"},
}

# Mapping of keywords found in titles/descriptions to target audiences
_AUDIENCE_KEYWORDS = {
    "security": "Security operations teams",
    "devops": "DevOps engineers",
    "developer": "Software developers",
    "data": "Data teams and analysts",
    "analytics": "Data teams and analysts",
    "compliance": "Compliance and governance teams",
    "enterprise": "Enterprise IT teams",
    "infrastructure": "Infrastructure and platform teams",
    "machine learning": "Data scientists and ML engineers",
    "ai": "AI/ML practitioners",
    "iot": "IoT engineers and solution architects",
    "finance": "Finance and accounting teams",
    "healthcare": "Healthcare IT teams",
    "network": "Network engineers",
    "database": "Database administrators",
    "monitoring": "SRE and operations teams",
}


def derive_product_context(details):
    """Derive product context from listing categories, title, and description.
    Returns a dict with 'product_type', 'industry', 'target_audience', and 'summary' keys.
    Falls back to generic values if context cannot be determined. Never raises."""
    fallback = {
        "product_type": "Software",
        "industry": "General",
        "target_audience": "Technical teams",
        "summary": "General software product",
    }
    try:
        if not details or not isinstance(details, dict):
            return fallback

        description_block = details.get("Description", {})
        if not isinstance(description_block, dict):
            description_block = {}

        categories = description_block.get("Categories", [])
        if not isinstance(categories, list):
            categories = []

        title = description_block.get("Title", "")
        if not isinstance(title, str):
            title = ""

        short_desc = description_block.get("ShortDescription", "")
        if not isinstance(short_desc, str):
            short_desc = ""

        # Try to match categories against the industry map
        product_type = None
        industry = None
        for cat in categories:
            if not isinstance(cat, str):
                continue
            cat_lower = cat.strip().lower()
            for key, mapping in _CATEGORY_INDUSTRY_MAP.items():
                if key in cat_lower:
                    industry = mapping["industry"]
                    product_type = mapping["product_type"]
                    break
            if industry:
                break

        # If no category match, try title and short description
        if not industry:
            combined = (title + " " + short_desc).lower()
            for key, mapping in _CATEGORY_INDUSTRY_MAP.items():
                if key in combined:
                    industry = mapping["industry"]
                    product_type = mapping["product_type"]
                    break

        # Derive target audience from title and short description
        target_audience = None
        combined_text = (title + " " + short_desc).lower()
        for keyword, audience in _AUDIENCE_KEYWORDS.items():
            if keyword in combined_text:
                target_audience = audience
                break

        # If still no audience match, try categories
        if not target_audience:
            for cat in categories:
                if not isinstance(cat, str):
                    continue
                cat_lower = cat.strip().lower()
                for keyword, audience in _AUDIENCE_KEYWORDS.items():
                    if keyword in cat_lower:
                        target_audience = audience
                        break
                if target_audience:
                    break

        # Apply fallbacks for any missing values
        product_type = product_type or "Software"
        industry = industry or "General"
        target_audience = target_audience or "Technical teams"

        summary = f"{industry} {product_type.lower()} targeting {target_audience.lower()}"

        return {
            "product_type": product_type,
            "industry": industry,
            "target_audience": target_audience,
            "summary": summary,
        }
    except Exception:
        return fallback


# ── Lambda Handler ───────────────────────────────────────────────────────────

def check_registration_ssl(body):
    """Check the HTTPS certificate of the registration page URL."""
    import ssl
    import socket
    import datetime
    from urllib.parse import urlparse

    url = body.get("registration_page_url")
    if not url:
        return {"pass": False, "error": "registration_page_url is required"}

    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        port = parsed.port or 443

        if not hostname:
            return {"pass": False, "error": "Could not parse hostname from URL"}

        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()

        # Extract issuer
        issuer_parts = []
        for rdn in cert.get("issuer", ()):
            for attr_type, attr_value in rdn:
                if attr_type in ("organizationName", "commonName"):
                    issuer_parts.append(attr_value)
        issuer = ", ".join(issuer_parts) if issuer_parts else "Unknown"

        # Extract subject for self-signed check
        subject_parts = []
        for rdn in cert.get("subject", ()):
            for attr_type, attr_value in rdn:
                if attr_type in ("organizationName", "commonName"):
                    subject_parts.append(attr_value)
        subject = ", ".join(subject_parts) if subject_parts else "Unknown"

        is_self_signed = issuer == subject

        # Parse expiry
        not_after = cert.get("notAfter", "")
        expiry_date = datetime.datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
        now = datetime.datetime.utcnow()
        days_until_expiry = (expiry_date - now).days
        is_expired = days_until_expiry < 0
        expiring_soon = days_until_expiry <= 30

        passes = not is_expired and not is_self_signed and not expiring_soon

        if is_expired:
            note = f"Certificate expired {abs(days_until_expiry)} day(s) ago. Renew immediately — MCO will reject an expired certificate."
        elif is_self_signed:
            note = "Certificate is self-signed. Use a certificate from a trusted CA (e.g. ACM, Let's Encrypt). MCO will reject self-signed certificates."
        elif expiring_soon:
            note = f"Certificate expires in {days_until_expiry} day(s). Renew before submitting for MCO review."
        else:
            note = f"Valid certificate from {issuer}, expires in {days_until_expiry} days."

        return {
            "pass": passes,
            "issuer": issuer,
            "expiry_date": expiry_date.isoformat(),
            "days_until_expiry": days_until_expiry,
            "is_self_signed": is_self_signed,
            "note": note,
        }
    except ssl.SSLCertVerificationError as e:
        return {"pass": False, "error": f"SSL certificate verification failed: {str(e)}", "note": "Certificate is invalid or untrusted. Use a certificate from a trusted CA."}
    except socket.timeout:
        return {"pass": False, "error": "Connection timed out while checking SSL certificate"}
    except Exception as e:
        return {"pass": False, "error": f"SSL check failed: {str(e)}"}


def check_fulfillment_url_match(body):
    """Check if the provided registration_page_url matches the FulfillmentUrl in the listing."""
    from urllib.parse import urlparse

    url = body.get("registration_page_url")
    entity_id = body.get("entity_id")

    if not url:
        return {"pass": False, "error": "registration_page_url is required"}
    if not entity_id:
        return {"pass": False, "error": "entity_id is required"}

    try:
        mp = boto3.client("marketplace-catalog", region_name="us-east-1")
        resp = mp.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
        raw = resp.get("Details", "{}")
        details = json.loads(raw) if isinstance(raw, str) else raw

        # Extract FulfillmentUrl
        versions = details.get("Versions", [])
        fulfillment_url = ""
        if versions:
            delivery_options = versions[0].get("DeliveryOptions", [])
            if delivery_options:
                fulfillment_url = delivery_options[0].get("FulfillmentUrl", "")

        if not fulfillment_url:
            return {
                "pass": False,
                "listing_url": None,
                "provided_url": url,
                "match": False,
                "note": "No FulfillmentUrl found in the listing. Ensure your listing has a registration page URL configured.",
            }

        # Normalize both URLs for comparison — strip trailing slashes, compare origins + paths
        def normalize(u):
            parsed = urlparse(u.rstrip("/"))
            return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/").lower()

        norm_listing = normalize(fulfillment_url)
        norm_provided = normalize(url)
        match = norm_listing == norm_provided

        if match:
            note = "Registration URL matches the FulfillmentUrl configured in your listing."
        else:
            note = (f"URL mismatch — your listing's FulfillmentUrl is '{fulfillment_url}' but you provided '{url}'. "
                    "Ensure you are testing with the same URL configured in your listing.")

        return {
            "pass": match,
            "listing_url": fulfillment_url,
            "provided_url": url,
            "match": match,
            "note": note,
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}
    except Exception as e:
        return {"pass": False, "error": f"Fulfillment URL check failed: {str(e)}"}


def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    action = body.get("action")

    handlers = {
        "resolve_customer": resolve_customer,
        "get_entitlements": get_entitlements,
        "meter_usage": meter_usage,
        "check_registration_page": check_registration_page,
        "check_resolve_customer_causality": check_resolve_customer_causality,
        "check_registration_error_handling": check_registration_error_handling,
        "score_listing": score_listing,
        "rewrite_field": rewrite_field,
        "detect_listing_type": detect_listing_type,
        "check_concurrent_agreements": check_concurrent_agreements,
        "check_eventbridge": check_eventbridge,
        "check_metering_history": check_metering_history,
        "check_resolve_customer_history": check_resolve_customer_history,
        "check_listing_completeness": check_listing_completeness,
        "check_notification_endpoint": check_notification_endpoint,
        "check_registration_ssl": check_registration_ssl,
        "check_fulfillment_url_match": check_fulfillment_url_match,
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

    # Step 1: POST with token in form body (matches real Marketplace flow)
    try:
        post_resp = requests.post(
            url,
            data={"x-amzn-marketplace-token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
            allow_redirects=True,
        )
        post_result = {
            "pass": post_resp.status_code < 500,
            "status_code": post_resp.status_code,
            "final_url": post_resp.url,
            "method": "POST",
            "content_type_sent": "application/x-www-form-urlencoded",
            "accepts_post": post_resp.status_code < 400,
        }
    except requests.exceptions.Timeout:
        return {"pass": False, "error": "Registration page timed out after 10 seconds"}
    except requests.exceptions.ConnectionError as e:
        return {"pass": False, "error": f"Could not connect to registration page: {str(e)}"}

    # Step 2: Legacy GET fallback for comparison
    legacy_get = None
    try:
        get_url = f"{url}?x-amzn-marketplace-token={token}"
        get_resp = requests.get(get_url, timeout=10, allow_redirects=True)
        legacy_get = {
            "status_code": get_resp.status_code,
            "note": f"GET {'also works' if get_resp.status_code < 400 else f'returned {get_resp.status_code}'}",
        }
    except Exception:
        legacy_get = {"status_code": None, "note": "GET request failed"}

    # Step 3: Build response with guidance
    if post_result["accepts_post"]:
        note = "Registration page accepts POST with marketplace token correctly."
    elif post_result["status_code"] < 500:
        note = (f"Registration page returned {post_result['status_code']} for POST. "
                "AWS Marketplace sends the token as a POST with form body — ensure your page handles POST requests.")
    else:
        note = (f"Registration page returned {post_result['status_code']} server error. "
                "Your page must handle POST requests with x-amzn-marketplace-token in the form body.")

    post_result["note"] = note
    post_result["legacy_get_result"] = legacy_get
    return post_result


def check_resolve_customer_causality(body):
    url = body.get("registration_page_url")
    token = body.get("registration_token")

    if not url or not token:
        return {"pass": False, "error": "registration_page_url and registration_token are required"}

    import datetime
    import time

    # Step 1: Get own ARN for exclusion
    sts = boto3.client("sts", region_name="us-east-1")
    own_arn = sts.get_caller_identity().get("Arn", "")

    ct = boto3.client("cloudtrail", region_name="us-east-1")

    # Step 2: Record pre-POST event count
    pre_time = datetime.datetime.utcnow()
    pre_resp = ct.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "ResolveCustomer"}],
        StartTime=pre_time - datetime.timedelta(minutes=10),
        MaxResults=50,
    )
    pre_events = [e for e in pre_resp.get("Events", [])
                  if own_arn not in json.loads(e.get("CloudTrailEvent", "{}"))
                  .get("userIdentity", {}).get("arn", "")]
    pre_count = len(pre_events)

    # Step 3: POST the token to the registration page
    try:
        requests.post(
            url,
            data={"x-amzn-marketplace-token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
            allow_redirects=True,
        )
    except Exception:
        pass  # We still check CloudTrail even if POST fails

    # Step 4: Wait for CloudTrail propagation
    time.sleep(5)

    # Step 5: Query CloudTrail for events after the POST
    post_time = datetime.datetime.utcnow()
    post_resp = ct.lookup_events(
        LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "ResolveCustomer"}],
        StartTime=pre_time - datetime.timedelta(minutes=10),
        MaxResults=50,
    )
    post_events = [e for e in post_resp.get("Events", [])
                   if own_arn not in json.loads(e.get("CloudTrailEvent", "{}"))
                   .get("userIdentity", {}).get("arn", "")]
    post_count = len(post_events)

    # Step 6: Check for new events (causality signal)
    new_events = post_count - pre_count
    causality_confirmed = new_events > 0

    result = {
        "pass": causality_confirmed,
        "causality_confirmed": causality_confirmed,
        "time_window_seconds": int((post_time - pre_time).total_seconds()) + 600,
        "events_in_window": post_count,
        "pre_count": pre_count,
        "post_count": post_count,
    }

    if causality_confirmed:
        result["note"] = (f"ResolveCustomer call detected — {new_events} new call(s) appeared "
                         f"after submitting the token to your registration page.")
    else:
        result["note"] = (
            "No new ResolveCustomer call detected after submitting the token to your registration page. "
            "Note: CloudTrail events can take 5-15 minutes to appear. "
            "If this just failed, wait a few minutes and re-run. "
            "Your backend must call ResolveCustomer immediately when a buyer POSTs the token."
        )
        result["code_example"] = {
            "python": (
                "import boto3\n\n"
                "client = boto3.client('meteringmarketplace', region_name='us-east-1')\n\n"
                "# Call this in your registration page POST handler\n"
                "# token = request.POST.get('x-amzn-marketplace-token')\n"
                "response = client.resolve_customer(RegistrationToken=token)\n\n"
                "customer_id = response['CustomerIdentifier']\n"
                "account_id = response['CustomerAWSAccountId']\n"
                "product_code = response['ProductCode']\n\n"
                "# Store these in your database for entitlement and metering"
            ),
            "nodejs": (
                "const { MarketplaceMeteringClient, ResolveCustomerCommand } = "
                "require('@aws-sdk/client-marketplace-metering');\n\n"
                "const client = new MarketplaceMeteringClient({ region: 'us-east-1' });\n\n"
                "// Call this in your registration page POST handler\n"
                "// const token = req.body['x-amzn-marketplace-token'];\n"
                "const response = await client.send(new ResolveCustomerCommand({\n"
                "  RegistrationToken: token\n"
                "}));\n\n"
                "const { CustomerIdentifier, CustomerAWSAccountId, ProductCode } = response;\n"
                "// Store these in your database for entitlement and metering"
            ),
        }

    return result


# ── Stack trace patterns for error handling check ────────────────────────────

STACK_TRACE_PATTERNS = [
    "Traceback (most recent call last)",
    "at com.", "at org.", "at java.",
    "NullPointerException", "TypeError:", "ValueError:",
    "SyntaxError:", "ReferenceError:", "AttributeError:",
    "Internal Server Error",
    "stack trace",
]


def check_registration_error_handling(body):
    url = body.get("registration_page_url")

    if not url:
        return {"pass": False, "error": "registration_page_url is required"}

    invalid_token = "test-invalid-token-00000"

    try:
        resp = requests.post(
            url,
            data={"x-amzn-marketplace-token": invalid_token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
            allow_redirects=True,
        )
    except requests.exceptions.Timeout:
        return {"pass": False, "error": "Registration page timed out on invalid token"}
    except requests.exceptions.ConnectionError as e:
        return {"pass": False, "error": f"Could not connect: {str(e)}"}

    body_text = resp.text[:2000]  # Limit scan to first 2000 chars
    body_lower = body_text.lower()

    # Check for stack trace indicators
    has_stack_trace = any(pattern.lower() in body_lower for pattern in STACK_TRACE_PATTERNS)

    # Check for user-friendly error indicators
    error_indicators = ["invalid", "expired", "error", "try again", "contact", "support"]
    has_error_message = any(indicator in body_lower for indicator in error_indicators)

    is_server_error = resp.status_code >= 500
    passes = not is_server_error and not has_stack_trace

    # Build response snippet (sanitised)
    snippet = body_text[:200].replace("\n", " ").strip()

    if passes and has_error_message:
        note = "Registration page handles invalid tokens gracefully with a user-friendly error message."
    elif passes and not has_error_message:
        note = (f"Registration page returned {resp.status_code} for invalid token without crashing, "
                "but no clear error message was detected. Consider showing a user-friendly message "
                "like 'Invalid or expired token — please return to AWS Marketplace to subscribe.'")
    elif has_stack_trace:
        note = ("Registration page exposes a stack trace or error details when given an invalid token. "
                "This is a security risk and will likely fail MCO review. "
                "Catch the InvalidTokenException from ResolveCustomer and show a friendly error page.")
    else:
        note = (f"Registration page returned {resp.status_code} server error for invalid token. "
                "Your page should catch errors from ResolveCustomer and return a user-friendly error page.")

    return {
        "pass": passes,
        "status_code": resp.status_code,
        "has_error_message": has_error_message,
        "has_stack_trace": has_stack_trace,
        "response_snippet": snippet,
        "note": note,
    }


def check_listing_completeness(body):
    entity_id = body.get("entity_id")
    if not entity_id:
        return {"pass": False, "error": "entity_id is required"}
    try:
        mp = boto3.client("marketplace-catalog", region_name="us-east-1")
        resp = mp.describe_entity(Catalog="AWSMarketplace", EntityId=entity_id)
        raw = resp.get("Details", "{}")
        details = json.loads(raw) if isinstance(raw, str) else raw

        checks = []
        issues = []

        # Logo
        logo = details.get("PromotionalResources", {}).get("LogoUrl", "")
        checks.append({"field": "Logo", "pass": bool(logo)})
        if not logo:
            issues.append("Logo is missing — required for MCO review")

        # Videos/Screenshots
        videos = details.get("PromotionalResources", {}).get("Videos", [])
        media = details.get("PromotionalResources", {}).get("AdditionalResources", [])
        has_media = bool(videos or media)
        checks.append({"field": "Screenshots / Videos", "pass": has_media})
        if not has_media:
            issues.append("No screenshots or videos — strongly recommended for conversion")

        # Support information
        support = details.get("SupportInformation", {}).get("Description", "")
        checks.append({"field": "Support Information", "pass": bool(support)})
        if not support:
            issues.append("Support information is missing — required for MCO review")

        # Registration/Fulfillment URL
        versions = details.get("Versions", [])
        fulfillment_url = ""
        if versions:
            delivery_options = versions[0].get("DeliveryOptions", [])
            if delivery_options:
                fulfillment_url = delivery_options[0].get("FulfillmentUrl", "")
        checks.append({"field": "Registration Page URL", "pass": bool(fulfillment_url)})
        if not fulfillment_url:
            issues.append("Registration page URL (FulfillmentUrl) is missing — required for SaaS listings")

        # Categories
        categories = details.get("Description", {}).get("Categories", [])
        checks.append({"field": "Categories", "pass": bool(categories)})
        if not categories:
            issues.append("No categories selected — required for discoverability")

        all_pass = len(issues) == 0
        return {
            "pass": all_pass,
            "checks": checks,
            "issues": issues,
            "note": "All required listing fields are present." if all_pass else f"{len(issues)} issue(s) found in listing completeness.",
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def check_notification_endpoint(body):
    """Check CloudTrail for SNS ConfirmSubscription or EventBridge rule activity
    indicating the seller's notification endpoint is configured."""
    try:
        import datetime
        sts = boto3.client("sts", region_name="us-east-1")
        own_arn = sts.get_caller_identity().get("Arn", "")

        ct = boto3.client("cloudtrail", region_name="us-east-1")

        # Check for SNS ConfirmSubscription (legacy) or EventBridge rule creation
        results = {}
        for event_name in ["ConfirmSubscription", "PutRule"]:
            resp = ct.lookup_events(
                LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": event_name}],
                StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=30),
                MaxResults=10,
            )
            events = [e for e in resp.get("Events", [])
                     if own_arn not in json.loads(e.get("CloudTrailEvent", "{}")).get("userIdentity", {}).get("arn", "")]
            results[event_name] = len(events)

        # Also check if EventBridge rules exist for marketplace
        eb = boto3.client("events", region_name="us-east-1")
        rules = eb.list_rules(EventBusName="default").get("Rules", [])
        mp_rules = [r for r in rules if "agreement-marketplace" in json.dumps(r.get("EventPattern", "")).lower()
                   or "marketplace" in r.get("Name", "").lower()]

        has_eventbridge = len(mp_rules) > 0
        has_sns = results.get("ConfirmSubscription", 0) > 0

        if has_eventbridge:
            return {
                "pass": True,
                "method": "EventBridge",
                "rules": [r["Name"] for r in mp_rules],
                "note": f"EventBridge configured with {len(mp_rules)} rule(s) for Marketplace notifications.",
            }
        elif has_sns:
            return {
                "pass": True,
                "method": "SNS",
                "note": "SNS subscription confirmed. Note: SNS is being replaced by EventBridge for new listings.",
            }
        else:
            return {
                "pass": False,
                "note": "No notification endpoint detected (neither EventBridge rules nor SNS subscription confirmation found in the last 30 days). Your application must handle subscription lifecycle events.",
            }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def check_resolve_customer_history(body):
    try:
        import datetime
        sts = boto3.client("sts", region_name="us-east-1")
        own_arn = sts.get_caller_identity().get("Arn", "")

        ct = boto3.client("cloudtrail", region_name="us-east-1")
        resp = ct.lookup_events(
            LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "ResolveCustomer"}],
            StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=7),
            MaxResults=50,
        )
        events = resp.get("Events", [])

        # Exclude calls made by this Lambda
        external_events = []
        for e in events:
            ct_event = json.loads(e.get("CloudTrailEvent", "{}"))
            caller_arn = ct_event.get("userIdentity", {}).get("arn", "")
            if own_arn and own_arn in caller_arn:
                continue
            external_events.append(e)

        if not external_events:
            return {
                "pass": False,
                "note": "No ResolveCustomer calls found from your application in the last 7 days. Your backend must call ResolveCustomer immediately when a buyer lands on your registration page. Tip: run the 'ResolveCustomer Causality' check to verify your registration page triggers a ResolveCustomer call in real time.",
                "count": 0,
                "code_example": {
                    "python": """import boto3

client = boto3.client('meteringmarketplace', region_name='us-east-1')

# Call this immediately when buyer lands on your registration page
# token comes from the POST body: request.POST.get('x-amzn-marketplace-token')
response = client.resolve_customer(RegistrationToken=token)

customer_identifier = response['CustomerIdentifier']
customer_aws_account_id = response['CustomerAWSAccountId']
product_code = response['ProductCode']
license_arn = response['LicenseArn']

# Store customer_identifier and customer_aws_account_id in your database""",
                    "nodejs": """const { MarketplaceMeteringClient, ResolveCustomerCommand } = require('@aws-sdk/client-marketplace-metering');

const client = new MarketplaceMeteringClient({ region: 'us-east-1' });

// token comes from POST body: req.body['x-amzn-marketplace-token']
const response = await client.send(new ResolveCustomerCommand({
  RegistrationToken: token
}));

const { CustomerIdentifier, CustomerAWSAccountId, ProductCode, LicenseArn } = response;
// Store CustomerIdentifier and CustomerAWSAccountId in your database"""
                }
            }

        summary = []
        for e in external_events[:5]:
            ct_event = json.loads(e.get("CloudTrailEvent", "{}"))
            summary.append({
                "time": str(e.get("EventTime", "")),
                "source": ct_event.get("userIdentity", {}).get("arn", ""),
                "error": ct_event.get("errorCode", None),
            })

        errors = [s for s in summary if s.get("error")]
        return {
            "pass": len(errors) == 0,
            "count": len(external_events),
            "recent_calls": summary,
            "note": f"Found {len(external_events)} ResolveCustomer call(s) from your application in the last 7 days." + (f" {len(errors)} call(s) had errors." if errors else " All calls succeeded."),
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def check_metering_history(body):
    product_code = body.get("product_code")
    try:
        import datetime
        # Get our own Lambda role ARN to exclude from results
        sts = boto3.client("sts", region_name="us-east-1")
        own_arn = sts.get_caller_identity().get("Arn", "")

        ct = boto3.client("cloudtrail", region_name="us-east-1")
        resp = ct.lookup_events(
            LookupAttributes=[{"AttributeKey": "EventName", "AttributeValue": "BatchMeterUsage"}],
            StartTime=datetime.datetime.utcnow() - datetime.timedelta(days=7),
            MaxResults=50,
        )
        events = resp.get("Events", [])

        # Filter out calls made by this Lambda (our own test calls)
        external_events = []
        for e in events:
            ct_event = json.loads(e.get("CloudTrailEvent", "{}"))
            caller_arn = ct_event.get("userIdentity", {}).get("arn", "")
            if own_arn and own_arn in caller_arn:
                continue
            # Filter to this product code if provided
            if product_code:
                request = ct_event.get("requestParameters", {})
                if request.get("productCode") != product_code:
                    continue
            external_events.append(e)

        if not external_events:
            return {
                "pass": False,
                "note": "No BatchMeterUsage calls found from your application in the last 7 days. Ensure your backend is calling BatchMeterUsage to report usage.",
                "count": 0,
                "code_example": {
                    "python": """import boto3
from datetime import datetime

client = boto3.client('meteringmarketplace', region_name='us-east-1')

response = client.batch_meter_usage(
    ProductCode='YOUR_PRODUCT_CODE',
    UsageRecords=[
        {
            'Timestamp': datetime.utcnow(),
            'CustomerAWSAccountId': 'CUSTOMER_AWS_ACCOUNT_ID',
            'Dimension': 'YOUR_DIMENSION_KEY',
            'Quantity': 1,
        }
    ]
)
print(response['Results'][0]['Status'])  # Should be 'Success'""",
                    "nodejs": """const { MarketplaceMeteringClient, BatchMeterUsageCommand } = require('@aws-sdk/client-marketplace-metering');

const client = new MarketplaceMeteringClient({ region: 'us-east-1' });

const response = await client.send(new BatchMeterUsageCommand({
  ProductCode: 'YOUR_PRODUCT_CODE',
  UsageRecords: [{
    Timestamp: new Date(),
    CustomerAWSAccountId: 'CUSTOMER_AWS_ACCOUNT_ID',
    Dimension: 'YOUR_DIMENSION_KEY',
    Quantity: 1,
  }]
}));
console.log(response.Results[0].Status); // Should be 'Success'"""
                }
            }

        summary = []
        for e in external_events[:5]:
            ct_event = json.loads(e.get("CloudTrailEvent", "{}"))
            summary.append({
                "time": str(e.get("EventTime", "")),
                "source": ct_event.get("userIdentity", {}).get("arn", ""),
                "error": ct_event.get("errorCode", None),
            })

        errors = [s for s in summary if s.get("error")]
        return {
            "pass": len(errors) == 0,
            "count": len(external_events),
            "recent_calls": summary,
            "note": f"Found {len(external_events)} BatchMeterUsage call(s) from your application in the last 7 days." + (f" {len(errors)} call(s) had errors." if errors else " All calls succeeded."),
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


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
            "dimensions": [d.get("Key") for d in details.get("Dimensions", []) if d.get("Key")],
        }
    except ClientError as e:
        return {"pass": False, "error": e.response["Error"]["Message"]}


def rewrite_field(body):
    field = body.get("field")  # title | description | highlights
    current = body.get("current", "")
    context = body.get("context", "")  # other listing fields for context
    product_context = body.get("product_context")  # optional product context dict

    # ── Task 7.1: Build guidelines text from GUIDELINES module constant ──────
    guidelines_text = "Official AWS Marketplace guidelines:\n"
    for section_key, section_data in GUIDELINES.items():
        if section_key == "plg":
            guidelines_text += "PLG best practices: "
            stats = section_data.get("stats", {})
            plg_parts = []
            if stats.get("free_trial_payg_conversion_multiplier"):
                plg_parts.append(f"Free trial + PAYG = {stats['free_trial_payg_conversion_multiplier']}x higher conversion")
            if stats.get("search_traffic_pct"):
                plg_parts.append(f"{stats['search_traffic_pct']}% of traffic from search engines")
            if stats.get("media_pricing_engagement_multiplier"):
                plg_parts.append(f"listings with media have {stats['media_pricing_engagement_multiplier']}x higher pricing engagement")
            guidelines_text += "; ".join(plg_parts) + "\n"
        else:
            label = section_key.replace("_", " ").title()
            rules = section_data.get("rules", [])
            if rules:
                guidelines_text += f"- {label}: {', '.join(r.lower() if r[0].isupper() else r for r in rules)}\n"

    # ── Task 7.2: Build product context line for prompts ─────────────────────
    context_line = ""
    if product_context and isinstance(product_context, dict):
        summary = product_context.get("summary", "")
        if summary:
            context_line = f"\nProduct domain: {summary}\nTailor the rewrite to this product's domain and target audience.\n"

    prompts = {
        "title": f"""Rewrite this AWS Marketplace product listing title to comply with official guidelines.

{guidelines_text}
Current title: {current}
Product context: {context}
{context_line}
Requirements:
- Use title case (capitalise first letter of each important word)
- Buyer must be able to identify the product by name alone
- Use the brand or manufacturer name
- Avoid hyperbole and generic words like "Solution", "Platform", "Product", "Test", "AnyCompany"
- Maximum 80 characters

Respond with ONLY the rewritten title, nothing else.""",

        "description": f"""Rewrite this AWS Marketplace short description to comply with official guidelines.

{guidelines_text}
Current description: {current}
Product context: {context}
{context_line}
Requirements:
- Maximum 350 characters
- Avoid unnecessary capitalisation and punctuation
- Do not redirect to other platforms or include upsell language
- Lead with the problem solved or value delivered (not "We are..." or "Our product...")
- No hyperbole — include only critical, useful information

Respond with ONLY the rewritten description, nothing else.""",

        "highlights": f"""Rewrite these AWS Marketplace product highlights to comply with official guidelines.

{guidelines_text}
Current highlights: {current}
Product context: {context}
{context_line}
Requirements:
- Provide exactly 3 bullet points
- Each highlight must briefly describe a primary selling point
- Be specific with metrics or concrete outcomes
- Avoid generic phrases like "Easy to use", "Scalable", "Reliable", "Powerful"
- Maximum 150 characters each

Respond with ONLY 3 bullet points, one per line, no numbering or dashes.""",

        "long_description": f"""Rewrite this AWS Marketplace long description to comply with official guidelines.

{guidelines_text}
Current description: {current}
Product context: {context}
{context_line}
Requirements:
- Lead with the problem solved or value delivered
- Include: key use cases, target personas, integration ecosystem, compliance certifications, customer outcomes with metrics
- Structure clearly: Overview → Use Cases → Key Features → Why Choose Us
- Minimum 300 characters
- Use plain text, no markdown or HTML
- Do not redirect to other platforms or include upsell language

Respond with ONLY the rewritten long description, nothing else.""",

        "keywords": f"""Suggest 3 search keywords for this AWS Marketplace product listing, following official guidelines.

{guidelines_text}
Product context: {context}
Current keywords: {current}
{context_line}
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

    # ── Task 5.3: Derive product context ─────────────────────────────────────
    product_context = derive_product_context(details)

    # ── Task 5.1: Build guidelines text from GUIDELINES module constant ──────
    guidelines_text = "AWS MARKETPLACE OFFICIAL LISTING GUIDELINES:\n\n"
    for section_key, section_data in GUIDELINES.items():
        if section_key == "plg":
            guidelines_text += "PLG BEST PRACTICES (from AWS Marketplace field data):\n"
            for stat_key, stat_val in section_data.get("stats", {}).items():
                label = stat_key.replace("_", " ").replace("pct", "%").title()
                guidelines_text += f"- {label}: {stat_val}\n"
        else:
            guidelines_text += f"{section_key.upper().replace('_', ' ')} GUIDELINES:\n"
            for rule in section_data.get("rules", []):
                guidelines_text += f"- {rule}\n"
            if "search_ranking" in section_data:
                guidelines_text += f"- Search ranking: {section_data['search_ranking']}\n"
            if "generic_phrases" in section_data:
                guidelines_text += f"- Generic phrases to avoid: {', '.join(section_data['generic_phrases'])}\n"
        guidelines_text += "\n"

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

    # ── Task 6.1: Generic phrase penalty for highlights ──────────────────────
    if highlights:
        generic_phrases = GUIDELINES["highlights"]["generic_phrases"]
        for h in highlights:
            h_lower = str(h).lower()
            if any(gp in h_lower for gp in generic_phrases):
                hl_score = max(0, hl_score - 15)
                break  # Apply penalty once regardless of how many highlights contain generic phrases

    scores.append({"category": "Highlights", "score": hl_score})

    # ── AI quality assessment (title, description, highlights) ───────────────
    # ── Task 5.4: Include full rubric definitions in AI scoring prompt ────────
    ai_scores = {}
    ai_feedback = {}

    # Build rubric text for the AI prompt
    rubric_text = "SCORING RUBRIC DEFINITIONS:\n\n"
    for field_key, rubric_data in SCORING_RUBRICS.items():
        rubric_text += f"{field_key.upper().replace('_', ' ')}:\n"
        for band in rubric_data["bands"]:
            rubric_text += f"  {band['range'][0]}-{band['range'][1]} ({band['label']}): {band['criteria']}\n"
        rubric_text += "\n"

    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        prompt = f"""You are an AWS Marketplace listing quality evaluator. Score each field against the official AWS Marketplace guidelines, PLG best practices, and the structured scoring rubric provided below.

{guidelines_text}

{rubric_text}

Product context: {product_context["summary"]}

Now evaluate this listing:

Product Title: {title or "(empty)"}
Short Description: {desc or "(empty)"}
Highlights: {json.dumps(highlights) if highlights else "(empty)"}

Score each field 0-100 based on the scoring rubric bands defined above. Use the criteria for each band to determine the appropriate score range. Provide one specific improvement tip and a concrete example for each, tailored to this product's domain ({product_context["industry"]}).

Respond ONLY with valid JSON in this exact format:
{{
  "title": {{"score": 0-100, "tip": "...", "example": "..."}},
  "description": {{"score": 0-100, "tip": "...", "example": "..."}},
  "highlights": {{"score": 0-100, "tip": "...", "example": "...", "per_highlight": [{{"index": 0, "text": "...", "feedback": "..." or null}}, ...]}}
}}

For the highlights "per_highlight" array: assess each highlight individually. For each highlight, provide its 0-based index, the original text, and specific feedback on how to improve it (or null if the highlight is already strong). Focus on specificity, measurable outcomes, and alignment with the product's value proposition.

Score against the defined criteria per band. A score of 80+ means the field meets all "Optimised" criteria. A score of 60-79 means "Good" with minor issues. A score of 30-59 means "Fair" with significant room for improvement. Below 30 means "Needs Attention" with critical issues."""

        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "temperature": 0,
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
            # ── Task 6.2: Capture per-highlight feedback from AI response ─────
            if field == "highlights" and "per_highlight" in ai_result[field]:
                ai_feedback[field]["per_highlight"] = ai_result[field]["per_highlight"]
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
            tip_entry = {"category": label, "tip": ai_feedback[field]["tip"], "example": ai_feedback[field]["example"]}
            # ── Task 6.2: Include per_highlight in Highlights tip when score < 80 ──
            if field == "highlights" and ai_scores.get("highlights", 100) < 80:
                per_highlight = ai_feedback[field].get("per_highlight")
                if per_highlight and isinstance(per_highlight, list):
                    tip_entry["per_highlight"] = per_highlight
            tips.insert(0, tip_entry)

    # ── Keywords (Task 5.2: graduated scoring) ─────────────────────────────────
    keywords = (details.get("Description", {}).get("SearchKeywords") or
                details.get("SearchKeywords") or
                details.get("Keywords") or [])
    kw_score = score_keywords(keywords)
    # tip handled in PLG Discovery section below

    # ── Categories (Task 5.2: Title SEO inline scoring replaced below) ──────
    categories = (details.get("Description", {}).get("Categories") or
                  details.get("Categories") or [])
    cat_score = 100 if categories else 0
    if not categories:
        tips.append({"category": "Categories", "tip": "No categories selected. Choose up to 3 relevant categories."})
    scores.append({"category": "Categories", "score": cat_score})

    # ── Media (Task 5.2: graduated scoring) ───────────────────────────────────
    media_score = score_media(details)
    if media_score < 80:
        tips.append({"category": "Media / Videos", "tip": "Add demo videos and screenshots. 20% of customers engage with videos on listing pages, and engagement with pricing is 3x higher on listings with rich media.", "example": "✓ Add a 2-3 minute product demo video and at least 3 screenshots showing key features."})
    scores.append({"category": "Media / Videos", "score": media_score})

    # ── Support (Task 5.2: graduated scoring) ─────────────────────────────────
    support_score = score_support(details)
    if support_score < 100:
        tips.append({"category": "Support", "tip": "Add comprehensive support information including a support URL and email address.", "example": "✓ Include: support description, URL (e.g. https://support.example.com), and email (e.g. support@example.com)."})
    scores.append({"category": "Support", "score": support_score})

    # ── PLG: Discovery (Task 5.2: graduated scoring) ────────────────────────
    if kw_score < 100:
        tips.append({"category": "Search Keywords", "tip": "Add all 3 search keywords using buyer-vocabulary terms — 30% of Marketplace traffic comes from search engines and the majority of clicks go to the first 5 results.", "example": "✓ Good: \"cloud monitoring\", \"infrastructure observability\", \"APM tool\"\n✗ Avoid: your product name or company name (already indexed separately)"})
    scores.append({"category": "Search Keywords", "score": kw_score})

    # Title SEO (Task 5.2: graduated scoring)
    title_seo_score = 0
    if title:
        word_count = len(title.split())
        if word_count >= 5:
            title_seo_score = 100
        elif word_count >= 3:
            title_seo_score = 70
        else:
            title_seo_score = 40
    if title_seo_score < 70:
        tips.append({"category": "Title SEO", "tip": "Optimise your title with searchable terms buyers use — title is one of 6 key search ranking fields on AWS Marketplace.", "example": "✓ Good: \"Datadog — Cloud Monitoring & Security Platform\"\n✗ Avoid: \"Datadog\" alone or \"Our Monitoring Tool\""})
    scores.append({"category": "Title SEO", "score": title_seo_score})

    # ── PLG: Evaluation ───────────────────────────────────────────────────────
    # ── Reviews — not scored, shown as static recommendation ─────────────────
    tips.append({"category": "Reviews (G2 / Peerspot)", "tip": "Build your G2 and Peerspot profiles — AWS Marketplace automatically ingests reviews from these platforms. Customers spend 3–6 months researching and browse 3–5 listings before buying.", "example": "✓ Action: Create or claim your product profile at g2.com and peerspot.com, then ask existing customers to leave reviews. AWS Marketplace will automatically display them on your listing."})

    long_desc = (get_nested(details, "Description", "LongDescription") or
                 get_nested(details, "LongDescription") or "")
    long_desc_score = score_long_description(long_desc)
    if long_desc_score < 70:
        tips.append({"category": "Long Description", "tip": "Expand your long description with specific use cases and features — customers use generative AI-powered comparisons to evaluate listings, so detailed content wins.", "example": "✓ Include: key use cases, target personas, integration ecosystem, compliance certifications, and customer outcomes with metrics.\n✓ Structure with clear sections: Overview → Use Cases → Key Features → Why Choose Us"})
    scores.append({"category": "Long Description", "score": long_desc_score})

    # ── Pricing — fetch from public offer for accurate detection ─────────────
    has_free_trial = False
    has_payg = False
    has_contract = False
    has_scmp = False
    try:
        offer_resp = mp.list_entities(
            Catalog="AWSMarketplace",
            EntityType="Offer",
            FilterList=[{"Name": "ProductId", "ValueList": [entity_id]}],
        )
        public_offers = [e for e in offer_resp.get("EntitySummaryList", [])
                        if e.get("OfferSummary", {}).get("Targeting") == ["None"]]
        if public_offers:
            offer_detail = mp.describe_entity(
                Catalog="AWSMarketplace",
                EntityId=public_offers[0]["EntityId"]
            )
            offer_raw = offer_detail.get("Details", "{}")
            offer = json.loads(offer_raw) if isinstance(offer_raw, str) else offer_raw
            term_types = [t.get("Type", "") for t in offer.get("Terms", [])]
            has_free_trial = any("FreeTrial" in t for t in term_types)
            has_payg = any("UsageBased" in t for t in term_types)
            has_contract = any("ConfigurableUpfront" in t or "FixedUpfront" in t for t in term_types)
            has_scmp = any(
                t.get("Type") == "LegalTerm" and
                any(d.get("Type") == "StandardEula" for d in t.get("Documents", []))
                for t in offer.get("Terms", [])
            )
    except Exception:
        # Fall back to dimension-based detection if offer fetch fails
        pricing_str = json.dumps(details).lower()
        has_payg = "externallymetered" in pricing_str
        has_contract = "entitled" in pricing_str

    # ── Pricing (Task 5.2: graduated scoring) ───────────────────────────────
    if not has_free_trial:
        tips.append({"category": "Free Trial", "tip": "Add a free trial — 25% of customers say free trials are essential before purchase, and free trial to PAYG conversion is 3x higher than free trial to contract only.", "example": "✓ Set a 14 or 30-day free trial on your listing. Couple it with PAYG pricing for the highest conversion rate."})
    scores.append({"category": "Free Trial", "score": score_free_trial(has_free_trial, has_payg)})

    if not has_payg:
        tips.append({"category": "Pay-As-You-Go Pricing", "tip": "Add PAYG pricing alongside contracts — coupling free trial with PAYG gives the highest conversion rate.", "example": "✓ Example: Add a per-user/month or per-API-call dimension so buyers can start small and scale up before committing to a contract."})
    scores.append({"category": "Pay-As-You-Go Pricing", "score": score_payg(has_payg, has_contract)})

    if not has_contract:
        tips.append({"category": "Contract Pricing", "tip": "Consider contract pricing for enterprise buyers — transition customers from PAYG to contract as relationships develop.", "example": "✓ Offer annual contract tiers (e.g. Starter / Pro / Enterprise) with volume discounts to incentivise commitment."})
    scores.append({"category": "Contract Pricing", "score": score_contract(has_contract)})

    # ── PLG: Procurement ──────────────────────────────────────────────────────
    # ── Vendor Insights — not scored, shown as static recommendation ──────────
    tips.append({"category": "Vendor Insights", "tip": "Enable Vendor Insights — security reviews delay procurement by 8–10 weeks. Vendor Insights gives buyers a dashboard of 125 security and compliance controls to speed up their review.", "example": "✓ Action: Go to Partner Central → your listing → Vendor Insights and connect your AWS account. Supports SOC 2, ISO 27001, PCI DSS, FedRAMP, HIPAA, GDPR evidence."})

    # ── SCMP — static recommendation only, not scored ────────────────────────
    if not has_scmp:
        tips.append({"category": "Standard Contract (SCMP)", "tip": "Consider using the Standard Contract for AWS Marketplace (SCMP) instead of a custom EULA — it can accelerate sales cycles by up to 80% by removing the need for buyers to involve their legal team.", "example": "✓ Action: Select SCMP when configuring your listing's contract terms. Optional addendum templates are available for enhanced security and regulatory compliance."})

    # ── Task 5.5: Add score band labels and weights to each score entry ─────
    for s in scores:
        cat = s["category"]
        s["weight"] = CATEGORY_WEIGHTS.get(cat, 1)
        # Map category names to rubric field keys for band lookup
        field_map = {"Title": "title", "Short Description": "short_description", "Highlights": "highlights"}
        field_key = field_map.get(cat)
        s["band"] = get_band_label(field_key, s["score"]) if field_key else None

    # ── Task 5.6: Weighted average for overall score ─────────────────────────
    total_weighted = sum(s["score"] * CATEGORY_WEIGHTS.get(s["category"], 1) for s in scores)
    total_weights = sum(CATEGORY_WEIGHTS.get(s["category"], 1) for s in scores)
    overall = round(total_weighted / total_weights) if total_weights > 0 else 0

    # Sort tips by score ascending (worst first)
    score_map = {s["category"]: s["score"] for s in scores}
    tips.sort(key=lambda t: score_map.get(t["category"], 50))

    # ── AI executive summary (Task 5.3: include product context) ──────────────
    summary = ""
    try:
        bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
        score_summary = "\n".join(f"- {s['category']}: {s['score']}%" for s in scores)
        tip_summary = "\n".join(f"- {t['category']}: {t['tip']}" for t in tips[:6])
        summary_prompt = f"""You are an AWS Marketplace listing advisor. Write a 3-4 sentence executive summary for a seller based on their listing effectiveness scores, benchmarked against official AWS Marketplace guidelines and PLG best practices.

{guidelines_text}

Product context: {product_context["summary"]}

Overall score: {overall}% — {"Optimised" if overall >= 85 else "Good" if overall >= 70 else "Needs Work" if overall >= 50 else "Needs Attention"}

Category scores:
{score_summary}

Top recommendations:
{tip_summary}

Write a concise, actionable summary that:
1. States the overall listing health relative to AWS Marketplace best practices in one sentence
2. Identifies the 2-3 highest priority areas to fix, referencing specific guidelines where relevant
3. Ends with one specific next action they should take today

Be direct and specific. Do not use bullet points. Do not mention AWS Marketplace by name repeatedly. Tailor advice to this product's domain ({product_context["industry"]})."""

        resp = bedrock.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,
                "temperature": 0,
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
        "product_context": product_context,
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
