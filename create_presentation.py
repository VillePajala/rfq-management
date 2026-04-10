"""
Generate CGI-branded PowerPoint — concise demo deck.
Audience knows the use case. Go straight to the deliverable.
"""

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE
import os

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cgi_template.pptx")
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Tender_Intelligence_CGI.pptx")
OUTPUT_DESKTOP = "/mnt/c/Users/ville.pajala/Desktop/Tender_Intelligence_CGI.pptx"

CGI_BLUE = RGBColor(0, 121, 193)
CGI_DARK = RGBColor(51, 51, 51)
CGI_GRAY = RGBColor(120, 120, 120)
WHITE = RGBColor(255, 255, 255)
GREEN = RGBColor(46, 164, 79)
RED = RGBColor(192, 57, 43)
ORANGE = RGBColor(230, 126, 34)


def tb(slide, left, top, width, height, text, size=18, bold=False, color=CGI_DARK, align=PP_ALIGN.LEFT):
    t = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = t.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.alignment = align
    return tf


def bullets(tf, items, size=16, color=CGI_DARK):
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.space_after = Pt(5)


def box(slide, left, top, width, height, fill, text="", size=13, fc=CGI_DARK, bold=False):
    s = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    s.fill.solid()
    s.fill.fore_color.rgb = fill
    s.line.fill.background()
    if text:
        tf = s.text_frame
        tf.word_wrap = True
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        tf.paragraphs[0].text = text
        tf.paragraphs[0].font.size = Pt(size)
        tf.paragraphs[0].font.color.rgb = fc
        tf.paragraphs[0].font.bold = bold
    return s


def arrow(slide, left, top, width, height):
    s = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(left), Inches(top), Inches(width), Inches(height))
    s.fill.solid()
    s.fill.fore_color.rgb = CGI_BLUE
    s.line.fill.background()


