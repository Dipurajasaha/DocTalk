import { apiClient } from './apiClient';

export const authApi = {
  loginPatient: (username, password) => apiClient.post('/api/auth/patient/login', { username, password }, { retries: 0 }),
  loginDoctor: (doctorId, password) => apiClient.post('/api/auth/doctor/login', { doctor_id: doctorId, password }, { retries: 0 }),
  signupPatient: (username, name, password) => apiClient.post('/api/auth/patient/signup', { username, name, password }, { retries: 0 }),
  signupDoctor: (doctorId, name, password) => apiClient.post('/api/auth/doctor/signup', { doctor_id: doctorId, name, password }, { retries: 0 }),
  me: (token) => apiClient.get('/me', { auth: true, token, retries: 0 }),
};

export const patientApi = {
  listAppointments: () => apiClient.get('/api/appointments', { retries: 1, auth: true }),
  listMyAppointments: () => apiClient.get('/api/my_appointments', { retries: 1, auth: true }),
  listDoctors: () => apiClient.get('/api/doctor/list', { retries: 1, auth: true }),
  createAppointment: (body) => apiClient.post('/api/appointments', body, { retries: 0, auth: true }),
  cancelAppointment: (appointmentId) => apiClient.patch(`/api/appointments/${appointmentId}/cancel`, {}, { retries: 0, auth: true }),
  listMedicalImages: () => apiClient.get('/api/medical_images', { retries: 1, auth: true }),
  uploadMedicalImage: (formData) => apiClient.post('/api/medical_images/upload', formData, { retries: 0, auth: true }),
  uploadAssetV2: (formData) => apiClient.post('/api/v2/upload_asset', formData, { retries: 0, auth: true }),
  listConsultations: () => apiClient.get('/api/chat/consultations', { retries: 1, auth: true }),
  requestAppointment: (body) => apiClient.post('/api/appointment_request', body, { retries: 0, auth: true }),
  getDoctorPatientChat: (docId) => apiClient.get(`/api/doctor_patient_chat?other=${encodeURIComponent(docId)}`, { retries: 1, auth: true }),
  postDoctorPatientChat: (payload) => apiClient.post('/api/doctor_patient_chat', payload, { retries: 0, auth: true }),
  // v2 asset ops (form-encoded)
  createFolderV2: (name) => apiClient.post('/api/v2/create_folder', new URLSearchParams({ name }), { retries: 0, auth: true, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }),
  deleteAssetV2: (id, type) => apiClient.post('/api/v2/delete_asset', new URLSearchParams({ id, type }), { retries: 0, auth: true, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }),
  renameAssetV2: (id, old_name, new_name, type) => apiClient.post('/api/v2/rename_asset', new URLSearchParams({ id, old_name, new_name, type }), { retries: 0, auth: true, headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }),
};

export const doctorApi = {
  dashboardData: () => apiClient.get('/api/doctor_dashboard_data', { retries: 1, auth: true }),
};
