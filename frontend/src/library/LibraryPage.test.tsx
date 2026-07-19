import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LibraryPage } from "./LibraryPage";

function response(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    redirected: false,
    headers: new Headers(),
    text: async () => payload === undefined ? "" : JSON.stringify(payload),
    json: async () => payload,
  };
}

function rowFor(name: string) {
  return screen
    .getAllByText(name)
    .map((node) => node.closest("tr"))
    .find((row): row is HTMLTableRowElement => row !== null)!;
}

function hasTableRow(name: string) {
  return screen
    .queryAllByText(name)
    .some((node) => node.closest("tr") !== null);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.history.replaceState({}, "", "/ui/projects");
});

describe("LibraryPage", () => {
  it("keeps the active tab in the URL and covers loading and empty states", async () => {
    let resolveProjects!: (value: unknown) => void;
    const projectsRequest = new Promise((resolve) => {
      resolveProjects = resolve;
    });
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(projectsRequest)
      .mockResolvedValueOnce(
        response({
          items: [],
          can_edit: true,
          suggested_color: "#123abc",
          default_color: "#e2e8f0",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <LibraryPage
        endpoint="/api/ui/library"
        initialTab="projects"
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("Loading projects");
    resolveProjects(
      response({
        items: [],
        can_edit: true,
        default_color: "#94a3b8",
      }),
    );
    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("tab", { name: "Tags" }));
    expect(window.location.search).toBe("?tab=tags");
    expect(await screen.findByText("No tags yet.")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/ui/library/tags",
      expect.objectContaining({ credentials: "same-origin" }),
    );
  });

  it("shows a retryable load error", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(
        response({
          items: [],
          can_edit: false,
          default_color: "#94a3b8",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <LibraryPage endpoint="/api/ui/library" initialTab="projects" />,
    );

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Projects could not be loaded. Please try again.",
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No projects yet.")).toBeInTheDocument();
  });

  it("preserves drawer focus, Escape close, and unsaved-change confirmation", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        response({
          items: [],
          can_edit: true,
          default_color: "#94a3b8",
        }),
      ),
    );
    const confirmMock = vi
      .spyOn(window, "confirm")
      .mockReturnValueOnce(false)
      .mockReturnValueOnce(true);

    render(<LibraryPage endpoint="/api/ui/library" initialTab="projects" />);
    await screen.findByText("No projects yet.");
    fireEvent.click(screen.getByRole("button", { name: "New Project" }));

    const dialog = screen.getByRole("dialog", { name: "Create Project" });
    const nameInput = within(dialog).getByRole("textbox", { name: "Name" });
    await waitFor(() => expect(nameInput).toHaveFocus());
    fireEvent.change(nameInput, { target: { value: "Draft" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(confirmMock).toHaveBeenCalledWith("Discard changes?");
    expect(dialog).toHaveClass("is-open");

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(dialog).not.toHaveClass("is-open"));
  });

  it("runs project create, edit, and delete without a page reload", async () => {
    const core = {
      id: 1,
      name: "Core",
      description: "Primary",
      color: "#94a3b8",
      usage_count: 2,
    };
    const edge = {
      id: 2,
      name: "Edge",
      description: null,
      color: "#22c55e",
      usage_count: 0,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({ items: [core], can_edit: true, default_color: "#94a3b8" }),
      )
      .mockResolvedValueOnce(response(edge, 201))
      .mockResolvedValueOnce(
        response({
          items: [core, edge],
          can_edit: true,
          default_color: "#94a3b8",
        }),
      )
      .mockResolvedValueOnce(response({ ...core, name: "Platform" }))
      .mockResolvedValueOnce(
        response({
          items: [{ ...core, name: "Platform" }, edge],
          can_edit: true,
          default_color: "#94a3b8",
        }),
      )
      .mockResolvedValueOnce(response(undefined, 204))
      .mockResolvedValueOnce(
        response({
          items: [{ ...core, name: "Platform" }],
          can_edit: true,
          default_color: "#94a3b8",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<LibraryPage endpoint="/api/ui/library" initialTab="projects" />);
    await screen.findByText("Core");

    fireEvent.click(screen.getByRole("button", { name: "New Project" }));
    let dialog = screen.getByRole("dialog", { name: "Create Project" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), {
      target: { value: "Edge" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create project" }));
    expect(await screen.findByText("Project created.")).toBeInTheDocument();
    await screen.findByText("Edge");

    fireEvent.click(within(rowFor("Core")).getByRole("button", { name: "Edit" }));
    dialog = screen.getByRole("dialog", { name: "Edit Project" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), {
      target: { value: "Platform" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(await screen.findByText("Platform")).toBeInTheDocument();

    fireEvent.click(
      within(rowFor("Edge")).getByRole("button", {
        name: "More actions for Edge",
      }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete Edge" }));
    dialog = screen.getByRole("dialog", { name: "Delete Project" });
    fireEvent.click(
      within(dialog).getByRole("checkbox", {
        name: "I understand this cannot be undone",
      }),
    );
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "Edge" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Delete permanently" }),
    );
    await waitFor(() => expect(hasTableRow("Edge")).toBe(false));
    expect(fetchMock).toHaveBeenCalledTimes(7);
  });

  it("runs vendor create, edit, and delete", async () => {
    window.history.replaceState({}, "", "/ui/projects?tab=vendors");
    const cisco = { id: 1, name: "Cisco", usage_count: 3 };
    const juniper = { id: 2, name: "Juniper", usage_count: 0 };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ items: [cisco], can_edit: true }))
      .mockResolvedValueOnce(response(juniper, 201))
      .mockResolvedValueOnce(
        response({ items: [cisco, juniper], can_edit: true }),
      )
      .mockResolvedValueOnce(response({ ...cisco, name: "Cisco Systems" }))
      .mockResolvedValueOnce(
        response({
          items: [{ ...cisco, name: "Cisco Systems" }, juniper],
          can_edit: true,
        }),
      )
      .mockResolvedValueOnce(response(undefined, 204))
      .mockResolvedValueOnce(
        response({ items: [{ ...cisco, name: "Cisco Systems" }], can_edit: true }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<LibraryPage endpoint="/api/ui/library" initialTab="vendors" />);
    await screen.findByText("Cisco");

    fireEvent.click(screen.getByRole("button", { name: "New Vendor" }));
    let dialog = screen.getByRole("dialog", { name: "Create Vendor" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), {
      target: { value: "Juniper" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create vendor" }));
    await screen.findByText("Juniper");

    fireEvent.click(within(rowFor("Cisco")).getByRole("button", { name: "Edit" }));
    dialog = screen.getByRole("dialog", { name: "Edit Vendor" });
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), {
      target: { value: "Cisco Systems" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await screen.findByText("Cisco Systems");

    fireEvent.click(
      within(rowFor("Juniper")).getByRole("button", {
        name: "More actions for Juniper",
      }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete Juniper" }));
    dialog = screen.getByRole("dialog", { name: "Delete Vendor" });
    fireEvent.click(within(dialog).getByRole("checkbox"));
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "Juniper" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Delete permanently" }),
    );
    await waitFor(() => expect(hasTableRow("Juniper")).toBe(false));
  });

  it("runs tag create, normalized edit validation, and delete", async () => {
    window.history.replaceState({}, "", "/ui/projects?tab=tags");
    const prod = {
      id: 1,
      name: "prod",
      color: "#22c55e",
      usage_count: 4,
    };
    const edge = {
      id: 2,
      name: "edge",
      color: "#123abc",
      usage_count: 0,
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        response({
          items: [prod],
          can_edit: true,
          suggested_color: "#123abc",
          default_color: "#e2e8f0",
        }),
      )
      .mockResolvedValueOnce(response(edge, 201))
      .mockResolvedValueOnce(
        response({
          items: [prod, edge],
          can_edit: true,
          suggested_color: "#abcdef",
          default_color: "#e2e8f0",
        }),
      )
      .mockResolvedValueOnce(
        response(
          {
            detail:
              "Tag name may include letters, digits, dash, and underscore only.",
          },
          422,
        ),
      )
      .mockResolvedValueOnce(response({ ...prod, name: "production" }))
      .mockResolvedValueOnce(
        response({
          items: [{ ...prod, name: "production" }, edge],
          can_edit: true,
          suggested_color: "#abcdef",
          default_color: "#e2e8f0",
        }),
      )
      .mockResolvedValueOnce(response(undefined, 204))
      .mockResolvedValueOnce(
        response({
          items: [{ ...prod, name: "production" }],
          can_edit: true,
          suggested_color: "#abcdef",
          default_color: "#e2e8f0",
        }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<LibraryPage endpoint="/api/ui/library" initialTab="tags" />);
    await screen.findAllByText("prod");

    fireEvent.click(screen.getByRole("button", { name: "New Tag" }));
    let dialog = screen.getByRole("dialog", { name: "Create Tag" });
    expect(within(dialog).getByLabelText("Color")).toHaveValue("#123abc");
    fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), {
      target: { value: "edge" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Create tag" }));
    await screen.findAllByText("edge");
    expect(
      screen.queryByRole("dialog", { name: "Create Tag" }),
    ).not.toBeInTheDocument();

    fireEvent.click(within(rowFor("prod")).getByRole("button", { name: "Edit" }));
    dialog = screen.getByRole("dialog", { name: "Edit Tag" });
    const nameInput = within(dialog).getByRole("textbox", { name: "Name" });
    fireEvent.change(nameInput, { target: { value: "bad name" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent(
      "Tag name may include letters",
    );
    fireEvent.change(nameInput, { target: { value: "production" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Save changes" }));
    await screen.findAllByText("production");

    fireEvent.click(
      within(rowFor("edge")).getByRole("button", {
        name: "More actions for edge",
      }),
    );
    fireEvent.click(screen.getByRole("menuitem", { name: "Delete edge" }));
    dialog = screen.getByRole("dialog", { name: "Delete Tag" });
    fireEvent.click(within(dialog).getByRole("checkbox"));
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "edge" },
    });
    fireEvent.click(
      within(dialog).getByRole("button", { name: "Delete permanently" }),
    );
    await waitFor(() => expect(hasTableRow("edge")).toBe(false));
  });
});
