"use client";
import Panel from "@/components/Panel";
import StatCard from "@/components/StatCard";
import { BarChart3, CalendarDays, Route, Brain, Zap, AlertTriangle, CheckCircle, Clock } from "lucide-react";
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, LineChart, Line } from "recharts";

const forecastData = [
  { month: "Jun", projected: 3200, actual: null },
  { month: "Jul", projected: 3600, actual: null },
  { month: "Aug", projected: 3900, actual: null },
  { month: "Sep", projected: 3750, actual: null },
];

const orderForecastData = [
  { week: "W1 Jun", north: 82, south: 68, east: 94, west: 57 },
  { week: "W2 Jun", north: 88, south: 74, east: 101, west: 62 },
  { week: "W3 Jun", north: 76, south: 71, east: 89, west: 59 },
  { week: "W4 Jun", north: 91, south: 78, east: 108, west: 65 },
];

const monthlyPlan = [
  { segment: "Champion (RFM: 5-5-5)", customers: 142, frequency: "Weekly", priority: "Critical" },
  { segment: "Loyal (RFM: 4-4-4)", customers: 318, frequency: "Bi-weekly", priority: "High" },
  { segment: "At-Risk (RFM: 3-2-3)", customers: 201, frequency: "Weekly", priority: "Urgent" },
  { segment: "Promising (RFM: 4-3-3)", customers: 284, frequency: "Monthly", priority: "Normal" },
  { segment: "Lost (RFM: 1-1-1)", customers: 87, frequency: "Re-engage", priority: "Low" },
];

const routeData = [
  { driver: "Arjun", stops: 12, distance: 84, eta: "5:30 PM", load: 92 },
  { driver: "Priya", stops: 10, distance: 71, eta: "4:45 PM", load: 87 },
  { driver: "Ravi", stops: 14, distance: 103, eta: "6:15 PM", load: 96 },
  { driver: "Sunita", stops: 11, distance: 78, eta: "5:10 PM", load: 88 },
];

export function ForecastInventoryTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Forecast Horizon" value="90 Days" sub="SKU-level demand modeling" icon={<BarChart3 size={20} />} color="var(--accent)" />
        <StatCard label="Reorder Actions" value="21 SKUs" sub="Flagged for replenishment" icon={<AlertTriangle size={20} />} color="var(--warning)" />
        <StatCard label="Overstock Risk" value="14 SKUs" sub="Exceeds 90-day projection" icon={<BarChart3 size={20} />} color="var(--info)" />
        <StatCard label="Forecast Accuracy" value="91.4%" sub="vs. actual last quarter" icon={<CheckCircle size={20} />} color="var(--success)" />
      </div>
      <Panel title="3-Month Inventory Demand Forecast" subtitle="Projected SKU demand using trend & seasonality" fullWidth>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={forecastData}>
            <defs>
              <linearGradient id="proj" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#7CB9E8" stopOpacity={0.22} />
                <stop offset="95%" stopColor="#7CB9E8" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
            <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} />
            <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
            <Area type="monotone" dataKey="projected" stroke="#7CB9E8" strokeWidth={2.5} fill="url(#proj)" strokeDasharray="6 3" name="Projected Units" />
          </AreaChart>
        </ResponsiveContainer>
      </Panel>
      <Panel title="Methods Used" subtitle="AI forecasting engine" fullWidth>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
          {[
            { method: "Time-Series Forecasting", desc: "ARIMA/ETS models on historical consumption data" },
            { method: "Per-SKU Demand Modeling", desc: "Individual product-level trend isolation" },
            { method: "Reorder Point Calculation", desc: "Safety stock + lead time buffer optimization" },
          ].map((m, i) => (
            <div key={i} style={{ background: "var(--bg-base)", borderRadius: 12, padding: 16, border: "1.5px solid var(--border)" }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: "var(--text-primary)", marginBottom: 6 }}>{m.method}</div>
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{m.desc}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}

export function ForecastOrdersTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Expected Orders" value="368/wk" sub="Next 4 weeks forecast" icon={<BarChart3 size={20} />} color="var(--accent)" />
        <StatCard label="Revenue Projection" value="₹9.7L" sub="June 2026 forecast" icon={<BarChart3 size={20} />} color="var(--success)" trend="7.2%" trendUp />
        <StatCard label="Peak Territory" value="East Zone" sub="Highest projected demand" icon={<Zap size={20} />} color="var(--warning)" />
        <StatCard label="Demand Alerts" value="3" sub="Territories with variance > 15%" icon={<AlertTriangle size={20} />} color="var(--danger)" />
      </div>
      <Panel title="Weekly Expected Orders by Territory" subtitle="June 2026 forecast" fullWidth>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={orderForecastData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
            <XAxis dataKey="week" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} />
            <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
            <Bar dataKey="north" fill="#4F7FFA" radius={[4, 4, 0, 0]} name="North" stackId="a" />
            <Bar dataKey="south" fill="#34C48B" radius={[0, 0, 0, 0]} name="South" stackId="a" />
            <Bar dataKey="east" fill="#7CB9E8" radius={[0, 0, 0, 0]} name="East" stackId="a" />
            <Bar dataKey="west" fill="#F5A623" radius={[4, 4, 0, 0]} name="West" stackId="a" />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}

