"""
OpenClaw Backend API - WORKING VERSION
Simple backend that connects to Supabase properly
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
import re
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# DATABASE CONNECTION - FIXED FOR VERCEL
def get_database_config():
    """Parse DATABASE_URL from Vercel/Supabase"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Parse the full connection string
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', database_url)
        if match:
            user, password, host, port, database = match.groups()
            return {
                'host': host,
                'database': database.split('?')[0],  # Remove query params
                'user': user,
                'password': password,
                'port': int(port),
                'sslmode': 'require'
            }
    
    # Fallback to individual env vars
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'postgres'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'port': int(os.getenv('DB_PORT', '5432'))
    }

@contextmanager
def get_db_connection():
    """Database connection context manager"""
    config = get_database_config()
    conn = psycopg2.connect(**config)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# PYDANTIC MODELS
class ServerBase(BaseModel):
    name: str
    ip_address: str
    purpose: Optional[str] = None
    cpu_cores: Optional[int] = 0
    ram_gb: Optional[int] = 0
    disk_tb: Optional[float] = 0
    status: str = 'online'
    proxmox_api_url: Optional[str] = None
    proxmox_node: Optional[str] = None
    proxmox_username: Optional[str] = None
    proxmox_password: Optional[str] = None
    gpu_model: Optional[str] = None
    gpu_count: Optional[int] = None
    gpu_memory: Optional[str] = None
    gpu_notes: Optional[str] = None
    notes: Optional[str] = None

class ServerCreate(ServerBase):
    pass

class ServerUpdate(BaseModel):
    name: Optional[str] = None
    ip_address: Optional[str] = None
    purpose: Optional[str] = None
    cpu_cores: Optional[int] = None
    ram_gb: Optional[int] = None
    disk_tb: Optional[float] = None
    status: Optional[str] = None
    proxmox_api_url: Optional[str] = None
    proxmox_node: Optional[str] = None
    proxmox_username: Optional[str] = None
    proxmox_password: Optional[str] = None
    gpu_model: Optional[str] = None
    gpu_count: Optional[int] = None
    gpu_memory: Optional[str] = None
    gpu_notes: Optional[str] = None
    notes: Optional[str] = None

class VMBase(BaseModel):
    server_id: int
    name: str
    ip_address: str
    os: str
    os_version: Optional[str] = None
    status: str = 'running'
    cpu: str = '—'
    ram: str = '—'
    disk: str = '—'
    ssh_port: str = '22'
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    proxmox_vmid: Optional[int] = None
    notes: Optional[str] = None

class VMCreate(VMBase):
    pass

class VMUpdate(BaseModel):
    server_id: Optional[int] = None
    name: Optional[str] = None
    ip_address: Optional[str] = None
    os: Optional[str] = None
    os_version: Optional[str] = None
    status: Optional[str] = None
    cpu: Optional[str] = None
    ram: Optional[str] = None
    disk: Optional[str] = None
    ssh_port: Optional[str] = None
    ssh_user: Optional[str] = None
    ssh_password: Optional[str] = None
    proxmox_vmid: Optional[int] = None
    notes: Optional[str] = None

class ProjectBase(BaseModel):
    vm_id: int
    name: str
    port: Optional[str] = None
    path: Optional[str] = None
    domain: Optional[str] = None
    status: str = 'running'
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    vm_id: Optional[int] = None
    name: Optional[str] = None
    port: Optional[str] = None
    path: Optional[str] = None
    domain: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None

# FASTAPI APP
app = FastAPI(
    title="OpenClaw API",
    description="Server Management API",
    version="1.5.0"
)

class CORSManualMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            from starlette.responses import Response
            response = Response()
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "*"
            response.headers["Access-Control-Allow-Headers"] = "*"
            return response
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "*"
        response.headers["Access-Control-Allow-Headers"] = "*"
        return response

app.add_middleware(CORSManualMiddleware)

# ENDPOINTS
@app.get("/")
async def read_index():
    return FileResponse('static/index.html')

