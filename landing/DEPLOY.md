# Code Atlas Landing Page — Deployment Guide

## Overview

`index.html` is a fully self-contained landing page. No build step, no local asset pipeline.
The only external dependency is Google Fonts (loaded via `<link>` in the `<head>`). All CSS
and markup are inline. Open it directly in a browser or serve it from any static host.

## Local Preview

```bash
# Open directly (no server needed — fonts require internet)
open /home/openclaw/work/FORGE/portfolio/codeswiftr-com/code-atlas/landing/index.html

# Or serve with any static server for accurate font rendering
python3 -m http.server 8080 --directory /home/openclaw/work/FORGE/portfolio/codeswiftr-com/code-atlas/landing
# then open http://localhost:8080
```

---

## Deployment Targets

### Cloudflare Pages (recommended)

1. Push the repo to GitHub (already done if you are reading this in the FORGE repo).
2. In the Cloudflare dashboard, go to **Pages → Create a project → Connect to Git**.
3. Select the FORGE repository.
4. Set the following build settings:

   | Setting | Value |
   |---------|-------|
   | Build command | *(leave blank — no build step)* |
   | Build output directory | `portfolio/codeswiftr-com/code-atlas/landing` |
   | Root directory | *(leave blank)* |

5. Click **Save and Deploy**.
6. Assign a custom domain: `atlas.codeswiftr.com`.
7. In domain settings, enable **Always Use HTTPS** and **Auto Minify** (HTML + CSS).

Cloudflare Pages serves `index.html` automatically as the root document.

### Netlify

```bash
# Option 1: drag-and-drop
# Drag the landing/ folder to https://app.netlify.com/drop

# Option 2: CLI deploy
cd portfolio/codeswiftr-com/code-atlas/landing
npx netlify-cli deploy --prod --dir .
```

Or connect GitHub and set publish directory to
`portfolio/codeswiftr-com/code-atlas/landing`.

### Vercel

```bash
cd portfolio/codeswiftr-com/code-atlas/landing
npx vercel --prod
```

Set the output directory to `.` (current directory, single-file project).

---

## Before Going Live — Required Changes

### 1. Update domain references

Search `index.html` for `atlas.codeswiftr.com` and confirm all occurrences match the
actual custom domain you assign in Cloudflare:

| Meta tag / field | Current value |
|-----------------|---------------|
| `og:url` | `https://atlas.codeswiftr.com` |
| `og:image` | `https://atlas.codeswiftr.com/assets/og.png` |
| `twitter:image` | `https://atlas.codeswiftr.com/assets/og.png` |
| JSON-LD `url` | `https://atlas.codeswiftr.com` |

### 2. Create the OG image

Add a real Open Graph image at the path referenced above:

```
https://atlas.codeswiftr.com/assets/og.png
```

Recommended: 1200 × 630 px. Dark background (`#070B14`), the graph node SVG from the
hero, headline "Your codebase, as a knowledge graph" in white, accent `#7B6CF6`.

To serve it from Cloudflare Pages, add `assets/og.png` to this `landing/` directory and
it will be deployed automatically.

### 3. Verify CTA links

The following links point to the live app and docs — confirm they resolve before launch:

| Link text | URL |
|-----------|-----|
| "Get started free" | `https://atlas.codeswiftr.com/signup` |
| "Start Pro trial" | `https://atlas.codeswiftr.com/signup?plan=pro` |
| "View docs" | `https://docs.atlas.codeswiftr.com/quickstart` |
| "API reference" | `https://atlas.codeswiftr.com/api/docs` |
| "Changelog" | `https://atlas.codeswiftr.com/changelog` |

### 4. Verify pricing

The pricing section shows:

| Tier | Price |
|------|-------|
| Free | $0/month — up to 100 sessions |
| Pro  | $19/month — unlimited sessions |

Confirm these match the live product before launch. Update by searching `price-amount`
in `index.html`.

### 5. Stats strip

The stats strip contains these figures — replace with real data at launch:

| Placeholder | Replace with |
|-------------|--------------|
| `6` entity types | Real count from schema |
| `3` search modes | Real count |
| `<2s` to ingest | Real p50 benchmark |
| `REST` | Stays as-is (factual) |

---

## Analytics

Add your analytics snippet before `</body>`. Plausible is recommended (privacy-first,
no cookie banner needed):

```html
<script defer data-domain="atlas.codeswiftr.com"
  src="https://plausible.io/js/script.js"></script>
```

PostHog (consistent with the rest of the CodeSwiftr portfolio):

```html
<script>
  /* PostHog snippet here */
</script>
```

Comply with GDPR and CCPA before adding cookie-setting trackers.

---

## Performance Checklist

- [ ] Lighthouse score 90+ (Performance, Accessibility, Best Practices, SEO)
- [ ] OG image created and URL updated in meta tags
- [ ] Domain references point to real custom domain
- [ ] CTA links resolve (signup, docs, API reference)
- [ ] Pricing confirmed with product team
- [ ] Stats strip reflects real benchmarks
- [ ] Analytics snippet added
- [ ] Custom domain connected in Cloudflare Pages (`atlas.codeswiftr.com`)
- [ ] HTTPS redirect enabled in Cloudflare
- [ ] Google Fonts loads correctly on the live domain (check for mixed-content warnings)

---

## File Structure

```
landing/
  index.html   # Self-contained landing page (HTML + inline CSS, Google Fonts only)
  DEPLOY.md    # This file
```

## Tech Notes

- Zero JavaScript — HTML + CSS only. Fully accessible without JS.
- FAQ accordion uses native `<details>`/`<summary>` — no JS required.
- CSS custom properties (design tokens) defined in `:root` — re-theme by changing
  `--accent-primary`, `--bg-base`, and gradient variables only.
- Dark theme: background `#070B14`, accent `#7B6CF6` (indigo/violet), teal `#2DD4BF`.
- Responsive breakpoints at 960px and 640px.
- All hover animations use `opacity` + `transform` (GPU-composited, no layout shifts).
- WCAG AA contrast maintained throughout.
- Sticky glassmorphism nav, smooth scroll, and `focus-visible` styles included.
- Semantic HTML with ARIA labels, landmark regions, and `role="list"` on grids.
- JSON-LD structured data for SEO (SoftwareApplication schema with Free + Pro offers).
- Hero graph is a pure SVG — no canvas, no external library, no JS.
