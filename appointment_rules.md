# DocTalk Appointment Management Rules

This document outlines the rules and policies governing how appointments are scheduled, managed, and cancelled within the DocTalk application.

---

## 1. Time Slot Creation & Availability (For Doctors)
* **Required Data:** Each availability slot must have a defined start time and end time.
* **Chronological Validity:** The end time of a slot must be strictly after the start time.
* **No Past Scheduling:** Time slots cannot be created or opened for dates or times in the past.
* **Updating Availability:**
  * When a doctor updates their schedule, any existing unbooked slot that is omitted from the new schedule is automatically deactivated (disabled) to prevent future bookings.
  * Previously deactivated slots that match the new schedule are reactivated.
  * Already booked slots are preserved and cannot be deactivated or deleted by schedule updates.

---

## 2. Booking an Appointment (For Patients)
Patients can secure an appointment through one of two methods:

### A. Direct Booking (Slot-Based)
* **Requirements:** The patient must select an available, active, and unbooked time slot, and specify a reason for the consultation. They can also add an optional note.
* **Instant Confirmation:** Upon booking, the slot is marked as booked, and the appointment status is immediately set to `CONFIRMED`.
* **Double-Booking Prevention:** If another user books the slot in the split second before the patient confirms, the booking fails, and the patient is prompted to choose another available time slot.

### B. Open Request (Request-Based)
* **Requirements:** The patient selects a doctor and specifies a reason for the consultation (plus an optional note). No specific time slot is chosen.
* **Pending Status:** The appointment is created with a `PENDING` status and has no set date or time. It remains pending until the doctor acts on it.

---

## 3. Responding to Pending Requests (For Doctors)
When reviewing a patient's open request, the doctor can perform one of two actions:
* **Accept:** The doctor must assign a specific date and time for the session. Upon acceptance, the appointment is marked as `CONFIRMED`.
* **Decline / Reject:** The doctor can reject the request, setting the status to `REJECTED`, and can optionally provide an explanation message.

---

## 4. Cancelling an Appointment (Both Patients & Doctors)
* **Authorization:** An appointment can only be cancelled by the patient who requested/booked it or by the doctor assigned to it.
* **State Limit:** Only active appointments (either `PENDING` or `CONFIRMED`) can be cancelled. Appointments that are already `COMPLETED`, `CANCELLED`, or `REJECTED` cannot be cancelled.
* **Time Slot Release Policy:**
  * If a slot-based appointment is cancelled, the associated time slot is unbooked.
  * To prevent immediate automatic re-booking, the slot is also marked as **inactive**. The doctor must manually reactivate or recreate it to make it available for booking again.

---

## 5. Doctor-Patient Consultation Chat Rooms
* **Prerequisite:** A chat room between a patient and a doctor can only be created if there is a confirmed appointment between them.
* **Dynamic Chat Room Access:**
  * **No Active Consultation:** If no scheduled appointments exist, the chat is unavailable.
  * **In Consultation (Live Chat):** The chat room becomes active (highlighted in green) starting **15 minutes before** the scheduled appointment time and remains live until **30 minutes after** the scheduled time.
  * **Available for Consultation:** If a scheduled appointment exists but the current time is outside the live window, the chat room is visible (highlighted in blue) but indicates the consultation is not currently active.
* **AI Support Filtering:** Standard automated AI assistant support messages (from `doctalk-ai`) are filtered out of doctor-patient consultation rooms to keep direct human communication clean and clinical.

---

## 6. System & Database Constraints
* **One-to-One Slot Association:** Database constraints dictate that a specific time slot (`slotId`) can be linked to at most **one** appointment. This prevents double-booking at the database level.
* **Status Normalization:** The system normalizes and maps incoming status terms to standardized values:
  * `PENDING` and `REQUESTED` map to `PENDING`
  * `SCHEDULED` and `CONFIRMED` map to `CONFIRMED`
  * `DECLINED` and `REJECTED` map to `REJECTED`
* **Role-Based Permissions (RBAC):**
  * **Doctors** only: Access to create/update availability slots and accept/reject pending requests.
  * **Patients** only: Access to initiate direct bookings and submit open requests.
  * **Access Scoping**: Both roles can view their own appointments and cancel them, but they are strictly prevented from viewing or modifying appointments belonging to other users.

---

## 7. Chat Integration & Clinical Safety Guardrails
* **Triage Routing**: When patients ask questions or describe symptoms, the system runs a triage classifier. If severe emergency symptoms (like chest pain, severe bleeding, or breathing difficulties) are detected, the route is flagged as an emergency to prioritize safety.
* **Prognosis Disclaimer**: AI assistants are strictly forbidden from diagnosing patients. If the assistant attempts to output a clinical diagnosis (using trigger words like "you have", "diagnose", or "suffer from"), the message is blocked and replaced with a standard disclaimer: *"I cannot provide a definitive diagnosis. Please consult a licensed physician."*
