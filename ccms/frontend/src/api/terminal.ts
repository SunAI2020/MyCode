import apiClient from "./client";

// ── Types ──

export interface ExecuteResponse {
  session_id: string;
  status: string;
}

export interface SessionResponse {
  id: string;
  working_directory: string;
  shell_type: string;
  status: string;
  output_buffer: string | null;
  started_at: string;
  closed_at: string | null;
}

export interface SessionListResponse {
  sessions: SessionResponse[];
  total: number;
}

export interface DirectoryEntry {
  name: string;
  path: string;
  is_directory: boolean;
  size: number | null;
  modified_at: string | null;
}

export interface ListDirectoryResponse {
  current_path: string;
  entries: DirectoryEntry[];
}

export interface DriveInfo {
  name: string;
  path: string;
  mountpoint: string;
  fstype: string;
}

export interface DrivesResponse {
  drives: DriveInfo[];
}

// ── Terminal API ──

export const executeCommand = (
  command: string,
  workingDirectory: string,
) =>
  apiClient.post<ExecuteResponse>("/terminal/sessions", {
    command,
    working_directory: workingDirectory,
  });

export const getSession = (sessionId: string) =>
  apiClient.get<SessionResponse>(`/terminal/sessions/${sessionId}`);

export const listSessions = () =>
  apiClient.get<SessionListResponse>("/terminal/sessions");

export const cancelSession = (sessionId: string) =>
  apiClient.post(`/terminal/sessions/${sessionId}/cancel`);

// ── Filesystem API ──

export const listDirectory = (path?: string) =>
  apiClient.get<ListDirectoryResponse>("/filesystem/list", {
    params: { path: path || "~" },
  });

export const listDrives = () =>
  apiClient.get<DrivesResponse>("/filesystem/drives");
