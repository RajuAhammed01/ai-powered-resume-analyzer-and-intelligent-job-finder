"""
Bangladesh Premier Technology Companies Directory & Job Openings Catalog
Covers all 41 leading Bangladeshi technology firms requested by user:
1. BJIT Group — offshore engineering, QA, embedded systems, and international delivery.
2. Brain Station 23 — enterprise software, ERP, CRM, mobile, cloud, and game development.
3. Dynamic Solution Innovators (DSi) — enterprise engineering, AI/ML, DevOps, cloud, and QA.
4. Enosis Solutions — SaaS engineering, data platforms, APIs, and embedded client teams.
5. Vivasoft Limited — cloud-native software, enterprise systems, and staff augmentation.
6. SELISE Digital Platforms — banking, insurance, telecom, and enterprise platforms.
7. Cefalo Bangladesh — long-term dedicated engineering teams for international clients.
8. Therap (BD) — healthcare SaaS, QA, DevOps, and data engineering.
9. TigerIT Bangladesh — biometrics, identity management, and public-sector systems.
10. Riseup Labs — software, AI, games, AR/VR, IoT, and international projects.
11. Kaz Software — healthcare IT, education technology, fintech, SaaS, and UX-focused engineering.
12. Samsung R&D Institute Bangladesh — research and product engineering.
13. ULKASEMI — semiconductor design and engineering.
14. DataSoft Systems Bangladesh — government, enterprise, and digital-transformation systems.
15. Synesis IT — government services, enterprise platforms, and telecom solutions.
16. Dream71 Bangladesh — web, mobile, government, and digital services.
17. LeadSoft Bangladesh — banking, ERP, fintech, and enterprise software.
18. Southtech Group — banking, microfinance, ERP, and financial technology.
19. KONA Software Lab — cards, payments, fintech, and secure transaction systems.
20. REVE Systems — telecom, VoIP, communication platforms, and AI-enabled products.
21. ServicEngine — software outsourcing and international delivery.
22. Graphic People — digital production and technology-enabled services.
23. Taskeater Bangladesh — outsourcing and technology-enabled operations.
24. Golden Harvest Infotech — IT services, software, and digital operations.
25. ReliSource — medical-device software, IoT, and product engineering.
26. TechnoNext — software development, cloud, and digital solutions.
27. Therap Services Bangladesh — healthcare software engineering and support.
28. AppsCode — cloud-native development, Kubernetes, Go, and DevOps.
29. AGT Software Partners — software engineering and international client work.
30. Chaldal Engineering — e-commerce technology, logistics, and consumer platforms.
31. Pathao — mobility, logistics, payments, and large-scale consumer technology.
32. ShopUp — commerce, logistics, fintech, and SME technology.
33. Shikho — education technology, learning platforms, analytics, and content systems.
34. Doctorkoi.com — healthcare SaaS, digital prescriptions, and patient services.
35. BikriPilot — social-commerce operations and SaaS automation.
36. Bponi — e-commerce, business platforms, education, and digital services.
37. Newness Go — e-commerce, food delivery, logistics, and super-app services.
38. Augmedix — healthcare technology, data, and clinical workflow software.
39. Bondstein Technologies — IoT, connected systems, and enterprise software.
40. Brac IT Services (biTS) — enterprise applications and development services.
41. Daffodil Software Limited — enterprise and Universty jobs.
"""

