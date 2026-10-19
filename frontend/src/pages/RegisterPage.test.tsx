import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import RegisterPage from "./RegisterPage";

let mockRegister: ReturnType<typeof vi.fn> = vi.fn();

vi.mock("../auth/AuthContext", () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuth: () => ({
    user: null,
    loading: false,
    login: vi.fn(),
    register: (...args: unknown[]) => mockRegister(...args),
    logout: vi.fn(),
    hasRole: vi.fn(),
    canManage: false,
  }),
  __setMockRegister: (fn: ReturnType<typeof vi.fn>) => { mockRegister = fn; },
}));

vi.mock("../api/client");

import { api } from "../api/client";

const mockApi = vi.mocked(api);

const renderWithRouter = (component: React.ReactNode) => {
  return render(<BrowserRouter>{component}</BrowserRouter>);
};

describe("RegisterPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    mockApi.register.mockReset();
    // Configure the AuthContext mock to use api.register
    // RegisterPage calls register(fullName, email, password)
    // @ts-ignore - mock export added in vi.mock
    const { __setMockRegister } = await import("../auth/AuthContext");
    // @ts-ignore - mock function signature differs
    __setMockRegister(async (fullName: string, email: string, password: string) => {
      return mockApi.register({ full_name: fullName, email, password });
    });
  });

  it("renders registration form with all fields", () => {
    renderWithRouter(<RegisterPage />);

    expect(screen.getByText("CREATE ACCOUNT")).toBeInTheDocument();
    expect(screen.getByText("Join your workspace")).toBeInTheDocument();
    expect(screen.getByLabelText("Full Name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByLabelText("Confirm Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /create account/i })).toBeInTheDocument();
  });

  it("shows link to sign in page", () => {
    renderWithRouter(<RegisterPage />);

    const link = screen.getByRole("link", { name: /sign in/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/login");
  });

  it("validates password confirmation mismatch", async () => {
    renderWithRouter(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "different123" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("Passwords do not match")).toBeInTheDocument();
    });
  });

  it("validates minimum password length", async () => {
    renderWithRouter(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "short" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "short" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("Password must be at least 8 characters")).toBeInTheDocument();
    });
  });

  it("calls register API on valid submission and redirects on success", async () => {
    mockApi.register.mockResolvedValue({
      access_token: "test-token",
      user: {
        id: "123",
        full_name: "Jane Doe",
        email: "jane@example.com",
        account_status: "active",
        roles: [{ code: "client", name: "Client" }],
      },
    });

    renderWithRouter(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "password123" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    await waitFor(() => {
      expect(mockApi.register).toHaveBeenCalledWith({
        full_name: "Jane Doe",
        email: "jane@example.com",
        password: "password123",
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Account created successfully. Redirecting to sign in…")).toBeInTheDocument();
    });
  });

  it("displays API error for duplicate email", async () => {
    mockApi.register.mockRejectedValue(new Error("409: Email is already registered"));

    renderWithRouter(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "password123" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    await waitFor(() => {
      expect(screen.getByText("An account with this email already exists")).toBeInTheDocument();
    });
  });

  it("disables submit button during submission", async () => {
    let resolvePromise: (value: { access_token: string; user: { id: string; full_name: string; email: string; account_status: string; roles: Array<{ code: "admin" | "project_manager" | "team_lead" | "developer" | "tester" | "client"; name: string }> } }) => void;
    mockApi.register.mockImplementation(() => new Promise((resolve) => { resolvePromise = resolve; }));

    renderWithRouter(<RegisterPage />);

    fireEvent.change(screen.getByLabelText("Full Name"), { target: { value: "Jane Doe" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "jane@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "password123" } });
    fireEvent.change(screen.getByLabelText("Confirm Password"), { target: { value: "password123" } });

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /create account/i }));
    });

    expect(screen.getByRole("button", { name: /creating account/i })).toBeDisabled();

    resolvePromise!({
      access_token: "test-token",
      user: { id: "123", full_name: "Jane Doe", email: "jane@example.com", account_status: "active", roles: [{ code: "client", name: "Client" }] },
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /create account/i })).not.toBeDisabled();
    });
  });
});