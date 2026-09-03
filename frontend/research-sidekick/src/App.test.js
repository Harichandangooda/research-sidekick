import { render, screen } from "@testing-library/react";
import App from "./App";

test("renders authentication screen when signed out", () => {
  localStorage.clear();
  render(<App />);
  expect(screen.getByRole("heading", { name: /research sidekick/i })).toBeInTheDocument();
  expect(screen.getAllByRole("button", { name: /login/i })).toHaveLength(2);
});
