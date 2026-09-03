import { useState } from "react";

function LoginForm(props) {
    const [userAuth, setUserAuth] = useState({ email: "", password: "" });

    function handleChange(event) {
        const { name, value } = event.target;
        setUserAuth((previous) => ({ ...previous, [name]: value }));
    }

    function handleSubmit(event) {
        event.preventDefault();
        props.onLogin(userAuth);
    }

    return (
        <form onSubmit={handleSubmit}>
            <div className="mb-3">
                <label htmlFor="loginEmail" className="form-label">Email</label>
                <input type="email" className="form-control" id="loginEmail" name="email" value={userAuth.email} onChange={handleChange} required autoComplete="email" disabled={props.isSubmitting} />
            </div>
            <div className="mb-3">
                <label htmlFor="loginPassword" className="form-label">Password</label>
                <input type="password" className="form-control" id="loginPassword" name="password" value={userAuth.password} onChange={handleChange} required minLength={8} autoComplete="current-password" disabled={props.isSubmitting} />
            </div>
            <button className="btn btn-primary w-100" disabled={props.isSubmitting}>{props.isSubmitting ? "Signing in..." : "Login"}</button>
        </form>
    );
}

export default LoginForm;
