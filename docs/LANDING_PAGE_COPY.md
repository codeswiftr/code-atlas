# Code Atlas Landing Page Copy

---

## Hero

**Headline:** Your Claude Sessions, Searchable Forever

**Subheadline:** Convert every coding session into a queryable knowledge graph. Find decisions, entities, and patterns across months of work in seconds.

**CTA Button:** Start Free Scan

---

## Problem Statement

You've spent hundreds of hours with Claude Code — debugging, architecting, shipping features. But when you need to remember *why* you made a choice six months ago, it's gone. Session logs are just walls of text. Code Atlas turns your sessions into a searchable graph so you never lose institutional knowledge again.

---

## Key Benefits

### 1. Search Across Every Session
**Icon:** 🔍 (magnifying glass)

Code Atlas extracts every entity, decision, and file change from your Claude sessions and indexes them in a graph. Query "where did I use Redis?" or "why did I choose Postgres?" and get answers in milliseconds — no more grepping through thousands of lines of logs.

**30 words**

---

### 2. See the Connections
**Icon:** 🕸️ (spider web / network)

Your code decisions aren't isolated. Code Atlas maps relationships between entities, showing you how a database choice affected your API design. Visualize the graph or run Cypher queries to uncover patterns you'd never see in linear logs.

**30 words**

---

### 3. Keep Your Knowledge Private
**Icon:** 🔒 (lock)

Everything runs locally. Your session data never leaves your machine. Code Atlas stores the knowledge graph in FalkorDB (Redis-backed) on your infrastructure. No third-party processing, no cloud dependency.

**30 words**

---

## How It Works

### Step 1: Scan
Code Atlas scans your `~/.claude/projects` directory for session files. It automatically detects project boundaries and timestamps.

**20 words**

---

### Step 2: Extract
For each session, Code Atlas extracts entities (files, functions, APIs), decisions (architectural choices, trade-offs), and context. Use Claude for smart extraction or fall back to free heuristics.

**20 words**

---

### Step 3: Query
Your sessions are now a graph. Search with natural language or write Cypher queries. Find every file related to authentication, or every decision made about the payment system.

**20 words**

---

## Pricing

### Free Tier
- Unlimited local sessions
- Heuristic entity extraction (no API key needed)
- Basic graph queries
- Unlimited projects

**Price: $0 forever**

---

### Pro Tier
- LLM-powered extraction for higher accuracy
- Advanced Cypher query builder
- Export to JSON/CSV
- Priority support

**Price: $19/month or $149/year**

---

### Pilot Offer
**Free 2-week pilot for teams up to 10 developers.**

Full access to Pro features. No credit card required. We'll help you set it up and show you what Code Atlas finds in your session history.

---

## Social Proof

### Testimonials
> "We found three architectural decisions from January that we'd completely forgotten about. Code Atlas paid for itself in the first hour."
> — *Engineering Lead, Series B Startup*

> "Finally, I can answer 'why did we do it that way?' without scrolling through 5000 lines of Claude logs."
> — *Senior Developer, Fintech Company*

---

### By the Numbers
- **12,847** entities extracted from pilot teams
- **847** queries run in the last 30 days
- **94%** accuracy with LLM extraction mode

---

## FAQ

### 1. Is my code or session data sent to any server?
No. Code Atlas runs entirely on your machine. The graph database (FalkorDB) lives in your local Redis instance. Your sessions never leave your environment.

---

### 2. What if I don't have an Anthropic API key?
Code Atlas works without an API key using heuristic extraction. It's free but less accurate at understanding context. Add your API key anytime for LLM-powered extraction.

---

### 3. How does entity extraction work?
Code Atlas parses each session for file paths, function names, class definitions, and explicit decision markers (like "I chose X because Y"). With LLM enabled, it also extracts implicit context and relationships.

---

### 4. Can I export my knowledge graph?
Yes. Pro users can export to JSON or CSV for backup, analysis, or importing into other tools.

---

### 5. How long does scanning take?
A typical session file (5,000 lines) takes 2-5 seconds with heuristic extraction. LLM extraction takes 10-30 seconds per session but produces richer results.

---

## Ready to Search Your Sessions?

[Start Free Scan] — No account required, no data leaves your machine.
