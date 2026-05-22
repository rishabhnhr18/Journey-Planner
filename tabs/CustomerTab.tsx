"use client";
import StatCard from "@/components/StatCard";
import Panel from "@/components/Panel";
import { Users, TrendingUp, AlertCircle, ShoppingBag } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid } from "recharts";

const topCustomers = [
  { name: "Krishna Stores", value: 84200, orders: 38 },
  { name: "Ananya Wholesale", value: 76400, orders: 44 },
  { name: "Raj Enterprises", value: 68900, orders: 29 },
  { name: "Sharma & Sons", value: 61300, orders: 35 },
  { name: "Lakshmi Traders", value: 54700, orders: 31 },
];

const churnRisk = [
  { customer: "Mehta Kirana", lastOrder: "62 days ago", cycle: "21 days", risk: "High" },
  { customer: "Patel Provisions", lastOrder: "48 days ago", cycle: "18 days", risk: "High" },
  { customer: "Gupta General", lastOrder: "36 days ago", cycle: "14 days", risk: "Medium" },
  { customer: "Verma Mart", lastOrder: "29 days ago", cycle: "12 days", risk: "Medium" },
];

const aovTrend = [
  { month: "Dec", avg: 2100 },
  { month: "Jan", avg: 2340 },
  { month: "Feb", avg: 2180 },
  { month: "Mar", avg: 2510 },
  { month: "Apr", avg: 2380 },
  { month: "May", avg: 2640 },
];

export default function CustomerTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Total Customers" value="1,482" icon={<Users size={20} />} color="var(--accent)" trend="4.7%" trendUp />
        <StatCard label="Avg Order Value" value="₹2,640" sub="Up from ₹2,380 last month" icon={<TrendingUp size={20} />} color="var(--success)" trend="10.9%" trendUp />
        <StatCard label="Churn Risk" value="24 Customers" sub="Overdue vs. normal cycle" icon={<AlertCircle size={20} />} color="var(--danger)" />
        <StatCard label="Avg Order Frequency" value="2.8×/mo" icon={<ShoppingBag size={20} />} color="#9B7FFA" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16 }}>
        <Panel title="Top Customers by Order Value" subtitle="Total order amount — last 30 days">
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {topCustomers.map((c, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: "var(--accent-light)", color: "var(--accent)", fontWeight: 800, fontSize: 12, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {i + 1}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{c.name}</div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)" }}>{c.orders} orders</div>
                </div>
                <div style={{ fontWeight: 800, fontSize: 14, color: "var(--text-primary)" }}>₹{(c.value / 1000).toFixed(1)}K</div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="Avg Order Value Trend" subtitle="Month-on-month per customer (₹)">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={aovTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
              <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} />
              <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} formatter={(v) => { const n = Number(v); return [`₹${n}`, "AOV"]; }} />
              <Line type="monotone" dataKey="avg" stroke="#34C48B" strokeWidth={2.5} dot={{ r: 4, fill: "#34C48B" }} />
            </LineChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      <Panel title="Customer Churn Risk Scores" subtitle="Customers overdue compared to their normal order cycle" fullWidth
        action={<span style={{ background: "#F0656520", color: "var(--danger)", fontWeight: 700, fontSize: 11, padding: "4px 10px", borderRadius: 20 }}>Action Required</span>}
      >
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["Customer", "Last Order", "Normal Cycle", "Churn Risk"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11.5, fontWeight: 700, color: "var(--text-muted)", borderBottom: "1.5px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {churnRisk.map((c, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "11px 12px", fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{c.customer}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{c.lastOrder}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{c.cycle}</td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ background: c.risk === "High" ? "#F0656518" : "#F5A62318", color: c.risk === "High" ? "var(--danger)" : "var(--warning)", fontWeight: 700, fontSize: 12, padding: "3px 12px", borderRadius: 20 }}>
                    {c.risk}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
