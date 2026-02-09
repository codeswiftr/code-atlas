# Cloudflare Pages Deployment Guide for Code Atlas Frontend

## Overview

Code Atlas frontend is configured for deployment on Cloudflare Pages using Vite + React. This guide validates the deployment configuration and provides a deployment checklist.

## Configuration Files

### wrangler.toml
- **Location**: `/frontend/wrangler.toml`
- **Purpose**: Cloudflare Pages configuration
- **Status**: ✅ Validated

### package.json
- **Location**: `/frontend/package.json`
- **Build Script**: `tsc && vite build`
- **Status**: ✅ Validated

### vite.config.ts
- **Location**: `/frontend/vite.config.ts`
- **Output Directory**: `dist`
- **Status**: ✅ Validated

## Configuration Validation

### Build Configuration ✅

```toml
name = "code-atlas"
compatibility_date = "2024-01-01"
pages_build_output_dir = "dist"

[build]
command = "npm run build"
```

**Validation:**
- ✅ **App Name**: `code-atlas` (consistent naming)
- ✅ **Build Command**: `npm run build` → Runs `tsc && vite build`
- ✅ **Output Directory**: `dist` (matches Vite output)
- ✅ **Compatibility Date**: `2024-01-01` (valid)

**TypeScript Compilation**: The build command includes `tsc` for type checking before build.

**Vite Build**: Optimized production build with:
- Tree shaking
- Minification
- Code splitting
- Asset optimization

### Environment Variables ✅

```toml
[vars]
VITE_APP_NAME = "Code Atlas"

[env.production]
vars = { VITE_APP_ENV = "production" }

[env.preview]
vars = { VITE_APP_ENV = "preview" }
```

**Validation:**
- ✅ **VITE_APP_NAME**: Application name for branding
- ✅ **VITE_APP_ENV**: Environment identifier (production/preview)
- ✅ **Prefix**: All vars use `VITE_` prefix (required for Vite)

**Missing Environment Variables**: ⚠️

The following variables should be added to `wrangler.toml`:

```toml
[env.production.vars]
VITE_APP_ENV = "production"
VITE_API_URL = "https://code-atlas-api.railway.app"  # Backend API URL
VITE_WS_URL = "wss://code-atlas-api.railway.app"     # WebSocket URL

[env.preview.vars]
VITE_APP_ENV = "preview"
VITE_API_URL = "https://code-atlas-preview.railway.app"
VITE_WS_URL = "wss://code-atlas-preview.railway.app"
```

**Action Required**: Add API proxy configuration for production environment.

## Frontend Build Validation

### Build Command Test ✅

```bash
# Navigate to frontend directory
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend

# Install dependencies
npm install

# Run build
npm run build

# Expected output:
# - TypeScript compilation (0 errors)
# - Vite build output
# - dist/ directory created
# - index.html, assets/ with hashed filenames
```

**Build Artifacts:**
- `dist/index.html` - Entry point
- `dist/assets/*.js` - JavaScript bundles (hashed)
- `dist/assets/*.css` - CSS bundles (hashed)
- `dist/assets/*` - Images, fonts, other assets

### Build Output Validation

**Expected Structure:**
```
dist/
├── index.html
├── assets/
│   ├── index-[hash].js
│   ├── index-[hash].css
│   └── vendor-[hash].js
└── favicon.ico
```

**File Size Targets:**
- Initial JS bundle: < 200KB (gzipped)
- Vendor chunk: < 500KB (gzipped)
- CSS bundle: < 50KB (gzipped)

## API Proxy Configuration

### Development (Local) ✅

```typescript
// vite.config.ts
server: {
  port: 5174,
  proxy: {
    '/api': {
      target: 'http://localhost:8002',
      changeOrigin: true,
    },
    '/ws': {
      target: 'ws://localhost:8002',
      ws: true,
    },
  },
}
```

**Validation:**
- ✅ **Port**: 5174 (Code Atlas frontend port)
- ✅ **API Proxy**: `/api` → `http://localhost:8002`
- ✅ **WebSocket Proxy**: `/ws` → `ws://localhost:8002`

### Production (Cloudflare Pages) ⚠️

**Current Issue**: Vite proxy only works in development. Production needs environment variables.

**Solution 1: Environment Variables (Recommended)**

Add to `wrangler.toml`:
```toml
[env.production.vars]
VITE_API_URL = "https://code-atlas-api.railway.app"
```

