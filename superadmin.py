from fastapi import FastAPI, status, Response, HTTPException
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
import os

load_dotenv()

class Modules(BaseModel):
    SS: bool = True
    CT: bool = True
    BA: bool = True
    DU: bool = True
    UM: bool = True
    CR: bool = True
    SB: bool = True
    AMA: bool = True

class Access(BaseModel):
    client_list: list[str]
    studies_list: list[str]
    modules_list: list[Modules]
    entry_points_list: list[str]

class AdminData(BaseModel):
    first_name: str
    last_name: str
    email_id: str
    role: str
    group: Optional[list[str]] = None
    access: Optional[list[Access]] = None

class AdminDataUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email_id: Optional[str] = None
    role: Optional[str] = None
    group: Optional[list[str]] = None
    access: Optional[list[Access]] = None


username = os.getenv("ELASTIC_USER")
password = os.getenv("ELASTIC_PASSWORD")

es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=(username, password),
    verify_certs=False,
)

app= FastAPI()

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
        self.es.index(index="logs", document=document)

logger = Logger(es)
app= FastAPI()
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
        raise HTTPException(status_code=400, detail="Invalid role")

def is_kantar_employee(email_id: str):
    if email_id.endswith("@kantar.com"):
        return True
    else:
        return False
    


@app.get("/", status_code=status.HTTP_200_OK)
def home():
    return {"Super Admin": "Welcome to the Super Admin API!"}

@app.post("/add_user", status_code=status.HTTP_201_CREATED)
def add_user(admin_data: AdminData):
    document = admin_data.dict()
    document["is_super_admin"] = normalise_role(admin_data.role) == "superadmin"
    document["is_kantar_employee"] = is_kantar_employee(admin_data.email_id)
    document["level"] = level(normalise_role(admin_data.role))
    document["role"] = normalise_role(admin_data.role)
    document["created_at"] = datetime.now(timezone.utc).isoformat()
    document["updated_at"] = datetime.now(timezone.utc).isoformat()
    response = es.index(index="superadmin", document=document)
    return {"message": "User added successfully", "response": response}

@app.get("/users", status_code=status.HTTP_200_OK)
def get_users(role: Optional[str] = None):
    if role:
        response = es.search(
            index="superadmin",
            query={
                "term": {
                    "role": normalise_role(role)
                }
            }
        )
    else:
        response = es.search(
            index="superadmin",
            query={
                "match_all": {}
            }
        )
    return [hit["_source"] for hit in response["hits"]["hits"]]

@app.put("/update_user/{user_id}", status_code=status.HTTP_200_OK)
def update_user(user_id: str, admin_data: AdminDataUpdate):
    if not es.exists(index="superadmin", id=user_id):
        raise HTTPException(status_code=404, detail="User not found")
    
    document = admin_data.dict(exclude_unset=True)
    
    if "role" in document:
        document["is_super_admin"] = document["role"] == "super admin"
        document["level"] = level(document["role"])

    document["updated_at"] = datetime.now(timezone.utc).isoformat()

    response = es.update(
        index="superadmin",
        id=user_id,
        doc=document
    )

    return {"message": "User updated successfully", "response": response, "updated details": document}

@app.delete("/delete_user/{user_id}", status_code=status.HTTP_200_OK)
def delete_user(user_id: str):
    if not es.exists(index="superadmin", id=user_id):
        raise HTTPException(status_code=404, detail="User not found")
    response = es.delete(index="superadmin", id=user_id)

    return {"message": "User deleted successfully", "response": response}
