"use client";
import StatCard from "@/components/StatCard";
import Panel from "@/components/Panel";
import { UserCheck, Route, DollarSign, Target } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

const salespeople = [
  { name: "Arjun Sharma", deliveries: 148, failed: 6, successRate: 96.1, km: 2840, ordersPerKm: 0.052, revenue: 412000, customers: 68, aov: 2784, onTime: 94.2 },
  { name: "Priya Nair", deliveries: 136, failed: 9, successRate: 93.8, km: 2210, ordersPerKm: 0.062, revenue: 386000, customers: 61, aov: 2838, onTime: 91.5 },
  { name: "Ravi Kumar", deliveries: 124, failed: 14, successRate: 89.9, km: 3100, ordersPerKm: 0.040, revenue: 344000, customers: 55, aov: 2774, onTime: 87.4 },
  { name: "Sunita Patel", deliveries: 158, failed: 5, successRate: 96.9, km: 2650, ordersPerKm: 0.060, revenue: 441000, customers: 72, aov: 2791, onTime: 95.8 },
  { name: "Mohan Das", deliveries: 112, failed: 18, successRate: 86.2, km: 3420, ordersPerKm: 0.033, revenue: 298000, customers: 48, aov: 2661, onTime: 84.1 },
];

export default function SalespersonTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Top Performer" value="Sunita Patel" sub="158 deliveries · 96.9% success" icon={<UserCheck size={20} />} color="var(--success)" />
        <StatCard label="Avg Success Rate" value="92.6%" icon={<Target size={20} />} color="var(--accent)" trend="1.8%" trendUp />
        <StatCard label="Total Revenue" value="₹18.8L" sub="All salespeople — 6 months" icon={<DollarSign size={20} />} color="#9B7FFA" />
        <StatCard label="Avg Orders/km" value="0.049" sub="Cost efficiency metric" icon={<Route size={20} />} color="#F5A623" />
      </div>

      <Panel title="Salesperson Performance Leaderboard" subtitle="Last 6 months — key metrics" fullWidth>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Salesperson", "Deliveries", "Success Rate", "KM Travelled", "Orders/KM", "Revenue", "Customers", "AOV", "On-Time"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11.5, fontWeight: 700, color: "var(--text-muted)", borderBottom: "1.5px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...salespeople].sort((a, b) => b.deliveries - a.deliveries).map((s, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "11px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <div style={{ width: 30, height: 30, borderRadius: 8, background: i === 0 ? "#4F7FFA20" : "var(--bg-base)", color: i === 0 ? "var(--accent)" : "var(--text-muted)", fontWeight: 800, fontSize: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
                      {i + 1}
                    </div>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{s.name}</span>
                  </div>
                </td>
                <td style={{ padding: "11px 12px", fontWeight: 700, fontSize: 13 }}>{s.deliveries}</td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ background: s.successRate >= 95 ? "#34C48B18" : s.successRate >= 90 ? "#F5A62318" : "#F0656518", color: s.successRate >= 95 ? "var(--success)" : s.successRate >= 90 ? "var(--warning)" : "var(--danger)", fontWeight: 700, fontSize: 12, padding: "3px 9px", borderRadius: 20 }}>
                    {s.successRate}%
                  </span>
                </td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{s.km.toLocaleString()} km</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{s.ordersPerKm.toFixed(3)}</td>
                <td style={{ padding: "11px 12px", fontWeight: 700, fontSize: 13, color: "var(--text-primary)" }}>₹{(s.revenue / 1000).toFixed(0)}K</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{s.customers}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>₹{s.aov}</td>
                <td style={{ padding: "11px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ flex: 1, height: 5, background: "var(--bg-base)", borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ width: `${s.onTime}%`, height: "100%", background: s.onTime >= 93 ? "var(--success)" : "var(--warning)", borderRadius: 3 }} />
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", minWidth: 34 }}>{s.onTime}%</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Panel title="Revenue by Salesperson" subtitle="₹ — last 6 months">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={salespeople}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#6B8CAE" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} tickFormatter={v => `₹${v / 1000}K`} />
              <Tooltip formatter={(v) => { const n = Number(v); return [`₹${(n / 1000).toFixed(0)}K`, "Revenue"]; }} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Bar dataKey="revenue" fill="#9B7FFA" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Route Efficiency (Orders per KM)" subtitle="Higher is better">
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={salespeople}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
              <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: "#6B8CAE" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} />
              <Tooltip formatter={(v) => { const n = Number(v); return [n.toFixed(3), "Orders/KM"]; }} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Bar dataKey="ordersPerKm" fill="#F5A623" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>
    </div>
  );
}
