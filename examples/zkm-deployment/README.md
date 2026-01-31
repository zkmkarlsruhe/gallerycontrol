# ZKM Deployment

Production deployment configuration for ZKM | Center for Art and Media Karlsruhe.

## Migration from mutech-control

When upgrading from the old `mutech-control` deployment:

### 1. Backup the database
```bash
docker exec mutech-postgres pg_dump -U mutech mutech > backup.sql
```

### 2. Stop old containers
```bash
docker compose -f docker-compose.prod.yml down
```

### 3. Rename database (optional but recommended)
```bash
# Connect to postgres
docker exec -it mutech-postgres psql -U mutech

# Rename database and user
ALTER DATABASE mutech RENAME TO gallerycontrol;
ALTER USER mutech RENAME TO gallerycontrol;
\q
```

### 4. Update volume
```bash
docker volume create gallerycontrol_postgres_data
# Copy data from old volume or restore from backup
```

### 5. Deploy new version
```bash
docker compose -f docker-compose.prod.yml up -d
```

## Environment Variables

Create a `.env` file:

```bash
DB_PASSWORD=your-secure-password
ANEL_API_KEY=your-anel-api-key
EMAIL_RECIPIENT=admin@yourmuseum.org
LOG_LEVEL=INFO
```

## Traefik Integration

This deployment assumes Traefik is running on the `traefik` network with:
- `whitelist-and-guardian@file` middleware for main UI
- `zkm-intern-whitelist@file` middleware for API endpoints
