import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import Login from './pages/Login';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';
import ReportView from './pages/ReportView';
import PrescriptionView from './pages/PrescriptionView';
import { useSession } from './contexts/SessionContext';

function App() {
  const { session, loaded, expired, justLoggedOut, startLogoutTimer, clearLogoutTimer } = useSession();

  const RequirePatient = ({ children }) => {
    if (!loaded) return null; // wait for session bootstrap
    if (!session) return <Navigate to="/login" replace />;
    if (session.role !== 'patient') return <Navigate to="/login" replace />;
    return children;
  };

  const RequireDoctor = ({ children }) => {
    if (!loaded) return null;
    if (!session) return <Navigate to="/login" replace />;
    if (session.role !== 'doctor') return <Navigate to="/login" replace />;
    return children;
  };

  const RequireAuth = ({ children }) => {
    if (!loaded) return null;
    if (!session) return <Navigate to="/login" replace />;
    return children;
  };

  return (
    <BrowserRouter>
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
        <Route path="/patient/dashboard" element={<RequirePatient><PatientDashboard /></RequirePatient>} />
        <Route path="/doctor/dashboard" element={<RequireDoctor><DoctorDashboard /></RequireDoctor>} />
        <Route path="/reports/:id" element={<RequireAuth><ReportView /></RequireAuth>} />
        <Route path="/prescriptions/:id" element={<RequireAuth><PrescriptionView /></RequireAuth>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