def create_presentation():
    prs = Presentation(TEMPLATE)
    while len(prs.slides) > 0:
        rId = prs.slides._sldIdLst[0].rId
        prs.part.drop_rel(rId)
        del prs.slides._sldIdLst[0]

    L = prs.slide_layouts
    TITLE = 2
    CONTENT = 12
    TWOCOL = 19
    BLANK = 36

    # ── 1: Title ────────────────────────────────────────────────────────
    slide = prs.slides.add_slide(L[TITLE])
    slide.placeholders[0].text = "Tender Intelligence"
    slide.placeholders[14].text = "Automated Public Sector Tender Monitoring for CGI\n\nWorking Proof of Concept — April 2026"

    # ── 2: Email Example (the hook — show the end result first) ─────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "What CGI Experts Receive"

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_email_sample.png")
    if os.path.exists(img_path):
        slide.shapes.add_picture(img_path, Inches(0.5), Inches(1.2), Inches(11.4))

    tb(slide, 8.8, 1.4, 4.3, 0.4, "Daily email per department:", 16, True, CGI_BLUE)
    tb(slide, 8.8, 1.9, 4.3, 4.6,
       "Each department receives one email\n"
       "containing only their relevant tenders.\n\n"
       "For each tender:\n"
       "  • Clickable link to tarjouspalvelu.fi\n"
       "  • Organization and deadline\n"
       "  • AI-generated summary:\n"
       "     — What is being procured\n"
       "     — Relevance to CGI\n"
       "     — Recommended action\n\n"
       "Tier 1A: CGI own products\n"
       "(Aromi, Raindance, Titania, etc.)\n"
       "→ Defend existing customers or\n"
       "   bid on upgrades/renewals\n\n"
       "Tier 1B: Partner platforms\n"
       "(SAP, Azure, ServiceNow, etc.)\n"
       "→ Bid as implementation partner",
       14, False, CGI_DARK)

    # ── 3: Routing Config (Excel screenshot) ───────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "Routing Configuration"

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_routing_excel.png")
    if os.path.exists(img_path):
        slide.shapes.add_picture(img_path, Inches(0.3), Inches(1.1), Inches(12.5))

    tb(slide, 0.3, 5.5, 12.5, 1.0,
       "Non-technical users edit this Excel file to control who receives which tenders.\n"
       "Keywords are matched against tender name and description. One email per department per day.\n"
       "Tier 1 product alerts (Aromi, SAP, etc.) are handled automatically — no configuration needed.",
       14, False, CGI_GRAY)

    # ── 4: Process Diagram ──────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "How It Works"

    # Row 1: Pipeline
    box(slide, 0.3, 1.3, 2.4, 0.9, RGBColor(220, 235, 250), "tarjouspalvelu.fi\n(5,000+ tenders)", 13, CGI_DARK, True)
    arrow(slide, 2.8, 1.5, 0.5, 0.35)
    box(slide, 3.4, 1.3, 2.0, 0.9, RGBColor(220, 235, 250), "Automated\nScraping", 14, CGI_DARK, True)
    arrow(slide, 5.5, 1.5, 0.5, 0.35)
    box(slide, 6.1, 1.3, 2.2, 0.9, RGBColor(245, 230, 230), "Filtering\n& Classification", 13, CGI_DARK, True)
    arrow(slide, 8.4, 1.5, 0.5, 0.35)
    box(slide, 9.0, 1.3, 2.2, 0.9, RGBColor(252, 243, 207), "AI Summary\n(GPT-4.1)", 13, CGI_DARK, True)
    arrow(slide, 11.3, 1.5, 0.5, 0.35)
    box(slide, 11.9, 1.3, 1.2, 0.9, RGBColor(212, 239, 223), "Store &\nRoute", 13, CGI_DARK, True)

    # Arrow down to routing
    tb(slide, 5.0, 2.5, 3.5, 0.4, "▼   Smart Routing   ▼", 16, True, CGI_BLUE, PP_ALIGN.CENTER)

    # Row 2: Tiers
    box(slide, 0.3, 3.1, 3.8, 1.6, RGBColor(255, 235, 220),
        "TIER 1: PRODUCT ALERTS\n\n1A: CGI own products (Aromi,\nRaindance, Titania, OMNI360...)\n1B: Partner platforms (SAP,\nAzure, ServiceNow, UiPath...)", 11)
    box(slide, 1.2, 4.75, 1.8, 0.35, RED, "CRITICAL", 11, WHITE, True)

    box(slide, 4.3, 3.1, 3.8, 1.6, RGBColor(224, 247, 224),
        "TIER 2: DOMAIN MATCH\n\nKeywords match CGI department\n(IT, consulting, health, etc.)\n\n→ Daily email digest", 12)
    box(slide, 5.2, 4.75, 1.8, 0.35, ORANGE, "HIGH", 11, WHITE, True)

    box(slide, 8.3, 3.1, 2.4, 1.6, RGBColor(240, 240, 240),
        "TIER 3: GENERAL\n\nNo specific match\n\n→ Dashboard only\n→ No email", 12, CGI_GRAY)
    box(slide, 8.8, 4.75, 1.5, 0.35, CGI_GRAY, "LOW", 11, WHITE, True)

    box(slide, 10.9, 3.1, 2.2, 1.6, RGBColor(245, 235, 235),
        "ANALYTICS\n\nAward results feed\nprice intelligence &\ncompetitor profiles", 11, CGI_GRAY)

    tb(slide, 0.3, 5.6, 12.5, 0.4,
       "All tenders stored permanently  |  Deduplication across runs  |  Historical data grows over time",
       13, False, CGI_GRAY, PP_ALIGN.CENTER)

    # ── 4: What We Access ───────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "Tarjouspalvelu.fi"

    # Current solution flow
    tb(slide, 0.3, 1.2, 12, 0.3, "Working pipeline (fully automated, including login):", 16, True, GREEN)

    box(slide, 0.3, 1.6, 2.2, 0.7, RGBColor(212, 239, 223), "Open Chrome\n(automated)", 12, CGI_DARK, True)
    arrow(slide, 2.6, 1.7, 0.4, 0.3)
    box(slide, 3.1, 1.6, 2.4, 0.7, RGBColor(212, 239, 223), "Bypass Cloudflare\n(auto-resolves)", 12, CGI_DARK, True)
    arrow(slide, 5.6, 1.7, 0.4, 0.3)
    box(slide, 6.1, 1.6, 2.4, 0.7, RGBColor(212, 239, 223), "Login via SSO\n(Cloudia Services)", 12, CGI_DARK, True)
    arrow(slide, 8.6, 1.7, 0.4, 0.3)
    box(slide, 9.1, 1.6, 2.2, 0.7, RGBColor(212, 239, 223), "Global search\n(all of Finland)", 12, CGI_DARK, True)
    arrow(slide, 11.4, 1.7, 0.4, 0.3)
    box(slide, 11.9, 1.6, 1.2, 0.7, RGBColor(212, 239, 223), "Extract\ndata", 12, CGI_DARK, True)

    # Data available
    tb(slide, 0.3, 2.6, 12, 0.3, "Data extracted per tender:", 16, True, CGI_BLUE)

    box(slide, 0.3, 3.0, 6.2, 1.6, RGBColor(220, 235, 250),
        "From listing page (all tenders at once)\n\n"
        "• Tender name and ID\n"
        "• Organisation\n"
        "• Type (competition, results, DPS, etc.)\n"
        "• Full description text\n"
        "• Publication date and deadline", 12, CGI_DARK)

    box(slide, 6.7, 3.0, 6.4, 1.6, RGBColor(252, 243, 207),
        "From detail page (one by one, login required)\n\n"
        "• Publication documents (specs, pricing sheets)\n"
        "• Evaluation criteria (price vs quality weighting)\n"
        "• Qualification requirements\n"
        "• Questions & Answers thread\n"
        "• Buyer contact information", 12, CGI_DARK)

    # Challenges
    tb(slide, 0.3, 4.9, 12, 0.3, "Solved challenges:", 16, True, ORANGE)

    box(slide, 0.3, 5.3, 4.0, 1.2, RGBColor(255, 243, 224),
        "Cloudflare Bot Protection\n\nBlocks all standard automation.\nOur solution auto-resolves it.\nTested 5 approaches — only one works.", 11, CGI_DARK)

    box(slide, 4.5, 5.3, 4.0, 1.2, RGBColor(255, 243, 224),
        "Login Automation\n\nTwo-step SSO redirect to Cloudia.\nVaadin framework (non-standard UI).\nFully automated with credentials.", 11, CGI_DARK)

    box(slide, 8.7, 5.3, 4.4, 1.2, RGBColor(255, 243, 224),
        "Production Readiness\n\nNeeds: service account (not personal),\nvirtual display for server,\nscheduled nightly runs.", 11, CGI_DARK)

    # ── 5: Filter Funnel ────────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "Narrowing Down: From 5,000 to Relevant"

    tb(slide, 0.5, 1.1, 12, 0.5,
       "We filter in layers — cheapest and fastest first, AI only on what survives. Each layer is configurable.",
       16, False, CGI_DARK)

    # Layer 1
    box(slide, 0.5, 1.8, 7.0, 0.75, RGBColor(220, 235, 250),
        "Layer 1: Notice Type (built-in search filter)\nKeep only open competitions, planning notices, DPS. Remove awards, cancellations, direct awards.", 12)
    tb(slide, 7.7, 1.9, 2.5, 0.5, "5,000 → ~2,000", 16, True, GREEN)
    box(slide, 10.3, 1.95, 2.8, 0.45, RGBColor(212, 239, 223), "Automatic", 12, CGI_DARK, True)

    # Layer 2
    box(slide, 0.5, 2.75, 7.0, 0.75, RGBColor(220, 235, 250),
        "Layer 2: Procurement Category (built-in search filter)\nKeep only categories CGI operates in: Service, Health & Social, IT, etc.", 12)
    tb(slide, 7.7, 2.85, 2.5, 0.5, "2,000 → ~800", 16, True, GREEN)
    box(slide, 10.3, 2.9, 2.8, 0.45, RGBColor(255, 243, 224), "Need your input", 12, RED, True)

    # Layer 3
    box(slide, 0.5, 3.7, 7.0, 0.75, RGBColor(220, 235, 250),
        "Layer 3: CPV Codes — standardized EU procurement categories\nFilter to IT (72xxx), consulting (79xxx), and other relevant codes.", 12)
    tb(slide, 7.7, 3.8, 2.5, 0.5, "800 → ~300", 16, True, GREEN)
    box(slide, 10.3, 3.85, 2.8, 0.45, RGBColor(255, 243, 224), "Need your input", 12, RED, True)

    # Layer 4
    box(slide, 0.5, 4.65, 7.0, 0.75, RGBColor(252, 243, 207),
        "Layer 4: Keyword + Product Name Matching\nTier 1: CGI product names (Aromi, etc.)  |  Tier 2: department keywords  |  Tier 3: everything else", 12)
    tb(slide, 7.7, 4.75, 2.5, 0.5, "300 → routed", 16, True, GREEN)
    box(slide, 10.3, 4.8, 2.8, 0.45, RGBColor(255, 243, 224), "Need your input", 12, RED, True)

    # Layer 5
    box(slide, 0.5, 5.6, 7.0, 0.65, RGBColor(252, 243, 207),
        "Layer 5: AI Summary + Relevance Scoring\nOnly for tenders that passed all filters. Costs ~$0.002 per tender.", 12)
    tb(slide, 7.7, 5.65, 5, 0.4, "~$40-70/month total AI cost", 14, False, CGI_GRAY)

    tb(slide, 0.5, 6.5, 12.5, 0.4,
       "Numbers are estimates — actual reduction depends on which categories and codes CGI selects.",
       12, False, CGI_GRAY)

    # ── 6: AI Costs ─────────────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "AI Costs: Right Model for Each Task"

    tb(slide, 0.3, 1.1, 12, 0.4,
       "Different tasks need different models. Cheap models handle most work. Total monthly cost is negligible.",
       16, False, CGI_DARK)

    # Headers
    tb(slide, 0.3, 1.6, 3.5, 0.3, "Task", 14, True, CGI_BLUE)
    tb(slide, 3.8, 1.6, 2.5, 0.3, "Model", 14, True, CGI_BLUE)
    tb(slide, 6.3, 1.6, 2.5, 0.3, "Data used", 14, True, CGI_BLUE)
    tb(slide, 8.8, 1.6, 1.8, 0.3, "Per tender", 14, True, CGI_BLUE)
    tb(slide, 10.6, 1.6, 2.5, 0.3, "300/month", 14, True, CGI_BLUE)

    tasks = [
        ("Summarization\n(Finnish → English)", "Basic AI\n(GPT-4.1-nano)", "Detail page\n(full docs)", "$0.002", "$18", RGBColor(212, 239, 223)),
        ("Classification\n(categorize tender)", "Basic AI\n(GPT-4.1-nano)", "Listing\n(description)", "$0.0002", "$1.60", RGBColor(212, 239, 223)),
        ("Award Analysis\n(extract winner + price)", "Standard AI\n(GPT-4.1-mini)", "Detail page\n(award text)", "$0.003", "$9", RGBColor(220, 235, 250)),
        ("Relevance Scoring\n(relevant to CGI?)", "Standard AI\n(GPT-4.1-mini)", "Detail page\n(full docs)", "$0.003", "$9", RGBColor(220, 235, 250)),
        ("Bid Recommendation\n(should CGI bid?)", "Advanced AI\n(GPT-4.1 / 4o)", "All docs +\nhistory", "$0.01", "$30+", RGBColor(252, 243, 207)),
    ]

    for i, (task, model, data, cost_per, cost_month, color) in enumerate(tasks):
        y = 2.0 + i * 0.85
        box(slide, 0.3, y, 3.4, 0.75, color, task, 11, CGI_DARK)
        tb(slide, 3.8, y + 0.15, 2.5, 0.5, model, 13, True, CGI_DARK)
        tb(slide, 6.3, y + 0.1, 2.5, 0.5, data, 11, False, CGI_GRAY)
        tb(slide, 8.8, y + 0.15, 1.8, 0.5, cost_per, 14, False, CGI_DARK)
        tb(slide, 10.6, y + 0.15, 2.5, 0.5, cost_month, 14, False, CGI_DARK)

    tb(slide, 0.3, 6.2, 12.5, 0.8,
       "Daily pipeline (summarize + classify + score): ~$40-70/month.  Runs as a nightly scheduled job.\n"
       "Bid recommendation (future) is the only premium task — runs only on tenders CGI decides to pursue.",
       13, False, CGI_GRAY)

    # ── Console Output slide ────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    slide.placeholders[0].text = "Automated Pipeline Run"

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_console_output.png")
    if os.path.exists(img_path):
        slide.shapes.add_picture(img_path, Inches(0.3), Inches(1.1), Inches(8.0))

    tb(slide, 8.6, 1.1, 4.5, 0.4, "What happens in one run:", 16, True, CGI_BLUE)
    tb(slide, 8.6, 1.6, 4.5, 5.0,
       "1. Browser launches and logs in\n"
       "   automatically to tarjouspalvelu.fi\n\n"
       "2. Scrapes all open tenders\n"
       "   across Finland (100+ per run)\n\n"
       "3. Classifies each tender:\n"
       "   open / signal / closed\n\n"
       "4. AI summarizes in English\n\n"
       "5. Three-tier routing:\n"
       "   product alerts, department\n"
       "   match, or dashboard only\n\n"
       "6. Sends emails per department\n\n"
       "Runs nightly as scheduled job.\n"
       "Total time: ~2 minutes.",
       13, False, CGI_DARK)

    # ── What We Need + Next Steps ─────────────────────────────────────
    slide = prs.slides.add_slide(L[TWOCOL])
    slide.placeholders[0].text = "To Get Started"

    tf = slide.placeholders[17].text_frame
    tf.paragraphs[0].text = "We need from you:"
    tf.paragraphs[0].font.bold = True
    tf.paragraphs[0].font.size = Pt(18)
    tf.paragraphs[0].font.color.rgb = RED

    bullets(tf, [
        "",
        "1. Which procurement categories?",
        "   Service, Health, Works, all?",
        "",
        "2. CGI's public sector products?",
        "   Aromi, and what else?",
        "   → These trigger critical alerts",
        "",
        "3. Department keywords + contacts",
        "   Who gets what, at which email?",
        "",
        "4. Service account for tarjouspalvelu.fi",
        "   (currently using personal login)",
    ], size=15)

    tf2 = slide.placeholders[23].text_frame
    tf2.paragraphs[0].text = "Then we:"
    tf2.paragraphs[0].font.bold = True
    tf2.paragraphs[0].font.size = Pt(18)
    tf2.paragraphs[0].font.color.rgb = GREEN

    bullets(tf2, [
        "",
        "1. Configure filters and routing",
        "   Based on your answers",
        "",
        "2. First pilot run — all of Finland",
        "   Review: are we catching the right ones?",
        "",
        "3. Iterate on keywords and filters",
        "   Fine-tune based on feedback",
        "",
        "4. Schedule daily automated runs",
        "",
        "5. Production deployment",
    ], size=15)

    # ── Save ────────────────────────────────────────────────────────────
    prs.save(OUTPUT)
    prs.save(OUTPUT_DESKTOP)
    print(f"Saved: {OUTPUT}")
    print(f"Desktop: {OUTPUT_DESKTOP}")


if __name__ == "__main__":
    create_presentation()
