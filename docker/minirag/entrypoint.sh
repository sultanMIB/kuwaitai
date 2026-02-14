#!/bin/bash
set -e

echo "Using DATABASE_URL for SQLAlchemy:"
echo "$DATABASE_URL"

# -------------------------------
# 1) إعداد URLs
# -------------------------------
# URL المستخدم بواسطة SQLAlchemy + asyncpg
export DATABASE_URL="postgresql+asyncpg://${POSTGRES_USERNAME}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_MAIN_DATABASE}"

# URL المستخدم بواسطة psql CLI
PSQL_URL="postgresql://${POSTGRES_USERNAME}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_MAIN_DATABASE}"

echo "Running database migrations..."
echo "Ensuring 'vector' extension exists..."

# -------------------------------
# 2) انتظر لحد ما Postgres يفتح Port 5432
# -------------------------------
until pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USERNAME"; do
    echo "Waiting for Postgres to start..."
    sleep 1
done

# -------------------------------
# 3) إنشاء امتداد vector لو مش موجود
# -------------------------------
psql "$PSQL_URL" -c "DO \$\$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        CREATE EXTENSION vector;
    END IF;
END \$\$;"

echo "Vector extension ensured."

# -------------------------------
# 4) Alembic migrations
# -------------------------------
cd /app/models/db_schems/kwituni/
alembic upgrade head
cd /app

echo "Migrations completed."

# -------------------------------
# 5) تشغيل السيرفر
# -------------------------------
echo "Starting FastAPI server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
