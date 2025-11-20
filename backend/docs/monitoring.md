# Code Atlas Monitoring and Metrics

This guide covers monitoring and metrics collection for Code Atlas, including Prometheus integration, health checks, and operational observability.

## Overview

Code Atlas provides comprehensive monitoring capabilities out of the box:

- **Prometheus Metrics**: Production-ready metrics collection with standard instrumentation
- **Health Checks**: HTTP endpoints for service health monitoring
- **System Monitoring**: CPU, memory, and disk usage tracking
- **Pipeline Metrics**: Session processing, extraction performance, and cost tracking
- **Error Monitoring**: Error rates, types, and failure patterns

## Configuration

### Basic Configuration

Add monitoring settings to your `.code-atlas.toml`:

```toml
[monitoring]
enable_metrics = true
metrics_host = "0.0.0.0"
metrics_port = 8000
metrics_path = "/metrics"
health_path = "/health"
status_path = "/status"
metrics_collection_interval = 30
prometheus_namespace = "code_atlas"
```

### Environment Variables

All monitoring settings can be overridden with environment variables:

```bash
export CODE_ATLAS_ENABLE_METRICS=true
export CODE_ATLAS_METRICS_HOST=0.0.0.0
export CODE_ATLAS_METRICS_PORT=8000
export CODE_ATLAS_PROMETHEUS_NAMESPACE=code_atlas
```

## Quick Start

### 1. Enable Metrics

```bash
# Using config file
code-atlas run --config .code-atlas.toml

# Using environment variables
CODE_ATLAS_ENABLE_METRICS=true code-atlas run
```

### 2. Start Dedicated Metrics Server

```bash
# Start metrics server in foreground
code-atlas metrics --config .code-atlas.toml

# Start in daemon mode (background)
code-atlas metrics --daemon --config .code-atlas.toml

# Override host/port
code-atlas metrics --host 127.0.0.1 --port 9090
```

### 3. Verify Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Metrics (Prometheus format)
curl http://localhost:8000/metrics

# Detailed status
curl http://localhost:8000/status | jq .
```

## Prometheus Integration

### Prometheus Configuration

Add to your `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'code-atlas'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
    scrape_timeout: 10s
```

### Available Metrics

#### Pipeline Metrics

```
# Total sessions processed
code_atlas_pipeline_sessions_total{project="myproject", status="success|failed"}

# Pipeline processing time
code_atlas_pipeline_processing_seconds{project="myproject"}

# Messages and tokens processed
code_atlas_pipeline_messages_total
code_atlas_pipeline_tokens_total

# Active sessions and queue size
code_atlas_sessions_active
code_atlas_sessions_queue_size
```

#### Database Metrics

```
# Nodes and relationships created
code_atlas_db_nodes_created_total{node_type="Session|File|Concept|Insight"}
code_atlas_db_relationships_created_total{relationship_type="RELATED_TO|MENTIONS"}

# Query performance
code_atlas_db_query_seconds{operation="execute"}

# Active connections
code_atlas_db_connections_active
```

#### Extraction Metrics

```
# Extraction requests and performance
code_atlas_extraction_requests_total{method="llm|heuristic", model="claude-3-sonnet"}
code_atlas_extraction_seconds{method="llm|heuristic"}

# Entities and relationships extracted
code_atlas_extraction_entities_created_total{entity_type="file|concept|tool"}
code_atlas_extraction_relationships_created_total{relationship_type="related_to"}
```

#### Cost Metrics

```
# Total cost by model and operation
code_atlas_cost_total_usd{model="claude-3-sonnet", operation="extraction|api_call"}

# Cost per session distribution
code_atlas_cost_per_session_usd
```

#### Error Metrics

```
# Error counts by component and type
code_atlas_errors_total{component="pipeline|database|extraction", error_type="ValueError"}

# Error rates
code_atlas_error_rate{component="pipeline"}
```

#### System Metrics

```
# System resources
code_atlas_system_memory_bytes{type="available|used|total"}
code_atlas_system_cpu_percent
code_atlas_system_disk_bytes{type="used|free|total", mount_point="/"}

