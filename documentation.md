# DocTalk Architecture Source of Truth

This file is the strict backend architecture contract for DocTalk.

It is the reference that future code generation, refactors, and feature work must follow to avoid schema drift, route fragmentation, and ID corruption.

If any implementation choice conflicts with this file, this file wins.

## 0. Non-Negotiable Principles

- Preserve a flat backend layout.
- Preserve a unified routing surface.
- Preserve the current Prisma model boundaries.
- Preserve the separation between persistent database IDs, role-specific login identifiers, and temporary frontend AI thread identifiers.
- Never invent a new schema layer, wrapper app folder, or parallel route tree to solve a feature.

## 1. Core Architecture and Routing

### 1.1 Flat Backend Structure

The backend must remain flat under `/backend`.

Allowed top-level backend areas include:

- `/backend/api`
- `/backend/services`
- `/backend/schemas`
- `/backend/core`
- `/backend/workflows`
- `/backend/ai`

The backend must not introduce a nested `/app` folder or an alternate application root.

All new business logic must be placed in the appropriate existing backend layer:

- API routing in `/backend/api`
- domain logic in `/backend/services`
- request/response models in `/backend/schemas`
- infrastructure/config/security in `/backend/core`
- orchestration and graph logic in `/backend/workflows`
- AI-specific helpers in `/backend/ai`

### 1.2 Unified Routing Prefix Rule

The canonical public API prefixes are:

- Auth: `/api/auth`
- Users: `/api/users`
- Appointments: `/api/appointments`
- Assets: `/api/assets`
- Chat: `/api/chat`

These prefixes are the only default surfaces for future code generation.

Do not generate alternate core prefixes such as:

- `/api/doctor/*` for primary appointment flows
- `/api/patient/*` for primary booking flows
- `/api/profile/*` as a replacement for `/api/users`
- `/api/file/*` as a replacement for `/api/assets`

If a route does not fit one of the canonical prefixes, it must be explicitly justified and treated as exceptional, not as a default pattern.

### 1.3 Route Responsibilities

- `/api/auth` owns login and registration only.
- `/api/users` owns authenticated profile retrieval and profile updates.
- `/api/appointments` owns slot creation, slot listing, direct booking, open booking, appointment actions, cancellation, and appointment lifecycle operations.
- `/api/assets` owns medical file upload, listing, download, rename, delete, and attachment flows.
- `/api/chat` owns consultation-thread AI interactions and message exchange.

### 1.4 Frontend-Visible Contract

The frontend pages currently depend on the following expectations:

- `Login.jsx` toggles between patient and doctor modes and submits a role-aware auth payload.
- `DoctorDashboard.jsx` manages slots, pending requests, confirmed sessions, and action buttons for accept, reject, complete, and cancel behaviors.

Any backend change that breaks those flows is a contract regression.

## 2. Prisma Schema Contract

The current Prisma schema does not define a single unified `User` table.

Instead, the database is anchored by role-specific records and related operational tables.

### 2.1 Persistent Anchors in Prisma

- `Patient.username` is the primary key for patient records.
- `Doctor.doctorId` is the primary key for doctor records.
- `DoctorSlot.id` is the primary key for a doctor availability block.
- `Appointment.id` is the primary key for a booking record.
- `Consultation.id` is the primary key for a persisted consultation record.
- `Message.id` is the primary key for a chat message.
- `FileKey.id` is the primary key for encrypted file-key records.
- `Report.id`, `Prescription.id`, and `MedicalImage.id` are the primary keys for uploaded assets.

### 2.2 Relationship Boundaries

- `Appointment.patientUsername` references `Patient.username`.
- `Appointment.doctorId` references `Doctor.doctorId`.
- `Appointment.slotId` references `DoctorSlot.id` and is optional.
- `Consultation.appointmentId` references `Appointment.id` and is unique.
- `Consultation.patientUsername` references `Patient.username`.
- `Consultation.doctorId` references `Doctor.doctorId`.

