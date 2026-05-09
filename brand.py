"""Vici Peptides — single source of truth for all brand rules."""

BRAND_NAME = "Vici Peptides"
BRAND_URL = "vicipeptides.com"
GUIDE_URL = "vicipeptides.com/research-guides"

PRODUCTS = [
    "Tirzepatide", "Semaglutide", "Retatrutide", "BPC-157",
    "GHK-Cu", "Tesamorelin", "L-Carnitine", "Epitalon", "MOTS-c", "TB-500"
]

POSITIONING = (
    "Pharmaceutical-grade research peptides. >99% purity HPLC/MS tested. "
    "Third-party CoA with every batch. Same-day shipping. Research use only."
)

AUDIENCE = [
    "Biohackers", "Longevity researchers", "GLP-1 curious",
    "Metabolic health seekers", "Bodybuilders", "Health truth seekers",
    "People who believe in what mainstream medicine won't say"
]

CONTENT_PHILOSOPHY = (
    "High view-to-follower ratio. Truth-based. Make people feel like insiders. "
    "NOT entertainment — conviction. Niche and polarising, not broad and safe. "
    "FACELESS ONLY. No faces. B-roll + voiceover + text overlays."
)

CTA = {
    "standard": (
        "If you want to go further into this topic, we do have a free research guide available. "
        "Just click the link in my bio and feel free to download it. I really hope this helps."
    ),
    "compound": (
        "If you're researching {compound} specifically, we've put together a full compound guide — "
        "mechanism, published data, all of it. Free in the link in bio."
    ),
    "cliffhanger": (
        "Part 2 on this is coming — but if you want the full picture now, "
        "the research guide is already in the link in bio."
    ),
    "x": "Full compound research guides at vicipeptides.com",
    "instagram": "Research compound profiles and CoA library — link in bio",
}

BANNED_WORDS = [
    "buy now", "order today", "get yours", "shop here", "click to purchase",
    "weight loss drug", "weight loss injection", "dose", "results", "transformation",
    "before and after", "treat", "cure", "diagnose", "take it", "use it",
    "lose weight fast", "fat burner", "diet pill"
]

INSTAGRAM_SAFE_TERMS = [
    "research compounds", "longevity research", "metabolic science",
    "scientific wellness", "laboratory research use only", "research-grade",
    "published literature suggests", "compound mechanisms", "cellular research",
    "third-party tested", "certificate of analysis", "HPLC verified",
    "metabolic signalling research", "GLP-1 receptor research", "biooptimisation research"
]
INSTAGRAM_BANNED_TERMS = [
    "peptides", "injection", "weight loss drug", "buy", "order",
    "take", "dose", "results", "transformation", "before and after",
    "treat", "cure", "diagnose"
]

