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


def set_title(slide, text, left=0.35, top=0.42, width=11.6, height=0.55):
    """Set slide title with explicit dimensions to prevent vertical text."""
    ph = slide.placeholders[0]
    ph.text = text
    ph.left = Inches(left)
    ph.top = Inches(top)
    ph.width = Inches(width)
    ph.height = Inches(height)


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
    set_title(slide, "What CGI Experts Receive")

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
    set_title(slide, "Routing Configuration")

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
    set_title(slide, "How It Works: Tender Scraping")

    # Row 1: Pipeline
    box(slide, 0.3, 1.3, 2.4, 0.9, RGBColor(220, 235, 250), "tarjouspalvelu.fi\n(5,000+ tenders)", 13, CGI_DARK, True)
    arrow(slide, 2.8, 1.5, 0.5, 0.35)
    box(slide, 3.4, 1.3, 2.0, 0.9, RGBColor(220, 235, 250), "Automated\nScraping", 14, CGI_DARK, True)
    arrow(slide, 5.5, 1.5, 0.5, 0.35)
    box(slide, 6.1, 1.3, 2.2, 0.9, RGBColor(245, 230, 230), "Filtering\n& Classification", 13, CGI_DARK, True)
    arrow(slide, 8.4, 1.5, 0.5, 0.35)
    box(slide, 9.0, 1.3, 2.2, 0.9, RGBColor(252, 243, 207), "AI Summary", 13, CGI_DARK, True)
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
        "TIER 3: GENERAL\n\nNo specific match\n\n→ No email", 12, CGI_GRAY)
    box(slide, 8.8, 4.75, 1.5, 0.35, CGI_GRAY, "LOW", 11, WHITE, True)

    box(slide, 10.9, 3.1, 2.2, 1.6, RGBColor(245, 235, 235),
        "ANALYTICS\n\nAward results feed\nprice intelligence &\ncompetitor profiles", 11, CGI_GRAY)

    tb(slide, 0.3, 5.6, 12.5, 0.4,
       "All tenders stored permanently  |  Deduplication across runs  |  Historical data grows over time",
       13, False, CGI_GRAY, PP_ALIGN.CENTER)

    # ── 5: What We Access ───────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "Tarjouspalvelu.fi")

    # Current solution flow
    tb(slide, 0.3, 1.2, 12, 0.37, "Pipeline:", 16, True, GREEN)

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
        "From detail page tabs (login required, per tender)\n\n"
        "• Summary with full description and dates\n"
        "• Questions & Answers thread\n"
        "• Terms and conditions / qualification reqs\n"
        "• Procurement object details\n"
        "• Persons in charge / buyer contacts", 12, CGI_DARK)

    # Challenges
    tb(slide, 0.3, 4.9, 12, 0.3, "Solved challenges:", 16, True, ORANGE)

    box(slide, 0.3, 5.3, 4.0, 1.2, RGBColor(255, 243, 224),
        "Cloudflare Bot Protection\n\nBlocks all standard automation.\nOur solution auto-resolves it.\nTested 5 approaches — only one works.", 11, CGI_DARK)

    box(slide, 4.5, 5.3, 4.0, 1.2, RGBColor(255, 243, 224),
        "Login Automation\n\nTwo-step SSO redirect to Cloudia.\nVaadin framework (non-standard UI).\nFully automated with credentials.", 11, CGI_DARK)

    box(slide, 8.7, 5.3, 4.4, 1.2, RGBColor(255, 243, 224),
        "Production Readiness\n\nNeeds: service account (not personal),\nvirtual display for server,\nscheduled nightly runs.", 11, CGI_DARK)

    # ── 5b: Technical Implementation ──────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "Technical Implementation (demo)")

    # Row 1: Extraction layer
    tb(slide, 0.3, 1.1, 12, 0.3, "Data Extraction", 16, True, CGI_BLUE)

    box(slide, 0.3, 1.5, 2.6, 0.9, RGBColor(220, 235, 250),
        "Python\nSelenium + undetected-\nchromedriver", 11, CGI_DARK, True)
    arrow(slide, 3.0, 1.7, 0.4, 0.3)
    box(slide, 3.5, 1.5, 2.4, 0.9, RGBColor(220, 235, 250),
        "Browser Automation\nCloudflare bypass,\nSSO login, pagination", 10, CGI_DARK)
    arrow(slide, 6.0, 1.7, 0.4, 0.3)
    box(slide, 6.5, 1.5, 2.6, 0.9, RGBColor(220, 235, 250),
        "HTML Parsing\nJavaScript extraction\nfrom listings + detail tabs", 10, CGI_DARK)
    arrow(slide, 9.2, 1.7, 0.4, 0.3)
    box(slide, 9.7, 1.5, 3.4, 0.9, RGBColor(212, 239, 223),
        "SQLite Database\nDeduplicated storage,\nchange tracking across runs", 10, CGI_DARK)

    # Row 2: Processing layer
    tb(slide, 0.3, 2.7, 12, 0.3, "Processing & Intelligence", 16, True, CGI_BLUE)

    LIGHT_YELLOW = RGBColor(252, 243, 207)
    AI_COLOR = RGBColor(255, 235, 200)

    box(slide, 0.3, 3.1, 2.6, 0.9, RGBColor(245, 230, 230),
        "Rule-based Classification\nPython regex\n(no AI needed)", 10, CGI_DARK, True)
    arrow(slide, 3.0, 3.3, 0.4, 0.3)
    box(slide, 3.5, 3.1, 2.4, 0.9, AI_COLOR,
        "AI Summarization\nOpenAI API\n(GPT-4.1-nano)", 10, CGI_DARK, True)
    # AI marker
    tb(slide, 4.0, 4.1, 2.0, 0.3, "⚡ OpenAI API call", 9, True, ORANGE)
    arrow(slide, 6.0, 3.3, 0.4, 0.3)
    box(slide, 6.5, 3.1, 2.6, 0.9, RGBColor(224, 247, 224),
        "Three-Tier Routing\nProduct matching +\nkeyword rules (Excel)", 10, CGI_DARK, True)
    arrow(slide, 9.2, 3.3, 0.4, 0.3)
    box(slide, 9.7, 3.1, 3.4, 0.9, AI_COLOR,
        "Award Analysis\nOpenAI API — extract\nwinner, price, bidders", 10, CGI_DARK, True)
    tb(slide, 10.8, 4.1, 2.0, 0.3, "⚡ OpenAI API call", 9, True, ORANGE)

    # Row 3: Delivery layer
    tb(slide, 0.3, 4.5, 12, 0.3, "Delivery", 16, True, CGI_BLUE)

    box(slide, 0.3, 4.9, 3.0, 0.9, RGBColor(212, 239, 223),
        "Email Digests\nSMTP — one HTML email\nper department per day", 10, CGI_DARK, True)
    box(slide, 3.5, 4.9, 3.0, 0.9, RGBColor(212, 239, 223),
        "Tier 1 Alerts\nCritical notifications for\nCGI product mentions", 10, CGI_DARK, True)
    box(slide, 6.7, 4.9, 3.0, 0.9, RGBColor(240, 240, 240),
        "Web Dashboard\n?", 10, CGI_GRAY)
    box(slide, 9.9, 4.9, 3.2, 0.9, RGBColor(240, 240, 240),
        "Competitor & Price\nIntelligence Reports", 10, CGI_GRAY)

    # Tech stack summary bar
    tb(slide, 0.3, 6.1, 12.5, 0.7,
       "Stack: Python 3.12  |  Selenium + undetected-chromedriver  |  SQLite  |  OpenAI API  |  openpyxl  |  SMTP\n"
       "Deployment: Linux VM + Xvfb (virtual display)  |  Cron scheduling  |  No cloud dependencies beyond OpenAI",
       11, False, CGI_GRAY, PP_ALIGN.CENTER)

    # ── 7: Deep Intelligence ──────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "Deep Intelligence")

    tb(slide, 0.3, 1.1, 12, 0.4,
       "Separate analytics mode scrapes award results, builds competitive and pricing intelligence over time.",
       15, False, CGI_DARK)

    # Left side: Analytics pipeline
    tb(slide, 0.3, 1.6, 6.0, 0.35, "Analytics Pipeline", 15, True, CGI_BLUE)

    box(slide, 0.3, 2.0, 2.8, 0.8, RGBColor(220, 235, 250),
        "Scrape Award Results\nFilter to decided tenders\n(Results, Contract Awards)", 10, CGI_DARK, True)
    arrow(slide, 3.2, 2.2, 0.4, 0.3)
    box(slide, 3.7, 2.0, 2.8, 0.8, AI_COLOR,
        "AI Extraction\nOpenAI parses Finnish text →\nwinner, price, bidders, sector", 10, CGI_DARK, True)
    tb(slide, 3.9, 2.75, 2.0, 0.3, "⚡ OpenAI API call", 9, True, ORANGE)

    # What AI extracts
    tb(slide, 0.3, 3.2, 6.0, 0.3, "Structured data extracted per award:", 13, True, CGI_DARK)
    box(slide, 0.3, 3.55, 6.2, 1.3, RGBColor(248, 248, 248),
        "• Winner company name (preserved in Finnish)\n"
        "• Winning price (EUR, ex. VAT)\n"
        "• Estimated contract value\n"
        "• Number of bidders\n"
        "• Contract duration (e.g. '2 years + 2 option years')\n"
        "• Sector (IT, Construction, Healthcare, etc.)\n"
        "• Confidence level (high / medium / low)", 11, CGI_DARK)

    # Right side: Intelligence databases
    tb(slide, 6.8, 1.6, 6.0, 0.3, "Intelligence That Grows Over Time", 15, True, CGI_BLUE)

    box(slide, 6.8, 2.0, 6.2, 1.4, RGBColor(224, 247, 224),
        "COMPETITOR PROFILES\n\n"
        "Each award result updates a rolling database:\n"
        "• Win count per company\n"
        "• Total and average contract value\n"
        "• Sectors they operate in\n"
        "• Most recent win date", 11, CGI_DARK)

    box(slide, 6.8, 3.55, 6.2, 1.3, RGBColor(220, 235, 250),
        "PRICE INTELLIGENCE\n\n"
        "Contract values grouped by sector:\n"
        "• Average, min, max per sector\n"
        "• Helps size CGI bids competitively\n"
        "• Identifies high-value sectors", 11, CGI_DARK)

    # Bottom: how it accumulates
    tb(slide, 0.3, 5.2, 12.5, 0.3, "How it works in practice:", 14, True, CGI_DARK)

    box(slide, 0.3, 5.6, 4.0, 0.8, RGBColor(252, 243, 207),
        "Week 1\nFirst analytics run: ~100 awards\n→ initial competitor/price data", 11, CGI_DARK, True)
    arrow(slide, 4.4, 5.8, 0.3, 0.3)
    box(slide, 4.8, 5.6, 4.0, 0.8, RGBColor(252, 243, 207),
        "Month 1\nNightly runs accumulate ~500+\n→ patterns emerge per sector", 11, CGI_DARK, True)
    arrow(slide, 8.9, 5.8, 0.3, 0.3)
    box(slide, 9.3, 5.6, 3.8, 0.8, RGBColor(252, 243, 207),
        "Ongoing\nHistorical database grows\n→ benchmark bids, spot trends", 11, CGI_DARK, True)

    tb(slide, 0.3, 6.6, 12.5, 0.3,
       "Runs as a separate nightly job alongside tender alerts  |  Same infrastructure, different filter  |  ~$9/month AI cost",
       11, False, CGI_GRAY, PP_ALIGN.CENTER)

    # ── 7b: Detail Page Enrichment ─────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "Detail Page Enrichment")

    tb(slide, 0.3, 1.1, 12, 0.4,
       "Logged-in scraping unlocks structured tender data across 6 content tabs for richer AI analysis.",
       15, False, CGI_DARK)

    # Left: what we get from listing vs detail
    tb(slide, 0.3, 1.7, 6.0, 0.3, "Listing Page (public, fast)", 14, True, CGI_GRAY)
    box(slide, 0.3, 2.1, 6.0, 1.2, RGBColor(240, 240, 240),
        "• Tender name, ID, organisation\n"
        "• Type and category\n"
        "• Short description\n"
        "• Publication date and deadline\n"
        "→ Enough for routing and basic summaries", 12, CGI_GRAY)

    tb(slide, 6.7, 1.7, 6.0, 0.3, "Detail Page Tabs (login required)", 14, True, GREEN)
    box(slide, 6.7, 2.1, 6.4, 1.2, RGBColor(212, 239, 223),
        "• Summary — full description, dates, org details\n"
        "• Q&A thread — buyer answers, competitor signals\n"
        "• Terms & conditions — qualification requirements\n"
        "• Procurement object — scope, volumes, structure\n"
        "• Persons in charge — buyer contacts\n"
        "→ Richer summaries, competitor signals, initial bid assessment", 12, CGI_DARK)

    # How it works technically
    tb(slide, 0.3, 3.6, 12, 0.3, "How detail scraping works (session-preserving navigation):", 14, True, CGI_BLUE)

    box(slide, 0.3, 4.0, 2.4, 0.7, RGBColor(220, 235, 250),
        "On listings page\nfind tender row", 11, CGI_DARK, True)
    arrow(slide, 2.8, 4.15, 0.3, 0.3)
    box(slide, 3.2, 4.0, 2.4, 0.7, RGBColor(220, 235, 250),
        "Click link\n(ActionChains —\npreserves session)", 10, CGI_DARK, True)
    arrow(slide, 5.7, 4.15, 0.3, 0.3)
    box(slide, 6.1, 4.0, 2.4, 0.7, RGBColor(212, 239, 223),
        "Full detail page\nall tabs accessible\n(logged-in view)", 10, CGI_DARK, True)
    arrow(slide, 8.6, 4.15, 0.3, 0.3)
    box(slide, 9.0, 4.0, 2.0, 0.7, RGBColor(220, 235, 250),
        "Extract text\n+ tab data", 11, CGI_DARK, True)
    arrow(slide, 11.1, 4.15, 0.3, 0.3)
    box(slide, 11.5, 4.0, 1.6, 0.7, RGBColor(220, 235, 250),
        "Back to\nlistings", 11, CGI_DARK, True)

    # What this enables
    tb(slide, 0.3, 5.0, 12, 0.3, "What richer data enables:", 14, True, CGI_DARK)

    box(slide, 0.3, 5.4, 4.0, 1.0, RGBColor(252, 243, 207),
        "Better AI Summaries\n\nFull tab content instead of\nshort descriptions → more\naccurate relevance scoring", 11, CGI_DARK, True)
    box(slide, 4.5, 5.4, 4.0, 1.0, RGBColor(252, 243, 207),
        "Initial Bid Assessment\n\nTerms & procurement object\nreveal qualification reqs →\nAI flags fit or misfit", 11, CGI_DARK, True)
    box(slide, 8.7, 5.4, 4.4, 1.0, RGBColor(252, 243, 207),
        "Competitive Intelligence\n\nQ&A threads reveal what\ncompetitors are asking about\n→ signals about who's bidding", 11, CGI_DARK, True)

    tb(slide, 0.3, 6.6, 12.5, 0.3,
       "Note: attached files (PDFs, Excel) are not downloaded — full bid intelligence requires file processing (Level 3)",
       11, False, CGI_GRAY, PP_ALIGN.CENTER)

    # ── 8: Filter Funnel ────────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "Narrowing Down Results")

    tb(slide, 0.42, 1.1, 12, 0.5,
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

    # ── 8: AI Costs ─────────────────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "AI Costs: Right Model for Each Task")

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
        ("Summarization\n(Finnish → English)", "Basic AI\n(GPT-4.1-nano)", "Detail tabs\n(all tab text)", "$0.002", "$18", RGBColor(212, 239, 223)),
        ("Classification\n(categorize tender)", "Basic AI\n(GPT-4.1-nano)", "Listing\n(description)", "$0.0002", "$1.60", RGBColor(212, 239, 223)),
        ("Award Analysis\n(extract winner + price)", "Standard AI\n(GPT-4.1-mini)", "Detail tabs\n(award text)", "$0.003", "$9", RGBColor(220, 235, 250)),
        ("Relevance Scoring\n(relevant to CGI?)", "Standard AI\n(GPT-4.1-mini)", "Detail tabs\n(all tab text)", "$0.003", "$9", RGBColor(220, 235, 250)),
        ("Bid Recommendation\n(should CGI bid?)", "Advanced AI\n(GPT-4.1 / 4o)", "Tabs + files\n(Level 3)", "$0.01", "$30+", RGBColor(252, 243, 207)),
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

    # ── 9: Console Output slide ──────────────────────────────────────────
    slide = prs.slides.add_slide(L[BLANK])
    set_title(slide, "Automated Pipeline Run")

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshot_console_output.png")
    if os.path.exists(img_path):
        slide.shapes.add_picture(img_path, Inches(0.84), Inches(1.33), Inches(6.71), Inches(6.06))

    tb(slide, 8.6, 1.33, 4.5, 0.4, "What happens in one run:", 16, True, CGI_BLUE)
    tb(slide, 8.6, 1.96, 4.5, 5.0,
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

    # ── Save ────────────────────────────────────────────────────────────
    prs.save(OUTPUT)
    print(f"Saved: {OUTPUT}")
    try:
        prs.save(OUTPUT_DESKTOP)
        print(f"Desktop: {OUTPUT_DESKTOP}")
    except PermissionError:
        print(f"Desktop: SKIPPED (file is open in PowerPoint?) — close it and copy manually:")
        print(f"  cp '{OUTPUT}' '{OUTPUT_DESKTOP}'")


if __name__ == "__main__":
    create_presentation()
