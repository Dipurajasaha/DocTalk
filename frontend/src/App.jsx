import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import Login from './pages/Login';
import PatientDashboard from './pages/PatientDashboard';
import DoctorDashboard from './pages/DoctorDashboard';

function App({ initialSession, setSession }) {
  const getSession = () => {
    if (initialSession) return initialSession;
    try {
      const local = localStorage.getItem('doctalk_session');
      const token = localStorage.getItem('doctalk_token');
      if (!local) return null;
      const parsed = JSON.parse(local);
      if (token) return { ...parsed, token };
      return parsed;
    } catch (e) { return null; }
  };

  const RequirePatient = ({ children }) => {
    const s = getSession();
    if (!s) return <Navigate to="/login" replace />;
    if (s.role !== 'patient') return <Navigate to="/login" replace />;
    return children;
  };

  const RequireDoctor = ({ children }) => {
    const s = getSession();
    if (!s) return <Navigate to="/login" replace />;
    if (s.role !== 'doctor') return <Navigate to="/login" replace />;
    return children;
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login setSession={setSession} />} />
        <Route path="/patient/dashboard" element={<RequirePatient><PatientDashboard /></RequirePatient>} />
        <Route path="/doctor/dashboard" element={<RequireDoctor><DoctorDashboard /></RequireDoctor>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