Update API client to use `import.meta.env.VITE_API_URL`:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8002';
```

**Solution 2: Cloudflare Workers Proxy**

Create `frontend/functions/api/[[path]].ts`:
```typescript
export async function onRequest(context) {
  const url = new URL(context.request.url);
  const apiUrl = `https://code-atlas-api.railway.app${url.pathname.replace('/api', '')}`;

  return fetch(apiUrl, {
    method: context.request.method,
    headers: context.request.headers,
    body: context.request.body,
  });
}
```

**Action Required**: Implement one of the above solutions before production deployment.

## Custom Domain Configuration

### Cloudflare Pages Domain Setup

```toml
# Add to wrangler.toml (optional)
[env.production]
routes = [
  { pattern = "code-atlas.yourdomain.com", custom_domain = true }
]
```

**Steps:**
1. Add custom domain in Cloudflare Pages dashboard
2. Configure DNS CNAME record: `code-atlas` → `code-atlas.pages.dev`
3. Wait for DNS propagation (5-10 minutes)
4. SSL certificate auto-provisioned by Cloudflare

## Deployment Checklist

### Pre-Deployment ✅

- [ ] **Dependencies Installed**: Run `npm install`
- [ ] **TypeScript Errors**: Run `npm run lint` (0 errors)
- [ ] **Build Test**: Run `npm run build` (successful)
- [ ] **Unit Tests**: Run `npm run test` (all passing)
- [ ] **E2E Tests**: Run `npm run test:e2e` (all passing)
- [ ] **Bundle Size**: Check `dist/` output (< 1MB total)
- [ ] **Environment Variables**: Configure API URLs in `wrangler.toml`

### Cloudflare Pages Project Setup ✅

#### Via Wrangler CLI (Recommended)

```bash
# Install Wrangler
npm install -g wrangler

# Login to Cloudflare
wrangler login

# Deploy
cd /Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/frontend
wrangler pages deploy dist --project-name code-atlas
```

#### Via Dashboard

1. Go to https://dash.cloudflare.com/
2. Navigate to **Pages** → **Create a project**
3. Connect GitHub repository: `codeswiftr-com/code-atlas`
4. Configure build:
   - **Framework**: Vite
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: `frontend`
5. Add environment variables:
   - `VITE_API_URL`: Backend API URL
   - `VITE_WS_URL`: WebSocket URL
6. Click **Save and Deploy**

### Post-Deployment ✅

- [ ] **Homepage Loads**: Visit `https://code-atlas.pages.dev`
- [ ] **Assets Load**: Check browser network tab (no 404s)
- [ ] **API Connectivity**: Test API calls (check browser console)
- [ ] **WebSocket Connection**: Test real-time features
- [ ] **Routing Works**: Test navigation between pages
- [ ] **Performance**: Run Lighthouse audit (score > 90)
- [ ] **SSL Certificate**: Verify HTTPS working
- [ ] **Custom Domain** (if configured): Test custom domain access

## Environment Variables

### Required for Production

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `VITE_APP_NAME` | Application name | `Code Atlas` | Yes |
| `VITE_APP_ENV` | Environment identifier | `production` | Yes |
| `VITE_API_URL` | Backend API base URL | `https://code-atlas-api.railway.app` | Yes |
| `VITE_WS_URL` | WebSocket base URL | `wss://code-atlas-api.railway.app` | Yes |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_ENABLE_ANALYTICS` | Enable PostHog analytics | `false` |
| `VITE_POSTHOG_KEY` | PostHog API key | - |
| `VITE_SENTRY_DSN` | Sentry error tracking DSN | - |

### Setting Variables in Cloudflare Pages

#### Via Wrangler

```bash
# Production environment
wrangler pages secret put VITE_API_URL --env production
# Enter value: https://code-atlas-api.railway.app

wrangler pages secret put VITE_WS_URL --env production
# Enter value: wss://code-atlas-api.railway.app
```

#### Via Dashboard

1. Go to project settings
2. Navigate to **Environment variables**
3. Add variables for **Production** and **Preview** environments
4. Redeploy to apply changes

## Performance Optimization

### Build Optimizations ✅

Current Vite configuration includes:

```typescript
build: {
  outDir: 'dist',
  sourcemap: !isProduction,  // Disable in production
}
```

**Additional Recommendations:**

```typescript
build: {
  outDir: 'dist',
  sourcemap: false,
  rollupOptions: {
    output: {
      manualChunks: {
        vendor: ['react', 'react-dom', 'react-router-dom'],
        charts: ['recharts'],
      },
    },
  },
  chunkSizeWarningLimit: 1000,
}
```

### Cloudflare Optimizations

Cloudflare Pages automatically provides:
- ✅ **Global CDN**: Assets served from edge locations
- ✅ **Brotli Compression**: Better than gzip
- ✅ **HTTP/3**: Faster connections
- ✅ **Automatic Minification**: HTML/CSS/JS
- ✅ **Image Optimization**: Cloudflare Images (optional)

## CI/CD Integration

### GitHub Actions (Recommended)

Create `.github/workflows/deploy-frontend.yml`:

```yaml
name: Deploy Frontend to Cloudflare Pages

