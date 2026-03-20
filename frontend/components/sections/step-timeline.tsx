type StepTimelineProps = {
  title: string;
  steps: string[];
};

export function StepTimeline({ title, steps }: StepTimelineProps) {
  return (
    <div className="timeline">
      <div className="timeline-label">{title}</div>
      <ol className="timeline-list">
        {steps.map((step, index) => (
          <li key={step} className="timeline-item">
            <span className="timeline-index">{index + 1}</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
