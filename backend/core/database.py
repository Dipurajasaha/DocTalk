from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import urllib.parse
from datetime import datetime, timezone
import queue
from typing import Any

import pymysql
import pymysql.cursors

from .config import settings

logger = logging.getLogger(__name__)

# List of fields that should be serialized/deserialized as JSON in the database
JSON_FIELDS = {
    "closedDoctorChats",
    "doctorChats",
    "xrayAnalyses",
    "customAssets",
    "schedules",
    "appointmentRequests",
    "payments",
    "patientChats",
    "closedChats",
    "metadata",
    "embedding"
}

# Mapping of python/prisma model names to table names and primary keys
MODEL_CONFIGS = {
    "patient": {"table": "patients", "pk": "username", "mapping": {}},
    "doctor": {"table": "doctors", "pk": "doctorId", "mapping": {}},
    "doctorslot": {"table": "doctor_slots", "pk": "id", "mapping": {}},
    "appointment": {"table": "appointments", "pk": "id", "mapping": {}},
    "consultation": {"table": "consultations", "pk": "id", "mapping": {}},
    "message": {"table": "messages", "pk": "id", "mapping": {}},
    "filekey": {"table": "file_keys", "pk": "id", "mapping": {}},
    "user": {"table": "users", "pk": "id", "mapping": {}},
    "medicalasset": {"table": "medical_assets", "pk": "id", "mapping": {}},
    "ragdocument": {
        "table": "rag_documents",
        "pk": "id",
        "mapping": {
            "patientId": "patient_id",
            "consultationId": "consultation_id",
            "sourceType": "source_type",
            "createdAt": "created_at"
        }
    },
    "aichatsession": {"table": "ai_chat_sessions", "pk": "id", "mapping": {}},
    "aichatmessage": {"table": "ai_chat_messages", "pk": "id", "mapping": {}}
}

# Inverse mappings helper (db columns to python fields)
for config in MODEL_CONFIGS.values():
    config["inverse_mapping"] = {v: k for k, v in config["mapping"].items()}


def build_where_clause(where: dict | None, args: list, field_mapping: dict) -> str:
    if not where:
        return ""
    
    clauses = []
    
    # Handle logical AND
    if "AND" in where:
        and_clauses = []
        for cond in where["AND"]:
            c = build_where_clause(cond, args, field_mapping)
            if c:
                and_clauses.append(c)
        if and_clauses:
            clauses.append("(" + " AND ".join(and_clauses) + ")")
            
    # Handle logical OR
    if "OR" in where:
        or_clauses = []
        for cond in where["OR"]:
            cond_args = []
            c = build_where_clause(cond, cond_args, field_mapping)
            if c:
                or_clauses.append(c)
                args.extend(cond_args)
        if or_clauses:
            clauses.append("(" + " OR ".join(or_clauses) + ")")
            
    for key, value in where.items():
        if key in ("AND", "OR"):
            continue
        
        db_field = field_mapping.get(key, key)
        
        if isinstance(value, dict):
            if "contains" in value:
                clauses.append(f"{db_field} LIKE %s")
                args.append(f"%{value['contains']}%")
            elif "in" in value:
                val_list = value["in"]
                if not val_list:
                    clauses.append("1=0")
                else:
                    placeholders = ", ".join(["%s"] * len(val_list))
                    clauses.append(f"{db_field} IN ({placeholders})")
                    args.extend(val_list)
        elif value is None:
            clauses.append(f"{db_field} IS NULL")
        else:
            clauses.append(f"{db_field} = %s")
            args.append(value)
            
    return " AND ".join(clauses)


def build_order_clause(order: Any, field_mapping: dict) -> str:
    if not order:
        return ""
    parts = []
    if isinstance(order, dict):
        for k, v in order.items():
            db_k = field_mapping.get(k, k)
            parts.append(f"{db_k} {v.upper()}")
    elif isinstance(order, list):
        for o in order:
            if isinstance(o, dict):
                for k, v in o.items():
                    db_k = field_mapping.get(k, k)
                    parts.append(f"{db_k} {v.upper()}")
    return "ORDER BY " + ", ".join(parts) if parts else ""


def build_limit_clause(skip: int | None = None, take: int | None = None) -> str:
    if take is not None:
        if skip is not None:
            return f"LIMIT {int(skip)}, {int(take)}"
        return f"LIMIT {int(take)}"
    return ""


