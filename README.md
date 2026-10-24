# Finlytics — AI Financial Due Diligence Agent

> **From financial documents to evidence-backed credit intelligence.**

 Finlytics is a proposed AI-assisted financial due-diligence platform for lenders, fintech companies, and financial analysts. It aims to turn financial documents into explainable risk signals, investigate important anomalies, and connect findings to traceable supporting evidence.

The central idea is simple: **don't stop at identifying a financial anomaly—investigate why it matters, look for relevant evidence, and clearly show what is verified, uncertain, or contradicted.**

> **Project status:** Hackathon prototype / active development. Capabilities described as planned or optional may not yet be implemented. The demo may use synthetic data and simulated external evidence; simulated evidence must never be presented as live-verified information.

## Table of Contents

- [Problem Statement](#problem-statement)
- [Our Solution](#our-solution)
- [Key Features](#key-features)
- [How It Works](#how-it-works)
- [Example Investigation](#example-investigation)
- [Proposed Architecture](#proposed-architecture)
- [Technology Stack](#technology-stack)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [Demo Mode and Evidence Integrity](#demo-mode-and-evidence-integrity)
- [Project Structure](#project-structure)
- [Security and Responsible Use](#security-and-responsible-use)
- [Roadmap](#roadmap)
- [Team](#team)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)

## Problem Statement

Financial due diligence often requires analysts to review multiple sources, such as:

- Bank statements
- GST returns and tax documents
- Ledgers and receivables reports
- Financial statements
- Company and industry information from external sources

Manual review can be time-consuming and repetitive. Financial figures may tell only part of the story, and an unusual metric does not automatically explain its cause. Analysts need a way to identify relevant questions, investigate them, and trace conclusions back to their evidence.

## Our Solution

 Finlytics is designed as an **evidence-driven financial investigation workflow**. It aims to:

1. Extract useful financial information from uploaded documents.
2. Calculate financial indicators and flag unusual patterns.
3. Turn important signals into investigation questions.
4. Retrieve relevant external information through configured search tools.
5. assess whether evidence supports, contradicts, or fails to resolve a hypothesis.
6. Present an explainable risk summary with source references and open questions.

 Finlytics  is intended to **support financial analysts, not replace their judgment**.

## Key Features

The following describes the intended product scope. Check the current implementation before treating any feature as production-ready.

- **Document-based analysis:** Work with supported financial documents and structured data.
- **Financial signal detection:** Calculate indicators and highlight patterns that may need investigation.
- **AI-assisted investigation:** Use an agent workflow to identify information gaps and select appropriate tools.
- **External evidence retrieval:** Connect to an external research provider, such as TinyFish, when configured.
- **Evidence status tracking:** Distinguish findings that are supported, corroborated, contradicted, unverified, or inconclusive.
- **Interactive investigation graph:** Explore relationships among financial metrics, hypotheses, sources, and findings.
- **Explainable findings:** Show why a signal matters and which evidence supports the conclusion.
- **Risk report:** Summarize key signals, evidence, uncertainty, and suggested follow-up questions.
- **Demo mode:** Demonstrate the workflow using clearly labelled synthetic data when live integrations are unavailable.

## How It Works

### 1. Understand

Upload supported financial files and extract relevant data. The exact file formats and extraction coverage depend on the implementation.

### 2. Analyze

Calculate financial indicators and flag patterns such as rising receivables, weakening cash flow, or changes in revenue. A flagged pattern is a **signal to investigate**, not proof of fraud or financial distress.

### 3. Investigate

An agent can turn a signal into a question, identify missing information, and decide which available tool could help answer it.

### 4. Verify

Retrieve relevant external evidence when a live provider is configured. Check that the source relates to the correct company and that it actually supports the claim. Preserve conflicting or incomplete evidence rather than hiding it.

### 5. Explain

Present the findings with source references, evidence status, limitations, and follow-up questions so a human reviewer can assess the result.

## Example Investigation

**Illustrative scenario only — not a real company assessment.**

Suppose a sample business shows:

- Revenue increased by 32%.
- Operating cash flow decreased by 18%.
- Receivables increased by 47%.

These figures may suggest that reported growth is not translating into cash collection at the same rate. They do **not** establish the cause.

 Finlytics  could create an investigation question such as:

> Why are receivables increasing while operating cash flow is decreasing?

The workflow could then seek relevant evidence, check whether it refers to the correct company, and report one of the following:

- **Supported:** The available evidence supports the hypothesis.
- **Corroborated:** Multiple independent, relevant sources support it.
- **Contradicted:** Credible evidence conflicts with the hypothesis.
- **Unverified:** The claim has not been adequately verified.
- **Inconclusive:** Available evidence does not support a reliable conclusion.

The final report should distinguish observed financial data from hypotheses and external findings.

## Proposed Architecture

The following is the proposed architecture, not a guarantee that every component is already implemented.

```text
                 ┌─────────────────────────────┐
                 │       Web Dashboard         │
                 │   React / Next.js / TypeScript
                 └──────────────┬──────────────┘
                                │ HTTP API
                 ┌──────────────▼──────────────┐
                 │        FastAPI Backend      │
                 │ Validation & orchestration  │
                 └──────────────┬──────────────┘
                                │
          ┌─────────────────────┼────────────────────┐
          │                     │                    │
┌─────────▼────────┐  ┌─────────▼────────┐  ┌────────▼─────────┐
│ Document & KPI   │  │ Agent Workflow   │  │ Evidence Search  │
│ Extraction       │  │ LangGraph / ReAct│  │ TinyFish adapter │
└─────────┬────────┘  └─────────┬────────┘  └────────┬─────────┘
          │                     │                    │
          └─────────────────────┼────────────────────┘
                                │
                 ┌──────────────▼─────────────┐
                 │ Evidence, findings & report│
                 │                            │
                 └────────────────────────────┘
```

## Technology Stack

Planned or proposed technologies include:

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | React / Next.js, TypeScript, Tailwind CSS
| Visualizations | Lucide,Lenis, Rechart,three fiber js
| Backend API | Python, FastAPI, Pydantic 
| Data analysis | Pandas, NumPy 
| Agent workflow | LangGraph / ReAct pattern 
| ML explainability |  XGBoost and SHAP 
| Retrieval | Optional embeddings with FAISS or ChromaDB 
| Persistence | PostgreSQL / SQLAlchemy 
| External research | TinyFish integration