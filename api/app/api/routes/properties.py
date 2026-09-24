from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Property
from app.schemas.property import PropertyOut, PropertySearchParams, PropertySearchResult
from app.services.property_search import search_properties

router = APIRouter(prefix="/properties", tags=["imóveis"])


@router.get("", response_model=list[PropertySearchResult])
def list_properties(params: Annotated[PropertySearchParams, Query()], db: Session = Depends(get_db)):
    return search_properties(db, params)


@router.post("/search", response_model=list[PropertySearchResult])
def search(params: PropertySearchParams, db: Session = Depends(get_db)):
    return search_properties(db, params)


@router.get("/{property_id}", response_model=PropertyOut)
def get_property(property_id: str, db: Session = Depends(get_db)):
    prop = db.get(Property, property_id)
    if not prop:
        raise HTTPException(404, "Imóvel não encontrado")
    return prop
