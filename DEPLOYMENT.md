# ASCDC Deployment Guide

## Quick Start (Local Development)

### Backend
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Backend available at: `http://localhost:8000`

### Frontend
```bash
cd src
npm install
npm run dev
```

Frontend available at: `http://localhost:5173`

---

## Docker Deployment

### Build and Run
```bash
docker-compose up --build
```

Services:
- Backend: `http://localhost:8000`
- Frontend: `http://localhost:3000`
- Nginx: `http://localhost:80`

### Environment Variables

Create `.env` file in project root:
```
VITE_API_URL=http://localhost:8000
PYTHONPATH=/app
```

---

## Production Deployment

### Prerequisites
- Docker & Docker Compose
- 2+ vCPU, 4GB+ RAM
- Port 80, 8000 accessible

### Steps

1. **Clone repository**
   ```bash
   git clone <repo>
   cd ascdc
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

3. **Build and start**
   ```bash
   docker-compose -f docker-compose.yml up -d
   ```

4. **Verify health**
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:3000
   ```

5. **View logs**
   ```bash
   docker-compose logs -f backend
   docker-compose logs -f frontend
   ```

---

## Health Checks

### Backend
```bash
curl http://localhost:8000/health
# Response: {"status": "ok"}
```

### Frontend
```bash
curl http://localhost:3000
# Response: HTML page
```

### Full Stack
```bash
docker-compose ps
# All services should show "Up"
```

---

## Scaling

### Horizontal Scaling
For multiple backend instances, use load balancer (nginx, HAProxy):

```nginx
upstream backend {
  server backend1:8000;
  server backend2:8000;
  server backend3:8000;
}

server {
  listen 80;
  location /api {
    proxy_pass http://backend;
  }
}
```

### Vertical Scaling
Increase resources in docker-compose.yml:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

---

## Monitoring

### Logs
```bash
# Backend logs
docker-compose logs backend

# Frontend logs
docker-compose logs frontend

# All logs
docker-compose logs -f
```

### Performance
Monitor container stats:
```bash
docker stats
```

---

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker-compose logs backend

# Verify port 8000 is free
lsof -i :8000

# Rebuild
docker-compose build --no-cache backend
```

### Frontend won't connect to backend
```bash
# Check VITE_API_URL in .env
cat .env

# Verify backend is running
curl http://localhost:8000/health

# Check network
docker network ls
docker network inspect ascdc_default
```

### High memory usage
```bash
# Check container memory
docker stats

# Reduce in docker-compose.yml
memory: 2G
```

---

## Backup & Recovery

### Backup
```bash
# Export environment state
docker-compose exec backend python -c "from env.environment import ASCDCEnvironment; print('OK')"
```

### Recovery
```bash
# Restart services
docker-compose restart

# Full reset
docker-compose down
docker-compose up -d
```

---

## Security

### Recommendations
1. Use HTTPS in production (add SSL certificate to nginx)
2. Set strong environment variables
3. Restrict API access with authentication
4. Use private Docker registry
5. Regular security updates: `docker-compose pull && docker-compose up -d`

### Example nginx SSL config
```nginx
server {
  listen 443 ssl;
  ssl_certificate /etc/nginx/certs/cert.pem;
  ssl_certificate_key /etc/nginx/certs/key.pem;
  
  location / {
    proxy_pass http://frontend:3000;
  }
}
```

---

## Performance Tuning

### Backend
- Increase uvicorn workers: `--workers 4`
- Adjust timeout: `--timeout 120`

### Frontend
- Enable gzip compression in nginx
- Cache static assets
- Use CDN for assets

### Database (if added)
- Use connection pooling
- Index frequently queried fields
- Regular maintenance

---

## Maintenance

### Regular Tasks
- Monitor disk space
- Check logs for errors
- Update dependencies monthly
- Test backup/recovery quarterly

### Update Procedure
```bash
# Pull latest code
git pull

# Rebuild containers
docker-compose build --no-cache

# Restart services
docker-compose up -d

# Verify health
curl http://localhost:8000/health
```

---

## Support

For issues:
1. Check logs: `docker-compose logs`
2. Verify health: `curl http://localhost:8000/health`
3. Check environment: `cat .env`
4. Review README.md for setup instructions
