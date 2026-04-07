"use client";

interface AudioVisualizerProps {
  levels: number[];
  isActive: boolean;
}

export function AudioVisualizer({ levels, isActive }: AudioVisualizerProps) {
  if (!isActive || levels.length === 0) return null;

  return (
    <div className="flex items-center gap-[2px] h-6">
      {levels.map((level, i) => (
        <div
          key={i}
          className="w-[3px] rounded-full bg-red-400 transition-all duration-75"
          style={{ height: `${4 + level * 20}px` }}
        />
      ))}
    </div>
  );
}
