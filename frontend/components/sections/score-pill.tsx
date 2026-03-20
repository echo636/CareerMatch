type ScorePillProps = {
  label: string;
  value: number;
};

export function ScorePill({ label, value }: ScorePillProps) {
  const percentage = Math.round(value * 100);

  return (
    <div className="score-pill">
      <span>{label}</span>
      <strong>{percentage}%</strong>
    </div>
  );
}
