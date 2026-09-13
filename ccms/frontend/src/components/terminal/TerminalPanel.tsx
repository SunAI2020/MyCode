import DirectorySelector from "./DirectorySelector";
import OutputDisplay from "./OutputDisplay";
import CommandInput from "./CommandInput";

export default function TerminalPanel() {
  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* 目录选择器 */}
      <DirectorySelector />

      {/* 输出历史 */}
      <OutputDisplay />

      {/* 命令输入 */}
      <CommandInput />
    </div>
  );
}
