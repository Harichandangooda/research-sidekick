import { useState } from "react";

function RegisterForm(props) {
    const [ userAuth, setUserAuth ] = useState({
        "createEmail": "",
        "createPassword": ""
    })
    const [ confirmedPassword, setConfirmedPassword ] = useState("");
    const [error, setError] = useState("");
    function handleSubmit(e) {
        e.preventDefault();

        if (userAuth.createPassword !== confirmedPassword) {
            setError("Passwords do not match.");
            return;
        }

        setError("");
        props.onRegister({ email: userAuth.createEmail, password: userAuth.createPassword });
    }
    function handleChange(e) {
        const { name, value } = e.target;
        setUserAuth((prev) => {
            return {
                ...prev,
                [name]: value
            }
        })
    }
    function handleConfirmedPasswordChange(e) {
        const value = e.target.value;
        setConfirmedPassword(value);
    }
    return (
        <form onSubmit={handleSubmit}>
            <div className="mb-3">
                <label htmlFor="registerEmail" className="form-label">Email</label>
                <input type="email" id="registerEmail" className="form-control" name="createEmail" value={userAuth.createEmail} onChange={handleChange} required autoComplete="email" disabled={props.isSubmitting} />
            </div>
            <div className="mb-3">
                <label htmlFor="registerPassword" className="form-label">Password</label>
                <input type="password" id="registerPassword" className="form-control" name="createPassword" value={userAuth.createPassword} onChange={handleChange} required minLength={8} maxLength={256} autoComplete="new-password" disabled={props.isSubmitting} />
            </div>
            <div className="mb-3">
                <label htmlFor="confirmPassword" className="form-label">Confirm Password</label>
                <input type="password" id="confirmPassword" className="form-control" name="confirmPassword" value={confirmedPassword} onChange={handleConfirmedPasswordChange} required minLength={8} autoComplete="new-password" disabled={props.isSubmitting}/>
            </div>
            {error && (<div className="alert alert-danger">{error}</div>)}
            <button className="btn btn-primary w-100" disabled={props.isSubmitting}>{props.isSubmitting ? "Creating account..." : "Create Account"}</button>
        </form>
    )
}

export default RegisterForm;
