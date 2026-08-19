---
id: evidence_rules
version: 0.1.0
---

# Evidence Policy

Public web evidence may be used only through Frontier web evidence tools.

## Source lifecycle

search_web:
- discovery only;
- search snippets are never verified evidence.

fetch_web_page:
- must occur before a source can support a claim;
- fetching does not itself verify a claim.

record_claim_evidence:
- records claim-level machine-assessed evidence;
- machine-supported evidence is not HUMAN_VERIFIED;
- human review remains required before canonical promotion.

## Claim discipline

Prefer atomic claims.

A claim should contain one independently assessable factual proposition whenever possible.

Do not combine a factual observation with a strategic implication in the same evidence claim.

Bad:

"Mini-grids may reach 10 MW, making the market commercially attractive."

Better FACT:

"Under the regulation, interconnected mini-grids may have installed capacity up to 10 MW per site."

Possible separate INFERENCE:

"The higher capacity ceiling may allow participation in larger projects."

## Evidence reasoning

Evidence reasoning may explain only how the fetched excerpt and its stored context
support, contradict, or fail to support the recorded claim.

Evidence reasoning must not contain:

- market attractiveness conclusions;
- commercial viability judgments;
- strategic priority;
- market-entry recommendations;
- customer targeting recommendations.

Those belong in the analytical layer as INFERENCE or ASSUMPTION.

## Time and scenario discipline

Always distinguish:

- historical fact;
- current state;
- announced target;
- project objective;
- company projection;
- independent forecast;
- policy scenario.

Scenario projections such as STEPS or NZE must be explicitly labeled as projections.

An announced project is not a completed project.
A financing target is not disbursed financing.
A company forecast is not an independently established market fact.

## Provenance

Prefer the most specific stable source URL available:

- article page;
- report page;
- regulatory document;
- dataset page;
- official project page.

Avoid using an institution homepage as evidence when a specific source page exists.

## Source quality

For important claims, prefer the original source behind a secondary article when practical.

Do not create duplicate or near-duplicate claims merely to satisfy research-quality counts.
