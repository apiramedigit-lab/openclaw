"""
Server Management Portal - FastAPI Backend
Connects PostgreSQL database with frontend portal
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
from datetime import datetime
from urllib.parse import urlparse

# ═══════════════════════════════════════════════════════════
# DATABASE CONNECTION
# ═══════════════════════════════════════════════════════════

def get_database_config():
    """Parse DATABASE_URL or use individual env vars"""
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # Use connection string directly - handles special chars in password
        import re
        match = re.match(r'postgresql://([^:]+):(.+)@([^:]+):(\d+)/(.+)', database_url)
        if match:
            return {
                'host': match.group(3),
                'database': match.group(5).split('?')[0],
                'user': match.group(1),
                'password': match.group(2),
                'port': int(match.group(4))
            }
    else:
        # Fallback to individual env vars (local development)
        return {
            'host': os.getenv('DB_HOST', 'localhost'),
            'database': os.getenv('DB_NAME', 'openclaw_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'password'),
            'port': os.getenv('DB_PORT', '5432')
        }

DATABASE_CONFIG = get_database_config()

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

# CORS middleware - allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════
# SERVE FRONTEND (Static Files)
# ═══════════════════════════════════════════════════════════

# Mount static directory if it exists
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve frontend at root path
@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the main frontend HTML file"""
    if os.path.exists("static/index.html"):
        return FileResponse('static/index.html')
    else:
        return {"message": "Frontend not found. API is running at /docs"}


# ═══════════════════════════════════════════════════════════
# SERVER ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/api/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok", "message": "Server Management Portal API"}


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
                                    proxmox_password, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
            """, (
                server.name, server.ip_address, server.purpose, server.cpu_cores,
                server.ram_gb, server.disk_tb, server.status, server.proxmox_api_url,
                server.proxmox_node, server.proxmox_username, server.proxmox_password,
                server.notes
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
            
            return {
                "total_servers": total_servers,
                "total_vms": total_vms,
                "running_vms": running_vms,
                "total_projects": total_projects,
                "online_servers": online_servers
            }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
