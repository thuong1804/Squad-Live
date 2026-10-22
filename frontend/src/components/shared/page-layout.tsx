import type { ReactNode } from "react";
import { FolderOpen } from "lucide-react";

interface PageHeaderProps {
  title: string;
  description: string;
  eyebrow?: string;
  action?: ReactNode;
}
export function PageHeader({
  title,
  description,
  eyebrow,
  action,
}: PageHeaderProps): React.JSX.Element {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}
export function EmptyState({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}): React.JSX.Element {
  return (
    <div className="empty-state">
      <span className="empty-icon" aria-hidden="true">
        <FolderOpen size={24} />
      </span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {children}
    </div>
  );
}
