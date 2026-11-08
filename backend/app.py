"""FastAPI service for the new role-based police operations workspace."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import hmac
import os
import re
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from starlette.middleware.sessions import SessionMiddleware

from backend.offline_queue import OfflineCommandQueue

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
DATABASE_URL = os.getenv("NEON_ADMIN_DATABASE_URL") or os.getenv("DATABASE_URL")
OFFLINE_QUEUE_KEY = os.getenv("OFFLINE_QUEUE_KEY", "")
OFFLINE_QUEUE = OfflineCommandQueue(ROOT / "data" / "offline_commands.sqlite3", OFFLINE_QUEUE_KEY)
logger = logging.getLogger("police_app")
INITIAL_ANALYST_EMAIL = os.getenv("INITIAL_ANALYST_EMAIL", "").strip().lower()
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
if len(SESSION_SECRET) < 32:
    raise RuntimeError("Set a random SESSION_SECRET of at least 32 characters in .env.")

ROLES = {
    "data_analyst": "مسؤول قواعد البيانات",
    "police_commander": "قائد الشرطة",
    "officer": "ضابط",
    "mayor": "العمدة",
}
ASSIGNABLE_ROLES = {"police_commander", "officer", "mayor"}
SQL_DATABASE_ROLES = {
    "officer": "police_app_officer_sql",
    "police_commander": "police_app_commander_sql",
    "data_analyst": "police_app_analyst_sql",
    "mayor": "police_app_mayor_sql",
}
ROLE_DETAILS = {
    "data_analyst": {"description": "إدارة كاملة لبيانات العمليات والصلاحيات.", "capabilities": ["قراءة وتعديل وحذف بيانات العمليات", "إنشاء وتعديل الجداول التشغيلية", "إدارة أدوار الموظفين", "مراجعة التعديلات المتصاعدة", "متابعة سجل الأوامر"]},
    "police_commander": {"description": "تدقيق البيانات ومراجعة التقارير وطلبات الفريق.", "capabilities": ["قراءة جميع السجلات", "التحقق من صحة السجلات والرسوم", "تحديث حالة العملية", "توجيه طلبات العمدة", "استعلامات SQL للقراءة"]},
    "officer": {"description": "قراءة السجلات والتمثيل البياني مع إدخال وتعديل مقيّد.", "capabilities": ["قراءة السجلات المسندة إليه", "إنشاء رسوم بيانية للمراجعة", "إضافة سجل جديد", "تعديل حقول محدودة", "تصعيد التعديلات السابقة للمحلل"]},
    "mayor": {"description": "الاطلاع على العمليات المعتمدة وتنفيذ تمارين SQL على اللقطة التدريبية الاصطناعية.", "capabilities": ["عرض واستعلام العمليات المعتمدة فقط", "تنفيذ تمارين التحليل على بيانات التدريب الاصطناعية", "طلب بيانات من قائد الشرطة"]},
}


def sync_database_role(connection, user_id: int, app_role: str, db_user: str | None = None):
    """Give each account a non-login DB role so row policies bind to current_user."""
    db_user = db_user or connection.execute("SELECT current_user").fetchone()["current_user"]
    account_role = f"police_app_user_{int(user_id)}"
    exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (account_role,)).fetchone()
    if not exists:
        connection.execute(sql.SQL("CREATE ROLE {} NOLOGIN INHERIT").format(sql.Identifier(account_role)))
    for database_role in SQL_DATABASE_ROLES.values():
        connection.execute(sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(database_role), sql.Identifier(account_role)))
    if app_role in SQL_DATABASE_ROLES:
        connection.execute(
            sql.SQL("GRANT {} TO {}").format(sql.Identifier(SQL_DATABASE_ROLES[app_role]), sql.Identifier(account_role))
        )
    connection.execute(
        sql.SQL("GRANT {} TO {}").format(sql.Identifier(account_role), sql.Identifier(db_user))
    )


def db():
    if not DATABASE_URL:
        raise RuntimeError("Set NEON_ADMIN_DATABASE_URL in the local .env file.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=15)


def initialize_database():
    with db() as connection:
        db_user = connection.execute("SELECT current_user").fetchone()["current_user"]
        analyst_db_role = SQL_DATABASE_ROLES["data_analyst"]
        for role_name in SQL_DATABASE_ROLES.values():
            exists = connection.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role_name,)).fetchone()
            if not exists:
                connection.execute(sql.SQL("CREATE ROLE {} NOLOGIN").format(sql.Identifier(role_name)))
            connection.execute(sql.SQL("GRANT {} TO {}").format(sql.Identifier(role_name), sql.Identifier(db_user)))

        connection.execute("CREATE SCHEMA IF NOT EXISTS app_private")
        connection.execute("CREATE SCHEMA IF NOT EXISTS operations")
        connection.execute("CREATE SCHEMA IF NOT EXISTS analyst_workspace")
        connection.execute("CREATE SCHEMA IF NOT EXISTS spatial_lab")
        connection.execute("""
            DO $$ BEGIN
                IF to_regclass('public.app_users') IS NOT NULL AND to_regclass('app_private.app_users') IS NULL THEN
                    ALTER TABLE public.app_users SET SCHEMA app_private;
                END IF;
                IF to_regclass('public.role_change_log') IS NOT NULL AND to_regclass('app_private.role_change_log') IS NULL THEN
                    ALTER TABLE public.role_change_log SET SCHEMA app_private;
                END IF;
                IF to_regclass('public.operation_records') IS NOT NULL AND to_regclass('operations.operation_records') IS NULL THEN
                    ALTER TABLE public.operation_records SET SCHEMA operations;
                END IF;
            END $$
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.app_users (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'officer'
                    CHECK (role IN ('data_analyst','police_commander','officer','mayor')),
                active BOOLEAN NOT NULL DEFAULT TRUE,
                must_change_password BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.execute("ALTER TABLE app_private.app_users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'officer'")
        connection.execute("ALTER TABLE app_private.app_users ADD COLUMN IF NOT EXISTS active BOOLEAN NOT NULL DEFAULT TRUE")
        connection.execute("ALTER TABLE app_private.app_users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS operations.operation_records (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                region TEXT NOT NULL,
                priority TEXT NOT NULL DEFAULT 'عادي' CHECK (priority IN ('منخفض','عادي','مرتفع','عاجل')),
                status TEXT NOT NULL DEFAULT 'قيد المتابعة' CHECK (status IN ('قيد المتابعة','جارٍ التنفيذ','مكتملة')),
                response_minutes INTEGER CHECK (response_minutes IS NULL OR response_minutes >= 0),
                occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                created_by BIGINT NOT NULL REFERENCES app_private.app_users(id)
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.account_creation_log (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                created_by BIGINT NOT NULL REFERENCES app_private.app_users(id),
                target_user_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                assigned_role TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.role_change_log (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                changed_by BIGINT NOT NULL REFERENCES app_private.app_users(id),
                target_user_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                previous_role TEXT NOT NULL,
                new_role TEXT NOT NULL,
                changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS version BIGINT NOT NULL DEFAULT 0")
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS modified_count INTEGER NOT NULL DEFAULT 0")
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS validation_state TEXT NOT NULL DEFAULT 'pending'")
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS validation_note TEXT")
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS validated_by BIGINT REFERENCES app_private.app_users(id)")
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ")
        connection.execute("ALTER TABLE operations.operation_records ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.operation_change_log (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                operation_id BIGINT NOT NULL REFERENCES operations.operation_records(id),
                actor_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                action TEXT NOT NULL,
                before_values JSONB NOT NULL DEFAULT '{}'::jsonb,
                after_values JSONB NOT NULL DEFAULT '{}'::jsonb,
                note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.operation_change_requests (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                command_id UUID UNIQUE,
                operation_id BIGINT NOT NULL REFERENCES operations.operation_records(id),
                requested_by BIGINT NOT NULL REFERENCES app_private.app_users(id),
                expected_version BIGINT NOT NULL,
                changes JSONB NOT NULL,
                before_values JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_analyst',
                review_note TEXT,
                reviewed_by BIGINT REFERENCES app_private.app_users(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.data_requests (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                command_id UUID UNIQUE,
                requester_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                title TEXT NOT NULL,
                question TEXT NOT NULL,
                complexity TEXT NOT NULL CHECK (complexity IN ('standard','advanced')),
                status TEXT NOT NULL DEFAULT 'pending_commander',
                routed_to TEXT,
                routed_by BIGINT REFERENCES app_private.app_users(id),
                result_text TEXT,
                result_data JSONB,
                submitted_by BIGINT REFERENCES app_private.app_users(id),
                reviewed_by BIGINT REFERENCES app_private.app_users(id),
                review_note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.data_request_events (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                request_id BIGINT NOT NULL REFERENCES app_private.data_requests(id),
                actor_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                action TEXT NOT NULL,
                note TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.visual_reports (
                id BIGINT GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
                author_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                title TEXT NOT NULL,
                chart_type TEXT NOT NULL CHECK (chart_type IN ('bar','line')),
                label_column TEXT NOT NULL,
                value_column TEXT NOT NULL,
                source_sql TEXT NOT NULL,
                chart_data JSONB NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending_commander',
                review_note TEXT,
                reviewed_by BIGINT REFERENCES app_private.app_users(id),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reviewed_at TIMESTAMPTZ
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS app_private.sql_command_log (
                command_id UUID PRIMARY KEY,
                actor_id BIGINT NOT NULL REFERENCES app_private.app_users(id),
                statement_hash TEXT NOT NULL,
                statement TEXT NOT NULL DEFAULT '',
                result JSONB NOT NULL,
                executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        connection.execute("ALTER TABLE app_private.sql_command_log ADD COLUMN IF NOT EXISTS statement TEXT NOT NULL DEFAULT ''")
        if INITIAL_ANALYST_EMAIL:
            connection.execute(
                "UPDATE app_private.app_users SET role='officer' WHERE role='data_analyst' AND lower(email)<>%s",
                (INITIAL_ANALYST_EMAIL,),
            )
            connection.execute(
                "UPDATE app_private.app_users SET role='data_analyst' WHERE lower(email)=%s",
                (INITIAL_ANALYST_EMAIL,),
            )
        connection.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS app_users_single_data_analyst
            ON app_private.app_users (role) WHERE role='data_analyst'
        """)
        connection.execute("REVOKE ALL ON SCHEMA app_private FROM PUBLIC")
        connection.execute("REVOKE ALL ON ALL TABLES IN SCHEMA app_private FROM PUBLIC")
        connection.execute("REVOKE ALL ON SCHEMA app_private FROM police_app_officer_sql, police_app_commander_sql, police_app_analyst_sql")

        for account in connection.execute("SELECT id,role FROM app_private.app_users").fetchall():
            sync_database_role(connection, account["id"], account["role"], db_user)

        has_training_schema = connection.execute("SELECT to_regnamespace('training') IS NOT NULL AS exists").fetchone()['exists']
        if has_training_schema:
            schema_owner = connection.execute("SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname='training'").fetchone()['owner']
            if schema_owner != analyst_db_role:
                connection.execute(sql.SQL("ALTER SCHEMA training OWNER TO {}").format(sql.Identifier(analyst_db_role)))
            for table in connection.execute("""
                SELECT c.relname,pg_get_userbyid(c.relowner) AS owner
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='training' AND c.relkind IN ('r','p')
            """).fetchall():
                if table["owner"] != analyst_db_role:
                    connection.execute(sql.SQL("ALTER TABLE training.{} OWNER TO {}").format(sql.Identifier(table["relname"]),sql.Identifier(analyst_db_role)))
            for view in connection.execute("""
                SELECT c.relname,c.relkind,pg_get_userbyid(c.relowner) AS owner
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='training' AND c.relkind IN ('v','m')
            """).fetchall():
                if view["owner"] != analyst_db_role:
                    statement = "ALTER VIEW" if view["relkind"] == "v" else "ALTER MATERIALIZED VIEW"
                    connection.execute(sql.SQL("{} training.{} OWNER TO {}").format(sql.SQL(statement),sql.Identifier(view["relname"]),sql.Identifier(analyst_db_role)))
            for sequence in connection.execute("""
                SELECT c.relname,pg_get_userbyid(c.relowner) AS owner
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname='training' AND c.relkind='S'
            """).fetchall():
                if sequence["owner"] != analyst_db_role:
                    connection.execute(sql.SQL("ALTER SEQUENCE training.{} OWNER TO {}").format(sql.Identifier(sequence["relname"]),sql.Identifier(analyst_db_role)))

        for schema in ("operations", "analyst_workspace", "spatial_lab"):
            owner = connection.execute("SELECT pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname=%s", (schema,)).fetchone()['owner']
            if owner != analyst_db_role:
                connection.execute(sql.SQL("ALTER SCHEMA {} OWNER TO {}").format(sql.Identifier(schema),sql.Identifier(analyst_db_role)))
        table_owner = connection.execute("""
            SELECT pg_get_userbyid(c.relowner) AS owner FROM pg_class c
            WHERE c.oid='operations.operation_records'::regclass
        """).fetchone()["owner"]
        if table_owner != analyst_db_role:
            connection.execute(sql.SQL("ALTER TABLE operations.operation_records OWNER TO {}").format(sql.Identifier(analyst_db_role)))
        sequence_owner = connection.execute("""
            SELECT pg_get_userbyid(c.relowner) AS owner FROM pg_class c
            WHERE c.oid='operations.operation_records_id_seq'::regclass
        """).fetchone()["owner"]
        if sequence_owner != analyst_db_role:
            connection.execute(sql.SQL("ALTER SEQUENCE operations.operation_records_id_seq OWNER TO {}").format(sql.Identifier(analyst_db_role)))

        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(analyst_db_role)))
        connection.execute("""
            CREATE TABLE IF NOT EXISTS spatial_lab.demo_zones (
                zone TEXT PRIMARY KEY,
                geom geometry(Polygon,4326) NOT NULL
            )
        """)
        connection.execute("""
            INSERT INTO spatial_lab.demo_zones(zone,geom) VALUES
                ('A',ST_MakeEnvelope(-87.70,41.80,-87.65,41.85,4326)),
                ('B',ST_MakeEnvelope(-87.65,41.80,-87.60,41.85,4326))
            ON CONFLICT(zone) DO UPDATE SET geom=EXCLUDED.geom
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS spatial_lab.demo_points (
                id INTEGER PRIMARY KEY,
                geom geometry(Point,4326)
            )
        """)
        connection.execute("""
            INSERT INTO spatial_lab.demo_points(id,geom) VALUES
                (1,ST_SetSRID(ST_MakePoint(-87.68,41.82),4326)),
                (2,ST_SetSRID(ST_MakePoint(-87.65,41.82),4326)),
                (3,ST_SetSRID(ST_MakePoint(-87.55,41.90),4326)),
                (4,NULL)
            ON CONFLICT(id) DO UPDATE SET geom=EXCLUDED.geom
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS spatial_lab.distance_demo (
                id INTEGER PRIMARY KEY,
                geom geometry(Point,4326) NOT NULL
            )
        """)
        connection.execute("""
            INSERT INTO spatial_lab.distance_demo(id,geom) VALUES
                (1,ST_SetSRID(ST_MakePoint(-87.65,41.82),4326)),
                (2,ST_SetSRID(ST_MakePoint(-87.65,41.821),4326)),
                (3,ST_SetSRID(ST_MakePoint(-87.65,41.84),4326))
            ON CONFLICT(id) DO UPDATE SET geom=EXCLUDED.geom
        """)
        if has_training_schema:
            connection.execute("""
                CREATE OR REPLACE VIEW spatial_lab.spatial_crashes AS
                SELECT crash_record_id,geom,geom::geography AS geog
                FROM training.crashes WHERE geom IS NOT NULL
            """)
            connection.execute("""
                CREATE OR REPLACE VIEW spatial_lab.assigned_crime AS
                SELECT c.id,c.date,z.dist_num
                FROM training.crimes AS c
                LEFT JOIN LATERAL (
                    SELECT d.dist_num FROM training.districts AS d
                    WHERE ST_Covers(d.geom,c.geom)
                    ORDER BY d.dist_num LIMIT 1
                ) AS z ON TRUE
                WHERE c.date >= TIMESTAMP '2025-01-01' AND c.date < TIMESTAMP '2026-01-01'
            """)
            connection.execute("""
                CREATE OR REPLACE VIEW spatial_lab.assigned_traffic AS
                SELECT c.crash_record_id,c.crash_date,c.injuries_total,z.dist_num
                FROM training.crashes AS c
                LEFT JOIN LATERAL (
                    SELECT d.dist_num FROM training.districts AS d
                    WHERE ST_Covers(d.geom,c.geom)
                    ORDER BY d.dist_num LIMIT 1
                ) AS z ON TRUE
                WHERE c.crash_date >= TIMESTAMP '2025-01-01' AND c.crash_date < TIMESTAMP '2026-01-01'
            """)
            connection.execute("""
                CREATE OR REPLACE VIEW spatial_lab.integrated_report AS
                WITH calendar AS (
                    SELECT d.dist_num,m.month::date AS month
                    FROM training.districts AS d
                    CROSS JOIN generate_series(
                        TIMESTAMP '2025-01-01',TIMESTAMP '2025-12-01',INTERVAL '1 month'
                    ) AS m(month)
                ), crime_monthly AS (
                    SELECT dist_num,date_trunc('month',date)::date AS month,COUNT(*)::bigint AS crime_records
                    FROM spatial_lab.assigned_crime
                    WHERE dist_num IS NOT NULL
                    GROUP BY dist_num,date_trunc('month',date)::date
                ), traffic_monthly AS (
                    SELECT dist_num,date_trunc('month',crash_date)::date AS month,
                           COUNT(*)::bigint AS crash_records,
                           COUNT(injuries_total)::bigint AS observed_injuries,
                           SUM(injuries_total)::bigint AS injuries
                    FROM spatial_lab.assigned_traffic
                    WHERE dist_num IS NOT NULL
                    GROUP BY dist_num,date_trunc('month',crash_date)::date
                )
                SELECT c.dist_num,c.month,
                       COALESCE(cr.crime_records,0)::bigint AS crime_records,
                       COALESCE(tr.crash_records,0)::bigint AS crash_records,
                       COALESCE(tr.observed_injuries,0)::bigint AS observed_injuries,
                       tr.injuries
                FROM calendar AS c
                LEFT JOIN crime_monthly AS cr USING(dist_num,month)
                LEFT JOIN traffic_monthly AS tr USING(dist_num,month)
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS training_crashes_geography_lab_gist
                ON training.crashes USING GIST ((geom::geography))
            """)
        connection.execute("ALTER DEFAULT PRIVILEGES IN SCHEMA spatial_lab GRANT SELECT ON TABLES TO police_app_officer_sql, police_app_commander_sql, police_app_mayor_sql")
        if has_training_schema:
            connection.execute("GRANT USAGE ON SCHEMA training TO police_app_officer_sql, police_app_commander_sql, police_app_analyst_sql, police_app_mayor_sql")
            connection.execute("GRANT SELECT ON ALL TABLES IN SCHEMA training TO police_app_officer_sql, police_app_commander_sql")
            connection.execute("GRANT SELECT ON training.crimes,training.crashes,training.districts,training.provenance TO police_app_mayor_sql")
            connection.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA training TO police_app_analyst_sql")
            connection.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA training TO police_app_analyst_sql")
            connection.execute("GRANT USAGE, CREATE ON SCHEMA training TO police_app_analyst_sql")
        for role_name in SQL_DATABASE_ROLES.values():
            connection.execute(sql.SQL("GRANT USAGE ON SCHEMA operations TO {}").format(sql.Identifier(role_name)))
        connection.execute("GRANT SELECT ON operations.operation_records TO police_app_officer_sql, police_app_commander_sql, police_app_mayor_sql")
        connection.execute("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA operations TO police_app_analyst_sql")
        connection.execute("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA operations TO police_app_analyst_sql")
        connection.execute("GRANT USAGE, CREATE ON SCHEMA operations, analyst_workspace, spatial_lab TO police_app_analyst_sql")
        connection.execute("GRANT USAGE ON SCHEMA spatial_lab TO police_app_officer_sql, police_app_commander_sql, police_app_mayor_sql")
        connection.execute("GRANT SELECT ON ALL TABLES IN SCHEMA spatial_lab TO police_app_officer_sql, police_app_commander_sql, police_app_mayor_sql")
        connection.execute(sql.SQL("GRANT ALL ON SCHEMA operations, analyst_workspace TO {}").format(sql.Identifier(db_user)))
        connection.execute(sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA operations TO {}").format(sql.Identifier(db_user)))
        connection.execute(sql.SQL("GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA operations TO {}").format(sql.Identifier(db_user)))
        connection.execute("DROP POLICY IF EXISTS police_officer_own_records ON operations.operation_records")
        connection.execute("DROP POLICY IF EXISTS police_commander_all_records ON operations.operation_records")
        connection.execute("DROP POLICY IF EXISTS police_analyst_all_records ON operations.operation_records")
        connection.execute("DROP POLICY IF EXISTS police_backend_service_access ON operations.operation_records")
        connection.execute("DROP POLICY IF EXISTS police_mayor_approved_records ON operations.operation_records")
        connection.execute("""
            CREATE POLICY police_officer_own_records ON operations.operation_records
            FOR SELECT TO police_app_officer_sql
            USING (
                current_user ~ '^police_app_user_[0-9]+$'
                AND created_by = SUBSTRING(current_user FROM '[0-9]+$')::BIGINT
            )
        """)
        connection.execute("""
            CREATE POLICY police_commander_all_records ON operations.operation_records
            FOR SELECT TO police_app_commander_sql USING (TRUE)
        """)
        connection.execute("""
            CREATE POLICY police_analyst_all_records ON operations.operation_records
            FOR ALL TO police_app_analyst_sql USING (TRUE) WITH CHECK (TRUE)
        """)
        connection.execute("""
            CREATE POLICY police_mayor_approved_records ON operations.operation_records
            FOR SELECT TO police_app_mayor_sql USING (validation_state='approved')
        """)
        connection.execute(sql.SQL("""
            CREATE POLICY police_backend_service_access ON operations.operation_records
            FOR ALL TO {} USING (TRUE) WITH CHECK (TRUE)
        """).format(sql.Identifier(db_user)))



@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await asyncio.to_thread(initialize_database)
    except psycopg.OperationalError:
        logger.warning("Neon is unavailable at startup; offline SQL queue remains active.")
    worker = asyncio.create_task(replay_offline_commands())
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


app = FastAPI(title="مرصد العمليات API", version="0.1.0", lifespan=lifespan)
origins = [x.strip() for x in os.getenv("FRONTEND_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"], allow_headers=["Content-Type"])
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)


def password_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return salt.hex() + ":" + digest.hex()


def verify_password(password: str, saved: str) -> bool:
    try:
        salt_hex, digest_hex = saved.split(":", 1)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 600_000).hex()
        return hmac.compare_digest(candidate, digest_hex)
    except (ValueError, TypeError):
        return False


def current_user(request: Request):
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "سجّل الدخول للمتابعة")
    try:
        with db() as connection:
            user = connection.execute(
                "SELECT id,email,name,role,active,must_change_password FROM app_private.app_users WHERE id=%s", (user_id,)
            ).fetchone()
    except psycopg.OperationalError:
        snapshot = request.session.get("user_snapshot")
        if snapshot and snapshot.get("id") == user_id and snapshot.get("role") in ROLES:
            if snapshot.get("must_change_password") and request.url.path not in {"/api/auth/me", "/api/account/change-password"}:
                raise HTTPException(403, "غيّر كلمة المرور الأولية قبل استخدام النظام")
            return {**snapshot, "active": True, "offline_snapshot": True}
        raise HTTPException(503, "قاعدة البيانات غير متاحة؛ سجّل الدخول مجددًا بعد عودة الاتصال") from None
    if not user or not user["active"]:
        request.session.clear()
        raise HTTPException(401, "الحساب غير متاح أو انتهت الجلسة")
    if user["must_change_password"] and request.url.path not in {"/api/auth/me", "/api/account/change-password"}:
        raise HTTPException(403, "غيّر كلمة المرور الأولية قبل استخدام النظام")
    return dict(user)


def require_roles(*roles: str):
    def dependency(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(403, "ليس لديك صلاحية لتنفيذ هذا الإجراء")
        return user
    return dependency


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)
    name: str = Field(default="", max_length=120)


class RoleChange(BaseModel):
    role: Literal["police_commander", "officer", "mayor"]


class EmployeeCreate(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    name: str = Field(min_length=2, max_length=120)
    role: Literal["police_commander", "officer", "mayor"]
    temporary_password: str = Field(min_length=12, max_length=256)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class OperationCreate(BaseModel):
    title: str = Field(min_length=2, max_length=180)
    category: str = Field(min_length=2, max_length=80)
    region: str = Field(min_length=2, max_length=80)
    priority: Literal["منخفض", "عادي", "مرتفع", "عاجل"] = "عادي"


class OperationStatus(BaseModel):
    status: Literal["قيد المتابعة", "جارٍ التنفيذ", "مكتملة"]


class OperationPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=180)
    category: str | None = Field(default=None, min_length=2, max_length=80)
    region: str | None = Field(default=None, min_length=2, max_length=80)
    priority: Literal["منخفض", "عادي", "مرتفع", "عاجل"] | None = None


class RecordValidation(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=1000)


class DataRequestCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    question: str = Field(min_length=5, max_length=3000)
    complexity: Literal["standard", "advanced"] = "standard"


class DataRequestRoute(BaseModel):
    target_role: Literal["officer", "data_analyst"]
    note: str = Field(default="", max_length=1000)


class DataRequestSubmit(BaseModel):
    result_text: str = Field(min_length=3, max_length=5000)
    result_data: list[dict] | None = Field(default=None, max_length=50)


class DataRequestReview(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=1000)


class ChartRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    statement: str = Field(min_length=1, max_length=20_000)
    label_column: str = Field(min_length=1, max_length=120)
    value_column: str = Field(min_length=1, max_length=120)
    chart_type: Literal["bar", "line"] = "bar"


class ChartReview(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=1000)


class ChangeReview(BaseModel):
    approved: bool
    note: str = Field(default="", max_length=1000)


class SQLStatement(BaseModel):
    command_id: UUID
    statement: str = Field(min_length=1, max_length=20_000)


class LabTaskRequest(BaseModel):
    task_id: str = Field(min_length=3, max_length=80)


@app.get("/api/health")
def health():
    return {"ok": True, "service": "مرصد العمليات API"}


@app.get("/api/auth/registration-status")
def registration_status():
    if not INITIAL_ANALYST_EMAIL:
        return {"allowed": False}
    try:
        with db() as connection:
            exists = connection.execute(
                "SELECT EXISTS(SELECT 1 FROM app_private.app_users WHERE role='data_analyst' OR lower(email)=%s) AS exists",
                (INITIAL_ANALYST_EMAIL,),
            ).fetchone()["exists"]
        return {"allowed": not exists, "email": INITIAL_ANALYST_EMAIL}
    except psycopg.OperationalError:
        return {"allowed": False}


@app.post("/api/auth/register")
def register(body: Credentials, request: Request):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "أدخل بريدًا إلكترونيًا صحيحًا")
    if not INITIAL_ANALYST_EMAIL or email != INITIAL_ANALYST_EMAIL:
        raise HTTPException(403, "ينشئ مسؤول قواعد البيانات حسابات الموظفين من صفحة الصلاحيات")
    name = body.name.strip() or email.split("@", 1)[0]
    try:
        with db() as connection:
            with connection.transaction():
                exists = connection.execute("SELECT 1 FROM app_private.app_users WHERE role='data_analyst' OR lower(email)=%s FOR UPDATE", (email,)).fetchone()
                if exists:
                    raise HTTPException(409, "حساب مسؤول قواعد البيانات موجود بالفعل؛ سجّل الدخول")
                user = connection.execute(
                    "INSERT INTO app_private.app_users(email,name,password_hash,role) VALUES(%s,%s,%s,'data_analyst') RETURNING id,email,name,role",
                    (email, name, password_hash(body.password)),
                ).fetchone()
            sync_database_role(connection, user["id"], user["role"])
    except psycopg.IntegrityError:
        raise HTTPException(409, "هذا البريد مسجل مسبقًا") from None
    request.session["user_id"] = user["id"]
    request.session["user_snapshot"] = {key: user[key] for key in ("id", "email", "name", "role")}
    return dict(user)


@app.post("/api/auth/login")
def login(body: Credentials, request: Request):
    email = body.email.strip().lower()
    with db() as connection:
        user = connection.execute("SELECT * FROM app_private.app_users WHERE lower(email)=%s", (email,)).fetchone()
    if not user or not user["active"] or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "البريد أو كلمة المرور غير صحيحة")
    request.session.clear()
    request.session["user_id"] = user["id"]
    request.session["user_snapshot"] = {key: user[key] for key in ("id", "email", "name", "role", "must_change_password")}
    return {"id": user["id"], "email": user["email"], "name": user["name"], "role": user["role"], "must_change_password": user["must_change_password"]}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return {key: user[key] for key in ("id", "email", "name", "role", "must_change_password")}


@app.post("/api/account/change-password")
def change_own_password(body: PasswordChange, request: Request, user=Depends(current_user)):
    with db() as connection:
        row = connection.execute("SELECT password_hash FROM app_private.app_users WHERE id=%s", (user["id"],)).fetchone()
        if not row or not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(400, "كلمة المرور الحالية غير صحيحة")
        connection.execute("UPDATE app_private.app_users SET password_hash=%s,must_change_password=FALSE WHERE id=%s", (password_hash(body.new_password), user["id"]))
    snapshot = request.session.get("user_snapshot", {key:user[key] for key in ("id","email","name","role")})
    snapshot["must_change_password"] = False
    request.session["user_snapshot"] = snapshot
    return {"ok": True, "must_change_password": False}


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/dashboard")
def dashboard(user=Depends(current_user)):
    filters = []
    params = []
    if user["role"] == "officer":
        filters.append("created_by=%s")
        params.append(user["id"])
    elif user["role"] == "mayor":
        filters.append("validation_state='approved'")
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with db() as connection:
        row = connection.execute(f"""
            SELECT COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status='قيد المتابعة') AS pending,
                   COUNT(*) FILTER (WHERE status='جارٍ التنفيذ') AS in_progress,
                   COUNT(*) FILTER (WHERE status='مكتملة') AS completed,
                   ROUND(AVG(response_minutes)::numeric,1) AS avg_response_minutes
            FROM operations.operation_records {where}
        """, tuple(params)).fetchone()
    return {**dict(row), "role": user["role"], "role_label": ROLES[user["role"]]}


@app.get("/api/operations")
def list_operations(user=Depends(current_user)):
    filters = []
    params = []
    if user["role"] == "officer":
        filters.append("o.created_by=%s")
        params.append(user["id"])
    elif user["role"] == "mayor":
        filters.append("o.validation_state='approved'")
    where = "WHERE " + " AND ".join(filters) if filters else ""
    with db() as connection:
        records = connection.execute(f"""
            SELECT o.id,o.title,o.category,o.region,o.priority,o.status,o.response_minutes,o.occurred_at,
                   o.version,o.modified_count,o.validation_state,o.validation_note,o.updated_at,
                   u.name AS created_by_name
            FROM operations.operation_records o JOIN app_private.app_users u ON u.id=o.created_by
            {where}
            ORDER BY o.occurred_at DESC,o.id DESC LIMIT 250
        """, tuple(params)).fetchall()
    return [dict(row) for row in records]


@app.post("/api/operations")
def create_operation(body: OperationCreate, user=Depends(require_roles("officer", "data_analyst"))):
    with db() as connection:
        row = connection.execute("""
            INSERT INTO operations.operation_records(title,category,region,priority,created_by)
            VALUES(%s,%s,%s,%s,%s)
            RETURNING id,title,category,region,priority,status,response_minutes,occurred_at,version,validation_state
        """, (body.title.strip(), body.category.strip(), body.region.strip(), body.priority, user["id"])).fetchone()
        connection.execute("""
            INSERT INTO app_private.operation_change_log(operation_id,actor_id,action,after_values)
            VALUES(%s,%s,'created',%s)
        """, (row["id"], user["id"], Jsonb({key: row[key] for key in ("title","category","region","priority","status")})))
    return dict(row)


@app.patch("/api/operations/{operation_id}/status")
def update_operation_status(operation_id: int, body: OperationStatus, user=Depends(require_roles("police_commander", "data_analyst"))):
    with db() as connection:
        with connection.transaction():
            before = connection.execute("SELECT status,version FROM operations.operation_records WHERE id=%s FOR UPDATE", (operation_id,)).fetchone()
            if not before:
                raise HTTPException(404, "العملية غير موجودة")
            row = connection.execute("""
                UPDATE operations.operation_records
                SET status=%s,version=version+1,updated_at=NOW(),validation_state='pending',validated_by=NULL,validated_at=NULL
                WHERE id=%s RETURNING id,status,version
            """, (body.status, operation_id)).fetchone()
            connection.execute("""
                INSERT INTO app_private.operation_change_log(operation_id,actor_id,action,before_values,after_values)
                VALUES(%s,%s,'status_updated',%s,%s)
            """, (operation_id,user["id"],Jsonb(dict(before)),Jsonb({"status":body.status})))
    return dict(row)


@app.post("/api/operations/{operation_id}/validation")
def validate_operation(operation_id: int, body: RecordValidation, user=Depends(require_roles("police_commander"))):
    state = "approved" if body.approved else "needs_correction"
    with db() as connection:
        row = connection.execute("""
            UPDATE operations.operation_records
            SET validation_state=%s,validation_note=%s,validated_by=%s,validated_at=NOW()
            WHERE id=%s RETURNING id,validation_state,validation_note,validated_at
        """, (state,body.note.strip(),user["id"],operation_id)).fetchone()
        if not row:
            raise HTTPException(404, "العملية غير موجودة")
        connection.execute("""
            INSERT INTO app_private.operation_change_log(operation_id,actor_id,action,after_values,note)
            VALUES(%s,%s,%s,%s,%s)
        """, (operation_id,user["id"],"commander_approved" if body.approved else "commander_returned",Jsonb({"validation_state":state}),body.note.strip()))
    return dict(row)


@app.patch("/api/operations/{operation_id}")
def patch_operation(operation_id: int, body: OperationPatch, user=Depends(require_roles("officer", "data_analyst"))):
    changes = {key:value.strip() if isinstance(value,str) else value for key,value in body.model_dump(exclude_unset=True).items() if value is not None}
    if not changes:
        raise HTTPException(400, "اختر حقلًا واحدًا على الأقل للتعديل")
    allowed = {"title","category","region","priority"}
    if not set(changes).issubset(allowed):
        raise HTTPException(400, "بعض الحقول غير قابلة للتعديل من هذا الدور")
    with db() as connection:
        with connection.transaction():
            row = connection.execute("""
                SELECT id,created_by,version,modified_count,title,category,region,priority
                FROM operations.operation_records WHERE id=%s FOR UPDATE
            """, (operation_id,)).fetchone()
            if not row:
                raise HTTPException(404, "العملية غير موجودة")
            if user["role"] == "officer" and row["created_by"] != user["id"]:
                raise HTTPException(403, "يمكنك تعديل السجلات التي أنشأتها فقط")
            before = {key:row[key] for key in changes}
            if user["role"] == "officer" and row["modified_count"] > 0:
                req = connection.execute("""
                    INSERT INTO app_private.operation_change_requests(operation_id,requested_by,expected_version,changes,before_values)
                    VALUES(%s,%s,%s,%s,%s) RETURNING id,status
                """, (operation_id,user["id"],row["version"],Jsonb(changes),Jsonb(before))).fetchone()
                connection.execute("""
                    INSERT INTO app_private.operation_change_log(operation_id,actor_id,action,before_values,after_values,note)
                    VALUES(%s,%s,'sent_to_analyst',%s,%s,%s)
                """, (operation_id,user["id"],Jsonb(before),Jsonb(changes),f"request:{req['id']}"))
                return {"id":operation_id,"request_id":req["id"],"status":"pending_analyst","message":"أُرسل التعديل لمسؤول قواعد البيانات للمراجعة"}
            assignments = sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(key)) for key in changes)
            values = [changes[key] for key in changes]
            updated = connection.execute(sql.SQL("""
                UPDATE operations.operation_records
                SET {},version=version+1,modified_count=modified_count+1,updated_at=NOW(),
                    validation_state='pending',validated_by=NULL,validated_at=NULL
                WHERE id=%s RETURNING id,version,modified_count,validation_state
            """).format(assignments), tuple(values+[operation_id])).fetchone()
            after = dict(changes)
            connection.execute("""
                INSERT INTO app_private.operation_change_log(operation_id,actor_id,action,before_values,after_values)
                VALUES(%s,%s,'limited_edit_applied',%s,%s)
            """, (operation_id,user["id"],Jsonb(before),Jsonb(after)))
    return dict(updated)


@app.post("/api/admin/users")
def create_employee(body: EmployeeCreate, user=Depends(require_roles("data_analyst"))):
    email = body.email.strip().lower()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(400, "أدخل بريدًا إلكترونيًا صحيحًا")
    name = body.name.strip()
    try:
        with db() as connection:
            with connection.transaction():
                created = connection.execute(
                    "INSERT INTO app_private.app_users(email,name,password_hash,role,must_change_password) VALUES(%s,%s,%s,%s,TRUE) RETURNING id,email,name,role,active,created_at,must_change_password",
                    (email, name, password_hash(body.temporary_password), body.role),
                ).fetchone()
                sync_database_role(connection, created["id"], created["role"])
                connection.execute(
                    "INSERT INTO app_private.account_creation_log(created_by,target_user_id,assigned_role) VALUES(%s,%s,%s)",
                    (user["id"], created["id"], body.role),
                )
    except psycopg.IntegrityError:
        raise HTTPException(409, "يوجد حساب مسجل بهذا البريد") from None
    return {**dict(created), "role_label": ROLES[body.role], "permissions": ROLE_DETAILS[body.role]["capabilities"]}


@app.get("/api/admin/users")
def list_users(user=Depends(require_roles("data_analyst"))):
    with db() as connection:
        users = connection.execute("""
            SELECT id,email,name,role,active,created_at,must_change_password FROM app_private.app_users ORDER BY created_at,id
        """).fetchall()
    return [{**dict(row), "role_label": ROLES[row["role"]], "permissions": ROLE_DETAILS[row["role"]]["capabilities"]} for row in users]


@app.get("/api/admin/access-model")
def access_model(user=Depends(require_roles("data_analyst"))):
    return [{"role": role, "label": ROLES[role], **details} for role, details in ROLE_DETAILS.items()]


@app.get("/api/admin/role-history")
def role_history(user=Depends(require_roles("data_analyst"))):
    with db() as connection:
        entries = connection.execute("""
            SELECT h.id,h.previous_role,h.new_role,h.changed_at,
                   actor.name AS actor_name,target.name AS target_name,target.email AS target_email
            FROM app_private.role_change_log h
            JOIN app_private.app_users actor ON actor.id=h.changed_by
            JOIN app_private.app_users target ON target.id=h.target_user_id
            ORDER BY h.changed_at DESC,h.id DESC LIMIT 100
        """).fetchall()
    return [{**dict(row), "previous_role_label": ROLES[row["previous_role"]], "new_role_label": ROLES[row["new_role"]]} for row in entries]


@app.get("/api/admin/account-history")
def account_creation_history(user=Depends(require_roles("data_analyst"))):
    with db() as connection:
        rows = connection.execute("""
            SELECT l.id,l.assigned_role,l.created_at,creator.name AS creator_name,
                   employee.name AS employee_name,employee.email AS employee_email
            FROM app_private.account_creation_log l
            JOIN app_private.app_users creator ON creator.id=l.created_by
            JOIN app_private.app_users employee ON employee.id=l.target_user_id
            ORDER BY l.created_at DESC,l.id DESC LIMIT 100
        """).fetchall()
    return [{**dict(row), "role_label": ROLES[row["assigned_role"]]} for row in rows]


@app.put("/api/admin/users/{target_id}/role")
def set_user_role(target_id: int, body: RoleChange, request: Request, user=Depends(require_roles("data_analyst"))):
    if target_id == user["id"]:
        raise HTTPException(400, "لا يمكن لمسؤول قواعد البيانات تغيير دوره من هذه الصفحة")
    with db() as connection:
        with connection.transaction():
            target = connection.execute("SELECT id,role FROM app_private.app_users WHERE id=%s FOR UPDATE", (target_id,)).fetchone()
            if not target:
                raise HTTPException(404, "الحساب غير موجود")
            old_role = target["role"]
            connection.execute("UPDATE app_private.app_users SET role=%s WHERE id=%s", (body.role, target_id))
            sync_database_role(connection, target_id, body.role)
            connection.execute("""
                INSERT INTO app_private.role_change_log(changed_by,target_user_id,previous_role,new_role)
                VALUES(%s,%s,%s,%s)
            """, (user["id"], target_id, old_role, body.role))
    return {"id": target_id, "previous_role": old_role, "role": body.role, "role_label": ROLES[body.role]}


@app.get("/api/admin/change-requests")
def list_change_requests(user=Depends(require_roles("data_analyst"))):
    with db() as connection:
        rows = connection.execute("""
            SELECT r.id,r.operation_id,r.requested_by,r.expected_version,r.changes,r.before_values,r.created_at,
                   u.name AS requested_by_name,o.title AS operation_title,o.version AS current_version
            FROM app_private.operation_change_requests r
            JOIN app_private.app_users u ON u.id=r.requested_by
            JOIN operations.operation_records o ON o.id=r.operation_id
            WHERE r.status='pending_analyst'
            ORDER BY r.created_at,r.id LIMIT 200
        """).fetchall()
    return [dict(row) for row in rows]


@app.put("/api/admin/change-requests/{request_id}")
def review_change_request(request_id: int, body: ChangeReview, user=Depends(require_roles("data_analyst"))):
    with db() as connection:
        with connection.transaction():
            request_row = connection.execute("""
                SELECT id,operation_id,requested_by,expected_version,changes,before_values,status
                FROM app_private.operation_change_requests WHERE id=%s FOR UPDATE
            """, (request_id,)).fetchone()
            if not request_row or request_row["status"] != "pending_analyst":
                raise HTTPException(404, "طلب التعديل غير موجود أو سبق مراجعته")
            operation = connection.execute("SELECT version FROM operations.operation_records WHERE id=%s FOR UPDATE", (request_row["operation_id"],)).fetchone()
            if not operation:
                raise HTTPException(404, "السجل المرتبط بالتعديل غير موجود")
            if body.approved and operation["version"] != request_row["expected_version"]:
                connection.execute("""
                    UPDATE app_private.operation_change_requests
                    SET status='conflict',review_note='تغير السجل بعد تقديم الطلب',reviewed_by=%s,reviewed_at=NOW()
                    WHERE id=%s
                """, (user["id"],request_id))
                return {"id":request_id,"status":"conflict","message":"تغير السجل منذ تقديم الطلب؛ راجع آخر نسخة قبل اعتماد التعديل."}
            status = "approved" if body.approved else "rejected"
            if body.approved:
                changes = dict(request_row["changes"])
                assignments = sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(key)) for key in changes)
                connection.execute(sql.SQL("""
                    UPDATE operations.operation_records
                    SET {},version=version+1,modified_count=modified_count+1,updated_at=NOW(),
                        validation_state='pending',validated_by=NULL,validated_at=NULL
                    WHERE id=%s
                """).format(assignments), tuple(list(changes.values())+[request_row["operation_id"]]))
                connection.execute("""
                    INSERT INTO app_private.operation_change_log(operation_id,actor_id,action,before_values,after_values,note)
                    VALUES(%s,%s,'analyst_approved_edit',%s,%s,%s)
                """, (request_row["operation_id"],user["id"],Jsonb(dict(request_row["before_values"])),Jsonb(changes),body.note.strip()))
            connection.execute("""
                UPDATE app_private.operation_change_requests
                SET status=%s,review_note=%s,reviewed_by=%s,reviewed_at=NOW() WHERE id=%s
            """, (status,body.note.strip(),user["id"],request_id))
    return {"id":request_id,"status":status}


def add_data_request_event(connection, request_id: int, actor_id: int, action: str, note: str = ""):
    connection.execute("""
        INSERT INTO app_private.data_request_events(request_id,actor_id,action,note)
        VALUES(%s,%s,%s,%s)
    """, (request_id,actor_id,action,note[:1000]))


@app.post("/api/data-requests")
def create_data_request(body: DataRequestCreate, user=Depends(require_roles("mayor"))):
    with db() as connection:
        with connection.transaction():
            row = connection.execute("""
                INSERT INTO app_private.data_requests(requester_id,title,question,complexity)
                VALUES(%s,%s,%s,%s) RETURNING id,status,created_at
            """, (user["id"],body.title.strip(),body.question.strip(),body.complexity)).fetchone()
            add_data_request_event(connection,row["id"],user["id"],"submitted",body.title.strip())
    return dict(row)


@app.get("/api/data-requests")
def list_data_requests(user=Depends(current_user)):
    if user["role"] == "mayor":
        condition,params="WHERE r.requester_id=%s",(user["id"],)
    elif user["role"] == "police_commander":
        condition,params="",()
    elif user["role"] == "officer":
        condition,params="WHERE r.routed_to='officer' AND r.status='routed_officer'",()
    else:
        condition,params="WHERE r.routed_to='data_analyst' AND r.status IN ('routed_analyst','pending_commander_review')",()
    with db() as connection:
        rows=connection.execute(f"""
            SELECT r.id,r.requester_id,r.title,r.question,r.complexity,r.status,r.routed_to,
                   r.result_text,r.result_data,r.created_at,r.updated_at,u.name AS requester_name
            FROM app_private.data_requests r JOIN app_private.app_users u ON u.id=r.requester_id
            {condition} ORDER BY r.created_at DESC,r.id DESC LIMIT 200
        """,params).fetchall()
    result=[]
    for row in rows:
        entry=dict(row)
        if user["role"]=="mayor" and entry["status"]!="completed":
            entry["result_text"]=None; entry["result_data"]=None
        result.append(entry)
    return result


@app.put("/api/data-requests/{request_id}/route")
def route_data_request(request_id: int, body: DataRequestRoute, user=Depends(require_roles("police_commander"))):
    if body.target_role=="officer":
        with db() as connection:
            request_row=connection.execute("SELECT id,complexity,status FROM app_private.data_requests WHERE id=%s FOR UPDATE",(request_id,)).fetchone()
            if not request_row or request_row["status"]!="pending_commander": raise HTTPException(404,"الطلب غير متاح للتوجيه")
            if request_row["complexity"]!="standard": raise HTTPException(403,"هذا الطلب يحتاج صلاحية محلل البيانات")
            connection.execute("UPDATE app_private.data_requests SET status='routed_officer',routed_to='officer',routed_by=%s,updated_at=NOW() WHERE id=%s",(user["id"],request_id))
            add_data_request_event(connection,request_id,user["id"],"routed_to_officer",body.note)
    else:
        with db() as connection:
            request_row=connection.execute("SELECT id,status FROM app_private.data_requests WHERE id=%s FOR UPDATE",(request_id,)).fetchone()
            if not request_row or request_row["status"] not in ("pending_commander","routed_officer"): raise HTTPException(404,"الطلب غير متاح للتوجيه")
            connection.execute("UPDATE app_private.data_requests SET status='routed_analyst',routed_to='data_analyst',routed_by=%s,updated_at=NOW() WHERE id=%s",(user["id"],request_id))
            add_data_request_event(connection,request_id,user["id"],"routed_to_analyst",body.note)
    return {"id":request_id,"status":"routed_"+body.target_role,"routed_to":body.target_role}


@app.post("/api/data-requests/{request_id}/escalate")
def escalate_data_request(request_id: int, body: DataRequestRoute, user=Depends(require_roles("officer"))):
    with db() as connection:
        with connection.transaction():
            request_row=connection.execute("SELECT id,status,routed_to FROM app_private.data_requests WHERE id=%s FOR UPDATE",(request_id,)).fetchone()
            if not request_row or request_row["status"]!="routed_officer" or request_row["routed_to"]!="officer": raise HTTPException(404,"الطلب غير متاح للضابط")
            connection.execute("UPDATE app_private.data_requests SET status='routed_analyst',routed_to='data_analyst',updated_at=NOW() WHERE id=%s",(request_id,))
            add_data_request_event(connection,request_id,user["id"],"escalated_to_analyst",body.note)
    return {"id":request_id,"status":"routed_analyst"}


@app.post("/api/data-requests/{request_id}/submit")
def submit_data_request(request_id: int, body: DataRequestSubmit, user=Depends(require_roles("officer","data_analyst"))):
    with db() as connection:
        with connection.transaction():
            request_row=connection.execute("SELECT id,status,routed_to FROM app_private.data_requests WHERE id=%s FOR UPDATE",(request_id,)).fetchone()
            expected_route="officer" if user["role"]=="officer" else "data_analyst"
            if not request_row or request_row["status"]!="routed_"+expected_route or request_row["routed_to"]!=expected_route: raise HTTPException(404,"الطلب غير موجه إلى حسابك")
            connection.execute("""
                UPDATE app_private.data_requests
                SET status='pending_commander_review',result_text=%s,result_data=%s,submitted_by=%s,updated_at=NOW()
                WHERE id=%s
            """,(body.result_text.strip(),Jsonb(body.result_data) if body.result_data is not None else None,user["id"],request_id))
            add_data_request_event(connection,request_id,user["id"],"submitted_for_commander_review",body.result_text[:300])
    return {"id":request_id,"status":"pending_commander_review"}


@app.put("/api/data-requests/{request_id}/review")
def review_data_request(request_id: int, body: DataRequestReview, user=Depends(require_roles("police_commander"))):
    status="completed" if body.approved else "rejected"
    with db() as connection:
        with connection.transaction():
            request_row=connection.execute("SELECT id,status FROM app_private.data_requests WHERE id=%s FOR UPDATE",(request_id,)).fetchone()
            if not request_row or request_row["status"]!="pending_commander_review": raise HTTPException(404,"الطلب غير جاهز للمراجعة")
            connection.execute("UPDATE app_private.data_requests SET status=%s,reviewed_by=%s,review_note=%s,updated_at=NOW() WHERE id=%s",(status,user["id"],body.note.strip(),request_id))
            add_data_request_event(connection,request_id,user["id"],"approved_for_mayor" if body.approved else "rejected",body.note)
    return {"id":request_id,"status":status}


def query_as_user(user: dict, statement: str, max_rows: int = 500):
    statement=validate_sql(statement,user["role"])
    first=re.match(r"\s*([A-Za-z]+)",statement)
    if not first or first.group(1).upper() not in {"SELECT","WITH","EXPLAIN"}:
        raise HTTPException(400,"الرسم يحتاج استعلام قراءة")
    with db() as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout='10s'")
            role=SQL_DATABASE_ROLES["data_analyst"] if user["role"]=="data_analyst" else f"police_app_user_{int(user['id'])}"
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            path="spatial_lab, operations, analyst_workspace, training, public" if user["role"]=="data_analyst" else "spatial_lab, operations, training, public"
            connection.execute("SELECT set_config('search_path',%s,TRUE)",(path,))
            cursor=connection.execute(statement)
            columns=[column.name for column in cursor.description] if cursor.description else []
            rows=cursor.fetchmany(max_rows+1) if columns else []
            truncated=len(rows)>max_rows
            rows=rows[:max_rows]
            output=[[None if row[column] is None else row[column] if isinstance(row[column],(str,int,float,bool)) else str(row[column]) for column in columns] for row in rows]
    return {"columns":columns,"rows":output,"affected_rows":len(output),"truncated":truncated,"connected":True,"database":connection_info["database_name"],"execution_role":SQL_DATABASE_ROLES[user["role"]]}


@app.post("/api/reports")
def create_visual_report(body: ChartRequest, user=Depends(require_roles("officer","data_analyst"))):
    data=query_as_user(user,body.statement,50)
    if data["truncated"]: raise HTTPException(400,"اختصر الاستعلام إلى ٥٠ فئة كحد أقصى")
    if body.label_column not in data["columns"] or body.value_column not in data["columns"]: raise HTTPException(400,"اختر أعمدة موجودة في نتيجة الاستعلام")
    label_index=data["columns"].index(body.label_column); value_index=data["columns"].index(body.value_column)
    chart=[]
    try:
        for row in data["rows"]:
            if row[label_index] is None or row[value_index] is None: continue
            chart.append({"label":str(row[label_index]),"value":float(row[value_index])})
    except (TypeError,ValueError):
        raise HTTPException(400,"عمود القيمة يجب أن يحتوي أرقامًا") from None
    if not chart: raise HTTPException(400,"الاستعلام لم يُرجع بيانات قابلة للرسم")
    with db() as connection:
        row=connection.execute("""
            INSERT INTO app_private.visual_reports(author_id,title,chart_type,label_column,value_column,source_sql,chart_data)
            VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id,status,created_at
        """,(user["id"],body.title.strip(),body.chart_type,body.label_column,body.value_column,body.statement,Jsonb(chart))).fetchone()
    return {**dict(row),"chart_data":chart}


@app.get("/api/reports")
def list_visual_reports(user=Depends(current_user)):
    if user["role"]=="mayor": condition,params="WHERE r.status='approved'",()
    elif user["role"]=="police_commander": condition,params="WHERE r.status='pending_commander'",()
    elif user["role"]=="officer": condition,params="WHERE r.author_id=%s",(user["id"],)
    else: condition,params="",()
    with db() as connection:
        rows=connection.execute(f"""
            SELECT r.id,r.author_id,r.title,r.chart_type,r.label_column,r.value_column,r.chart_data,r.status,r.review_note,r.created_at,
                   u.name AS author_name
            FROM app_private.visual_reports r JOIN app_private.app_users u ON u.id=r.author_id
            {condition} ORDER BY r.created_at DESC,r.id DESC LIMIT 200
        """,params).fetchall()
    return [dict(row) for row in rows]


@app.put("/api/reports/{report_id}/review")
def review_visual_report(report_id: int, body: ChartReview, user=Depends(require_roles("police_commander"))):
    status="approved" if body.approved else "rejected"
    with db() as connection:
        row=connection.execute("""
            UPDATE app_private.visual_reports SET status=%s,review_note=%s,reviewed_by=%s,reviewed_at=NOW()
            WHERE id=%s AND status='pending_commander' RETURNING id,status
        """,(status,body.note.strip(),user["id"],report_id)).fetchone()
    if not row: raise HTTPException(404,"التقرير غير موجود أو سبق تدقيقه")
    return dict(row)


def validate_sql(statement: str, role: str):
    statement = statement.strip()
    if not statement:
        raise HTTPException(400, "اكتب استعلام SQL أولًا")
    if statement.endswith(";"):
        statement = statement[:-1].rstrip()
    if ";" in statement:
        raise HTTPException(400, "نفّذ أمر SQL واحدًا في كل مرة")
    if "--" in statement or "/*" in statement or "*/" in statement:
        raise HTTPException(400, "التعليقات غير متاحة في محرر SQL")
    first = re.match(r"\s*([A-Za-z]+)", statement)
    keyword = first.group(1).upper() if first else ""
    blocked = {"BEGIN", "START", "COMMIT", "END", "ROLLBACK", "SAVEPOINT", "RELEASE", "SET", "RESET", "GRANT", "REVOKE", "DO", "CALL", "COPY", "LISTEN", "NOTIFY", "VACUUM", "DISCARD", "PREPARE", "EXECUTE"}
    if keyword in blocked or re.search(r"\bset_config\s*\(", statement, re.IGNORECASE):
        raise HTTPException(400, "هذا الأمر غير متاح من محرر الاستعلامات")
    if role != "data_analyst" and keyword not in {"SELECT", "WITH", "EXPLAIN"}:
        raise HTTPException(403, "هذا الدور يستطيع تشغيل استعلامات القراءة فقط")
    return statement


SPATIAL_LABS = [
    {
        "id": "point-zones",
        "title": "تعيين النقاط إلى المناطق وحدودها",
        "source": "02_point_to_zone_assignment_and_boundaries_student.ipynb",
        "rubric": "التقييم: صحة SQL 40، أدلة التحقق 25، التفسير 20، قابلية الإعادة وتقليل البيانات 15.",
        "tasks": [
            "E1: أعدّ معرّف النقطة والمنطقة باستخدام ST_Contains، ورتّب حسب المعرّف والمنطقة.",
            "E2: أعدّ معرّفات النقاط ذات الهندسة التي لا تغطيها أي منطقة، مرتبة حسب المعرّف.",
            "E3: أعدّ معرّفات النقاط التي تفتقد الهندسة، مرتبة حسب المعرّف.",
            "E4: غيّر قاعدة فضّ التعادل إلى اسم المنطقة الأبجدي الأخير، وأعدّ نقطة واحدة لكل نقطة من الأربع.",
            "المهمة اليومية: اعرض التعيين وتعداد التغطية واشرح سياسة الحدود، وميّز النقطة 3 خارج المناطق عن النقطة 4 ذات الإحداثيات المفقودة.",
            "التسليم: الاستعلامات الأربعة ونتائجها وشرح قصير يذكر مستوى الصفوف والدليل والقيود وخطأ واحدًا تم تشخيصه.",
        ],
    },
    {
        "id": "spatial-distance-grid",
        "title": "المسافات والفهارس المكانية وملخصات الشبكة",
        "source": "03_spatial_distances_indexes_and_grid_summaries_student.ipynb",
        "rubric": "التقييم: صحة SQL 40، أدلة التحقق 25، التفسير 20، قابلية الإعادة وتقليل البيانات 15.",
        "tasks": [
            "E1: أعدّ معرّفات النقاط ضمن 150 مترًا من النقطة المرجعية، مرتبة حسب المعرّف.",
            "E2: أعدّ معرّفات النقاط ضمن 50 مترًا من النقطة المرجعية، مرتبة حسب المعرّف.",
            "E3: احسب total_records بجمع كل أعداد خلايا الشبكة المسقطة ذات حجم كيلومتر واحد، من دون حدّ للنتائج.",
            "E4: أعدّ معرّفات سجلات الحوادث ضمن 5 كم، وقارنها بنتيجة ST_Distance على geography حتى 5000 متر.",
            "المهمة اليومية: قدّم استعلام قرب بوحدة المتر وشرح خطة تنفيذه ومطابقة مجموع الشبكة وملاحظة عن CRS والتغطية.",
            "التسليم: الاستعلامات الأربعة ونتائجها وشرح قصير يذكر مستوى الصفوف والدليل والقيود وخطأ واحدًا تم تشخيصه.",
        ],
    },
    {
        "id": "district-month-analytics",
        "title": "تحليل الجرائم والحوادث حسب المنطقة والشهر",
        "source": "02_district_month_analytics_team_project_student.ipynb",
        "rubric": "صحة SQL 40، التحقق والمطابقة 25، التفسير 20، قابلية الإعادة وتقليل البيانات 15.",
        "tasks": [
            "المهمة اليومية: جدول منطقة-شهر، تغطية المصدرين، ومطابقتان للمجاميع؛ اشرح قاعدة الحدود والأشهر الفارغة والفرق بين عدد قياسات الإصابات ومجموع الإصابات.",
            "التسليم: الاستعلامات الأربعة ونتائجها وشرح مستوى الصفوف والدليل والقيود وخطأ واحد تم تشخيصه.",
        ],
        "exercises": [
            {"id":"district-e1","title":"E1 · جميع صفوف المنطقة والشهر (48 صفًا)"},
            {"id":"district-e2","title":"E2 · تغطية الجرائم والحوادث مع إبقاء غير المطابق"},
            {"id":"district-e3","title":"E3 · إجمالي الجرائم السنوي لكل منطقة، بما فيها الصفر"},
            {"id":"district-e4","title":"E4 · عدد الحوادث، وعدد قياسات الإصابات، ومجموعها"},
        ],
    },
    {
        "id": "dashboard-handover",
        "title": "لوحة المؤشرات والتصدير وتسليم التقرير",
        "source": "03_dashboard_export_and_reporting_handover_student.ipynb",
        "rubric": "صحة SQL 40، التحقق والمطابقة 25، التفسير 20، قابلية الإعادة وتقليل البيانات 15.",
        "tasks": [
            "المهمة اليومية: جهّز CSV وملف provenance JSON وملخص تسليم مدته خمس دقائق يشرح مستوى الصفوف وبديلًا فاشلًا ونتيجة تحقق وقيدًا واحدًا.",
            "اشرح مقام متوسط الإصابات: عدد القياسات المعروفة، لا كل الحوادث؛ القيمة المفقودة ليست صفرًا.",
            "أرفق أدلة مطابقة مجموعات كل مصدر، ومجموع المعيّن وغير المعيّن، وعدد صفوف المنطقة-الشهر.",
        ],
        "exercises": [
            {"id":"dashboard-e1","title":"E1 · مجموع الجرائم والحوادث حسب الشهر (12 شهرًا)"},
            {"id":"dashboard-e2","title":"E2 · LAG للجرائم مع تقسيم مستقل لكل منطقة"},
            {"id":"dashboard-e3","title":"E3 · متوسط الإصابات المجمّع مع مقام القياسات المعروفة"},
            {"id":"dashboard-e4","title":"E4 · مقارنة غير المطابق بين المصدرين"},
        ],
    },
]


@app.get("/api/labs/tasks")
def list_spatial_lab_tasks(user=Depends(current_user)):
    return SPATIAL_LABS


@app.get("/api/sql-console/status")
def sql_console_status(user=Depends(current_user)):
    try:
        with db() as connection:
            account_role = f"police_app_user_{int(user['id'])}"
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(account_role)))
            row = connection.execute("SELECT current_database() AS database_name, current_user AS execution_role").fetchone()
        return {"enabled": True, "connected": True, "database": row["database_name"], "execution_role": row["execution_role"], "read_only": user["role"] != "data_analyst"}
    except psycopg.OperationalError:
        return {"enabled": True, "connected": False, "database": None, "execution_role": None, "read_only": user["role"] != "data_analyst"}


def run_sql_command(command_id: str, user: dict, statement: str):
    statement = validate_sql(statement, user["role"])
    digest = hashlib.sha256(statement.encode("utf-8")).hexdigest()
    columns: list[str] = []
    rows: list[list] = []
    truncated = False
    affected_rows = 0
    with db() as connection:
        with connection.transaction():
            if user["role"] == "data_analyst":
                previous = connection.execute(
                    "SELECT statement_hash,result FROM app_private.sql_command_log WHERE command_id=%s",
                    (command_id,),
                ).fetchone()
                if previous:
                    if previous["statement_hash"] != digest:
                        raise HTTPException(409, "معرّف الأمر مستخدم لاستعلام مختلف")
                    return dict(previous["result"])
            else:
                connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout='10s'")
            account_role = SQL_DATABASE_ROLES["data_analyst"] if user["role"] == "data_analyst" else f"police_app_user_{int(user['id'])}"
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(account_role)))
            if user["role"] == "data_analyst":
                search_path = "spatial_lab, operations, analyst_workspace, training, public"
            elif user["role"] == "mayor":
                search_path = "spatial_lab, training, operations, public"
            else:
                search_path = "spatial_lab, operations, training, public"
            connection.execute("SELECT set_config('search_path',%s,TRUE)", (search_path,))
            connection_info = connection.execute("SELECT current_database() AS database_name").fetchone()
            cursor = connection.execute(statement)
            columns = [column.name for column in cursor.description] if cursor.description else []
            records = cursor.fetchmany(501) if columns else []
            truncated = len(records) > 500
            records = records[:500]
            rows = [[None if record[column] is None else record[column] if isinstance(record[column], (str, int, float, bool)) else str(record[column]) for column in columns] for record in records]
            affected_rows = len(rows) if columns else max(cursor.rowcount, 0)
            result = {"columns": columns, "rows": rows, "affected_rows": affected_rows, "truncated": truncated, "connected": True, "database": connection_info["database_name"], "execution_role": SQL_DATABASE_ROLES[user["role"]]}
            if user["role"] == "data_analyst":
                connection.execute("RESET ROLE")
                connection.execute(
                    "INSERT INTO app_private.sql_command_log(command_id,actor_id,statement_hash,statement,result) VALUES(%s,%s,%s,%s,%s)",
                    (command_id, user["id"], digest, statement, Jsonb(result)),
                )
    return result


LAB_TASK_SQL = {
    "district-e1": """SELECT dist_num,month,crime_records,crash_records FROM spatial_lab.integrated_report ORDER BY dist_num,month""",
    "district-e2": """SELECT source,total,assigned,unmatched FROM (
        SELECT 'crime'::text AS source,COUNT(*)::bigint AS total,COUNT(dist_num)::bigint AS assigned,COUNT(*) FILTER (WHERE dist_num IS NULL)::bigint AS unmatched FROM spatial_lab.assigned_crime
        UNION ALL
        SELECT 'traffic'::text,COUNT(*)::bigint,COUNT(dist_num)::bigint,COUNT(*) FILTER (WHERE dist_num IS NULL)::bigint FROM spatial_lab.assigned_traffic
    ) AS coverage ORDER BY CASE source WHEN 'crime' THEN 1 ELSE 2 END""",
    "district-e3": """SELECT d.dist_num,COALESCE(SUM(r.crime_records),0)::bigint AS crime_records
        FROM training.districts AS d LEFT JOIN spatial_lab.integrated_report AS r USING(dist_num)
        GROUP BY d.dist_num ORDER BY d.dist_num""",
    "district-e4": """SELECT COUNT(*)::bigint AS assigned_crashes,COUNT(injuries_total)::bigint AS observed_injuries,SUM(injuries_total)::bigint AS injuries
        FROM spatial_lab.assigned_traffic WHERE dist_num IS NOT NULL""",
    "dashboard-e1": """SELECT month,SUM(crime_records)::bigint AS crimes,SUM(crash_records)::bigint AS crashes
        FROM spatial_lab.integrated_report GROUP BY month ORDER BY month""",
    "dashboard-e2": """SELECT dist_num,month,crime_records,LAG(crime_records) OVER(PARTITION BY dist_num ORDER BY month) AS previous
        FROM spatial_lab.integrated_report ORDER BY dist_num,month""",
    "dashboard-e3": """SELECT d.dist_num,COALESCE(SUM(r.observed_injuries),0)::bigint AS observed,
        ROUND(SUM(r.injuries)::numeric/NULLIF(SUM(r.observed_injuries),0),3) AS mean_injuries
        FROM training.districts AS d LEFT JOIN spatial_lab.integrated_report AS r USING(dist_num)
        GROUP BY d.dist_num ORDER BY d.dist_num""",
    "dashboard-e4": """SELECT source,unmatched FROM (
        SELECT 'crime'::text AS source,COUNT(*) FILTER (WHERE dist_num IS NULL)::bigint AS unmatched FROM spatial_lab.assigned_crime
        UNION ALL
        SELECT 'traffic'::text,COUNT(*) FILTER (WHERE dist_num IS NULL)::bigint FROM spatial_lab.assigned_traffic
    ) AS coverage ORDER BY CASE source WHEN 'crime' THEN 1 ELSE 2 END""",
}


@app.post("/api/labs/tasks/run")
def run_spatial_lab_task(body: LabTaskRequest, user=Depends(current_user)):
    statement = LAB_TASK_SQL.get(body.task_id)
    if statement is None:
        raise HTTPException(404, "المهمة غير موجودة")
    result = run_sql_command(str(uuid4()), user, statement)
    if not result["rows"]:
        raise HTTPException(503, "لم تُرجع قاعدة البيانات صفوفًا لهذه المهمة؛ تأكد من جاهزية بيانات التدريب.")
    return {"task_id": body.task_id, "statement": statement, "result": result}


def lab_result_dicts(result: dict):
    return [dict(zip(result["columns"], row)) for row in result["rows"]]


@app.get("/api/labs/district-dashboard")
def district_month_dashboard(user=Depends(current_user)):
    monthly = query_as_user(user, """SELECT month,SUM(crime_records)::bigint AS crimes,SUM(crash_records)::bigint AS crashes
        FROM spatial_lab.integrated_report GROUP BY month ORDER BY month""", 24)
    districts = query_as_user(user, """SELECT d.dist_num,COALESCE(SUM(r.crime_records),0)::bigint AS crimes,
        COALESCE(SUM(r.crash_records),0)::bigint AS crashes,COALESCE(SUM(r.observed_injuries),0)::bigint AS observed_injuries,
        SUM(r.injuries)::bigint AS injuries,
        ROUND(SUM(r.injuries)::numeric/NULLIF(SUM(r.observed_injuries),0),3) AS mean_injuries
        FROM training.districts AS d LEFT JOIN spatial_lab.integrated_report AS r USING(dist_num)
        GROUP BY d.dist_num ORDER BY d.dist_num""", 24)
    coverage = query_as_user(user, """SELECT source,total,assigned,unmatched FROM (
        SELECT 'crime'::text AS source,COUNT(*)::bigint AS total,COUNT(dist_num)::bigint AS assigned,COUNT(*) FILTER (WHERE dist_num IS NULL)::bigint AS unmatched FROM spatial_lab.assigned_crime
        UNION ALL
        SELECT 'traffic'::text,COUNT(*)::bigint,COUNT(dist_num)::bigint,COUNT(*) FILTER (WHERE dist_num IS NULL)::bigint FROM spatial_lab.assigned_traffic
    ) AS sources ORDER BY CASE source WHEN 'crime' THEN 1 ELSE 2 END""", 4)
    reconciliation = query_as_user(user, """SELECT
        (SELECT COUNT(*) FROM spatial_lab.assigned_crime)::bigint AS source_crimes,
        (SELECT COUNT(dist_num) FROM spatial_lab.assigned_crime)::bigint AS assigned_crimes,
        (SELECT COUNT(*) FROM spatial_lab.assigned_crime WHERE dist_num IS NULL)::bigint AS unmatched_crimes,
        (SELECT COALESCE(SUM(crime_records),0) FROM spatial_lab.integrated_report)::bigint AS report_crimes,
        (SELECT COUNT(*) FROM spatial_lab.assigned_traffic)::bigint AS source_crashes,
        (SELECT COUNT(dist_num) FROM spatial_lab.assigned_traffic)::bigint AS assigned_crashes,
        (SELECT COUNT(*) FROM spatial_lab.assigned_traffic WHERE dist_num IS NULL)::bigint AS unmatched_crashes,
        (SELECT COALESCE(SUM(crash_records),0) FROM spatial_lab.integrated_report)::bigint AS report_crashes,
        (SELECT COUNT(*) FROM spatial_lab.integrated_report)::bigint AS report_rows,
        (SELECT COUNT(*)*12 FROM training.districts)::bigint AS expected_rows""", 2)
    monthly_rows=lab_result_dicts(monthly)
    district_rows=lab_result_dicts(districts)
    coverage_rows=lab_result_dicts(coverage)
    check=lab_result_dicts(reconciliation)[0]
    if not monthly_rows or not district_rows or len(coverage_rows)!=2:
        raise HTTPException(503, "لم تُجهز جداول التحليل السنوي؛ أعد تشغيل خدمة API لتحديث بيانات التمارين.")
    checks={
        "crime_source_matches_assignment": check["source_crimes"] == check["assigned_crimes"]+check["unmatched_crimes"],
        "crime_assignment_matches_report": check["assigned_crimes"] == check["report_crimes"],
        "traffic_source_matches_assignment": check["source_crashes"] == check["assigned_crashes"]+check["unmatched_crashes"],
        "traffic_assignment_matches_report": check["assigned_crashes"] == check["report_crashes"],
        "district_month_calendar_complete": check["report_rows"] == check["expected_rows"] and check["report_rows"] > 0,
    }
    if any(not value for value in checks.values()):
        raise HTTPException(503, "فشل تحقق مطابقة بيانات التدريب؛ لم أعد لوحة بنتيجة ناقصة.")
    provenance_result=query_as_user(user,"SELECT mode FROM training.provenance LIMIT 1",2)
    provenance_rows=lab_result_dicts(provenance_result)
    return {
        "database": monthly.get("database"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "monthly": monthly_rows,
        "districts": district_rows,
        "coverage": coverage_rows,
        "reconciliation": check,
        "checks": checks,
        "provenance": {
            "mode": provenance_rows[0]["mode"] if provenance_rows else "unknown",
            "year": 2025,
            "grain": "district-month; 12 calendar months per district",
            "district_assignment": "ST_Covers; alphabetically lowest dist_num wins boundary ties",
            "sources": ["training.crimes", "training.crashes", "training.districts"],
            "views": ["spatial_lab.assigned_crime", "spatial_lab.assigned_traffic", "spatial_lab.integrated_report"],
            "injury_measure": "injuries_total sum with observed value count as denominator; NULL is not converted to zero",
            "reconciliation": check,
            "checks": checks,
        },
    }


async def replay_offline_commands():
    online_ready = False
    while True:
        try:
            if not online_ready:
                try:
                    await asyncio.to_thread(initialize_database)
                    online_ready = True
                except psycopg.OperationalError:
                    await asyncio.sleep(5)
                    continue
                except psycopg.Error:
                    logger.exception("Database setup could not be completed before replaying queued commands")
                    await asyncio.sleep(15)
                    continue
            item = await asyncio.to_thread(OFFLINE_QUEUE.claim)
            if item is None:
                await asyncio.sleep(3)
                continue
            payload = item["payload"]
            try:
                with db() as connection:
                    active = connection.execute(
                        "SELECT id,email,name,role,active FROM app_private.app_users WHERE id=%s",
                        (payload["user"]["id"],),
                    ).fetchone()
                if not active or not active["active"] or active["role"] != payload["user"]["role"]:
                    await asyncio.to_thread(OFFLINE_QUEUE.mark, item["command_id"], "failed", error="تم إيقاف الأمر لأن الحساب غير نشط أو تغير دوره قبل عودة الاتصال")
                    continue
                result = await asyncio.to_thread(run_sql_command, item["command_id"], dict(active), payload["statement"])
                await asyncio.to_thread(OFFLINE_QUEUE.mark, item["command_id"], "applied", result=result)
            except psycopg.OperationalError:
                online_ready = False
                await asyncio.to_thread(OFFLINE_QUEUE.mark, item["command_id"], "queued", error="لا يزال الاتصال بقاعدة البيانات منقطعًا")
                await asyncio.sleep(5)
            except (psycopg.Error, HTTPException, ValueError) as exc:
                message = exc.detail if isinstance(exc, HTTPException) else (str(exc).splitlines()[0] or "تعذر تنفيذ الأمر")
                await asyncio.to_thread(OFFLINE_QUEUE.mark, item["command_id"], "failed", error=message)
            except Exception:
                logger.exception("Unexpected offline SQL replay failure")
                await asyncio.to_thread(OFFLINE_QUEUE.mark, item["command_id"], "failed", error="حدث خطأ غير متوقع أثناء إعادة التنفيذ")
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Offline command queue worker failed")
            await asyncio.sleep(5)


@app.get("/api/sql-console/commands")
def sql_command_history(user=Depends(require_roles("data_analyst"))):
    commands = {
        item["command_id"]: {"command_id": item["command_id"], "statement": item["payload"].get("statement", ""), "status": item["status"], "attempts": item["attempts"], "last_error": item["last_error"], "result": item["result"], "created_at": item["created_at"], "updated_at": item["updated_at"]}
        for item in OFFLINE_QUEUE.list(100)
    }
    try:
        with db() as connection:
            rows = connection.execute("SELECT command_id,statement,result,executed_at FROM app_private.sql_command_log ORDER BY executed_at DESC LIMIT 100").fetchall()
        for row in rows:
            key = str(row["command_id"])
            commands.setdefault(key, {"command_id": key, "statement": row["statement"], "status": "applied", "attempts": 1, "last_error": None, "result": dict(row["result"]), "created_at": row["executed_at"].isoformat(), "updated_at": row["executed_at"].isoformat()})
    except psycopg.OperationalError:
        pass
    return sorted(commands.values(), key=lambda item: item["updated_at"], reverse=True)[:100]


@app.post("/api/sql-console/execute")
def execute_sql(body: SQLStatement, user=Depends(current_user)):
    if user["role"] not in SQL_DATABASE_ROLES:
        raise HTTPException(403, "محرر SQL غير متاح لهذا الدور")
    statement = validate_sql(body.statement, user["role"])
    try:
        return run_sql_command(str(body.command_id), user, statement)
    except psycopg.OperationalError:
        try:
            OFFLINE_QUEUE.put(str(body.command_id), {"user": {key: user[key] for key in ("id", "email", "name", "role")}, "statement": statement})
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        return JSONResponse(status_code=202, content={"queued": True, "command_id": str(body.command_id), "status": "queued", "message": "انقطع الاتصال؛ حُفظ الأمر محليًا وسيُراجع قبل إعادة تنفيذه."})
    except psycopg.Error as exc:
        message = str(exc).splitlines()[0] if str(exc) else "استعلام SQL غير صالح"
        raise HTTPException(400, f"تعذر تنفيذ الاستعلام: {message}") from None
