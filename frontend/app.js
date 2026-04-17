function escapeHtml(str) {
  if (typeof str !== 'string') return str;
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

const STEPS = {
  registration_ssl: "HTTPS Certificate",
  fulfillment_url_match: "Registration URL Match",
  registration_page: "Registration Page",
  resolve_customer: "ResolveCustomer",
  resolve_customer_history: "ResolveCustomer History (CloudTrail)",
  registration_error_handling: "Error Handling (Invalid Token)",
  get_entitlements: "GetEntitlements (Guidance)",
  meter_usage: "BatchMeterUsage (Guidance)",
  metering_history: "Metering History (CloudTrail)",
  notification_endpoint: "Notification Endpoint",
  concurrent_agreements: "Concurrent Agreements",
  eventbridge: "EventBridge Integration",
};

const STEP_DESC = {
  registration_ssl: "Validates that your registration page has a valid HTTPS certificate from a trusted certificate authority. Expired, self-signed, or soon-to-expire certificates will fail MCO review.",
  fulfillment_url_match: "Compares the registration URL you provided with the FulfillmentUrl configured in your listing to ensure they match.",
  registration_page: "Buyers are redirected here after subscribing. MCO verifies your page loads correctly and accepts the marketplace token. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-integrate-registration.html' target='_blank' style='color:#0073bb'>Docs →</a>",
  resolve_customer: "Validates the token can be exchanged for a customer identifier using the Marketplace API.",
  resolve_customer_history: "Checks CloudTrail to confirm your application is calling ResolveCustomer when buyers land on your registration page.",
  registration_error_handling: "Sends an invalid token to your registration page to verify it handles errors gracefully without crashing or exposing stack traces.",
  get_entitlements: "Your backend must call GetEntitlements after ResolveCustomer to verify the buyer's subscription. MCO checks this via internal service logs that this tool cannot access. Ensure your registration page calls GetEntitlements and stores the entitlement data. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-integrate-contract.html' target='_blank' style='color:#0073bb'>Docs →</a>",
  meter_usage: "Your backend must call BatchMeterUsage to report usage for metering-based listings. Ensure your application submits usage records with the correct dimension key and customer identifier. The Metering History check below verifies your app is calling this API. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-integrate-metering.html' target='_blank' style='color:#0073bb'>Docs →</a>",
  metering_history: "Checks CloudTrail for recent BatchMeterUsage calls from your application to confirm your backend is actively submitting usage records.",
  notification_endpoint: "Verifies your application has a configured endpoint to receive subscription lifecycle notifications via EventBridge or SNS.",
  concurrent_agreements: "Allows buyers to purchase your product multiple times within the same AWS account. Required for all new SaaS products from June 1, 2026. <a href='https://catalog.workshops.aws/mpseller/en-US/saas/integration-for-concurrent-agreements' target='_blank' style='color:#0073bb'>Integration lab →</a>",
  eventbridge: "AWS Marketplace sends subscription lifecycle events via EventBridge. Replaces SNS for new listings. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-eventbridge-integration.html' target='_blank' style='color:#0073bb'>Docs →</a>",
};

// Hide API endpoint fields if pre-configured via CloudFormation
window.addEventListener("DOMContentLoaded", () => {
  ["apiEndpoint", "apiEndpoint2"].forEach(id => {
    const el = document.getElementById(id);
    const hint = document.getElementById(id + "Hint");
    if (el && el.value && el.value.startsWith("https://") && !el.value.includes("xxxxxxxxxx")) {
      el.previousElementSibling.style.display = "none";
      el.style.display = "none";
      if (hint) hint.style.display = "block";
    }
  });
});

function showLang(btn, lang) {
  document.getElementById("code-python").style.display = lang === "python" ? "" : "none";
  document.getElementById("code-nodejs").style.display = lang === "nodejs" ? "" : "none";
  btn.parentElement.querySelectorAll("button").forEach(b => { b.style.background = "white"; b.style.color = "#333"; });
  btn.style.background = "#ff9900"; btn.style.color = "white";
}

function showLang2(btn, lang) {
  document.getElementById("code-rc-python").style.display = lang === "python" ? "" : "none";
  document.getElementById("code-rc-nodejs").style.display = lang === "nodejs" ? "" : "none";
  btn.parentElement.querySelectorAll("button").forEach(b => { b.style.background = "white"; b.style.color = "#333"; });
  btn.style.background = "#ff9900"; btn.style.color = "white";
}

function showLangEnt(btn, lang) {
  document.getElementById("code-ent-python").style.display = lang === "python" ? "" : "none";
  document.getElementById("code-ent-nodejs").style.display = lang === "nodejs" ? "" : "none";
  btn.parentElement.querySelectorAll("button").forEach(b => { b.style.background = "white"; b.style.color = "#333"; });
  btn.style.background = "#ff9900"; btn.style.color = "white";
}

function showLangMeter(btn, lang) {
  document.getElementById("code-meter-python").style.display = lang === "python" ? "" : "none";
  document.getElementById("code-meter-nodejs").style.display = lang === "nodejs" ? "" : "none";
  btn.parentElement.querySelectorAll("button").forEach(b => { b.style.background = "white"; b.style.color = "#333"; });
  btn.style.background = "#ff9900"; btn.style.color = "white";
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t, i) => t.classList.toggle("active", ["integration","scorer"][i] === name));
  document.querySelectorAll(".tab-content").forEach(t => t.classList.remove("active"));
  document.getElementById(`tab-${name}`).classList.add("active");
}

function extractToken() {
  const val = document.getElementById("redirectUrl").value.trim();
  const preview = document.getElementById("tokenPreview");
  try {
    const url = new URL(val);
    const token = url.searchParams.get("x-amzn-marketplace-token");
    preview.textContent = token ? `✓ Token found: ${token.substring(0, 40)}...` : (val ? "⚠ No x-amzn-marketplace-token found in URL" : "");
  } catch { preview.textContent = val ? "⚠ Not a valid URL" : ""; }
}