This means the system already has two independent identity anchors for the two actor types.

Do not collapse them into a fake shared foreign key unless the Prisma schema is explicitly redesigned.

### 2.3 Schema Corruption Rule

Code generation must not invent new Prisma tables, synthetic ID columns, or shadow relationship models to solve auth, booking, or chat problems.

If a feature needs new persistence, it must be modeled against the existing schema boundaries or added through a deliberate schema migration.

## 3. Unified Authentication and Polymorphic Schemas

### 3.1 Authentication Model

`/api/auth/login` must handle both doctors and patients through a single endpoint.

The backend must not force separate login endpoints for each role.

The client may identify the role explicitly, but the request schema must remain flexible enough to accept the identifiers already used by the frontend and by future clients.

### 3.2 LoginRequest Schema Rule

The `LoginRequest` schema must make identifier fields optional so the payload does not break when a client sends a different valid identifier shape.

It must accept any of the following as the principal identifier:

- `username`
- `email`
- `doctor_id`

The payload must always include `password`.

Recommended logical shape:

```json
{
	"username": "optional",
	"email": "optional",
	"doctor_id": "optional",
	"password": "required",
	"role": "optional"
}
```

Rules:

- At least one identifier must be present.
- The backend must normalize the identifier and authenticate the matching record.
- The schema must not require all identifier fields.
- The schema must not reject a valid login because the client used `doctor_id` instead of `username`, or vice versa.

### 3.3 Login Resolution Rules

- Patient login resolves against the patient identity path.
- Doctor login resolves against the doctor identity path.
- The server should use the submitted identifier, not an assumed field name hardcoded to one role.
- The login endpoint must return a token payload that can be consumed by JWT middleware and session hydration.

The frontend login page currently sends:

- `{ username, password }` for patients
- `{ doctor_id, password }` for doctors

The backend must remain compatible with that behavior.

### 3.4 Register Flow and Polymorphic Role Contract

`/api/auth/register` uses a required `role` field with the values:

- `patient`
- `doctor`

The registration body must be polymorphic by role.

#### Patient registration

When `role = "patient"`, the backend must require the standard patient data used by the application, including the patient login identifier and profile fields.

The current frontend collects patient-facing data such as:

- `username`
- `name`
- `dob`
- `gender`
- `blood_group`
- `mobile`
- `address`
- `password`

The backend should persist the patient profile into Prisma without inventing a separate doctor-style profile path.

#### Doctor registration

When `role = "doctor"`, the backend must require doctor-specific data and must create the associated `Doctor` record in Prisma.

Doctor registration must require and process, at minimum, the doctor-specific inputs the frontend is already collecting:

- `doctor_id`
- `name`
- `password`
- `registration_number`
- `hospital_name`
- `hospital_location`
- `specialization`

Additional doctor profile fields present in Prisma, such as `category`, `location`, `address`, `bio`, `displayName`, `gender`, or `profilePic`, may be accepted if supplied, but they do not replace the mandatory doctor registration fields.

### 3.5 Registration Transaction Rule

Doctor registration must create the `Doctor` record in the same logical operation as the registration flow.

Do not create a partial doctor account that leaves the identity record half-initialized.

If the implementation ever introduces a shared auth record in the future, that auth record and the role-specific record must still be created atomically.

### 3.6 Frontend Compatibility Rule

The frontend currently expects auth payloads that use role-aware identifier names.

The backend must tolerate those field names and must not force the frontend to rename them before authentication works.

## 4. The ID Dictionary

This section defines the meaning and boundaries of every important identifier.

