"""Purchase-class resolution, at PRODUCT grain with a FAMILY fallback.

⚠⚠ WHY THIS MODULE EXISTS. `class` used to live only on the family, and a family
is a merge of product spellings — so ONE judgement set the lever for every
contract inside it. Measured 2026-08-11 on the largest family on the page:

    Microsoft            $643.5M   23 contracts   classed `software-licence`
      Microsoft ELA      $573.8M   89.2%          <- genuinely a licence
      Microsoft Unified Support      $57.0M       <- genuinely support
      Microsoft Premier Support      $11.4M       <- genuinely support
      Microsoft Premier Services      $0.4M       <- genuinely services

$68.9M of vendor support was filed as a software licence and asked "is there an
open-source substitute?", because the family grain could not hold two answers.
That is 10.7% of the family and 5.0% of all licence value.

⚠ The grain is PRODUCT, not contract, on purpose. Measured: 948 contracts reduce
to 525 (family, product) pairs, and only 53 families hold more than one product —
most of those being spelling variants (`ArcGIS` / `ESRI ArcGIS` / `Esri ArcGIS`)
whose lever is identical. Contract grain would mean re-deciding the same product
up to 23 times and would make curation impossible; product grain puts one
judgement exactly where the purchase kind actually differs.

⚠ Resolution is an OVERRIDE, never a replacement: a product with no entry
inherits its family's class. So this layer is purely additive — adding it changes
nothing until a product is explicitly given its own class, which is what made it
safe to ship over a live page.
"""
import re

# The seven kinds of purchase, and the ONE question each one implies. ⚠ Kept here
# rather than in the classifier so the router, the loader, the seeds and the
# classifier cannot drift apart; a test pins this against
# classify_license_purchases.py.
CLASSES = ("software-licence", "managed-hosting", "cloud-infrastructure",
           "oss-support-tier", "content-subscription", "professional-services",
           "support-maintenance")

LEVER_FOR = {
    "software-licence": "open-source-substitute",
    "managed-hosting": "benchmark-then-self-host",
    "cloud-infrastructure": "price-and-rightsizing",
    "oss-support-tier": "is-the-paid-tier-needed",
    "content-subscription": "is-the-content-needed",
    "professional-services": "scope-and-rate-review",
    "support-maintenance": "is-the-paid-tier-needed",
}

# ⚠ Hosting and cloud must point at a PRICE review. Classifying a line as
# infrastructure is not a defence of it — it is the class where a public rate
# card makes overcharging provable. Enforced on both seeds by a test.
PRICE_LEVERS = ("benchmark-then-self-host", "price-and-rightsizing")


def norm(s):
    """Fold case and punctuation. MUST stay identical to
    build_license_families.norm() — a product override is keyed on this, so a
    different definition here would silently match nothing.

    ⚠ Deliberately does NOT strip corporate suffixes; see the builder for why.
    """
    return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", s or "")).strip().upper()


def resolve(product, family, product_classes, family_classes):
    """The class for ONE contract: its product's own class if it has one, else
    its family's, else nothing.

    `product_classes` is keyed on norm(product) so an override applies to every
    raw spelling of that product. `family_classes` is keyed on the family's
    display name, as stored.

    Returns a dict with `class`, `lever`, `why`, `source` and `tier`, where
    `source` is 'product' | 'family' | '' — ⚠ carried deliberately so a page can
    say WHERE a classification came from, and so a test can prove the product
    layer is actually being consulted rather than silently skipped.

    ⚠ `tier` ('curated' | 'auto' | '') is carried for the same reason the summary
    carries its provenance: on a PUBLISHED page a reader must be able to tell a
    reviewed judgement from an automatic one. Defaults to 'auto' when a row exists
    but names no tier — the safe direction, since claiming review is the harmful
    error and an unlabelled row is not evidence of review.
    """
    p = (product_classes or {}).get(norm(product))
    if p and (p.get("class") or "").strip():
        return {"class": p["class"], "lever": p.get("lever") or LEVER_FOR.get(p["class"], ""),
                "why": p.get("why") or "", "source": "product",
                "tier": (p.get("tier") or "auto").strip() or "auto"}
    f = (family_classes or {}).get(family or "")
    if f and (f.get("class") or "").strip():
        return {"class": f["class"], "lever": f.get("lever") or LEVER_FOR.get(f["class"], ""),
                "why": f.get("why") or "", "source": "family",
                "tier": (f.get("tier") or "auto").strip() or "auto"}
    return {"class": "", "lever": "", "why": "", "source": "", "tier": ""}


def mix(rows, product_classes, family_classes, value_of=None):
    """Value by resolved class across `rows`, plus which class dominates.

    Used for both the page-wide rollup and a single family's breakdown, so a
    family's own mix cannot disagree with the total it contributes to.

    ⚠ Dominance is by VALUE, not by contract count: Microsoft's support tail is
    16 of 23 contracts but 10.7% of the money, and counting rows would hand the
    family's headline lever to the smaller purchase.
    """
    val = value_of or (lambda r: float(r.get("value") or 0))
    acc = {}
    for r in rows:
        res = resolve(r.get("product"), r.get("family"), product_classes, family_classes)
        key = res["class"] or "(unclassified)"
        a = acc.setdefault(key, {"key": key, "contracts": 0, "value": 0.0,
                                 "lever": res["lever"], "families": set(),
                                 "products": set(), "tiers": set()})
        a["contracts"] += 1
        a["value"] += val(r)
        a["families"].add(r.get("family") or "")
        if r.get("product"):
            a["products"].add(r["product"])
        if res["tier"]:
            a["tiers"].add(res["tier"])
    # ⚠ One bucket can aggregate rows classified at DIFFERENT tiers (a curated
    # product override and an auto family answer landing on the same class), so
    # the bucket reports 'mixed' rather than picking one. Claiming 'curated' for a
    # bucket that is only partly reviewed is the error worth avoiding.
    for a in acc.values():
        t = a["tiers"]
        a["tier"] = (next(iter(t)) if len(t) == 1 else ("mixed" if t else ""))
    out = sorted(acc.values(), key=lambda a: -a["value"])
    return out, (out[0]["key"] if out else "")
