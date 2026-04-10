"""
CGI product and platform names for Tier 1 alert matching.

When any of these names appear in a tender, it triggers a CRITICAL alert.
Maintained as a Python file for easy editing and version control.
"""

# CGI's own products used in Finnish public sector
# Source: cgi.com/fi/fi/kaikki-tuoteratkaisut (April 2026)
CGI_OWN_PRODUCTS = {
    # Financial Management / ERP
    "Raindance": "Financial management / ERP",
    "Kuntamalli": "Municipality financial model (on Raindance)",
    "Kaupunkimalli": "City financial model (on Raindance)",
    "Hyvinvointimalli": "Wellbeing area financial model (on Raindance)",
    "Pro Economica": "Financial management for small/medium municipalities",
    "Sonet Premium": "ERP for financial, HR, operations",
    "DataCycle360": "Document workflow and electronic archiving",

    # HR & Payroll
    "Populus": "HR and payroll (600+ public admin customers)",
    "CGI Prima": "Payroll for wellbeing areas",
    "CGI Palkat": "Payroll for large organizations",
    "Titania": "Shift/workforce scheduling (healthcare, 40+ years)",
    "Palkat Mukana": "Mobile payroll",

    # Healthcare
    "OMNI360": "Patient and client information system",
    "Merlot Medi": "Emergency medical care management",
    "Merlot Mukana": "Mobile ERP for rescue services",
    "Gemini": "Hospital material logistics and instrument management",
    "Marela": "Hospital pharmacy operations management",

    # Municipal Operations
    "Facta": "Municipal registry and land-use data (200+ municipalities)",
    "KuntaNet": "Geospatial and municipal registry",
    "CGI WebGIS": "Browser-based geospatial platform",
    "Kuntapulssi": "Data-driven management dashboard for municipalities",
    "CGI Asioin": "Electronic services portal for residents",

    # Education & Food
    "CGI Vesa": "Early childhood education system",
    "Aromi": "Food service management (schools, hospitals)",

    # Utilities & Other
    "Kolibri": "Customer info system for energy/water utilities",
    "Lämpökanta": "District heating billing",
    "VesikantaPlus": "Water utility billing",
    "Mobilog": "Mobile work execution (healthcare, facilities)",
    "CGI Move360": "Mobility as a Service platform",
    "Travex360": "Travel expense management",
    "Koki360": "Real estate/property management",
    "SiiriNet": "Automated data transfer between systems",
    "Collections360": "Collections/debt management",
    "Verkkopalkka": "Online payroll slip service",
}

# Major platforms CGI implements / manages / consults on
# When these appear in tenders, CGI can bid as implementation partner
PARTNER_PLATFORMS = {
    # ERP & Business Applications
    "SAP": "ERP, S/4HANA, SuccessFactors, Ariba, Concur, Analytics Cloud",
    "S/4HANA": "SAP next-gen ERP",
    "SuccessFactors": "SAP HCM cloud",
    "Oracle": "Database, ERP, cloud",
    "Unit4": "Financial management (used in Finnish municipalities)",
    "Basware": "Invoice automation, purchase-to-pay (Finnish origin)",
    "Workday": "HR and finance cloud",

    # Microsoft Ecosystem
    "Microsoft Azure": "Cloud infrastructure and services",
    "Microsoft 365": "Productivity suite",
    "Dynamics 365": "Microsoft ERP/CRM",
    "Power Platform": "Power Apps, Power BI, Power Automate",
    "Power BI": "Business intelligence",
    "Microsoft Sentinel": "SIEM / security analytics",
    "SharePoint": "Document management and collaboration",
    "Azure DevOps": "CI/CD and development platform",

    # Cloud & Infrastructure
    "AWS": "Amazon cloud infrastructure",
    "Google Cloud": "GCP cloud infrastructure",
    "VMware": "Virtualization, vSphere, NSX",
    "Red Hat": "OpenShift, RHEL, Ansible",
    "OpenShift": "Red Hat container platform",
    "Kubernetes": "Container orchestration",
    "Citrix": "Virtual desktops, application delivery",
    "Nutanix": "Hyperconverged infrastructure",
    "Terraform": "Infrastructure as code",

    # IT Service Management
    "ServiceNow": "IT service management",
    "Atlassian": "Jira, Confluence, Jira Service Management",
    "Jira": "Project/issue tracking (Atlassian)",
    "Efecte": "Finnish ITSM platform",

    # CRM & Customer
    "Salesforce": "CRM",
    "Genesys": "Contact center platform",

    # Security
    "Fortinet": "Network security (common in Finnish public sector)",
    "FortiGate": "Fortinet firewall",
    "WithSecure": "Endpoint protection (Finnish origin, ex F-Secure)",
    "Palo Alto": "Firewalls, Prisma Cloud, Cortex",
    "CrowdStrike": "Endpoint detection and response",
    "CyberArk": "Privileged access management",
    "Splunk": "SIEM, log management",
    "Zscaler": "Cloud security / zero trust",

    # Data & Analytics
    "Snowflake": "Cloud data warehouse",
    "Databricks": "Data engineering and analytics",
    "Qlik": "Business intelligence",
    "Tableau": "Data visualization",
    "SAS": "Analytics and statistical analysis",
    "Elastic": "Elasticsearch, search and analytics",

    # RPA & Automation
    "UiPath": "Robotic Process Automation",
    "Blue Prism": "RPA platform",
    "Automation Anywhere": "RPA platform",
    "Robot Framework": "Test automation (Finnish origin)",

    # Document & Content Management
    "OpenText": "Enterprise content management",
    "M-Files": "Document management (Finnish origin)",
    "Alfresco": "Open-source ECM",
    "ABBYY": "OCR, intelligent document processing",
    "Kofax": "Document capture and process automation",

    # Healthcare & Integration
    "HL7 FHIR": "Health data interoperability standard",
    "Kanta-palvelu": "Finnish national health data architecture",
    "Kanta-järjestelmä": "Finnish national health data architecture",
    "Apotti": "Helsinki region health IT (Epic-based)",
    "Epic": "Patient information system",
    "Sectra": "Medical imaging (PACS/RIS)",

    # GIS & Municipal
    "ArcGIS": "Esri GIS platform",
    "Trimble Locus": "Municipal land use and mapping",
    "Suomi.fi": "National e-services platform",
    "X-Road": "Finnish/Estonian data exchange (Palveluväylä)",
    "Granlund Manager": "Finnish building management",
    "Haahtela": "Finnish facility management",

    # Database
    "PostgreSQL": "Open-source database (public sector preferred)",
    "MariaDB": "Open-source database (Finnish origin)",
    "SQL Server": "Microsoft database",
    "MongoDB": "NoSQL database",

    # Integration & Middleware
    "MuleSoft": "API management and integration",
    "WSO2": "Open-source API management (used with Suomi.fi)",
    "Boomi": "Integration platform",

    # Education
    "Peppi": "Finnish higher education student system",
    "Moodle": "Learning management system",
    "Wilma": "School administration (Visma)",
}