class Record:
    def __init__(self, data: dict):
        self.__dict__.update(data)
        
    def model_dump(self) -> dict:
        d = {}
        for k, v in self.__dict__.items():
            if isinstance(v, Record):
                d[k] = v.model_dump()
            elif isinstance(v, list) and v and isinstance(v[0], Record):
                d[k] = [item.model_dump() for item in v]
            else:
                d[k] = v
        return d
        
    def __getitem__(self, key: str) -> Any:
        return self.__dict__[key]
        
    def get(self, key: str, default: Any = None) -> Any:
        return self.__dict__.get(key, default)

    def __getattr__(self, name: str) -> Any:
        try:
            return self.__dict__[name]
        except KeyError:
            raise AttributeError(f"'Record' object has no attribute '{name}'")


class MySQLTableProxy:
    def __init__(self, db_client: Prisma, model_name: str):
        self.db_client = db_client
        self.model_name = model_name
        config = MODEL_CONFIGS[model_name]
        self.table_name = config["table"]
        self.primary_key = config["pk"]
        self.field_mapping = config["mapping"]
        self.inverse_mapping = config["inverse_mapping"]

    def _to_record(self, row: dict) -> Record:
        mapped_data = {}
        for db_key, val in row.items():
            py_key = self.inverse_mapping.get(db_key, db_key)
            if py_key in JSON_FIELDS and isinstance(val, str):
                try:
                    val = json.loads(val)
                except Exception:
                    pass
            mapped_data[py_key] = val
        return Record(mapped_data)

    async def find_unique(self, where: dict, include: dict | None = None) -> Record | None:
        args: list[Any] = []
        where_clause = build_where_clause(where, args, self.field_mapping)
        sql = f"SELECT * FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        sql += " LIMIT 1"
        
        rows = await self.db_client._execute_in_thread(sql, args)
        if not rows:
            return None
        
        record = self._to_record(rows[0])
        if include:
            await self.db_client._resolve_includes(record, include, self.model_name)
        return record

    async def find_first(self, where: dict, order: Any = None, include: dict | None = None) -> Record | None:
        args: list[Any] = []
        where_clause = build_where_clause(where, args, self.field_mapping)
        sql = f"SELECT * FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if order:
            sql += " " + build_order_clause(order, self.field_mapping)
        sql += " LIMIT 1"
        
        rows = await self.db_client._execute_in_thread(sql, args)
        if not rows:
            return None
        
        record = self._to_record(rows[0])
        if include:
            await self.db_client._resolve_includes(record, include, self.model_name)
        return record

    async def find_many(self, where: dict | None = None, order: Any = None, skip: int | None = None, take: int | None = None, include: dict | None = None) -> list[Record]:
        args: list[Any] = []
        where_clause = build_where_clause(where, args, self.field_mapping)
        sql = f"SELECT * FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        if order:
            sql += " " + build_order_clause(order, self.field_mapping)
        limit_clause = build_limit_clause(skip, take)
        if limit_clause:
            sql += " " + limit_clause
            
        rows = await self.db_client._execute_in_thread(sql, args)
        records = [self._to_record(row) for row in rows]
        
        if include and records:
            for record in records:
                await self.db_client._resolve_includes(record, include, self.model_name)
        return records

    async def create(self, data: dict, include: dict | None = None) -> Record:
        cols = []
        placeholders = []
        args = []
        for key, val in data.items():
            db_key = self.field_mapping.get(key, key)
            cols.append(db_key)
            placeholders.append("%s")
            
            if isinstance(val, (dict, list, tuple, set)) or key in JSON_FIELDS:
                val = json.dumps(val, default=str)
            args.append(val)
            
        sql = f"INSERT INTO {self.table_name} ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
        
        pk_val = data.get(self.primary_key)
        await self.db_client._execute_in_thread(sql, args)
        
        if pk_val is not None:
            return await self.find_unique(where={self.primary_key: pk_val}, include=include)
        else:
            rows = await self.db_client._execute_in_thread("SELECT LAST_INSERT_ID() AS last_id")
            last_id = rows[0]["last_id"] if rows else None
            return await self.find_unique(where={self.primary_key: last_id}, include=include)

    async def update(self, where: dict, data: dict, include: dict | None = None) -> Record | None:
        set_parts = []
        args = []
        for key, val in data.items():
            db_key = self.field_mapping.get(key, key)
            set_parts.append(f"{db_key} = %s")
            if isinstance(val, (dict, list, tuple, set)) or key in JSON_FIELDS:
                val = json.dumps(val, default=str)
            args.append(val)
            
        where_args: list[Any] = []
        where_clause = build_where_clause(where, where_args, self.field_mapping)
        sql = f"UPDATE {self.table_name} SET {', '.join(set_parts)}"
        if where_clause:
            sql += f" WHERE {where_clause}"
            args.extend(where_args)
            
        await self.db_client._execute_in_thread(sql, args)
        return await self.find_first(where=where, include=include)

    async def delete(self, where: dict) -> Record | None:
        record = await self.find_first(where=where)
        if not record:
            return None
            
        args: list[Any] = []
        where_clause = build_where_clause(where, args, self.field_mapping)
        sql = f"DELETE FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
            
        await self.db_client._execute_in_thread(sql, args)
        return record

    async def delete_many(self, where: dict | None = None) -> BatchResult:
        args: list[Any] = []
        where_clause = build_where_clause(where, args, self.field_mapping)
        sql = f"DELETE FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
            
        affected = await self.db_client._execute_in_thread(sql, args, return_affected=True)
        return BatchResult(affected)

    async def count(self, where: dict | None = None) -> int:
        args: list[Any] = []
        where_clause = build_where_clause(where, args, self.field_mapping)
        sql = f"SELECT COUNT(*) AS total FROM {self.table_name}"
        if where_clause:
            sql += f" WHERE {where_clause}"
        rows = await self.db_client._execute_in_thread(sql, args)
        return rows[0]["total"] if rows else 0


