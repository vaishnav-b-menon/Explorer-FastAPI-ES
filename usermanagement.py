from fastapi import FastAPI, status, Response, HTTPException
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv,find_dotenv
import os


load_dotenv()
username = os.getenv("ELASTIC_USER")
password = os.getenv("ELASTIC_PASSWORD")

es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=(username, password),
    verify_certs=False,
)

app= FastAPI()

class Modules(BaseModel):
    SS: bool = True
    CT: bool = True
    BA: bool = True
    DU: bool = False
    UM: bool = False
    CR: bool = True
    SB: bool = True
    AMA: bool = True

class Access(BaseModel):
    client_list: Optional[list[str]] = None
    studies_list: Optional[list[str]] = None
    entrypoints_list: Optional[list[str]] = None
    modules_list: Modules

class AdminData(BaseModel):
    first_name: str
    last_name: str
    email_id: str
    role: str
    group: Optional[list[str]] = None
    access: Optional[Access] = None

class AdminDataUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email_id: Optional[str] = None
    role: Optional[str] = None
    group: Optional[list[str]] = None
    access: Optional[Access] = None

class studies(BaseModel):
    name: str
    entrypoints: Optional[list[str]]

class ClientData(BaseModel):
    name: str
    studies: Optional[list[studies]]

class Logger:
    def __init__(self, es):
        self.es = es
    def log(self, level, module,action, message, username='Vaishnav',status_code=None):
        document = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "module": module,
            "action": action,
            "message": message,
            "username": username,
            "status_code": status_code
        }
        self.es.index(index="log", document=document)

def normalise_role(role: str):
    return "".join(role.split()).lower()

def level(role: str):
    if role == "superadmin":
        return 3
    elif role == "kantaradmin":
        return 2
    elif role == "clientadmin":
        return 1
    elif role == "user":
        return 0
    else:
        app.state.logger.log("ERROR", "User Management", "Add User", f"User {role} is not valid.", username="Vaishnav", status_code=400)
        raise HTTPException(status_code=400, detail="Invalid role")
    

def is_kantar_employee(email_id: str):
    if email_id.endswith("@kantar.com"):
        return True
    else:
        return False
    

def access_validation(level, client_list: list[str],studies_list: list[str],modules_list: Modules,entrypoints_list: list[str]):
    if not client_list:
        if studies_list or entrypoints_list:
            app.state.logger.log("ERROR", "User Management", "Add User", "Client list is not provided even when studies and entrypoints are given", username="Vaishnav", status_code=400)
            raise HTTPException(
                status_code=400,
                detail="Client list must be provided if studies or entrypoints are provided"
            )
        if level == 3:
            return {
                "client_list": [],
                "studies_list": [],
                "entrypoints_list": [],
                "modules_list": module_validation(level, modules_list)
            }
        elif level == 2:
            app.state.logger.log("ERROR", "User Management", "Add User", "Client list is not provided for Kantar Admin", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail="Kantar Admin must have at least one client")
        elif level == 1:
            app.state.logger.log("ERROR", "User Management", "Add User", "Client list is not provided for Client Admin", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail="Client Admin must have at least one client" )
        elif level == 0:
            app.state.logger.log("ERROR", "User Management", "Add User", "Client list is not provided for User", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail="User must have atleast one client")
        else:
            return {"message":"Invalid Level"}
    if not studies_list:
        if entrypoints_list:
            app.state.logger.log("ERROR", "User Management", "Add User", "Study list is not provided even when entrypoints are given", username="Vaishnav", status_code=400)
            raise HTTPException(
                status_code=400,
                detail="Studies list must be provided if entrypoints are provided"
            )


    for client in client_list:
        es_clients = es.search(
        index="client",
        query={
            "term": {
                "name.keyword": client
                }
            }
        )
        clients_db = es_clients["hits"]["hits"]
        client_data = next(
            (
                hit["_source"]
                for hit in clients_db
                if hit["_source"]["name"] == client
            ),
            None
        )
        if client_data is None:
            app.state.logger.log("ERROR", "User Management", "Add User", f"Client {client} does not exist", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail=f"Client {client} does not exist")
        if studies_list:
            for study in studies_list:
                study_data = next((
                st
                for st in client_data["studies"]
                if st["name"] == study),None) 
                if study_data is None:
                    app.state.logger.log("ERROR", "User Management", "Add User", f"Study {study} does not exist for client {client}", username="Vaishnav", status_code=400)
                    raise HTTPException(status_code=400,detail=f"Study {study} does not exist for client {client}")
                if entrypoints_list:
                    for entrypoint in entrypoints_list:
                        if entrypoint not in study_data["entrypoints"]:
                            app.state.logger.log("ERROR", "User Management", "Add User", f"Entrypoint {entrypoint} does not exist for client {client}", username="Vaishnav", status_code=400)
                            raise HTTPException(status_code=400,detail=f"Entrypoint {entrypoint} does not exist for the study {study} of client {client}")
    return {
        "client_list": client_list,
        "studies_list": studies_list,
        "entrypoints_list": entrypoints_list,
        "modules_list": module_validation(level, modules_list)
    }

