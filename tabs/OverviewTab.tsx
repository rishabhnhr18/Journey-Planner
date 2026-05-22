"use client";
import StatCard from "@/components/StatCard";
import Panel from "@/components/Panel";
import {
  Package,
  Users,
  Map,
  UserCheck,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  Clock,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";

const revenueData = [
  { month: "Dec", value: 182000 },
  { month: "Jan", value: 214000 },
  { month: "Feb", value: 198000 },
  { month: "Mar", value: 241000 },
  { month: "Apr", value: 228000 },
  { month: "May", value: 267000 },
];

const deliveryData = [
  { name: "North", success: 340, failed: 18 },
  { name: "South", success: 290, failed: 22 },
  { name: "East", success: 410, failed: 12 },
  { name: "West", success: 275, failed: 30 },
  { name: "Central", success: 388, failed: 15 },
];

const pieData = [
  { name: "Optimal Stock", value: 54, color: "#34C48B" },
  { name: "Low Stock", value: 21, color: "#F5A623" },
  { name: "Overstock", value: 14, color: "#7CB9E8" },
  { name: "Stockout", value: 11, color: "#F06565" },
];

export default function OverviewTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {/* Stat row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard
          label="Total Order Value"
          value="₹26.7L"
          sub="Last 30 days"
          trend="11.2%"
          trendUp
          icon={<TrendingUp size={20} />}
          color="var(--accent)"
        />
        <StatCard
          label="Active Customers"
          value="1,482"
          sub="Across all territories"
          trend="4.7%"
          trendUp
          icon={<Users size={20} />}
          color="var(--success)"
        />
        <StatCard
          label="Delivery Success Rate"
          value="93.8%"
          sub="First-attempt success"
          trend="1.1%"
          trendUp={false}
          icon={<CheckCircle size={20} />}
          color="#7CB9E8"
        />
        <StatCard
          label="Low Stock Alerts"
          value="21 SKUs"
          sub="At or below reorder point"
          icon={<AlertTriangle size={20} />}
          color="var(--warning)"
        />
      </div>

      {/* Second row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard
          label="SKUs Tracked"
          value="348"
          sub="Across all categories"
          icon={<Package size={20} />}
          color="#9B7FFA"
        />
        <StatCard
          label="Territories"
          value="5 Zones"
          sub="North · South · East · West · Central"
          icon={<Map size={20} />}
          color="#F5A623"
        />
        <StatCard
          label="Active Salespeople"
          value="38"
          sub="Last 30 days activity"
          icon={<UserCheck size={20} />}
          color="#34C48B"
        />
        <StatCard
          label="Avg Delivery Time"
          value="2.4 hrs"
          sub="Per territory avg"
          icon={<Clock size={20} />}
          color="#F06565"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
        <Panel title="Revenue Trend" subtitle="Monthly order value (₹)">
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={revenueData}>
              <defs>
                <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#4F7FFA" stopOpacity={0.18} />
                  <stop offset="95%" stopColor="#4F7FFA" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="month" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
              <YAxis hide />
              <Tooltip
                contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", fontSize: 12 }}
                formatter={(v) => { const n = Number(v); return [`₹${(n / 1000).toFixed(0)}K`, "Revenue"]; }}
              />
              <Area type="monotone" dataKey="value" stroke="#4F7FFA" strokeWidth={2.5} fill="url(#rev)" dot={{ r: 4, fill: "#4F7FFA" }} />
            </AreaChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Inventory Status" subtitle="SKU distribution">
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={55} outerRadius={85} dataKey="value" paddingAngle={3}>
                {pieData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => { const n = Number(v); return [`${n}%`, ""]; }} contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
            </PieChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* Delivery performance */}
      <Panel title="Delivery Performance by Territory" subtitle="Successful vs. failed visits — last 6 months" fullWidth>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={deliveryData} barGap={4}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
            <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
            <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} />
            <Tooltip contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", fontSize: 12 }} />
            <Bar dataKey="success" fill="#34C48B" radius={[6, 6, 0, 0]} name="Successful" />
            <Bar dataKey="failed" fill="#F06565" radius={[6, 6, 0, 0]} name="Failed" />
            <Legend iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11 }} />
          </BarChart>
        </ResponsiveContainer>
      </Panel>
    </div>
  );
}