function getTokenFromUrl() {
  try { return new URL(document.getElementById("redirectUrl").value.trim()).searchParams.get("x-amzn-marketplace-token"); }
  catch { return null; }
}

function getRegistrationBaseUrl() {
  try { const u = new URL(document.getElementById("redirectUrl").value.trim()); return `${u.origin}${u.pathname}`; }
  catch { return document.getElementById("redirectUrl").value.trim(); }
}

function toggleMeteringFields() {
  document.getElementById("meteringFields").classList.toggle("hidden", document.getElementById("listingType").value === "entitlement");
}

function getStepsToRun() {
  const type = document.getElementById("listingType").value;
  const entityId = document.getElementById("entityId").value.trim();
  const steps = ["registration_ssl"];
  if (entityId) steps.push("fulfillment_url_match");
  steps.push("registration_page", "resolve_customer", "resolve_customer_history", "registration_error_handling");
  if (type !== "metering") steps.push("get_entitlements");
  if (type === "metering" || type === "both") steps.push("meter_usage", "metering_history");
  steps.push("notification_endpoint", "concurrent_agreements", "eventbridge");
  return steps;
}

function renderStep(id, state, title, detail, data) {
  const icons = { pass: "✓", fail: "✗", pending: "·", running: "", skipped: "–", warning: "!" };
  const spinner = state === "running" ? '<span class="spinner"></span>' : icons[state];
  const desc = STEP_DESC[id] ? `<p class="desc" style="font-size:12px;color:#888;margin-top:2px;margin-bottom:4px">${STEP_DESC[id]}</p>` : "";
  return `<div class="step ${state}" id="step-${id}">
    <div class="badge">${spinner}</div>
    <div class="step-content">
      <h3>${title}</h3>
      ${desc}
      ${detail ? `<p class="status">${detail}</p>` : ""}
      ${data ? `<pre>${JSON.stringify(data, null, 2)}</pre>` : ""}
    </div>
  </div>`;
}

function updateStep(id, state, detail, data) {
  const el = document.getElementById(`step-${id}`);
  if (!el) return;
  el.className = `step ${state}`;
  const icons = { pass: "✓", fail: "✗", pending: "·", running: "", skipped: "–", warning: "!" };
  el.querySelector(".badge").innerHTML = state === "running" ? '<span class="spinner"></span>' : icons[state]; // nosemgrep: insecure-document-method
  const content = el.querySelector(".step-content");
  let statusP = content.querySelector("p.status");
  if (detail) {
    if (statusP) { statusP.textContent = detail; }
    else { content.insertAdjacentHTML("beforeend", `<p class="status">${detail}</p>`); }
  }
  if (data) {
    const pre = content.querySelector("pre");
    const html = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    pre ? pre.outerHTML = html : content.insertAdjacentHTML("beforeend", html); // nosemgrep: insecure-document-method
  }
}

async function callApi(endpoint, action, payload) {
  const resp = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...payload }),
  });
  return resp.json();
}

async function detectListingType() {
  const endpoint = document.getElementById("apiEndpoint").value.trim();
  const productCode = document.getElementById("productCode").value.trim();
  const resultEl = document.getElementById("detectResult");
  if (!endpoint || !productCode) { resultEl.textContent = "⚠ Enter API Endpoint and Product Code first."; return; }

  resultEl.textContent = "Detecting...";
  try {
    const result = await callApi(endpoint, "detect_listing_type", { product_code: productCode });
    if (!result.pass) { resultEl.style.color = "#c0392b"; resultEl.textContent = `⚠ ${result.error}`; return; }

    const labels = { entitlement: "Contract-Based Pricing", metering: "Usage-Based Pricing", both: "Contract with Consumption" };
    document.getElementById("listingType").value = result.listing_type;
    toggleMeteringFields();
    resultEl.style.color = "#1d8348";
    resultEl.textContent = `✓ Detected: ${labels[result.listing_type]}`;

    // Auto-fill entity ID in scorer tab if detected
    if (result.entity_id) document.getElementById("entityId").value = result.entity_id;

    // Auto-fill metering dimensions
    if (result.dimensions && result.dimensions.length > 0) {
      const dimField = document.getElementById("meteringDimension");
      const dimContainer = dimField.parentElement;
      if (result.dimensions.length === 1) {
        dimField.value = result.dimensions[0];
        dimField.style.display = "";
        dimContainer.querySelector("select") && dimContainer.querySelector("select").remove();
      } else {
        // Replace input with select for multiple dimensions
        let sel = dimContainer.querySelector("select.dim-select");
        if (!sel) {
          sel = document.createElement("select");
          sel.className = "dim-select";
          sel.style.cssText = dimField.style.cssText;
          sel.onchange = () => { dimField.value = sel.value; };
          dimField.style.display = "none";
          dimField.parentElement.insertBefore(sel, dimField);
        }
        sel.innerHTML = result.dimensions.map(d => `<option value="${d}">${d}</option>`).join(""); // nosemgrep: insecure-document-method
        dimField.value = result.dimensions[0];
      }
    }
  } catch(e) {
    resultEl.style.color = "#c0392b";
    resultEl.textContent = `⚠ Request failed: ${e.message}`;
  }
}

