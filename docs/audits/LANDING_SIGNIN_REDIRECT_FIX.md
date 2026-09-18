# Security & Behavioral Audit: Landing Page Sign In Redirect Fix

**Date**: 2026-09-18  
**Author**: Antigravity AI Security & Core Engineering  
**Task**: Bug Fix — Landing Page Sign In Redirects to Admin Login  
**Status**: `VERIFIED`  

---

## 1. Executive Summary

When an unauthenticated visitor clicked **Sign In** on the CyberScout AI landing page (`/`), they were redirected to the **Admin Sign In** page (`/admin/login`) instead of the standard **User Sign In** page (`/login`).

This investigation determined the exact root cause, identified all canonical authentication endpoints, corrected the template navigation and route handling logic, preserved all security controls (MFA, CSRF, RLS, RBAC, session isolation), and added regression test coverage ensuring strict separation of User and Admin portals.

---

## 2. Root Cause Analysis

### The Redirect Chain
The unexpected redirect from `/` -> `/admin/login` was caused by a multi-hop sequence triggered by first-run setup middleware:

1. **Missing Route Exemptions in Middleware**:
   In `dashboard/app.py`, the global `@app.before_request` hook `check_first_run_setup()` intercepted incoming requests. It checked:
   ```python
   if not user_repo.has_users():
       return redirect(url_for('auth_ui.setup'))
   ```
   Crucially, `"auth_ui.login"`, `"auth_ui.register"`, `"auth_ui.forgot_password"`, and `"dashboard_ui.landing"` were **not** listed in the exemption set.

2. **Database State & Misdirected Setup Redirect**:
   In fresh database setups (e.g., following a reset or migration) where administrator accounts existed in `Admins` but zero regular users existed in `Users`, `user_repo.has_users()` evaluated to `False`. As a result, visiting `/login` immediately issued an HTTP 302 redirect to `/setup`.

3. **Admin Exists Guard in Setup Route**:
   In `dashboard/routes/auth.py` under `@auth_bp.route("/setup")`:
   ```python
   if admin_repo.has_admin() or user_repo.has_admin():
       return redirect(url_for('admin_ui.admin_login'))
   ```
   Because an admin already existed in the system, `/setup` redirected the user to `admin_ui.admin_login` (`/admin/login`).

4. **Hardcoded and Inconsistent Template Anchors**:
   In `dashboard/templates/landing.html`, `register.html`, `login.html`, `forgot_password.html`, and `admin/admin_login.html`, several navigation links used hardcoded strings (`href="/login"`, `href="/admin/login"`) rather than dynamic, canonical Flask `url_for(...)` endpoints. Additionally, table name casing in `src/database/user_repository.py` had unquoted `Users` table references that failed in case-sensitive PostgreSQL queries.

---

## 3. Canonical Authentication Routes

| Portal / Role | Action | Canonical Endpoint Name | URL Route | HTTP Methods | Protection / Decorator |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Standard User** | Sign In / Login | `auth_ui.login` | `/login` | `GET`, `POST` | Public / Rate-limited |
| **Standard User** | Register / Sign Up | `auth_ui.register` | `/register` | `GET`, `POST` | Public / Rate-limited |
| **Standard User** | Sign Out / Logout | `auth_ui.logout` | `/logout` | `GET` | Authenticated User |
| **Administrator** | Admin Sign In | `admin_ui.admin_login` | `/admin/login` | `GET`, `POST` | Public Admin Entrypoint / MFA |
| **Administrator** | Admin Sign Out | `admin_ui.admin_logout` | `/admin/logout` | `GET` | Authenticated Admin |
| **Administrator** | Admin Gateway Root | `admin_ui.admin_root` | `/admin` / `/admin/` | `GET` | Redirects to `/admin/login` or `/admin/dashboard` |
| **Administrator** | Admin Dashboard | `admin_ui.admin_dashboard` | `/admin/dashboard` | `GET` | `@admin_required` (Strict Admin session) |

---

## 4. Files Changed

### 1. `dashboard/app.py`
- **Exempted public and authentication endpoints from `check_first_run_setup()`**:
  Added `"dashboard_ui.landing"`, `"auth_ui.login"`, `"auth_ui.register"`, `"auth_ui.forgot_password"`, and `"auth_ui.reset_password"` to the exemption list.
- **Corrected Setup Condition**:
  Changed condition to verify `if not admin_repo.has_admin() and not user_repo.has_admin():` — first-run setup is only triggered when no administrative accounts exist in the entire system.

### 2. `src/database/user_repository.py`
- **Quoted `"Users"` table name in raw SQL**:
  Enclosed `"Users"` in double-quotes across `has_users()`, `has_admin()`, and lookup queries to ensure seamless compatibility with PostgreSQL's case-sensitive table identifiers.