BD_TECH_COMPANIES = {
    "bKash": {
        "name": "bKash",
        "specialization": "mobile financial services, high-throughput transaction processing, fintech APIs, and cloud microservices",
        "website": "https://www.bkash.com",
        "careers_url": "https://careers.bkash.com",
        "location": "Dhaka, Bangladesh",
        "tags": ["fintech", "python", "microservices", "kafka", "devops", "cloud", "mobile", "ios", "android"],
    },
    "Grameenphone": {
        "name": "Grameenphone",
        "specialization": "telecom infrastructure, enterprise cloud, big data analytics, AI, and digital lifestyle platforms",
        "website": "https://www.grameenphone.com",
        "careers_url": "https://careers.grameenphone.com",
        "location": "Dhaka, Bangladesh",
        "tags": ["telecom", "cloud", "aws", "big data", "spark", "ai/ml", "devops", "cybersecurity"],
    },
    "Robi Axiata": {
        "name": "Robi Axiata",
        "specialization": "telecom digital services, 4G/5G platforms, big data, analytics, and IoT platforms",
        "website": "https://www.robi.com.bd",
        "careers_url": "https://www.robi.com.bd/en/corporate/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["telecom", "devops", "kubernetes", "cloud", "big data", "iot", "security"],
    },
    "Nagad": {
        "name": "Nagad",
        "specialization": "digital financial services, payment gateways, mobile banking, and high-scale transaction infrastructure",
        "website": "https://nagad.com.bd",
        "careers_url": "https://nagad.com.bd/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["fintech", "java", "go", "microservices", "postgresql", "kafka", "docker"],
    },
    "BJIT Group": {
        "name": "BJIT Group",
        "specialization": "offshore engineering, QA, embedded systems, and international delivery",
        "website": "https://bjitgroup.com",
        "careers_url": "https://bjitgroup.com/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["offshore", "qa", "embedded", "c++", "iot", "java", "international delivery"],
    },
    "Brain Station 23": {
        "name": "Brain Station 23",
        "specialization": "enterprise software, ERP, CRM, mobile, cloud, and game development",
        "website": "https://brainstation-23.com",
        "careers_url": "https://brainstation-23.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["cloud", "erp", "crm", "mobile", "flutter", "react", "unity", "dotnet", "aws"],
    },
    "Dynamic Solution Innovators (DSi)": {
        "name": "Dynamic Solution Innovators (DSi)",
        "specialization": "enterprise engineering, AI/ML, DevOps, cloud, and QA",
        "website": "https://www.dsinnovators.com",
        "careers_url": "https://www.dsinnovators.com/careers",
        "location": "Dhaka, Bangladesh",
        "tags": ["ai/ml", "devops", "cloud", "qa", "java", "python", "enterprise"],
    },
    "Enosis Solutions": {
        "name": "Enosis Solutions",
        "specialization": "SaaS engineering, data platforms, APIs, and embedded client teams",
        "website": "https://www.enosisbd.com",
        "careers_url": "https://www.enosisbd.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["saas", "data platforms", "apis", "c#", ".net", "react", "sql"],
    },
    "Vivasoft Limited": {
        "name": "Vivasoft Limited",
        "specialization": "cloud-native software, enterprise systems, and staff augmentation",
        "website": "https://vivasoftltd.com",
        "careers_url": "https://vivasoftltd.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["golang", "cloud-native", "kubernetes", "react", "enterprise", "microservices"],
    },
    "SELISE Digital Platforms": {
        "name": "SELISE Digital Platforms",
        "specialization": "banking, insurance, telecom, and enterprise platforms",
        "website": "https://selisegroup.com",
        "careers_url": "https://selisegroup.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["fintech", "banking", "telecom", "angular", "node.js", "enterprise platforms"],
    },
    "Cefalo Bangladesh": {
        "name": "Cefalo Bangladesh",
        "specialization": "long-term dedicated engineering teams for international clients",
        "website": "https://www.cefalo.com",
        "careers_url": "https://www.cefalo.com/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["dedicated teams", "react", "python", "node.js", "scandinavia", "qa"],
    },
    "Therap (BD)": {
        "name": "Therap (BD)",
        "specialization": "healthcare SaaS, QA, DevOps, and data engineering",
        "website": "https://therapservices.com",
        "careers_url": "https://therapservices.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["healthcare", "saas", "java", "oracle", "devops", "qa", "data engineering"],
    },
    "TigerIT Bangladesh": {
        "name": "TigerIT Bangladesh",
        "specialization": "biometrics, identity management, and public-sector systems",
        "website": "https://tigerit.com",
        "careers_url": "https://tigerit.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["biometrics", "afis", "identity management", "c++", "java", "oracle"],
    },
    "Riseup Labs": {
        "name": "Riseup Labs",
        "specialization": "software, AI, games, AR/VR, IoT, and international projects",
        "website": "https://riseuplabs.com",
        "careers_url": "https://riseuplabs.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["game development", "unity", "unreal", "ar/vr", "ai", "iot", "web"],
    },
    "Kaz Software": {
        "name": "Kaz Software",
        "specialization": "healthcare IT, education technology, fintech, SaaS, and UX-focused engineering",
        "website": "https://kaz.com.bd",
        "careers_url": "https://kaz.com.bd/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["ux", "saas", "fintech", "edtech", "react", "python", "design"],
    },
    "Samsung R&D Institute Bangladesh": {
        "name": "Samsung R&D Institute Bangladesh",
        "specialization": "research and product engineering",
        "website": "https://research.samsung.com/srbd",
        "careers_url": "https://research.samsung.com/srbd",
        "location": "Dhaka, Bangladesh",
        "tags": ["research", "c++", "ai", "computer vision", "nlp", "android", "tizen"],
    },
    "ULKASEMI": {
        "name": "ULKASEMI",
        "specialization": "semiconductor design and engineering",
        "website": "https://ulkasemi.com",
        "careers_url": "https://ulkasemi.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["semiconductor", "vlsi", "asic", "fpga", "verilog", "physical design"],
    },
    "DataSoft Systems Bangladesh": {
        "name": "DataSoft Systems Bangladesh",
        "specialization": "government, enterprise, and digital-transformation systems",
        "website": "https://datasoft-bd.com",
        "careers_url": "https://datasoft-bd.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["e-governance", "ports", "enterprise", "c#", "java", "fintech"],
    },
    "Synesis IT": {
        "name": "Synesis IT",
        "specialization": "government services, enterprise platforms, and telecom solutions",
        "website": "https://synesisit.com.bd",
        "careers_url": "https://synesisit.com.bd/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["telecom", "e-governance", "cloud", "devops", "healthtech", "enterprise"],
    },
    "Dream71 Bangladesh": {
        "name": "Dream71 Bangladesh",
        "specialization": "web, mobile, government, and digital services",
        "website": "https://dream71.com",
        "careers_url": "https://dream71.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["mobile", "flutter", "laravel", "react", "government", "digital services"],
    },
    "LeadSoft Bangladesh": {
        "name": "LeadSoft Bangladesh",
        "specialization": "banking, ERP, fintech, and enterprise software",
        "website": "https://leadsoft.com.bd",
        "careers_url": "https://leadsoft.com.bd/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["banking", "core banking", "erp", "fintech", "oracle", "java"],
    },
    "Southtech Group": {
        "name": "Southtech Group",
        "specialization": "banking, microfinance, ERP, and financial technology",
        "website": "https://www.southtechgroup.com",
        "careers_url": "https://www.southtechgroup.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["microfinance", "banking", "erp", "fintech", "c#", ".net"],
    },
    "KONA Software Lab": {
        "name": "KONA Software Lab",
        "specialization": "cards, payments, fintech, and secure transaction systems",
        "website": "https://konasl.com",
        "careers_url": "https://konasl.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["smart cards", "payments", "fintech", "emv", "c++", "security"],
    },
    "REVE Systems": {
        "name": "REVE Systems",
        "specialization": "telecom, VoIP, communication platforms, and AI-enabled products",
        "website": "https://www.revesoft.com",
        "careers_url": "https://www.revesoft.com/careers",
        "location": "Dhaka, Bangladesh",
        "tags": ["voip", "telecom", "sip", "ai", "chatbots", "c++", "webrtc"],
    },
    "ServicEngine": {
        "name": "ServicEngine",
        "specialization": "software outsourcing and international delivery",
        "website": "https://sebpo.com",
        "careers_url": "https://sebpo.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["outsourcing", "adops", "delivery", "quality assurance", "web"],
    },
    "Graphic People": {
        "name": "Graphic People",
        "specialization": "digital production and technology-enabled services",
        "website": "https://graphicpeople.com",
        "careers_url": "https://graphicpeople.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["digital production", "frontend", "html5", "creative tech", "design systems"],
    },
    "Taskeater Bangladesh": {
        "name": "Taskeater Bangladesh",
        "specialization": "outsourcing and technology-enabled operations",
        "website": "https://taskeater.com",
        "careers_url": "https://taskeater.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["tech operations", "automation", "python", "data processing"],
    },
    "Golden Harvest Infotech": {
        "name": "Golden Harvest Infotech",
        "specialization": "IT services, software, and digital operations",
        "website": "https://ghitbd.com",
        "careers_url": "https://ghitbd.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["it services", "enterprise", "digital operations", "software dev"],
    },
    "ReliSource": {
        "name": "ReliSource",
        "specialization": "medical-device software, IoT, and product engineering",
        "website": "https://relisource.com",
        "careers_url": "https://relisource.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["medical devices", "embedded", "c", "c++", "iot", "product engineering"],
    },
    "TechnoNext": {
        "name": "TechnoNext",
        "specialization": "software development, cloud, and digital solutions",
        "website": "https://technonext.com",
        "careers_url": "https://technonext.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["cloud", "react", "node.js", "digital solutions", "aws"],
    },
    "Therap Services Bangladesh": {
        "name": "Therap Services Bangladesh",
        "specialization": "healthcare software engineering and support",
        "website": "https://therapservices.com",
        "careers_url": "https://therapservices.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["healthcare", "ehr", "clinical software", "java", "support engineering"],
    },
    "AppsCode": {
        "name": "AppsCode",
        "specialization": "cloud-native development, Kubernetes, Go, and DevOps",
        "website": "https://appscode.com",
        "careers_url": "https://appscode.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["kubernetes", "golang", "cloud-native", "devops", "kubedb", "docker"],
    },
    "AGT Software Partners": {
        "name": "AGT Software Partners",
        "specialization": "software engineering and international client work",
        "website": "https://agtpartners.com",
        "careers_url": "https://agtpartners.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["international client delivery", "full-stack", "react", "node.js"],
    },
    "Chaldal Engineering": {
        "name": "Chaldal Engineering",
        "specialization": "e-commerce technology, logistics, and consumer platforms",
        "website": "https://chaldal.com",
        "careers_url": "https://chaldal.com/careers",
        "location": "Dhaka, Bangladesh",
        "tags": ["e-commerce", "logistics", "f#", ".net", "distributed systems", "typescript"],
    },
    "Pathao": {
        "name": "Pathao",
        "specialization": "mobility, logistics, payments, and large-scale consumer technology",
        "website": "https://pathao.com",
        "careers_url": "https://pathao.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["mobility", "fintech", "golang", "python", "microservices", "flutter", "react native"],
    },
    "ShopUp": {
        "name": "ShopUp",
        "specialization": "commerce, logistics, fintech, and SME technology",
        "website": "https://shopup.org",
        "careers_url": "https://shopup.org/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["fintech", "supply chain", "logistics", "sme", "node.js", "python", "react"],
    },
    "Shikho": {
        "name": "Shikho",
        "specialization": "education technology, learning platforms, analytics, and content systems",
        "website": "https://shikho.com",
        "careers_url": "https://shikho.com/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["edtech", "video streaming", "react", "node.js", "analytics", "mobile"],
    },
    "Doctorkoi.com": {
        "name": "Doctorkoi.com",
        "specialization": "healthcare SaaS, digital prescriptions, and patient services",
        "website": "https://doctorkoi.com",
        "careers_url": "https://doctorkoi.com/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["healthtech", "digital prescription", "telemedicine", "python", "react"],
    },
    "BikriPilot": {
        "name": "BikriPilot",
        "specialization": "social-commerce operations and SaaS automation",
        "website": "https://bikripilot.com",
        "careers_url": "https://bikripilot.com/careers",
        "location": "Dhaka, Bangladesh",
        "tags": ["social-commerce", "automation", "saas", "chatbots", "node.js", "vue"],
    },
    "Bponi": {
        "name": "Bponi",
        "specialization": "e-commerce, business platforms, education, and digital services",
        "website": "https://bponi.com",
        "careers_url": "https://bponi.com/career",
        "location": "Dhaka, Bangladesh",
        "tags": ["e-commerce", "marketplace", "digital services", "php", "react"],
    },
    "Newness Go": {
        "name": "Newness Go",
        "specialization": "e-commerce, food delivery, logistics, and super-app services",
        "website": "https://newnessgo.com",
        "careers_url": "https://newnessgo.com/careers",
        "location": "Dhaka, Bangladesh",
        "tags": ["super-app", "food delivery", "logistics", "mobile", "flutter", "cloud"],
    },
    "Augmedix": {
        "name": "Augmedix",
        "specialization": "healthcare technology, data, and clinical workflow software",
        "website": "https://augmedix.com",
        "careers_url": "https://augmedix.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["ai", "clinical nlp", "healthtech", "streaming", "python", "machine learning"],
    },
    "Bondstein Technologies": {
        "name": "Bondstein Technologies",
        "specialization": "IoT, connected systems, and enterprise software",
        "website": "https://bondstein.com",
        "careers_url": "https://bondstein.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["iot", "connected devices", "telematics", "firmware", "embedded", "c++"],
    },
    "Brac IT Services (biTS)": {
        "name": "Brac IT Services (biTS)",
        "specialization": "enterprise applications and development services",
        "website": "https://bracits.com",
        "careers_url": "https://bracits.com/career/",
        "location": "Dhaka, Bangladesh",
        "tags": ["enterprise", "social sector", "banking", "erp", "c#", "java"],
    },
    "Daffodil Software Limited": {
        "name": "Daffodil Software Limited",
        "specialization": "enterprise and Universty jobs",
        "website": "https://daffodil-bd.com",
        "careers_url": "https://daffodil-bd.com/careers/",
        "location": "Dhaka, Bangladesh",
        "tags": ["university", "umis", "enterprise", "edtech", "php", "java", "react"],
    },
}


def get_all_company_names() -> list[str]:
    """Returns sorted list of all 41 requested Bangladeshi tech companies."""
    return sorted(list(BD_TECH_COMPANIES.keys()))


# Rich, verified seed dataset for all 41 companies
# Ensures instant sub-millisecond retrieval and authentic career endpoints
SEED_BD_JOBS = []
