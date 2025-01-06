from typing import Any, Dict

from fastapi import APIRouter, Depends
from starlette.exceptions import HTTPException
from src.app.backend.database.vector_db import get_doc_store
from src.app.backend.auth.utils import get_current_user, logger
from src.app.backend.pipelines.retrieval_pipeline import Query
from src.app.backend.database.models.user import User
from src.app.backend.database.models.workspace import Workspace
from src.app.backend.database.db import get_db
from pydantic import BaseModel
from sqlalchemy.orm import Session
from urllib.error import HTTPError
router = APIRouter()

class Message(BaseModel):
    collection_name: str
    message: str

"""
// 1 - get json from db
// 2 - update json with correct counter
// 3 - store new json in db
"""


@router.get("/get_chat_history")
async def get_chat_history(
    user=Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    try:
        res = db.query(User).filter(User.id == user.id).first()
        return res.chat_history
    except Exception as e:
        raise HTTPException(
            detail=f"Error getting the chat history: {e}", status_code=404
        )


@router.post("/send_message")
async def send_message(msg: Message, db = Depends(get_db), usr = Depends(get_current_user)) -> Dict[str, Any]:
    workspace = db.query(Workspace).filter(Workspace.name == msg.collection_name).first()
    if workspace.creator_id == usr.id:
        try:
            doc_store = get_doc_store(collection_name=msg.collection_name)
            logger.info(f"Got doc store {doc_store} for collection {msg.collection_name}")

            query = Query(doc_store)
            response = query.run_pipeline(msg.message)
            return {"message": response}

        except Exception as e:
            print(e)
    else:
        raise HTTPException(status_code=401, detail="You are not authorized to access this collection")
