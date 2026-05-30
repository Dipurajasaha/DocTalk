import { apiClient } from './apiClient';

export const buildAssetDownloadUrl = (assetId) => `/api/assets/${encodeURIComponent(assetId)}/download`;

export const authApi = {
  loginPatient: (username, password) => apiClient.post('/api/auth/patient/login', { username, password }, { retries: 0 }),
  loginDoctor: (doctorId, password) => apiClient.post('/api/auth/doctor/login', { doctor_id: doctorId, password }, { retries: 0 }),
  signupPatient: (username, name, password) => apiClient.post('/api/auth/patient/signup', { username, name, password }, { retries: 0 }),
  signupDoctor: (doctorId, name, password) => apiClient.post('/api/auth/doctor/signup', { doctor_id: doctorId, name, password }, { retries: 0 }),
  me: async (token) => {
    // Try common session endpoints used by different backend versions.
    const endpoints = ['/api/me', '/api/doctor_session', '/api/patient_session', '/me'];
    for (const ep of endpoints) {
      try {
        const data = await apiClient.get(ep, { auth: true, token, retries: 0 });
        if (data) return data;
      } catch (e) {
        // ignore and try next
      }
    }
    return null;
  },
};

export const patientApi = {
  listAppointments: () => apiClient.get('/api/appointments', { retries: 1, auth: true }),
  getAvailableSlots: (doctorId) => apiClient.get(`/api/appointments/slots/${encodeURIComponent(doctorId)}`, { retries: 1, auth: true }),
  bookDirectAppointment: (slotId, reason, note) => apiClient.post('/api/appointments/book/direct', { slotId, reason, note }, { retries: 0, auth: true }),
  bookOpenAppointment: (doctorId, reason, note) => apiClient.post('/api/appointments/book/open', { doctorId, reason, note }, { retries: 0, auth: true }),
  listDoctors: () => apiClient.get('/api/doctor/list', { retries: 1, auth: true }),
  getConsultation: (consultationId) => apiClient.get(`/api/chat/consultations/${encodeURIComponent(consultationId)}`, { retries: 1, auth: true }),
  createAppointment: (body) => {
    if (body?.slotId || body?.slot_id) {
      return apiClient.post('/api/appointments/book/direct', { slotId: body.slotId || body.slot_id, reason: body.reason, note: body.note }, { retries: 0, auth: true });
    }
    if (body?.doctorId || body?.doctor_id) {
      return apiClient.post('/api/appointments/book/open', { doctorId: body.doctorId || body.doctor_id, reason: body.reason || body.note || 'General consultation', note: body.note }, { retries: 0, auth: true });
    }
    return apiClient.post('/api/appointments', body, { retries: 0, auth: true });
  },
  cancelAppointment: (appointmentId) => apiClient.patch(`/api/appointments/${appointmentId}/cancel`, {}, { retries: 0, auth: true }),
  listAssets: (folder = '') => {
    const query = folder ? `?folder=${encodeURIComponent(folder)}` : '';
    return apiClient.get(`/api/assets${query}`, { retries: 1, auth: true });
  },
  uploadAsset: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/api/assets/upload', formData, { retries: 0, auth: true });
  },
  getAsset: (assetId) => apiClient.get(`/api/assets/${encodeURIComponent(assetId)}`, { retries: 1, auth: true }),
  deleteAsset: (assetId) => apiClient.delete(`/api/assets/${encodeURIComponent(assetId)}`, { retries: 0, auth: true }),
  renameAsset: (assetId, newName) => apiClient.patch(`/api/assets/${encodeURIComponent(assetId)}/rename`, { new_name: newName }, { retries: 0, auth: true }),
  listConsultations: () => apiClient.get('/api/chat/consultations', { retries: 1, auth: true }),
  getConsultation: (consultationId) => apiClient.get(`/api/chat/consultations/${encodeURIComponent(consultationId)}`, { retries: 1, auth: true }),
  getConsultationMessages: (consultationId, page = 1, limit = 20) => apiClient.get(`/api/chat/consultations/${encodeURIComponent(consultationId)}/messages?page=${page}&limit=${limit}`, { retries: 1, auth: true }),
  postConsultationMessage: (consultationId, message) => apiClient.post(`/api/chat/consultations/${encodeURIComponent(consultationId)}/messages`, { message }, { retries: 0, auth: true }),
  createConsultation: (appointmentId) => apiClient.post('/api/chat/consultations', { appointment_id: appointmentId }, { retries: 0, auth: true }),
  requestAppointment: (body) => apiClient.post('/api/appointment_request', body, { retries: 0, auth: true }),
};