async function runTests() {
  const endpoint = document.getElementById("apiEndpoint").value.trim();
  const productCode = document.getElementById("productCode").value.trim();
  const redirectUrl = document.getElementById("redirectUrl").value.trim();
  const token = getTokenFromUrl();
  const registrationUrl = getRegistrationBaseUrl();
  const dimension = document.getElementById("meteringDimension").value.trim();
  const quantity = document.getElementById("meteringQuantity").value;

  if (!endpoint || !productCode || !redirectUrl) { alert("Please fill in API Endpoint, Product Code, and the Registration Redirect URL."); return; }
  if (!token) { alert("Could not find x-amzn-marketplace-token in the redirect URL."); return; }

  const steps = getStepsToRun();
  const btn = document.getElementById("runBtn");
  btn.disabled = true; btn.textContent = "Running...";

  const resultsCard = document.getElementById("resultsCard");
  const resultsEl = document.getElementById("results");
  resultsCard.classList.remove("hidden");
  resultsEl.innerHTML = steps.map(s => renderStep(s, "pending", STEPS[s], "Waiting...")).join(""); // nosemgrep: insecure-document-method
  resultsCard.scrollIntoView({ behavior: "smooth" });
  let customerIdentifier = null;
  let customerAWSAccountId = null;

  for (const step of steps) {
    updateStep(step, "running", "Running...");
    try {
      let result;
      if (step === "registration_ssl") {
        result = await callApi(endpoint, "check_registration_ssl", { registration_page_url: registrationUrl });
        if (result.pass) {
          updateStep(step, "pass", result.note, { issuer: result.issuer, expiry_date: result.expiry_date, days_until_expiry: result.days_until_expiry });
        } else {
          updateStep(step, "fail", result.note || result.error, result.issuer ? { issuer: result.issuer, expiry_date: result.expiry_date, is_self_signed: result.is_self_signed } : null);
        }

      } else if (step === "fulfillment_url_match") {
        const entityId = document.getElementById("entityId").value.trim();
        result = await callApi(endpoint, "check_fulfillment_url_match", { registration_page_url: registrationUrl, entity_id: entityId });
        const fmState = result.pass ? "pass" : "warning";
        updateStep(step, fmState, result.note, { listing_url: result.listing_url, provided_url: result.provided_url });
        if (!result.pass) continue;

      } else if (step === "registration_page") {
        result = await callApi(endpoint, "check_registration_page", { registration_page_url: registrationUrl, registration_token: token });
        updateStep(step, result.pass ? "pass" : "fail", result.note || result.error, { status_code: result.status_code, final_url: result.final_url });

      } else if (step === "resolve_customer") {
        result = await callApi(endpoint, "resolve_customer", { registration_token: token });
        if (result.pass) {
          customerIdentifier = result.customer_identifier;
          customerAWSAccountId = result.customer_aws_account_id;
        }
        updateStep(step, result.pass ? "pass" : "fail", result.pass ? "Customer resolved successfully" : result.error,
          result.pass ? { customer_identifier: result.customer_identifier, customer_aws_account_id: result.customer_aws_account_id, product_code: result.product_code } : null);

      } else if (step === "resolve_customer_history") {
        result = await callApi(endpoint, "check_resolve_customer_history", {});
        const rchState = result.pass ? "pass" : "warning";
        updateStep(step, rchState, result.note || result.error,
          result.pass ? { calls_last_7_days: result.count } : null);
        if (!result.pass && result.code_example) {
          const el = document.getElementById(`step-resolve_customer_history`);
          if (el) {
            el.querySelector(".step-content").insertAdjacentHTML("beforeend", `
              <div style="margin-top:10px">
                <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#555">Example implementation:</div>
                <div style="display:flex;gap:8px;margin-bottom:6px">
                  <button onclick="showLang2(this,'python')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:#ff9900;color:white">Python</button>
                  <button onclick="showLang2(this,'nodejs')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:white;color:#333">Node.js</button>
                </div>
                <pre id="code-rc-python" style="font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">${result.code_example.python}</pre>
                <pre id="code-rc-nodejs" style="display:none;font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">${result.code_example.nodejs}</pre>
              </div>`);
          }
        }
        continue;

      } else if (step === "registration_error_handling") {
        result = await callApi(endpoint, "check_registration_error_handling", { registration_page_url: registrationUrl });
        let ehState;
        if (result.pass) {
          ehState = "pass";
        } else if (result.has_stack_trace) {
          ehState = "warning";
        } else if (result.status_code >= 500) {
          ehState = "fail";
        } else {
          ehState = "fail";
        }
        updateStep(step, ehState, result.note || result.error,
          result.pass
            ? { status_code: result.status_code, has_error_message: result.has_error_message, note: result.note }
            : { status_code: result.status_code, has_stack_trace: result.has_stack_trace, response_snippet: result.response_snippet, note: result.note });

      } else if (step === "get_entitlements") {
        // Guidance-only step — do not call GetEntitlements (MCO checks this via internal logs)
        const listingType = document.getElementById("listingType").value;
        if (listingType === "metering") {
          updateStep(step, "skipped", "Not applicable for metering-only listings.");
          continue;
        }
        updateStep(step, "warning",
          "Action required: your backend must call GetEntitlements after ResolveCustomer. MCO verifies this via internal service logs that this tool cannot access.",
          null);
        const el = document.getElementById(`step-get_entitlements`);
        if (el) {
          el.querySelector(".step-content").insertAdjacentHTML("beforeend", `
            <div style="margin-top:10px">
              <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#555">Your backend must implement this:</div>
              <div style="display:flex;gap:8px;margin-bottom:6px">
                <button onclick="showLangEnt(this,'python')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:#ff9900;color:white">Python</button>
                <button onclick="showLangEnt(this,'nodejs')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:white;color:#333">Node.js</button>
              </div>
              <pre id="code-ent-python" style="font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">import boto3

client = boto3.client('marketplace-entitlement', region_name='us-east-1')

# Call this after ResolveCustomer returns the customer identifier
response = client.get_entitlements(
    ProductCode='YOUR_PRODUCT_CODE',
    Filter={'CUSTOMER_IDENTIFIER': [customer_identifier]}
)

for entitlement in response['Entitlements']:
    dimension = entitlement['Dimension']
    value = entitlement['Value']
    expiration = entitlement.get('ExpirationDate')
    # Store entitlement data and provision access accordingly</pre>
              <pre id="code-ent-nodejs" style="display:none;font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">const { MarketplaceEntitlementServiceClient, GetEntitlementsCommand } = require('@aws-sdk/client-marketplace-entitlement-service');

const client = new MarketplaceEntitlementServiceClient({ region: 'us-east-1' });

// Call this after ResolveCustomer returns the customer identifier
const response = await client.send(new GetEntitlementsCommand({
  ProductCode: 'YOUR_PRODUCT_CODE',
  Filter: { CUSTOMER_IDENTIFIER: [customerIdentifier] }
}));

for (const entitlement of response.Entitlements) {
  const { Dimension, Value, ExpirationDate } = entitlement;
  // Store entitlement data and provision access accordingly
}</pre>
            </div>`);
        }
        continue;

      } else if (step === "meter_usage") {
        // Guidance-only step — do not call BatchMeterUsage (circular test with listing's own dimensions)
        updateStep(step, "warning",
          "Action required: your backend must call BatchMeterUsage to report usage. The Metering History check verifies your app is calling this API via CloudTrail.",
          null);
        const el = document.getElementById(`step-meter_usage`);
        if (el) {
          el.querySelector(".step-content").insertAdjacentHTML("beforeend", `
            <div style="margin-top:10px">
              <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#555">Your backend must implement this:</div>
              <div style="display:flex;gap:8px;margin-bottom:6px">
                <button onclick="showLangMeter(this,'python')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:#ff9900;color:white">Python</button>
                <button onclick="showLangMeter(this,'nodejs')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:white;color:#333">Node.js</button>
              </div>
              <pre id="code-meter-python" style="font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">import boto3
from datetime import datetime

client = boto3.client('meteringmarketplace', region_name='us-east-1')

response = client.batch_meter_usage(
    ProductCode='YOUR_PRODUCT_CODE',
    UsageRecords=[{
        'Timestamp': datetime.utcnow(),
        'CustomerAWSAccountId': 'CUSTOMER_AWS_ACCOUNT_ID',
        'Dimension': 'YOUR_DIMENSION_KEY',
        'Quantity': 1,
    }]
)
print(response['Results'][0]['Status'])  # Should be 'Success'</pre>
              <pre id="code-meter-nodejs" style="display:none;font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">const { MarketplaceMeteringClient, BatchMeterUsageCommand } = require('@aws-sdk/client-marketplace-metering');

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
console.log(response.Results[0].Status); // Should be 'Success'</pre>
            </div>`);
        }
        continue;

      } else if (step === "metering_history") {
        result = await callApi(endpoint, "check_metering_history", { product_code: productCode });
        const mhState = result.pass ? "pass" : "warning";
        let mhData = result.pass ? { calls_last_7_days: result.count, recent: result.recent_calls } : null;
        updateStep(step, mhState, result.note || result.error, mhData);
        // Show code example if no history found
        if (!result.pass && result.code_example) {
          const el = document.getElementById(`step-metering_history`);
          if (el) {
            el.querySelector(".step-content").insertAdjacentHTML("beforeend", `
              <div style="margin-top:10px">
                <div style="font-size:12px;font-weight:600;margin-bottom:6px;color:#555">Example implementation:</div>
                <div style="display:flex;gap:8px;margin-bottom:6px">
                  <button onclick="showLang(this,'python')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:#ff9900;color:white">Python</button>
                  <button onclick="showLang(this,'nodejs')" style="font-size:11px;padding:2px 8px;border:1px solid #ccc;border-radius:3px;cursor:pointer;background:white;color:#333">Node.js</button>
                </div>
                <pre id="code-python" style="font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">${result.code_example.python}</pre>
                <pre id="code-nodejs" style="display:none;font-size:11px;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;overflow-x:auto;white-space:pre">${result.code_example.nodejs}</pre>
              </div>`);
          }
        }
        continue;

      } else if (step === "notification_endpoint") {
        result = await callApi(endpoint, "check_notification_endpoint", {});
        updateStep(step, result.pass ? "pass" : "warning", result.note || result.error,
          result.pass ? { method: result.method } : null);
        continue;

      } else if (step === "concurrent_agreements") {
        const entityId = document.getElementById("entityId").value.trim();
        if (!entityId) { updateStep(step, "skipped", "Skipped — enter your Product ID in the Listing Effectiveness tab to check Concurrent Agreements"); continue; }
        result = await callApi(endpoint, "check_concurrent_agreements", { entity_id: entityId });
        updateStep(step, result.pass ? "pass" : "fail", result.note || result.error, null);

      } else if (step === "eventbridge") {
        result = await callApi(endpoint, "check_eventbridge", {});
        // EventBridge is a warning not a hard fail — SNS still works for existing listings
        const ebState = result.pass ? "pass" : "warning";
        updateStep(step, ebState, result.note || result.error,
          result.pass ? { rules: result.rule_names } : null);
        continue;
      }
    } catch (e) {
      updateStep(step, "fail", `Request failed: ${e.message}`);
    }
  }

  btn.disabled = false; btn.textContent = "Run Integration Tests";

  // Summary — insert at top of results card
  const allSteps = steps.map(s => document.getElementById(`step-${s}`));
  const passed = allSteps.filter(el => el?.classList.contains("pass")).length;
  const failed = allSteps.filter(el => el?.classList.contains("fail")).length;
  const warned = allSteps.filter(el => el?.classList.contains("warning")).length;
  const skipped = allSteps.filter(el => el?.classList.contains("skipped")).length;

  const failMessages = {
    registration_ssl: "Your registration page's HTTPS certificate is invalid, expired, or self-signed. Use a trusted CA certificate (e.g. ACM, Let's Encrypt).",
    fulfillment_url_match: "The registration URL you provided does not match the FulfillmentUrl in your listing. Ensure they are the same.",
    registration_page: "Your registration page is not loading correctly. MCO will fail this check — ensure the page is publicly accessible via HTTPS and accepts the marketplace token parameter. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-integrate-registration.html' target='_blank'>See docs →</a>",
    resolve_customer: "ResolveCustomer failed. This is a critical MCO requirement — your backend must call this API with the token immediately after the buyer lands on your registration page. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-integrate-registration.html#saas-resolve-customer' target='_blank'>See docs →</a>",
    registration_error_handling: "Your registration page crashes or exposes error details when given an invalid token. Catch exceptions from ResolveCustomer and return a user-friendly error page instead of a stack trace or 500 error.",
    concurrent_agreements: "Concurrent Agreements is not enabled. This is required for all new SaaS products from June 1, 2026. Complete the integration and opt in via Partner Central. <a href='https://catalog.workshops.aws/mpseller/en-US/saas/integration-for-concurrent-agreements' target='_blank'>Integration lab →</a>",
    eventbridge: "No EventBridge rules found for AWS Marketplace events. SNS is being replaced by EventBridge — configure rules for aws.agreement-marketplace events to receive subscription notifications. <a href='https://docs.aws.amazon.com/marketplace/latest/userguide/saas-eventbridge-integration.html' target='_blank'>See docs →</a>",
  };

  const failedSteps = steps.filter(s => document.getElementById(`step-${s}`)?.classList.contains("fail"));
  const failDetails = failedSteps.map(s => `<li>${failMessages[s] || s}</li>`).join("");

  const allPassed = failed === 0;
  const readyBadge = allPassed
    ? '<span style="display:inline-block;background:#1d8348;color:white;padding:4px 12px;border-radius:12px;font-size:13px;font-weight:600">✓ Ready</span>'
    : '<span style="display:inline-block;background:#c0392b;color:white;padding:4px 12px;border-radius:12px;font-size:13px;font-weight:600">✗ Not Ready</span>';
  const summaryColor = allPassed ? "#1d8348" : "#c0392b";
  const summaryBg = allPassed ? "#f0faf4" : "#fdf3f2";
  const summaryBorder = allPassed ? "#1d8348" : "#c0392b";

  const countsHtml = `<p style="font-size:13px;color:#555;margin:8px 0">${passed} passed, ${failed} failed, ${warned} warning${warned !== 1 ? "s" : ""}, ${skipped} skipped</p>`;
  const warningNote = warned > 0 ? `<p style="font-size:12px;color:#d68910;margin-top:6px">⚠ Warnings don't block MCO review but should be addressed.</p>` : "";

  const retryBtn = failed > 0 ? `<button class="primary" id="retryFailedBtn" onclick="retryFailed()" style="margin-top:12px;background:#c0392b;font-size:13px;padding:8px 16px">↻ Retry Failed Steps</button>` : "";

  const summaryHtml = `
    <div id="test-summary" style="border:1px solid ${summaryBorder};background:${summaryBg};border-radius:8px;padding:20px;margin-bottom:16px">
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
        <h3 style="font-size:15px;font-weight:600;color:${summaryColor};margin:0">MCO Readiness</h3>
        ${readyBadge}
      </div>
      ${countsHtml}
      ${warningNote}
      ${allPassed
        ? `<p style="font-size:13px;color:#555;margin-bottom:14px">Your SaaS listing integration is working correctly. Follow these steps to request your listing goes live:</p>
           <ol style="font-size:13px;color:#555;padding-left:18px;line-height:2">
             <li>Go to the <a href="https://us-east-1.console.aws.amazon.com/partnercentral/dashboard" target="_blank" style="color:#0073bb">AWS Partner Central</a> and open your listing</li>
             <li>Verify all listing details are complete — title, description, highlights, pricing, and support information</li>
             <li>Click <strong>Submit for review</strong> on your listing page</li>
             <li>MCO will review your submission — typical turnaround is <strong>3–5 business days</strong></li>
             <li>You will receive an email notification when your listing is approved or if changes are required</li>
             <li>Once approved, your listing status will change from <strong>Limited</strong> to <strong>Live</strong></li>
           </ol>
           <p style="font-size:12px;color:#888;margin-top:12px">💡 Tip: Run the <strong>Listing Effectiveness</strong> tab before submitting to maximise your listing's discoverability and conversion rate.</p>`
        : `<p style="font-size:13px;color:#555;margin-bottom:10px">Fix the following issues before submitting for MCO review:</p><ul style="font-size:13px;color:#555;padding-left:18px;line-height:1.8">${failDetails}</ul>${retryBtn}`
      }
    </div>`;

  // Enhancement 3: Export toolbar for integration test results
  const toolbarHtml = `
    <div class="toolbar" id="integration-toolbar">
      <button onclick="exportIntegrationReport()">⬇ Export report</button>
      <button onclick="copyIntegrationReport()">⎘ Copy to clipboard</button>
    </div>`;

  resultsEl.insertAdjacentHTML("afterbegin", toolbarHtml);
  resultsEl.insertAdjacentHTML("afterbegin", summaryHtml);
}

// Enhancement 3: Export and copy integration test results
function _collectIntegrationResults() {
  const stepEls = document.querySelectorAll("#results .step");
  const lines = ["AWS Marketplace Integration Test Report", `Date: ${new Date().toISOString()}`, ""];
  stepEls.forEach(el => {
    const title = el.querySelector("h3")?.textContent || "Unknown";
    const status = el.classList.contains("pass") ? "PASS" : el.classList.contains("fail") ? "FAIL" : el.classList.contains("warning") ? "WARNING" : el.classList.contains("skipped") ? "SKIPPED" : "PENDING";
    const note = el.querySelector("p.status")?.textContent || "";
    lines.push(`[${status}] ${title}`);
    if (note) lines.push(`  ${note}`);
    lines.push("");
  });
  return lines.join("\n");
}

function exportIntegrationReport() {
  const text = _collectIntegrationResults();
  const blob = new Blob([text], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `mp-integration-report-${new Date().toISOString().slice(0,10)}.txt`;
  a.click();
}

function copyIntegrationReport() {
  const text = _collectIntegrationResults();
  navigator.clipboard.writeText(text).then(() => {
    const btn = event.target;
    const orig = btn.textContent;
    btn.textContent = "✓ Copied!";
    setTimeout(() => btn.textContent = orig, 2000);
  });
}

// Enhancement 4: Retry failed steps
async function retryFailed() {
  const endpoint = document.getElementById("apiEndpoint").value.trim();
  const productCode = document.getElementById("productCode").value.trim();
  const token = getTokenFromUrl();
  const registrationUrl = getRegistrationBaseUrl();
  const dimension = document.getElementById("meteringDimension").value.trim();
  const quantity = document.getElementById("meteringQuantity").value;

  // Collect all failed step IDs
  const failedEls = document.querySelectorAll("#results .step.fail");
  const failedIds = Array.from(failedEls).map(el => el.id.replace("step-", ""));
  if (failedIds.length === 0) return;

  const btn = document.getElementById("retryFailedBtn");
  if (btn) { btn.disabled = true; btn.textContent = "Retrying..."; }

  // Re-read customerIdentifier from a previous pass if available
  let customerIdentifier = null;
  let customerAWSAccountId = null;
  const rcStep = document.getElementById("step-resolve_customer");
  if (rcStep && rcStep.classList.contains("pass")) {
    try {
      const preData = JSON.parse(rcStep.querySelector("pre")?.textContent || "{}");
      customerIdentifier = preData.customer_identifier;
      customerAWSAccountId = preData.customer_aws_account_id;
    } catch {}
  }

  for (const step of failedIds) {
    updateStep(step, "running", "Retrying...");
    try {
      let result;
      if (step === "registration_ssl") {
        result = await callApi(endpoint, "check_registration_ssl", { registration_page_url: registrationUrl });
        if (result.pass) {
          updateStep(step, "pass", result.note, { issuer: result.issuer, expiry_date: result.expiry_date, days_until_expiry: result.days_until_expiry });
        } else {
          updateStep(step, "fail", result.note || result.error, null);
        }
      } else if (step === "fulfillment_url_match") {
        const entityId = document.getElementById("entityId").value.trim();
        result = await callApi(endpoint, "check_fulfillment_url_match", { registration_page_url: registrationUrl, entity_id: entityId });
        updateStep(step, result.pass ? "pass" : "warning", result.note, null);
      } else if (step === "registration_page") {
        result = await callApi(endpoint, "check_registration_page", { registration_page_url: registrationUrl, registration_token: token });
        updateStep(step, result.pass ? "pass" : "fail", result.note || result.error, { status_code: result.status_code });
      } else if (step === "resolve_customer") {
        result = await callApi(endpoint, "resolve_customer", { registration_token: token });
        if (result.pass) { customerIdentifier = result.customer_identifier; customerAWSAccountId = result.customer_aws_account_id; }
        updateStep(step, result.pass ? "pass" : "fail", result.pass ? "Customer resolved successfully" : result.error, result.pass ? { customer_identifier: result.customer_identifier } : null);
      } else if (step === "registration_error_handling") {
        result = await callApi(endpoint, "check_registration_error_handling", { registration_page_url: registrationUrl });
        const ehState = result.pass ? "pass" : (result.has_stack_trace ? "warning" : "fail");
        updateStep(step, ehState, result.note || result.error, null);
      } else if (step === "meter_usage") {
        updateStep(step, "warning", "Guidance step — no retry needed");
      } else if (step === "concurrent_agreements") {
        const entityId = document.getElementById("entityId").value.trim();
        if (!entityId) { updateStep(step, "skipped", "Skipped — no Product ID"); continue; }
        result = await callApi(endpoint, "check_concurrent_agreements", { entity_id: entityId });
        updateStep(step, result.pass ? "pass" : "fail", result.note || result.error, null);
      } else {
        updateStep(step, "fail", "Retry not supported for this step");
      }
    } catch (e) {
      updateStep(step, "fail", `Retry failed: ${e.message}`);
    }
  }

  if (btn) { btn.disabled = false; btn.textContent = "↻ Retry Failed Steps"; }

  // Update summary counts
  const allStepEls = document.querySelectorAll("#results .step");
  const newPassed = document.querySelectorAll("#results .step.pass").length;
  const newFailed = document.querySelectorAll("#results .step.fail").length;
  const newWarned = document.querySelectorAll("#results .step.warning").length;
  const newSkipped = document.querySelectorAll("#results .step.skipped").length;
  const summaryEl = document.getElementById("test-summary");
  if (summaryEl && newFailed === 0) {
    summaryEl.style.borderColor = "#1d8348";
    summaryEl.style.background = "#f0faf4";
    summaryEl.innerHTML = `<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px"><h3 style="font-size:15px;font-weight:600;color:#1d8348;margin:0">MCO Readiness</h3><span style="display:inline-block;background:#1d8348;color:white;padding:4px 12px;border-radius:12px;font-size:13px;font-weight:600">✓ Ready</span></div><p style="font-size:13px;color:#555">${newPassed} passed, 0 failed, ${newWarned} warning${newWarned !== 1 ? "s" : ""}, ${newSkipped} skipped</p>${newWarned > 0 ? '<p style="font-size:12px;color:#d68910;margin-top:6px">⚠ Warnings don\'t block MCO review but should be addressed.</p>' : ''}`; // nosemgrep: insecure-document-method
  }
}

