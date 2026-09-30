import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ExportDropdown } from "./ExportDropdown";

afterEach(() => {
  cleanup();
});

describe("ExportDropdown", () => {
  it("renders trigger button and toggles dropdown menu", () => {
    const onExportStarted = vi.fn();
    render(
      <ExportDropdown
        csvUrl="/export/ip-assets.csv?type=VM"
        jsonUrl="/export/ip-assets.json?type=VM"
        totalCount={42}
        onExportStarted={onExportStarted}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Export options" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    // Open menu
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("menu")).toBeVisible();
    expect(screen.getByText("42 assets")).toBeVisible();

    const csvItem = screen.getByRole("menuitem", { name: "Export as CSV" });
    expect(csvItem).toHaveAttribute("href", "/export/ip-assets.csv?type=VM");
    expect(csvItem).toHaveAttribute("download", "ip-assets.csv");

    const jsonItem = screen.getByRole("menuitem", { name: "Export as JSON" });
    expect(jsonItem).toHaveAttribute("href", "/export/ip-assets.json?type=VM");
    expect(jsonItem).toHaveAttribute("download", "ip-assets.json");

    // Click item triggers callback and closes menu
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    fireEvent.click(csvItem);
    consoleError.mockRestore();

    expect(onExportStarted).toHaveBeenCalledOnce();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("closes on Escape key and outside click", () => {
    render(
      <div>
        <div data-testid="outside">Outside area</div>
        <ExportDropdown
          csvUrl="/export/ip-assets.csv"
          jsonUrl="/export/ip-assets.json"
        />
      </div>,
    );

    const trigger = screen.getByRole("button", { name: "Export options" });
    fireEvent.click(trigger);
    expect(screen.getByRole("menu")).toBeVisible();

    // Escape closes menu
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();

    // Open and click outside closes menu
    fireEvent.click(trigger);
    expect(screen.getByRole("menu")).toBeVisible();

    fireEvent.pointerDown(screen.getByTestId("outside"));
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});
