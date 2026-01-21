# SSO Integration Plan (OIDC + SAML)

## Summary

Add OIDC and SAML authentication providers alongside existing LDAP using **Authlib** (for OIDC) and **python3-saml** (for SAML). Users can choose their login method. All providers create the same JWT session token.

**Libraries:**
- `authlib>=1.3.0` - Industry-standard OAuth/OIDC library with Starlette/FastAPI support
- `python3-saml>=1.16.0` - De facto standard Python SAML toolkit

**Key Decisions:**
- Pre-registration required (users must exist in `allowed_users` table, or be auto-created if enabled)
- OIDC implemented using Authlib's OAuth client with OIDC discovery
- SAML implemented using python3-saml's `OneLogin_Saml2_Auth` class

## Architecture

```
Login Page
    ├── LDAP (existing) → Direct bind → JWT token
    ├── OIDC (Authlib)  → Redirect flow → JWT token
    └── SAML (python3-saml) → POST binding → JWT token
                              ↓
                      UserContext (same for all)
```

## Library Integration Patterns

### Authlib OIDC Pattern

```python
from authlib.integrations.starlette_client import OAuth
from starlette.middleware.sessions import SessionMiddleware

# Setup
app.add_middleware(SessionMiddleware, secret_key=config.session.secret_key)

oauth = OAuth()
oauth.register(
    'oidc',
    client_id=config.oidc.client_id,
    client_secret=config.oidc.client_secret,
    server_metadata_url=config.oidc.discovery_url,  # Auto-fetches OIDC config
    client_kwargs={'scope': 'openid profile email'}
)

# Login endpoint
@router.get("/login/oidc")
async def oidc_login(request: Request):
    redirect_uri = request.url_for('oidc_callback')
    return await oauth.oidc.authorize_redirect(request, redirect_uri)

# Callback endpoint
@router.get("/auth/oidc/callback")
async def oidc_callback(request: Request):
    token = await oauth.oidc.authorize_access_token(request)
    userinfo = token['userinfo']  # Contains sub, email, name, etc.
    # Create/link user and issue JWT session
```

### python3-saml Pattern

```python
from onelogin.saml2.auth import OneLogin_Saml2_Auth

def prepare_saml_request(request: Request) -> dict:
    """Convert FastAPI request to python3-saml format."""
    return {
        'https': 'on' if request.url.scheme == 'https' else 'off',
        'http_host': request.url.netloc,
        'script_name': request.url.path,
        'get_data': dict(request.query_params),
        'post_data': {},  # Populated for POST requests
    }

# Login endpoint
@router.get("/login/saml")
async def saml_login(request: Request):
    req = prepare_saml_request(request)
    auth = OneLogin_Saml2_Auth(req, saml_settings)
    return RedirectResponse(auth.login())

# ACS endpoint (Assertion Consumer Service)
@router.post("/auth/saml/acs")
async def saml_acs(request: Request):
    form_data = await request.form()
    req = prepare_saml_request(request)
    req['post_data'] = dict(form_data)

    auth = OneLogin_Saml2_Auth(req, saml_settings)
    auth.process_response()

    if auth.is_authenticated():
        attributes = auth.get_attributes()
        name_id = auth.get_nameid()
        # Create/link user and issue JWT session
```

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `auth/providers/base.py` | `AuthenticatedUser` dataclass for provider-agnostic user |
| `auth/providers/__init__.py` | Provider registry |
| `auth/providers/oidc.py` | Authlib OIDC wrapper |
| `auth/providers/saml.py` | python3-saml wrapper |
| `auth/providers/ldap_provider.py` | Wrap existing LDAP in provider interface |
| `auth/saml_settings.py` | SAML configuration loader |
| `migrations/011_sso_provider_links.py` | User-provider link table |
| `scripts/test_oidc.py` | OIDC flow test script |

### Modified Files
| File | Changes |
|------|---------|
| `api/auth.py` | Add OIDC/SAML login + callback endpoints |
| `database/models.py` | Add `UserProviderLink` model |
| `config/default.yaml` | Add OIDC/SAML config sections |
| `pyproject.toml` | Add authlib, python3-saml dependencies |
| `main.py` | Add SessionMiddleware, initialize OAuth |
| `templates/login.html` | Add SSO provider buttons |

## Implementation Details

### 1. Provider Base Interface

```python
# auth/providers/base.py
from dataclasses import dataclass

@dataclass
class AuthenticatedUser:
    """Provider-agnostic authenticated user."""
    username: str
    email: str | None = None
    display_name: str | None = None
    provider: str = "unknown"  # 'ldap', 'oidc', 'saml'
    external_id: str | None = None  # sub claim or NameID
```

### 2. OIDC Provider (Authlib Wrapper)

