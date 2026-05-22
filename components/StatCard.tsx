import { ReactNode } from "react";

interface StatCardProps {
  label: string;
  value: string;
  sub?: string;
  icon: ReactNode;
  trend?: string;
  trendUp?: boolean;
  color?: string;
}

export default function StatCard({
  label,
  value,
  sub,
  icon,
  trend,
  trendUp,
  color = "var(--accent)",
}: StatCardProps) {
  return (
    <div
      style={{
        background: "var(--bg-card)",
        borderRadius: 16,
        padding: "18px 20px",
        border: "1.5px solid var(--border)",
        display: "flex",
        flexDirection: "column",
        gap: 10,
        boxShadow: "0 2px 12px rgba(79,127,250,0.05)",
        transition: "box-shadow 0.2s",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow =
          "0 6px 24px rgba(79,127,250,0.13)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.boxShadow =
          "0 2px 12px rgba(79,127,250,0.05)";
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: `${color}18`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color,
          }}
        >
          {icon}
        </div>
        {trend && (
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color: trendUp ? "var(--success)" : "var(--danger)",
              background: trendUp ? "#34C48B18" : "#F0656518",
              padding: "3px 8px",
              borderRadius: 20,
            }}
          >
            {trendUp ? "▲" : "▼"} {trend}
          </span>
        )}
      </div>
      <div>
        <div
          style={{
            fontSize: 24,
            fontWeight: 800,
            color: "var(--text-primary)",
            lineHeight: 1.1,
          }}
        >
          {value}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--text-secondary)", fontWeight: 500, marginTop: 3 }}>
          {label}
        </div>
        {sub && (
          <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 2 }}>{sub}</div>
        )}
      </div>
    </div>
  );
}