async function scoreListing() {
  const endpoint = document.getElementById("apiEndpoint2").value.trim();
  const entityId = document.getElementById("entityId").value.trim();
  if (!endpoint || !entityId) { alert("Please fill in the API Endpoint and Product ID."); return; }

  const btn = document.getElementById("scoreBtn");
  btn.disabled = true; btn.textContent = "Scoring...";

  const resultsEl = document.getElementById("scoreResults");
  resultsEl.classList.remove("hidden");
  resultsEl.innerHTML = '<p style="color:#666;font-size:13px">Fetching listing data and running AI analysis...</p>'; // nosemgrep: insecure-document-method

  try {
    const result = await callApi(endpoint, "score_listing", { entity_id: entityId });
    if (!result.pass) { resultsEl.innerHTML = `<p style="color:#c0392b">${escapeHtml(result.error)}</p>`; return; } // nosemgrep: insecure-document-method

    window._lastScoreResult = result;
    window._lastEntityId = entityId;
    window._lastEndpoint = endpoint;
    renderScoreResults(result, entityId);
  } catch(e) {
    resultsEl.innerHTML = `<p style="color:#c0392b">Request failed: ${escapeHtml(e.message)}</p>`; // nosemgrep: insecure-document-method
  }

  btn.disabled = false; btn.textContent = "Score My Listing";
}

