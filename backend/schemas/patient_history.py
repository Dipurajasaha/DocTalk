from datetime import datetime
from pydantic import BaseModel, Field

class PatientHistoryEntry(BaseModel):
    id: str
    patientId: str
    historyType: str
    title: str
    value: str
    source: str | None = None
    sourceId: str | None = None
    recordDate: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

class CreatePatientHistory(BaseModel):
    patientId: str
    historyType: str
    title: str
    value: str
    source: str | None = None
    sourceId: str | None = None
    recordDate: datetime | None = None

class UpdatePatientHistory(BaseModel):
    historyType: str | None = None
    title: str | None = None
    value: str | None = None
    source: str | None = None
    sourceId: str | None = None
    recordDate: datetime | None = None
