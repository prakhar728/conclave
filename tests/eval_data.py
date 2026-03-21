"""
Realistic test submissions for live pipeline evaluation (Phase 5.5).

6 submissions with intentional variety to exercise all 3 triage branches:
  - eval_001 + eval_002: similar ideas (AI code review vs PR security scanner)
                         → one should be flagged as duplicate OR both to analyze
  - eval_003: TEE-based medical records (unique domain) → analyze
  - eval_004: vague "AI app" with no materials → quick
  - eval_005: decentralized ML model marketplace → analyze
  - eval_006: real-time LLM bias detection, no deck → analyze

Not committed as pytest fixtures — used only by scripts/eval_pipeline.py.
"""

EVAL_SUBMISSIONS = [
    {
        "submission_id": "eval_001",
        "idea_text": (
            "An AI-powered code review tool that automatically analyzes pull requests for bugs, "
            "security vulnerabilities, and code quality issues. Uses a fine-tuned LLM to provide "
            "inline suggestions with explanations and severity ratings."
        ),
        "repo_summary": (
            "Built on Python with LangChain. Uses GPT-4 to analyze git diffs and identifies patterns "
            "from a curated database of 10,000+ common vulnerability signatures. Provides per-suggestion "
            "confidence scores. Integrates with GitHub, GitLab, and Bitbucket via webhooks."
        ),
        "deck_text": (
            "Market: 27M developers globally. Problem: Code review takes 2+ hours per PR on average "
            "and misses 40% of security issues. Solution: Reduce review time by 60% with AI assistance. "
            "Revenue model: SaaS per-seat pricing, $15/user/month. Year 1 target: 500 enterprise teams."
        ),
        # "score": 37, # Placeholder score for testing triage logic; not based on actual evaluation criteria
    },
    {
        "submission_id": "eval_002",
        "idea_text": (
            "AI-powered security scanner for pull requests that detects vulnerabilities and malicious "
            "code patterns. Integrates directly with GitHub Actions to automatically block merges "
            "that introduce security regressions."
        ),
        "repo_summary": (
            "TypeScript/Node.js GitHub App. Uses Claude API to analyze PR diffs for OWASP Top 10 "
            "vulnerabilities, SQL injection, and XSS. Cross-references findings with CVE database. "
            "Generates remediation suggestions as PR comments."
        ),
        "deck_text": (
            "Addresses the $8B DevSecOps market. 73% of breaches originate from vulnerable code. "
            "Our tool shifts security left, catching issues before they reach production. "
            "B2B SaaS, $20/developer/month. Integration with Jira and Slack for triage workflows."
        ),
        # "score": 37, # Placeholder score for testing triage logic; not based on actual evaluation criteria

    },
    {
        "submission_id": "eval_003",
        "idea_text": (
            "Secure multi-hospital medical records platform using Trusted Execution Environments (TEEs) "
            "to enable collaborative research across institutions without ever exposing raw patient data. "
            "Hospitals can run federated queries and analytics while keeping records fully encrypted."
        ),
        "repo_summary": (
            "Rust-based enclave application using Intel SGX. Implements differential privacy on all "
            "aggregate query results. HIPAA-compliant audit logs with tamper-evident merkle proofs. "
            "Zero-knowledge proofs for access control — a hospital proves it holds a record without "
            "revealing the record. Remote attestation lets participants verify enclave integrity."
        ),
        "deck_text": (
            "Healthcare data silos cost $30B annually in duplicated diagnostics and missed research insights. "
            "Current federated learning tools require sharing model gradients, which can leak patient data. "
            "Our TEE approach provides cryptographic privacy guarantees. Pilot in progress with 3 "
            "regional hospital networks. Regulatory pre-approval pathway under FDA Digital Health framework."
        ),
        # "score": 37, # Placeholder score for testing triage logic; not based on actual evaluation criteria

    },
    {
        "submission_id": "eval_004",
        "idea_text": "An app that uses AI to help people.",
        "repo_summary": None,
        "deck_text": None,
        # "score": 37, # Placeholder score for testing triage logic; not based on actual evaluation criteria

    },
    {
        "submission_id": "eval_005",
        "idea_text": (
            "Decentralized marketplace for trained ML models where researchers can monetize their work "
            "using blockchain-based licensing. Model weights are stored encrypted and only become "
            "accessible to a buyer after payment is confirmed via smart contract, with automatic "
            "royalty distribution to all contributors in the training pipeline."
        ),
        "repo_summary": (
            "Solidity smart contracts deployed on an Ethereum L2 (Optimism). Encrypted model weights "
            "stored on IPFS with content-addressed keys. PyTorch integration for model serving via "
            "decentralized inference nodes. ZK proofs allow buyers to verify model performance claims "
            "(accuracy, benchmark scores) without revealing the weights themselves."
        ),
        "deck_text": (
            "ML model training costs $100k to $10M per run, yet researchers have no mechanism to "
            "monetize trained weights beyond publishing papers. Our marketplace enables perpetual "
            "royalties via on-chain licensing. $50M addressable market in year 1 from enterprise "
            "AI teams that need domain-specific models. DAO governance for marketplace policies."
        ),
        # "score": 37, # Placeholder score for testing triage logic; not based on actual evaluation criteria

    },
    {
        "submission_id": "eval_006",
        "idea_text": (
            "Real-time bias detection system for LLM outputs in production environments. "
            "The system monitors model responses across multiple demographic and topical dimensions, "
            "flags statistically significant bias patterns, and automatically schedules fine-tuning "
            "correction jobs when bias exceeds configurable thresholds."
        ),
        "repo_summary": (
            "Python FastAPI service deployed as middleware between LLM APIs and client applications. "
            "Uses embedding-based bias classifiers trained on 50,000 labeled examples across 12 "
            "demographic dimensions. Integrates with OpenAI, Anthropic, and Cohere APIs. "
            "Bias metrics stored in Prometheus; Grafana dashboards for ops teams. "
            "RLHF correction pipeline triggered automatically when rolling bias score exceeds threshold."
        ),
        "deck_text": None,
        # "score": 37, # Placeholder score for testing triage logic; not based on actual evaluation criteria

    },
]

# Standard operator config for all eval runs
EVAL_CRITERIA = {"originality": 0.4, "feasibility": 0.3, "impact": 0.3}
EVAL_GUIDELINES = "Focus on technical innovation and real-world applicability."
