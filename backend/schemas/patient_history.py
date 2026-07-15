from datetime import datetime
from typing import Any
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

class PatientHistoryRecord(BaseModel):
    id: str
    patientId: str
    bloodGroup: str | None = None
    weight: str | None = None
    bmi: str | None = None
    bloodPressure: str | None = None
    heartRate: str | None = None
    spo2: str | None = None
    temperature: str | None = None
    bloodSugarFasting: str | None = None
    bloodSugarPP: str | None = None
    conditions: list[dict[str, Any]] | None = None
    medications: list[dict[str, Any]] | None = None
    allergies: list[dict[str, Any]] | None = None
    recordDate: datetime | None = None
    createdAt: datetime
    updatedAt: datetime

class CreatePatientHistoryRecord(BaseModel):
    bloodGroup: str | None = None
    weight: str | None = None
    bmi: str | None = None
    bloodPressure: str | None = None
    heartRate: str | None = None
    spo2: str | None = None
    temperature: str | None = None
    bloodSugarFasting: str | None = None
    bloodSugarPP: str | None = None
    conditions: list[dict[str, Any]] | None = None
    medications: list[dict[str, Any]] | None = None
    allergies: list[dict[str, Any]] | None = None
    recordDate: datetime | None = None

class UpdatePatientHistoryRecord(BaseModel):
    bloodGroup: str | None = None
    weight: str | None = None
    bmi: str | None = None
    bloodPressure: str | None = None
    heartRate: str | None = None
    spo2: str | None = None
    temperature: str | None = None
    bloodSugarFasting: str | None = None
    bloodSugarPP: str | None = None
    conditions: list[dict[str, Any]] | None = None
    medications: list[dict[str, Any]] | None = None
    allergies: list[dict[str, Any]] | None = None
    recordDate: datetime | None = None
