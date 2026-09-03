import { useEffect, useState } from "react";
import { getApiError } from "../../api";
import { listMessages, listPapers, listReports, sendChat, uploadPaper } from "../../services/researchService";
import PageHeader from "./MainPageHeader";
import ResearchInput from "./ResearchInput";
import ResearchWorkspace from "./ResearchWorkspace";

function MainWorkspace({ activeSessionId, onSessionChanged, sessionError }) {
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [activeTab, setActiveTab] = useState("answer");
  const [isLoading, setIsLoading] = useState(false);
  const [isDataLoading, setIsDataLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [messages, setMessages] = useState([]);
  const [papers, setPapers] = useState([]);
  const [reports, setReports] = useState([]);
  const [selectedPaperId, setSelectedPaperId] = useState(null);

  useEffect(() => {
    setPrompt(""); setAnswer(""); setError(""); setMessages([]); setPapers([]); setReports([]); setSelectedPaperId(null);
    if (!activeSessionId) return;
    let current = true;
    setIsDataLoading(true);
    Promise.all([listMessages(activeSessionId), listPapers(activeSessionId), listReports(activeSessionId)]).then(([nextMessages, nextPapers, nextReports]) => {
      if (!current) return;
      setMessages(nextMessages); setPapers(nextPapers); setReports(nextReports);
      setAnswer([...nextMessages].reverse().find((item) => item.role === "assistant")?.content || "");
    }).catch((e) => current && setError(getApiError(e, "Could not load this conversation."))).finally(() => current && setIsDataLoading(false));
    return () => { current = false; };
  }, [activeSessionId]);

  async function runChat(message, showAnswer) {
    const cleanPrompt = message.trim();
    if (!cleanPrompt || !activeSessionId || isLoading) return false;
    setError(""); setIsLoading(true);
    try {
      const data = await sendChat(activeSessionId, cleanPrompt, selectedPaperId);
      const nextMessages = await listMessages(activeSessionId);
      setMessages(nextMessages); setAnswer(data.response);
      setReports(await listReports(activeSessionId));
      if (showAnswer) { setPrompt(""); setActiveTab("answer"); }
      onSessionChanged();
      return true;
    } catch (e) { setError(getApiError(e, "Sidekick could not complete the request.")); return false; }
    finally { setIsLoading(false); }
  }

  async function handleUpload(file) {
    if (!activeSessionId) { setError("Create or select a conversation before uploading a paper."); return; }
    setError(""); setIsUploading(true);
    try { const uploaded = await uploadPaper(activeSessionId, file); const nextPapers = await listPapers(activeSessionId); setPapers(nextPapers); setSelectedPaperId(uploaded.paper_id); setActiveTab("papers"); }
    catch (e) { setError(getApiError(e, "The PDF could not be uploaded and indexed.")); }
    finally { setIsUploading(false); }
  }

  return <main className="col-12 col-lg-10 p-3 p-md-4"><PageHeader/>{(sessionError || error) && <div className="alert alert-danger" role="alert">{sessionError || error}</div>}{!activeSessionId && !isDataLoading ? <div className="alert alert-info">Create a conversation to begin researching.</div> : <div className="row g-4"><div className="col-12 col-lg-5"><ResearchInput value={prompt} onChange={setPrompt} onRunSidekickClick={() => runChat(prompt, true)} isLoading={isLoading} isUploading={isUploading} disabled={!activeSessionId} papers={papers} selectedPaperId={selectedPaperId} onPaperChange={setSelectedPaperId} onUpload={handleUpload}/></div><div className="col-12 col-lg-7"><ResearchWorkspace value={answer} tabSelected={activeTab} onActiveTabChange={setActiveTab} messages={messages} papers={papers} reports={reports} selectedPaperId={selectedPaperId} onPaperSelect={setSelectedPaperId} onSendMessage={(value) => runChat(value, false)} isLoading={isLoading} isDataLoading={isDataLoading}/></div></div>}</main>;
}
export default MainWorkspace;
