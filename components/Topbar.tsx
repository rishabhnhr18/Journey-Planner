"use client";
import { Search, Bell, ChevronDown } from "lucide-react";

const tabTitles: Record<string, { title: string; desc: string }> = {
  overview: { title: "Dashboard Overview", desc: "Business visibility at a glance" },
  inventory: { title: "Know Your Inventory", desc: "10 metrics — stock health & demand" },
  customer: { title: "Know Your Customer", desc: "6 metrics — value, loyalty & risk" },
  territory: { title: "Know Your Territory", desc: "10 metrics — geography & delivery performance" },
  salesperson: { title: "Know Your Salesperson", desc: "9 metrics — productivity & efficiency" },
  "forecast-inventory": { title: "Inventory Forecast", desc: "30–90 day stock requirement predictions" },
  "forecast-orders": { title: "Order Forecast", desc: "Future demand by territory & customer" },
  "delivery-plan": { title: "Monthly Delivery Plan", desc: "Customer visit scheduling & prioritization" },
  "route-optimizer": { title: "Daily Route Optimizer", desc: "Warehouse-anchored delivery routing" },
  "ai-advanced": { title: "Advanced AI Features", desc: "Territory design & smart routing" },
  settings: { title: "Settings", desc: "System configuration" },
};

export default function Topbar({ active }: { active: string }) {
  const info = tabTitles[active] ?? { title: "Dashboard", desc: "" };
  return (
    <header
      style={{
        height: 64,
        background: "var(--bg-card)",
        borderBottom: "1.5px solid var(--border)",
        display: "flex",
        alignItems: "center",
        padding: "0 28px",
        gap: 20,
        position: "sticky",
        top: 0,
        zIndex: 50,
      }}
    >
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 16, fontWeight: 800, color: "var(--text-primary)" }}>
          {info.title}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--text-muted)" }}>{info.desc}</div>
      </div>

      {/* Search */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          background: "var(--bg-base)",
          border: "1.5px solid var(--border)",
          borderRadius: 10,
          padding: "7px 14px",
          width: 220,
        }}
      >
        <Search size={14} color="var(--text-muted)" />
        <input
          placeholder="Search metrics..."
          style={{
            border: "none",
            background: "transparent",
            outline: "none",
            fontSize: 13,
            color: "var(--text-primary)",
            fontFamily: "inherit",
            width: "100%",
          }}
        />
      </div>

      {/* Date badge */}
      <div
        style={{
          background: "var(--accent-light)",
          color: "var(--accent)",
          fontWeight: 700,
          fontSize: 12,
          padding: "6px 14px",
          borderRadius: 20,
        }}
      >
        May 2026
      </div>

      {/* Bell */}
      <div
        style={{
          width: 36,
          height: 36,
          borderRadius: 10,
          background: "var(--bg-base)",
          border: "1.5px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          position: "relative",
        }}
      >
        <Bell size={16} color="var(--text-secondary)" />
        <span
          style={{
            position: "absolute",
            top: 6,
            right: 7,
            width: 7,
            height: 7,
            background: "var(--danger)",
            borderRadius: "50%",
            border: "1.5px solid white",
          }}
        />
      </div>
    </header>
  );
}