# Process information
code_atlas_process_uptime_seconds
```

## Grafana Dashboards

### Example Grafana Dashboard JSON

```json
{
  "dashboard": {
    "title": "Code Atlas Overview",
    "panels": [
      {
        "title": "Pipeline Throughput",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(code_atlas_pipeline_sessions_total[5m])",
            "legendFormat": "Sessions/sec"
          }
        ]
      },
      {
        "title": "Processing Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(code_atlas_pipeline_processing_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(code_atlas_pipeline_processing_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(code_atlas_errors_total[5m])",
            "legendFormat": "{{component}}: {{error_type}}"
          }
        ]
      },
      {
        "title": "Cost Tracking",
        "type": "graph",
        "targets": [
          {
            "expr": "increase(code_atlas_cost_total_usd[1h])",
            "legendFormat": "Cost per hour"
          }
        ]
      }
    ]
  }
}
```

### Recommended Panels

1. **Pipeline Overview**
   - Sessions processed per minute
   - Average processing time
   - Success/failure ratio
   - Queue size

2. **Performance Metrics**
   - Extraction time percentiles
   - Database query performance
   - Token usage rates

3. **Resource Usage**
   - CPU and memory utilization
   - Disk space usage
   - Database connection count

4. **Cost Monitoring**
   - Hourly/daily cost trends
   - Cost per session
   - Model-specific costs

5. **Error Analysis**
   - Error rate by component
   - Top error types
   - Error correlation with load

## Alerting

### Prometheus Alert Rules

```yaml
groups:
  - name: code-atlas
    rules:
      # Pipeline health alerts
      - alert: CodeAtlasHighErrorRate
        expr: rate(code_atlas_errors_total[5m]) > 0.1
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High error rate in Code Atlas"
          description: "Error rate is {{ $value }} errors per second"

      - alert: CodeAtlasPipelineStalled
        expr: increase(code_atlas_pipeline_sessions_total[10m]) == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Code Atlas pipeline is not processing sessions"
          description: "No sessions processed in the last 10 minutes"

      # Resource alerts
      - alert: CodeAtlasHighMemoryUsage
        expr: code_atlas_system_memory_bytes{type="used"} / code_atlas_system_memory_bytes{type="total"} > 0.9
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value | humanizePercentage }}"

      - alert: CodeAtlasHighCPUUsage
        expr: code_atlas_system_cpu_percent > 80
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}%"

      # Cost alerts
      - alert: CodeAtlasHighSpendRate
        expr: increase(code_atlas_cost_total_usd[1h]) > 1.0
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "High cost spend rate"
          description: "Spending ${{ $value }} per hour"

      # Database alerts
      - alert: CodeAtlasDatabaseErrors
        expr: rate(code_atlas_errors_total{component="database"}[5m]) > 0.01
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Database errors detected"
          description: "Database error rate is {{ $value }} errors per second"
```

## Health Checks

### Health Endpoint

```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T12:00:00Z",
  "service": "code-atlas-metrics"
}
```

### Status Endpoint

```bash
curl http://localhost:8000/status
```

Response includes:
- Service version and configuration
- System resource usage
- Process information
- Metrics collection status

## Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

# Install dependencies
COPY pyproject.toml .
RUN pip install -e .

# Copy application
COPY src/ /app/src/
WORKDIR /app

# Expose metrics port
EXPOSE 8000

# Run with metrics enabled
CMD ["code-atlas", "metrics", "--daemon", "--host", "0.0.0.0"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: code-atlas-metrics
spec:
  replicas: 1
  selector:
    matchLabels:
      app: code-atlas-metrics
  template:
    metadata:
      labels:
        app: code-atlas-metrics
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
      - name: code-atlas
        image: code-atlas:latest
        ports:
        - containerPort: 8000
          name: metrics
        env:
        - name: CODE_ATLAS_ENABLE_METRICS
          value: "true"
        - name: CODE_ATLAS_METRICS_HOST
          value: "0.0.0.0"
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: code-atlas-metrics
  labels:
    app: code-atlas-metrics
spec:
  selector:
    app: code-atlas-metrics
  ports:
  - port: 8000
    targetPort: 8000
    name: metrics
```

### Monitoring Best Practices

