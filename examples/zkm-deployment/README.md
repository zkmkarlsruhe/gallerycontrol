# ZKM Deployment

Production deployment configuration for ZKM | Center for Art and Media Karlsruhe.

## Setup

1. Create `.env` file:
```bash
DB_PASSWORD=your-secure-password
ANEL_API_KEY=your-anel-api-key
EMAIL_RECIPIENT=admin@yourmuseum.org
LOG_LEVEL=INFO
```

2. Deploy:
```bash
docker compose -f docker-compose.prod.yml up -d
```

## Traefik Integration

This deployment assumes Traefik is running on the `traefik` network with:
- `whitelist-and-guardian@file` middleware for main UI
- `zkm-intern-whitelist@file` middleware for external API endpoints (`/api/sensor`, `/api/fast`)
