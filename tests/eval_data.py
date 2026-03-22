"""
Realistic test submissions for live pipeline evaluation.

20 submissions designed to stress-test every triage branch, edge case, and scoring dimension.

Coverage matrix:
  DUPLICATES / NEAR-DUPLICATES (should detect similarity):
    eval_001 + eval_002 + eval_010: AI code review / PR security / GitHub bot — same domain,
        varying depth. 001 and 002 have full materials, 010 is idea-only and shallower.
    eval_005 + eval_015: Decentralized ML marketplace vs decentralized dataset marketplace —
        structurally identical business model, different asset type.

  STRONG + RELEVANT (should score high on both novelty and relevance):
    eval_003: TEE-based medical records — unique domain, deep technical detail, full materials.
    eval_006: Real-time LLM bias detection — production-grade, strong technical depth.
    eval_009: On-device federated learning — detailed architecture, idea-only.
    eval_016: Adversarial robustness testing platform — unique niche, highly technical.

  RELEVANT BUT LOW NOVELTY (common ideas, well-executed):
    eval_001: AI code review — solid but crowded space.
    eval_002: PR security scanner — very similar to 001.
    eval_010: GitHub code quality bot — lightweight version of 001/002.

  OFF-TOPIC (should get low relevance for an AI/ML hackathon):
    eval_007: Recipe sharing app — consumer social, no AI angle.
    eval_011: Smart greenhouse controller — IoT/hardware, borderline.
    eval_012: Payment splitting app — fintech, no AI.
    eval_017: Fitness tracking app — consumer health, no AI.
    eval_020: Event planning platform — logistics, no AI.

  BUZZWORD SOUP / LOW SUBSTANCE (should score low on feasibility):
    eval_004: "An app that uses AI to help people." — minimal effort.
    eval_008: Web3+AI+quantum buzzword salad — no concrete plan.
    eval_018: "Revolutionary AI blockchain metaverse" — another buzzword entry.

  IDEA-ONLY (no repo, no deck — tests quick vs analyze routing):
    eval_009, eval_010, eval_011, eval_012, eval_013, eval_014, eval_015,
    eval_016, eval_017, eval_018, eval_019, eval_020

  EDGE CASES:
    eval_004: Extremely short idea text (single sentence).
    eval_013: Very long, rambling idea with excessive detail — tests whether length ≠ quality.
    eval_014: Non-English mixed in — idea is mostly English but has untranslated technical jargon.
    eval_019: Ethically sensitive topic — AI surveillance. Tests if scoring is content-neutral.

Not committed as pytest fixtures — used only by scripts/eval_pipeline.py.
"""

