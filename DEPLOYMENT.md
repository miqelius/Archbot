# Production Deployment Guide

## Table of Contents
1. [Local Development Setup](#local-development-setup)
2. [Production Deployment](#production-deployment)
3. [Monitoring & Scaling](#monitoring--scaling)
4. [Troubleshooting](#troubleshooting)

---

## Local Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### Quick Start (5 minutes)

```bash
# 1. Clone repository
git clone <repo-url>
cd translation-system

# 2. Create .env file
cp .env.example .env

# Edit .env with your API keys:
# TELEGRAM_TOKEN=your_bot_token_here
# ANTHROPIC_API_KEY=your_api_key_here

# 3. Start all services
docker-compose -f docker/docker-compose.dev.yml up

# 4. Verify services
curl http://localhost:8000/health
curl http://localhost:5555  # Flower (Celery monitor)
curl http://localhost:5050  # pgAdmin
```

### Manual Setup (without Docker)

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start PostgreSQL
# Ensure PostgreSQL is running on localhost:5432

# 4. Start Redis
# Ensure Redis is running on localhost:6379

# 5. Create database
python -c "
import asyncio
from core.database import DatabaseManager
asyncio.run(DatabaseManager.initialize())
asyncio.run(DatabaseManager.create_all_tables())
"

# 6. Start FastAPI server
uvicorn api.main:app --reload --port 8000

# 7. In another terminal, start Celery worker
celery -A workers.celery_app worker --loglevel=debug

# 8. (Optional) Monitor with Flower
celery -A workers.celery_app flower
```

### Project URLs (Local Dev)
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Flower Monitor**: http://localhost:5555
- **pgAdmin**: http://localhost:5050

---

## Production Deployment

### Architecture Overview

```
┌─────────────────────────────────────────────────┐
│          Telegram Bot (Aiogram)                 │
│          Running in Telegram cloud              │
└────────────────────┬────────────────────────────┘
                     │
        Webhook HTTPS │ (or polling)
                     │
┌────────────────────▼────────────────────────────┐
│     FastAPI (2-3 replicas)                      │
│     Load Balanced (nginx/Traefik)               │
│     Port 8000                                   │
└────────────────────┬────────────────────────────┘
                     │
        Async RPC    │
                     │
    ┌────────────────▼──────────────┐
    │                               │
┌───▼────────────────┐  ┌──────────▼─────────────┐
│  PostgreSQL        │  │  Redis Cluster        │
│  (2+ replicas)     │  │  (3+ nodes)           │
│  Streaming Rep.    │  │  Sentinel for HA      │
└────────────────────┘  └───────────┬───────────┘
                                    │
                    ┌───────────────▼─────────────┐
                    │   Celery Worker Fleet       │
                    │   (auto-scaled 2-10)        │
                    │   HPA based on queue depth  │
                    └─────────────────────────────┘
```

### Deployment Options

#### Option 1: Render (Recommended for MVP)

**Render Deployment Steps:**

1. **Create Postgres Database**
   - Render → PostgreSQL → Create New
   - Keep it in same region as app
   - Configure backups (daily)

2. **Create Redis Cache**
   - Render → Redis → Create New
   - Same region as app
   - Enable TLS/authentication

3. **Deploy FastAPI Service**
   ```
   Service Type: Web Service
   Runtime: Python
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn api.main:app --host 0.0.0.0 --port 8000
   
   Environment Variables:
   - Copy from .env.production
   - DB_HOST, DB_PORT, DB_USER, DB_PASSWORD from database
   - REDIS_HOST, REDIS_PORT, REDIS_PASSWORD from cache
   - TELEGRAM_TOKEN, ANTHROPIC_API_KEY from secrets
   ```

4. **Deploy Celery Worker**
   ```
   Service Type: Background Worker
   Runtime: Python
   Build Command: pip install -r requirements.txt
   Start Command: celery -A workers.celery_app worker --loglevel=info
   
   Same environment variables as FastAPI
   ```

5. **Setup Telegram Webhook**
   ```bash
   # After FastAPI service is running
   curl -X POST https://api.telegram.org/bot<TOKEN>/setWebhook \
     -d url=https://your-app.onrender.com/bot/webhook \
     -d allowed_updates=message,callback_query
   ```

#### Option 2: Kubernetes (Production Scale)

**Helm Values Example:**

```yaml
# values.yaml
replicaCount: 3

image:
  repository: your-registry/translation-system
  tag: "1.0.0"

service:
  type: LoadBalancer
  port: 80

ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  hosts:
    - host: api.yourdomain.com
      paths:
        - path: /
          pathType: Prefix

postgresql:
  enabled: true
  auth:
    username: translation_user
    password: secure_password
  primary:
    persistence:
      size: 100Gi

redis:
  enabled: true
  auth:
    enabled: true
  master:
    persistence:
      size: 50Gi
  replica:
    replicaCount: 2

celeryWorker:
  enabled: true
  replicaCount: 3
  autoscaling:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    targetCPUUtilizationPercentage: 70
```

**Deploy:**
```bash
helm repo add translation https://charts.yourdomain.com
helm install translation-system translation/translation-system \
  -f values.yaml \
  --namespace production
```

#### Option 3: AWS (ECS/Fargate + RDS)

**Infrastructure as Code (Terraform):**

```hcl
# main.tf
resource "aws_ecs_cluster" "translation" {
  name = "translation-cluster"
}

resource "aws_rds_cluster" "postgres" {
  cluster_identifier      = "translation-postgres"
  engine                  = "aurora-postgresql"
  engine_version          = "15.2"
  database_name           = "translation_db"
  master_username         = "postgres"
  master_password         = random_password.db_password.result
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  skip_final_snapshot    = false
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "translation-redis"
  engine               = "redis"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 3
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  automatic_failover_enabled = true
}

resource "aws_ecs_task_definition" "fastapi" {
  family                   = "translation-api"
  container_definitions    = jsonencode([
    {
      name      = "translation-api"
      image     = "your-account.dkr.ecr.us-east-1.amazonaws.com/translation:latest"
      portMappings = [{ containerPort = 8000 }]
      environment = [
        { name = "DB_HOST", value = aws_rds_cluster.postgres.endpoint }
        # ... other env vars
      ]
    }
  ])
}
```

---

## Monitoring & Scaling

### Metrics to Monitor

**Application Metrics:**
- Request latency (p50, p95, p99)
- Error rate (4xx, 5xx)
- Translation pipeline duration (Translator, Stylist, QA separately)
- Queue depth (Celery tasks)

**Database Metrics:**
- Connection pool utilization
- Query latency
- Replication lag (if replicated)
- Storage usage

**Redis Metrics:**
- Memory usage
- Eviction rate
- Key hit/miss ratio

### Auto-scaling Configuration

**Kubernetes HPA:**
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: translation-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: translation-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Celery Worker Scaling:**
```python
# Adjust based on queue length
from celery.signals import before_task_publish

@before_task_publish.connect
def check_queue_depth(sender=None, **kwargs):
    queue_length = get_queue_depth()
    if queue_length > 1000:
        # Trigger scale-up event
        scale_workers(target=10)
    elif queue_length < 100:
        # Trigger scale-down
        scale_workers(target=3)
```

### Logging & Observability

**Structured Logging Example:**
```python
import structlog

logger = structlog.get_logger()

logger.info(
    "translation_completed",
    job_id=job_id,
    duration_seconds=duration,
    quality_score=score,
    tokens_used=total_tokens,
    cost_usd=cost,
    user_id=user_id,
)
```

**Export to Cloud:**
- **AWS CloudWatch**: `pip install watchtower`
- **Google Cloud Logging**: `pip install google-cloud-logging`
- **Datadog**: `pip install datadog`
- **ELK Stack**: Use logstash sidecar

---

## Troubleshooting

### Common Issues

**1. Database Connection Refused**
```bash
# Check if PostgreSQL is running
psql -h localhost -U postgres -c "SELECT 1"

# Check connection pool settings
# Reduce pool_size if memory constrained
DB_POOL_SIZE=10  # Not 20
DB_MAX_OVERFLOW=5
```

**2. Celery Tasks Not Processing**
```bash
# Check Redis connection
redis-cli ping

# Check Celery worker logs
celery -A workers.celery_app worker --loglevel=debug

# Purge queue if stuck
celery -A workers.celery_app purge

# Monitor tasks
celery -A workers.celery_app events
```

**3. High Memory Usage**
```python
# Disable SQLAlchemy object expiration
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,  # Key!
)

# Limit connection pool
pool_size=10,
max_overflow=5,
pool_pre_ping=True,
```

**4. Timeout on Large Documents**
```python
# Increase timeouts
task_soft_time_limit=600,  # 10 minutes
task_time_limit=900,  # 15 minutes

# Or split processing
# 1. Extract text (short timeout)
# 2. Translate chunks separately
# 3. Combine results
```

### Performance Tuning

**Database Query Optimization:**
```python
# Use eager loading for relationships
stmt = select(TranslationJobDB).options(
    selectinload(TranslationJobDB.audit_logs),
    selectinload(TranslationJobDB.pipeline_metrics)
)

# Use indexes
Index("idx_user_status", TranslationJobDB.telegram_user_id, TranslationJobDB.status)
```

**Caching Strategy:**
```python
@cache.cached(timeout=300, key_prefix="job_")
async def get_job_cached(job_id: str):
    # Results cached for 5 minutes
    return await get_job_from_db(job_id)
```

---

## Security Checklist

- [ ] HTTPS/TLS enabled for all endpoints
- [ ] API keys stored in environment variables (not in code)
- [ ] Database password complex (32+ chars)
- [ ] Redis password enabled and strong
- [ ] Input validation on all endpoints
- [ ] Rate limiting enabled (per-user, per-IP)
- [ ] CORS restricted to known origins
- [ ] Database backups automated and tested
- [ ] Logs don't contain sensitive data
- [ ] Regular security audits scheduled
- [ ] Dependencies updated regularly (`pip audit`)

---

## Cost Optimization

**Development:**
- Use Render free tier (limited)
- Local PostgreSQL for testing
- Shared Redis instance

**Production:**
- Reserve instances for steady-state load
- On-demand instances for spikes
- Spot instances for Celery workers
- Storage tiering (hot/cold)

**Estimated Monthly Costs (AWS):**
- RDS PostgreSQL (3 instances): $500-1000
- ElastiCache Redis: $200-400
- ECS Fargate (3 tasks): $300-600
- Data transfer: $100-200
- **Total**: $1,100-2,200/month for ~1M translations/month

---

## Next Steps

1. **Set up CI/CD**: GitHub Actions → Docker build → Registry → Deploy
2. **Configure alerts**: Page on incidents (error rate > 5%, latency p95 > 2s)
3. **Load testing**: k6 or locust for 1000+ concurrent users
4. **Disaster recovery**: Test restore from backups
5. **Cost monitoring**: Set up billing alerts
