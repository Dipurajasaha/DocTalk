/**
 * RazorpayCheckout
 *
 * Dynamically loads the Razorpay checkout script, opens the payment popup,
 * and returns the result to the parent component via callbacks.
 *
 * Props:
 *   order        – { order_id, amount, currency, key_id, appointment_id }
 *   patientName  – displayed in the checkout modal
 *   patientEmail – pre-filled email
 *   patientPhone – pre-filled phone
 *   onSuccess(paymentResult) – called with { razorpay_order_id, razorpay_payment_id, razorpay_signature }
 *   onFailure(error)  – called when payment fails
 *   onDismiss()       – called when user closes the modal without paying
 *   autoOpen         – if true, opens immediately after mounting (default: true)
 */
import { useEffect, useRef } from 'react';

const RAZORPAY_SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js';

function loadRazorpayScript() {
  return new Promise((resolve, reject) => {
    if (window.Razorpay) {
      resolve(true);
      return;
    }
    const existing = document.getElementById('razorpay-checkout-script');
    if (existing) {
      existing.addEventListener('load', () => resolve(true));
      existing.addEventListener('error', () => reject(new Error('Failed to load Razorpay SDK')));
      return;
    }
    const script = document.createElement('script');
    script.id = 'razorpay-checkout-script';
    script.src = RAZORPAY_SCRIPT_URL;
    script.async = true;
    script.onload = () => resolve(true);
    script.onerror = () => reject(new Error('Failed to load Razorpay SDK. Check your internet connection.'));
    document.head.appendChild(script);
  });
}

export default function RazorpayCheckout({
  order,
  patientName = '',
  patientEmail = '',
  patientPhone = '',
  onSuccess,
  onFailure,
  onDismiss,
  autoOpen = true,
}) {
  const rzpInstanceRef = useRef(null);

  async function openCheckout() {
    if (!order?.order_id || !order?.key_id) {
      onFailure?.(new Error('Invalid order data'));
      return;
    }

    try {
      await loadRazorpayScript();
    } catch (err) {
      onFailure?.(err);
      return;
    }

    const amountInRupees = ((order.amount || 0) / 100).toFixed(2);

    const options = {
      key: order.key_id,
      amount: order.amount,          // paise
      currency: order.currency || 'INR',
      name: 'DocTalk',
      description: `Consultation Appointment`,
      image: '/favicon.ico',
      order_id: order.order_id,
      prefill: {
        name: patientName,
        email: patientEmail,
        contact: patientPhone,
      },
      notes: {
        appointment_id: order.appointment_id,
      },
      theme: {
        color: '#6C5CE7',
      },
      modal: {
        ondismiss: () => {
          onDismiss?.();
        },
        escape: true,
        backdropclose: false,
      },
      handler: (response) => {
        // Called by Razorpay on successful payment
        onSuccess?.({
          razorpay_order_id: response.razorpay_order_id,
          razorpay_payment_id: response.razorpay_payment_id,
          razorpay_signature: response.razorpay_signature,
          appointment_id: order.appointment_id,
        });
      },
    };

    // eslint-disable-next-line no-undef
    const rzp = new window.Razorpay(options);
    rzp.on('payment.failed', (response) => {
      onFailure?.(new Error(response?.error?.description || 'Payment failed'));
    });

    rzpInstanceRef.current = rzp;
    rzp.open();
  }

  useEffect(() => {
    if (autoOpen && order?.order_id) {
      openCheckout();
    }
    return () => {
      // Close popup if component unmounts while open
      rzpInstanceRef.current?.close?.();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [order?.order_id]);

  // This component renders nothing — it's purely behavioural
  return null;
}
