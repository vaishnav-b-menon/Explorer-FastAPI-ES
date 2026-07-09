from fastapi import FastAPI, status, Response, HTTPException
from pydantic import BaseModel
from elasticsearch import Elasticsearch
from datetime import datetime, timezone
from typing import Optional



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


username="elastic"
password="Ds=PF9*ft4dMXZG6794N"

es = Elasticsearch(
    "https://localhost:9200",
    basic_auth=(username, password),
    verify_certs=False,
)

app= FastAPI()

def level(role: str):
    if role == "super admin":
        return 3
    elif role == "kantar admin":
        return 2
    elif role == "client admin":
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
    is_super_admin = admin_data.role == "super admin"
    document["is_super_admin"] = is_super_admin
    document["level"] = level(admin_data.role)
    document["created_at"] = datetime.now(timezone.utc).isoformat()
    document["updated_at"] = datetime.now(timezone.utc).isoformat()
    response = es.index(index="superadmin", document=document)
    return {"message": "User added successfully", "response": response}

@app.get("/users", status_code=status.HTTP_200_OK)
def get_users():
    response = es.search(
        index="superadmin",
        query={
            "match_all": {}
        }
    )
    return [hit["_source"] for hit in response["hits"]["hits"]]
