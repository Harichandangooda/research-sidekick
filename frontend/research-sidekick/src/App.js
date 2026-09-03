import "./App.css";
import { useEffect, useState } from "react";
import WorkspacePage from "./pages/WorkspacePage";
import AuthPage from "./pages/AuthPage";
import { getToken, onAuthenticationFailure, setToken } from "./api";
import { getCurrentUser } from "./services/authService";

function App() {
  const [user, setUser] = useState(null);
  const [isRestoring, setIsRestoring] = useState(Boolean(getToken()));

  function logout() {
    setToken(null);
    setUser(null);
  }

  useEffect(() => {
    onAuthenticationFailure(logout);
    if (getToken()) getCurrentUser().then(setUser).catch(logout).finally(() => setIsRestoring(false));
    return () => onAuthenticationFailure(null);
  }, []);

  function handleAuthenticated(authResponse) {
    setToken(authResponse.access_token);
    setUser(authResponse.user);
  }

  if (isRestoring) return <div className="min-vh-100 d-flex align-items-center justify-content-center"><div className="spinner-border text-primary" aria-label="Restoring session" /></div>;
  return <div className="min-vh-100 bg-light container-fluid px-0">{user ? <WorkspacePage user={user} onLogout={logout} /> : <AuthPage onAuthenticated={handleAuthenticated} />}</div>;
}

export default App;
