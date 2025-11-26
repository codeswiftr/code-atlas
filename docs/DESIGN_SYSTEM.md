# Code Atlas Design System

**Version**: 1.0
**Last Updated**: 2025-11-26
**Status**: Foundation for Soft Launch

---

## Brand Overview

Code Atlas is a **CodeSwiftr** product. All design decisions align with the CodeSwiftr brand identity.

### Brand Positioning
- **Domain**: codeswiftr.com
- **Vibe**: Technical, precise, trustworthy
- **Target Audience**: CTOs, VCs, Software Engineers
- **Value Proposition**: Technical truth in minutes. AI-powered code analysis for confident decisions.

### Product Identity
Code Atlas transforms Claude Code session logs into a searchable, queryable knowledge graph. It enables persistent institutional memory for engineering teams using AI-assisted development workflows.

---

## Color System

### Primary Palette

| Token | Hex | RGB | Usage |
|-------|-----|-----|-------|
| `charcoal` | `#111827` | `17, 24, 39` | Primary backgrounds, text |
| `electric-blue` | `#38BDF8` | `56, 189, 248` | Primary accent, interactive elements |
| `clean-white` | `#F8FAFC` | `248, 250, 252` | Secondary background, cards |

### Extended Palette

| Token | Hex | Usage |
|-------|-----|-------|
| `slate-900` | `#0F172A` | Deep backgrounds, headers |
| `slate-800` | `#1E293B` | Card backgrounds, containers |
| `slate-700` | `#334155` | Borders, dividers |
| `slate-600` | `#475569` | Secondary text |
| `slate-400` | `#94A3B8` | Muted text, placeholders |
| `slate-200` | `#E2E8F0` | Light borders |
| `slate-50` | `#F8FAFC` | Light backgrounds |

### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `success` | `#10B981` | Success states, completed |
| `warning` | `#F59E0B` | Warnings, pending |
| `error` | `#EF4444` | Errors, failures |
| `info` | `#38BDF8` | Information, links |

### CSS Variables

```css
:root {
  /* Primary */
  --color-charcoal: #111827;
  --color-electric-blue: #38BDF8;
  --color-clean-white: #F8FAFC;

  /* Semantic */
  --color-bg-primary: #0F172A;
  --color-bg-secondary: #1E293B;
  --color-bg-tertiary: #334155;
  --color-text-primary: #F8FAFC;
  --color-text-secondary: #94A3B8;
  --color-text-muted: #64748B;
  --color-border: #334155;
  --color-accent: #38BDF8;

  /* Status */
  --color-success: #10B981;
  --color-warning: #F59E0B;
  --color-error: #EF4444;
  --color-info: #38BDF8;
}
```

### Dark Mode (Primary)

Code Atlas uses dark mode as the primary theme, aligning with developer tool conventions and reducing eye strain during extended use.

```css
/* Dark mode (default) */
.dark {
  --bg-primary: #0F172A;
  --bg-secondary: #1E293B;
  --text-primary: #F8FAFC;
  --text-secondary: #94A3B8;
}

/* Light mode (optional) */
.light {
  --bg-primary: #FFFFFF;
  --bg-secondary: #F8FAFC;
  --text-primary: #111827;
  --text-secondary: #475569;
}
```

---

## Typography

### Font Stack

```css
:root {
  /* Primary font for UI */
  --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;

  /* Monospace for code and data */
  --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
}
```

### Type Scale

| Token | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| `display-xl` | 48px | 1.1 | 700 | Hero headings |
| `display` | 36px | 1.2 | 700 | Page titles |
| `h1` | 30px | 1.3 | 600 | Section headers |
| `h2` | 24px | 1.35 | 600 | Subsection headers |
| `h3` | 20px | 1.4 | 600 | Card titles |
| `h4` | 18px | 1.4 | 600 | Small headers |
| `body-lg` | 18px | 1.6 | 400 | Lead paragraphs |
| `body` | 16px | 1.6 | 400 | Body text |
| `body-sm` | 14px | 1.5 | 400 | Secondary text |
| `caption` | 12px | 1.4 | 400 | Labels, captions |
| `code` | 14px | 1.5 | 400 | Code blocks |

