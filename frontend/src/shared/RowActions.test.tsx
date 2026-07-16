import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RowActions } from "./RowActions";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("RowActions", () => {
  it("keeps Delete in the overflow menu and marks open controls as visible", () => {
    const onEdit = vi.fn();
    const onDelete = vi.fn();
    render(
      <RowActions
        itemLabel="edge-01"
        onEdit={onEdit}
        actions={[{ label: "Delete", destructive: true, onSelect: onDelete }]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(onEdit).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Edit" })).toHaveClass(
      "row-action-control",
      "row-actions-edit",
    );
    expect(
      screen.getByRole("button", { name: "More actions for edge-01" }),
    ).toHaveClass("row-action-control", "row-actions-trigger");
    expect(
      screen.queryByRole("menuitem", { name: "Delete edge-01" }),
    ).not.toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: "More actions for edge-01" }),
    );
    expect(
      screen.getByRole("button", { name: "Edit" }).closest(".row-actions"),
    ).toHaveClass("is-open");
    const deleteItem = screen.getByRole("menuitem", {
      name: "Delete edge-01",
    });
    expect(deleteItem).toHaveClass("row-action-item-danger");
    fireEvent.click(deleteItem);
    expect(onDelete).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("supports keyboard open, Escape focus return, and disabled actions", () => {
    render(
      <RowActions
        itemLabel="admin"
        onEdit={vi.fn()}
        actions={[
          {
            label: "Delete",
            destructive: true,
            disabled: true,
            disabledReason: "You cannot delete your own account.",
            onSelect: vi.fn(),
          },
        ]}
      />,
    );

    const trigger = screen.getByRole("button", {
      name: "More actions for admin",
    });
    trigger.focus();
    fireEvent.keyDown(trigger, { key: "ArrowDown" });
    const deleteItem = screen.getByRole("menuitem", {
      name: /Delete admin/,
    });
    expect(deleteItem).toHaveFocus();
    expect(deleteItem).toHaveAttribute("aria-disabled", "true");
    fireEvent.keyDown(deleteItem, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