function renderScoreResults(result, entityId) {
  const s = result.overall_score;
  const cls = s >= 75 ? "high" : s >= 50 ? "mid" : "low";
  const bandLabel = s >= 85 ? "Optimised" : s >= 70 ? "Good" : s >= 50 ? "Needs Work" : "Needs Attention";
  const bandDesc = s >= 85
    ? "Your listing is in great shape. Content is strong, PLG features are in place, and you're well positioned to be discovered and convert buyers."
    : s >= 70
    ? "Your listing is solid with a few areas to improve. Addressing the recommendations below will help you stand out and convert more buyers."
    : s >= 50
    ? "Your listing has gaps that are likely affecting how buyers find and evaluate your product. Work through the recommendations below to improve discoverability and conversion."
    : "Your listing needs significant improvement before it can compete effectively. Start with the highest priority recommendations below.";
  const saved = JSON.parse(localStorage.getItem("mp-tester-done") || "[]");

  const bars = result.scores.map(sc => {
    const c = sc.score >= 75 ? "high" : sc.score >= 50 ? "mid" : "low";
    const bandText = sc.band ? ` — ${sc.band}` : "";
    const weightText = sc.weight ? `<span style="font-size:11px;color:#999;margin-left:4px" title="Weight: ${sc.weight}">×${sc.weight}</span>` : "";
    return `<div class="score-bar-row">
      <div class="score-bar-label">${sc.category}${weightText}</div>
      <div class="score-bar-track"><div class="score-bar-fill ${c}" style="width:${sc.score}%"></div></div>
      <div class="score-bar-pct">${sc.score}%${bandText}</div>
    </div>`;
  }).join("");

  const ammpLinks = {
    "Title": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Description": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Highlights": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "SEO / Keywords": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Search Keywords": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Media / Videos": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Free Trial": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Vendor Insights": "https://partnercentral.awspartner.com/partnercentral2/s/vendor-insights",
    "Standard Contract (SCMP)": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Quick Launch": "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard",
    "Reviews (G2 / Peerspot)": "https://www.g2.com/",
  };

  const rewritableFields = { "Title": "title", "Short Description": "description", "Highlights": "highlights", "Long Description": "long_description", "Search Keywords": "keywords" };

  const tips = result.tips.map((t, i) => {
    const isDone = saved.includes(`${entityId}-${t.category}`);
    const rewriteField = rewritableFields[t.category];
    const ammpUrl = ammpLinks[t.category] || "https://us-east-1.console.aws.amazon.com/partnercentral/dashboard";
    const perHighlight = (t.per_highlight && Array.isArray(t.per_highlight))
      ? t.per_highlight.filter(h => h.feedback).map(h =>
          `<div style="margin:6px 0 6px 24px;padding:6px 10px;background:#fff5e6;border-left:2px solid #d68910;border-radius:0 4px 4px 0;font-size:12px">
            <span style="font-weight:600;color:#232f3e">Highlight ${h.index + 1}:</span> <span style="color:#555">${escapeHtml(h.text)}</span>
            <div style="margin-top:3px;color:#8a6d3b">↳ ${escapeHtml(h.feedback)}</div>
          </div>`
        ).join("")
      : "";
    return `<div class="tip-item ${isDone ? 'done' : ''}" id="tip-${i}">
      <div style="display:flex;align-items:flex-start">
        <input type="checkbox" class="tip-check" ${isDone ? 'checked' : ''} onchange="toggleDone('${entityId}','${t.category}',${i},this.checked)" />
        <div style="flex:1">
          <strong>${t.category} <a class="ammp-link" href="${ammpUrl}" target="_blank">Fix in AMMP →</a></strong>
          ${escapeHtml(t.tip)}
          ${t.example ? `<pre class="example">${escapeHtml(t.example)}</pre>` : ""}
          ${perHighlight}
          ${rewriteField ? `<button class="rewrite-btn" onclick="rewriteField('${rewriteField}',${i})">✨ ${rewriteField === 'keywords' ? 'Suggest keywords' : 'Suggest rewrite'}</button><div id="rewrite-${i}"></div>` : ""}
        </div>
      </div>
    </div>`;
  }).join("");

  const resultsEl = document.getElementById("scoreResults");
  resultsEl.innerHTML = ` // nosemgrep: insecure-document-method
    <div class="score-hero">
      <div class="score-circle ${cls}">${s}</div>
      <div class="score-label" style="font-weight:600;font-size:14px;margin-bottom:4px">${escapeHtml(result.product_title) || entityId} — ${bandLabel}</div>
      <div class="score-label">${bandDesc}</div>
    </div>
    ${result.summary ? `<p style="font-size:14px;line-height:1.7;color:#333;margin:16px 0;padding:16px;background:#f8f9fa;border-radius:6px;border-left:4px solid #ff9900">${escapeHtml(result.summary)}</p>` : ""}
    <div class="toolbar">
      <button onclick="rescoreListing()">↻ Re-score</button>
      <button onclick="exportReport()">⬇ Export report</button>
      <button onclick="copyReport()">⎘ Copy to clipboard</button>
      <button onclick="toggleScoringLegend()" id="legendBtn" style="position:relative">ⓘ Scoring guide</button>
    </div>
    <div id="scoringLegend" style="display:none;background:#f8f9fa;border:1px solid #e0e0e0;border-radius:6px;padding:14px 16px;margin-bottom:16px;font-size:12px;line-height:1.7;color:#555">
      <div style="display:flex;gap:24px;flex-wrap:wrap">
        <div style="flex:1;min-width:200px">
          <strong style="color:#232f3e;font-size:13px">Score Bands</strong>
          <div style="margin-top:4px">
            <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#c0392b;margin-right:4px"></span>0–29: Needs Attention<br>
            <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#d68910;margin-right:4px"></span>30–59: Fair<br>
            <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#1d8348;margin-right:4px"></span>60–79: Good<br>
            <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#1d8348;margin-right:4px"></span>80–100: Optimised
          </div>
        </div>
        <div style="flex:1;min-width:200px">
          <strong style="color:#232f3e;font-size:13px">Category Weights</strong>
          <div style="margin-top:4px">
            The ×N value next to each category shows its weight. Higher weight means more impact on your overall score. For example, Title (×10) affects your score more than Categories (×3). The overall score is a weighted average of all categories.
          </div>
        </div>
      </div>
    </div>
    <div class="score-bars">${bars}</div>
    ${tips ? `<h2 style="font-size:15px;font-weight:600;margin:20px 0 12px;color:#232f3e">Recommendations</h2>${tips}` : '<p style="color:#1d8348;font-size:13px;margin-top:16px">✓ No recommendations — your listing looks great!</p>'}
  `;
}

