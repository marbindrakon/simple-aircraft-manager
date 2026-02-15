# OpenShift Deployment Guide

This directory contains example Kubernetes/OpenShift manifests for deploying Simple Aircraft Manager in production.

## Architecture

The deployment consists of:

- **Django Application** - Gunicorn serving the Django app on port 8000
- **nginx Sidecar** - TLS termination, static/media file serving, security headers
- **PostgreSQL Database** - Crunchy Data PGO-managed PostgreSQL 16 cluster
- **Persistent Storage** - RWX volume for media uploads

## Prerequisites

### Required Operators

1. **Crunchy Postgres Operator (PGO) v5.x** - For PostgreSQL database
   ```bash
   # Install from OperatorHub in openshift-operators namespace
   ```

2. **External Secrets Operator** (Optional) - If using Vault/external secret management
   ```bash
   # Install from OperatorHub or use plain Kubernetes Secrets
   ```

### Storage Requirements

- **PostgreSQL**: 2Gi RWO storage (persistent database)
- **Backups**: 2Gi RWO storage (PostgreSQL backups)
- **Media Files**: 50Gi RWX storage (user uploads - CephFS, NFS, etc.)

## Customization Guide

### 1. Update Domain Names

Replace `your-app.apps.example.com` with your actual route hostname in:
- `02-configmap.yaml` - DJANGO_ALLOWED_HOSTS, DJANGO_CSRF_TRUSTED_ORIGINS
- `03-nginx-config.yaml` - server_name directive
- `10-route.yaml` - spec.host

### 2. Configure Secrets

The application requires these secrets (see `04-externalsecret.yaml` or create plain Secret):

```yaml
DJANGO_SECRET_KEY: "random-50-character-string"
DJANGO_SUPERUSER_USERNAME: "admin"
DJANGO_SUPERUSER_PASSWORD: "secure-password"
DJANGO_SUPERUSER_EMAIL: "admin@example.com"

# OIDC Authentication (optional)
OIDC_RP_CLIENT_ID: "your-client-id"
OIDC_RP_CLIENT_SECRET: "your-client-secret"

# AI Logbook Import (optional)
ANTHROPIC_API_KEY: "sk-ant-..."
```

**Generate a Django secret key:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

### 3. Update Container Image

In `08-deployment.yaml`, change:
```yaml
image: quay.io/your-org/simple-aircraft-manager:latest
```

### 4. Configure OIDC (Optional)

If using OpenID Connect authentication:

1. Set `OIDC_ENABLED: "true"` in `02-configmap.yaml`
2. Update `OIDC_OP_DISCOVERY_ENDPOINT` with your provider's URL
3. Add `OIDC_RP_CLIENT_ID` and `OIDC_RP_CLIENT_SECRET` to secrets
4. Update CSP `form-action` in `03-nginx-config.yaml` to include your IdP domain

If NOT using OIDC:
- Set `OIDC_ENABLED: "false"` in ConfigMap
- Remove OIDC variables from ConfigMap and Secret

### 5. Configure Logbook Import AI (Optional)

The app supports AI-powered transcription of scanned maintenance logbook pages using Anthropic (Claude) and/or local Ollama models.

**Using Anthropic models (cloud):**
1. Add `ANTHROPIC_API_KEY` to your secrets
2. Built-in models (Sonnet, Haiku, Opus) are available by default

**Using Ollama models (self-hosted):**
1. Set `OLLAMA_BASE_URL` in `02-configmap.yaml` to your Ollama instance
2. Add models via `LOGBOOK_IMPORT_EXTRA_MODELS` JSON array in ConfigMap
3. Optionally adjust `OLLAMA_TIMEOUT` (default: 1200 seconds)

If NOT using logbook import:
- No configuration needed — the feature is optional and inactive without an API key

### 6. Adjust Storage Classes

In `07-pvc.yaml`, change `storageClassName` to match your cluster:
```yaml
storageClassName: your-rwx-storage-class  # Must support ReadWriteMany
```

Common options:
- OpenShift Data Foundation: `ocs-storagecluster-cephfs`
- NFS: `nfs-client` or similar
- Other: Check `oc get storageclass`

### 7. Review Resource Limits

The sam container defaults to 512Mi request / 2Gi limit. The higher limit accommodates AI-powered logbook import which processes multiple images in memory. If not using this feature, you can lower the limit to 512Mi.

## Deployment Order

The manifests are numbered for deployment order:

```bash
# Deploy in sequence
oc apply -f 01-namespace.yaml
oc apply -f 02-configmap.yaml
oc apply -f 03-nginx-config.yaml
oc apply -f 04-externalsecret.yaml  # Or your plain Secret
oc apply -f 05-pg-init-sql.yaml
oc apply -f 06-postgrescluster.yaml
oc apply -f 07-pvc.yaml

# Wait for PostgreSQL to be ready
oc wait --for=condition=Ready postgrescluster/sam-db -n sam --timeout=300s

# Deploy application
oc apply -f 08-deployment.yaml
oc apply -f 09-service.yaml
oc apply -f 10-route.yaml

# Check status
oc get pods -n sam
oc logs -f deployment/sam -n sam -c sam
```

## ArgoCD Sync Waves (Optional)

