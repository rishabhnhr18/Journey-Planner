"use client";
import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import Topbar from "@/components/Topbar";
import OverviewTab from "@/tabs/OverviewTab";
import InventoryTab from "@/tabs/InventoryTab";
import CustomerTab from "@/tabs/CustomerTab";
import TerritoryTab from "@/tabs/TerritoryTab";
import SalespersonTab from "@/tabs/SalespersonTab";
import {
  ForecastInventoryTab,
  ForecastOrdersTab,
  DeliveryPlanTab,
  RouteOptimizerTab,
  AIAdvancedTab,
  SettingsTab,
} from "@/tabs/AITabs";

const tabMap: Record<string, React.ReactNode> = {};

export default function Home() {
  const [active, setActive] = useState("overview");

  const renderTab = () => {
    switch (active) {
      case "overview": return <OverviewTab />;
      case "inventory": return <InventoryTab />;
      case "customer": return <CustomerTab />;
      case "territory": return <TerritoryTab />;
      case "salesperson": return <SalespersonTab />;
      case "forecast-inventory": return <ForecastInventoryTab />;
      case "forecast-orders": return <ForecastOrdersTab />;
      case "delivery-plan": return <DeliveryPlanTab />;
      case "route-optimizer": return <RouteOptimizerTab />;
      case "ai-advanced": return <AIAdvancedTab />;
      case "settings": return <SettingsTab />;
      default: return <OverviewTab />;
    }
  };

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "var(--bg-base)" }}>
      <Sidebar active={active} onSelect={setActive} />
      <div style={{ marginLeft: 256, flex: 1, display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <Topbar active={active} />
        <main style={{ flex: 1, padding: "28px 28px 40px", maxWidth: 1400 }}>
          {renderTab()}
        </main>
      </div>
    </div>
  );
}