function toggleScoringLegend() {
  const el = document.getElementById("scoringLegend");
  if (el) el.style.display = el.style.display === "none" ? "block" : "none";
}

function toggleDone(entityId, category, idx, checked) {
  const key = "mp-tester-done";
  const id = `${entityId}-${category}`;
  let saved = JSON.parse(localStorage.getItem(key) || "[]");
  saved = checked ? [...new Set([...saved, id])] : saved.filter(x => x !== id);
  localStorage.setItem(key, JSON.stringify(saved));
  document.getElementById(`tip-${idx}`).classList.toggle("done", checked);
}

async function rewriteField(field, tipIdx) {
  const endpoint = window._lastEndpoint;
  const result = window._lastScoreResult;
  const container = document.getElementById(`rewrite-${tipIdx}`);
  container.innerHTML = '<span style="font-size:12px;color:#666">Generating rewrite...</span>'; // nosemgrep: insecure-document-method

  const context = `Title: ${result.product_title}`;
  const currentMap = {
    title: result.product_title || "",
    description: result.short_description || "",
    highlights: JSON.stringify(result.highlights || []),
    long_description: result.long_description || "",
    keywords: (result.keywords || []).join(", "),
  };

  try {
    const r = await callApi(endpoint, "rewrite_field", { field, current: currentMap[field] || "", context });
    if (!r.pass) { container.innerHTML = `<p style="color:#c0392b;font-size:12px">${escapeHtml(r.error)}</p>`; return; } // nosemgrep: insecure-document-method
    container.innerHTML = `<div class="rewrite-output">${escapeHtml(r.rewrite)}</div> // nosemgrep: insecure-document-method
      <button class="rewrite-copy" onclick="navigator.clipboard.writeText(this.previousElementSibling.textContent);this.textContent='Copied!'">Copy</button>`;
  } catch(e) {
    container.innerHTML = `<p style="color:#c0392b;font-size:12px">Failed: ${e.message}</p>`; // nosemgrep: insecure-document-method
  }
}

