import React from 'react';
import RazorpayCheckout from '../../components/RazorpayCheckout';

export default function PatientAppointmentsPanel({
  appointments,
  doctors,
  appointmentDraft,
  setAppointmentDraft,
  bookingMode,
  setBookingMode,
  availableSlots,
  selectedSlotId,
  setSelectedSlotId,
  slotLoading,
  bookingInProgress,
  paymentProcessing,
  pendingOrder,
  user,
  handlePayNow,
  handleCancelAppointment,
  handleInitiatePayment,
  handleSelectDoctorForAppointment,
  handlePaymentSuccess,
  handlePaymentFailure,
  handlePaymentDismiss,
  renderSlotLabel
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0, paddingLeft: '32px', paddingRight: '32px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', justifyContent: 'center' }}>
          <h2 style={{ margin: 0, fontSize: '18px', color: '#6C5CE7', fontWeight: 'bold', textAlign: 'left', width: '100%', fontFamily: '"Poppins", system-ui, -apple-system, sans-serif', letterSpacing: '-0.5px' }}>Appointments Hub</h2>
        </div>
      </div>
      <div className="appointments-container neu-convex" style={{ display: 'flex', flexDirection: 'column', flex: 1, borderRadius: '16px', padding: '32px', overflowY: 'auto', minHeight: 0, boxSizing: 'border-box' }}>
      
        <div style={{ display: 'flex', gap: '40px' }}>
          <div style={{ flex: 1 }}>
            <h3 style={{ fontSize: '11px', marginBottom: '24px', color: '#475569', borderBottom: '2px solid #F1F5F9', paddingBottom: '12px' }}>Your Scheduled Sessions</h3>
            {appointments.length === 0 ? (
              <div className="neu-flat" style={{ padding: '48px 32px', textAlign: 'center', borderRadius: '16px', border: '1px dashed var(--border-subtle)' }}>
                <div style={{ fontSize: '20px', marginBottom: '16px' }}></div>
                <p style={{ color: '#64748B', margin: 0, fontSize: '11px' }}>No upcoming appointments scheduled.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {appointments.map((appt, i) => (
                  <div key={i} className="session-card neu-flat" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px 24px', border: `1px solid ${String(appt.status || '').toUpperCase() === 'PAYMENT_PENDING' ? '#FED7AA' : 'var(--border-subtle)'}`, borderRadius: '16px', borderLeft: `4px solid ${String(appt.status || '').toUpperCase() === 'CONFIRMED' ? '#22c55e' : String(appt.status || '').toUpperCase() === 'PAYMENT_PENDING' ? '#f97316' : String(appt.status || '').toUpperCase() === 'REJECTED' || String(appt.status || '').toUpperCase() === 'CANCELLED' ? '#ef4444' : 'var(--accent-primary)'}` }}>
                    <div>
                      <strong style={{ fontSize: '11px', color: '#1E293B' }}>Dr. {appt.doctor_display}</strong>
                      <div style={{ fontSize: '11px', color: '#64748B', marginTop: '6px' }}>Reason: {appt.reason}</div>
                      {(appt.appointmentDate || appt.scheduled_time) && <div style={{ fontSize: '11px', color: '#8B7EFF', marginTop: '4px', fontWeight: '500' }}>Time: {new Date(appt.appointmentDate || appt.scheduled_time).toLocaleString()}</div>}
                      {String(appt.doctorMessage || '').trim() && String(appt.status || '').toUpperCase() === 'REJECTED' && <div style={{ fontSize: '11px', color: '#B45309', marginTop: '4px' }}>Doctor note: {appt.doctorMessage}</div>}
                      {appt.amount_paise > 0 && (
                        <div style={{ fontSize: '10px', color: '#64748B', marginTop: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <span>💳</span>
                          <span>₹{(appt.amount_paise / 100).toFixed(0)} · </span>
                          <span style={{ fontWeight: '700', color: appt.payment_status === 'CAPTURED' ? '#16a34a' : appt.payment_status === 'FAILED' ? '#ef4444' : '#f97316' }}>
                            {appt.payment_status === 'CAPTURED' ? 'Paid' : appt.payment_status === 'FAILED' ? 'Failed' : 'Payment Pending'}
                          </span>
                        </div>
                      )}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      <span style={{ display: 'inline-block', padding: '6px 12px', borderRadius: '50px', fontSize: '10px', fontWeight: '700', background: String(appt.status || '').toUpperCase() === 'PAYMENT_PENDING' ? '#FFF7ED' : String(appt.status || '').toUpperCase() === 'PENDING' ? '#FEF3C7' : String(appt.status || '').toUpperCase() === 'CONFIRMED' ? '#DCFCE7' : String(appt.status || '').toUpperCase() === 'REJECTED' ? '#FEE2E2' : '#E2E8F0', color: String(appt.status || '').toUpperCase() === 'PAYMENT_PENDING' ? '#c2410c' : String(appt.status || '').toUpperCase() === 'PENDING' ? '#D97706' : String(appt.status || '').toUpperCase() === 'CONFIRMED' ? '#166534' : String(appt.status || '').toUpperCase() === 'REJECTED' ? '#B91C1C' : '#475569' }}>
                        {String(appt.status || '').toUpperCase() === 'PAYMENT_PENDING' ? '⏳ Awaiting Payment' : String(appt.status || '').toUpperCase()}
                      </span>
                      {String(appt.status || '').toUpperCase() === 'PAYMENT_PENDING' && appt.payment_status !== 'CAPTURED' && (
                        <button
                          type="button"
                          onClick={() => handlePayNow(appt)}
                          disabled={paymentProcessing}
                          className="neu-btn-accent"
                          style={{ padding: '8px 14px', background: '#f97316', fontSize: '10px', cursor: paymentProcessing ? 'not-allowed' : 'pointer' }}
                        >
                          {paymentProcessing ? '...' : '💳 Pay Now'}
                        </button>
                      )}
                      {String(appt.status || '').toUpperCase() !== 'CANCELLED' && String(appt.status || '').toUpperCase() !== 'COMPLETED' && String(appt.status || '').toUpperCase() !== 'REJECTED' && (
                        <button type="button" onClick={() => handleCancelAppointment(appt.id)} className="neu-convex" style={{ padding: '8px 14px', borderRadius: '50px', color: 'var(--accent-tertiary)', fontSize: '10px', fontWeight: '700', cursor: 'pointer' }}>
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ flex: 1 }}>
            <h3 style={{ fontSize: '11px', marginBottom: '24px', color: '#475569', borderBottom: '2px solid #F1F5F9', paddingBottom: '12px' }}>Book New Appointment</h3>
            <form onSubmit={handleInitiatePayment} className="neu-flat" style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: '12px', padding: '20px', borderRadius: '16px', marginBottom: '24px' }}>
              <div style={{ gridColumn: '1 / -1', display: 'flex', gap: '10px' }}>
                <button type="button" onClick={() => setBookingMode('direct')} style={{ flex: 1, padding: '10px 14px', borderRadius: '999px', border: bookingMode === 'direct' ? 'none' : '1px solid #CBD5E1', background: bookingMode === 'direct' ? '#6C5CE7' : '#FFF', color: bookingMode === 'direct' ? '#FFF' : '#475569', fontSize: '11px', fontWeight: '700', cursor: 'pointer' }}>Pick a Time</button>
                <button type="button" onClick={() => setBookingMode('open')} style={{ flex: 1, padding: '10px 14px', borderRadius: '999px', border: bookingMode === 'open' ? 'none' : '1px solid #CBD5E1', background: bookingMode === 'open' ? '#6C5CE7' : '#FFF', color: bookingMode === 'open' ? '#FFF' : '#475569', fontSize: '11px', fontWeight: '700', cursor: 'pointer' }}>Send Open Request</button>
              </div>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569' }}>
                Doctor
                <select value={appointmentDraft.doctor_id} onChange={e => setAppointmentDraft(prev => ({ ...prev, doctor_id: e.target.value }))} className="neu-input" style={{ fontSize: '11px' }}>
                  <option value="">Select a doctor</option>
                  {doctors.map(doc => {
                    const doctorId = doc.doctor_id || doc.id;
                    const fee = doc.consultation_fee ? ` · ₹${(doc.consultation_fee / 100).toFixed(0)}` : '';
                    return <option key={doctorId} value={doctorId}>Dr. {doc.name} {doc.category ? `- ${doc.category}` : ''}{fee}</option>;
                  })}
                </select>
              </label>
              {bookingMode === 'direct' ? (
                <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569' }}>
                  Available Slots
                  <select value={selectedSlotId} onChange={e => setSelectedSlotId(e.target.value)} disabled={!appointmentDraft.doctor_id || slotLoading} className="neu-input" style={{ fontSize: '11px' }}>
                    <option value="">{slotLoading ? 'Loading slots...' : 'Choose an available slot'}</option>
                    {availableSlots.map(slot => (
                      <option key={slot.id} value={slot.id}>{renderSlotLabel(slot)}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <div style={{ gridColumn: '1 / -1', padding: '12px 14px', background: '#FFF7ED', border: '1px solid #FED7AA', borderRadius: '12px', color: '#9A3412', fontSize: '11px', lineHeight: 1.5 }}>
                  Send an open request when you do not see a slot that fits. The doctor will confirm a time later.
                </div>
              )}
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569' }}>
                Reason
                <input type="text" value={appointmentDraft.reason} onChange={e => setAppointmentDraft(prev => ({ ...prev, reason: e.target.value }))} placeholder="General consultation" className="neu-input" style={{ fontSize: '11px' }} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '11px', color: '#475569', gridColumn: '1 / -1' }}>
                Note
                <textarea value={appointmentDraft.note} onChange={e => setAppointmentDraft(prev => ({ ...prev, note: e.target.value }))} placeholder="Optional context for the doctor" rows="3" className="neu-input" style={{ fontSize: '11px', resize: 'vertical' }} />
              </label>
              {appointmentDraft.doctor_id && (() => {
                const selDoc = doctors.find(d => String(d.doctor_id || d.id) === String(appointmentDraft.doctor_id));
                const fee = selDoc?.consultation_fee || 50000;
                return (
                  <div style={{ gridColumn: '1 / -1', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', background: 'linear-gradient(135deg, #EDE9FE, #F3F0FF)', borderRadius: '12px', border: '1px solid #C4B5FD' }}>
                    <span style={{ fontSize: '11px', color: '#5B21B6', fontWeight: '600' }}>💳 Consultation Fee</span>
                    <span style={{ fontSize: '14px', fontWeight: '800', color: '#4C1D95' }}>₹{(fee / 100).toFixed(0)}</span>
                  </div>
                );
              })()}
              <div style={{ gridColumn: '1 / -1', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="submit"
                  disabled={bookingInProgress || paymentProcessing || (bookingMode === 'direct' && (!selectedSlotId || slotLoading))}
                  className="neu-btn-accent"
                  style={{ padding: '12px 24px', borderRadius: '999px', fontSize: '11px', cursor: bookingInProgress || paymentProcessing || (bookingMode === 'direct' && (!selectedSlotId || slotLoading)) ? 'not-allowed' : 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  {bookingInProgress ? 'Creating Order…' : paymentProcessing ? 'Processing…' : '💳 Proceed to Pay'}
                </button>
              </div>
            </form>

            <div className="doctor-profile-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '20px' }}>
              {doctors.map(doc => {
                const doctorId = String(doc.doctor_id || doc.id || '');
                const feePaise = doc.consultation_fee || 0;
                const isSelected = appointmentDraft.doctor_id === doctorId;
                return (
                  <div key={doctorId} className={isSelected ? 'neu-convex' : 'neu-flat'} style={{ padding: '24px', borderRadius: '16px', border: isSelected ? '1px solid var(--accent-primary)' : '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', transition: 'all 0.2s' }}>
                    <div style={{ width: '60px', height: '60px', borderRadius: '50%', background: isSelected ? '#DDD6FE' : '#E2E8F0', marginBottom: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '20px' }}>👨‍⚕️</div>
                    <div style={{ fontWeight: '700', fontSize: '11px', color: '#1E293B', marginBottom: '2px' }}>Dr. {doc.name}</div>
                    <div style={{ fontSize: '10px', color: '#64748B', marginBottom: '6px' }}>{doc.category}</div>
                    {feePaise > 0
                      ? <div style={{ fontSize: '12px', fontWeight: '800', color: '#6C5CE7', marginBottom: '12px', background: '#EDE9FE', padding: '3px 10px', borderRadius: '50px' }}>₹{(feePaise / 100).toFixed(0)}</div>
                      : <div style={{ fontSize: '10px', color: '#94a3b8', marginBottom: '12px' }}>Fee not set</div>
                    }
                    <button type="button" onClick={() => handleSelectDoctorForAppointment(doctorId)} className={isSelected ? 'neu-btn-accent' : 'neu-convex'} style={{ width: '100%', padding: '10px 16px', borderRadius: '50px', cursor: 'pointer', fontSize: '11px', fontWeight: '600' }}>{isSelected ? '✓ Selected' : 'Select Doctor'}</button>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* ── Razorpay Checkout Modal ─────────────────────────────── */}
      {pendingOrder && (
        <RazorpayCheckout
          order={pendingOrder}
          patientName={user?.name || user?.display_name || ''}
          patientEmail={user?.email || ''}
          patientPhone={user?.mobile || user?.phone || ''}
          onSuccess={handlePaymentSuccess}
          onFailure={handlePaymentFailure}
          onDismiss={handlePaymentDismiss}
          autoOpen={true}
        />
      )}
    </div>
  );
}
