# Code Atlas Deployment - Decisions Required

**Task**: TD-005
**Status**: Awaiting human decisions before proceeding
**Created**: 2026-02-08

## Critical Decisions Needed

### Decision 1: FalkorDB Hosting Strategy

**Context**: Code Atlas requires FalkorDB (graph database) for vector search and knowledge graph storage. Railway may not have a native FalkorDB plugin.

**Options**:

| Option | Pros | Cons | Cost | Complexity |
|--------|------|------|------|------------|
| **A. Railway Redis + FalkorDB Module** | - Single platform<br>- Integrated billing<br>- Low latency | - May require custom Redis config<br>- Module compatibility risk | $5-10/month | Medium |
| **B. External FalkorDB Service** | - Managed service<br>- Guaranteed compatibility<br>- Expert support | - Additional platform<br>- Network latency<br>- CORS/networking setup | $10-25/month | Low |
| **C. Railway Redis + Fallback to SQLite** | - Simpler deployment<br>- Railway native | - Reduced graph query performance<br>- Feature limitations | $5/month | Low |
| **D. Self-hosted FalkorDB on Railway** | - Full control<br>- Cost-effective | - Maintenance burden<br>- Scaling complexity | $5/month | High |

**Recommendation**: Option A (Railway Redis + FalkorDB Module) for balance of cost and complexity.

**Required from you**:
- [ ] Choose hosting option: A, B, C, or D
- [ ] If Option B, provide FalkorDB service credentials
- [ ] Approve estimated costs

---

### Decision 2: LLM Mode Configuration

**Context**: Code Atlas can extract entities using:
1. **Heuristic Mode**: Free, no API keys, basic pattern matching
2. **LLM Mode**: Anthropic Claude API, advanced extraction, costs ~$0.02/session

**Options**:

| Mode | Pros | Cons | Monthly Cost (100 sessions) |
|------|------|------|----------------------------|
| **Heuristic Only** | - Free<br>- No API dependencies<br>- Fast deployment | - Lower extraction quality<br>- Limited insights | $0 |
| **LLM Enabled (Soft Launch)** | - Better extraction<br>- Enhanced insights<br>- Full feature set | - Requires API key<br>- Usage costs | ~$2 |
| **Hybrid (Recommended)** | - Heuristic fallback<br>- LLM for premium users<br>- Cost-controlled | - Slightly complex config | ~$1 (with fallback) |

**Recommendation**: Start with Heuristic mode, enable LLM post-launch for specific users.

**Required from you**:
- [ ] Choose mode: Heuristic, LLM, or Hybrid
- [ ] If LLM, provide ANTHROPIC_API_KEY or approve budget
- [ ] Approve cost controls: $0.02/session max, $10/month cumulative

---

### Decision 3: Domain and URL Strategy

**Context**: Railway provides auto-generated URLs. Custom domains improve branding and SEO.

**Options**:

| Option | Backend URL | Frontend URL | Setup Time | Cost |
|--------|-------------|--------------|------------|------|
| **Railway Default** | `code-atlas-api-xyz.railway.app` | `code-atlas-xyz.pages.dev` | 0 min | Free |
| **Custom Subdomain** | `api.codeatlas.codeswiftr.com` | `codeatlas.codeswiftr.com` | 15 min | Free (DNS only) |
| **Separate Domain** | `api.codeatlas.io` | `codeatlas.io` | 30 min | $12/year |

**Recommendation**: Railway default for soft launch, custom subdomain after validation.

**Required from you**:
- [ ] Choose URL strategy: Default, Subdomain, or Separate
- [ ] If custom domain, confirm DNS access to codeswiftr.com
- [ ] Approve SSL certificate auto-generation

---

### Decision 4: Monitoring and Observability

**Context**: Production services need error tracking, performance monitoring, and analytics.

**Options**:

