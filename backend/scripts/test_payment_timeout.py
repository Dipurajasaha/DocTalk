import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from backend.core.database import prisma
from backend.services.payment_service import PaymentService

async def test_payment_timeout():
    await prisma.connect()
    try:
        print("Starting test_payment_timeout...")
        # 1. Fetch a doctor and an available slot
        doctor = await prisma.doctor.find_first()
        if not doctor:
            print("No doctor found.")
            return

        slot = await prisma.doctorslot.find_first(where={"doctorId": doctor.doctorId, "isBooked": False})
        if not slot:
            print("No available slot found for testing.")
            return

        patient = await prisma.patient.find_first()
        if not patient:
            print("No patient found.")
            return

        print(f"Testing with Patient: {patient.username}, Doctor: {doctor.name}, Slot: {slot.id}")

        service = PaymentService(prisma)

        # 2. Call create_order_for_appointment (this will lock the slot and schedule the timeout)
        # We will mock the Razorpay client to avoid actual API calls?
        # Let's just create an appointment manually and call _schedule_payment_timeout directly.
        # This is a unit test of the timeout logic.
        
        print("Creating mock appointment...")
        await prisma.doctorslot.update(where={"id": slot.id}, data={"isBooked": True})
        
        appointment = await prisma.appointment.create(
            data={
                "patientUsername": patient.username,
                "doctorId": doctor.doctorId,
                "slotId": slot.id,
                "appointmentDate": slot.startTime,
                "scheduledTime": slot.startTime,
                "reason": "Test timeout",
                "status": "PAYMENT_PENDING",
                "amountPaise": 50000,
            }
        )
        
        payment = await prisma.payment.create(
            data={
                "id": "test_payment_123",
                "appointmentId": appointment.id,
                "razorpayOrderId": "order_test_123",
                "amountPaise": 50000,
                "currency": "INR",
                "status": "CREATED",
            }
        )

        print(f"Appointment created with ID {appointment.id}, Slot locked.")

        # Verify slot is booked
        slot_check = await prisma.doctorslot.find_unique(where={"id": slot.id})
        assert slot_check.isBooked is True
        print("Verified slot is initially booked.")

        # 3. Call _schedule_payment_timeout with a short timeout (e.g., 3 seconds)
        print("Waiting for 3 seconds timeout...")
        await service._schedule_payment_timeout(appointment.id, slot.id, timeout_seconds=3)

        # 4. Verify the appointment was cancelled and the slot was released
        appt_check = await prisma.appointment.find_unique(where={"id": appointment.id})
        slot_final = await prisma.doctorslot.find_unique(where={"id": slot.id})
        pay_check = await prisma.payment.find_unique(where={"id": payment.id})

        print(f"Final Appointment Status: {appt_check.status}")
        print(f"Final Payment Status: {pay_check.status}")
        print(f"Final Slot Booked: {slot_final.isBooked}")

        assert appt_check.status == "CANCELLED"
        assert pay_check.status == "FAILED"
        assert slot_final.isBooked is False

        print("SUCCESS! Timeout correctly cancelled appointment, failed payment, and released slot.")

    finally:
        await prisma.disconnect()

if __name__ == "__main__":
    asyncio.run(test_payment_timeout())
