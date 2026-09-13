import { useState, useEffect, useCallback } from "react";
import {
  FolderOpen,
  FolderSearch,
  Pencil,
  Check,
  X,
  ChevronRight,
  HardDrive,
  Loader,
  RefreshCw,
} from "lucide-react";
import {
  listDirectory,
  listDrives,
  type DirectoryEntry,
  type DriveInfo,
} from "../../api/terminal";
import { useTerminalStore } from "../../store/terminalStore";

export default function DirectorySelector() {
  const workingDirectory = useTerminalStore((s) => s.workingDirectory);
  const setWorkingDirectory = useTerminalStore((s) => s.setWorkingDirectory);

  const [showModal, setShowModal] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editValue, setEditValue] = useState(workingDirectory);

  // Modal state
  const [currentPath, setCurrentPath] = useState(workingDirectory);
  const [entries, setEntries] = useState<DirectoryEntry[]>([]);
  const [drives, setDrives] = useState<DriveInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"drives" | "dir">("drives");

  // ── Load drives ──
  const loadDrives = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await listDrives();
      setDrives(res.data.drives);
      setViewMode("drives");
    } catch {
      setError("无法获取磁盘列表");
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Load directory ──
  const loadDirectory = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listDirectory(path);
      setCurrentPath(res.data.current_path);
      setEntries(res.data.entries);
      setViewMode("dir");
    } catch {
      setError("无法访问该目录");
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Open modal ──
  const openModal = () => {
    setShowModal(true);
    setEditValue(workingDirectory);
    loadDrives();
  };

  // ── Navigate into directory ──
  const navigateTo = (path: string) => {
    loadDirectory(path);
  };

  // ── Go up one level ──
  const goUp = () => {
    const parent = currentPath.split("\\").slice(0, -1).join("\\") || currentPath.slice(0, 3);
    loadDirectory(parent);
  };

  // ── Select current directory ──
  const selectPath = (path: string) => {
    setWorkingDirectory(path);
    setShowModal(false);
    setEditMode(false);
  };

  // ── Handle edit confirm ──
  const confirmEdit = () => {
    const trimmed = editValue.trim();
    if (trimmed) {
      setWorkingDirectory(trimmed);
    }
    setEditMode(false);
  };

  const cancelEdit = () => {
    setEditValue(workingDirectory);
    setEditMode(false);
  };

  // ── Drive click ──
  const handleDriveClick = (drive: DriveInfo) => {
    loadDirectory(drive.path);
  };

  // ── Display path (truncated) ──
  const displayPath =
    workingDirectory.length > 50
      ? "..." + workingDirectory.slice(workingDirectory.length - 47)
      : workingDirectory;

  return (
    <>
      {/* ── Bar ── */}
      <div className="h-10 bg-surface-200 border-b border-gray-700 flex items-center px-3 gap-2 shrink-0">
        <FolderOpen size={16} className="text-primary-400 shrink-0" />
        {editMode ? (
          <div className="flex-1 flex items-center gap-1">
            <input
              type="text"
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") confirmEdit();
                if (e.key === "Escape") cancelEdit();
              }}
              className="flex-1 bg-surface-300 border border-gray-600 rounded px-2 py-0.5 text-xs text-white font-mono outline-none focus:border-primary-500"
              autoFocus
            />
            <button
              onClick={confirmEdit}
              className="p-0.5 rounded hover:bg-green-700 text-gray-400 hover:text-white"
            >
              <Check size={14} />
            </button>
            <button
              onClick={cancelEdit}
              className="p-0.5 rounded hover:bg-red-700 text-gray-400 hover:text-white"
            >
              <X size={14} />
            </button>
          </div>
        ) : (
          <>
            <span
              className="flex-1 text-xs text-gray-400 font-mono truncate cursor-pointer hover:text-gray-300"
              onClick={openModal}
              title={workingDirectory}
            >
              {displayPath}
            </span>
            <button
              onClick={() => {
                setEditValue(workingDirectory);
                setEditMode(true);
              }}
              className="p-0.5 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300"
              title="编辑路径"
            >
              <Pencil size={13} />
            </button>
            <button
              onClick={openModal}
              className="p-0.5 rounded hover:bg-gray-700 text-gray-500 hover:text-gray-300 flex items-center gap-0.5"
              title="浏览目录"
            >
              <FolderSearch size={13} />
              <span className="text-[10px] hidden sm:inline">浏览</span>
            </button>
          </>
        )}
      </div>

      {/* ── Modal ── */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-surface-200 border border-gray-600 rounded-lg w-[520px] max-h-[480px] flex flex-col shadow-2xl">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
              <h3 className="text-sm font-semibold text-white">选择工作目录</h3>
              <button
                onClick={() => setShowModal(false)}
                className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
              >
                <X size={16} />
              </button>
            </div>

            {/* Breadcrumb / Drives toggle */}
            <div className="flex items-center gap-1 px-3 py-2 border-b border-gray-700 text-xs">
              <button
                onClick={loadDrives}
                className={`flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-700 transition-colors ${
                  viewMode === "drives" ? "text-primary-400" : "text-gray-400"
                }`}
              >
                <HardDrive size={12} />
                磁盘
              </button>
              {viewMode === "dir" && (
                <>
                  <ChevronRight size={12} className="text-gray-600" />
                  <span className="text-gray-400 font-mono text-[11px] truncate">
                    {currentPath}
                  </span>
                </>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto p-2 min-h-[200px]">
              {loading ? (
                <div className="flex items-center justify-center h-full text-gray-500 gap-2">
                  <Loader size={18} className="animate-spin" />
                  <span className="text-sm">加载中...</span>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-2">
                  <span className="text-sm text-red-400">{error}</span>
                  <button
                    onClick={() =>
                      viewMode === "drives" ? loadDrives() : loadDirectory(currentPath)
                    }
                    className="flex items-center gap-1 text-xs text-primary-400 hover:text-primary-300"
                  >
                    <RefreshCw size={12} />
                    重试
                  </button>
                </div>
              ) : viewMode === "drives" ? (
                /* ── Drive list ── */
                drives.length === 0 ? (
                  <div className="text-center text-gray-500 text-sm py-8">无可用磁盘</div>
                ) : (
                  drives.map((d) => (
                    <button
                      key={d.name}
                      onClick={() => handleDriveClick(d)}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded hover:bg-gray-700 transition-colors text-left"
                    >
                      <HardDrive size={18} className="text-primary-400 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm text-white truncate">{d.name}</div>
                        <div className="text-[10px] text-gray-500">{d.fstype}</div>
                      </div>
                      <ChevronRight size={14} className="text-gray-600 shrink-0" />
                    </button>
                  ))
                )
              ) : (
                /* ── Directory list ── */
                <>
                  {/* Up */}
                  <button
                    onClick={goUp}
                    className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-700 transition-colors text-left mb-1"
                  >
                    <FolderOpen size={18} className="text-yellow-500 shrink-0" />
                    <span className="text-sm text-gray-300">..</span>
                  </button>

                  {entries.length === 0 && (
                    <div className="text-center text-gray-500 text-sm py-8">空目录</div>
                  )}

                  {entries
                    .filter((e) => e.is_directory)
                    .map((e) => (
                      <button
                        key={e.path}
                        onClick={() => navigateTo(e.path)}
                        className="w-full flex items-center gap-3 px-3 py-2 rounded hover:bg-gray-700 transition-colors text-left"
                      >
                        <FolderOpen size={18} className="text-primary-400 shrink-0" />
                        <span className="text-sm text-white truncate">{e.name}</span>
                      </button>
                    ))}
                </>
              )}
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-700">
              <span className="text-[10px] text-gray-500 font-mono truncate max-w-[300px]">
                {viewMode === "dir" ? currentPath : "选择磁盘"}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowModal(false)}
                  className="px-4 py-1.5 rounded text-xs text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                >
                  取消
                </button>
                {viewMode === "dir" && (
                  <button
                    onClick={() => selectPath(currentPath)}
                    className="px-4 py-1.5 rounded text-xs bg-primary-600 text-white hover:bg-primary-500 transition-colors"
                  >
                    选择此目录
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