# Key competitors to track in award analysis
COMPETITORS = {
    "TietoEvry": "Lifecare (patient info), IT services",
    "Gofore": "IT consulting, digital transformation",
    "Accenture": "Consulting, system integration",
    "Fujitsu": "IT services",
    "Siili Solutions": "Software development",
    "Vincit": "Software development",
    "Elisa": "IT infrastructure, cloud",
    "Telia": "IT infrastructure, communications",
    "Knowit": "IT consulting",
    "Solita": "Data, digital services",
    "Digia": "Software, integration",
    "Innofactor": "Microsoft solutions",
    "Bilot": "SAP consulting",
    "Capgemini": "Consulting, system integration",
    "Deloitte": "Consulting",
    "KPMG": "Consulting, advisory",
    "BearingPoint": "Consulting",
    "Netum": "IT consulting, public sector",
    "Enfo": "Data, integration",
    "Softera": "Microsoft Dynamics partner",
}


def get_all_alert_keywords() -> list[str]:
    """Get all product and platform names for Tier 1 matching."""
    keywords = []
    for name in CGI_OWN_PRODUCTS:
        keywords.append(name.lower())
    for name in PARTNER_PLATFORMS:
        keywords.append(name.lower())
    return keywords


import re

# Short keywords that need word boundary matching to avoid false positives
# e.g. "SAP" matching inside "kunnossapito", "SAS" inside Finnish words
_SHORT_KEYWORDS = {"sap", "sas", "aws", "gcp", "f5", "ifs", "qlik", "epic"}


def _matches_word(keyword: str, text: str) -> bool:
    """Check if keyword appears in text, using word boundaries for short keywords."""
    keyword_lower = keyword.lower()
    text_lower = text.lower()

    if keyword_lower in _SHORT_KEYWORDS or len(keyword_lower) <= 4:
        # Use word boundary regex for short keywords
        pattern = r'\b' + re.escape(keyword_lower) + r'\b'
        return bool(re.search(pattern, text_lower))
    else:
        return keyword_lower in text_lower


def match_products(text: str) -> list[dict]:
    """Check if text mentions any CGI products or partner platforms.
    Returns list of matches with name, type, and description.
    Uses word boundary matching for short keywords to avoid false positives.
    """
    matches = []

    for name, desc in CGI_OWN_PRODUCTS.items():
        if _matches_word(name, text):
            matches.append({"name": name, "type": "CGI product", "description": desc})

    for name, desc in PARTNER_PLATFORMS.items():
        if _matches_word(name, text):
            matches.append({"name": name, "type": "Partner platform", "description": desc})

    return matches


def match_competitors(text: str) -> list[dict]:
    """Check if text mentions any known competitors."""
    matches = []

    for name, desc in COMPETITORS.items():
        if _matches_word(name, text):
            matches.append({"name": name, "description": desc})

    return matches
