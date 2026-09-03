import { useRef, useState } from "react";

function ResearchInput({ value, onChange, onRunSidekickClick, isLoading, isUploading, disabled, papers, selectedPaperId, onPaperChange, onUpload }) {
  const inputRef = useRef(null);
  const [fileError, setFileError] = useState("");
  function chooseFile(event) {
    const file = event.target.files?.[0];
    setFileError("");
    if (!file) return;
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) { setFileError("Choose a PDF file."); event.target.value = ""; return; }
    onUpload(file).finally(() => { if (inputRef.current) inputRef.current.value = ""; });
  }
  return <div className="card border-0 shadow-sm p-4"><h4 className="fw-semibold mb-1">Ask Sidekick</h4><p className="text-secondary small mb-4">Ask a question about your research or analyze an uploaded paper</p><form onSubmit={(e) => { e.preventDefault(); onRunSidekickClick(); }}><textarea className="form-control" placeholder="Ask a question about a paper, research topic, or experiment..." rows={5} value={value} onChange={(e) => onChange(e.target.value)} maxLength={10000} disabled={disabled || isLoading}/><section className="d-flex flex-wrap gap-2 mt-3">{["Summarize the main contributions", "Compare this approach with RAG", "Design an experiment to evaluate this method"].map((text) => <button key={text} className="btn btn-outline-secondary btn-sm" onClick={() => onChange(text)} type="button" disabled={disabled || isLoading}>{text}</button>)}</section><hr/><label className="form-label" htmlFor="paperSelect">Active Paper</label><select id="paperSelect" className="form-select mb-2" value={selectedPaperId ?? ""} onChange={(e) => onPaperChange(e.target.value ? Number(e.target.value) : null)} disabled={disabled || isLoading || isUploading}><option value="">No paper</option>{papers.map((paper) => <option value={paper.id} key={paper.id}>{paper.file_name}</option>)}</select><label className="form-label" htmlFor="paperUpload">Upload a PDF</label><input ref={inputRef} id="paperUpload" type="file" className="form-control" accept=".pdf,application/pdf" onChange={chooseFile} disabled={disabled || isLoading || isUploading}/>{fileError && <div className="text-danger small mt-2">{fileError}</div>}{isUploading && <div className="small text-secondary mt-2"><span className="spinner-border spinner-border-sm me-2"/>Uploading and indexing…</div>}<button className="btn btn-primary mt-3 w-100" type="submit" disabled={disabled || isLoading || isUploading || !value.trim()}>{isLoading ? <><span className="spinner-border spinner-border-sm me-2"/>Analyzing…</> : <><i className="bi-stars me-2"/>Run Sidekick</>}</button></form></div>;
}
export default ResearchInput;
