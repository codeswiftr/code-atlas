# Pilot Onboarding Guide

Welcome to the Code Atlas pilot. This guide walks you through setup, first use, and team configuration. Total time: about 20 minutes.

---

## Step 1: Account Setup (5 min)

1. Go to **codeatlas.dev/pilot/signup**
2. Sign in with GitHub (we use GitHub OAuth -- no new password to manage)
3. Enter the pilot invite code provided in your welcome email
4. Confirm your email address when prompted

Your account is automatically provisioned with Pro-tier features for the duration of the pilot. No credit card required.

**Verify it worked:** Your dashboard should show a "Pro (Pilot)" badge in the top-right corner next to your avatar.

---

## Step 2: Connect Claude Code Sessions (5 min)

Code Atlas indexes your Claude Code session logs to build knowledge graphs. Session logs stay on your machine -- only structural metadata (file paths, tool usage, session timestamps) is transmitted when you opt in.

### Option A: CLI Integration (Recommended)

```bash
# Install the Code Atlas CLI
npm install -g @codeatlas/cli

# Authenticate with your account
codeatlas auth login

# Point to your Claude Code session directory
codeatlas sessions connect

# Verify the connection
codeatlas sessions status
```

The CLI auto-detects the default Claude Code session log location. If your logs are in a non-standard path, specify it:

```bash
codeatlas sessions connect --path /path/to/claude-code/sessions
```

### Option B: Manual Upload

1. Open **codeatlas.dev/dashboard/sessions**
2. Click **Upload Sessions**
3. Select your Claude Code session log files (`.json` format)
4. Wait for processing to complete (typically under 60 seconds per session)

### Verify

After connecting, your dashboard should show a session count greater than zero within 2 minutes. If it shows zero after 5 minutes, check the troubleshooting section below.

---

## Step 3: First Graph Exploration (10 min)

Once sessions are indexed, your knowledge graph is ready to explore.

### 3.1 Open the Graph View

Navigate to **codeatlas.dev/dashboard/graph**. You should see nodes representing files, functions, and decisions from your Claude Code sessions.

### 3.2 Try These Actions

| Action | How | What You'll See |
|--------|-----|-----------------|
| **Search** | Type a filename or keyword in the search bar | Matching nodes highlighted, with session context |
| **Filter by date** | Use the date range picker above the graph | Graph scoped to sessions in that window |
| **Inspect a node** | Click any node | Right panel shows: what changed, which session, AI reasoning |
| **Trace a decision** | Click "Show decision trail" on any node | Chain of related changes across sessions |
| **Full-text search** | Use the search bar with natural language (e.g., "auth refactor") | Ranked results from session logs |

### 3.3 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `/` | Focus search bar |
| `Esc` | Close side panel |
| `F` | Fit graph to screen |
| `R` | Reset filters |
| `?` | Show all shortcuts |

---

## Step 4: Setting Up a Team Workspace

If you have 2+ team members in the pilot, set up a shared workspace so everyone sees the same graph.

1. Go to **codeatlas.dev/dashboard/team**
2. Click **Create Workspace**
3. Name your workspace (e.g., your team or project name)
4. Click **Invite Members** and enter their email addresses
5. Each invited member receives an email with a join link

### Permissions

| Role | Can View | Can Upload | Can Admin |
|------|----------|------------|-----------|
| Member | Yes | Yes | No |
| Admin | Yes | Yes | Yes |

The workspace creator is automatically an Admin. You can promote members to Admin from the team settings page.

### Shared vs. Personal Graphs

- **Personal graph**: Built from your sessions only. Visible only to you.
- **Team graph**: Merges sessions from all workspace members. Visible to the entire workspace.

Both are accessible from the graph view -- use the dropdown in the top-left corner to switch.

---

## Step 5: Getting Help

### Support Channels

| Channel | Response Time | Best For |
|---------|---------------|----------|
| **Pilot Slack channel** | < 4 hours (business days) | Quick questions, feedback, feature requests |
| **Email: pilot-support@codeatlas.dev** | < 24 hours | Detailed bug reports, account issues |
| **Onboarding call** | Scheduled | Walkthrough, team setup, troubleshooting |

### Troubleshooting

**Sessions not appearing after connecting:**
- Confirm the CLI is authenticated: `codeatlas auth status`
- Check the session path: `codeatlas sessions status`
- Ensure session log files are valid JSON and non-empty
- Try a manual re-sync: `codeatlas sessions sync`

**Graph is empty or incomplete:**
- Processing can take up to 5 minutes for large session histories
- Check the processing queue: **Dashboard > Sessions > Processing Status**
- If stuck, contact support with your account email

**Invite emails not arriving:**
- Check spam/junk folders
- Ensure the email address matches the recipient's GitHub account email
- Re-send from **Dashboard > Team > Pending Invites**

### Feedback

We actively want your feedback during the pilot. You can share it through:

- The Slack channel (preferred for quick notes)
- The in-app feedback button (bottom-right corner of any page)
- The weekly survey (sent via email each Monday)

Your input directly shapes what we build next. Every piece of feedback is read by the team.
