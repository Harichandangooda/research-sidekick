import { useCallback, useEffect, useRef, useState } from "react";
import { getApiError } from "../api";
import { createSession, deleteSession, listSessions, renameSession } from "../services/researchService";
import Sidebar from "./components/Sidebar";
import MainWorkspace from "./components/MainWorkspace";

function WorkspacePage({ user, onLogout }) {
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");
  const refreshVersion = useRef(0);
  const refreshSessions = useCallback(async (preferredId) => {
    const version = ++refreshVersion.current;
    const items = await listSessions();
    if (version !== refreshVersion.current) return;
    setSessions(items);
    setIsLoading(false);
    setActiveSessionId((current) => preferredId || (items.some((item) => item.id === current) ? current : items[0]?.id || null));
  }, []);
  useEffect(() => {
    let current = true;
    refreshSessions().catch((e) => current && setError(getApiError(e, "Could not load conversations."))).finally(() => current && setIsLoading(false));
    return () => { current = false; refreshVersion.current += 1; };
  }, [refreshSessions]);
  async function handleCreate() { setError(""); try { const item = await createSession(); await refreshSessions(item.id); } catch (e) { setError(getApiError(e, "Could not create a conversation.")); } }
  async function handleRename(id, title) { setError(""); try { const item = await renameSession(id, title); setSessions((all) => all.map((x) => x.id === id ? item : x)); } catch (e) { setError(getApiError(e, "Could not rename the conversation.")); } }
  async function handleDelete(id) { setError(""); try { await deleteSession(id); await refreshSessions(); } catch (e) { setError(getApiError(e, "Could not delete the conversation.")); } }
  return <div className="row g-0 min-vh-100"><Sidebar sessions={sessions} activeSessionId={activeSessionId} onSelect={setActiveSessionId} onCreate={handleCreate} onRename={handleRename} onDelete={handleDelete} user={user} onLogout={onLogout} isLoading={isLoading}/><MainWorkspace key={activeSessionId} activeSessionId={activeSessionId} onSessionChanged={() => refreshSessions()} sessionError={error}/></div>;
}
export default WorkspacePage;
