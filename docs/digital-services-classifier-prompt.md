# Digital Services - AI Contract Classifier: Prompt, Inputs, Output & Assumptions

**For expert review.** This document describes exactly how the "Digital Services
Analysis" pages on databook.nyc classify NYC technology contracts. Everything
below is editorial/AI-derived enrichment layered on top of official, normalized
government data - it is **a prompt to investigate, not a determination**. We are
seeking feedback on whether the prompt, the inputs it relies on, and the outputs
it produces are sound enough to publish and to inform renewal decisions.

- **Where it runs:** an offline batch job over contracts held by vendors tagged
  `digital_services`. Results are stored and read by the public pages; a human
  `curated` override is never overwritten by re-runs.
- **Model / settings:** Google **Gemini 3.5 Flash**, `temperature = 0`, forced
  JSON output, ~20 contracts per request.
- **Source code:** `api/classify_digital_contracts.py`.
- **Status:** v2 - the classifier now reads **richer, multi-source scope text**
  (see Sec.1), not just the contract title. This directly addresses the biggest
  v1 critique. ~639 expiring-before-2030 contracts are classified today.

---

## 1. What the model sees (tiered inputs)

The model no longer judges from a bare title. For each contract we assemble the
best available description by joining four official, already-normalized sources,
and the prompt tells the model to **weigh them in priority order** (richest first):

| Priority | Field(s) given to model | Source (all official NYC data) | How joined | Coverage* |
|---|---|---|---|---|
| 1 | `contract_purpose`, `expense_category` | **Checkbook NYC** (`checkbook_contract_meta`) | by normalized contract ID | **~88%** |
| 2 | `scope_description`, `notice_category`, `selection_method`, `special_case_reason` | **City Record / CROL** notice for the PIN (longest description wins) | by PIN/EPIN | subset |
| 3 | `commodity` (Main Commodity), `solicitation_name` | **PASSPort solicitations** | EPIN-prefix crosswalk | ~8% |
| 4 | `contract_title`, `program`, `industry`, `vendor_name`, `agency` | **PASSPort / MOCS** contracts | base record | 100% |
| context | `contract_type`, `term`, `award_amount` vs `current_amount`, `status`, `procurement_method` | PASSPort | base record | 100% |

\* Share of the classified set for which that input is present and non-empty.
**The Checkbook contract purpose - the most authoritative statement of what a
contract actually buys - is available for ~88% of contracts**, so most judgments
now rest on a real scope description. Where higher tiers are missing the model
falls back to the title (a known weak case - see Assumption 2).

> **It still does NOT see:** the full statement of work / deliverables, line
> items, actual spend, number of integrations, data sensitivity/classification,
> or user counts. The richest input is typically one to a few sentences.

---

## 2. The exact prompt (system instruction)

> You classify New York City government technology contracts to help the city decide which EXPIRING contracts it should NOT renew.
>
> Each contract comes with several fields - weigh them in roughly this priority when they are present and non-empty: **contract_purpose** and **expense_category** (from Checkbook NYC, the most authoritative description of what the contract buys), then **scope_description** and **notice_category** (from the City Record notice), then **commodity** and **solicitation_name** (from the originating solicitation), then **contract_title**, **program** and **industry**. The title alone is often vague; always prefer the richer contract_purpose / scope_description / commodity when available. contract_type, term, award_amount vs current_amount, status, procurement_method, selection_method and special_case_reason are context for the renewal judgment.
>
> For each contract, judge:
>
> - **tech_relevant**: Is this genuinely a digital / IT / software / data service or product? Return false for physical-world work mis-tagged as tech: pest control, painting, ship/drydock repair, physical security guards, fuel, waste hauling, generators/power equipment, office furniture/filing, medical supplies, building/HVAC systems, courier/delivery.
> - **is_license**: Is this primarily the purchase of a SOFTWARE LICENSE or subscription (vs. custom development, staffing, consulting, hardware)?
> - **license_product**: If is_license, the product/platform name (e.g. "Microsoft Office 365", "ArcGIS", "Salesforce"); else "".
> - **license_purpose**: If is_license, what the software is used for, one short phrase; else "".
> - **function_category**: A 2-4 word capability bucket. Prefer reusing common buckets: "Website/CMS", "GIS/mapping", "ERP/financials", "Case management", "Cybersecurity", "Data/analytics", "Office productivity", "Staffing/consulting", "Hardware/infrastructure", "Telecom/network", "Identity/access", "Payments", "Document management", "Non-tech". Use the commodity field as a strong hint when present.
> - **build_vs_buy**: How plausibly could the city replace this by building its own solution with open-source software + modern AI tooling? "high" = simple, commoditized software a small team could now stand up (basic websites, forms, simple dashboards, chatbots); "medium" = feasible but real effort/integration; "low" = specialized/regulated/hardware/deeply-integrated platforms or non-tech.
> - **rationale**: One sentence justifying the build_vs_buy rating, citing the scope/commodity evidence you relied on.
>
> Base your judgment on the evidence provided; do not invent capabilities not implied by the fields. Return one result object per contract, preserving the given id.

