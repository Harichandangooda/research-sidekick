import { useEffect, useRef, useState } from "react";
import { getApiError } from "../../api";
import { listMessages, listPapers, listReports, sendChat, uploadPaper } from "../../services/researchService";
import PageHeader from "./MainPageHeader";
import ResearchInput from "./ResearchInput";
import ResearchWorkspace from "./ResearchWorkspace";

function newRequestId() {
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function MainWorkspace({ activeSessionId, onSessionChanged, sessionError }) {
  const [prompt, setPrompt] = useState("");
  const [answer, setAnswer] = useState("");
  const [activeTab, setActiveTab] = useState("answer");
  const [isLoading, setIsLoading] = useState(false);
  const [isDataLoading, setIsDataLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [messages, setMessages] = useState([]);
  const [papers, setPapers] = useState([]);
  const [reports, setReports] = useState([]);
  const [selectedPaperId, setSelectedPaperId] = useState(null);
  const [uploadAttempted, setUploadAttempted] = useState(false);
  const requestScope = useRef({ active: false });
  const busy = useRef(false);
  const retryRequest = useRef(null);

  useEffect(() => {
    const scope = { active: true };
    requestScope.current = scope;
    const current = () => scope.active;
    busy.current = false;
    retryRequest.current = null;
    setIsLoading(false); setIsUploading(false); setIsDataLoading(Boolean(activeSessionId));
    setUploadAttempted(false);
    setUploadError("");
    setPrompt(""); setAnswer(""); setError(""); setMessages([]); setPapers([]); setReports([]); setSelectedPaperId(null);
    if (activeSessionId) {
      Promise.all([listMessages(activeSessionId), listPapers(activeSessionId), listReports(activeSessionId)]).then(([nextMessages, nextPapers, nextReports]) => {
        if (!current()) return;
        setMessages(nextMessages); setPapers(nextPapers); setReports(nextReports);
        setAnswer([...nextMessages].reverse().find((item) => item.role === "assistant")?.content || "");
      }).catch((e) => current() && setError(getApiError(e, "Could not load this conversation."))).finally(() => current() && setIsDataLoading(false));
    }
    return () => { scope.active = false; };
  }, [activeSessionId]);

  async function runChat(message, showAnswer) {
    const cleanPrompt = message.trim();
    if (!activeSessionId || busy.current || isDataLoading) return false;
    if (!cleanPrompt && !papers.some((paper) => paper.source === "uploaded_pdf")) {
      setError("Please enter a prompt or upload at least one file."); return false;
    }
    const scope = requestScope.current;
    const current = () => scope.active;
    const signature = JSON.stringify([cleanPrompt, selectedPaperId, uploadAttempted, papers.map((paper) => paper.id)]);
    if (retryRequest.current?.signature !== signature) {
      retryRequest.current = { signature, id: newRequestId() };
    }
    const requestId = retryRequest.current.id;
    busy.current = true;
    setError(""); setIsLoading(true);
    try {
      const data = await sendChat(activeSessionId, cleanPrompt, selectedPaperId, uploadAttempted, requestId);
      if (!current()) return false;
      const [nextMessages, nextReports, nextPapers] = await Promise.all([
        listMessages(activeSessionId), listReports(activeSessionId), listPapers(activeSessionId),
      ]);
      if (!current()) return false;
      setMessages(nextMessages); setAnswer(data.response); setReports(nextReports); setPapers(nextPapers);
      setUploadAttempted(false);
      if (showAnswer) { setPrompt(""); setActiveTab("answer"); }
      retryRequest.current = null;
      try { await onSessionChanged(); }
      catch (e) { if (current()) setError(getApiError(e, "Research completed, but the conversation list could not refresh.")); }
      return true;
    } catch (e) { if (current()) setError(getApiError(e, "Sidekick could not complete the request.")); return false; }
    finally { if (current()) { busy.current = false; setIsLoading(false); } }
  }

  async function handleUpload(files, showPapers = true) {
    if (!files.length) return;
    if (!activeSessionId) { setError("Create or select a conversation before uploading a paper."); return; }
    if (busy.current || isDataLoading) return;
    const scope = requestScope.current;
    const current = () => scope.active;
    busy.current = true;
    retryRequest.current = null;
    setUploadAttempted(true); setError(""); setUploadError(""); setIsUploading(true);
    try {
      const results = await Promise.allSettled(files.map((file) => uploadPaper(activeSessionId, file)));
      if (!current()) return;
      const failures = results.flatMap((result, index) => result.status === "rejected"
        ? [`${files[index].name}: ${getApiError(result.reason, "Could not upload and index this PDF.")}`] : []);
      setUploadError(failures.join("; "));
      const nextPapers = await listPapers(activeSessionId);
      if (!current()) return;
      setPapers(nextPapers);
      if (results.some((result) => result.status === "fulfilled")) setSelectedPaperId(null);
      if (showPapers) setActiveTab("papers");
    } catch (e) { if (current()) setError(getApiError(e, "Could not refresh uploaded papers.")); }
    finally { if (current()) { busy.current = false; setIsUploading(false); } }
  }

  return <main className="col-12 col-lg-10 p-3 p-md-4">
    <PageHeader/>
    {(sessionError || uploadError || error) && <div className="alert alert-danger" role="alert">{sessionError || [uploadError, error].filter(Boolean).join("; ")}</div>}
    {!activeSessionId && !isDataLoading ? <div className="alert alert-info">Create a conversation to begin researching.</div> :
      <div className="row g-4">
        <div className="col-12 col-lg-5">
          <ResearchInput value={prompt} onChange={setPrompt} onRunSidekickClick={() => runChat(prompt, true)}
            isLoading={isLoading} isUploading={isUploading} disabled={!activeSessionId || isDataLoading}
            papers={papers} selectedPaperId={selectedPaperId} onPaperChange={setSelectedPaperId} onUpload={handleUpload}/>
        </div>
        <div className="col-12 col-lg-7">
          <ResearchWorkspace value={answer} tabSelected={activeTab} onActiveTabChange={setActiveTab}
            messages={messages} papers={papers} reports={reports} selectedPaperId={selectedPaperId}
            onPaperSelect={setSelectedPaperId} onSendMessage={(value) => runChat(value, false)}
            onUpload={(files) => handleUpload(files, false)} isUploading={isUploading}
            isLoading={isLoading || isUploading || isDataLoading} isDataLoading={isDataLoading}/>
        </div>
      </div>}
  </main>;
}
export default MainWorkspace;
