"""
OpenClaw Backend API v2.0 - WITH REAL-TIME SERVER HEALTH MONITORING
Complete FastAPI backend with health check endpoints
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
import httpx
import asyncio

# DATABASE CONNECTION
def get_database_config():
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', database_url)
        if match:
            user, password, host, port, database = match.groups()
            return {
                'host': host,
                'database': database.split('?')[0],
                'user': user,
                'password': password,
                'port': int(port),
                'sslmode': 'require'
            }
    return {
        'host': os.getenv('DB_HOST', 'localhost'),
        'database': os.getenv('DB_NAME', 'postgres'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'password'),
        'port': int(os.getenv('DB_PORT', '5432'))
    }

@contextmanager
def get_db_connection():
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

# VM MODELS (keeping same as before)
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

# PROJECT MODELS (keeping same as before)
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

# ═════════════════════════════════════════════════════
# HEALTH CHECK FUNCTIONS - NEW!
# ═════════════════════════════════════════════════════

async def check_server_health(ip_address: str, timeout: int = 5) -> dict:
    """Check if a Proxmox server is responding"""
    urls_to_try = [
        f"https://{ip_address}:8006",
        f"http://{ip_address}:8006",
        f"http://{ip_address}:80",
        f"http://{ip_address}",
    ]
    
    start_time = datetime.now()
    
    async with httpx.AsyncClient(verify=False, timeout=timeout) as client:
        for url in urls_to_try:
            try:
                response = await client.get(url)
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                if response.status_code < 500:
                    return {
                        'is_online': True,
                        'response_time_ms': round(response_time, 2),
                        'responding_url': url,
                        'status_code': response.status_code
                    }
            except:
                continue
    
    response_time = (datetime.now() - start_time).total_seconds() * 1000
    return {
        'is_online': False,
        'response_time_ms': round(response_time, 2),
        'responding_url': None,
        'status_code': None,
        'error': 'No response'
    }

async def check_all_servers_health():
    """Check health of all servers concurrently"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM servers ORDER BY name")
            servers = cursor.fetchall()
    
    tasks = [check_server_health(server['ip_address']) for server in servers]
    health_results = await asyncio.gather(*tasks)
    
    health_checks = []
    for server, health in zip(servers, health_results):
        health_checks.append({
            'id': server['id'],
            'name': server['name'],
            'ip_address': server['ip_address'],
            'db_status': server['status'],
            'actual_status': 'online' if health['is_online'] else 'offline',
            'status_match': (server['status'] == ('online' if health['is_online'] else 'offline')),
            'response_time_ms': health.get('response_time_ms'),
            'responding_url': health.get('responding_url'),
            'error': health.get('error')
        })
    
    total = len(health_checks)
    actually_online = sum(1 for s in health_checks if s['actual_status'] == 'online')
    db_says_online = sum(1 for s in health_checks if s['db_status'] == 'online')
    mismatches = [s for s in health_checks if not s['status_match']]
    
    return {
        'total_servers': total,
        'actually_online': actually_online,
        'actually_offline': total - actually_online,
        'db_says_online': db_says_online,
        'db_says_offline': total - db_says_online,
        'discrepancies': len(mismatches),
        'servers': health_checks,
        'mismatched_servers': mismatches,
        'offline_servers': [s for s in health_checks if s['actual_status'] == 'offline'],
        'timestamp': datetime.now().isoformat(),
        'all_systems_operational': actually_online == total
    }

# FASTAPI APP
app = FastAPI(
    title="OpenClaw API v2.0",
    description="Server Management API with Real-Time Health Monitoring",
    version="2.0.0"
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

# ═════════════════════════════════════════════════════
# HEALTH CHECK ENDPOINTS - USE THESE IN N8N!
# ═════════════════════════════════════════════════════

@app.get("/health/servers")
async def get_servers_health():
    """
    ★ USE THIS ENDPOINT IN YOUR N8N WORKFLOW! ★
    Returns real-time health status of all servers
    """
    try:
        return await check_all_servers_health()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.get("/health/quick")
async def quick_health_check():
    """Quick health summary"""
    health_report = await check_all_servers_health()
    return {
        'all_systems_operational': health_report['all_systems_operational'],
        'total_servers': health_report['total_servers'],
        'online': health_report['actually_online'],
        'offline': health_report['actually_offline'],
        'offline_servers': [
            {'name': s['name'], 'ip': s['ip_address']} 
            for s in health_report['servers'] 
            if s['actual_status'] == 'offline'
        ],
        'timestamp': health_report['timestamp']
    }

# ═════════════════════════════════════════════════════
# ORIGINAL ENDPOINTS (SAME AS BEFORE)
# ═════════════════════════════════════════════════════

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

# VM ENDPOINTS (keeping same - abbreviated for space)
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

# STATS ENDPOINT
@app.get("/stats")
def get_stats():
    """Database stats - for real-time use /health/servers"""
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
                "total_gpus": total_gpus,
                "note": "Use /health/servers for real-time server status"
            }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
