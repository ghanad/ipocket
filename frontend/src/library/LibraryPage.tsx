import { useCallback, useEffect, useState } from "react";

import { ProjectsTab } from "./ProjectsTab";
import { TagsTab } from "./TagsTab";
import type { LibraryBootstrap, LibraryTab } from "./types";
import { VendorsTab } from "./VendorsTab";

const tabLabels: Record<LibraryTab, string> = {
  projects: "Project",
  vendors: "Vendor",
  tags: "Tag",
};

function tabFromLocation(fallback: LibraryTab): LibraryTab {
  const tab = new URLSearchParams(window.location.search).get("tab");
  return tab === "vendors" || tab === "tags" || tab === "projects"
    ? tab
    : fallback;
}

export function LibraryPage({
  endpoint,
  initialTab,
  initialEditId,
  initialDeleteId,
  bootstrap,
}: {
  endpoint: string;
  initialTab: LibraryTab;
  initialEditId?: number;
  initialDeleteId?: number;
  bootstrap?: LibraryBootstrap | null;
}) {
  const [activeTab, setActiveTab] = useState<LibraryTab>(() =>
    tabFromLocation(initialTab),
  );
  const [canEdit, setCanEdit] = useState(false);
  const [editId, setEditId] = useState(initialEditId);
  const [deleteId, setDeleteId] = useState(initialDeleteId);
  const [createRequests, setCreateRequests] = useState<
    Record<LibraryTab, number>
  >({ projects: 0, vendors: 0, tags: 0 });

  const clearQuery = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", activeTab);
    url.searchParams.delete("edit");
    url.searchParams.delete("delete");
    window.history.replaceState({}, "", `${url.pathname}${url.search}`);
    setEditId(undefined);
    setDeleteId(undefined);
  }, [activeTab]);

  const selectTab = useCallback((tab: LibraryTab, push = true) => {
    const url = new URL(window.location.href);
    url.searchParams.set("tab", tab);
    url.searchParams.delete("edit");
    url.searchParams.delete("delete");
    if (push) {
      window.history.pushState({}, "", `${url.pathname}${url.search}`);
    }
    setActiveTab(tab);
    setCanEdit(false);
    setEditId(undefined);
    setDeleteId(undefined);
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      const nextTab = tabFromLocation("projects");
      const params = new URLSearchParams(window.location.search);
      setActiveTab(nextTab);
      setCanEdit(false);
      setEditId(parseOptionalId(params.get("edit")));
      setDeleteId(parseOptionalId(params.get("delete")));
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const commonProps = {
    endpoint,
    initialEditId: editId,
    initialDeleteId: deleteId,
    onPermissionChange: setCanEdit,
    onClearQuery: clearQuery,
    bootstrap: bootstrap?.tab === activeTab ? bootstrap : null,
  };

  return (
    <>
      <section className="page-header">
        <div>
          <p className="eyebrow">Library</p>
          <h1>Catalog Settings</h1>
          <p className="subtitle">
            Manage Projects, Tags, and Vendors from a single page.
          </p>
        </div>
        <div className="page-header-actions">
          {canEdit && (
            <button
              className="btn btn-primary"
              type="button"
              onClick={() =>
                setCreateRequests((current) => ({
                  ...current,
                  [activeTab]: current[activeTab] + 1,
                }))
              }
            >
              New {tabLabels[activeTab]}
            </button>
          )}
        </div>
      </section>

      <div
        className="tabs library-tabs"
        role="tablist"
        aria-label="Catalog sections"
      >
        <TabLink
          tab="projects"
          activeTab={activeTab}
          onSelect={selectTab}
        />
        <TabLink tab="tags" activeTab={activeTab} onSelect={selectTab} />
        <TabLink tab="vendors" activeTab={activeTab} onSelect={selectTab} />
      </div>

      {activeTab === "projects" ? (
        <ProjectsTab
          {...commonProps}
          createRequest={createRequests.projects}
        />
      ) : activeTab === "vendors" ? (
        <VendorsTab
          {...commonProps}
          createRequest={createRequests.vendors}
        />
      ) : (
        <TagsTab {...commonProps} createRequest={createRequests.tags} />
      )}
    </>
  );
}

function TabLink({
  tab,
  activeTab,
  onSelect,
}: {
  tab: LibraryTab;
  activeTab: LibraryTab;
  onSelect: (tab: LibraryTab) => void;
}) {
  const label = `${tab[0].toUpperCase()}${tab.slice(1)}`;
  return (
    <a
      className={`tab${activeTab === tab ? " tab-active" : ""}`}
      href={`/ui/projects?tab=${tab}`}
      role="tab"
      aria-selected={activeTab === tab}
      onClick={(event) => {
        event.preventDefault();
        onSelect(tab);
      }}
    >
      {label}
    </a>
  );
}

function parseOptionalId(value: string | null): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}
