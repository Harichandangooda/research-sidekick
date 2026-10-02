import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import MainWorkspace from "./MainWorkspace";
import * as service from "../../services/researchService";

jest.mock("../../services/researchService", () => ({
  listMessages: jest.fn(), listPapers: jest.fn(), listReports: jest.fn(),
  sendChat: jest.fn(), uploadPaper: jest.fn(),
}));

beforeEach(() => {
  HTMLElement.prototype.scrollIntoView = jest.fn();
  jest.clearAllMocks();
  service.listMessages.mockResolvedValue([]);
  service.listPapers.mockResolvedValue([]);
  service.listReports.mockResolvedValue([]);
  service.sendChat.mockResolvedValue({ response: "Done" });
});

async function workspace() {
  render(<MainWorkspace activeSessionId="session" onSessionChanged={jest.fn()} />);
  await waitFor(() => expect(service.listPapers).toHaveBeenCalled());
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
}

test("blank input shows validation and does not call backend processing", async () => {
  await workspace();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "   " } });
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  expect(screen.getByRole("alert")).toHaveTextContent("Please enter a prompt or upload at least one file.");
  expect(service.sendChat).not.toHaveBeenCalled();
});

test("multiple uploads retain successful files and report individual failures", async () => {
  await workspace();
  const files = [new File(["pdf"], "first.pdf"), new File(["bad"], "broken.pdf"), new File(["pdf"], "last.pdf")];
  service.uploadPaper.mockResolvedValueOnce({ paper_id: 1 }).mockRejectedValueOnce({ response: { data: { detail: "Corrupt PDF" } } }).mockResolvedValueOnce({ paper_id: 3 });
  service.listPapers.mockResolvedValue([{ id: 1, file_name: "first.pdf", source: "uploaded_pdf" }, { id: 3, file_name: "last.pdf", source: "uploaded_pdf" }]);
  fireEvent.change(screen.getByLabelText("Upload PDFs"), { target: { files } });
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("broken.pdf: Corrupt PDF"));
  expect(service.uploadPaper).toHaveBeenCalledTimes(3);
  expect(screen.getByRole("option", { name: "first.pdf" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "last.pdf" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(service.sendChat).toHaveBeenCalledWith("session", "", null, true, expect.any(String)));
});

test("prompt alone is sent without upload intent", async () => {
  await workspace();
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Find papers on AI" } });
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(service.sendChat).toHaveBeenCalledWith("session", "Find papers on AI", null, false, expect.any(String)));
});

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("a late chat result cannot overwrite another session or switch it back", async () => {
  const pending = deferred();
  const changed = jest.fn();
  service.sendChat.mockReturnValueOnce(pending.promise);
  const view = render(<MainWorkspace activeSessionId="first" onSessionChanged={changed}/>);
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Analyze first" } });
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  view.rerender(<MainWorkspace activeSessionId="second" onSessionChanged={changed}/>);
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
  await act(async () => { pending.resolve({ response: "First session answer" }); });
  expect(screen.queryByText("First session answer")).not.toBeInTheDocument();
  expect(changed).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: /Run Sidekick/ })).toBeEnabled();
});

test("late upload results and failures do not affect the new session", async () => {
  const pending = deferred();
  service.uploadPaper.mockReturnValueOnce(pending.promise);
  const view = render(<MainWorkspace activeSessionId="first" onSessionChanged={jest.fn()}/>);
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Upload PDFs"), { target: { files: [new File(["pdf"], "old.pdf")] } });
  view.rerender(<MainWorkspace activeSessionId="second" onSessionChanged={jest.fn()}/>);
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
  await act(async () => { pending.reject({ response: { data: { detail: "Old failure" } } }); });
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: /Run Sidekick/ })).toBeEnabled();
  expect(service.listPapers.mock.calls.filter(([id]) => id === "first")).toHaveLength(1);
});

test("retrying a failed request reuses its ID", async () => {
  await workspace();
  service.sendChat.mockRejectedValueOnce({ response: { data: { detail: "Try again" } } });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Research AI" } });
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Try again"));
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(service.sendChat).toHaveBeenCalledTimes(2));
  expect(service.sendChat.mock.calls[0][4]).toBe(service.sendChat.mock.calls[1][4]);
});

test("online paper metadata and source links are displayed", async () => {
  service.listPapers.mockResolvedValue([{ id: 1, file_name: "Paper", title: "Discovered paper", source: "online_discovery",
    authors: "A. Researcher", year: 2025, summary: "A useful summary", url: "https://example.org/paper", relevance: 0.8,
    relevance_reason: "Matches the topic" }]);
  await workspace();
  fireEvent.click(screen.getByRole("button", { name: "papers" }));
  expect(screen.getByText("A useful summary")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "View paper source" })).toHaveAttribute("href", "https://example.org/paper");
  expect(screen.getByText(/Relevance: 80%/)).toBeInTheDocument();
});

test("a session change during chat refresh discards the old refreshed data", async () => {
  const pending = deferred();
  const changed = jest.fn();
  const view = render(<MainWorkspace activeSessionId="first" onSessionChanged={changed}/>);
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
  service.listMessages.mockReturnValueOnce(pending.promise);
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Research AI" } });
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(service.listMessages).toHaveBeenCalledTimes(2));
  view.rerender(<MainWorkspace activeSessionId="second" onSessionChanged={changed}/>);
  await waitFor(() => expect(screen.queryByText(/Loading conversation/)).not.toBeInTheDocument());
  await act(async () => { pending.resolve([{ role: "assistant", content: "Old refreshed answer" }]); });
  expect(screen.queryByText("Done")).not.toBeInTheDocument();
  expect(screen.queryByText("Old refreshed answer")).not.toBeInTheDocument();
  expect(changed).not.toHaveBeenCalled();
});

