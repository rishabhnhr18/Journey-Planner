"use client";
import Image from "next/image";
import {
  LayoutDashboard,
  Package,
  Users,
  Map,
  UserCheck,
  BarChart3,
  CalendarDays,
  Route,
  Brain,
  Settings,
  Bell,
  ChevronRight,
  User,            // ← ADDED for Profile icon
} from "lucide-react";

const navItems = [
  {
    group: "Overview",
    items: [{ id: "overview", label: "Dashboard", icon: LayoutDashboard }],
  },
  {
    group: "Metrics",
    items: [
      { id: "inventory", label: "Know Your Inventory", icon: Package },
      { id: "customer", label: "Know Your Customer", icon: Users },
      { id: "territory", label: "Know Your Territory", icon: Map },
      { id: "salesperson", label: "Know Your Salesperson", icon: UserCheck },
    ],
  },
  {
    group: "AI Planning",
    items: [
      { id: "forecast-inventory", label: "Inventory Forecast", icon: BarChart3 },
      { id: "forecast-orders", label: "Order Forecast", icon: BarChart3 },
      { id: "delivery-plan", label: "Monthly Delivery Plan", icon: CalendarDays },
      { id: "route-optimizer", label: "Daily Route Optimizer", icon: Route },
      { id: "ai-advanced", label: "Advanced AI Features", icon: Brain },
    ],
  },
  {
    group: "System",
    items: [
      { id: "profile", label: "Profile", icon: User },   // ← Profile item
      { id: "settings", label: "Settings", icon: Settings },
    ],
  },
];

interface SidebarProps {
  active: string;
  onSelect: (id: string) => void;
}

export default function Sidebar({ active, onSelect }: SidebarProps) {
  return (
    <aside
      style={{
        width: 256,
        minHeight: "100vh",
        background: "var(--bg-sidebar)",
        borderRight: "1.5px solid var(--sidebar-border)",
        display: "flex",
        flexDirection: "column",
        padding: "0",
        boxShadow: "2px 0 16px rgba(79,127,250,0.04)",
        position: "fixed",
        top: 0,
        left: 0,
        zIndex: 100,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: "20px 24px 18px",
          borderBottom: "1.5px solid var(--sidebar-border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
        }}
      >
        <Image src="/logo.svg" alt="DelivIQ Logo" width={140} height={40} priority />
      </div>

      {/* Nav */}
      <nav style={{ flex: 1, padding: "16px 12px", overflowY: "auto" }}>
        {navItems.map((group) => (
          <div key={group.group} style={{ marginBottom: 8 }}>
            <div
              style={{
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "1.2px",
                textTransform: "uppercase",
                color: "var(--text-muted)",
                padding: "6px 12px 4px",
              }}
            >
              {group.group}
            </div>
            {group.items.map((item) => {
              const Icon = item.icon;
              const isActive = active === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => onSelect(item.id)}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "9px 12px",
                    borderRadius: 10,
                    border: "none",
                    cursor: "pointer",
                    background: isActive ? "var(--accent-light)" : "transparent",
                    color: isActive ? "var(--accent)" : "var(--text-secondary)",
                    fontWeight: isActive ? 700 : 500,
                    fontSize: 13.5,
                    fontFamily: "inherit",
                    transition: "all 0.15s",
                    marginBottom: 2,
                    textAlign: "left",
                    position: "relative",
                  }}
                >
                  <Icon size={17} strokeWidth={isActive ? 2.2 : 1.8} />
                  <span style={{ flex: 1 }}>{item.label}</span>
                  {isActive && <ChevronRight size={14} style={{ opacity: 0.5 }} />}
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Bottom user card - NOW CLICKABLE */}
      <button
        onClick={() => onSelect("profile")}
        style={{
          width: "100%",
          padding: "16px",
          borderTop: "1.5px solid var(--sidebar-border)",
          display: "flex",
          alignItems: "center",
          gap: 10,
          background: "transparent",
          border: "none",
          cursor: "pointer",
          textAlign: "left",
          transition: "background 0.15s",
        }}
        onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-light)")}
        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: "var(--accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "white",
            fontWeight: 700,
            fontSize: 14,
          }}
        >
          RL
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "var(--text-primary)" }}>
            Raj Logistics
          </div>
          <div style={{ fontSize: 11, color: "var(--text-muted)" }}>Admin</div>
        </div>
        <Bell size={16} color="var(--text-muted)" />
      </button>
    </aside>
  );
}