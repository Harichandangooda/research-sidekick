import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import WorkspacePage from "./WorkspacePage";
import * as service from "../services/researchService";

jest.mock("../services/researchService", () => ({
  listSessions: jest.fn(), createSession: jest.fn(),
  renameSession: jest.fn(), deleteSession: jest.fn(),
}));
jest.mock("./components/MainWorkspace", () => ({ activeSessionId }) => <div data-testid="active">{activeSessionId}</div>);
jest.mock("./components/Sidebar", () => ({ sessions, onCreate, onDelete }) => <div>
  <button onClick={onCreate}>Create</button>
  <button onClick={() => onDelete("old")}>Delete</button>
  {sessions.map((item) => <div key={item.id}>{item.title}</div>)}
</div>);

beforeEach(() => jest.resetAllMocks());

test("a late initial list cannot replace a newly created conversation", async () => {
  let finishInitial;
  service.listSessions.mockReturnValueOnce(new Promise((resolve) => { finishInitial = resolve; }))
    .mockResolvedValueOnce([{ id: "new", title: "New conversation" }]);
  service.createSession.mockResolvedValue({ id: "new" });
  render(<WorkspacePage user={{ email: "user@example.com" }} onLogout={jest.fn()} />);
  fireEvent.click(screen.getByText("Create"));
  await waitFor(() => expect(screen.getByTestId("active")).toHaveTextContent("new"));
  await act(async () => { finishInitial([{ id: "old", title: "Stale conversation" }]); });
  expect(screen.getByTestId("active")).toHaveTextContent("new");
  expect(screen.queryByText("Stale conversation")).not.toBeInTheDocument();
});

test("an older refresh cannot restore a conversation deleted by a newer refresh", async () => {
  let finishCreateRefresh;
  service.listSessions.mockResolvedValueOnce([{ id: "old", title: "Old conversation" }])
    .mockReturnValueOnce(new Promise((resolve) => { finishCreateRefresh = resolve; }))
    .mockResolvedValueOnce([]);
  service.createSession.mockResolvedValue({ id: "old" });
  service.deleteSession.mockResolvedValue();
  render(<WorkspacePage user={{ email: "user@example.com" }} onLogout={jest.fn()} />);
  await screen.findByText("Old conversation");
  fireEvent.click(screen.getByText("Create"));
  await waitFor(() => expect(service.listSessions).toHaveBeenCalledTimes(2));
  fireEvent.click(screen.getByText("Delete"));
  await waitFor(() => expect(screen.queryByText("Old conversation")).not.toBeInTheDocument());
  await act(async () => { finishCreateRefresh([{ id: "old", title: "Old conversation" }]); });
  expect(screen.getByTestId("active")).toBeEmptyDOMElement();
  expect(screen.queryByText("Old conversation")).not.toBeInTheDocument();
});