export const doctorApi = {
  createSlots: (slots) => apiClient.post('/api/appointments/slots', slots, { retries: 0, auth: true }),
  getSlots: (doctorId) => apiClient.get(`/api/appointments/slots/${encodeURIComponent(doctorId)}`, { retries: 1, auth: true }),
  respondToAppointment: (appointmentId, body) => apiClient.put(`/api/appointments/${encodeURIComponent(appointmentId)}/action`, body, { retries: 0, auth: true }),
  cancelAppointment: (appointmentId) => apiClient.patch(`/api/appointments/${encodeURIComponent(appointmentId)}/cancel`, {}, { retries: 0, auth: true }),
  dashboardData: async (doctorId) => {
    const normalizeStatus = (value) => String(value || '').trim().toUpperCase();
    const resolvedDoctorId = String(doctorId || '').trim();

    const [appointmentsResult, slotsResult, consultationsResult] = await Promise.allSettled([
      apiClient.get('/api/appointments', { retries: 1, auth: true }),
      resolvedDoctorId ? apiClient.get(`/api/appointments/slots/${encodeURIComponent(resolvedDoctorId)}`, { retries: 1, auth: true }) : Promise.resolve([]),
      apiClient.get('/api/chat/consultations', { retries: 0, auth: true }),
    ]);

    const appointments = appointmentsResult.status === 'fulfilled' && Array.isArray(appointmentsResult.value)
      ? appointmentsResult.value
      : [];
    const slots = slotsResult.status === 'fulfilled' && Array.isArray(slotsResult.value)
      ? slotsResult.value
      : [];
    const consultations = consultationsResult.status === 'fulfilled' && Array.isArray(consultationsResult.value)
      ? consultationsResult.value
      : [];

    const requests = appointments.filter((item) => normalizeStatus(item.status) === 'PENDING');
    const upcoming_schedules = appointments.filter((item) => normalizeStatus(item.status) === 'CONFIRMED');
    const completed_schedules = appointments.filter((item) => normalizeStatus(item.status) === 'COMPLETED');
    const patient_chat_patients = Array.from(new Set(
      consultations
        .map((item) => String(item.patientUsername || item.patient_id || item.patientId || '').trim())
        .filter(Boolean),
    ));

    return {
      success: true,
      appointments,
      upcoming_schedules,
      completed_schedules,
      requests,
      patient_chat_patients,
      closed_chats: [],
      slots,
      total_requests: requests.length,
      total_patients: Array.from(new Set(appointments.map((item) => String(item.patientUsername || item.patient_id || item.patient || '').trim()).filter(Boolean))).length,
      monthly_revenue: 0,
    };
  },
  getCopilotForPatient: (patientId, consultationId = '') => {
    const query = consultationId ? `?consultation_id=${encodeURIComponent(consultationId)}` : '';
    return apiClient.get(`/api/doctor/copilot/patients/${encodeURIComponent(patientId)}${query}`, { retries: 1, auth: true });
  },
  getCopilotForConsultation: (consultationId) => apiClient.get(`/api/doctor/copilot/consultations/${encodeURIComponent(consultationId)}`, { retries: 1, auth: true }),
};