@app.get("/servers", response_model=List[dict])
def get_servers():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM servers ORDER BY created_at DESC")
            return cursor.fetchall()

@app.get("/servers/{server_id}", response_model=dict)
def get_server(server_id: int):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM servers WHERE id = %s", (server_id,))
            server = cursor.fetchone()
            if not server:
                raise HTTPException(status_code=404, detail="Server not found")
            return server

@app.post("/servers", response_model=dict, status_code=201)
def create_server(server: ServerCreate):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                INSERT INTO servers (name, ip_address, purpose, cpu_cores, ram_gb, disk_tb, 
                                    status, proxmox_api_url, proxmox_node, proxmox_username, 
                                    proxmox_password, gpu_model, gpu_count, gpu_memory, 
                                    gpu_notes, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                server.name, server.ip_address, server.purpose, server.cpu_cores,
                server.ram_gb, server.disk_tb, server.status, server.proxmox_api_url,
                server.proxmox_node, server.proxmox_username, server.proxmox_password,
                server.gpu_model, server.gpu_count, server.gpu_memory, 
                server.gpu_notes, server.notes
            ))
            return cursor.fetchone()

@app.put("/servers/{server_id}", response_model=dict)
def update_server(server_id: int, server: ServerUpdate):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            update_fields = []
            values = []
            for field, value in server.dict(exclude_unset=True).items():
                update_fields.append(f"{field} = %s")
                values.append(value)
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            values.append(server_id)
            query = f"UPDATE servers SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
            cursor.execute(query, values)
            updated_server = cursor.fetchone()
            
            if not updated_server:
                raise HTTPException(status_code=404, detail="Server not found")
            return updated_server

@app.delete("/servers/{server_id}", status_code=204)
def delete_server(server_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM servers WHERE id = %s", (server_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Server not found")

# VM ENDPOINTS (abbreviated)
@app.get("/vms", response_model=List[dict])
def get_vms():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM vms ORDER BY created_at DESC")
            return cursor.fetchall()

@app.post("/vms", response_model=dict, status_code=201)
def create_vm(vm: VMCreate):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                INSERT INTO vms (server_id, name, ip_address, os, os_version, status,
                                cpu, ram, disk, ssh_port, ssh_user, ssh_password,
                                proxmox_vmid, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                vm.server_id, vm.name, vm.ip_address, vm.os, vm.os_version,
                vm.status, vm.cpu, vm.ram, vm.disk, vm.ssh_port,
                vm.ssh_user, vm.ssh_password, vm.proxmox_vmid, vm.notes
            ))
            return cursor.fetchone()

# PROJECT ENDPOINTS (abbreviated)
@app.get("/projects", response_model=List[dict])
def get_projects():
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
            return cursor.fetchall()

@app.post("/projects", response_model=dict, status_code=201)
def create_project(project: ProjectCreate):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("""
                INSERT INTO projects (vm_id, name, port, path, domain, status, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                project.vm_id, project.name, project.port, project.path,
                project.domain, project.status, project.description
            ))
            return cursor.fetchone()

# STATS ENDPOINT - WORKING!
@app.get("/stats")
def get_stats():
    """Get dashboard statistics - THIS WORKS FOR N8N!"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM servers")
            total_servers = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM vms")
            total_vms = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM vms WHERE status = 'running'")
            running_vms = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM projects")
            total_projects = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM servers WHERE status = 'online'")
            online_servers = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT COUNT(*) as count 
                FROM servers 
                WHERE gpu_model IS NOT NULL AND gpu_model != ''
            """)
            servers_with_gpu = cursor.fetchone()['count']
            
            cursor.execute("""
                SELECT COALESCE(SUM(gpu_count), 0) as total
                FROM servers
                WHERE gpu_count IS NOT NULL
            """)
            total_gpus = cursor.fetchone()['total']
            
            return {
                "total_servers": total_servers,
                "total_vms": total_vms,
                "running_vms": running_vms,
                "total_projects": total_projects,
                "online_servers": online_servers,
                "servers_with_gpu": servers_with_gpu,
                "total_gpus": total_gpus
            }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
