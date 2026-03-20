## Superadmin Tenant Management Console

### Summary
Add a dedicated superadmin-only tenant management area in the dashboard for church lifecycle, plan administration, limit overrides, and tenant support visibility.

This v1 will be **tenant administration only**:
- manage church profile
- create church
- assign first church admin during creation
- change church status (`draft`, `active`, `suspended`, `archived`)
- assign plan and override limits
- view tenant usage and admin contacts

It will **not** add church-content editing from the superadmin console. Church content stays inside each tenant dashboard.

### Implementation Changes
- Add a new superadmin dashboard section in the existing sidebar under the current `Super Admin` block.
  - New entry: `Gestion des eglises`
  - Keep existing `Parametres plateforme`
- Add new superadmin-only routes under a platform namespace style, for example:
  - `dashboard/platform/churches/`
  - `dashboard/platform/churches/create/`
  - `dashboard/platform/churches/<id>/`
  - `dashboard/platform/churches/<id>/edit/`
  - `dashboard/platform/churches/<id>/status/`
  - `dashboard/platform/churches/<id>/plan/`
- Keep all route protection in the existing capability system using `CAP_MANAGE_SITE_SETTINGS`. Do not introduce ad hoc superadmin checks in templates or views.

- Add dedicated superadmin forms instead of reusing `ChurchForm`.
  - `SuperAdminChurchCreateForm`
    - church profile basics
    - status
    - plan
    - optional limit overrides
    - first admin selection by existing user email/username or new user creation fields
  - `SuperAdminChurchUpdateForm`
    - editable tenant profile and status
  - `SuperAdminChurchPlanForm`
    - plan
    - all override fields already present on `Church`
  - `SuperAdminChurchStatusForm`
    - explicit lifecycle transitions only
- Do not overload tenant-facing `ChurchForm` with plan/status fields.

- Add a tenant list page with:
  - search by church name, city, slug, admin email
  - filters for status and plan
  - usage summary columns
  - active admin count
  - quick actions: view, edit, change status, plan/limits
- Add a tenant detail page with:
  - church identity and status
  - plan and effective limits
  - current usage from `get_plan_usage`
  - active admins and memberships summary
  - recent audit entries for that tenant
  - support shortcuts: switch into tenant, open audit filtered to tenant

- Creation flow will be **Create + Assign Admin in one transaction**.
  - Create church
  - create or attach first admin membership
  - validate single-church rule for non-superusers
  - if creating a new admin user, reuse the existing account creation rules and password validation
  - if anything fails, rollback the whole operation
- Default created church status:
  - use the submitted status
  - recommended UI default is `draft`
- If a church is created as `active`, the first admin must be active immediately.
- Prevent creating an active church without at least one active admin.

- Lifecycle rules:
  - `draft`: visible in superadmin console only, not public, not available to normal tenant access
  - `active`: normal tenant behavior
  - `suspended`: public pages blocked and tenant dashboard access blocked for non-superusers
  - `archived`: same access block as suspended, treated as inactive historical tenant
- Status changes must be explicit POST actions, not GET.
- Add confirmation UX for suspend/archive/reactivate actions.
- Keep existing middleware and permission behavior aligned with these statuses.

- Support console behavior:
  - superadmin can see all tenants regardless of status
  - superadmin can switch into any tenant from the detail page or existing church selector
  - superadmin can inspect tenant usage and admin roster without using Django admin
  - no direct content CRUD from this console

- Audit:
  - log church create
  - log church profile update
  - log status change
  - log plan change
  - log limit override change
  - log first-admin assignment
- Reuse the existing audit subsystem with clear action names and metadata payloads.

### Public Interfaces / Routes
- New route names should be explicit and stable:
  - `superadmin_church_list`
  - `superadmin_church_create`
  - `superadmin_church_detail`
  - `superadmin_church_edit`
  - `superadmin_church_status`
  - `superadmin_church_plan`
- New templates under `templates/admin_dashboard/superadmin/`:
  - `church_list.html`
  - `church_form.html`
  - `church_detail.html`
  - `church_plan_form.html`
  - `church_status_form.html`

### Test Plan
- Unit tests
  - new superadmin forms validate status, plan, and override fields correctly
  - create flow rejects invalid first-admin assignment
  - status transition validation works as intended
- Integration tests
  - superadmin can create a church and assign first admin in one flow
  - failed admin assignment rolls back church creation
  - superadmin can update church plan and overrides
  - superadmin can suspend, archive, and reactivate a church
  - tenant list filters by status and plan
  - audit logs are created for each superadmin action
- Application tests
  - non-superusers are denied all new superadmin routes
  - suspended/archived churches remain inaccessible to tenant users
  - superadmin can still view and switch into suspended/archived tenants for support
  - sidebar shows the new section only to superadmin
- Regression tests
  - existing tenant dashboard behavior remains unchanged
  - existing plan enforcement still uses the effective limit values after overrides

### Assumptions
- Scope is limited to **tenant administration only**, not cross-tenant content editing.
- Church creation flow is **Create + Assign Admin** in one transaction.
- Existing `Church` fields for plan, status, and overrides are sufficient; no schema changes are required unless an implementation gap appears during form wiring.
- Superadmin access continues to be granted through the existing capability model and not through separate template-only logic.
- After implementation, changed files and the proposed commit message will be shown for your review before any commit.
