import { useState } from "react";
import AuthPageCard from "./components/AuthPageCard";
import { getApiError } from "../api";
import { login, register } from "../services/authService";

function AuthPage({ onAuthenticated }) {
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function authenticate(action, credentials) {
    setError("");
    setIsSubmitting(true);
    try { onAuthenticated(await action(credentials)); }
    catch (requestError) { setError(getApiError(requestError, "Authentication failed.")); }
    finally { setIsSubmitting(false); }
  }

  return <div className="min-vh-100 d-flex align-items-center justify-content-center p-3"><div className="row w-100 justify-content-center"><div className="col-12 col-md-7 col-lg-5 col-xl-4"><AuthPageCard error={error} isSubmitting={isSubmitting} onLogin={(values) => authenticate(login, values)} onRegister={(values) => authenticate(register, values)} /></div></div></div>;
}

export default AuthPage;