EVAL_SUBMISSIONS = [
    # --- 001-003: Full materials (idea + repo + deck) ---
    {
        "submission_id": "eval_001",
        "idea_text": (
            "An AI-powered code review tool that automatically analyzes pull requests for bugs, "
            "security vulnerabilities, and code quality issues. Uses a fine-tuned LLM to provide "
            "inline suggestions with explanations and severity ratings. The system learns from "
            "accepted and rejected suggestions to improve over time, building a per-repository "
            "model of what 'good code' looks like for that specific team."
        ),
        "repo_summary": (
            "Built on Python with LangChain. Uses GPT-4 to analyze git diffs and identifies patterns "
            "from a curated database of 10,000+ common vulnerability signatures. Provides per-suggestion "
            "confidence scores. Integrates with GitHub, GitLab, and Bitbucket via webhooks. "
            "Custom fine-tuning pipeline using DPO on 50k labeled accept/reject pairs from open-source repos. "
            "Evaluation harness with precision/recall metrics against known CVE-introducing commits."
        ),
        "deck_text": (
            "Market: 27M developers globally. Problem: Code review takes 2+ hours per PR on average "
            "and misses 40% of security issues. Solution: Reduce review time by 60% with AI assistance. "
            "Revenue model: SaaS per-seat pricing, $15/user/month. Year 1 target: 500 enterprise teams. "
            "Competitive advantage: fine-tuned per-repo models that learn team conventions, not just "
            "generic linting. Early design partners: 3 YC companies with 50+ engineer teams."
        ),
    },
    {
        "submission_id": "eval_002",
        "idea_text": (
            "AI-powered security scanner for pull requests that detects vulnerabilities and malicious "
            "code patterns. Integrates directly with GitHub Actions to automatically block merges "
            "that introduce security regressions. Unlike static analysis tools, it understands "
            "semantic context — e.g., it can detect that a new SQL query is constructed from "
            "user input three function calls away, even across file boundaries."
        ),
        "repo_summary": (
            "TypeScript/Node.js GitHub App. Uses Claude API to analyze PR diffs for OWASP Top 10 "
            "vulnerabilities, SQL injection, and XSS. Cross-references findings with CVE database. "
            "Generates remediation suggestions as PR comments. Call-graph analysis built on "
            "tree-sitter AST parsing for Python, TypeScript, Go, and Java. Benchmarked against "
            "SemGrep and CodeQL on OWASP Benchmark — 23% higher true positive rate."
        ),
        "deck_text": (
            "Addresses the $8B DevSecOps market. 73% of breaches originate from vulnerable code. "
            "Our tool shifts security left, catching issues before they reach production. "
            "B2B SaaS, $20/developer/month. Integration with Jira and Slack for triage workflows. "
            "Key differentiator: cross-file semantic analysis, not pattern matching. "
            "LOI from 2 Fortune 500 security teams for pilot program."
        ),
    },
    {
        "submission_id": "eval_003",
        "idea_text": (
            "Secure multi-hospital medical records platform using Trusted Execution Environments (TEEs) "
            "to enable collaborative research across institutions without ever exposing raw patient data. "
            "Hospitals can run federated queries and analytics while keeping records fully encrypted. "
            "The system supports SQL-like aggregate queries (e.g., 'average blood pressure for diabetic "
            "patients aged 40-60') where the TEE computes the result and adds calibrated noise via "
            "differential privacy before returning it. Individual records never leave the enclave."
        ),
        "repo_summary": (
            "Rust-based enclave application using Intel SGX. Implements differential privacy on all "
            "aggregate query results with configurable epsilon per query class. HIPAA-compliant audit "
            "logs with tamper-evident merkle proofs. Zero-knowledge proofs for access control — a "
            "hospital proves it holds a record without revealing the record. Remote attestation lets "
            "participants verify enclave integrity before submitting data. Custom query planner that "
            "rejects queries returning fewer than k=10 records to prevent re-identification attacks."
        ),
        "deck_text": (
            "Healthcare data silos cost $30B annually in duplicated diagnostics and missed research insights. "
            "Current federated learning tools require sharing model gradients, which can leak patient data "
            "(demonstrated in Carlini et al. 2021). Our TEE approach provides cryptographic privacy "
            "guarantees. Pilot in progress with 3 regional hospital networks covering 2.1M patient records. "
            "Regulatory pre-approval pathway under FDA Digital Health framework. "
            "Revenue: per-query pricing for researchers, annual license for hospital networks."
        ),
    },
    # --- 004: Minimal effort, extremely vague ---
    {
        "submission_id": "eval_004",
        "idea_text": "An app that uses AI to help people.",
        "repo_summary": None,
        "deck_text": None,
    },
    # --- 005: Strong + unique, full materials ---
    {
        "submission_id": "eval_005",
        "idea_text": (
            "Decentralized marketplace for trained ML models where researchers can monetize their work "
            "using blockchain-based licensing. Model weights are stored encrypted and only become "
            "accessible to a buyer after payment is confirmed via smart contract, with automatic "
            "royalty distribution to all contributors in the training pipeline. The marketplace "
            "tracks model lineage — if Model B was fine-tuned from Model A, original authors of A "
            "receive a configurable royalty percentage on every sale of B."
        ),
        "repo_summary": (
            "Solidity smart contracts deployed on an Ethereum L2 (Optimism). Encrypted model weights "
            "stored on IPFS with content-addressed keys. PyTorch integration for model serving via "
            "decentralized inference nodes. ZK proofs allow buyers to verify model performance claims "
            "(accuracy, benchmark scores) without revealing the weights themselves. Model lineage "
            "tracked via on-chain DAG — each model's training provenance is immutable."
        ),
        "deck_text": (
            "ML model training costs $100k to $10M per run, yet researchers have no mechanism to "
            "monetize trained weights beyond publishing papers. Our marketplace enables perpetual "
            "royalties via on-chain licensing. $50M addressable market in year 1 from enterprise "
            "AI teams that need domain-specific models. DAO governance for marketplace policies. "
            "Partnerships with Hugging Face for model hosting integration and arXiv for paper linking."
        ),
    },
    # --- 006: Strong, production-grade, no deck ---
    {
        "submission_id": "eval_006",
        "idea_text": (
            "Real-time bias detection system for LLM outputs in production environments. "
            "The system monitors model responses across multiple demographic and topical dimensions, "
            "flags statistically significant bias patterns, and automatically schedules fine-tuning "
            "correction jobs when bias exceeds configurable thresholds. Uses a sliding window of "
            "10,000 responses per dimension and applies Bonferroni-corrected chi-squared tests "
            "to avoid false positives from multiple comparisons."
        ),
        "repo_summary": (
            "Python FastAPI service deployed as middleware between LLM APIs and client applications. "
            "Uses embedding-based bias classifiers trained on 50,000 labeled examples across 12 "
            "demographic dimensions. Integrates with OpenAI, Anthropic, and Cohere APIs. "
            "Bias metrics stored in Prometheus; Grafana dashboards for ops teams. "
            "RLHF correction pipeline triggered automatically when rolling bias score exceeds threshold. "
            "Latency overhead: <15ms p99 on cached classifier inference."
        ),
        "deck_text": None,
    },
    # --- 007: Off-topic, consumer app, no AI ---
    {
        "submission_id": "eval_007",
        "idea_text": (
            "A recipe sharing app for home cooks that lets users upload photos of their dishes, "
            "share step-by-step cooking instructions, and follow other home chefs. Features include "
            "ingredient-based search, dietary restriction filters, and a weekly meal planner. "
            "Users can create shopping lists from selected recipes that auto-merge overlapping "
            "ingredients. Social features include commenting, recipe remixing (fork a recipe and "
            "modify it), and seasonal cooking challenges with community voting."
        ),
        "repo_summary": (
            "React Native mobile app with Firebase backend. Image upload via Cloudinary with "
            "automatic thumbnail generation. PostgreSQL for recipe storage, Algolia for full-text "
            "search with typo tolerance. 3.2k lines of code. CI/CD via GitHub Actions. "
            "80% test coverage on backend API routes."
        ),
        "deck_text": (
            "The home cooking market is worth $200B. Existing recipe apps lack social features. "
            "We combine recipe sharing with a social feed. Revenue from premium meal plans and "
            "sponsored ingredient partnerships. Target: 100k users in year 1. "
            "Differentiation: recipe forking (like GitHub for recipes) and smart shopping lists."
        ),
    },
    # --- 008: Buzzword soup, no real substance ---
    {
        "submission_id": "eval_008",
        "idea_text": (
            "A next-generation Web3-native AI-powered decentralized autonomous platform leveraging "
            "cutting-edge transformer architectures and zero-knowledge proofs to revolutionize "
            "the paradigm of trustless computation with quantum-resistant blockchain consensus "
            "mechanisms for enterprise-grade scalability. Our proprietary neural-symbolic hybrid "
            "architecture achieves unprecedented synergies between on-chain and off-chain intelligence "
            "layers, enabling a truly decentralized cognitive mesh network."
        ),
        "repo_summary": (
            "Built with Python and JavaScript. Uses various open-source libraries. "
            "Architecture diagram attached. Working on MVP. README has project vision."
        ),
        "deck_text": (
            "Total addressable market: $500B. Our disruptive synergistic platform creates "
            "exponential value through network effects. First-mover advantage in the convergence "
            "of AI, blockchain, and quantum computing. Seeking $5M seed round. "
            "Team: 2 co-founders with 'passion for innovation'."
        ),
    },
    # --- 009-020: Idea-only submissions (no repo, no deck) ---
    {
        "submission_id": "eval_009",
        "idea_text": (
            "An on-device federated learning framework that lets mobile apps collaboratively train "
            "neural networks without sending user data to a central server. Each device computes "
            "local gradient updates, encrypts them with secure aggregation (Bonawitz et al. protocol), "
            "and contributes to a shared global model. Includes automatic model compression for edge "
            "deployment using structured pruning and INT8 quantization, differential privacy guarantees "
            "per update round (epsilon tracked cumulatively across rounds), and a scheduling system "
            "that only trains when the device is charging and on Wi-Fi to minimize user impact. "
            "Targets Android and iOS via a C++ core with platform-specific bindings."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_010",
        "idea_text": (
            "A GitHub bot that reviews pull requests for code quality issues. It scans diffs for "
            "common anti-patterns, checks naming conventions against the repo's style guide, and "
            "leaves inline comments suggesting improvements. Works with Python, TypeScript, and Go. "
            "Configurable via a .codereview.yml file in the repo root."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_011",
        "idea_text": (
            "A smart greenhouse controller that uses sensor arrays and microcontrollers to "
            "autonomously manage temperature, humidity, soil moisture, and lighting. The system "
            "uses historical crop yield data and weather forecasts to optimize growing conditions. "
            "Includes a mobile dashboard for remote monitoring and manual override. Built on "
            "Raspberry Pi with custom PCB sensor boards and a LoRa mesh network for field coverage. "
            "Sensor data is logged to InfluxDB with 10-second granularity. Alert thresholds are "
            "configurable per crop type using a built-in library of 200+ plant profiles."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_012",
        "idea_text": (
            "A peer-to-peer payment splitting app for group expenses. Users scan receipts with "
            "OCR, the app itemizes charges, and each person claims their items. Settlements are "
            "calculated to minimize the number of transactions between group members using a "
            "min-cost flow algorithm. Integrates with Venmo, Zelle, and bank transfers via Plaid. "
            "Supports recurring splits for shared rent and subscriptions with automatic monthly "
            "reminders. Group expense history is exportable as CSV for tax purposes."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_013",
        "idea_text": (
            "So basically what we want to build is like a platform where you can upload any kind of "
            "document — PDFs, Word docs, spreadsheets, whatever — and then you can ask questions about "
            "them in natural language and the system will find the answer. We're thinking of using "
            "embeddings and vector search, probably Pinecone or Weaviate, and then RAG with GPT-4 or "
            "Claude to generate answers. We also want to support multiple languages eventually, and "
            "maybe add a feature where it can summarize entire documents or extract key entities. "
            "Oh and we also want to add collaboration features where teams can share document "
            "collections and annotate AI-generated answers. And maybe a Slack integration. "
            "And an API so other tools can query it. We haven't decided on the tech stack yet but "
            "probably Python backend, React frontend. One of our team members knows Vue though so "
            "maybe Vue. We're also considering adding voice input so you can ask questions by talking "
            "to it, which would be cool for accessibility. And we want to make it work offline too, "
            "or at least have a local mode for sensitive documents that can't leave the company network."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_014",
        "idea_text": (
            "A multi-agent system for automated scientific literature review. Given a research question, "
            "the system dispatches specialized agents: one queries PubMed/arXiv/Semantic Scholar APIs "
            "to retrieve candidate papers, another performs citation graph traversal to find seminal "
            "and recent works, a third extracts methodology sections and builds a structured comparison "
            "table (sample size, metrics, datasets used), and a synthesis agent generates a coherent "
            "literature review draft with proper citations. Uses LangGraph for agent orchestration "
            "with human-in-the-loop checkpoints — the researcher can approve/reject papers at each "
            "stage before the next agent proceeds. Grounding is enforced: every claim in the output "
            "must link to a specific paper section via page number."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_015",
        "idea_text": (
            "A decentralized marketplace for datasets where data providers can list, license, and sell "
            "structured datasets using smart contracts. Buyers purchase access tokens that grant "
            "time-limited or query-limited access to the data. Revenue is split automatically between "
            "the data provider and any upstream contributors whose data was used to derive the dataset. "
            "Data quality is ensured via staked validators who run automated schema checks, freshness "
            "audits, and statistical profiling. Disputes are resolved by a DAO arbitration committee."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_016",
        "idea_text": (
            "An adversarial robustness testing platform for deployed ML models. The system automatically "
            "generates adversarial inputs tailored to the model's domain — perturbed images for vision "
            "models, paraphrased prompts for language models, synthetic edge cases for tabular models. "
            "It runs continuous red-team campaigns against a model endpoint, tracks robustness metrics "
            "over time, and alerts when a model update introduces new vulnerabilities. Attacks are "
            "drawn from a library of 40+ published adversarial techniques (PGD, FGSM, TextFooler, "
            "Tree of Attacks) with automatic hyperparameter search. Results are presented as a "
            "security-style report with severity ratings and reproduction scripts."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_017",
        "idea_text": (
            "A fitness tracking app that lets users log workouts, track calories, and set personal "
            "goals. Features include exercise library with instructional videos, progress charts, "
            "social challenges where friends compete on weekly step counts, and integration with "
            "Apple Health and Google Fit. Premium tier adds personalized workout plans generated "
            "from a template library based on user goals (weight loss, muscle gain, endurance). "
            "Built as a React Native app with a Node.js backend."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_018",
        "idea_text": (
            "A revolutionary AI-blockchain-metaverse convergence platform that tokenizes human "
            "creativity using neural style transfer NFTs minted on a carbon-negative proof-of-stake "
            "chain. Users enter immersive 3D environments where AI co-creates art, music, and "
            "interactive experiences. The platform's native token powers a creator economy with "
            "algorithmic curation and decentralized reputation scores. Integrates with all major "
            "VR headsets and features a proprietary 'Imagination Engine' that turns text prompts "
            "into fully navigable virtual worlds in real-time."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_019",
        "idea_text": (
            "A real-time surveillance optimization system that uses computer vision to track "
            "individuals across multiple camera feeds in public spaces. The system assigns persistent "
            "IDs to people using gait analysis and facial recognition, predicts movement patterns "
            "using a spatio-temporal transformer model, and automatically flags 'anomalous behavior' "
            "such as loitering, running, or deviating from typical pedestrian flow patterns. "
            "Designed for deployment in transit stations and shopping centers. Uses NVIDIA DeepStream "
            "for real-time inference on edge GPUs with <100ms latency per frame."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
    {
        "submission_id": "eval_020",
        "idea_text": (
            "An event planning and coordination platform for corporate teams. Features include "
            "venue search with availability calendars, budget tracking with approval workflows, "
            "attendee RSVP management, dietary preference collection, seating arrangement tool, "
            "and post-event feedback surveys. Integrates with Google Calendar, Outlook, and Slack "
            "for notifications. Supports recurring events with template-based setup. "
            "Built as a SaaS with tiered pricing: free for up to 50 attendees, paid plans for larger events."
        ),
        "repo_summary": None,
        "deck_text": None,
    },
]

# Standard operator config for all eval runs
EVAL_CRITERIA = {"originality": 0.4, "feasibility": 0.3, "impact": 0.3}
EVAL_GUIDELINES = "Focus on technical innovation and real-world applicability in AI and machine learning."
