"use client";
import { useState } from "react";
import Panel from "@/components/Panel";
import { User, Mail, Building, Phone, Save, Edit2 } from "lucide-react";

export default function ProfileTab() {
  const [isEditing, setIsEditing] = useState(false);
  const [profile, setProfile] = useState({
    name: "Raj Logistics",
    fullName: "Rajesh Kumar",
    email: "raj@deliviq.com",
    role: "Admin",
    company: "Raj Logistics Pvt. Ltd.",
    phone: "+91 98765 43210",
  });

  const [edited, setEdited] = useState(profile);

  const handleSave = () => {
    setProfile(edited);
    setIsEditing(false);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <Panel title="User Profile" subtitle="View and edit your account details">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
          {Object.entries(isEditing ? edited : profile).map(([key, value]) => {
            if (key === "name") return null; // handled separately
            const Icon = getIconForKey(key);
            return (
              <div key={key} style={{ background: "var(--bg-base)", borderRadius: 12, padding: "14px 16px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                  {Icon}
                  <div style={{ fontSize: 11, fontWeight: 700, color: "var(--text-muted)", textTransform: "capitalize" }}>
                    {key.replace(/([A-Z])/g, " $1").trim()}
                  </div>
                </div>
                {isEditing ? (
                  <input
                    type="text"
                    value={edited[key as keyof typeof edited] as string}
                    onChange={(e) => setEdited({ ...edited, [key]: e.target.value })}
                    style={{
                      width: "100%",
                      padding: "8px 0",
                      border: "none",
                      borderBottom: "1px solid var(--border)",
                      background: "transparent",
                      fontSize: 14,
                      fontWeight: 600,
                      color: "var(--text-primary)",
                      outline: "none",
                    }}
                  />
                ) : (
                  <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-primary)" }}>{value as string}</div>
                )}
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 24 }}>
          {isEditing ? (
            <>
              <button
                onClick={() => { setIsEditing(false); setEdited(profile); }}
                style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid var(--border)", background: "transparent", cursor: "pointer" }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                style={{ padding: "8px 16px", borderRadius: 8, background: "var(--accent)", color: "white", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
              >
                <Save size={14} /> Save Changes
              </button>
            </>
          ) : (
            <button
              onClick={() => setIsEditing(true)}
              style={{ padding: "8px 16px", borderRadius: 8, background: "var(--accent-light)", color: "var(--accent)", border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 6 }}
            >
              <Edit2 size={14} /> Edit Profile
            </button>
          )}
        </div>
      </Panel>
    </div>
  );
}

function getIconForKey(key: string) {
  switch (key) {
    case "fullName": return <User size={16} color="var(--accent)" />;
    case "email": return <Mail size={16} color="var(--accent)" />;
    case "role": return <User size={16} color="var(--accent)" />;
    case "company": return <Building size={16} color="var(--accent)" />;
    case "phone": return <Phone size={16} color="var(--accent)" />;
    default: return <User size={16} color="var(--accent)" />;
  }
}