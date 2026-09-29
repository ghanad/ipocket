import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { HostSelector } from "./HostSelector";
import type { HostOption } from "./types";

const mockHosts: HostOption[] = [
  { id: 1, name: "server-alpha" },
  { id: 2, name: "server-beta" },
  { id: 3, name: "worker-01" },
];

function ControlledHostSelector({
  hosts = mockHosts,
  initialValue = "",
  onChange,
}: {
  hosts?: HostOption[];
  initialValue?: string;
  onChange?: (value: string) => void;
}) {
  const [val, setVal] = useState(initialValue);
  return (
    <HostSelector
      hosts={hosts}
      value={val}
      onChange={(next) => {
        setVal(next);
        onChange?.(next);
      }}
    />
  );
}

afterEach(() => {
  cleanup();
});

describe("HostSelector", () => {
  it("renders with placeholder when unassigned", () => {
    render(<HostSelector hosts={mockHosts} value="" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    expect(input).toHaveValue("");
    expect(input).toHaveAttribute("placeholder", "Search and select host");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("renders with selected host name when value is provided", () => {
    render(<HostSelector hosts={mockHosts} value="2" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    expect(input).toHaveValue("server-beta");
  });

  it("opens dropdown on focus and shows Unassigned plus all hosts", () => {
    render(<HostSelector hosts={mockHosts} value="2" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.focus(input);

    expect(screen.getByRole("listbox")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Unassigned" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "server-alpha" })).toBeInTheDocument();
    const selectedOption = screen.getByRole("option", { name: "server-beta" });
    expect(selectedOption).toBeInTheDocument();
    expect(selectedOption).toHaveAttribute("aria-selected", "true");
    expect(selectedOption.className).toContain("is-selected");
  });

  it("filters options when typing a query and displays empty message if no matches", () => {
    render(<HostSelector hosts={mockHosts} value="" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.change(input, { target: { value: "worker" } });

    expect(screen.getByRole("option", { name: "worker-01" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "server-alpha" })).not.toBeInTheDocument();

    fireEvent.change(input, { target: { value: "nonexistent" } });
    expect(screen.getByText("No matching hosts.")).toBeInTheDocument();
  });

  it("selects a host on option click, calls onChange and closes dropdown", () => {
    const onChange = vi.fn();
    render(<ControlledHostSelector initialValue="" onChange={onChange} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.focus(input);
    fireEvent.click(screen.getByRole("option", { name: "worker-01" }));

    expect(onChange).toHaveBeenCalledWith("3");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input).toHaveValue("worker-01");
  });

  it("selects Unassigned to clear the host", () => {
    const onChange = vi.fn();
    render(<ControlledHostSelector initialValue="1" onChange={onChange} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.focus(input);
    fireEvent.click(screen.getByRole("option", { name: "Unassigned" }));

    expect(onChange).toHaveBeenCalledWith("");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input).toHaveValue("");
  });

  it("handles Enter to select the first visible matching option", () => {
    const onChange = vi.fn();
    render(<ControlledHostSelector initialValue="" onChange={onChange} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.change(input, { target: { value: "beta" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith("2");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input).toHaveValue("server-beta");
  });

  it("handles Escape to close dropdown and reverts input to selected host", () => {
    render(<HostSelector hosts={mockHosts} value="1" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "some search" } });
    fireEvent.keyDown(input, { key: "Escape" });

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input).toHaveValue("server-alpha");
  });

  it("closes dropdown on blur and restores selected host name", () => {
    render(<HostSelector hosts={mockHosts} value="2" onChange={vi.fn()} />);

    const input = screen.getByRole("combobox", { name: "Search hosts" });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "temp" } });
    fireEvent.blur(input);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    expect(input).toHaveValue("server-beta");
  });
});
