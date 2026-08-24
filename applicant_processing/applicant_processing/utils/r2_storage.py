# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import os
import mimetypes
import frappe

def get_r2_settings():
    """Fetches Cloudflare R2 Settings doc, site config, or environment variables."""
    # 1. Check Cloudflare R2 Settings DocType
    try:
        if frappe.db.exists("DocType", "Cloudflare R2 Settings"):
            doc = frappe.get_single("Cloudflare R2 Settings")
            if doc.get("enabled") and doc.get("account_id") and doc.get("access_key_id"):
                return {
                    "enabled": 1,
                    "account_id": doc.get("account_id"),
                    "access_key_id": doc.get("access_key_id"),
                    "secret_access_key": doc.get_password("secret_access_key") if hasattr(doc, "get_password") else doc.get("secret_access_key"),
                    "bucket_name": doc.get("bucket_name") or "tracking-agency",
                    "public_domain": (doc.get("public_domain") or "").rstrip("/"),
                    "sync_cv_pdfs": doc.get("sync_cv_pdfs", 1),
                    "sync_applicant_photos": doc.get("sync_applicant_photos", 1),
                    "sync_contracts": doc.get("sync_contracts", 1),
                    "auto_sync_on_upload": doc.get("auto_sync_on_upload", 1),
                    "use_presigned_for_private": doc.get("use_presigned_for_private", 0),
                }
    except Exception:
        pass

    # 2. Check site_config.json
    conf = getattr(frappe, "conf", {})
    r2_conf = conf.get("cloudflare_r2", {})
    if r2_conf and r2_conf.get("access_key_id"):
        return {
            "enabled": 1,
            "account_id": r2_conf.get("account_id") or "d15df85be1a4d4b5cb1fbf61381eede7",
            "access_key_id": r2_conf.get("access_key_id"),
            "secret_access_key": r2_conf.get("secret_access_key"),
            "bucket_name": r2_conf.get("bucket_name") or "tracking-agency",
            "public_domain": (r2_conf.get("public_domain") or "").rstrip("/"),
            "sync_cv_pdfs": r2_conf.get("sync_cv_pdfs", 1),
            "sync_applicant_photos": r2_conf.get("sync_applicant_photos", 1),
            "sync_contracts": r2_conf.get("sync_contracts", 1),
            "auto_sync_on_upload": r2_conf.get("auto_sync_on_upload", 1),
            "use_presigned_for_private": r2_conf.get("use_presigned_for_private", 0),
        }

    # 3. Check Environment Variables (useful for Railway / Docker deployments)
    env_acc = os.environ.get("CLOUDFLARE_R2_ACCOUNT_ID") or os.environ.get("R2_ACCOUNT_ID") or "d15df85be1a4d4b5cb1fbf61381eede7"
    env_key = os.environ.get("CLOUDFLARE_R2_ACCESS_KEY_ID") or os.environ.get("R2_ACCESS_KEY_ID") or "9eaa499d46c47dfa01b651353eb1a9a9"
    env_sec = os.environ.get("CLOUDFLARE_R2_SECRET_ACCESS_KEY") or os.environ.get("R2_SECRET_ACCESS_KEY") or "98f54ae6632aa5f5e69da90431cb2022f0662ac0a06329242ef4d0ff85b132aa"
    env_bkt = os.environ.get("CLOUDFLARE_R2_BUCKET_NAME") or os.environ.get("R2_BUCKET_NAME") or "tracking-agency"
    env_dom = (os.environ.get("CLOUDFLARE_R2_PUBLIC_DOMAIN") or os.environ.get("R2_PUBLIC_DOMAIN") or "").rstrip("/")

    if env_acc and env_key and env_sec:
        return {
            "enabled": 1,
            "account_id": env_acc,
            "access_key_id": env_key,
            "secret_access_key": env_sec,
            "bucket_name": env_bkt,
            "public_domain": env_dom,
            "sync_cv_pdfs": 1,
            "sync_applicant_photos": 1,
            "sync_contracts": 1,
            "auto_sync_on_upload": 1,
            "use_presigned_for_private": 0,
        }

    return None


def get_r2_client():
    """Initializes and returns a boto3 S3 client configured for Cloudflare R2."""
    settings = get_r2_settings()
    if not settings or not settings.get("enabled"):
        return None, "Cloudflare R2 is disabled or not configured."

    account_id = settings.get("account_id")
    access_key = settings.get("access_key_id")
    secret_key = settings.get("secret_access_key")

    if not account_id or not access_key or not secret_key:
        return None, "Missing Cloudflare Account ID, Access Key ID, or Secret Access Key."

    import boto3
    from botocore.config import Config

    endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"

    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"})
    )

    return s3_client, None


