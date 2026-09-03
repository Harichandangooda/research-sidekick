function AnswerTab({ value }) {
  if (!value) return <p className="text-secondary">Run Sidekick to generate an analysis.</p>;
  return <div className="overflow-safe"><p className="small text-secondary mb-2">Generated Response</p><h4>Answer</h4><div className="preserve-lines">{value}</div></div>;
}
export default AnswerTab;