export function DeliveryPlanTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Customers Planned" value="1,032" sub="This month" icon={<CalendarDays size={20} />} color="var(--accent)" />
        <StatCard label="Unscheduled" value="450" sub="Not yet in visit plan" icon={<AlertTriangle size={20} />} color="var(--warning)" />
        <StatCard label="High Priority" value="142" sub="Champion segment" icon={<Zap size={20} />} color="var(--danger)" />
        <StatCard label="Working Days" value="26" sub="May 2026" icon={<CalendarDays size={20} />} color="var(--success)" />
      </div>
      <Panel title="RFM-Based Customer Priority Tiers" subtitle="Visit cadence by segment — May 2026" fullWidth>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Segment", "Customers", "Visit Frequency", "Priority"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11.5, fontWeight: 700, color: "var(--text-muted)", borderBottom: "1.5px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {monthlyPlan.map((row, i) => {
              const colors: Record<string, string> = { Critical: "var(--danger)", High: "var(--warning)", Urgent: "#F06565", Normal: "var(--accent)", Low: "var(--text-muted)" };
              const bgs: Record<string, string> = { Critical: "#F0656518", High: "#F5A62318", Urgent: "#F0656518", Normal: "var(--accent-light)", Low: "#E8EDF5" };
              return (
                <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "11px 12px", fontWeight: 600, fontSize: 13, color: "var(--text-primary)" }}>{row.segment}</td>
                  <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{row.customers}</td>
                  <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{row.frequency}</td>
                  <td style={{ padding: "11px 12px" }}>
                    <span style={{ background: bgs[row.priority], color: colors[row.priority], fontWeight: 700, fontSize: 12, padding: "3px 12px", borderRadius: 20 }}>{row.priority}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

export function RouteOptimizerTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Routes Generated" value="4 Routes" sub="Today — May 22, 2026" icon={<Route size={20} />} color="var(--accent)" />
        <StatCard label="Total Distance" value="336 km" sub="All drivers combined" icon={<Route size={20} />} color="var(--info)" />
        <StatCard label="Total Stops" value="47" sub="Customer visits" icon={<CheckCircle size={20} />} color="var(--success)" />
        <StatCard label="Avg Load Factor" value="90.8%" sub="Truck capacity utilization" icon={<Zap size={20} />} color="var(--warning)" />
      </div>
      <Panel title="Today's Optimized Delivery Routes" subtitle="VRP-solved, warehouse-anchored — traffic-adjusted ETAs" fullWidth>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Driver", "Stops", "Total Distance", "ETA", "Load Factor"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11.5, fontWeight: 700, color: "var(--text-muted)", borderBottom: "1.5px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {routeData.map((r, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "11px 12px", fontWeight: 600, fontSize: 13, color: "var(--text-primary)" }}>{r.driver}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{r.stops} stops</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{r.distance} km</td>
                <td style={{ padding: "11px 12px", fontSize: 13 }}>
                  <span style={{ background: "var(--accent-light)", color: "var(--accent)", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 20 }}>{r.eta}</span>
                </td>
                <td style={{ padding: "11px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ flex: 1, height: 6, background: "var(--bg-base)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${r.load}%`, height: "100%", background: r.load > 90 ? "var(--warning)" : "var(--success)", borderRadius: 3 }} />
                    </div>
                    <span style={{ fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>{r.load}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

export function AIAdvancedTab() {
  const features = [
    {
      title: "Dynamic Territory Design",
      icon: "🗺️",
      status: "In Research",
      color: "#7CB9E8",
      desc: "Automatically redesign sales and delivery territories as customer distribution changes.",
      methods: ["Geospatial clustering (K-means, DBSCAN, HDBSCAN)", "Revenue and workload balancing", "Warehouse distance constraints", "Territory stability vs. adaptability tradeoff"],
    },
    {
      title: "Smart Routing by Volume & Capacity",
      icon: "🚚",
      status: "In Research",
      color: "#F5A623",
      desc: "Maximize truck utilization while minimizing distance and trips.",
      methods: ["Multi-capacity VRP (volume + weight)", "SKU-level load planning", "Split delivery constraints", "Integration with warehouse picking"],
    },
    {
      title: "In-Visit Product Recommendation",
      icon: "🛍️",
      status: "Planned",
      color: "#34C48B",
      desc: "Enable incremental sales at the point of delivery via driver-facing recommendation scripts.",
      methods: ["Previously purchased but missing products", "Seasonal & trending products", "Cross-sell (basket analysis)", "Inventory & capacity filters"],
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ background: "var(--accent-light)", borderRadius: 16, padding: "16px 20px", border: "1.5px solid #C8D9FF", display: "flex", alignItems: "center", gap: 12 }}>
        <Brain size={22} color="var(--accent)" />
        <div>
          <div style={{ fontWeight: 700, fontSize: 14, color: "var(--text-primary)" }}>Optional Advanced Optimization Features</div>
          <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Future capabilities — currently in research and planning phase. Requires modeling investment.</div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
        {features.map((f, i) => (
          <Panel key={i} title={`${f.icon} ${f.title}`} subtitle={f.desc}
            action={<span style={{ background: `${f.color}20`, color: f.color, fontWeight: 700, fontSize: 11, padding: "3px 10px", borderRadius: 20 }}>{f.status}</span>}
          >
            <ul style={{ listStyle: "none", display: "flex", flexDirection: "column", gap: 8 }}>
              {f.methods.map((m, j) => (
                <li key={j} style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: f.color, marginTop: 5, flexShrink: 0 }} />
                  <span style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>{m}</span>
                </li>
              ))}
            </ul>
          </Panel>
        ))}
      </div>
    </div>
  );
}

export function SettingsTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <Panel title="System Configuration" subtitle="Dashboard & data settings">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
          {[
            { label: "Company Name", value: "Raj Logistics Pvt. Ltd." },
            { label: "Currency", value: "INR (₹)" },
            { label: "Fiscal Year Start", value: "April" },
            { label: "Reorder Lead Time (default)", value: "7 days" },
            { label: "Low Stock Threshold", value: "≤ 30 days of cover" },
            { label: "Churn Risk Threshold", value: "2× normal cycle" },
          ].map((item, i) => (
            <div key={i} style={{ background: "var(--bg-base)", borderRadius: 10, padding: "14px 16px" }}>
              <div style={{ fontSize: 11.5, color: "var(--text-muted)", fontWeight: 600, marginBottom: 4 }}>{item.label}</div>
              <div style={{ fontSize: 14, fontWeight: 700, color: "var(--text-primary)" }}>{item.value}</div>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