```python
# auth/providers/oidc.py
from authlib.integrations.starlette_client import OAuth

class OIDCProvider:
    def __init__(self, oauth: OAuth, config: dict):
        self.oauth = oauth
        self.config = config
        self._register()

    def _register(self):
        """Register OIDC client with Authlib."""
        self.oauth.register(
            'oidc',
            client_id=self.config['client_id'],
            client_secret=self.config['client_secret'],
            server_metadata_url=self.config['discovery_url'],
            client_kwargs={'scope': ' '.join(self.config.get('scopes', ['openid', 'profile', 'email']))}
        )

    @property
    def enabled(self) -> bool:
        return self.config.get('enabled', False) and bool(self.config.get('client_id'))

    async def authorize_redirect(self, request, redirect_uri: str):
        return await self.oauth.oidc.authorize_redirect(request, redirect_uri)

    async def authorize_callback(self, request) -> AuthenticatedUser | None:
        token = await self.oauth.oidc.authorize_access_token(request)
        userinfo = token.get('userinfo', {})

        return AuthenticatedUser(
            username=userinfo.get('preferred_username') or userinfo.get('email') or userinfo.get('sub'),
            email=userinfo.get('email'),
            display_name=userinfo.get('name'),
            provider='oidc',
            external_id=userinfo.get('sub'),
        )
```

### 3. SAML Provider (python3-saml Wrapper)

```python
# auth/providers/saml.py
from onelogin.saml2.auth import OneLogin_Saml2_Auth

class SAMLProvider:
    def __init__(self, config: dict):
        self.config = config
        self._settings = self._load_settings()

    def _load_settings(self) -> dict:
        """Build python3-saml settings dict from config."""
        return {
            'strict': True,
            'debug': False,
            'sp': {
                'entityId': self.config['sp_entity_id'],
                'assertionConsumerService': {
                    'url': self.config['acs_url'],
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST'
                },
                'NameIDFormat': 'urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress',
            },
            'idp': {
                'entityId': self.config['idp_entity_id'],
                'singleSignOnService': {
                    'url': self.config['idp_sso_url'],
                    'binding': 'urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect'
                },
                'x509cert': self.config['idp_cert'],
            },
        }

    @property
    def enabled(self) -> bool:
        return self.config.get('enabled', False) and bool(self.config.get('idp_sso_url'))

    def get_login_url(self, request_data: dict) -> str:
        auth = OneLogin_Saml2_Auth(request_data, self._settings)
        return auth.login()

    def process_response(self, request_data: dict) -> AuthenticatedUser | None:
        auth = OneLogin_Saml2_Auth(request_data, self._settings)
        auth.process_response()

        if not auth.is_authenticated():
            return None

        attributes = auth.get_attributes()
        name_id = auth.get_nameid()

        return AuthenticatedUser(
            username=attributes.get('uid', [name_id])[0],
            email=attributes.get('email', [None])[0],
            display_name=attributes.get('displayName', [None])[0],
            provider='saml',
            external_id=name_id,
        )

    def get_metadata(self) -> str:
        """Generate SP metadata XML."""
        from onelogin.saml2.settings import OneLogin_Saml2_Settings
        settings = OneLogin_Saml2_Settings(self._settings, sp_validation_only=True)
        return settings.get_sp_metadata()
```

### 4. Auth Endpoints

```python
# api/auth.py additions

# --- OIDC Endpoints ---

@router.get("/login/oidc")
async def oidc_login(request: Request):
    """Redirect to OIDC provider for authentication."""
    if not oidc_provider.enabled:
        raise HTTPException(400, "OIDC not configured")
    redirect_uri = str(request.url_for('oidc_callback'))
    return await oidc_provider.authorize_redirect(request, redirect_uri)

@router.get("/auth/oidc/callback", name="oidc_callback")
async def oidc_callback(request: Request, session=Depends(get_session)):
    """Handle OIDC callback, create session."""
    auth_user = await oidc_provider.authorize_callback(request)
    if not auth_user:
        return RedirectResponse("/login?error=OIDC+authentication+failed")

    # Find or create user, issue JWT
    return await _complete_sso_login(request, session, auth_user)

# --- SAML Endpoints ---

@router.get("/login/saml")
async def saml_login(request: Request):
    """Redirect to SAML IdP for authentication."""
    if not saml_provider.enabled:
        raise HTTPException(400, "SAML not configured")
    req = _prepare_saml_request(request)
    return RedirectResponse(saml_provider.get_login_url(req))

@router.post("/auth/saml/acs", name="saml_acs")
async def saml_acs(request: Request, session=Depends(get_session)):
    """SAML Assertion Consumer Service endpoint."""
    form_data = await request.form()
    req = _prepare_saml_request(request, dict(form_data))

    auth_user = saml_provider.process_response(req)
    if not auth_user:
        return RedirectResponse("/login?error=SAML+authentication+failed")

    return await _complete_sso_login(request, session, auth_user)

@router.get("/auth/saml/metadata")
async def saml_metadata():
    """Return SP metadata for IdP configuration."""
    return Response(saml_provider.get_metadata(), media_type="application/xml")

# --- Shared SSO Login Completion ---

async def _complete_sso_login(request: Request, session, auth_user: AuthenticatedUser):
    """Complete SSO login: find/create user, link provider, issue JWT."""
    source_ip = _get_client_ip(request)

    # Try to find user by provider link first
    user = await _find_user_by_provider_link(session, auth_user.provider, auth_user.external_id)

    # Fall back to email matching if configured
    if not user and auth_user.email:
        user = await _find_user_by_email(session, auth_user.email)
        if user:
            # Auto-link this provider to the user
            await _create_provider_link(session, user.id, auth_user)

    # Auto-create user if configured and not found
    if not user and config.get(f'auth.providers.{auth_user.provider}.auto_create_users'):
        user = await _create_allowed_user(session, auth_user)
        await _create_provider_link(session, user.id, auth_user)

    if not user or not user.enabled:
        return RedirectResponse("/login?error=User+not+authorized")

    # Create JWT session token
    token = create_session_token(
        username=user.username,
        role=user.role,
        display_name=auth_user.display_name or user.display_name,
    )

    # Log and redirect
    await log_action(session, action="auth.login.success", user_id=user.username,
                     user_source=auth_user.provider, source_ip=source_ip)
    await session.commit()

    redirect = RedirectResponse("/", status_code=303)
    redirect.set_cookie(key=session_manager.cookie_name, value=token, ...)
    return redirect
```

