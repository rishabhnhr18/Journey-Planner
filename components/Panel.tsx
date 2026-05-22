import { ReactNode } from "react";

interface PanelProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  action?: ReactNode;
  fullWidth?: boolean;
}

export default function Panel({ title, subtitle, children, action, fullWidth }: PanelProps) {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderRadius: 18,
        border: "1.5px solid var(--border)",
        boxShadow: "0 2px 12px rgba(79,127,250,0.05)",
        padding: "22px 24px",
        gridColumn: fullWidth ? "1 / -1" : undefined,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: 18,
        }}
      >
        <div>
          <h3
            style={{
              fontSize: 15,
              fontWeight: 700,
              color: "var(--text-primary)",
              marginBottom: subtitle ? 3 : 0,
            }}
          >
            {title}
          </h3>
          {subtitle && (
            <p style={{ fontSize: 12, color: "var(--text-muted)" }}>{subtitle}</p>
          )}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