1. **Metrics Collection**
   - Use 30-second intervals for system metrics
   - Keep metrics retention appropriate to your needs
   - Monitor the monitoring system itself

2. **Alert Thresholds**
   - Set alerts based on baseline behavior
   - Use multiple severity levels
   - Include runbooks in alert annotations

3. **Resource Planning**
   - Monitor memory usage of metrics collection
   - Plan for disk space for metrics storage
   - Consider network bandwidth for metrics scraping

4. **Security**
   - Restrict access to metrics endpoints
   - Use authentication in production environments
   - Monitor metrics endpoint for abuse

## Troubleshooting

### Common Issues

#### Metrics Not Appearing

1. **Check configuration**:
   ```bash
   code-atlas metrics --config .code-atlas.toml
   ```

2. **Verify endpoints**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:8000/metrics
   ```

3. **Check logs**:
   ```bash
   CODE_ATLAS_LOG_LEVEL=DEBUG code-atlas metrics
   ```

#### High Memory Usage

1. **Monitor metrics collection interval**:
   ```toml
   metrics_collection_interval = 60  # Increase from 30s
   ```

2. **Check for metric leaks**:
   ```bash
   curl http://localhost:8000/metrics | wc -l
   ```

#### Performance Impact

1. **Profile metrics collection**:
   ```python
   import cProfile
   cProfile.run('your_code_here()')
   ```

2. **Monitor system metrics**:
   ```bash
   curl http://localhost:8000/status | jq .system
   ```

### Debug Commands

```bash
# Test metrics collection
CODE_ATLAS_ENABLE_METRICS=true code-atlas run --limit 1

# Check server status
curl -s http://localhost:8000/status | jq .

# Validate Prometheus metrics
curl -s http://localhost:8000/metrics | promtool check metrics

# Monitor in real-time
watch -n 5 'curl -s http://localhost:8000/metrics | grep pipeline_sessions_total'
```

### Log Analysis

```bash
# Enable debug logging
CODE_ATLAS_LOG_LEVEL=DEBUG code-atlas metrics

# Monitor specific components
grep "metrics" /var/log/code-atlas.log
grep "system_metrics" /var/log/code-atlas.log
```

## Advanced Configuration

### Custom Metrics Namespace

```toml
[monitoring]
prometheus_namespace = "company_code_atlas"
```

### Custom Collection Interval

```toml
[monitoring]
metrics_collection_interval = 60  # seconds
```

### Network Configuration

```toml
[monitoring]
metrics_host = "127.0.0.1"  # Localhost only
metrics_port = 9090        # Custom port
```

## Integration Examples

### Docker Compose

```yaml
version: '3.8'
services:
  code-atlas:
    build: .
    environment:
      - CODE_ATLAS_ENABLE_METRICS=true
      - CODE_ATLAS_METRICS_HOST=0.0.0.0
      - CODE_ATLAS_REDIS_URL=redis://redis:6379
    ports:
      - "8000:8000"
    depends_on:
      - redis

  redis:
    image: falkordb/falkordb:latest
    ports:
      - "6379:6379"

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana-storage:/var/lib/grafana

volumes:
  grafana-storage:
```

### Terraform

```hcl
resource "kubernetes_deployment" "code_atlas" {
  metadata {
    name = "code-atlas"
  }

  spec {
    selector {
      match_labels = {
        app = "code-atlas"
      }
    }

    template {
      metadata {
        labels = {
          app = "code-atlas"
        }

        annotations {
          "prometheus.io/scrape" = "true"
          "prometheus.io/port"   = "8000"
          "prometheus.io/path"   = "/metrics"
        }
      }

      spec {
        container {
          name  = "code-atlas"
          image = "code-atlas:latest"

          port {
            container_port = 8000
            name          = "metrics"
          }

          env {
            name  = "CODE_ATLAS_ENABLE_METRICS"
            value = "true"
          }

          resources {
            limits = {
              memory = "1Gi"
              cpu    = "500m"
            }
            requests = {
              memory = "256Mi"
              cpu    = "100m"
            }
          }
        }
      }
    }
  }
}
```

This monitoring system provides production-ready observability for Code Atlas, enabling you to track performance, costs, errors, and system health in real-time.