test("a failed refresh retries the completed chat using the same request ID", async () => {
  await workspace();
  service.listMessages.mockRejectedValueOnce({ response: { data: { detail: "Refresh failed" } } });
  fireEvent.change(screen.getByRole("textbox"), { target: { value: "Research AI" } });
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Refresh failed"));
  fireEvent.click(screen.getByRole("button", { name: /Run Sidekick/ }));
  await waitFor(() => expect(screen.getByText("Done")).toBeInTheDocument());
  expect(service.sendChat.mock.calls[0][4]).toBe(service.sendChat.mock.calls[1][4]);
});

test.each([{ names: [] }, { names: ["C.pdf"] }, { names: ["C.pdf", "D.pdf"] }])("follow-up accepts new files $names in the existing session", async ({ names }) => {
  const papers = [{ id: 1, file_name: "A.pdf", source: "uploaded_pdf" }, { id: 2, file_name: "B.pdf", source: "uploaded_pdf" }];
  service.listPapers.mockImplementation(async () => [...papers]);
  service.listMessages.mockResolvedValue([{ role: "assistant", content: "Original experiment plan", created_at: "2026-01-01" }]);
  service.uploadPaper.mockImplementation(async (sessionId, file) => {
    const id = papers.length + 1;
    papers.push({ id, file_name: file.name, source: "uploaded_pdf" });
    return { paper_id: id };
  });
  await workspace();
  fireEvent.click(screen.getByRole("button", { name: "chat" }));
  fireEvent.change(screen.getByPlaceholderText("Ask a follow-up question..."), { target: { value: "What evidence supports the method?" } });
  if (names.length) {
    fireEvent.change(screen.getByLabelText("Active Paper"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Add papers to this follow-up"), {
      target: { files: names.map((name) => new File(["pdf"], name, { type: "application/pdf" })) },
    });
    await waitFor(() => expect(service.uploadPaper).toHaveBeenCalledTimes(names.length));
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
    expect(screen.getByText("Original experiment plan")).toBeInTheDocument();
    expect(service.sendChat).not.toHaveBeenCalled();
    for (const [sessionId] of service.uploadPaper.mock.calls) expect(sessionId).toBe("session");
  } else {
    expect(service.uploadPaper).not.toHaveBeenCalled();
  }
  for (const name of ["A.pdf", "B.pdf", ...names]) expect(screen.getByRole("option", { name })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(service.sendChat).toHaveBeenCalledWith("session", "What evidence supports the method?", null, Boolean(names.length), expect.any(String)));
  await waitFor(() => expect(screen.getByPlaceholderText("Ask a follow-up question...")).toHaveValue(""));
});

test("failed follow-up uploads leave old papers and a filename-specific error after sending", async () => {
  service.listPapers.mockResolvedValue([{ id: 1, file_name: "A.pdf", source: "uploaded_pdf" }]);
  service.uploadPaper.mockRejectedValueOnce({ response: { data: { detail: "Corrupt PDF" } } });
  await workspace();
  fireEvent.click(screen.getByRole("button", { name: "chat" }));
  fireEvent.change(screen.getByPlaceholderText("Ask a follow-up question..."), { target: { value: "Explain A" } });
  fireEvent.change(screen.getByLabelText("Add papers to this follow-up"), { target: { files: [new File(["bad"], "broken.pdf")] } });
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("broken.pdf: Corrupt PDF"));
  expect(screen.getByRole("option", { name: "A.pdf" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "broken.pdf" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(service.sendChat).toHaveBeenCalledWith("session", "Explain A", null, true, expect.any(String)));
  await waitFor(() => expect(screen.getByPlaceholderText("Ask a follow-up question...")).toHaveValue(""));
  expect(screen.getByRole("alert")).toHaveTextContent("broken.pdf: Corrupt PDF");
});

test("follow-up waits for indexing before sending and retains successful files from a mixed batch", async () => {
  const pending = deferred();
  const papers = [{ id: 1, file_name: "A.pdf", source: "uploaded_pdf" }];
  service.listPapers.mockImplementation(async () => [...papers]);
  service.uploadPaper.mockImplementationOnce(async () => {
    const result = await pending.promise;
    papers.push({ id: 2, file_name: "C.pdf", source: "uploaded_pdf" });
    return result;
  }).mockRejectedValueOnce({ response: { data: { detail: "Indexing failed" } } });
  await workspace();
  fireEvent.click(screen.getByRole("button", { name: "chat" }));
  fireEvent.change(screen.getByPlaceholderText("Ask a follow-up question..."), { target: { value: "Compare evidence" } });
  fireEvent.change(screen.getByLabelText("Add papers to this follow-up"), {
    target: { files: [new File(["pdf"], "C.pdf"), new File(["bad"], "broken.pdf")] },
  });
  expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  expect(service.sendChat).not.toHaveBeenCalled();
  await act(async () => { pending.resolve({ paper_id: 2 }); });
  await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).toBeEnabled());
  expect(screen.getByPlaceholderText("Ask a follow-up question...")).toHaveValue("Compare evidence");
  expect(screen.getByRole("option", { name: "A.pdf" })).toBeInTheDocument();
  expect(screen.getByRole("option", { name: "C.pdf" })).toBeInTheDocument();
  expect(screen.queryByRole("option", { name: "broken.pdf" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(service.sendChat).toHaveBeenCalledWith("session", "Compare evidence", null, true, expect.any(String)));
  expect(screen.getByRole("alert")).toHaveTextContent("broken.pdf: Indexing failed");
});
