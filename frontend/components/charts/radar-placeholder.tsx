import type { CSSProperties } from "react";

type RadarPlaceholderProps = {
  values: {
    skills: number;
    experience: number;
    salary: number;
    growth: number;
  };
};

export function RadarPlaceholder({ values }: RadarPlaceholderProps) {
  const average =
    (values.skills + values.experience + values.salary + values.growth) / 4;

  return (
    <div className="radar-card">
      <div
        className="radar-core"
        style={
          {
            "--radar-fill": `${Math.round(average * 100)}%`,
          } as CSSProperties
        }
      />
      <ul className="radar-legend">
        <li>技能覆盖 {Math.round(values.skills * 100)}%</li>
        <li>经验对齐 {Math.round(values.experience * 100)}%</li>
        <li>薪资匹配 {Math.round(values.salary * 100)}%</li>
        <li>成长空间 {Math.round(values.growth * 100)}%</li>
      </ul>
    </div>
  );
}
