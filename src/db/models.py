from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from sqlalchemy import Column, TIMESTAMP, text
from zoneinfo import ZoneInfo
from enum import Enum

class TipoEstoque(str, Enum):
    ENTRADA = "Entrada"
    SAIDA = "Saída"
    BALANCO = "Balanço"

class Deposito(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str = Field(index=True, unique=True, max_length=100)
    tipo: str = Field(default="Próprio", max_length=50)
    observacoes: Optional[str] = Field(default=None, max_length=200)
    
    estoques: List["Estoque"] = Relationship(back_populates="deposito")

class Produto(SQLModel, table=True):
    sku: str = Field(primary_key=True, max_length=50)
    nome: str = Field(index=True, max_length=200)
    descricao: Optional[str] = Field(default=None, max_length=500)
    
    estoques: List["Estoque"] = Relationship(back_populates="produto")

class Estoque(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sku: str = Field(foreign_key="produto.sku")
    deposito_id: int = Field(foreign_key="deposito.id")
    quantidade: int
    tipo: str = Field(default="Entrada", max_length=50)
    data_hora: datetime = Field(
        default_factory=lambda: datetime.now(ZoneInfo("America/Sao_Paulo")),
        sa_column=Column(TIMESTAMP(timezone=True))
    )
    observacoes: Optional[str] = Field(default=None, max_length=200)
    saldo: int = Field(default=0)
    
    produto: Produto = Relationship(back_populates="estoques")
    deposito: Deposito = Relationship(back_populates="estoques")

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