function SessionItem({ session, activeSessionId, onSelect, onRename, onDelete }) {
  function rename(event) { event.stopPropagation(); const title = window.prompt("Conversation title", session.title)?.trim(); if (title && title !== session.title) onRename(session.id, title); }
  function remove(event) { event.stopPropagation(); if (window.confirm(`Delete “${session.title}”? This cannot be undone.`)) onDelete(session.id); }
  return <div className={`session-item d-flex align-items-center mb-1 rounded ${session.id === activeSessionId ? "active" : ""}`}><button className="btn text-start flex-grow-1 d-flex align-items-center gap-2 text-truncate border-0" onClick={() => onSelect(session.id)}><i className="bi-chat-left-text"/><span className="text-truncate">{session.title}</span></button><button className="btn btn-sm px-1" onClick={rename} aria-label={`Rename ${session.title}`}><i className="bi-pencil"/></button><button className="btn btn-sm px-1 me-1 text-danger" onClick={remove} aria-label={`Delete ${session.title}`}><i className="bi-trash"/></button></div>;
}
export default SessionItem;
