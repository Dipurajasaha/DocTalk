# Patient History → Patient Dashboard — Focused Plan

> Derived from `newUiPlan.md` (premium neumorphic AI healthcare theme) and the specific
> request: convert the **patient history** panel into a **Patient Dashboard** with 4 sections.
> Constraint: **take ONLY the vitals section from patient history for the dashboard**, and
> **do not change any other section/panel**.

## Scope guardrails
- **Only** the `history` panel is reworked: `PatientDashboard.jsx` render block at
  `frontend/src/pages/PatientDashboard.jsx:1606` (the `activePanel === 'history'` IIFE).
- **No changes** to: chat (`explain`), documents, xray, appointments, docchat, profile panels;
  backend; API; routing; `VALID_PANELS`; auth; folder structure; right analysis panel; sidebar items.
- The sidebar button for this panel already reads `Dashboard` (`PatientDashboard.jsx:1587-1592`),
  and its panel key stays `history` (so `?panel=history` links keep working).

## Already wired (reuse, do not re-add)
- `healthView` state — `PatientDashboard.jsx:238` (currently unused in render; `'dashboard' | 'record'`).
- `prescriptionsList`, `prescriptionsLoading` + `loadPrescriptions()` using
  `prescriptionApi.listMine()` — `PatientDashboard.jsx:239-253`.
- On `activePanel === 'history'` the effect already calls `loadAppointments()` + `loadPrescriptions()`
  — `PatientDashboard.jsx:444-447`.
- All source data already in component state: `vitals`, `conditions`, `medications`,
  `allergies`, `surgeries`, `appointments`, `prescriptionsList`.

## The Dashboard (replaces the tabbed "Medical Profile" block)
Replace the `TABS`/`medTab` tabbed UI (lines 1634-173, and the `{medTab === ...}` branches
through the end of the `history` IIFE) with a single **Dashboard** view containing 4 sections.
Keep a small **"Manage Record ▸"** link that flips `healthView` to `'record'`, which renders the
EXISTING tabbed editor unchanged (so add/edit/delete workflows for vitals/conditions/etc. survive).

### 1. Health Overview — built ONLY from the `vitals` section
Use `vitals` state. Neumorphic stat cards (do **not** pull conditions/meds/allergies here):
Blood Group, Height/Weight, BMI (via existing `bmiCalc`), Blood Pressure, Heart Rate, SpO₂,
Temperature, Fasting/PP Sugar. Include the existing **✏️ Edit Vitals** action (reuses
`editingVitals`/`vitalsForm`/`saveVitals` — `PatientDashboard.jsx:261-268`, `:1776-1837`).
This satisfies "take only vitals section from patient history to make the dashboard".

### 2. Highlights of Medical History
Compact 3-card row from existing non-vitals state:
- **Active Conditions** — `conditions.filter(c=>c.status==='active'||c.status==='chronic')` (top 3).
- **Current Medications** — `medications.filter(m=>m.is_ongoing)` (top 3).
- **Allergies** — `allergies` (top 3, severity pill).
Each card shows count + first few entries + a `Manage` button → `setHealthView('record')`.

### 3. Upcoming Appointments
Reuse `appointments` from `loadAppointments()` (`PatientDashboard.jsx:543`). Filter to
`status === 'scheduled' || status === 'confirmed'` and sort by `scheduled_time` ascending
(reuse `getDoctorChatStatus`/`renderSlotLabel` helpers already present). Show doctor, time,
status pill, and a `Book New` button → `setActivePanelFromNav('appointments')`.
Empty state: CTA card "No upcoming appointments".

### 4. Latest Prescription (or minimized fallback)
Take `prescriptionsList` (from `loadPrescriptions()`), sort by `issuedAt` desc, pick latest.
Render: `prescriptionNumber`, `doctorName`, date, top medicines (`p.medicines.slice(0,3)`),
`sickNote` flag, **Download PDF** (`prescriptionApi.pdfUrl(p.id)`) and **Verify** buttons.
- **If `prescriptionsList` is empty / none:** show a **minimized Wellness card** instead
  (health tip + quick links: Book Appointment / Ask AI Assistant). This satisfies
  "otherwise change to others thing or minimize".

## Theme (neumorphism per `newUiPlan.md`)
- Palette: bg `#F5F5F7`, primary `#7C5CFF`, accent `#A88CFF`, text `#1C1C1E`, secondary `#6E6E73`.
- Cards: dual box-shadow `8px 8px 18px rgba(209,209,214,.6)`, `-8px -8px 18px rgba(255,255,255,.9)`,
  20–24px radius, hairline `rgba(255,255,255,.6)` border.
- Update `.main-content` background to `#F5F5F7` with a very subtle fluid gradient overlay
  (in `frontend/src/styles/patient.css`). Primary buttons use the purple gradient; active sidebar
  item keeps the pressed neumorphic accent. Thin rounded scrollbars + soft hover scale.
- Reuse existing local `S` style object at `:1608` as the base, swapping to neumorphic tokens.

## Files touched
- `frontend/src/pages/PatientDashboard.jsx` — replace `history` IIFE render with the 4-section
  dashboard + the `healthView === 'record'` fallback to the existing tabbed editor.
- `frontend/src/styles/patient.css` — add neumorphic tokens, gradient background, scrollbar.

## Verification
- Project build/lint passes (e.g. `npm run build`).
- Open `/patient/dashboard?panel=history` → see the 4 dashboard sections.
- Vitals Edit works; `Manage Record` opens the full tabbed editor with all forms intact.
- Book an appointment then reload → appears under Upcoming Appointments.
- With a prescription present → Latest Prescription populates (Download/Verify work);
  without one → minimized Wellness card shows instead.
