"use client";
import StatCard from "@/components/StatCard";
import Panel from "@/components/Panel";
import { AlertTriangle, TrendingDown, RotateCcw, ShoppingCart, Package } from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  LineChart, Line, Legend,
} from "recharts";

const topProducts = [
  { name: "Rice 25kg", orders: 412 },
  { name: "Wheat Flour 10kg", orders: 384 },
  { name: "Sugar 5kg", orders: 341 },
  { name: "Cooking Oil 5L", orders: 308 },
  { name: "Dal Yellow 1kg", orders: 276 },
  { name: "Salt 1kg", orders: 251 },
];

const lowStockItems = [
  { sku: "SKU-1042", product: "Cooking Oil 5L", stock: 24, reorder: 50, days: 3 },
  { sku: "SKU-2017", product: "Basmati Rice 5kg", stock: 11, reorder: 30, days: 2 },
  { sku: "SKU-3091", product: "Tea 500g", stock: 8, reorder: 25, days: 1 },
  { sku: "SKU-4055", product: "Ghee 1L", stock: 17, reorder: 40, days: 4 },
  { sku: "SKU-5012", product: "Mustard Oil 1L", stock: 5, reorder: 20, days: 1 },
];

const forecastData = [
  { month: "Jun", projected: 3200 },
  { month: "Jul", projected: 3600 },
  { month: "Aug", projected: 3900 },
];

const turnoverData = [
  { cat: "Grains", ratio: 8.2 },
  { cat: "Oils", ratio: 6.1 },
  { cat: "Spices", ratio: 11.4 },
  { cat: "Pulses", ratio: 7.8 },
  { cat: "Beverages", ratio: 5.3 },
];

export default function InventoryTab() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 16 }}>
        <StatCard label="Low Stock SKUs" value="21" sub="At/below reorder threshold" icon={<AlertTriangle size={20} />} color="var(--warning)" />
        <StatCard label="Overstocked SKUs" value="14" sub="Exceeds 90-day demand" icon={<TrendingDown size={20} />} color="var(--info)" />
        <StatCard label="Avg Turnover Ratio" value="7.8×" sub="COGS ÷ avg inventory" icon={<RotateCcw size={20} />} color="var(--accent)" trend="0.4×" trendUp />
        <StatCard label="Return Rate" value="2.3%" sub="Quality/fulfillment issues" icon={<Package size={20} />} color="var(--danger)" trend="0.2%" trendUp={false} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Panel title="Top Products by Order Count" subtitle="Demand & volume leaders">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={topProducts} layout="vertical" barSize={12}>
              <XAxis type="number" hide />
              <YAxis type="category" dataKey="name" width={130} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
              <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} />
              <Bar dataKey="orders" fill="#4F7FFA" radius={[0, 6, 6, 0]} name="Orders" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>

        <Panel title="Inventory Turnover by Category" subtitle="COGS ÷ average inventory">
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={turnoverData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E8EDF5" />
              <XAxis dataKey="cat" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "#6B8CAE" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "#A8BDD4" }} />
              <Tooltip contentStyle={{ borderRadius: 10, fontSize: 12 }} formatter={(v) => { const n = Number(v); return [`${n}×`, "Ratio"]; }} />
              <Bar dataKey="ratio" fill="#7CB9E8" radius={[6, 6, 0, 0]} name="Turnover" />
            </BarChart>
          </ResponsiveContainer>
        </Panel>
      </div>

      {/* Low stock alerts table */}
      <Panel title="Low Stock Alerts" subtitle="Products at or below reorder threshold" fullWidth
        action={
          <span style={{ background: "#F5A62322", color: "#F5A623", fontWeight: 700, fontSize: 11, padding: "4px 10px", borderRadius: 20 }}>
            {lowStockItems.length} Alerts
          </span>
        }
      >
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {["SKU", "Product", "Current Stock", "Reorder Level", "Days Cover"].map(h => (
                <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11.5, fontWeight: 700, color: "var(--text-muted)", borderBottom: "1.5px solid var(--border)" }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {lowStockItems.map((item, i) => (
              <tr key={i} style={{ borderBottom: "1px solid var(--border)" }}>
                <td style={{ padding: "11px 12px", fontSize: 12, color: "var(--text-muted)", fontWeight: 600 }}>{item.sku}</td>
                <td style={{ padding: "11px 12px", fontSize: 13, fontWeight: 600, color: "var(--text-primary)" }}>{item.product}</td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ background: item.stock < 10 ? "#F0656520" : "#F5A62320", color: item.stock < 10 ? "var(--danger)" : "var(--warning)", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 20 }}>
                    {item.stock} units
                  </span>
                </td>
                <td style={{ padding: "11px 12px", fontSize: 13, color: "var(--text-secondary)" }}>{item.reorder} units</td>
                <td style={{ padding: "11px 12px" }}>
                  <span style={{ background: item.days <= 2 ? "#F0656518" : "#F5A62318", color: item.days <= 2 ? "var(--danger)" : "var(--warning)", fontWeight: 700, fontSize: 12, padding: "3px 10px", borderRadius: 20 }}>
                    {item.days}d
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