| Identifier | Meaning | Source | Allowed Use |
| --- | --- | --- | --- |
| `userId` | The canonical authenticated principal anchor exposed by JWT middleware | JWT / session layer | Read from auth context only; never accept from request bodies |
| `doctor_id` | Doctor login and registration identifier string | Auth payload / doctor form | Used to locate or create the doctor identity record |
| `doctorId` | Prisma doctor primary key and service-layer doctor anchor | Prisma `Doctor.doctorId` | Used for backend relations and service lookups |
| `slotId` | A doctor's available time block | Prisma `DoctorSlot.id` | Used to book or manage availability |
| `appointmentId` | The booking record for a consultation event | Prisma `Appointment.id` | Used for booking lifecycle and doctor actions |
| `assetId` | UUID of an uploaded file | Prisma asset record id | Used to fetch, rename, delete, or attach an asset |
| `consultationId` | Temporary frontend/LangGraph thread identifier used exclusively in chat flows | Frontend chat orchestration | Used only for `/api/chat` and LangGraph thread routing |

### 4.1 `userId`

`userId` is the primary authenticated identity anchor.

Rules:

- It is extracted from JWT middleware.
- It must not be passed in request bodies.
- It must not be treated as a booking identifier.
- It must not be overloaded to mean `appointmentId`, `slotId`, `doctorId`, or any asset identifier.

Important nuance:

- The current Prisma schema does not expose a dedicated `User` table.
- Therefore, `userId` is a logical auth-layer concept, not a schema field to invent by default.

### 4.2 `doctor_id` vs `doctorId`

These two names are related but not interchangeable.

- `doctor_id` is the external API field used by doctors in login and register payloads.
- `doctorId` is the internal Prisma and service-layer identifier for the doctor record.

Implementation should normalize `doctor_id` into `doctorId` after validation.

Do not expose both as competing canonical identifiers in the same layer.

### 4.3 `slotId`

`slotId` identifies one doctor availability block.

Rules:

- It exists before a booking is created.
- It represents an available time block owned by a doctor.
- It must not be used as a consultation thread identifier.
- It must not be reused across multiple appointments.

### 4.4 `appointmentId`

`appointmentId` identifies the booking agreement.

Rules:

- Every appointment has one booking record id.
- Direct bookings have a `slotId`.
- Open requests have a null `slotId` until a doctor assigns or confirms scheduling.
- `appointmentId` is not a chat thread id.

### 4.5 `assetId`

`assetId` identifies a stored file record.

It is used only for file-oriented operations such as:

- fetch
- rename
- delete
- attach to a consultation

It must never be treated as a medical record user id or appointment id.

### 4.6 `consultationId`

`consultationId` is a temporary frontend thread identifier used exclusively by LangGraph AI in `POST /api/chat`.

Rules:

- It is not the appointment id.
- It is not the patient username.
- It is not the doctor id.
- It is not the asset id.
- It is not a substitute for the Prisma `Consultation.id` relation key unless an explicit adapter maps them.

The backend must keep the distinction between the frontend thread identifier and the persisted consultation row.

## 5. Appointment Workflow Rules

### 5.1 Core Workflow Overview

Appointments move through two patient booking modes and then into doctor management.

The backend must preserve the distinction between:

- a booking tied to an existing slot
- a booking request that waits for a doctor decision

### 5.2 Patient Booking Mode 1: Direct Book

Direct Book is a slot-backed booking.

Rules:

- `slotId` is required.
- The slot must already exist.
- The slot must belong to the selected doctor.
- The slot must be available for booking.
- The appointment is created as a concrete scheduled interaction tied to that slot.

Direct Book is the correct mode when the patient selects a known open time block.

### 5.3 Patient Booking Mode 2: Open Request

Open Request is a doctor-directed request.

Rules:

- `slotId` is null or omitted.
- The request enters a pending state.
- The doctor later accepts or rejects the request.
- The request is not a confirmed slot reservation at creation time.

Open Request is the correct mode when the patient wants care from a doctor but does not yet have a fixed time block.

### 5.4 Doctor Slot Management

Doctors own availability through `DoctorSlot` records.

The doctor dashboard behavior shows that doctors must be able to:

- create availability blocks
- view them on a calendar
- toggle open vs booked slot state
- save open slots in bulk
- see booked slots as unavailable

