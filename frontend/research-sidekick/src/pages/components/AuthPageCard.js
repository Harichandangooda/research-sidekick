import { useState } from "react";
import LoginForm from "./LoginForm.js";
import RegisterForm from "./RegisterForm.js";

function AuthPageCard(props) {
    const [ authMode, setAuthMode] = useState("login");
    function handleAuthMode(e) {
        const name = e.target.name;
        setAuthMode(name);
    }
    return (<div className="card shadow-sm border-0 rounded-3 p-4">
        <section className="text-center mb-4">
            <i className="bi-journal-text fs-2" />
            <h2 className="fw-semibold mb-1">Research Sidekick</h2>
            <p className="text-secondary">AI-assisted paper analysis and research workspace.</p>
        </section>
        <section className="mb-4">
            <div className="nav nav-tabs nav-fill">
                <button className={"nav-link " + (authMode === "login" ? "active" : "")} name="login" onClick={handleAuthMode}>Login</button>
                <button className={"nav-link " + (authMode === "register" ? "active" : "")} name="register" onClick={handleAuthMode}>Register</button>
            </div>
        </section>
        <section>
            <div>
                {props.error && <div className="alert alert-danger" role="alert">{props.error}</div>}
                {authMode === "login" ? <LoginForm onLogin={props.onLogin} isSubmitting={props.isSubmitting}/> : <RegisterForm onRegister={props.onRegister} isSubmitting={props.isSubmitting}/>}
            </div>
        </section>
    </div>)
}

export default AuthPageCard;