If using ArgoCD, the sync waves ensure proper ordering:
- Wave -1: Namespace
- Wave 0: ConfigMaps, PVC
- Wave 1: ExternalSecret, PostgresCluster
- Wave 3: Deployment, Service, Route

Add this annotation to enable:
```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: '0'
```

## TLS Certificate Management

### Option 1: Service Serving Certificate (Built-in)

The example uses OpenShift's service-serving certificate:
```yaml
# In service.yaml
annotations:
  service.beta.openshift.io/serving-cert-secret-name: sam-nginx-tls
```

This auto-generates a cert in the `sam-nginx-tls` secret.

### Option 2: cert-manager

If using cert-manager, create a Certificate resource:
```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: sam-nginx-tls
  namespace: sam
spec:
  secretName: sam-nginx-tls
  issuerRef:
    name: letsencrypt-prod
    kind: ClusterIssuer
  dnsNames:
  - your-app.apps.example.com
```

### Option 3: Bring Your Own Cert

Create a TLS secret manually:
```bash
oc create secret tls sam-nginx-tls \
  --cert=tls.crt \
  --key=tls.key \
  -n sam
```

## Database Connection

The PostgreSQL cluster auto-generates connection credentials:

```yaml
# Secret created by PGO: sam-db-pguser-sam-db
host: sam-db-primary.sam.svc
port: 5432
dbname: sam-db
user: sam-db
password: <auto-generated>
```

The deployment mounts these as environment variables (see `08-deployment.yaml`).

## Health Checks

- **Endpoint**: `/healthz/` on port 8443
- **Handled by**: nginx (returns 200 without proxying to Django)
- **Purpose**: Avoids ALLOWED_HOSTS validation issues with kube-probe IPs

## Security Features

### Content Security Policy (CSP)

Strict CSP configured in nginx:
- Scripts: `'self'`, `cdn.jsdelivr.net` (Alpine.js)
- Styles: `'self'`, `unpkg.com` (PatternFly)
- Forms: `'self'`, OIDC provider (if enabled)

### Security Headers

- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- X-XSS-Protection: 1; mode=block
- Referrer-Policy: strict-origin-when-cross-origin

### Network Policies (Optional)

Consider adding NetworkPolicies to restrict:
- Ingress to port 8443 only
- Egress to PostgreSQL, OIDC provider, external APIs only

## Scaling

To scale horizontally:

1. **Enable session affinity** on the Service:
   ```yaml
   sessionAffinity: ClientIP
   ```

2. **Use external session storage** (Redis, Memcached):
   - Configure Django session backend
   - Update deployment with cache connection details

3. **Scale replicas**:
   ```bash
   oc scale deployment/sam --replicas=3 -n sam
   ```

## Backup and Restore

### PostgreSQL Backups

PGO handles automatic backups. To take a manual backup:
```bash
oc annotate postgrescluster sam-db \
  postgres-operator.crunchydata.com/pgbackrest-backup="$(date +%Y%m%d-%H%M%S)" \
  -n sam
```

### Media Files

Backup the media PVC:
```bash
# Using rsync or backup tool of choice
oc rsync sam-<pod-id>:/opt/app-root/src/mediafiles ./backup/
```

## Monitoring

Add Prometheus annotations for monitoring:
```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8000"
    prometheus.io/path: "/metrics"
```

Install `django-prometheus` and configure in settings.

## Troubleshooting

### Pod fails to start
```bash
# Check logs
oc logs deployment/sam -n sam -c sam
oc logs deployment/sam -n sam -c nginx

# Check events
oc get events -n sam --sort-by='.lastTimestamp'
```

### Database connection issues
```bash
# Check PGO cluster status
oc get postgrescluster -n sam
oc get pods -l postgres-operator.crunchydata.com/cluster=sam-db -n sam

# Test connection from pod
oc exec -it deployment/sam -n sam -c sam -- bash
psql -h sam-db-primary.sam.svc -U sam-db -d sam-db
```

### Static files not loading
```bash
# Check nginx logs
oc logs deployment/sam -n sam -c nginx

# Verify static files were collected
oc exec deployment/sam -n sam -c nginx -- ls -la /opt/app-root/src/static/
```

### OIDC authentication fails
```bash
# Check OIDC configuration
oc exec deployment/sam -n sam -c sam -- env | grep OIDC

# Test discovery endpoint
oc exec deployment/sam -n sam -c sam -- \
  curl -k https://your-idp.example.com/.well-known/openid-configuration
```

## Production Checklist

- [ ] Secrets generated and stored securely
- [ ] Domain names updated in all manifests
- [ ] Container image built and pushed to registry
- [ ] Storage classes configured for your cluster
- [ ] PostgreSQL PGO operator installed
- [ ] TLS certificates configured
- [ ] OIDC provider configured (if using)
- [ ] Logbook import AI configured (if using)
- [ ] Resource limits tuned for workload
- [ ] Backups configured and tested
- [ ] Monitoring/alerting configured
- [ ] NetworkPolicies applied (optional)

## Additional Resources

- [Crunchy PGO Documentation](https://access.crunchydata.com/documentation/postgres-operator/latest/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [OpenShift Routes](https://docs.openshift.com/container-platform/latest/networking/routes/route-configuration.html)