### 3. `dashboard/routes/admin.py`
- **Added explicit `/admin` and `/admin/` root routes**:
  Defined `admin_root()` to redirect unauthenticated visitors cleanly to `/admin/login` and authenticated admins to `/admin/dashboard`, preventing unintended 404 fallbacks.

### 4. Templates Updated to Canonical `url_for` Endpoints
- **`dashboard/templates/landing.html`**:
  - Header "Sign In" -> `{{ url_for('auth_ui.login') }}`
  - Header "Get Started" -> `{{ url_for('auth_ui.register') }}`
  - Hero "Explore Opportunities" -> `{{ url_for('auth_ui.login') }}`
  - Hero "Access Portal" -> `{{ url_for('auth_ui.login') }}`
  - Footer "User Login" -> `{{ url_for('auth_ui.login') }}`
  - Footer "Admin Gateway" -> `{{ url_for('admin_ui.admin_login') }}` (isolated in footer utility links)
- **`dashboard/templates/register.html`**:
  - Link to Sign In -> `{{ url_for('auth_ui.login') }}`
- **`dashboard/templates/login.html`**:
  - Form action -> `{{ url_for('auth_ui.login') }}`
  - Logo link -> `{{ url_for('dashboard_ui.landing') }}`
  - Forgot Password -> `{{ url_for('auth_ui.forgot_password') }}`
  - Create Account -> `{{ url_for('auth_ui.register') }}`
- **`dashboard/templates/forgot_password.html`**:
  - "Back to Sign In" -> `{{ url_for('auth_ui.login') }}`
- **`dashboard/templates/admin/admin_login.html`**:
  - "Return to User Portal" -> `{{ url_for('auth_ui.login') }}`

### 5. `tests/unit/test_auth_landing_redirect.py`
- Added comprehensive 10-point regression suite covering:
  1. Landing page Sign In link resolves to `/login`.
  2. Public actions in navbar and hero contain no `/admin` routes.
  3. Standard user login page loads with HTTP 200 and standard form.
  4. Admin login page loads at dedicated `/admin/login` route.
  5. Standard-user protected route redirects to `/login`.
  6. Admin-protected route redirects to `/admin/login`.
  7. Invalid/external `next` URLs rejected safely.
  8. Admin MFA flow remains functional.
  9. CSRF generation and validation functional.
  10. Strict identity separation (standard user denied access to `/admin/dashboard` with HTTP 403).

---

## 5. Before and After Behavior

| Scenario / Action | Before Fix | After Fix |
| :--- | :--- | :--- |
| Click "Sign In" on Landing Page (`/`) | Redirected via `/setup` to `/admin/login` (Admin Portal) | Navigates directly to `/login` (User Portal, HTTP 200) |
| Click "Get Started" on Landing Page | Hardcoded or redirected to setup | Navigates directly to `/register` (HTTP 200) |
| Visit `/login` directly as unauthenticated visitor | Redirected to `/setup` -> `/admin/login` | Renders standard User Sign In form (HTTP 200) |
| Visit `/admin` directly as unauthenticated visitor | May 404 or fall back | Redirects to `/admin/login` (HTTP 302) |
| Visit `/admin/dashboard` as standard user (`Viewer`) | N/A | HTTP 403 Forbidden (Blocked by `@admin_required`) |
| Admin MFA & CSRF Token Validation | Functional | Functional & strictly preserved |

---

## 6. Regression Testing Results

```
test_1_landing_signin_link_resolves_to_user_login (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_2_landing_does_not_contain_admin_link_for_public_signin (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_3_standard_user_login_page_loads (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_4_admin_login_page_dedicated_route (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_5_standard_protected_route_redirects_to_user_login (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_6_admin_protected_route_redirects_to_admin_login (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_7_invalid_or_external_next_urls_rejected (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_8_admin_mfa_flow_remains_functional (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_9_csrf_and_session_protections_functional (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok
test_10_identities_remain_strictly_separated (tests.unit.test_auth_landing_redirect.TestAuthLandingRedirect) ... ok

----------------------------------------------------------------------
Ran 10 tests in 12.768s

OK
```

---

## 7. Security Invariants Verification

- **Role Separation**: Standard user authentication and administrator authentication remain strictly isolated across separate routes, controllers, and session states (`user_id` vs `admin_authenticated`).
- **No Role Bypasses**: Unauthenticated users visiting admin endpoints are redirected to `/admin/login`, while authenticated non-admin users receive HTTP 403 Forbidden.
- **Open Redirect Protection**: Malicious or off-domain `next` parameters are rejected by `is_safe_internal_url()`.
- **Zero Git Mutations**: No Git modification commands were executed.

---

## 8. Final Status

**`VERIFIED`**
