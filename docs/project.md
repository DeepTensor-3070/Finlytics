# Problem

**Imagine a small business owner approaches a bank for a loan of ₹50 lakh.**

The bank wants to know:

1. Is this business financially healthy?
2. Can it repay the loan?
3. Is its revenue genuine and sustainable?
4. Are its customers paying on time?
5. Is the company facing any major problems?
6. Is giving this business a loan too risky?

--> Traditionally, a financial analyst manually checks bank statements, GST returns, balance sheets, and other documents. The analyst may also search the internet for information about the business.

# Our Project: Finlytics
**Aim to automate much of this investigation using AI, financial analysis, & live web intelligence.**

```
In One Line: Finlytics is an AI-powered financial investigation system that helps banks and fintech lenders evaluate a business's credit risk by combining financial document analysis with verified external information.
```

# What Problem we are solving ?
Financial documents show what happened in the past, but external information can help explain what is happening now and what risks may arise next.

### There are 2 types of evidence:
1. Internal financial evidence
    GST returns
    Bank statements
    Financial statements
    Ledgers

These help explain the company's financial condition.

2. External evidence

    Customer failures
    Industry downturns
    Regulatory events
    Market changes
    Company news

These help explain events outside the financial statements that might affect the company's future.

# Why is this useful?
1. Reduce repetitive manual investigation.
2. Identify financial anomalies.
3. Investigate risks using external evidence.
4. Make financial assessments more consistent.
5. Provide explanations and supporting sources.


# How does Finlytics work?
Project follows major 5 steps: Understand, Analyze, Investigate, Verify & Explain.

### Step-1: Understand - Read Financial Documents
The user upload docs, such as:
    Bank Statement
    GST return
    Ledgers
    Financial Statement

The system extracts useful info from these docs.

**Technical Concepts: OCR, doc parsing & data extraction**

### Step-2: Analyze - Calculate financial indicators
Once info extracted, the system calculates financial KPIs(Key Performance Indicator)

Includes:
    Revenue Growth
    Operating Cash Flow
    Liquidity
    Leverage
    Receivable growth

Next system looks unusual patterns.

**Technicl concept: XGBoost, anomaly detection, & SHAP**

### Step-3: Investigate - AI decides what to investigate next
Instead of stopping after finding a financial anomaly, an AI agent determines what additional information might be needed.

Suppose the system identifies a 47% increase in receivables.

It might ask:

    Why are receivables increasing?
    Is a major customer delaying payments?
    Has a customer experienced a business disruption?
    Is the problem specific to this company or affecting the whole industry?

The agent then selects an appropriate tool to investigate these questions.

**Technical Concept: ReAct agent**


### Step-4: Verify - Use TinyFish to investigate external evidence
The agent can use TinyFish tools to search websites, retrieve information from URLs, or investigate a goal through a web agent.

Suppose the agent suspects that a major customer is experiencing financial difficulties.

It can:

    Search for information about the customer.
    Retrieve relevant public information.
    Identify evidence related to the suspected disruption.
    Cross-check the evidence.
    Use the findings to update its risk assessment.

The important point is that finding a news article does not automatically prove a financial risk. The evidence must be relevant, credible, and connected to the company being assessed.

### Step 5: Explain — Generate the final report

Finally, the system combines the financial analysis and external evidence.

The proposed report includes:

    Risk score
    Risk drivers
    External signals
    Supporting evidence
    Source citations
    Recommendations

# Users
Bank & NBFCs
FinTech Leaders
Loan officers
MSMEs

# What's Innovative?
1. Financial analysis combined with external intelligence

The system does not rely exclusively on historical financial documents. It also investigates relevant external events.

2. Agent-driven investigation

The AI agent selects tools according to the information it needs, instead of performing the same fixed search for every business.

3. Evidence-based explanations

The system aims to provide supporting evidence and citations for its risk findings, making the assessment easier for an analyst to review.

4. Human-supervised credit assessment

The goal is to automate repetitive investigation, not replace experienced financial analysts. The analyst can use the report to investigate risks and make a more informed lending decision.

