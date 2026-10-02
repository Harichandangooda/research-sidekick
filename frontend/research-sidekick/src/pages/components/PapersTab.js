function formatBytes(bytes) {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / (1024 ** index)).toFixed(index ? 1 : 0)} ${units[index]}`;
}

function PapersTab({ papers, selectedPaperId, onSelect }) {
  return <div>
    <p className="small text-secondary mb-2">Research Library</p>
    <h4 className="mb-3">Papers</h4>
    {!papers.length ? <p className="text-secondary">No papers in this conversation.</p> :
      <div className="list-group">{papers.map((paper) => {
        const online = paper.source === "online_discovery";
        const sourceUrl = /^https?:\/\//i.test(paper.url || "") ? paper.url : null;
        return <div className="list-group-item" key={paper.id}>
          <button type="button" className={`btn text-start w-100 ${paper.id === selectedPaperId ? "btn-primary" : "btn-light"}`}
            aria-pressed={paper.id === selectedPaperId} onClick={() => onSelect(paper.id)}>
            <h6 className="fw-semibold mb-1 text-break">{paper.title || paper.file_name}</h6>
            <p className="small mb-0">{online ? "Online discovery · Summary only" : `Uploaded PDF · ${formatBytes(paper.file_size)}`}</p>
            {paper.created_at && <p className="small mb-0">{new Date(paper.created_at).toLocaleDateString()}</p>}
          </button>
          {online && <div className="small mt-2">
            <p className="mb-1">{[paper.authors, paper.year].filter(Boolean).join(" · ")}</p>
            {paper.summary && <p className="mb-1">{paper.summary}</p>}
            {paper.relevance != null && <p className="mb-1">Relevance: {Math.round(paper.relevance * 100)}%{paper.relevance_reason && ` · ${paper.relevance_reason}`}</p>}
            {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer">View paper source</a>}
          </div>}
        </div>;
      })}</div>}
  </div>;
}
export default PapersTab;