### Typography CSS

```css
/* Headings */
.display-xl { font-size: 3rem; font-weight: 700; line-height: 1.1; letter-spacing: -0.02em; }
.display { font-size: 2.25rem; font-weight: 700; line-height: 1.2; letter-spacing: -0.02em; }
.h1 { font-size: 1.875rem; font-weight: 600; line-height: 1.3; }
.h2 { font-size: 1.5rem; font-weight: 600; line-height: 1.35; }
.h3 { font-size: 1.25rem; font-weight: 600; line-height: 1.4; }
.h4 { font-size: 1.125rem; font-weight: 600; line-height: 1.4; }

/* Body */
.body-lg { font-size: 1.125rem; line-height: 1.6; }
.body { font-size: 1rem; line-height: 1.6; }
.body-sm { font-size: 0.875rem; line-height: 1.5; }
.caption { font-size: 0.75rem; line-height: 1.4; }

/* Code */
.code { font-family: var(--font-mono); font-size: 0.875rem; }
```

---

## Spacing System

### Base Unit: 4px

| Token | Value | Usage |
|-------|-------|-------|
| `space-0` | 0 | Reset |
| `space-1` | 4px | Tight spacing |
| `space-2` | 8px | Compact elements |
| `space-3` | 12px | Form elements |
| `space-4` | 16px | Default spacing |
| `space-5` | 20px | Component padding |
| `space-6` | 24px | Section spacing |
| `space-8` | 32px | Large spacing |
| `space-10` | 40px | Section margins |
| `space-12` | 48px | Page sections |
| `space-16` | 64px | Major sections |
| `space-20` | 80px | Hero sections |

### Layout Grid

```css
:root {
  --container-max: 1280px;
  --sidebar-width: 280px;
  --header-height: 64px;
  --grid-gap: 24px;
}

/* 12-column grid */
.grid {
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: var(--grid-gap);
}
```

---

## Component Library

### Buttons

#### Primary Button
```css
.btn-primary {
  background: linear-gradient(135deg, #38BDF8 0%, #0EA5E9 100%);
  color: #0F172A;
  font-weight: 600;
  padding: 12px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary:hover {
  background: linear-gradient(135deg, #7DD3FC 0%, #38BDF8 100%);
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(56, 189, 248, 0.3);
}
```

#### Secondary Button
```css
.btn-secondary {
  background: transparent;
  color: #38BDF8;
  font-weight: 600;
  padding: 12px 24px;
  border-radius: 8px;
  border: 1px solid #38BDF8;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-secondary:hover {
  background: rgba(56, 189, 248, 0.1);
}
```

#### Ghost Button
```css
.btn-ghost {
  background: transparent;
  color: #94A3B8;
  font-weight: 500;
  padding: 12px 24px;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-ghost:hover {
  color: #F8FAFC;
  background: rgba(248, 250, 252, 0.05);
}
```

### Cards

```css
.card {
  background: #1E293B;
  border-radius: 12px;
  border: 1px solid #334155;
  padding: 24px;
  transition: all 0.2s ease;
}

.card:hover {
  border-color: #38BDF8;
  box-shadow: 0 4px 20px rgba(56, 189, 248, 0.1);
}

.card-header {
  font-size: 1.25rem;
  font-weight: 600;
  color: #F8FAFC;
  margin-bottom: 12px;
}

.card-body {
  color: #94A3B8;
  line-height: 1.6;
}
```

### Status Badges

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 9999px;
  font-size: 0.75rem;
  font-weight: 600;
}

.badge-success {
  background: rgba(16, 185, 129, 0.1);
  color: #10B981;
  border: 1px solid rgba(16, 185, 129, 0.2);
}

