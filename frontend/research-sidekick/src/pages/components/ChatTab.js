import { useEffect, useRef, useState } from "react";

function ChatTab({ messages, onSend, isLoading }) {
  const [message, setMessage] = useState("");
  const endRef = useRef(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, isLoading]);
  async function handleSend(event) { event.preventDefault(); if (!message.trim()) return; if (await onSend(message)) setMessage(""); }
  return <div className="d-flex flex-column h-100"><p className="small text-secondary mb-2">Continue Research</p><h4 className="mb-3">Follow-up Chat</h4><div className="chat-messages flex-grow-1 overflow-auto mb-3">{!messages.length ? <p className="text-secondary">Ask a follow-up question about the current paper or analysis.</p> : messages.map((item, index) => <div className={`border rounded p-3 mb-2 overflow-safe ${item.role === "user" ? "bg-primary-subtle ms-md-4" : "bg-light me-md-4"}`} key={`${item.created_at}-${index}`}><p className="small text-secondary mb-1">{item.role === "user" ? "You" : "Sidekick"}</p><div className="preserve-lines">{item.content}</div></div>)}{isLoading && <div className="small text-secondary"><span className="spinner-border spinner-border-sm me-2"/>Sidekick is thinking…</div>}<div ref={endRef}/></div><form onSubmit={handleSend}><textarea className="form-control mb-3" rows={3} placeholder="Ask a follow-up question..." value={message} onChange={(e) => setMessage(e.target.value)} maxLength={10000} disabled={isLoading}/><div className="d-flex justify-content-end"><button className="btn btn-primary" type="submit" disabled={isLoading || !message.trim()}><i className="bi-send me-2"/>Send</button></div></form></div>;
}
export default ChatTab;
