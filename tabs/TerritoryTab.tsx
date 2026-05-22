"use client";
import StatCard from "@/components/StatCard";
import Panel from "@/components/Panel";
import { Map, TrendingUp, Truck, XCircle } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis } from "recharts";

const territories = [
  { name: "North", orderValue: 580000, customers: 312, newCustomers: 24, successRate: 96.2, failedVisits: 12, avgTime: 2.1 },
  { name: "South", orderValue: 490000, customers: 278, newCustomers: 18, successRate: 92.8, failedVisits: 22, avgTime: 2.6 },
  { name: "East", orderValue: 640000, customers: 388, newCustomers: 31, successRate: 97.1, failedVisits: 12, avgTime: 1.9 },
  { name: "West", orderValue: 425000, customers: 241, newCustomers: 15, successRate: 89.7, failedVisits: 30, avgTime: 3.1 },
  { name: "Central", orderValue: 534000, customers: 263, newCustomers: 21, successRate: 94.4, failedVisits: 15, avgTime: 2.3 },
];

const radarData = territories.map(t => ({
  territory: t.name,
  "Success Rate": t.successRate,
  "Coverage": Math.round(t.customers / 4),
  "Growth": t.newCustomers * 3,
}));

export default function TerritoryTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Total Territories" value="5 Zones" icon={<Map size={20} />} color="var(--accent)" />
        <StatCard label="Best Territory" value="East Zone" sub="₹6.4L order value" icon={<TrendingUp size={20} />} color="var(--success)" />
        <StatCard label="Total Deliveries" value="1,703" sub="Last 6 months" icon={<Truck size={20} />} color="#7CB9E8" trend="8.4%" trendUp />
        <StatCard label="Failed Visits" value="91" sub="Across all territories" icon={<XCircle size={20} />} color="var(--danger)" trend="3.2%" trendUp={false} />
      </div>

      {/* Territory table */}
      <Panel title="Territory Performance Summary" subtitle="Last 6 months — all zones" fullWidth>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Territory", "Order Value", "Active Customers", "New Customers", "Success Rate", "Failed Visits", "Avg Delivery Time"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11.5, fontWeight: 700, color: "var(--text-muted)", borderBottom: "1.5px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {territories.map((t, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ background: "var(--accent-light)", color: "var(--accent)", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 20 }}>{t.name}</span>
                </td>
                <td style={{ padding: "11px 12px", fontWeight: 700, fontSize: 13, color: "var(--text-primary)" }}>₹{(t.orderValue / 1000).toFixed(0)}K</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{t.customers}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--success)", fontWeight: 600 }}>+{t.newCustomers}</td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ background: t.successRate >= 95 ? "#34C48B18" : t.successRate >= 90 ? "#F5A62318" : "#F0656518", color: t.successRate >= 95 ? "var(--success)" : t.successRate >= 90 ? "var(--warning)" : "var(--danger)", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 20 }}>
                    {t.successRate}%
                  </span>
                </td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: t.failedVisits > 20 ? "var(--danger)" : "var(--text-secondary)", fontWeight: t.failedVisits > 20 ? 700 : 400 }}>{t.failedVisits}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{t.avgTime}h</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Panel title="Order Value by Territory" subtitle="₹ — last 6 months">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={territories}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} tickFormatter={(v) => `₹${v / 1000}K`} />
              <Tooltip formatter={(v) => { const n = Number(v); return [`₹${(n / 1000).toFixed(0)}K`, "Order Value"]; }} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Bar dataKey="orderValue" fill="#4F7FFA" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Territory Radar — Multi-Metric" subtitle="Success rate, coverage & growth">
          <ResponsiveContainer width="100%" height={200}>
            <RadarChart data={territories}>
              <PolarGrid stroke="#E8EDF5" />
              <PolarAngleAxis dataKey="name" tick={{ fontSize: 11, fill: "#6B8CAE" }} />
              <PolarRadiusAxis tick={false} axisLine={false} />
              <Radar name="Success" dataKey="successRate" stroke="#4F7FFA" fill="#4F7FFA" fillOpacity={0.15} />
              <Radar name="Customers" dataKey="customers" stroke="#34C48B" fill="#34C48B" fillOpacity={0.12} />
            </RadarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </div>
  );
}