def module_validation(level, modules_list=None):
    if level==3:
            return { "SS": True, "CT": True, "BA": True, "DU": True, "UM": True, "CR": True, "SB": True, "AMA": True }
    elif level==2:
        if modules_list.DU is True or modules_list.UM is True:
            app.state.logger.log("ERROR", "User Management", "Add User", "Kantar Admin cannot have access to Data Upload or User Management modules", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail="Kantar Admin cannot have access to Data Upload or User Management modules")
        else:
            return modules_list.dict()
    elif level==1:
        if modules_list.DU is True or modules_list.UM is True:
            app.state.logger.log("ERROR", "User Management", "Add User", "Client Admin cannot have access to Data Upload or User Management modules", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail="Client Admin cannot have access to Data Upload or User Management modules")
        else:
            return modules_list.dict()
    elif level==0:
        if modules_list.DU is True or modules_list.UM is True:
            app.state.logger.log("ERROR", "User Management", "Add User", "User cannot have access to Data Upload or User Management modules", username="Vaishnav", status_code=400)
            raise HTTPException(status_code=400, detail="User cannot have access to Data Upload or User Management modules")
        else:
            return modules_list.dict()
    else:
        return {"message": "Invalid role"}

def email_check(document: dict):
    users = es.search(
        index="admin",
        query={
            "term": {
                "email_id.keyword": document["email_id"]
            }
        }
    )

    if users["hits"]["hits"]:
        app.state.logger.log("ERROR","User Management","Add User",f"The user with {document['email_id']} email id already exists",username="Vaishnav",status_code=409)
        raise HTTPException(status_code=409,detail=f"The user with {document['email_id']} email id already exists")


@app.on_event("startup")
def startup_event():
    app.state.logger = Logger(es)
    app.state.logger.log("INFO", "Startup", "Application Startup", "FastAPI application has started successfully.")

@app.on_event("shutdown")
def shutdown_event():
    app.state.logger.log("INFO", "Shutdown", "Application Shutdown", "FastAPI application is shutting down.")

@app.get("/", status_code=status.HTTP_200_OK)
def home():
    return {"Super Admin": "Welcome to the Super Admin API!"}