on:
  push:
    branches: [main]
    paths:
      - 'frontend/**'
  pull_request:
    branches: [main]
    paths:
      - 'frontend/**'

jobs:
  deploy:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Install dependencies
        run: npm ci

      - name: Run tests
        run: npm run test -- --run

      - name: Build
        run: npm run build
        env:
          VITE_API_URL: ${{ secrets.VITE_API_URL }}
          VITE_WS_URL: ${{ secrets.VITE_WS_URL }}

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/pages-action@v1
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          projectName: code-atlas
          directory: frontend/dist
          gitHubToken: ${{ secrets.GITHUB_TOKEN }}
```

### Secrets Required

Add to GitHub repository secrets:
- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`
- `VITE_API_URL`
- `VITE_WS_URL`

## Monitoring

### Cloudflare Analytics

Access via Cloudflare Pages dashboard:
- Page views
- Unique visitors
- Bandwidth usage
- Geographic distribution

### Web Vitals

Monitor Core Web Vitals:
- **LCP** (Largest Contentful Paint): < 2.5s
- **FID** (First Input Delay): < 100ms
- **CLS** (Cumulative Layout Shift): < 0.1

### Error Tracking (Optional)

Integrate Sentry for production error tracking:

```bash
npm install @sentry/react

# Add to wrangler.toml
[env.production.vars]
VITE_SENTRY_DSN = "https://xxx@sentry.io/xxx"
```

## Troubleshooting

### Build Fails

**Check:**
1. Node version: `node --version` (should be 18+)
2. TypeScript errors: `npm run lint`
3. Package dependencies: `npm install`

**Common Issues:**
- Missing dependencies: Run `npm install`
- TypeScript errors: Fix type errors shown in build output
- Out of memory: Increase Node heap size: `NODE_OPTIONS=--max-old-space-size=4096 npm run build`

### Assets Not Loading

**Debug:**
1. Check Cloudflare Pages deployment logs
2. Verify `dist/` contains built files
3. Check browser console for 404 errors
4. Verify base path in `vite.config.ts`

### API Calls Fail

**Debug:**
1. Check `VITE_API_URL` environment variable
2. Verify CORS headers on backend
3. Check browser network tab for failed requests
4. Test API directly: `curl https://code-atlas-api.railway.app/health`

### Routing Issues (404 on Refresh)

**Solution**: Add `_redirects` file:

```bash
# frontend/public/_redirects
/*    /index.html   200
```

This ensures all routes serve `index.html` for client-side routing.

## Rollback Procedure

### Via Cloudflare Dashboard

1. Go to **Pages** → **code-atlas** → **Deployments**
2. Find previous successful deployment
3. Click **Rollback to this deployment**

### Via Wrangler

```bash
# List deployments
wrangler pages deployment list --project-name code-atlas

# Rollback is done by redeploying previous build
```

## Security Considerations

### Content Security Policy

Add to `dist/index.html` (or via Cloudflare headers):

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self';
               script-src 'self' 'unsafe-inline';
               style-src 'self' 'unsafe-inline';
               connect-src 'self' https://code-atlas-api.railway.app">
```

### HTTPS Only

Cloudflare Pages enforces HTTPS by default. Configure HSTS:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Cost Optimization

Cloudflare Pages Free Tier:
- ✅ Unlimited requests
- ✅ Unlimited bandwidth
- ✅ 500 builds/month
- ✅ 1 build at a time

**Paid Plan** ($20/month):
- 5,000 builds/month
- 5 concurrent builds
- Advanced features

## Support Resources

- **Cloudflare Pages Docs**: https://developers.cloudflare.com/pages
- **Vite Docs**: https://vitejs.dev
- **Wrangler CLI**: https://developers.cloudflare.com/workers/wrangler
- **Code Atlas Docs**: `/frontend/README.md`

## Changelog

- **2024-01-01**: Initial Cloudflare Pages configuration
- **2024-01-15**: Added environment variable validation
- **2024-02-01**: Added API proxy recommendations
- **2026-02-08**: Comprehensive deployment guide created

---

**Last Validated**: 2026-02-08
**Status**: ⚠️ **Requires API URL Configuration**
**Action Required**: Add `VITE_API_URL` and `VITE_WS_URL` to production environment
**Deployment Confidence**: Medium (after env vars configured: High)
