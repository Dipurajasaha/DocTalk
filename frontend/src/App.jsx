import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import Login from './pages/Login';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import AdminDashboard from './pages/AdminDashboard';
import ReportView from './pages/ReportView';
import PrescriptionView from './pages/PrescriptionView';
import DoctorSignatureSetup from './pages/DoctorSignatureSetup';
import DoctorPrescriptionsList from './pages/DoctorPrescriptionsList';
import PrescriptionComposer from './pages/PrescriptionComposer';
import PatientPrescriptionsList from './pages/PatientPrescriptionsList';
import PublicVerify from './pages/PublicVerify';
import { useSession } from './contexts/SessionContext';
import { useEffect } from 'react';
import { useNotifications } from './contexts';
import NotificationTray from './components/NotificationTray';

function RequirePatient({ children, loaded, session }) {
  if (!loaded) return null;
  if (!session) return <Navigate to="/login" replace />;
  if (session.role !== 'patient') return <Navigate to="/login" replace />;
  return children;
}

function RequireDoctor({ children, loaded, session }) {
  if (!loaded) return null;
  if (!session) return <Navigate to="/login" replace />;
  if (session.role !== 'doctor') return <Navigate to="/login" replace />;
  return children;
}

function RequireAdmin({ children, loaded, session }) {
  if (!loaded) return null;
  if (!session) return <Navigate to="/login" replace />;
  if (session.role !== 'admin') return <Navigate to="/login" replace />;
  return children;
}

function RequireAuth({ children, loaded, session }) {
  if (!loaded) return null;
  if (!session) return <Navigate to="/login" replace />;
  return children;
}

function App() {
  const { session, loaded, expired, justLoggedOut, startLogoutTimer, clearLogoutTimer } = useSession();
  const { addNotification } = useNotifications();

  useEffect(() => {
    if (expired) {
      try { addNotification({ type: 'error', message: 'Session expired — please log in again.' }); } catch (e) {}
    }
  }, [expired, addNotification]);

  return (
    <BrowserRouter>
      <NotificationTray />
      {justLoggedOut && (
        <div
          onMouseEnter={() => { try { clearLogoutTimer(); } catch (e) {} }}
          onMouseLeave={() => { try { startLogoutTimer(2000); } catch (e) {} }}
          style={{
            position: 'fixed',
            top: '12px',
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#ecfdf5',
            color: '#065f46',
            padding: '10px 16px',
            borderRadius: '8px',
            boxShadow: '0 6px 18px rgba(2,6,23,0.08)',
            zIndex: 1000,
            cursor: 'default',
            transition: 'opacity 0.12s ease-in-out'
          }}
        >
          Successfully logged out.
        </div>
      )}
      {!justLoggedOut && expired && (
        <div style={{ background: '#fee2e2', color: '#991b1b', padding: '8px 12px', textAlign: 'center' }}>
          Your session has expired — please <a href="/login">log in</a> again.
        </div>
      )}
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/patient/dashboard" element={<RequirePatient loaded={loaded} session={session}><PatientDashboard /></RequirePatient>} />
        <Route path="/doctor/dashboard" element={<RequireDoctor loaded={loaded} session={session}><DoctorDashboard /></RequireDoctor>} />
        <Route path="/admin/dashboard" element={<RequireAdmin loaded={loaded} session={session}><AdminDashboard /></RequireAdmin>} />
        <Route path="/reports/:id" element={<RequireAuth loaded={loaded} session={session}><ReportView /></RequireAuth>} />
        <Route path="/prescriptions/:id" element={<RequireAuth loaded={loaded} session={session}><PrescriptionView /></RequireAuth>} />
        <Route path="/doctor/signature" element={<RequireDoctor loaded={loaded} session={session}><DoctorSignatureSetup /></RequireDoctor>} />
        <Route path="/doctor/prescriptions" element={<RequireDoctor loaded={loaded} session={session}><DoctorPrescriptionsList /></RequireDoctor>} />
        <Route path="/doctor/prescriptions/new" element={<RequireDoctor loaded={loaded} session={session}><PrescriptionComposer /></RequireDoctor>} />
        <Route path="/doctor/prescriptions/new/:patientUsername" element={<RequireDoctor loaded={loaded} session={session}><PrescriptionComposer /></RequireDoctor>} />
        <Route path="/patient/prescriptions" element={<RequirePatient loaded={loaded} session={session}><PatientPrescriptionsList /></RequirePatient>} />
        <Route path="/verify/:qrToken" element={<PublicVerify />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
