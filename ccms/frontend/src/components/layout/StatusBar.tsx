import { Cpu, HardDrive, Wifi } from "lucide-react";

export default function StatusBar() {
  return (
    <footer className="h-7 bg-surface-200 border-t border-gray-700 flex items-center justify-between px-4 text-xs text-gray-500 shrink-0">
      {/* 左侧状态 */}
      <div className="flex items-center gap-4">
        <span className="flex items-center gap-1">
          <Wifi size={12} className="text-green-500" />
          已连接
        </span>
        <span className="flex items-center gap-1">
          <Cpu size={12} />
          CPU 0%
        </span>
        <span className="flex items-center gap-1">
          <HardDrive size={12} />
          存储 -- GB
        </span>
      </div>

      {/* 右侧状态 */}
      <div className="flex items-center gap-4">
        <span>Agent 在线: 0</span>
        <span>Token: 0</span>
        <span>会话: 0</span>
      </div>
    </footer>
  );
}
