# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in GalleryControl, please report it responsibly.

### How to Report

1. **Do not** open a public GitHub issue for security vulnerabilities.
2. Email security issues to **security@zkm.de**, or use GitHub's private vulnerability reporting.
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Any suggested fixes (optional)

### What to Expect

- Acknowledgment of your report within 48 hours
- Regular updates on the progress of addressing the issue
- Credit in the security advisory (if desired)

## Security Considerations

### Authentication & Credentials

- Device credentials are stored server-side and referenced by name; never commit them.
- Place GalleryControl behind an authenticating reverse proxy (nginx, Caddy, Traefik) — it has no built-in user auth.

### Network Security

- Restrict access to the admin UI and API to trusted networks.
- The `/api/sensor` and `/api/fast` endpoints are intended for trusted automation only — protect them with an IP allow-list.
- Devices (projectors, PDUs, shell hosts) are controlled over the LAN; isolate that network from untrusted hosts.

### Environment Variables

Never commit sensitive values. Use environment variables / `.env` (gitignored) for:
- `DB_PASSWORD`
- `DATABASE_URL` (if it contains credentials)
- `ANEL_API_KEY`

## Security Updates

Security patches are released as soon as possible after a vulnerability is confirmed. We recommend always running the latest version.
