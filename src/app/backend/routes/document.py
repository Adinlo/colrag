from fastapi import APIRouter, Depends, UploadFile, HTTPException, Form
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime

from src.app.backend.database.models.document import Document
from src.app.backend.database.models.user import User
from src.app.backend.database.models.workspace import Workspace
from src.app.backend.auth.utils import get_current_user
from src.app.backend.database.db import get_db
from src.app.backend.auth.utils import logger
from src.app.backend.documents.utils import check_existing_document
from src.app.backend.documents.models import DocumentWorkspaceProperties


router = APIRouter()


@router.post("/send_document")
async def upload_document(
    doc: UploadFile,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    properties: DocumentWorkspaceProperties = Depends(),
):
    if check_existing_document(
        doc, db=db, properties=properties, current_user_id=current_user.id
    ):
        raise HTTPException(
            status_code=401, detail=f"Document '{doc.filename}' already exists!"
        )

    workspace = None
    if properties.workspace_id:
        workspace = (
            db.query(Workspace)
            .filter(
                Workspace.id == properties.workspace_id,
                Workspace.creator_id == current_user.id,
            )
            .first()
        )
    elif properties.workspace_name:
        workspace = (
            db.query(Workspace)
            .filter(
                Workspace.name == properties.workspace_name,
                Workspace.creator_id == current_user.id,
            )
            .first()
        )

    if not workspace:
        raise HTTPException(
            status_code=404,
            detail=f"Workspace with name '{properties.workspace_name}' not found!",
        )

    document = Document(
        filename=doc.filename,
        file_path=f"dump/{doc.filename}",
        file_type=doc.filename.split(".")[-1],
        uploaded_at=datetime.now(),
        user_id=current_user.id,
        workspace_id=workspace.id,
    )

    try:
        db.add(document)
        db.commit()
        logger.info(
            f"Document '{doc.filename}' uploaded by {current_user.email} into workspace '{workspace.name}'"
        )
        return {"message": "Document uploaded successfully", "document": doc.filename}
    except Exception as e:
        db.rollback()
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Document upload failed")


@router.get(
    "/get_all"
)  # maybe add decorator to check if doc (or user, workspace etc .., is empty)
async def get_all_docs(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    documents = (
        db.query(Document)
        .join(Workspace, Document.workspace_id == Workspace.id)
        .filter(or_(Workspace.privacy == "public", Workspace.creator_id == user.id))
        .all()
    )
    if documents:
        return {
            "documents": [
                {
                    "document name": document.filename,
                    "document id": document.id,
                    "author": document.owner.username,
                    "workspace_name": (
                        document.workspace.name if documents else "No docs"
                    ),
                }
                for document in documents
            ]
        }
    else:
        raise HTTPException(status_code=404, detail="No documents found!")


@router.get("/get_document/{id}")
async def get_doc_by_id(
    id: int, user: Session = Depends(get_current_user), db: Session = Depends(get_db)
):
    document = db.query(Document).filter(User.id == user.id, Document.id == id).first()
    if document:
        return document
    else:
        raise HTTPException(status_code=404, details="No document with id: {id} found ")