---

## 3. The output (per contract)

| Field | Type | Meaning |
|---|---|---|
| `tech_relevant` | true/false | Is this genuinely a digital/IT service (vs. mis-tagged physical work)? |
| `is_license` | true/false | Is this primarily a software license/subscription? |
| `license_product` | text | Product name, if a license |
| `license_purpose` | text | One-phrase use of the software, if a license |
| `function_category` | text | One of ~14 capability buckets (see prompt) |
| `build_vs_buy` | high / medium / low | How replaceable with open-source + AI |
| `rationale` | text | One sentence justifying the build-vs-buy rating |

How each output is used on the site: `tech_relevant=false` hides the contract
from digital totals (cleanup of mis-tagged vendors); `build_vs_buy=high` raises a
"Build-your-own candidate" flag; licenses get a badge + "Licenses only" filter;
`function_category` powers a category filter.

---

## 4. Worked examples (live output)

These are real rows from the current run, chosen to show the tiered inputs at
work. Note how several **titles are just a vendor name + procurement code** - the
classification is only possible because of the richer Checkbook/solicitation/
notice text.

### Opaque title -> decoded by richer input
| Contract title (input tier 4) | Richer input used (tier 1-3) | Result |
|---|---|---|
| `K Systems Solutions LLC 25MI021301R0X00` | "New and Renewal Licenses for Existing **SurveyMonkey** Software" | license - SurveyMonkey - Data/analytics - **build=high** |
| `Amendment-SPRUCE TECHNOLOGY INC-22EI014301R0J0` | "**Online referral portal** for Early Intervention" | Website/CMS - **build=high** |
| `BIT Nintex Workflow Software 6300039X` | (purpose) Nintex workflow automation | license - Nintex Workflow - Office productivity - **build=high** |
| `Maintenance and support of Track IT` | "Maintenance and support of **Track It!**" | license - Track-It! - Case management - **build=high** ("basic IT ticketing... can easily be built") |

### "Build-your-own" candidates (build=high)
| Title / scope | Result + rationale (verbatim, truncated) |
|---|---|
| OrgChart Now Software Subscription | Office productivity - "Org chart visualization is a highly commoditized capability that can easily be built..." |
| GoDiagram 10 Team License (MTA project) | Data/analytics - "GoDiagram is a software library for creating interactive diagrams, which can easily..." |
| MWBE Public Building Dashboard and Data Analysis | Data/analytics - "Building a public building dashboard and performing data analysis is highly feasible..." |

### Non-tech catches (tech_relevant = false -> removed from digital totals)
| Title | Richer input | Result |
|---|---|---|
| `CSB Multiyear High and Low Pressure Boiler...` | "High and Low Pressure **Boilers Maintenance** Services" | **Non-tech** - physical boiler maintenance |
| `Janitorial Services at DYFJ Secure Detention...` | (purpose) janitorial services | **Non-tech** |
| `Interagency Communications Committee Support` | "...Committee Support Renewal" (meeting support) | **Non-tech** - professional committee support |