class BatchResult:
    def __init__(self, count: int):
        self.count = count


class ConnectionPool:
    def __init__(self, creator, max_connections=5):
        self.creator = creator
        self.pool = queue.Queue(maxsize=max_connections)
        self.max_connections = max_connections
        self.active_count = 0

    @contextlib.contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = self.pool.get_nowait()
            conn.ping(reconnect=True)
        except queue.Empty:
            conn = self.creator()

        try:
            yield conn
        finally:
            if conn:
                try:
                    self.pool.put_nowait(conn)
                except queue.Full:
                    conn.close()


class Prisma:
    """Compatibility layer mimicking Prisma client while connecting directly to MySQL using PyMySQL."""

    def __init__(self):
        self._pool = None
        
        # Initialize table actions proxies
        self.patient = MySQLTableProxy(self, "patient")
        self.doctor = MySQLTableProxy(self, "doctor")
        self.doctorslot = MySQLTableProxy(self, "doctorslot")
        self.appointment = MySQLTableProxy(self, "appointment")
        self.consultation = MySQLTableProxy(self, "consultation")
        self.message = MySQLTableProxy(self, "message")
        self.filekey = MySQLTableProxy(self, "filekey")
        self.user = MySQLTableProxy(self, "user")
        self.medicalasset = MySQLTableProxy(self, "medicalasset")
        self.ragdocument = MySQLTableProxy(self, "ragdocument")
        self.aichatsession = MySQLTableProxy(self, "aichatsession")
        self.aichatmessage = MySQLTableProxy(self, "aichatmessage")

    def _create_connection(self) -> pymysql.Connection:
        url = urllib.parse.urlparse(settings.database_url)
        username = url.username
        password = url.password
        host = url.hostname or "127.0.0.1"
        port = url.port or 3306
        db = url.path.lstrip("/")
        
        return pymysql.connect(
            host=host,
            user=username,
            password=password,
            database=db,
            port=port,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )

    async def connect(self):
        # Create connection pool
        self._pool = ConnectionPool(self._create_connection, max_connections=10)
        
        # Perform DB schema checks and initialization
        await self._init_schema()

    async def disconnect(self):
        if self._pool:
            while not self._pool.pool.empty():
                try:
                    conn = self._pool.pool.get_nowait()
                    conn.close()
                except Exception:
                    pass
            self._pool = None

    def _sync_execute(self, query: str, args: list | None = None, return_affected: bool = False) -> Any:
        if not self._pool:
            raise RuntimeError("Database pool is not connected")
        
        with self._pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, args or ())
                if return_affected:
                    return cursor.rowcount
                try:
                    return cursor.fetchall()
                except Exception:
                    return []

    async def _execute_in_thread(self, query: str, args: list | None = None, return_affected: bool = False) -> Any:
        return await asyncio.to_thread(self._sync_execute, query, args, return_affected)

    async def query_raw(self, query: str, *args) -> list[dict]:
        # Translate positional placeholders $1, $2 to %s (PyMySQL uses %s)
        # We can substitute $1, $2... with %s using a regular expression or simple string replace
        import re
        translated_query = re.sub(r'\$\d+', '%s', query)
        
        # Replace types like ::vector or ::timestamp or ::jsonb casts
        translated_query = re.sub(r'::[a-zA-Z0-9_]+', '', translated_query)
        
        # Replace PG-specific constructs
        translated_query = translated_query.replace("NULL::float AS similarity", "NULL AS similarity")
        
        rows = await self._execute_in_thread(translated_query, list(args))
        return [dict(row) for row in rows]

    async def execute_raw(self, query: str, *args) -> int:
        import re
        translated_query = re.sub(r'\$\d+', '%s', query)
        translated_query = re.sub(r'::[a-zA-Z0-9_]+', '', translated_query)
        
        # Replace pgvector -> json_unquote json_extract
        # E.g. metadata->>'asset_id' = $1 -> JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.asset_id')) = %s
        # Let's do a simple replace for RAG deletion:
        translated_query = translated_query.replace("metadata->>'asset_id'", "JSON_UNQUOTE(JSON_EXTRACT(metadata, '$.asset_id'))")
        
        return await self._execute_in_thread(translated_query, list(args), return_affected=True)

    async def _resolve_includes(self, record: Record, include: dict, model_name: str):
        if not include:
            return
            
        if model_name == "doctorslot" and include.get("doctor"):
            doctor = await self.doctor.find_unique(where={"doctorId": record.doctorId})
            record.__dict__["doctor"] = doctor
            
        elif model_name == "appointment":
            if include.get("patient"):
                patient = await self.patient.find_unique(where={"username": record.patientUsername})
                record.__dict__["patient"] = patient
            if include.get("doctor"):
                doctor = await self.doctor.find_unique(where={"doctorId": record.doctorId})
                record.__dict__["doctor"] = doctor
            if include.get("slot") and getattr(record, "slotId", None):
                slot = await self.doctorslot.find_unique(where={"id": record.slotId})
                record.__dict__["slot"] = slot
                
        elif model_name == "medicalasset" and include.get("user"):
            user = await self.user.find_unique(where={"id": record.userId})
            record.__dict__["user"] = user

    async def _init_schema(self):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS patients (
                username VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                displayName VARCHAR(255) NULL,
                dob DATETIME NULL,
                gender VARCHAR(50) NULL,
                password VARCHAR(255) NOT NULL,
                bloodGroup VARCHAR(50) NULL,
                address TEXT NULL,
                mobile VARCHAR(50) NULL,
                email VARCHAR(255) NULL,
                phone VARCHAR(50) NULL,
                profilePic TEXT NULL,
                closedDoctorChats JSON NULL,
                doctorChats JSON NULL,
                xrayAnalyses JSON NULL,
                customAssets JSON NULL,
                publicKey TEXT NULL,
                encryptedPrivateKey TEXT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS doctors (
                doctorId VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                displayName VARCHAR(255) NULL,
                gender VARCHAR(50) NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(50) DEFAULT 'doctor',
                category VARCHAR(255) NULL,
                location VARCHAR(255) NULL,
                address TEXT NULL,
                registrationNumber VARCHAR(255) NULL,
                hospitalName VARCHAR(255) NULL,
                hospitalLocation VARCHAR(255) NULL,
                specialization VARCHAR(255) NULL,
                bio TEXT NULL,
                profilePic TEXT NULL,
                schedules JSON NULL,
                appointmentRequests JSON NULL,
                payments JSON NULL,
                patientChats JSON NULL,
                closedChats JSON NULL,
                publicKey TEXT NULL,
                encryptedPrivateKey TEXT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS doctor_slots (
                id VARCHAR(255) PRIMARY KEY,
                doctorId VARCHAR(255) NOT NULL,
                startTime DATETIME NOT NULL,
                endTime DATETIME NOT NULL,
                isBooked BOOLEAN DEFAULT FALSE,
                isActive BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (doctorId) REFERENCES doctors(doctorId) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id VARCHAR(255) PRIMARY KEY,
                patientUsername VARCHAR(255) NOT NULL,
                doctorId VARCHAR(255) NOT NULL,
                slotId VARCHAR(255) NULL,
                appointmentDate DATETIME NULL,
                scheduledTime DATETIME NULL,
                date VARCHAR(50) NULL,
                time VARCHAR(50) NULL,
                reason TEXT NOT NULL,
                note TEXT NULL,
                doctorMessage TEXT NULL,
                status VARCHAR(50) DEFAULT 'PENDING',
                requestedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                completedAt DATETIME NULL,
                FOREIGN KEY (patientUsername) REFERENCES patients(username) ON DELETE CASCADE,
                FOREIGN KEY (doctorId) REFERENCES doctors(doctorId) ON DELETE CASCADE,
                FOREIGN KEY (slotId) REFERENCES doctor_slots(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS consultations (
                id VARCHAR(255) PRIMARY KEY,
                appointmentId VARCHAR(255) UNIQUE NOT NULL,
                patientUsername VARCHAR(255) NOT NULL,
                doctorId VARCHAR(255) NOT NULL,
                lastMessageAt DATETIME NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (appointmentId) REFERENCES appointments(id) ON DELETE CASCADE,
                FOREIGN KEY (patientUsername) REFERENCES patients(username) ON DELETE CASCADE,
                FOREIGN KEY (doctorId) REFERENCES doctors(doctorId) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS messages (
                id VARCHAR(255) PRIMARY KEY,
                consultationId VARCHAR(255) NOT NULL,
                senderId VARCHAR(255) NOT NULL,
                senderRole VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (consultationId) REFERENCES consultations(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS file_keys (
                id VARCHAR(255) PRIMARY KEY,
                fileId VARCHAR(255) NOT NULL,
                patientUsername VARCHAR(255) NULL,
                doctorId VARCHAR(255) NULL,
                encryptedFileKey TEXT NOT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patientUsername) REFERENCES patients(username) ON DELETE CASCADE,
                FOREIGN KEY (doctorId) REFERENCES doctors(doctorId) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id VARCHAR(255) PRIMARY KEY,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS medical_assets (
                id VARCHAR(255) PRIMARY KEY,
                userId VARCHAR(255) NOT NULL,
                fileName VARCHAR(255) NOT NULL,
                fileType VARCHAR(255) NOT NULL,
                folderPath VARCHAR(255) DEFAULT '/my_documents/unclassified/',
                assetCategory VARCHAR(50) DEFAULT 'UNCLASSIFIED',
                processingStatus VARCHAR(50) DEFAULT 'PENDING',
                extractedText TEXT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (userId) REFERENCES users(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS rag_documents (
                id VARCHAR(255) PRIMARY KEY,
                patient_id VARCHAR(255) NOT NULL,
                consultation_id VARCHAR(255) NULL,
                source_type VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                summary TEXT NOT NULL,
                embedding JSON NOT NULL,
                metadata JSON NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patients(username) ON DELETE CASCADE,
                FOREIGN KEY (consultation_id) REFERENCES consultations(id) ON DELETE SET NULL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_chat_sessions (
                id VARCHAR(255) PRIMARY KEY,
                userId VARCHAR(255) NOT NULL,
                userRole VARCHAR(50) NOT NULL,
                mode VARCHAR(50) DEFAULT 'default',
                targetPatientId VARCHAR(255) NULL,
                title VARCHAR(255) NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                updatedAt DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ai_chat_messages (
                id VARCHAR(255) PRIMARY KEY,
                sessionId VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                createdAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sessionId) REFERENCES ai_chat_sessions(id) ON DELETE CASCADE
            )
            """
        ]

        logger.info("Initializing MySQL tables...")
        for stmt in statements:
            try:
                await self._execute_in_thread(stmt)
            except Exception as exc:
                logger.error(f"Error executing schema statement: {stmt.strip()[:100]}... error: {exc}")
                raise exc
        logger.info("MySQL tables initialized successfully.")


# Singleton Prisma replacement instance
prisma = Prisma()
_is_connected = False


async def connect_prisma() -> None:
    global _is_connected
    if _is_connected:
        return

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    connect_timeout_seconds = 5.0
    try:
        await asyncio.wait_for(prisma.connect(), timeout=connect_timeout_seconds)
        _is_connected = True
        logger.info("Direct MySQL database client connected", extra={"component": "database"})
    except Exception as exc:
        _is_connected = False
        logger.warning(
            "Direct MySQL client connect failed",
            extra={"component": "database", "error": str(exc)},
        )
        raise exc


async def disconnect_prisma() -> None:
    global _is_connected
    if not _is_connected:
        return

    await prisma.disconnect()
    _is_connected = False
    logger.info("Direct MySQL client disconnected", extra={"component": "database"})


async def ensure_connected() -> None:
    if not _is_connected:
        await connect_prisma()


async def get_prisma() -> Prisma:
    await ensure_connected()
    return prisma


async def ping_database() -> dict[str, Any]:
    try:
        await ensure_connected()
        result = await prisma.query_raw("SELECT 1 AS ok")
    except Exception:
        logger.warning("Database ping failed, retrying reconnect", extra={"component": "database"})
        await disconnect_prisma()
        await connect_prisma()
        result = await prisma.query_raw("SELECT 1 AS ok")

    first_row = result[0] if result else {"ok": 1}
    return {"status": "ok", "database": "connected", "result": first_row}
