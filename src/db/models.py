from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, TIMESTAMP, text
from zoneinfo import ZoneInfo
from enum import Enum

class EstoqueMercos(SQLModel, table=True):
    __tablename__ = "estoque_mercos"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(max_length=50)
    produto: str = Field(max_length=200)
    deposito: str = Field(max_length=100)
    quantidade: int
    data_atualizacao: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    )

class ConciliacaoMercos(SQLModel, table=True):
    __tablename__ = "conciliacao_mercos"

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_mercos: str = Field(max_length=50)
    sku_ml_amazon: str = Field(max_length=50)
    produto: str = Field(max_length=200)
    deposito_mercos: str = Field(max_length=100)
    estoque_mercos: int
    data_atualizacao: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    )