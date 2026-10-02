import AnswerTab from "./AnswerTab";
import PapersTab from "./PapersTab";
import ReportsTab from "./ReportsTab";
import ChatTab from "./ChatTab";

function ResearchWorkspace(props) {
  const tabs = ["answer", "papers", "reports", "chat"];
  return <div className="card border-0 shadow-sm p-3 p-md-4 research-workspace d-flex flex-column"><div className="nav nav-tabs nav-fill flex-nowrap research-workspace-tabs">{tabs.map((tab) => <button key={tab} className={`nav-link text-capitalize ${props.tabSelected === tab ? "active" : ""}`} onClick={() => props.onActiveTabChange(tab)}>{tab}</button>)}</div><div className="pt-4 flex-grow-1 research-workspace-content">{props.isDataLoading ? <div className="text-center py-5"><div className="spinner-border text-primary"/><p className="text-secondary mt-2">Loading conversation…</p></div> : props.tabSelected === "answer" ? <AnswerTab value={props.value}/> : props.tabSelected === "papers" ? <PapersTab papers={props.papers} selectedPaperId={props.selectedPaperId} onSelect={props.onPaperSelect}/> : props.tabSelected === "reports" ? <ReportsTab reports={props.reports}/> : <ChatTab messages={props.messages} onSend={props.onSendMessage} onUpload={props.onUpload} isLoading={props.isLoading} isUploading={props.isUploading}/>}</div></div>;
}
export default ResearchWorkspace;
