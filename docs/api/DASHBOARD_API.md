# CyberScout AI — Web Dashboard REST API Reference

**Version:** v1.1.0  
**Base URL:** `http://127.0.0.1:5000/api`

---

## GET Endpoints

### 1. GET `/api/health`
Returns system health check diagnostic JSON.
```json
{
  "overall_status": "HEALTHY",
  "healthy": true,
  "checks": [...]
}
```

### 2. GET `/api/stats`
Returns KPI overview summary.
```json
{
  "total_opportunities": 284,
  "active_collectors": 18,
  "database_size_mb": 0.35,
  "p0_count": 14,
  "p1_count": 48,
  "p2_count": 82,
  "p3_count": 60
}
```

### 3. GET `/api/opportunities`
Query opportunities with optional `category` and `q` search parameters.

### 4. GET `/api/analytics`
Returns growth and keyword frequency analytical trends.

### 5. GET `/api/providers`
Returns provider yield comparison stats.

### 6. GET `/api/collectors`
Returns list of registered collector definitions and status.

### 7. GET `/api/system`
Returns environment version metadata.

### 8. GET `/api/logs`
Returns tail of application logs.

### 9. GET `/api/config`
Returns dictionary of application configuration parameters.

---

## POST Endpoints

### 10. POST `/api/run`
Triggers single scan loop execution. Payload: `{"dry_run": true}`.

### 11. POST `/api/email/test`
Dispatches a test HTML email digest report.

### 12. POST `/api/config/save`
Saves YAML configuration updates.

### 13. POST `/api/scheduler/pause`
Pauses background daemon scheduler service.

### 14. POST `/api/scheduler/resume`
Resumes background daemon scheduler service.

### 15. POST `/api/scheduler/restart`
Restarts background daemon scheduler service.
