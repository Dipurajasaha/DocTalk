import { apiClient } from './apiClient';

const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.gif'];
const PRESCRIPTION_HINTS = ['prescription', 'rx', 'medication', 'medicine', 'pharmacy', 'drug'];

export const resolvePatientAssetKind = (file) => {
  const kind = String(file?.asset_kind || file?.file_type || '').toLowerCase();
  if (kind === 'report' || kind === 'prescription' || kind === 'medical_image') return kind;

  const fileName = String(file?.name || file?.original_name || '').toLowerCase();
  const mimeType = String(file?.mime_type || file?.mimeType || '').toLowerCase();
  if (mimeType.startsWith('image/') || IMAGE_EXTENSIONS.some((ext) => fileName.endsWith(ext))) return 'medical_image';
  if (mimeType === 'application/pdf' || fileName.endsWith('.pdf')) {
    return PRESCRIPTION_HINTS.some((hint) => fileName.includes(hint)) ? 'prescription' : 'report';
  }
  return 'medical_image';
};

export const resolvePatientUploadTarget = (file) => {
  const fileName = String(file?.name || '').toLowerCase();
  const mimeType = String(file?.type || '').toLowerCase();
  const isImage = mimeType.startsWith('image/') || IMAGE_EXTENSIONS.some((ext) => fileName.endsWith(ext));
  if (isImage) {
    return { endpoint: '/api/assets/medical_images/upload', kind: 'medical_image' };
  }

  const isPdf = mimeType === 'application/pdf' || fileName.endsWith('.pdf');
  if (isPdf) {
    const isPrescription = PRESCRIPTION_HINTS.some((hint) => fileName.includes(hint));
    return {
      endpoint: isPrescription ? '/api/assets/prescriptions/upload' : '/api/assets/reports/upload',
      kind: isPrescription ? 'prescription' : 'report',
    };
  }

  return { endpoint: '/api/assets/medical_images/upload', kind: 'medical_image' };
};

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
  listMyAppointments: () => apiClient.get('/api/my_appointments', { retries: 1, auth: true }),
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
  listMedicalImages: () => apiClient.get('/api/assets/medical_images', { retries: 1, auth: true }),
  uploadMedicalImage: (formData) => apiClient.post('/api/assets/medical_images/upload', formData, { retries: 0, auth: true }),
  deleteMedicalImage: (medicalImageId) => apiClient.delete(`/api/assets/medical_images/${encodeURIComponent(medicalImageId)}`, { retries: 0, auth: true }),
  renameMedicalImage: (medicalImageId, newName) => apiClient.patch(`/api/assets/medical_images/${encodeURIComponent(medicalImageId)}`, { new_name: newName }, { retries: 0, auth: true }),
  renameReport: (reportId, newName) => apiClient.patch(`/api/assets/reports/${encodeURIComponent(reportId)}`, { new_name: newName }, { retries: 0, auth: true }),
  renamePrescription: (prescriptionId, newName) => apiClient.patch(`/api/assets/prescriptions/${encodeURIComponent(prescriptionId)}`, { new_name: newName }, { retries: 0, auth: true }),
  deleteReport: (reportId) => apiClient.delete(`/api/assets/reports/${encodeURIComponent(reportId)}`, { retries: 0, auth: true }),
  deletePrescription: (prescriptionId) => apiClient.delete(`/api/assets/prescriptions/${encodeURIComponent(prescriptionId)}`, { retries: 0, auth: true }),
  renameAsset: async (file, newName) => {
    const kind = resolvePatientAssetKind(file);
    const assetId = file?.id;
    if (!assetId) {
      throw new Error('Missing asset id');
    }

    const attempts = kind === 'report'
      ? [() => apiClient.patch(`/api/assets/reports/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true }), () => apiClient.patch(`/api/assets/prescriptions/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true }), () => apiClient.patch(`/api/assets/medical_images/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true })]
      : kind === 'prescription'
        ? [() => apiClient.patch(`/api/assets/prescriptions/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true }), () => apiClient.patch(`/api/assets/reports/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true }), () => apiClient.patch(`/api/assets/medical_images/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true })]
        : [() => apiClient.patch(`/api/assets/medical_images/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true }), () => apiClient.patch(`/api/assets/reports/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true }), () => apiClient.patch(`/api/assets/prescriptions/${encodeURIComponent(assetId)}`, { new_name: newName }, { retries: 0, auth: true })];

    let lastError = null;
    for (const attempt of attempts) {
      try {
        return await attempt();
      } catch (error) {
        lastError = error;
        const status = error?.status || 0;
        if (status && status !== 404 && status !== 405 && status !== 422) break;
      }
    }

    throw lastError || new Error('Rename failed');
  },
  listConsultations: () => apiClient.get('/api/chat/consultations', { retries: 1, auth: true }),
  getConsultation: (consultationId) => apiClient.get(`/api/chat/consultations/${encodeURIComponent(consultationId)}`, { retries: 1, auth: true }),
  getConsultationMessages: (consultationId, page = 1, limit = 20) => apiClient.get(`/api/chat/consultations/${encodeURIComponent(consultationId)}/messages?page=${page}&limit=${limit}`, { retries: 1, auth: true }),
  postConsultationMessage: (consultationId, message) => apiClient.post(`/api/chat/consultations/${encodeURIComponent(consultationId)}/messages`, { message }, { retries: 0, auth: true }),
  createConsultation: (appointmentId) => apiClient.post('/api/chat/consultations', { appointment_id: appointmentId }, { retries: 0, auth: true }),
  requestAppointment: (body) => apiClient.post('/api/appointment_request', body, { retries: 0, auth: true }),
  // Reports & prescriptions
  listReports: () => apiClient.get('/api/assets/reports', { retries: 1, auth: true }),
  getReport: (reportId) => apiClient.get(`/api/assets/reports/${encodeURIComponent(reportId)}`, { retries: 1, auth: true }),
  listPrescriptions: () => apiClient.get('/api/assets/prescriptions', { retries: 1, auth: true }),
  getPrescription: (prescriptionId) => apiClient.get(`/api/assets/prescriptions/${encodeURIComponent(prescriptionId)}`, { retries: 1, auth: true }),
  attachReportToConsultation: (reportId, consultationId) => apiClient.post(`/api/assets/reports/${encodeURIComponent(reportId)}/attach`, { consultation_id: consultationId }, { retries: 0, auth: true }),
  attachPrescriptionToConsultation: (prescriptionId, consultationId) => apiClient.post(`/api/assets/prescriptions/${encodeURIComponent(prescriptionId)}/attach`, { consultation_id: consultationId }, { retries: 0, auth: true }),
};