### 5. Configuration

```yaml
# config/default.yaml
auth:
  enabled: false

  providers:
    ldap:
      enabled: true
      display_name: "LDAP Login"
      server: "${LDAP_SERVER}"
      base_dn: "${LDAP_BASE_DN}"
      user_dn_template: "${LDAP_USER_DN_TEMPLATE}"

    oidc:
      enabled: false
      display_name: "SSO Login"
      client_id: "${OIDC_CLIENT_ID}"
      client_secret: "${OIDC_CLIENT_SECRET}"
      discovery_url: "${OIDC_DISCOVERY_URL}"  # .well-known/openid-configuration
      scopes: ["openid", "profile", "email"]
      auto_create_users: false

    saml:
      enabled: false
      display_name: "Enterprise SSO"
      sp_entity_id: "${SAML_SP_ENTITY_ID}"
      acs_url: "${SAML_ACS_URL}"
      idp_entity_id: "${SAML_IDP_ENTITY_ID}"
      idp_sso_url: "${SAML_IDP_SSO_URL}"
      idp_cert: "${SAML_IDP_CERT}"
      auto_create_users: false

  session:
    secret_key: "${SESSION_SECRET_KEY}"
    expiry_days: 30
    cookie_name: "mutech_session"
```

### 6. Database Migration

```python
# migrations/011_sso_provider_links.py
def upgrade():
    op.create_table(
        'user_provider_links',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('allowed_users.id', ondelete='CASCADE')),
        sa.Column('provider', sa.String(20)),  # 'oidc', 'saml'
        sa.Column('external_id', sa.String(255)),  # sub claim or NameID
        sa.Column('external_email', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_login_at', sa.DateTime()),
    )
    op.create_unique_constraint('uq_provider_external_id', 'user_provider_links', ['provider', 'external_id'])
```

### 7. Dependencies

```toml
# pyproject.toml additions
authlib = "^1.3.0"
python3-saml = "^1.16.0"
```

**Note:** python3-saml requires `xmlsec` system library. Add to Dockerfile:
```dockerfile
RUN apt-get update && apt-get install -y pkg-config libxml2-dev libxmlsec1-dev libxmlsec1-openssl
```

## Implementation Phases

### Phase 1: Foundation
1. Add dependencies to pyproject.toml
2. Create provider base interface
3. Add SessionMiddleware to main.py
4. Create database migration

### Phase 2: OIDC
1. Implement OIDCProvider wrapper
2. Add OIDC endpoints to auth.py
3. Update login template with OIDC button
4. Create test script

### Phase 3: SAML
1. Implement SAMLProvider wrapper
2. Add SAML endpoints (login, acs, metadata)
3. Update login template with SAML button
4. Test with Keycloak or similar IdP

### Phase 4: User Linking
1. Add UserProviderLink model
2. Implement find/create/link logic
3. Add admin UI for manual linking (optional)

## Verification

### OIDC Test
```bash
# Set up test IdP (Keycloak, Auth0, or Google)
export OIDC_DISCOVERY_URL="https://accounts.google.com/.well-known/openid-configuration"
export OIDC_CLIENT_ID="your-client-id"
export OIDC_CLIENT_SECRET="your-client-secret"

# Run test script
python scripts/test_oidc.py
```

### SAML Test
```bash
# Configure with Keycloak SAML client
# Access SP metadata at /auth/saml/metadata
# Import into IdP and test login flow
```

## Security Checklist

- [ ] OIDC: State parameter validated (handled by Authlib)
- [ ] OIDC: ID token signature verified (handled by Authlib)
- [ ] SAML: XML signature validated (handled by python3-saml with `strict: true`)
- [ ] SAML: Assertion timestamps checked (handled by python3-saml)
- [ ] Both: Redirect URIs restricted to configured values
- [ ] Both: All SSO events logged to audit trail
- [ ] Both: Session cookies httponly, secure, samesite=lax
