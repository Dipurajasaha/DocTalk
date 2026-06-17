import { apiClient } from './apiClient';

export const buildAssetDownloadUrl = (assetId) => `/api/assets/${encodeURIComponent(assetId)}/download`;

export const authApi = {
  loginPatient: (username, password) => apiClient.post('/api/auth/patient/login', { username, password }, { retries: 0 }),
  loginDoctor: (doctorId, password) => apiClient.post('/api/auth/doctor/login', { doctor_id: doctorId, password }, { retries: 0 }),
  signupPatient: (username, name, password) => apiClient.post('/api/auth/patient/signup', { username, name, password }, { retries: 0 }),
  signupDoctor: (doctorId, name, password, extra = {}) => apiClient.post('/api/auth/doctor/signup', { doctor_id: doctorId, name, password, ...extra }, { retries: 0 }),
  me: (token) => apiClient.get('/api/me', { auth: true, token, retries: 0 }),
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
  getConsultationMessages: (consultationId, page = 1, limit = 20, role = '') => {
    const roleQuery = role ? `&role=${encodeURIComponent(role)}` : '';
    return apiClient.get(`/api/chat/consultations/${encodeURIComponent(consultationId)}/messages?page=${page}&limit=${limit}${roleQuery}`, { retries: 1, auth: true });
  },
  postConsultationMessage: (consultationId, message) => apiClient.post(`/api/chat/consultations/${encodeURIComponent(consultationId)}/messages`, { message }, { retries: 0, auth: true }),
  createConsultation: (appointmentId) => apiClient.post('/api/chat/consultations', { appointment_id: appointmentId }, { retries: 0, auth: true }),
  getAiChatHistory: (aiSessionId = 'patient_ai', targetPatientId = '') => {
    const targetQuery = targetPatientId ? `&target_patient_id=${encodeURIComponent(targetPatientId)}` : '';
    return apiClient.get(`/api/chat/ai/history?ai_session_id=${encodeURIComponent(aiSessionId)}${targetQuery}`, { retries: 1, auth: true });
  },
  requestAppointment: (body) => apiClient.post('/api/appointment_request', body, { retries: 0, auth: true }),
};

export const hospitalApi = {
  login: (hospitalId, password) => apiClient.post('/api/hospital/auth/login', { hospital_id: hospitalId, password }, { retries: 0 }),
  signup: (data) => apiClient.post('/api/hospital/auth/signup', data, { retries: 0 }),
  dashboard: () => apiClient.get('/api/hospital/dashboard', { retries: 0, auth: true }),
  createReport: (data) => apiClient.post('/api/hospital/reports', data, { retries: 0, auth: true }),
  listReports: (page = 1, perPage = 20, disease = '', severity = '') => {
    const params = new URLSearchParams({ page, per_page: perPage });
    if (disease) params.set('disease', disease);
    if (severity) params.set('severity', severity);
    return apiClient.get(`/api/hospital/reports?${params}`, { retries: 1, auth: true });
  },
  getReport: (reportId) => apiClient.get(`/api/hospital/reports/${encodeURIComponent(reportId)}`, { retries: 0, auth: true }),
  createNews: (data) => apiClient.post('/api/hospital/news', data, { retries: 0, auth: true }),
  listNews: () => apiClient.get('/api/hospital/news', { retries: 1, auth: true }),
  getGlobalNews: (limit = 10) => apiClient.get(`/api/hospital/public/news/global?limit=${limit}`, { retries: 1 }),
  getGlobalReports: (page = 1, perPage = 20, disease = '') => {
    const params = new URLSearchParams({ page, per_page: perPage });
    if (disease) params.set('disease', disease);
    return apiClient.get(`/api/hospital/public/reports/global?${params}`, { retries: 1 });
  },
  getDiseaseSummary: () => apiClient.get('/api/hospital/public/disease-summary', { retries: 1 }),
  registerPatient: (data) => apiClient.post('/api/hospital/register-patient', data, { retries: 0, auth: true }),
  listPatients: () => apiClient.get('/api/hospital/patients', { retries: 1, auth: true }),
  updateReportStatus: (reportId, status) => apiClient.put(`/api/hospital/reports/${encodeURIComponent(reportId)}/status`, { status }, { retries: 0, auth: true }),
  getDetailedAnalysis: () => apiClient.get('/api/hospital/detailed-analysis', { retries: 1, auth: true }),
  getGlobalDetailedAnalysis: () => apiClient.get('/api/hospital/public/detailed-analysis/global', { retries: 1 }),
  getPatientMedicalHistory: (username) => apiClient.get(`/api/hospital/patients/${encodeURIComponent(username)}/medical-history`, { retries: 1, auth: true }),
  getPatientReports: (username) => apiClient.get(`/api/hospital/reports/patient/${encodeURIComponent(username)}`, { retries: 1, auth: true }),
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