export const doctorApi = {
  createSlots: (slots) => apiClient.post('/api/appointments/slots', slots, { retries: 0, auth: true }),
  getSlots: (doctorId) => apiClient.get(`/api/appointments/slots/${encodeURIComponent(doctorId)}`, { retries: 1, auth: true }),
  respondToAppointment: (appointmentId, body) => apiClient.put(`/api/appointments/${encodeURIComponent(appointmentId)}/action`, body, { retries: 0, auth: true }),
  cancelAppointment: (appointmentId) => apiClient.patch(`/api/appointments/${encodeURIComponent(appointmentId)}/cancel`, {}, { retries: 0, auth: true }),
  dashboardData: async () => {
    try {
      const summary = await apiClient.get('/api/doctor_dashboard_data', { retries: 1, auth: true });
      if (summary && summary.success) return summary;
    } catch (err) {
      // fall back to composing from existing endpoints
    }

    try {
      const appointments = await apiClient.get('/api/appointments', { retries: 1, auth: true });
      let consultations = [];
      try {
        consultations = await apiClient.get('/api/chat/consultations', { retries: 0, auth: true });
      } catch (e) {
        consultations = [];
      }

      const now = Date.now();
      const upcoming_schedules = Array.isArray(appointments)
        ? appointments.filter(a => a.scheduled_time && new Date(a.scheduled_time).getTime() > now)
        : [];

      const completed_schedules = Array.isArray(appointments)
        ? appointments.filter(a => a.status === 'completed')
        : [];

      const requests = Array.isArray(appointments)
        ? appointments.filter(a => a.status === 'pending' || a.status === 'requested' || a.status === 'awaiting')
        : [];

      const patient_chat_patients = Array.isArray(consultations)
        ? Array.from(new Set(consultations.map(c => c.patientUsername || c.patient || c.patient_id).filter(Boolean)))
        : [];

      const closed_chats = [];

      return {
        success: true,
        upcoming_schedules,
        completed_schedules,
        requests,
        patient_chat_patients,
        closed_chats,
        total_requests: requests.length,
        total_patients: Array.isArray(appointments) ? Array.from(new Set(appointments.map(a => a.patientUsername || a.patient))).length : 0,
        monthly_revenue: 0,
      };
    } catch (err) {
      throw err;
    }
  },
  getCopilotForPatient: (patientId, consultationId = '') => {
    const query = consultationId ? `?consultation_id=${encodeURIComponent(consultationId)}` : '';
    return apiClient.get(`/api/doctor/copilot/patients/${encodeURIComponent(patientId)}${query}`, { retries: 1, auth: true });
  },
  getCopilotForConsultation: (consultationId) => apiClient.get(`/api/doctor/copilot/consultations/${encodeURIComponent(consultationId)}`, { retries: 1, auth: true }),
};