async function rescoreListing() {
  document.getElementById("scoreResults").innerHTML = '<p style="color:#666;font-size:13px">Re-scoring...</p>'; // nosemgrep: insecure-document-method
  const endpoint = window._lastEndpoint;
  const entityId = window._lastEntityId;
  try {
    const result = await callApi(endpoint, "score_listing", { entity_id: entityId });
    window._lastScoreResult = result;
    renderScoreResults(result, entityId);
  } catch(e) {
    document.getElementById("scoreResults").innerHTML = `<p style="color:#c0392b">Failed: ${escapeHtml(e.message)}</p>`; // nosemgrep: insecure-document-method
  }
}

function exportReport() {
  const result = window._lastScoreResult;
  if (!result) return;
  const formatScore = (s) => {
    let text = `${s.category}: ${s.score}%`;
    if (s.band) text += ` (${s.band})`;
    if (s.weight) text += ` [Weight: ${s.weight}]`;
    return text;
  };
  const lines = [
    `AWS Marketplace Listing Effectiveness Report`,
    `Product: ${result.product_title}`,
    `Overall Score: ${result.overall_score}%`,
    ``,
    result.summary || "",
    ``,
    `SCORES`,
    ...result.scores.map(formatScore),
    ``,
    `RECOMMENDATIONS`,
    ...result.tips.map(t => {
      let entry = `[${t.category}]\n${t.tip}${t.example ? '\n' + t.example : ''}`;
      if (t.per_highlight && Array.isArray(t.per_highlight)) {
        const highlights = t.per_highlight.filter(h => h.feedback).map(h => `  - Highlight ${h.index + 1} ("${h.text}"): ${h.feedback}`);
        if (highlights.length) entry += '\n' + highlights.join('\n');
      }
      return entry;
    }),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `mp-listing-report-${result.product_title?.replace(/[^a-zA-Z0-9-_ ]/g, "").replace(/\s+/g,"-") || "report"}.txt`;
  a.click();
}

function copyReport() {
  const result = window._lastScoreResult;
  if (!result) return;
  const formatScore = (s) => {
    let text = `${s.category}: ${s.score}%`;
    if (s.band) text += ` (${s.band})`;
    if (s.weight) text += ` [Weight: ${s.weight}]`;
    return text;
  };
  const lines = [
    `AWS Marketplace Listing Effectiveness Report`,
    `Product: ${result.product_title} | Score: ${result.overall_score}%`,
    ``,
    result.summary || "",
    ``,
    ...result.scores.map(formatScore),
    ``,
    ...result.tips.map(t => `• ${t.category}: ${t.tip}`),
  ];
  navigator.clipboard.writeText(lines.join("\n")).then(() => {
    const btn = event.target;
    btn.textContent = "✓ Copied!";
    setTimeout(() => btn.textContent = "⎘ Copy to clipboard", 2000);
  });
}
