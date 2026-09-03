import { useEffect, useState } from "react";
import { getApiError } from "../api";
import { createSession, deleteSession, listSessions, renameSession } from "../services/researchService";
import Sidebar from "./components/Sidebar";
import MainWorkspace from "./components/MainWorkspace";

function WorkspacePage({ user, onLogout }) {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  async function refreshSessions(preferredId) {
    const items = await listSessions();
    setSessions(items);
    setActiveSessionId((current) => preferredId || (items.some((item) => item.id === current) ? current : items[0]?.id || null));
  }
  useEffect(() => {
    let current = true;
    listSessions().then((items) => { if (current) { setSessions(items); setActiveSessionId(items[0]?.id || null); } }).catch((e) => current && setError(getApiError(e, "Could not load conversations."))).finally(() => current && setIsLoading(false));
    return () => { current = false; };
  }, []);
  async function handleCreate() { setError(""); try { const item = await createSession(); await refreshSessions(item.id); } catch (e) { setError(getApiError(e, "Could not create a conversation.")); } }
  async function handleRename(id, title) { setError(""); try { const item = await renameSession(id, title); setSessions((all) => all.map((x) => x.id === id ? item : x)); } catch (e) { setError(getApiError(e, "Could not rename the conversation.")); } }
  async function handleDelete(id) { setError(""); try { await deleteSession(id); await refreshSessions(); } catch (e) { setError(getApiError(e, "Could not delete the conversation.")); } }
  return <div className="row g-0 min-vh-100"><Sidebar sessions={sessions} activeSessionId={activeSessionId} onSelect={setActiveSessionId} onCreate={handleCreate} onRename={handleRename} onDelete={handleDelete} user={user} onLogout={onLogout} isLoading={isLoading}/><MainWorkspace activeSessionId={activeSessionId} onSessionChanged={() => refreshSessions(activeSessionId)} sessionError={error}/></div>;
}
export default WorkspacePage;
