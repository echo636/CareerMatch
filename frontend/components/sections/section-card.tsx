import type { PropsWithChildren, ReactNode } from "react";

type SectionCardProps = PropsWithChildren<{
  title: string;
  description?: string;
  accent?: ReactNode;
}>;

export function SectionCard({ title, description, accent, children }: SectionCardProps) {
  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        {accent ? <div className="panel-accent">{accent}</div> : null}
      </div>
      {children}
    </section>
  );
}
