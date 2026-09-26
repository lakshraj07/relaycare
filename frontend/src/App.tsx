import { Routes, Route, useLocation } from 'react-router-dom';
import Navigation from './components/Navigation';
import Footer from './components/Footer';
import LandingPage from './pages/LandingPage';
import MissionPage from './pages/MissionPage';
import TechnologyPage from './pages/TechnologyPage';
import AppDashboard from './pages/AppDashboard';

function App() {
  const { pathname } = useLocation();
  return (
    <>
      <Navigation />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/mission" element={<MissionPage />} />
        <Route path="/technology" element={<TechnologyPage />} />
        <Route path="/app" element={<AppDashboard />} />
      </Routes>
      {pathname !== '/app' && <Footer />}
    </>
  );
}

export default App;