TOPIC_QUEUE = [
    {
        "id": "bpc157_origin",
        "title": "BPC-157: the peptide your stomach already makes",
        "compound": "BPC-157",
        "hook": "BPC-157 isn't synthetic. It's a fragment derived from a protein your stomach already produces. And what the published literature says it does to tissue is remarkable.",
        "format": "Science Revelation",
        "duration_s": 60,
        "score": 9,
        "key_data": "Body Protection Compound, isolated from gastric juice. Consistently outperforms controls in animal tissue repair. Gut healing + tendon/ligament + dopamine pathway research.",
    },
    {
        "id": "glp1_three_tiers",
        "title": "GLP-1 vs GLP-2 vs GLP-3 — the three-tier breakdown",
        "compound": "Tirzepatide / Retatrutide",
        "hook": "GLP-1s aren't created equal. Ozempic hits one receptor. Tirzepatide hits two. Retatrutide hits three — and the trial data shows a completely different ceiling.",
        "format": "Versus Breakdown",
        "duration_s": 75,
        "score": 9,
        "key_data": "Semaglutide ~15% weight loss avg. Tirzepatide ~22%. Retatrutide 24%+ in early trials. Triple agonist: GLP-1 + GIP + glucagon receptor.",
    },
    {
        "id": "purity_gap",
        "title": "The 5.8% purity problem",
        "compound": "General",
        "hook": "Two vials. Same label. One is 99.2% pure. One is 94%. The 5.8% gap? Unknown degradation products. In research applications, it changes everything.",
        "format": "Data Drop",
        "duration_s": 25,
        "score": 8,
        "key_data": "HPLC measures peak purity. CoA batch number = only objective verifier. Vici: >99% purity, lot-numbered CoA on every batch.",
    },
    {
        "id": "ghkcu_decline",
        "title": "GHK-Cu: the copper peptide your body stopped making at 40",
        "compound": "GHK-Cu",
        "hook": "At 20, your body produces GHK-Cu naturally. By 40, levels have dropped over 70%. And what the published literature says it does to collagen synthesis is genuinely fascinating.",
        "format": "Science Revelation",
        "duration_s": 55,
        "score": 8,
        "key_data": "Tripeptide copper complex. Naturally occurring. Activates 32% of human wound healing genes in research. 90,500 monthly searches, KD 11.",
    },
    {
        "id": "fat_as_co2",
        "title": "Where fat actually goes when you burn it",
        "compound": "General metabolic",
        "hook": "Your fat doesn't sweat out. It doesn't get flushed. You literally breathe it out as CO2 — and most people have no idea.",
        "format": "Science Revelation",
        "duration_s": 45,
        "score": 9,
        "key_data": "84% exits via lungs as CO2. Fat oxidation converts triglycerides to CO2 + H2O. This format achieved 2.6M views in niche from a small account.",
        "proven_viral": True,
    },
    {
        "id": "glp1_dopamine",
        "title": "The GLP-1 dopamine effect nobody warned you about",
        "compound": "Semaglutide / GLP-1",
        "hook": "GLP-1 receptor agonists don't just suppress appetite. They appear to dampen your entire dopamine reward system — including the part involved in romantic attraction. Here's the published data.",
        "format": "Science Revelation",
        "duration_s": 50,
        "score": 8,
        "key_data": "GLP-1 receptors in nucleus accumbens (reward centre). Same pathways: food, alcohol, gambling, early romantic attraction. 60M+ people on these compounds.",
    },
    {
        "id": "tesamorelin_hidden",
        "title": "Tesamorelin: the FDA-approved compound nobody talks about",
        "compound": "Tesamorelin",
        "hook": "Tesamorelin is FDA-approved. It targets visceral fat specifically. And most people in the GLP-1 conversation have never heard of it — because it works through an entirely different mechanism.",
        "format": "Compound Profile",
        "duration_s": 55,
        "score": 7,
        "key_data": "GHRH analog. Stimulates pituitary GH release. FDA-approved for HIV lipodystrophy. 40,500 searches/mo, KD 0 — essentially an open goal.",
    },
    {
        "id": "longevity_stack_2025",
        "title": "The longevity stack researchers are building in 2025",
        "compound": "Multiple",
        "hook": "Want to know what serious longevity researchers are actually studying right now? It's not a single compound. It's a stack — and the individual mechanisms are extraordinary.",
        "format": "Teaser series",
        "duration_s": 60,
        "score": 8,
        "key_data": "Epitalon (telomere research), BPC-157 (tissue + gut), GHK-Cu (collagen + gene expression), Tirzepatide (metabolic), MOTS-c (mitochondrial). Series format drives follows.",
    },
    {
        "id": "semaglutide_liver",
        "title": "Ozempic's liver effect — the data nobody is explaining",
        "compound": "Semaglutide",
        "hook": "There's a 1.8M-view TikTok called 'Ozempic liver' with zero explanation. Here's what the published research actually shows about GLP-1 agonists and hepatic fat.",
        "format": "Science Revelation",
        "duration_s": 50,
        "score": 7,
        "key_data": "GLP-1 reduces hepatic steatosis in multiple RCTs. 30-40% liver fat reduction in some studies. Mechanism entirely separate from appetite suppression.",
    },
    {
        "id": "research_vs_pharma",
        "title": "Research-grade vs pharmaceutical-grade — same molecule, not the same product",
        "compound": "General",
        "hook": "Research grade. Pharmaceutical grade. Same molecule. Not the same product. Here's what the difference actually means — and why it matters for every purchase decision.",
        "format": "Data Drop",
        "duration_s": 25,
        "score": 7,
        "key_data": "Pharma grade = FDA-approved manufacturing process. Research grade = third-party HPLC verified, not for human use. CoA = the only objective differentiator.",
    },
]

FASTLANE_ANGLES = [
    {
        "title": "Research Truth Revelation",
        "description": (
            "Short-form content that reveals counterintuitive scientific findings about GLP-1 compounds, "
            "peptides, and metabolic health. Framed as 'what most people don't know' — truth-based, "
            "data-cited, no personal use claims. Makes the audience feel like insiders with access to "
            "information the mainstream hasn't covered. Faceless production: voiceover + B-roll."
        ),
        "targetAudience": "Biohackers, longevity researchers, GLP-1 curious adults 25-45",
    },
    {
        "title": "Compound Profile Education",
        "description": (
            "Dedicated 45-60 second explainers on individual research compounds — BPC-157, GHK-Cu, "
            "Tirzepatide, Retatrutide, Tesamorelin. Covers mechanism, endogenous origin (where applicable), "
            "research applications, and key published data. Science-first, credible, no medical claims. "
            "Research use only framing throughout. Faceless: B-roll + ElevenLabs voiceover."
        ),
        "targetAudience": "Peptide researchers, biohackers, metabolic health seekers",
    },
    {
        "title": "Versus Breakdown",
        "description": (
            "Head-to-head comparisons of research compounds: Semaglutide vs Tirzepatide, "
            "BPC-157 vs TB-500, GLP-1 vs GLP-2 vs GLP-3. Uses published trial data to compare "
            "receptor mechanisms, research outcomes, and compound profiles. Drives comment debate."
        ),
        "targetAudience": "Informed health researchers comparing compound options",
    },
    {
        "title": "Purity and Quality Standards",
        "description": (
            "Content that educates on what third-party testing, HPLC verification, and Certificates "
            "of Analysis actually mean for research compounds. Positions Vici's quality standards as "
            "the benchmark without making promotional claims."
        ),
        "targetAudience": "Research compound buyers who care about quality verification",
    },
    {
        "title": "Longevity Stack Research",
        "description": (
            "Content covering multi-compound longevity research stacks: Epitalon, BPC-157, GHK-Cu, "
            "MOTS-c, Tirzepatide. Series format — each video covers one compound in the stack."
        ),
        "targetAudience": "Anti-aging researchers, biohackers building longevity protocols",
    },
]
