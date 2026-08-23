# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import json
import frappe
from frappe.utils import now_datetime, validate_email_address, cstr
from frappe.utils.password import update_password


# ─────────────────────────────────────────────────────────────────────────────
# Helper & Security Guards
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_admin_access():
    """
    Guarantees that only users with 'System Manager' or 'Administrator'
    roles can invoke administrative user and permission management APIs.
    """
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Authentication required. Please log in.", frappe.AuthenticationError)

    user_roles = frappe.get_roles(frappe.session.user)
    if not any(r in user_roles for r in ("System Manager", "Administrator")):
        frappe.throw("Access denied. System Manager or Administrator role required.", frappe.PermissionError)


def _parse_roles(roles_input):
    """
    Parses roles from JSON array, Python list, or comma-separated string.
    Returns a clean list of unique, non-empty role name strings.
    """
    if not roles_input:
        return []
    if isinstance(roles_input, list):
        return [str(r).strip() for r in roles_input if str(r).strip()]
    if isinstance(roles_input, str):
        try:
            parsed = json.loads(roles_input)
            if isinstance(parsed, list):
                return [str(r).strip() for r in parsed if str(r).strip()]
        except (json.JSONDecodeError, ValueError):
            pass
        return [r.strip() for r in roles_input.split(",") if r.strip()]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# 1. User Creation & Registration Wrapper
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_system_user(
    email,
    first_name,
    last_name=None,
    roles=None,
    password=None,
    phone=None,
    contractor=None,
    user_type="System User",
    send_welcome_email=False,
    desk_access=None
):
    """
    Atomic 1-call endpoint to create a user account, set password, assign roles,
    and optionally link a Partner Agency (Contractor) with User Permissions.

    Params:
        - email (str): Unique user email / login username (Required).
        - first_name (str): First name / display name (Required).
        - last_name (str, optional): Last name.
        - roles (list/str, optional): Role names to assign (e.g. ['LMS Employee'] or ['Foreign Agency']).
        - password (str, optional): Password for immediate direct login.
        - phone (str, optional): Contact phone / mobile number.
        - contractor (str, optional): Contractor ID to bind this user to.
        - user_type (str, optional): 'System User' (default) or 'Website User'.
        - send_welcome_email (bool, optional): Whether Frappe should email credentials (default False).
        - desk_access (bool, optional): Explicit desk access override (1/0).

    Returns:
        Dict with status, user email, full_name, assigned roles, and linked contractor.
    """
    _ensure_admin_access()

    if not email or not str(email).strip():
        frappe.throw("Email address is required.")

    clean_email = str(email).strip().lower()
    validate_email_address(clean_email, throw=True)

    if not first_name or not str(first_name).strip():
        frappe.throw("First name is required.")

    clean_first_name = str(first_name).strip()
    clean_last_name = str(last_name).strip() if last_name else ""

    if frappe.db.exists("User", clean_email):
        frappe.throw(f"User with email '{clean_email}' already exists.", frappe.DuplicateEntryError)

    parsed_roles = _parse_roles(roles)

    # Determine user type and desk access defaults based on roles
    is_foreign_agency = "Foreign Agency" in parsed_roles
    if desk_access is None:
        desk_access = 0 if (is_foreign_agency or user_type == "Website User") else 1

    # 1. Create Base User Document
    user_doc = frappe.get_doc({
        "doctype": "User",
        "email": clean_email,
        "first_name": clean_first_name,
        "last_name": clean_last_name,
        "phone": phone or "",
        "mobile_no": phone or "",
        "user_type": user_type,
        "desk_theme": "Light",
        "send_welcome_email": 1 if send_welcome_email else 0,
        "enabled": 1,
        "roles": []
    })

    # Validate or auto-provision roles in the database
    STANDARD_SYSTEM_ROLES = {
        "Foreign Agency": 0,
        "LMS Employee": 1,
        "Accounts Manager": 1,
        "Wakala Officer": 1,
        "Injaz Officer": 1,
        "Embassy Officer": 1
    }
    for r in parsed_roles:
        if not frappe.db.exists("Role", r):
            if r in STANDARD_SYSTEM_ROLES:
                role_doc = frappe.get_doc({
                    "doctype": "Role",
                    "role_name": r,
                    "desk_access": STANDARD_SYSTEM_ROLES[r]
                })
                role_doc.insert(ignore_permissions=True)
            else:
                frappe.throw(f"Role '{r}' does not exist in the system.")
        user_doc.append("roles", {"role": r})

    user_doc.flags.no_welcome_mail = not send_welcome_email
    user_doc.flags.ignore_permissions = True

    user_doc.insert(ignore_permissions=True)

    # 2. Set Direct Login Password (if supplied)
    if password and str(password).strip():
        update_password(user=clean_email, pwd=str(password).strip())

    # 3. Handle Partner Agency (Contractor) Linking & Granular User Permission
    contractor_linked = None
    if contractor and str(contractor).strip():
        clean_contractor = str(contractor).strip()
        if not frappe.db.exists("Contractor", clean_contractor):
            frappe.throw(f"Partner Agency (Contractor) '{clean_contractor}' not found.", frappe.DoesNotExistError)

        # Set user permission so the user's queries are scoped to this Contractor
        if not frappe.db.exists("User Permission", {"user": clean_email, "allow": "Contractor", "for_value": clean_contractor}):
            perm_doc = frappe.get_doc({
                "doctype": "User Permission",
                "user": clean_email,
                "allow": "Contractor",
                "for_value": clean_contractor,
                "is_default": 1
            })
            perm_doc.insert(ignore_permissions=True)

        # Also update Contractor record if it lacks an email or user pointer
        c_doc = frappe.get_doc("Contractor", clean_contractor)
        if not c_doc.email:
            c_doc.email = clean_email
            c_doc.save(ignore_permissions=True)

        contractor_linked = clean_contractor

    frappe.db.commit()

    return {
        "status": "success",
        "message": f"User '{clean_email}' created successfully.",
        "user": {
            "email": clean_email,
            "full_name": user_doc.full_name or f"{clean_first_name} {clean_last_name}".strip(),
            "first_name": clean_first_name,
            "last_name": clean_last_name,
            "roles": parsed_roles,
            "enabled": 1,
            "contractor": contractor_linked,
            "desk_access": desk_access
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. Update User Profile & Activation
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def update_system_user(
    user,
    first_name=None,
    last_name=None,
    phone=None,
    enabled=None,
    roles=None,
    contractor=None
):
    """
    Updates profile details, enabled status, roles, or contractor binding of an existing user.
    """
    _ensure_admin_access()

    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User '{user}' not found.", frappe.DoesNotExistError)

    user_doc = frappe.get_doc("User", user)

    if first_name is not None:
        user_doc.first_name = str(first_name).strip()
    if last_name is not None:
        user_doc.last_name = str(last_name).strip()
    if phone is not None:
        user_doc.phone = str(phone).strip()
        user_doc.mobile_no = str(phone).strip()
    if enabled is not None:
        # Prevent disabling the primary Administrator or current active session admin
        if user == "Administrator" and int(enabled) == 0:
            frappe.throw("The default Administrator account cannot be disabled.")
        user_doc.enabled = 1 if int(enabled) else 0

    # Update roles if provided
    if roles is not None:
        parsed_roles = _parse_roles(roles)
        STANDARD_SYSTEM_ROLES = {
            "Foreign Agency": 0,
            "LMS Employee": 1,
            "Accounts Manager": 1,
            "Wakala Officer": 1,
            "Injaz Officer": 1,
            "Embassy Officer": 1
        }
        for r in parsed_roles:
            if not frappe.db.exists("Role", r):
                if r in STANDARD_SYSTEM_ROLES:
                    role_doc = frappe.get_doc({
                        "doctype": "Role",
                        "role_name": r,
                        "desk_access": STANDARD_SYSTEM_ROLES[r]
                    })
                    role_doc.insert(ignore_permissions=True)
                else:
                    frappe.throw(f"Role '{r}' does not exist.")

        # Re-populate roles table
        user_doc.set("roles", [])
        for r in parsed_roles:
            user_doc.append("roles", {"role": r})

    user_doc.save(ignore_permissions=True)

    # Update Contractor binding if provided
    contractor_linked = None
    if contractor is not None:
        clean_contractor = str(contractor).strip() if contractor else None
        # Remove existing Contractor permissions for this user
        frappe.db.sql("DELETE FROM `tabUser Permission` WHERE user = %s AND allow = 'Contractor'", (user,))

        if clean_contractor:
            if not frappe.db.exists("Contractor", clean_contractor):
                frappe.throw(f"Partner Agency '{clean_contractor}' not found.", frappe.DoesNotExistError)

            perm_doc = frappe.get_doc({
                "doctype": "User Permission",
                "user": user,
                "allow": "Contractor",
                "for_value": clean_contractor,
                "is_default": 1
            })
            perm_doc.insert(ignore_permissions=True)
            contractor_linked = clean_contractor
    else:
        contractor_linked = frappe.db.get_value("User Permission", {"user": user, "allow": "Contractor"}, "for_value")

    frappe.db.commit()

    return {
        "status": "success",
        "message": f"User '{user}' updated successfully.",
        "user": {
            "email": user_doc.name,
            "full_name": user_doc.full_name,
            "first_name": user_doc.first_name,
            "last_name": user_doc.last_name,
            "enabled": user_doc.enabled,
            "roles": [r.role for r in user_doc.roles],
            "contractor": contractor_linked
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Direct Password Management API
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def set_user_password(user, new_password, logout_all_sessions=True):
    """
    Allows administrators to directly set or reset a password for any user account.
    """
    _ensure_admin_access()

    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User '{user}' not found.", frappe.DoesNotExistError)

    if not new_password or len(str(new_password).strip()) < 6:
        frappe.throw("Password must be at least 6 characters long.")

    update_password(
        user=user,
        pwd=str(new_password).strip(),
        logout_all_sessions=bool(logout_all_sessions)
    )
    frappe.db.commit()

    return {
        "status": "success",
        "message": f"Password for user '{user}' has been updated successfully."
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. Role Assignment & Synchronization API
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def assign_user_roles(user, roles, replace=False):
    """
    Assigns roles to a user.
    If replace=True, replaces all non-standard roles with the provided list.
    If replace=False (default), appends the roles if not already present.
    """
    _ensure_admin_access()

    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User '{user}' not found.", frappe.DoesNotExistError)

    parsed_roles = _parse_roles(roles)
    if not parsed_roles and not replace:
        frappe.throw("No roles specified.")

    STANDARD_SYSTEM_ROLES = {
        "Foreign Agency": 0,
        "LMS Employee": 1,
        "Accounts Manager": 1,
        "Wakala Officer": 1,
        "Injaz Officer": 1,
        "Embassy Officer": 1
    }
    for r in parsed_roles:
        if not frappe.db.exists("Role", r):
            if r in STANDARD_SYSTEM_ROLES:
                role_doc = frappe.get_doc({
                    "doctype": "Role",
                    "role_name": r,
                    "desk_access": STANDARD_SYSTEM_ROLES[r]
                })
                role_doc.insert(ignore_permissions=True)
            else:
                frappe.throw(f"Role '{r}' does not exist.")

    user_doc = frappe.get_doc("User", user)

    if replace:
        user_doc.set("roles", [])
        for r in parsed_roles:
            user_doc.append("roles", {"role": r})
    else:
        existing_roles = {r.role for r in user_doc.roles}
        for r in parsed_roles:
            if r not in existing_roles:
                user_doc.append("roles", {"role": r})

    user_doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "message": f"Roles for '{user}' updated successfully.",
        "roles": [r.role for r in user_doc.roles]
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5. Granular User Permissions API
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def manage_user_permission(action, user, doctype=None, docname=None, is_default=1):
    """
    Manages granular data restrictions (User Permission records).

    Actions:
        - 'list': Returns all active User Permission records for the user.
        - 'add': Creates a User Permission record (doctype & docname required).
        - 'remove': Deletes matching User Permission record(s).
    """
    _ensure_admin_access()

    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User '{user}' not found.", frappe.DoesNotExistError)

    action_lower = str(action).strip().lower()

    if action_lower == "list":
        permissions = frappe.get_all(
            "User Permission",
            filters={"user": user},
            fields=["name", "allow", "for_value", "is_default", "creation"]
        )
        return {"status": "success", "user": user, "permissions": permissions}

    if action_lower == "add":
        if not doctype or not docname:
            frappe.throw("Both 'doctype' and 'docname' are required to add a user permission.")

        if not frappe.db.exists(doctype, docname):
            frappe.throw(f"Record '{docname}' of DocType '{doctype}' does not exist.")

        existing = frappe.db.get_value("User Permission", {"user": user, "allow": doctype, "for_value": docname}, "name")
        if existing:
            return {"status": "success", "message": "Permission already exists.", "permission_name": existing}

        perm = frappe.get_doc({
            "doctype": "User Permission",
            "user": user,
            "allow": doctype,
            "for_value": docname,
            "is_default": 1 if int(is_default) else 0
        })
        perm.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": f"Permission for {doctype} '{docname}' assigned to '{user}'.",
            "permission_name": perm.name
        }

    if action_lower == "remove":
        if not doctype or not docname:
            frappe.throw("Both 'doctype' and 'docname' are required to remove a user permission.")

        existing = frappe.get_all("User Permission", filters={"user": user, "allow": doctype, "for_value": docname}, pluck="name")
        if not existing:
            return {"status": "success", "message": "No matching permission found to remove."}

        for perm_name in existing:
            frappe.delete_doc("User Permission", perm_name, ignore_permissions=True)

        frappe.db.commit()
        return {"status": "success", "message": f"Removed permission for {doctype} '{docname}' from '{user}'."}

    frappe.throw(f"Invalid action '{action}'. Supported actions: 'list', 'add', 'remove'.")


# ─────────────────────────────────────────────────────────────────────────────
# 6. User Directory, Search & Filtering API
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_system_users(role=None, status="all", search=None, limit=50, start=0):
    """
    Returns a paginated roster of users with their roles, status, linked agency,
    and profile info for the frontend Admin User Management screen.
    """
    _ensure_admin_access()

    conditions = ["u.name NOT IN ('Guest')"]
    params = {}

    if status == "active":
        conditions.append("u.enabled = 1")
    elif status == "disabled":
        conditions.append("u.enabled = 0")

    if search and str(search).strip():
        conditions.append("(u.name LIKE %(s)s OR u.full_name LIKE %(s)s OR u.phone LIKE %(s)s)")
        params["s"] = f"%{str(search).strip()}%"

    if role and str(role).strip():
        conditions.append("EXISTS (SELECT 1 FROM `tabHas Role` hr WHERE hr.parent = u.name AND hr.role = %(role)s)")
        params["role"] = str(role).strip()

    where_clause = " AND ".join(conditions)

    # Count total matching users
    count_sql = f"SELECT COUNT(*) as cnt FROM `tabUser` u WHERE {where_clause}"
    total_records = frappe.db.sql(count_sql, params, as_dict=True)[0].cnt

    # Fetch paginated users
    sql = f"""
        SELECT
            u.name AS email,
            u.full_name,
            u.first_name,
            u.last_name,
            u.phone,
            u.user_type,
            u.user_image,
            u.enabled,
            u.last_login,
            u.last_active,
            u.creation,
            u.modified
        FROM `tabUser` u
        WHERE {where_clause}
        ORDER BY u.creation DESC
        LIMIT {int(start)}, {int(limit)}
    """
    users = frappe.db.sql(sql, params, as_dict=True)

    # Batch attach roles and linked contractors
    user_emails = [u["email"] for u in users]
    roles_map = {}
    contractor_map = {}

    if user_emails:
        # Fetch all roles
        has_roles = frappe.get_all(
            "Has Role",
            filters={"parent": ["in", user_emails], "parenttype": "User"},
            fields=["parent", "role"]
        )
        for hr in has_roles:
            roles_map.setdefault(hr.parent, []).append(hr.role)

        # Fetch contractor permissions
        perms = frappe.get_all(
            "User Permission",
            filters={"user": ["in", user_emails], "allow": "Contractor"},
            fields=["user", "for_value"]
        )
        for p in perms:
            contractor_map[p.user] = p.for_value

    for u in users:
        u["roles"] = roles_map.get(u["email"], [])
        u["contractor"] = contractor_map.get(u["email"])

    return {
        "users": users,
        "total": total_records,
        "limit": int(limit),
        "start": int(start)
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. Available System Roles Reference API
# ─────────────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def get_available_roles():
    """
    Returns curated system roles categorized with human-readable labels and descriptions
    for frontend dropdowns and role selection checklists.
    """
    _ensure_admin_access()

    CURATED_ROLES = [
        {
            "role": "System Manager",
            "category": "Administration",
            "label": "System Administrator",
            "description": "Full administrative control, manager overrides, and user management."
        },
        {
            "role": "LMS Employee",
            "category": "Operations",
            "label": "Operations Officer",
            "description": "Applicant registration, GAMCA medical, clearance processing, and ticketing."
        },
        {
            "role": "Accounts Manager",
            "category": "Finance",
            "label": "Accounts & Commission Manager",
            "description": "Financial ledger, income/expense logs, and agency commission billing."
        },
        {
            "role": "Foreign Agency",
            "category": "External Partner",
            "label": "Partner Agency User",
            "description": "Portal candidate browsing, reservation locks, and dispute submissions."
        },
        {
            "role": "Wakala Officer",
            "category": "Specialized Clearances",
            "label": "Wakala / Musaned Officer",
            "description": "Dedicated Musaned Wakala verification and payment monitoring."
        },
        {
            "role": "Injaz Officer",
            "category": "Specialized Clearances",
            "label": "Injaz / MOFA Officer",
            "description": "MOFA Injaz visa submission and verification."
        },
        {
            "role": "Embassy Officer",
            "category": "Specialized Clearances",
            "label": "Embassy Liaison Officer",
            "description": "Consular submission, visa stamping, and biometric tracking."
        },
    ]

    # Check which roles actually exist in the DB
    existing_roles = set(frappe.get_all("Role", pluck="name"))

    roles_output = []
    for r in CURATED_ROLES:
        if r["role"] in existing_roles:
            roles_output.append({**r, "installed": True})
        else:
            roles_output.append({**r, "installed": False})

    return {"status": "success", "roles": roles_output}


# ─────────────────────────────────────────────────────────────────────────────
# 8. Single User Detailed Profile API
# ────────────────────────────────情報
@frappe.whitelist()
def get_user_detail(user):
    """
    Returns full profile, assigned roles, active user permissions, and linked contractor
    for a specific user.
    """
    _ensure_admin_access()

    if not user or not frappe.db.exists("User", user):
        frappe.throw(f"User '{user}' not found.", frappe.DoesNotExistError)

    user_doc = frappe.get_doc("User", user)
    roles = [r.role for r in user_doc.roles]

    user_permissions = frappe.get_all(
        "User Permission",
        filters={"user": user},
        fields=["name", "allow", "for_value", "is_default"]
    )

    contractor_linked = frappe.db.get_value("User Permission", {"user": user, "allow": "Contractor"}, "for_value")

    return {
        "status": "success",
        "user": {
            "email": user_doc.name,
            "full_name": user_doc.full_name,
            "first_name": user_doc.first_name,
            "last_name": user_doc.last_name,
            "phone": user_doc.phone or user_doc.mobile_no,
            "enabled": user_doc.enabled,
            "user_type": user_doc.user_type,
            "user_image": user_doc.user_image,
            "last_login": user_doc.last_login,
            "last_active": user_doc.last_active,
            "creation": user_doc.creation,
            "roles": roles,
            "contractor": contractor_linked,
            "permissions": user_permissions
        }
    }
