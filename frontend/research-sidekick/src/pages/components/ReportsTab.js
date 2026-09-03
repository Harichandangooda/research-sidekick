import { useState } from "react";

function ReportsTab({ reports }) {
  const [selectedId, setSelectedId] = useState(null);
  if (!reports.length) return <div><p className="small text-secondary mb-2">Research History</p><h4>Saved Reports</h4><p className="text-secondary">No reports have been generated.</p></div>;
  return <div><p className="small text-secondary mb-2">Research History</p><h4 className="mb-3">Saved Reports</h4><div className="d-flex flex-column gap-3">{reports.map((report) => <button type="button" className="border rounded p-3 text-start bg-white" key={report.id} onClick={() => setSelectedId(selectedId === report.id ? null : report.id)}><h6 className="fw-semibold mb-1 text-break">{report.title}</h6><p className="small text-secondary mb-2">{new Date(report.created_at).toLocaleString()}</p><div className={`overflow-safe preserve-lines ${selectedId === report.id ? "" : "report-preview"}`}>{report.content}</div></button>)}</div></div>;
}
export default ReportsTab;
