#!/bin/bash
set -e

# Detect Railway domain or fallback to configured SITE_NAME
DETECTED_DOMAIN="${RAILWAY_PUBLIC_DOMAIN:-${RAILWAY_STATIC_URL:-}}"
DETECTED_DOMAIN="${DETECTED_DOMAIN#https://}"
DETECTED_DOMAIN="${DETECTED_DOMAIN%/}"

SITE_NAME="${SITE_NAME:-${DETECTED_DOMAIN:-applicant-processing.railway.internal}}"
PORT="${PORT:-8000}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin}"

# Support both MariaDB Docker image variables and Railway MySQL variables
DB_HOST="${DB_HOST:-${MARIADB_HOST:-${MYSQLHOST:-mariadb}}}"
DB_PORT="${DB_PORT:-${MARIADB_PORT:-${MYSQLPORT:-3306}}}"
DB_USER="${DB_USER:-${MARIADB_USER:-${MYSQLUSER:-root}}}"
DB_PASSWORD="${DB_PASSWORD:-${MARIADB_PASSWORD:-${MYSQLPASSWORD:-${MARIADB_ROOT_PASSWORD:-root}}}}"
DB_NAME="${DB_NAME:-${MARIADB_DATABASE:-${MYSQLDATABASE:-frappe}}}"

# Support standard Railway Redis environment variables
REDIS_URL="${REDIS_URL:-${REDIS_PRIVATE_URL:-redis://redis:6379}}"
REDIS_CACHE_URL="${REDIS_CACHE_URL:-${REDIS_URL}}"
REDIS_QUEUE_URL="${REDIS_QUEUE_URL:-${REDIS_URL}}"

echo "=========================================================="
echo " Starting Applicant Processing App on Railway"
echo " Site Name:   $SITE_NAME"
echo " Detected:    $DETECTED_DOMAIN"
echo " Port:        $PORT"
echo " DB Host:     $DB_HOST:$DB_PORT"
echo " DB Name:     $DB_NAME"
echo " DB User:     $DB_USER"
echo "=========================================================="

cd /home/frappe/frappe-bench

export PYTHONPATH="/home/frappe/frappe-bench/apps/frappe:/home/frappe/frappe-bench/apps/applicant_processing:/home/frappe/frappe-bench/sites:${PYTHONPATH}"

# 1. Update common_site_config.json with default_site & Redis URLs
cat <<EOF > sites/common_site_config.json
{
  "auto_update": false,
  "background_workers": 1,
  "default_site": "${SITE_NAME}",
  "developer_mode": 0,
  "dns_multitenant": false,
  "file_watcher_port": 6787,
  "gunicorn_workers": 2,
  "rebase_on_pull": false,
  "redis_cache": "${REDIS_CACHE_URL}",
  "redis_queue": "${REDIS_QUEUE_URL}",
  "redis_socketio": "${REDIS_CACHE_URL}",
  "restart_supervisor_on_update": false,
  "restart_systemd_on_update": false,
  "serve_default_site": true,
  "socketio_port": 9000,
  "webserver_port": ${PORT}
}
EOF

# 2. Wait for Database
echo "Waiting for Database connection at $DB_HOST:$DB_PORT..."
until nc -z -v -w30 "$DB_HOST" "$DB_PORT" 2>/dev/null; do
  echo "Database is not available yet. Retrying in 3 seconds..."
  sleep 3
done
echo "Database is reachable!"

# 3. Check if database is already initialized or fresh
TABLE_EXISTS=$(mariadb -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" -p"$DB_PASSWORD" -D "$DB_NAME" -e "SHOW TABLES LIKE 'tabDocType';" 2>/dev/null | grep tabDocType || true)

if [ -z "$TABLE_EXISTS" ]; then
  echo "=========================================================="
  echo " Fresh database detected. Creating & initializing site: $SITE_NAME..."
  echo "=========================================================="
  bench new-site "$SITE_NAME" \
    --db-host "$DB_HOST" \
    --db-port "$DB_PORT" \
    --db-name "$DB_NAME" \
    --db-password "$DB_PASSWORD" \
    --admin-password "$ADMIN_PASSWORD" \
    --install-app applicant_processing \
    --no-mariadb-socket \
    --set-default \
    --force
else
  echo "=========================================================="
  echo " Existing database detected. Running migrations for: $SITE_NAME..."
  echo "=========================================================="
  mkdir -p "sites/$SITE_NAME"
  cat <<EOF > "sites/$SITE_NAME/site_config.json"
{
  "db_name": "${DB_NAME}",
  "db_password": "${DB_PASSWORD}",
  "db_type": "mariadb",
  "db_host": "${DB_HOST}",
  "db_port": ${DB_PORT},
  "db_user": "${DB_USER}"
}
EOF
  bench --site "$SITE_NAME" migrate || true
  bench --site "$SITE_NAME" install-app applicant_processing || true
  if [ -n "$ADMIN_PASSWORD" ]; then
    bench --site "$SITE_NAME" set-admin-password "$ADMIN_PASSWORD" || true
  fi
fi

# Link any detected domain alias to the site folder
if [ -n "$DETECTED_DOMAIN" ] && [ "$DETECTED_DOMAIN" != "$SITE_NAME" ]; then
  echo "Creating symlink alias from $DETECTED_DOMAIN to $SITE_NAME..."
  ln -sfn "$SITE_NAME" "sites/$DETECTED_DOMAIN" || true
fi

echo "$SITE_NAME" > sites/currentsite.txt

echo "=========================================================="
echo " Starting production web server on 0.0.0.0:$PORT..."
echo "=========================================================="

exec ./env/bin/gunicorn \
  --bind "0.0.0.0:${PORT}" \
  --workers 2 \
  --threads 4 \
  --timeout 120 \
  --worker-class gthread \
  --chdir /home/frappe/frappe-bench/sites \
  frappe.app:application
