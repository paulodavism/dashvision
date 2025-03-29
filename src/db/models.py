from sqlmodel import SQLModel, Field, registry
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, TIMESTAMP, text

# Criar um registro explícito para evitar conflitos
mapper_registry = registry()
Base = mapper_registry.generate_base()

class EstoqueMercos(Base, table=True):
    __tablename__ = "estoque_mercos"
    __table_args__ = {'extend_existing': True}
    
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(max_length=50)
    produto: str = Field(max_length=200)
    deposito: str = Field(max_length=100)
    quantidade: int
    data_atualizacao: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    )

class ConciliacaoMercos(Base, table=True):
    __tablename__ = "conciliacao_mercos"
    __table_args__ = {'extend_existing': True}

    id: Optional[int] = Field(default=None, primary_key=True)
    sku_mercos: str = Field(max_length=50)
    sku_ml_amazon: str = Field(max_length=50)
    produto: str = Field(max_length=200)
    deposito_mercos: str = Field(max_length=100)
    estoque_mercos: int
    data_atualizacao: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), server_default=text('CURRENT_TIMESTAMP'))
    )