Slot lifecycle rules:

- A slot is created before it is booked.
- A slot may be open or booked.
- Once booked, it should not be presented as open.
- A booked slot must remain tied to the appointment that consumed it.

### 5.5 Doctor Action on Open Requests

Doctors manage open requests through explicit actions.

The doctor dashboard expects two actions:

- Accept
- Reject

Rules for Accept:

- The doctor must choose a date/time assignment when required.
- The request becomes a confirmed scheduled appointment.
- The backend should persist the scheduling outcome in the appointment record using the schema fields available for scheduling.
- The request must no longer remain in the pending queue after it has been accepted.

Rules for Reject:

- The request is declined by the doctor.
- The appointment must transition out of the pending queue.
- The backend must store the rejection result clearly enough for dashboard history and auditability.

### 5.6 Appointment Status Contract

The frontend dashboard currently treats the following as request-like statuses:

- `pending`
- `requested`
- `awaiting`

The backend should keep those values consistent where they are already used.

The action API must be able to drive the appointment through the visible lifecycle states used by the dashboard:

- pending or requested state while waiting on doctor review
- accepted or confirmed state after doctor approval
- rejected state after doctor decline
- completed state after the consultation is finished
- cancelled state when the session is withdrawn

Do not generate a second hidden status vocabulary unless it is explicitly mapped to the one above.

### 5.7 Appointment Action Endpoint Contract

The canonical doctor action endpoint is:

- `PUT /api/appointments/{id}/action`

That endpoint is the place where doctor decisions are applied.

The action payload must support the accept/reject workflow used by the dashboard and must not require the frontend to branch into different endpoints for simple status changes.

### 5.8 Integrity Rules for Booking

- Do not create an appointment without a valid patient anchor.
- Do not attach a slot to an appointment unless that slot exists.
- Do not allow one slot to be consumed by more than one appointment.
- Do not use a null `slotId` for a direct booking.
- Do not force a slot into an open request when the patient never selected one.

## 6. Chat and Consultation Boundary

The chat surface belongs under `/api/chat`.

The frontend and AI orchestration must keep the following rule intact:

- `consultationId` in the frontend/AI flow is a thread identifier.
- `appointmentId` is the booking record.
- These are distinct values.

The backend must not replace one with the other.

The LangGraph AI integration may read or adapt consultation context, but it must respect the identifier boundary and must not contaminate appointment or asset identity with chat thread identity.

## 7. Assets and File Handling

The canonical asset prefix is `/api/assets`.

Asset categories are:

- medical images
- reports
- prescriptions

Each asset must be represented by an `assetId` from the file record and may be stored on disk under the application file tree.

Rules:

- Use asset endpoints for file lifecycle operations.
- Do not push file lifecycle operations into appointment routes.
- Do not use appointment ids as file ids.
- Do not expose file storage implementation details as public API identifiers.

## 8. Code Generation Guardrails

When generating backend or schema code, follow these rules:

- Keep business logic in the existing flat backend layers.
- Keep `/api/auth`, `/api/users`, `/api/appointments`, `/api/assets`, and `/api/chat` as the canonical public prefixes.
- Keep auth polymorphic and role-aware.
- Keep identifier fields optional where the frontend may send alternative valid shapes.
- Keep `doctor_id`, `doctorId`, `slotId`, `appointmentId`, `assetId`, `consultationId`, and `userId` semantically separated.
- Keep doctor registration responsible for creating the doctor record.
- Keep appointment booking mode explicit: direct slot booking versus open request.
- Keep doctor slot management separate from patient request submission.

## 9. Implementation Summary

The strict mental model is:

- Auth identifies the actor.
- Role-specific Prisma records hold the persistent profile identity.
- Slots represent availability.
- Appointments represent booking agreements.
- Assets represent files.
- Consultations represent chat context and must remain separate from bookings.

If a future change blurs those boundaries, it is a design bug, not a harmless refactor.
