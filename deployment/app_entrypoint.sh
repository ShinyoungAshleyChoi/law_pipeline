#!/bin/bash

# Application Entrypoint for Blue-Green Deployment

set -e

echo "Starting Legal Data Pipeline Application - Environment: ${ENVIRONMENT:-unknown}"

# Wait for database to be ready
echo "Waiting for database connection..."
while ! mysqladmin ping -h"${DB_HOST}" -P"${DB_PORT}" -u"${DB_USER}" -p"${DB_PASSWORD}" --silent; do
    echo "Database is unavailable - sleeping"
    sleep 2
done
echo "Database is up - continuing"

# Wait for Redis to be ready
echo "Waiting for Redis connection..."
while ! redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" ping > /dev/null 2>&1; do
    echo "Redis is unavailable - sleeping"
    sleep 2
done
echo "Redis is up - continuing"

# Run database migrations if needed
echo "Checking database schema..."
uv run python -c "
import sys
sys.path.insert(0, '/app/src')
from database.connection import DatabaseConnectionManager

try:
    db_manager = DatabaseConnectionManager()
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SHOW TABLES')
        tables = cursor.fetchall()
        print(f'Found {len(tables)} tables in database')
        cursor.close()
except Exception as e:
    print(f'Database check failed: {e}')
    sys.exit(1)
"

# Set up logging and Python path
export PYTHONPATH="/app/src:${PYTHONPATH}"

# Start the application with UV
echo "Starting application server..."
exec uv run uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --log-level info \
    --access-log \
    --loop asyncio
