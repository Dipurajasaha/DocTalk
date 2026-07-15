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
  const openingForOrderRef = useRef('');
  const openedForOrderRef = useRef('');
  const settledRef = useRef(false);

  const closeCheckout = () => {
    try {
      rzpInstanceRef.current?.close?.();
    } catch (err) {
      // Ignore close errors from Razorpay internals.
    } finally {
      rzpInstanceRef.current = null;
    }
  };

  const settleCheckout = (outcome, value) => {
    if (settledRef.current) return;

    // Razorpay can call ondismiss after close(). Mark it handled first so a
    // successful payment cannot also cancel its provisional appointment.
    settledRef.current = true;
    openingForOrderRef.current = '';
    console.debug('[RAZORPAY][SETTLE]', { outcome, order_id: order?.order_id, appointment_id: order?.appointment_id });
    closeCheckout();

    if (outcome === 'success') onSuccess?.(value);
    if (outcome === 'failure') onFailure?.(value);
    if (outcome === 'dismiss') onDismiss?.();
  };

  async function openCheckout(isActive, orderKey) {
    if (!isActive()) return;

    if (!order?.order_id || !order?.key_id) {
      settleCheckout('failure', new Error('Invalid order data'));
      return;
    }

    if (settledRef.current || openedForOrderRef.current === orderKey || openingForOrderRef.current === orderKey) {
      console.debug('[RAZORPAY][SKIP_OPEN]', {
        order_id: order?.order_id,
        orderKey,
        settled: settledRef.current,
        openedForOrder: openedForOrderRef.current,
        openingForOrder: openingForOrderRef.current,
      });
      return;
    }

    openingForOrderRef.current = orderKey;
    console.debug('[RAZORPAY][OPEN_START]', {
      order_id: order?.order_id,
      appointment_id: order?.appointment_id,
      orderKey,
      has_key_id: Boolean(order?.key_id),
    });

    try {
      await loadRazorpayScript();
    } catch (err) {
      if (isActive()) settleCheckout('failure', err);
      return;
    }

    if (!isActive() || settledRef.current) {
      openingForOrderRef.current = '';
      return;
    }

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
          settleCheckout('dismiss');
        },
        escape: true,
        backdropclose: false,
      },
      handler: (response) => {
        // Called by Razorpay on successful payment
        settleCheckout('success', {
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
      settleCheckout('failure', new Error(response?.error?.description || 'Payment failed'));
    });

    rzpInstanceRef.current = rzp;
    try {
      if (isActive() && !settledRef.current) {
        console.debug('[RAZORPAY][OPEN_CALL]', {
          order_id: order?.order_id,
          appointment_id: order?.appointment_id,
        });
        rzp.open();
        openedForOrderRef.current = orderKey;
      }
    } catch (err) {
      console.error('[RAZORPAY][OPEN_ERROR]', err);
      settleCheckout('failure', err);
    } finally {
      openingForOrderRef.current = '';
    }
  }

  useEffect(() => {
    const orderKey = `${order?.order_id || ''}:${order?.key_id || ''}`;
    let active = true;
    settledRef.current = false;

    if (!autoOpen || openedForOrderRef.current === orderKey) return undefined;

    // React Strict Mode intentionally tears down the first effect pass in dev.
    // Do not mark this order opened until the active effect actually opens it.
    const timer = window.setTimeout(() => {
      console.debug('[RAZORPAY][AUTO_OPEN_TIMER]', {
        order_id: order?.order_id,
        appointment_id: order?.appointment_id,
        orderKey,
      });
      openCheckout(() => active, orderKey);
    }, 0);

    return () => {
      active = false;
      window.clearTimeout(timer);
      // Suppress programmatic cleanup from being reported as a user dismissal.
      openingForOrderRef.current = '';
      settledRef.current = true;
      closeCheckout();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoOpen, order?.order_id, order?.key_id]);

  // This component renders nothing — it's purely behavioural
  return null;
}