| Service | Purpose | Cost | Setup Effort |
|---------|---------|------|--------------|
| **Sentry** | Error tracking, performance monitoring | Free tier (5K events/mo) | 10 min |
| **PostHog** | Product analytics, user behavior | Free tier (1M events/mo) | 10 min |
| **Railway Metrics** | Infrastructure monitoring | Included | 0 min |
| **None** | Rely on logs only | Free | 0 min |

**Recommendation**: Start with Railway Metrics only, add Sentry after first users.

**Required from you**:
- [ ] Approve monitoring strategy: Railway only, or + Sentry/PostHog
- [ ] If Sentry/PostHog, provide API keys or approve account creation

---

### Decision 5: Deployment Timing and Rollout

**Context**: Code Atlas can deploy immediately or wait for specific milestones.

**Options**:

| Strategy | Description | Risk | Timeline |
|----------|-------------|------|----------|
| **Immediate Soft Launch** | Deploy now, internal testing only | Low (no users) | Today |
| **Beta Launch** | Deploy + invite 5-10 beta testers | Medium (feedback needed) | Next week |
| **Public Launch** | Deploy + announce publicly | High (polish needed) | 2-3 weeks |
| **Defer** | Wait for other MVPs to launch first | Low (no pressure) | TBD |

**Recommendation**: Immediate soft launch for internal validation, beta in 1 week.

**Required from you**:
- [ ] Choose rollout strategy
- [ ] If beta, provide list of beta testers
- [ ] Approve go-live date

---

## Summary: Quick Decision Matrix

**Minimum viable deployment** (can deploy today):
- Decision 1: Railway Redis + FalkorDB Module (Option A)
- Decision 2: Heuristic mode only
- Decision 3: Railway default URLs
- Decision 4: Railway metrics only
- Decision 5: Immediate soft launch

**Estimated deployment time with minimal decisions**: 2.5 hours

**Recommended optimal deployment** (best long-term):
- Decision 1: Railway Redis + FalkorDB Module (Option A)
- Decision 2: Hybrid mode (heuristic + LLM for premium)
- Decision 3: Custom subdomain on codeswiftr.com
- Decision 4: Railway + Sentry
- Decision 5: Immediate soft launch → Beta in 1 week

**Estimated deployment time with optimal setup**: 4 hours

---

## Next Steps After Decisions

Once you provide decisions on items 1-5 above:

1. **Execute deployment** using DEPLOYMENT_RUNBOOK.md
2. **Run smoke tests** (18 tests in tests/e2e/test_smoke.py)
3. **Verify compounding loops** (CL-001 through CL-008)
4. **Document production URLs** in project README
5. **Update infrastructure map** in docs/INFRASTRUCTURE_MAP.md

---

## Questions for Clarification

**Q1**: Do you have an existing Railway account and project for Code Atlas?
- [ ] Yes, project ID: ___________
- [ ] No, will create new project

**Q2**: Do you have Cloudflare Pages access for codeswiftr.com?
- [ ] Yes, can deploy immediately
- [ ] No, need account setup

**Q3**: What is your monthly budget for Code Atlas infrastructure?
- [ ] $0-10 (minimal)
- [ ] $10-25 (recommended)
- [ ] $25-50 (enhanced)
- [ ] No hard budget

**Q4**: Who should have admin API key access?
- [ ] Just you
- [ ] Your team (provide list)
- [ ] Public (no auth)

**Q5**: What is the expected user load for first month?
- [ ] <10 users (internal only)
- [ ] 10-100 users (beta testers)
- [ ] 100-1000 users (soft launch)
- [ ] 1000+ users (public launch)

---

## Contact

Once decisions are made, reply with:
1. Decision numbers and chosen options (e.g., "1A, 2-Hybrid, 3-Subdomain, 4-Railway+Sentry, 5-Soft Launch")
2. Any required credentials (ANTHROPIC_API_KEY, etc.)
3. Approval to proceed with deployment

I will then execute the full deployment and provide production URLs + verification report.

---

**Status**: Awaiting decisions
**Last Updated**: 2026-02-08
**Next Action**: Human decision on items 1-5
