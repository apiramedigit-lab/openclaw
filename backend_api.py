"""
Server Management Portal - FastAPI Backend
Connects PostgreSQL database with frontend portal
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from fastapi.responses import FileResponse  # Add this
from fastapi.staticfiles import StaticFiles # Add this
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ═══════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════

DATABASE_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'openclaw_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'port': os.getenv('DB_PORT', '5432')
}

@contextmanager
def get_db_connection():
    """Database connection context manager"""
    conn = psycopg2.connect(**DATABASE_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

# ═══════════════════════════════════════════════════════════
# PYDANTIC MODELS (Request/Response schemas)
# ═══════════════════════════════════════════════════════════

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
    gpu_model: Optional[str] = None        # ← ADD THIS
    gpu_count: Optional[int] = None        # ← ADD THIS
    gpu_memory: Optional[str] = None       # ← ADD THIS
    gpu_notes: Optional[str] = None        # ← ADD THIS
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
    gpu_model: Optional[str] = None        # ← ADD THIS
    gpu_count: Optional[int] = None        # ← ADD THIS
    gpu_memory: Optional[str] = None       # ← ADD THIS
    gpu_notes: Optional[str] = None        # ← ADD THIS
    notes: Optional[str] = None

class Server(ServerBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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

class VM(VMBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


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

class Project(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════
# FASTAPI APP INITIALIZATION
# ═══════════════════════════════════════════════════════════

app = FastAPI(
    title="Server Management Portal API",
    description="Backend API for managing servers, VMs, and projects",
    version="1.0.0"
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


# ═══════════════════════════════════════════════════════════
# SERVER ENDPOINTS
# ═══════════════════════════════════════════════════════════

# Replace the old health check root with this:
@app.get("/")
async def read_index():
    """Serves the frontend dashboard"""
    return FileResponse('index.html') 

# Optional: If you have CSS/JS files in a folder named 'static'
# app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/servers", response_model=List[dict])
def get_servers():
    """Get all servers"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM servers ORDER BY created_at DESC")
            servers = cursor.fetchall()
            return servers


@app.get("/servers/{server_id}", response_model=dict)
def get_server(server_id: int):
    """Get a specific server by ID"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM servers WHERE id = %s", (server_id,))
            server = cursor.fetchone()
            if not server:
                raise HTTPException(status_code=404, detail="Server not found")
            return server


@app.post("/servers", response_model=dict, status_code=201)
def create_server(server: ServerCreate):
    """Create a new server"""
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
            new_server = cursor.fetchone()
            return new_server


@app.put("/servers/{server_id}", response_model=dict)
def update_server(server_id: int, server: ServerUpdate):
    """Update a server"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Build dynamic update query
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
    """Delete a server (and all its VMs)"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM servers WHERE id = %s", (server_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Server not found")
            return None


# ═══════════════════════════════════════════════════════════
# VM ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/vms", response_model=List[dict])
def get_vms():
    """Get all VMs"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM vms ORDER BY created_at DESC")
            vms = cursor.fetchall()
            return vms


@app.get("/servers/{server_id}/vms", response_model=List[dict])
def get_server_vms(server_id: int):
    """Get all VMs for a specific server"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM vms WHERE server_id = %s ORDER BY created_at DESC", 
                         (server_id,))
            vms = cursor.fetchall()
            return vms


@app.get("/vms/{vm_id}", response_model=dict)
def get_vm(vm_id: int):
    """Get a specific VM by ID"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM vms WHERE id = %s", (vm_id,))
            vm = cursor.fetchone()
            if not vm:
                raise HTTPException(status_code=404, detail="VM not found")
            return vm


@app.post("/vms", response_model=dict, status_code=201)
def create_vm(vm: VMCreate):
    """Create a new VM"""
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
            new_vm = cursor.fetchone()
            return new_vm


@app.put("/vms/{vm_id}", response_model=dict)
def update_vm(vm_id: int, vm: VMUpdate):
    """Update a VM"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            update_fields = []
            values = []
            for field, value in vm.dict(exclude_unset=True).items():
                update_fields.append(f"{field} = %s")
                values.append(value)
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            values.append(vm_id)
            query = f"UPDATE vms SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
            
            cursor.execute(query, values)
            updated_vm = cursor.fetchone()
            
            if not updated_vm:
                raise HTTPException(status_code=404, detail="VM not found")
            
            return updated_vm


@app.delete("/vms/{vm_id}", status_code=204)
def delete_vm(vm_id: int):
    """Delete a VM (and all its projects)"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM vms WHERE id = %s", (vm_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="VM not found")
            return None


# ═══════════════════════════════════════════════════════════
# PROJECT ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/projects", response_model=List[dict])
def get_projects():
    """Get all projects"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
            projects = cursor.fetchall()
            return projects


@app.get("/vms/{vm_id}/projects", response_model=List[dict])
def get_vm_projects(vm_id: int):
    """Get all projects for a specific VM"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM projects WHERE vm_id = %s ORDER BY created_at DESC", 
                         (vm_id,))
            projects = cursor.fetchall()
            return projects


@app.get("/projects/{project_id}", response_model=dict)
def get_project(project_id: int):
    """Get a specific project by ID"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
            project = cursor.fetchone()
            if not project:
                raise HTTPException(status_code=404, detail="Project not found")
            return project


@app.post("/projects", response_model=dict, status_code=201)
def create_project(project: ProjectCreate):
    """Create a new project"""
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
            new_project = cursor.fetchone()
            return new_project


@app.put("/projects/{project_id}", response_model=dict)
def update_project(project_id: int, project: ProjectUpdate):
    """Update a project"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            update_fields = []
            values = []
            for field, value in project.dict(exclude_unset=True).items():
                update_fields.append(f"{field} = %s")
                values.append(value)
            
            if not update_fields:
                raise HTTPException(status_code=400, detail="No fields to update")
            
            values.append(project_id)
            query = f"UPDATE projects SET {', '.join(update_fields)} WHERE id = %s RETURNING *"
            
            cursor.execute(query, values)
            updated_project = cursor.fetchone()
            
            if not updated_project:
                raise HTTPException(status_code=404, detail="Project not found")
            
            return updated_project


@app.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: int):
    """Delete a project"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Project not found")
            return None


# ═══════════════════════════════════════════════════════════
# STATISTICS ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/stats")
def get_stats():
    """Get dashboard statistics"""
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Total servers
            cursor.execute("SELECT COUNT(*) as count FROM servers")
            total_servers = cursor.fetchone()['count']
            
            # Total VMs
            cursor.execute("SELECT COUNT(*) as count FROM vms")
            total_vms = cursor.fetchone()['count']
            
            # Running VMs
            cursor.execute("SELECT COUNT(*) as count FROM vms WHERE status = 'running'")
            running_vms = cursor.fetchone()['count']
            
            # Total projects
            cursor.execute("SELECT COUNT(*) as count FROM projects")
            total_projects = cursor.fetchone()['count']
            
            # Online servers
            cursor.execute("SELECT COUNT(*) as count FROM servers WHERE status = 'online'")
            online_servers = cursor.fetchone()['count']
            
            # GPU stats - ADD THESE
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
                "servers_with_gpu": servers_with_gpu,    # ← ADD THIS
                "total_gpus": total_gpus                  # ← ADD THIS
            }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