def upload_bytes_to_r2(bytes_data, key, content_type=None):
    """
    Uploads raw bytes directly to Cloudflare R2 bucket.
    Returns the public/CDN URL or the key.
    """
    settings = get_r2_settings()
    client, err = get_r2_client()
    if not client:
        return {"status": "error", "message": err}

    bucket = settings.get("bucket_name")
    if not content_type:
        content_type, _ = mimetypes.guess_type(key)
        content_type = content_type or "application/octet-stream"

    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=bytes_data,
            ContentType=content_type
        )
        url = get_r2_url(key)
        return {
            "status": "success",
            "key": key,
            "url": url,
            "bucket": bucket
        }
    except Exception as e:
        frappe.log_error(f"Cloudflare R2 Upload Bytes Failed: {e}", "Cloudflare R2")
        return {"status": "error", "message": str(e)}


def upload_file_to_r2(local_file_path, key=None, content_type=None):
    """
    Uploads a physical file from local filesystem to Cloudflare R2 bucket.
    """
    if not local_file_path or not os.path.exists(local_file_path):
        return {"status": "error", "message": f"File not found: {local_file_path}"}

    settings = get_r2_settings()
    client, err = get_r2_client()
    if not client:
        return {"status": "error", "message": err}

    bucket = settings.get("bucket_name")
    if not key:
        key = os.path.basename(local_file_path)

    if not content_type:
        content_type, _ = mimetypes.guess_type(local_file_path)
        content_type = content_type or "application/octet-stream"

    try:
        with open(local_file_path, "rb") as f:
            client.put_object(
                Bucket=bucket,
                Key=key,
                Body=f,
                ContentType=content_type
            )
        url = get_r2_url(key)
        return {
            "status": "success",
            "key": key,
            "url": url,
            "bucket": bucket
        }
    except Exception as e:
        frappe.log_error(f"Cloudflare R2 Upload File Failed: {e}", "Cloudflare R2")
        return {"status": "error", "message": str(e)}


def get_r2_url(key):
    """
    Constructs the public CDN URL for an R2 key, or falls back to standard R2 URL.
    """
    settings = get_r2_settings()
    if not settings:
        return key

    pub_domain = settings.get("public_domain")
    if pub_domain:
        return f"{pub_domain}/{key.lstrip('/')}"

    return f"https://{settings.get('bucket_name')}.{settings.get('account_id')}.r2.cloudflarestorage.com/{key.lstrip('/')}"


def generate_presigned_url(key, expires_in=3600):
    """
    Generates a secure temporary presigned download URL for private documents.
    """
    settings = get_r2_settings()
    client, err = get_r2_client()
    if not client:
        return None

    try:
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.get("bucket_name"), "Key": key},
            ExpiresIn=expires_in
        )
        return url
    except Exception as e:
        frappe.log_error(f"Generate Presigned URL Failed: {e}", "Cloudflare R2")
        return None


def sync_frappe_file_to_r2(file_url):
    """
    Translates a Frappe file_url (/files/..., /private/files/...) to physical file,
    uploads it to Cloudflare R2, and returns the R2 URL.
    """
    if not file_url:
        return None

    url_str = str(file_url).strip()
    if url_str.startswith("http://") or url_str.startswith("https://"):
        return url_str

    clean_path = url_str.lstrip("/").replace("\\", "/")
    basename = os.path.basename(clean_path)

    # Check candidates
    candidate_paths = [
        frappe.get_site_path("public", "files", basename),
        frappe.get_site_path("private", "files", basename),
        frappe.get_site_path("public", clean_path),
        frappe.get_site_path(clean_path),
    ]

    for p in candidate_paths:
        if p and os.path.exists(p) and os.path.isfile(p):
            key = f"media/{basename}" if not clean_path.startswith("private") else f"private/{basename}"
            res = upload_file_to_r2(p, key=key)
            if res.get("status") == "success":
                return res.get("url")

    return file_url


def get_r2_key(doctype, docname, fieldname=None, filename=None):
    """
    Constructs an organized, clean folder hierarchy for Cloudflare R2:
    - Applicant Photos: applicants/{APP-00001}/photos/passport_photo.png
    - Applicant Scans: applicants/{APP-00001}/scans/passport_scan.png
    - Generated CVs: applicants/{APP-00001}/cvs/CV-APP-00001-CV-00001.pdf
    - Dossier Contracts: dossiers/{DOS-00001}/contract.pdf
    - General Documents: {doctype_plural}/{docname}/{filename}
    """
    if not filename:
        filename = "document"

    clean_fn = os.path.basename(str(filename).replace("\\", "/"))

    if doctype == "Applicant":
        if fieldname in ("photo_passport", "photo_full_body"):
            return f"applicants/{docname}/photos/{clean_fn}"
        elif fieldname == "passport_scan":
            return f"applicants/{docname}/scans/{clean_fn}"
        else:
            return f"applicants/{docname}/general/{clean_fn}"
    elif doctype == "CV Record":
        return f"applicants/{docname}/cvs/{clean_fn}"
    elif doctype == "Applicant Dossier":
        return f"dossiers/{docname}/contracts/{clean_fn}"
    elif doctype:
        dt_slug = doctype.lower().replace(" ", "_") + "s"
        return f"{dt_slug}/{docname}/{clean_fn}"

    return f"media/{clean_fn}"