.badge-warning {
  background: rgba(245, 158, 11, 0.1);
  color: #F59E0B;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.badge-error {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.2);
}

.badge-info {
  background: rgba(56, 189, 248, 0.1);
  color: #38BDF8;
  border: 1px solid rgba(56, 189, 248, 0.2);
}
```

### Input Fields

```css
.input {
  background: #0F172A;
  border: 1px solid #334155;
  border-radius: 8px;
  padding: 12px 16px;
  color: #F8FAFC;
  font-size: 1rem;
  width: 100%;
  transition: all 0.2s ease;
}

.input:focus {
  outline: none;
  border-color: #38BDF8;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.1);
}

.input::placeholder {
  color: #64748B;
}

.input-label {
  display: block;
  font-size: 0.875rem;
  font-weight: 500;
  color: #94A3B8;
  margin-bottom: 8px;
}
```

### Tables

```css
.table {
  width: 100%;
  border-collapse: collapse;
}

.table th {
  background: #0F172A;
  color: #94A3B8;
  font-weight: 600;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #334155;
}

.table td {
  padding: 16px;
  border-bottom: 1px solid #1E293B;
  color: #F8FAFC;
}

.table tr:hover {
  background: rgba(56, 189, 248, 0.05);
}
```

---

## Iconography

### Icon Library
Use **Lucide Icons** (lucide.dev) for consistency. They provide clean, minimal icons that align with the technical aesthetic.

### Icon Sizing

| Size | Pixels | Usage |
|------|--------|-------|
| `xs` | 16px | Inline with small text |
| `sm` | 20px | Buttons, inline elements |
| `md` | 24px | Default, navigation |
| `lg` | 32px | Feature icons |
| `xl` | 48px | Hero elements |

### Core Icons for Code Atlas

| Icon | Name | Usage |
|------|------|-------|
| `GitBranch` | Sessions | Session/branch representation |
| `Database` | Graph | Knowledge graph |
| `Sparkles` | AI/LLM | AI-powered features |
| `Search` | Query | Search and discover |
| `FileCode` | Code | Code-related elements |
| `Activity` | Metrics | Monitoring and stats |
| `Shield` | Security | Auth and security |
| `Settings` | Config | Configuration |
| `Terminal` | CLI | Command line interface |
| `Zap` | Fast | Performance indicators |

---

## Motion & Animation

### Timing Functions

```css
:root {
  --ease-out: cubic-bezier(0, 0, 0.2, 1);
  --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

### Duration

| Token | Value | Usage |
|-------|-------|-------|
| `duration-fast` | 100ms | Micro-interactions |
| `duration-normal` | 200ms | Buttons, hovers |
| `duration-slow` | 300ms | Card transitions |
| `duration-slower` | 500ms | Page transitions |

### Animation Presets

```css
/* Fade in */
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* Slide up */
@keyframes slideUp {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Pulse (for loading states) */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* Glow (for accent elements) */
@keyframes glow {
  0%, 100% { box-shadow: 0 0 20px rgba(56, 189, 248, 0.2); }
  50% { box-shadow: 0 0 30px rgba(56, 189, 248, 0.4); }
}
```

---

## Graph Visualization

### Node Colors

| Entity Type | Color | Hex |
|-------------|-------|-----|
| Session | Electric Blue | `#38BDF8` |
| Concept | Purple | `#A78BFA` |
| File | Green | `#34D399` |
| Tool | Orange | `#FB923C` |
| Problem | Red | `#F87171` |
| Solution | Emerald | `#10B981` |

### Edge Styles

| Relationship | Style | Color |
|--------------|-------|-------|
| MENTIONS | Solid | `#64748B` |
| REFERENCES | Dashed | `#94A3B8` |
| SOLVES | Solid, thick | `#10B981` |
| USES | Dotted | `#38BDF8` |

### Graph Visualization CSS

```css
.graph-node {
  stroke-width: 2px;
  transition: all 0.2s ease;
}

.graph-node:hover {
  stroke-width: 3px;
  filter: drop-shadow(0 0 8px currentColor);
}

.graph-node-session { fill: #38BDF8; stroke: #7DD3FC; }
.graph-node-concept { fill: #A78BFA; stroke: #C4B5FD; }
.graph-node-file { fill: #34D399; stroke: #6EE7B7; }
.graph-node-tool { fill: #FB923C; stroke: #FDBA74; }
.graph-node-problem { fill: #F87171; stroke: #FCA5A5; }
.graph-node-solution { fill: #10B981; stroke: #34D399; }

.graph-edge {
  stroke: #64748B;
  stroke-width: 1px;
}

.graph-edge-solves {
  stroke: #10B981;
  stroke-width: 2px;
}
```

---

## CLI Output Styling

### Rich Console Colors

For CLI output using Python's Rich library:

```python
from rich.theme import Theme

code_atlas_theme = Theme({
    "info": "bold cyan",
    "warning": "bold yellow",
    "error": "bold red",
    "success": "bold green",
    "heading": "bold white",
    "muted": "dim white",
    "accent": "bold #38BDF8",
    "session": "#38BDF8",
    "concept": "#A78BFA",
    "file": "#34D399",
    "tool": "#FB923C",
    "problem": "#F87171",
    "solution": "#10B981",
})
```

### CLI Table Styles

```python
from rich.table import Table

def create_styled_table(title: str) -> Table:
    return Table(
        title=title,
        title_style="bold #38BDF8",
        header_style="bold #94A3B8",
        border_style="#334155",
        row_styles=["", "dim"],
    )
```

---

## Responsive Breakpoints

```css
:root {
  --breakpoint-sm: 640px;
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
  --breakpoint-xl: 1280px;
  --breakpoint-2xl: 1536px;
}

/* Mobile first approach */
@media (min-width: 640px) { /* sm */ }
@media (min-width: 768px) { /* md */ }
@media (min-width: 1024px) { /* lg */ }
@media (min-width: 1280px) { /* xl */ }
@media (min-width: 1536px) { /* 2xl */ }
```

---

## Accessibility Guidelines

### Color Contrast
- All text meets WCAG AA standards (4.5:1 for normal text, 3:1 for large text)
- Interactive elements have distinct focus states
- Status colors are not the only indicator (use icons/text too)

### Focus States

```css
.focusable:focus {
  outline: none;
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.4);
}

.focusable:focus:not(:focus-visible) {
  box-shadow: none;
}

.focusable:focus-visible {
  box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.4);
}
```

### Motion Preferences

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Implementation Notes

### Technology Recommendations

| Layer | Recommendation |
|-------|----------------|
| **Framework** | React 18+ with TypeScript |
| **Styling** | Tailwind CSS + CSS Modules |
| **Components** | Radix UI primitives |
| **Icons** | Lucide React |
| **Charts** | Recharts or Visx |
| **Graph Viz** | D3.js or Cytoscape.js |
| **State** | Zustand or Jotai |
| **API** | TanStack Query |

### File Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── ui/           # Base components
│   │   ├── graph/        # Graph visualization
│   │   └── layout/       # Layout components
│   ├── styles/
│   │   ├── tokens.css    # Design tokens
│   │   ├── base.css      # Base styles
│   │   └── components.css
│   ├── lib/
│   │   └── theme.ts      # Theme configuration
│   └── pages/
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-26 | Initial design system based on CodeSwiftr branding |

---

## Related Documents

- [PLAN.md](./PLAN.md) - Implementation roadmap
- [project-brief.md](./project-brief.md) - Product vision
- [FORGE/docs/marketing/SOCIAL_PROFILE_ASSETS.md](../../docs/marketing/SOCIAL_PROFILE_ASSETS.md) - Brand guidelines