@app.post("/add_user", status_code=status.HTTP_201_CREATED)
def add_user(admin_data: AdminData):
    document = admin_data.dict()
    email_check(document)
    document["is_kantar_employee"] = is_kantar_employee(admin_data.email_id)
    document["level"] = level(normalise_role(admin_data.role))
    document["role"] = normalise_role(admin_data.role)
    document["created_at"] = datetime.now(timezone.utc).isoformat()
    document["updated_at"] = datetime.now(timezone.utc).isoformat()
    document["access"] = access_validation(
        level=document["level"] if document["level"] is not None else 0,
        client_list=admin_data.access.client_list if admin_data.access else [],
        studies_list=admin_data.access.studies_list if admin_data.access else [],
        entrypoints_list=admin_data.access.entrypoints_list if admin_data.access else [],
        modules_list=admin_data.access.modules_list if admin_data.access else None
    )
    response = es.index(index="admin", document=document)
    app.state.logger.log("INFO", "User Management", "Add User", f"User {admin_data.email_id} added successfully.", username="Vaishnav", status_code=201)
    return {"message": "User added successfully", "response": response}

@app.get("/users", status_code=status.HTTP_200_OK)
def get_users(role: Optional[str] = None):
    if role:
        response = es.search(
            index="admin",
            query={
                "term": {
                    "role": normalise_role(role)
                }
            }
        )
        app.state.logger.log("INFO", "User Management", "Get Users", f"Retrieved users with role {role} successfully.", username="Vaishnav", status_code=200)
    else:
        response = es.search(
            index="admin",
            query={
                "match_all": {}
            }
        )
        app.state.logger.log("INFO", "User Management", "Get Users", f"Retrieved all users successfully.", username="Vaishnav", status_code=200)

    return [hit for hit in response["hits"]["hits"]]

@app.put("/update_user/{user_id}", status_code=status.HTTP_200_OK)
def update_user(user_id: str, admin_data: AdminDataUpdate):
    if not es.exists(index="admin", id=user_id):
        app.state.logger.log("ERROR", "User Management", "Update User", f"User {user_id} not found for update.", username="Vaishnav", status_code=404)
        raise HTTPException(status_code=404, detail="User not found")
        
    document = admin_data.dict(exclude_unset=True)
    
    if "role" in document:
        document["is_super_admin"] = document["role"] == "superadmin"
        document["level"] = level(document["role"])

    document["updated_at"] = datetime.now(timezone.utc).isoformat()

    response = es.update(
        index="admin",
        id=user_id,
        doc=document
    )
    app.state.logger.log("INFO", "User Management", "Update User", f"User {user_id} updated successfully.", username="Vaishnav", status_code=200)

    return {"message": "User updated successfully", "response": response, "updated details": document}

@app.delete("/delete_user/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(user_id: str):
    if not es.exists(index="admin", id=user_id):
        raise HTTPException(status_code=404, detail="User not found")
    response = es.delete(index="admin", id=user_id)
    app.state.logger.log("INFO", "User Management", "Delete User", f"User {user_id} deleted successfully.", username="Vaishnav", status_code=200)
    return {"message": "User deleted successfully", "response": response}


@app.get("/logs", status_code=status.HTTP_200_OK)
def get_logs():
    response = es.search(
        index="log",
        query={
            "match_all": {}
        },
        sort=[
            {"timestamp": {"order": "desc"}}
        ]
    )
    app.state.logger.log("INFO", "Log Management", "Get Logs", f"Retrieved all logs successfully.", username="Vaishnav", status_code=200)
    return [hit["_source"] for hit in response["hits"]["hits"]]


@app.post("/add_client", status_code=status.HTTP_200_OK)
def add_client(client_data: ClientData):
    document = client_data.dict()
    response = es.index(index="client", document=document)
    app.state.logger.log("INFO", "Client Management", "Add Client", f"Client {document['name']} added successfully.", username="Vaishnav", status_code=201)
    return {"message": "Client added successfully", "response": response}

@app.get("/clients", status_code=status.HTTP_200_OK)
def get_clients():
    response = es.search(
        index="client",
        query={
            "match_all": {}
        }
    )
    app.state.logger.log("INFO", "Client Management", "Get Clients", f"Retrieved all clients successfully.", username="Vaishnav", status_code=200)
    return [hit["_source"] for hit in response["hits"]["hits"]]

