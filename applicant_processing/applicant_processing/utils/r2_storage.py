# Copyright (c) 2026, Admin and contributors
# For license information, please see license.txt

import os
import mimetypes
import frappe

def get_r2_settings():
    """Fetches Cloudflare R2 Settings doc or dict."""
    try:
        if frappe.db.exists("DocType", "Cloudflare R2 Settings"):
            doc = frappe.get_single("Cloudflare R2 Settings")
            return {
                "enabled": doc.get("enabled"),
                "account_id": doc.get("account_id"),
                "access_key_id": doc.get("access_key_id"),
                "secret_access_key": doc.get_password("secret_access_key") if hasattr(doc, "get_password") else doc.get("secret_access_key"),
                "bucket_name": doc.get("bucket_name"),
                "public_domain": (doc.get("public_domain") or "").rstrip("/"),
                "sync_cv_pdfs": doc.get("sync_cv_pdfs"),
                "sync_applicant_photos": doc.get("sync_applicant_photos"),
                "sync_contracts": doc.get("sync_contracts"),
                "auto_sync_on_upload": doc.get("auto_sync_on_upload"),
                "use_presigned_for_private": doc.get("use_presigned_for_private"),
            }
    except Exception:
        pass

    # Fallback to site_config.json if configured there
    conf = getattr(frappe, "conf", {})
    r2_conf = conf.get("cloudflare_r2", {})
    if r2_conf:
        return {
            "enabled": r2_conf.get("enabled", True),
            "account_id": r2_conf.get("account_id"),
            "access_key_id": r2_conf.get("access_key_id"),
            "secret_access_key": r2_conf.get("secret_access_key"),
            "bucket_name": r2_conf.get("bucket_name"),
            "public_domain": (r2_conf.get("public_domain") or "").rstrip("/"),
            "sync_cv_pdfs": r2_conf.get("sync_cv_pdfs", True),
            "sync_applicant_photos": r2_conf.get("sync_applicant_photos", True),
            "sync_contracts": r2_conf.get("sync_contracts", True),
            "auto_sync_on_upload": r2_conf.get("auto_sync_on_upload", True),
            "use_presigned_for_private": r2_conf.get("use_presigned_for_private", False),
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