### Specialized / not easily replaceable (build=low)
| Title | Result + rationale |
|---|---|
| IT Consulting Services for CurRent NYC | Staffing/consulting - "professional IT consulting and development services..." |
| TLC Connect Quality Assurance Consultant | Staffing/consulting - "professional services contract for a Quality Assurance consultant..." |

---

## 5. Assumptions & judgment calls baked in (please critique)

1. **The framing is renewal-oriented, not neutral.** The prompt's first line states
   the goal is *deciding which contracts NOT to renew* - this may bias the model
   toward "replaceable." Should this instead be a neutral capability classifier
   whose output a human weighs separately?
2. **Build-vs-buy is inferred from a short scope, not a full SOW.** v2 feeds the
   Checkbook contract purpose / notice / commodity (mitigating the v1 "title only"
   problem for ~88% of contracts), but the richest input is still typically one to
   a few sentences. It has no view of integration footprint, data sensitivity,
   compliance regime, user base, or maintenance burden - the things that usually
   decide build-vs-buy in practice. **And ~12% still fall back to the title alone.**
3. **The "open-source + AI can replace it" premise is itself an assumption.** It
   encodes an optimistic prior about the city's in-house build *and ongoing
   maintenance/security* capacity, and ignores total cost of ownership. "A small
   team could stand it up" is doing a lot of work.
4. **`tech_relevant` is a hard-coded exclusion list** (pest control, drydock,
   guards, fuel, waste...), not a principled definition. Dual-use cases (e.g.
   "security systems" = cybersecurity vs. physical alarm) are ambiguous; novel
   non-tech categories can slip through.
5. **`is_license` collapses a spectrum** - pure license vs. SaaS subscription vs.
   license-plus-implementation-plus-support bundles are lumped together;
   "primarily a license" is undefined.
6. **`function_category` is a fixed, NYC-agnostic taxonomy** chosen by us, not
   derived from how NYC actually organizes IT. Free-text drift is still possible.
7. **No confidence or abstention.** The model is asked to base its judgment on the
   evidence and not invent capabilities, but there is still no "insufficient
   information" output - a contract with only a thin title still gets a confident
   rating, indistinguishable from one backed by a full Checkbook purpose.
8. **Three coarse build-vs-buy tiers** with thresholds defined only by examples
   ("basic websites, forms, chatbots" = high); no notion of *who* builds/maintains
   it, or over what time horizon.
9. **Single model, single pass.** No second-model check or ensemble; human review
   is optional (supported via a `curated` flag, but not required).
10. **Input coverage is uneven and silent.** Higher-tier inputs (notice text,
    commodity) are present for only a minority of contracts, so two contracts with
    the same rating may rest on very different evidence - and the output does not
    record which tier of input it used.

---

## 6. Questions we'd like expert input on

1. Neutral classifier vs. explicitly renewal-oriented framing - which is appropriate
   for a public, official-data product?
2. With richer scope now available for most contracts, is a build-vs-buy rating
   **publishable** (labeled heuristic), or does a credible call still require inputs
   we don't feed (full SOW, # of integrations, data classification, incumbency)?
3. Should `build_vs_buy` carry an explicit **confidence** and an **"insufficient
   information"** value - and should the output record **which input tier** it relied on?
4. Is the `function_category` taxonomy right for NYC, or should it map to an existing
   city/federal IT category scheme (e.g. the Checkbook expense categories, NIGP
   commodity codes)?
5. Where is human review **required** vs. optional before a flag is shown publicly?
6. Is the `tech_relevant` denylist the right mechanism, or should "digital service"
   be defined positively (e.g. from commodity/expense codes)?

---

*Generated to support expert review of the databook.nyc Digital Services Analysis
classifier (v2 - tiered inputs). Proposed changes can be wired back into
`api/classify_digital_contracts.py` and re-run.*