def notify_frontend(event_name, data=None):
    """Publishes a realtime socket event to connected frontend clients."""
    try:
        frappe.publish_realtime(
            event=event_name,
            message=data or {},
            after_commit=True
        )
    except Exception:
        pass


def test_connection():
    """Tests connection to Cloudflare R2 bucket by listing objects or checking head_bucket."""
    settings = get_r2_settings()
    if not settings:
        return {"status": "error", "message": "Cloudflare R2 Settings not found or disabled."}

    client, err = get_r2_client()
    if not client:
        return {"status": "error", "message": err}

    bucket = settings.get("bucket_name")
    if not bucket:
        return {"status": "error", "message": "Bucket name is required."}

    try:
        client.head_bucket(Bucket=bucket)
        return {
            "status": "success",
            "message": f"Successfully connected to Cloudflare R2 bucket: '{bucket}'."
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to connect to R2 bucket '{bucket}': {e}"
        }


@frappe.whitelist()
def sync_all_existing_media():
    """
    Scans all Applicant records and CV Records, uploads local files to Cloudflare R2,
    and updates the document fields with R2 reference URLs.
    """
    settings = get_r2_settings()
    if not settings:
        return {"status": "error", "message": "Cloudflare R2 is not configured."}

    synced_counts = {"applicants": 0, "cvs": 0, "dossiers": 0}

    # 1. Sync Applicant Photos & Scans
    applicants = frappe.get_all("Applicant", fields=["name", "photo_passport", "photo_full_body", "passport_scan"])
    for app in applicants:
        updates = {}
        for field in ["photo_passport", "photo_full_body", "passport_scan"]:
            val = app.get(field)
            if val and not str(val).startswith("http://") and not str(val).startswith("https://") and not str(val).startswith("data:image"):
                key = get_r2_key("Applicant", app.name, fieldname=field, filename=val)
                p = frappe.get_site_path("public", "files", os.path.basename(val))
                if not os.path.exists(p):
                    p = frappe.get_site_path("private", "files", os.path.basename(val))
                if os.path.exists(p):
                    res = upload_file_to_r2(p, key=key)
                    if res.get("status") == "success":
                        updates[field] = res.get("url")

        if updates:
            frappe.db.set_value("Applicant", app.name, updates, update_modified=False)
            synced_counts["applicants"] += 1

    # 2. Sync CV Records
    if frappe.db.exists("DocType", "CV Record"):
        cv_records = frappe.get_all("CV Record", fields=["name", "applicant", "file_attachment"])
        for cv in cv_records:
            val = cv.get("file_attachment")
            if val and not str(val).startswith("http://") and not str(val).startswith("https://"):
                key = f"applicants/{cv.applicant or 'general'}/cvs/{os.path.basename(val)}"
                p = frappe.get_site_path("private", "files", os.path.basename(val))
                if not os.path.exists(p):
                    p = frappe.get_site_path("public", "files", os.path.basename(val))
                if os.path.exists(p):
                    res = upload_file_to_r2(p, key=key, content_type="application/pdf")
                    if res.get("status") == "success":
                        frappe.db.set_value("CV Record", cv.name, {
                            "file_attachment": res.get("url")
                        }, update_modified=False)
                        synced_counts["cvs"] += 1

    # 3. Sync Applicant Dossiers
    if frappe.db.exists("DocType", "Applicant Dossier"):
        dossiers = frappe.get_all("Applicant Dossier", fields=["name", "applicant", "attached_file"])
        for dos in dossiers:
            val = dos.get("attached_file")
            if val and not str(val).startswith("http://") and not str(val).startswith("https://"):
                key = f"dossiers/{dos.name}/contracts/{os.path.basename(val)}"
                p = frappe.get_site_path("private", "files", os.path.basename(val))
                if not os.path.exists(p):
                    p = frappe.get_site_path("public", "files", os.path.basename(val))
                if os.path.exists(p):
                    res = upload_file_to_r2(p, key=key, content_type="application/pdf")
                    if res.get("status") == "success":
                        frappe.db.set_value("Applicant Dossier", dos.name, {
                            "attached_file": res.get("url")
                        }, update_modified=False)
                        synced_counts["dossiers"] += 1

    frappe.db.commit()
    return {
        "status": "success",
        "message": f"Successfully synced to Cloudflare R2: {synced_counts['applicants']} applicants, {synced_counts['cvs']} CVs, {synced_counts['dossiers']} dossiers.",
        "synced": synced_counts
    }
