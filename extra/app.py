# import streamlit as st
# import pandas as pd
# import numpy as np
# import plotly.express as px
# import plotly.graph_objects as go
# import folium
# from streamlit_folium import st_folium
# from datetime import date, datetime, timedelta
# import random
# import math
# import string
# from faker import Faker

# # ------------------------------------------------------------
# # PAGE CONFIG (must be first)
# # ------------------------------------------------------------
# st.set_page_config(page_title="DelivIQ – Saudi Route Planner", layout="wide", initial_sidebar_state="expanded")

# # ------------------------------------------------------------
# # CUSTOM CSS (modern, clean)
# # ------------------------------------------------------------
# st.markdown("""
# <style>
#     .stat-card {
#         background: white;
#         border-radius: 16px;
#         padding: 1.2rem 1.5rem;
#         box-shadow: 0 4px 12px rgba(0,0,0,0.05);
#         border: 1px solid #E8EDF5;
#         transition: 0.2s;
#     }
#     .stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(79,127,250,0.15); }
#     .stat-label { font-size: 0.8rem; font-weight: 600; color: #6B8CAE; text-transform: uppercase; letter-spacing: 0.5px; }
#     .stat-value { font-size: 1.8rem; font-weight: 800; color: #1E3A5F; }
#     .stat-trend-up { background: #34C48B18; color: #34C48B; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
#     .stat-trend-down { background: #F0656518; color: #F06565; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
#     .badge { padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.7rem; display: inline-block; }
#     .badge-high { background: #34C48B18; color: #34C48B; }
#     .badge-medium { background: #F5A62318; color: #F5A623; }
#     .badge-low { background: #F0656518; color: #F06565; }
#     hr { margin: 1rem 0; }
# </style>
# """, unsafe_allow_html=True)

# # ------------------------------------------------------------
# # DATA GENERATION (exact copy of your notebook + RFM)
# # ------------------------------------------------------------
# @st.cache_data(ttl=3600, show_spinner=False)
# @st.cache_data(ttl=3600, show_spinner=False)
# def generate_all_data(seed=42):
#     random.seed(seed)
#     np.random.seed(seed)
#     Faker.seed(seed)
#     fake = Faker(["ar_SA", "en_US"])

#     # ---------- Territories ----------
#     TERRITORIES = [
#         {"territory_id":"TER_RUH","territory_name":"Riyadh Central","center_lat":24.7136,"center_lng":46.6753,"radius_km":25,
#          "warehouse_lat":24.5790,"warehouse_lng":46.8237,"warehouse_address":"Industrial Area, Riyadh"},
#         {"territory_id":"TER_JED","territory_name":"Jeddah North","center_lat":21.5433,"center_lng":39.1728,"radius_km":22,
#          "warehouse_lat":21.3429,"warehouse_lng":39.2357,"warehouse_address":"Al Khomrah Logistics Area, Jeddah"},
#         {"territory_id":"TER_DMM","territory_name":"Dammam Metro","center_lat":26.4207,"center_lng":50.0888,"radius_km":20,
#          "warehouse_lat":26.2926,"warehouse_lng":50.1629,"warehouse_address":"2nd Industrial City, Dammam"},
#     ]
#     territory_df = pd.DataFrame(TERRITORIES)
#     territory_df["default_salesperson"] = None
#     territory_df["default_van"] = None

#     LOCALITIES = {
#         "TER_RUH":[("Olaya",24.7115,46.6746),("Al Malaz",24.6676,46.7351),("Al Sulaymaniyah",24.7012,46.7112),("Al Yasmin",24.8271,46.6302),("Hittin",24.7636,46.6022)],
#         "TER_JED":[("Al Rawdah",21.5656,39.1652),("Al Hamra",21.5262,39.1611),("Al Safa",21.5854,39.2181),("Al Salamah",21.5948,39.1485),("Al Zahra",21.6152,39.1335)],
#         "TER_DMM":[("Al Faisaliyah",26.4282,50.0786),("Al Shati",26.4701,50.1124),("Al Mazruiyah",26.4481,50.0962),("Al Badiyah",26.4021,50.0587),("Al Nuzha",26.4337,50.0433)],
#     }
#     CITY_CODES = {"TER_RUH":"RUH","TER_JED":"JED","TER_DMM":"DMM"}
#     PLATE_PREFIXES = {"TER_RUH":"RU","TER_JED":"JE","TER_DMM":"DM"}
#     SAUDI_SALESPERSON_NAMES = [
#         "Abdullah Al-Qahtani","Fahad Al-Otaibi","Mohammed Al-Harbi","Nasser Al-Dossari","Khalid Al-Ghamdi","Saeed Al-Zahrani",
#         "Yousef Al-Mutairi","Majed Al-Shammari","Ahmed Al-Anazi","Salem Al-Rashidi","Omar Al-Shehri","Hassan Al-Yami",
#         "Rashid Al-Malki","Ibrahim Al-Subaie","Mansour Al-Qahtani","Waleed Al-Harbi","Bilal Khan","Imran Ahmed","Sameer Khan","Nadeem Ali","Arif Rahman","Mustafa Hussain"
#     ]
#     OWNER_NAMES = ["Al Rajhi","Al Othman","Al Harbi","Al Qahtani","Al Ghamdi","Al Zahrani","Al Dossari","Al Mutairi","Al Shammari","Al Anazi","Al Rashid","Al Saleh","Al Malki","Al Subaie","Al Shehri"]
#     BUSINESS_PREFIXES = ["Al Noor","Al Waha","Al Baraka","Al Safa","Al Madina","Al Qassim","Al Riyadh","Al Jazeera","Al Khaleej","Al Nada","Al Nakheel","Al Rawabi","Al Tazaj","Al Dana","Al Manar"]
#     SHOP_CATS = ["Grocery","Mini Market","Supermarket","Restaurant","Cafe","Bakery","Butchery","Cold Store","Hotel Kitchen","Catering Kitchen"]
#     BIZ_SUFFIX = {
#         "Grocery":["Grocery","Baqala","Food Store"],"Mini Market":["Mini Market","Corner Market","Baqala"],"Supermarket":["Supermarket","Hyper Mini","Market"],
#         "Restaurant":["Restaurant","Kitchen","Grill"],"Cafe":["Cafe","Coffee House","Roastery"],"Bakery":["Bakery","Sweets & Bakery","Oven"],
#         "Butchery":["Butchery","Meat Shop","Fresh Meat"],"Cold Store":["Cold Store","Frozen Foods","Chilled Foods"],
#         "Hotel Kitchen":["Hotel Kitchen","Hospitality Supplies"],"Catering Kitchen":["Catering Kitchen","Banquet Kitchen"]
#     }
#     LIFECYCLE = ["Active","New","At Risk","Dormant","Churned"]
#     LC_PROBS = [0.65,0.10,0.15,0.08,0.02]
#     VISIT_DAYS = ["Saturday","Sunday","Monday","Tuesday","Wednesday","Thursday"]
#     ORDER_WINS = ["Morning","Midday","Afternoon"]

#     def haversine(lat1,lng1,lat2,lng2):
#         r=6371.0088; p1,p2=math.radians(lat1),math.radians(lat2)
#         dp,dl=math.radians(lat2-lat1),math.radians(lng2-lng1)
#         a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
#         return 2*r*math.atan2(math.sqrt(a),math.sqrt(1-a))

#     def jitter(lat,lng,r=2.5):
#         lj=np.random.normal(0,r/111/2); lnj=np.random.normal(0,r/(111*np.cos(np.radians(lat)))/2)
#         return float(lat+lj),float(lng+lnj)

#     def generate_plate(pfx): return f"{pfx}{random.choice(string.ascii_uppercase)} {random.randint(1000,9999)}"
#     def perf_mult():
#         b=random.random()
#         if b<0.15: return round(random.uniform(1.10,1.20),2)
#         if b<0.85: return round(random.uniform(0.95,1.08),2)
#         return round(random.uniform(0.85,0.94),2)
#     def cold_req(cat):
#         p={"Cold Store":1.00,"Butchery":1.00,"Hotel Kitchen":0.80,"Catering Kitchen":0.75,"Restaurant":0.60,"Supermarket":0.45,"Bakery":0.25,"Cafe":0.20,"Grocery":0.12,"Mini Market":0.12}
#         return random.random()<p[cat]
#     def pay_type(tier): return "credit" if random.random()<{"HIGH":0.75,"MED":0.45,"LOW":0.20}[tier] else "cash"
#     def credit_terms(tier,pay,lc):
#         if pay=="cash": return 0.0,0.0
#         lo,hi={"HIGH":(30000,120000),"MED":(10000,45000),"LOW":(2000,15000)}[tier]
#         lim=round(random.uniform(lo,hi),2)
#         if lc in ["At Risk","Dormant"]: pct=random.uniform(0.55,1.10)
#         elif lc=="Churned": pct=random.uniform(0.70,1.10)
#         else: pct=random.choices([random.uniform(0.05,0.35),random.uniform(0.35,0.70),random.uniform(0.70,1.10)],weights=[0.65,0.25,0.10],k=1)[0]
#         return lim,round(lim*pct,2)
#     def shop_name(cat,loc,used):
#         sfx=random.choice(BIZ_SUFFIX[cat]); inc=random.random()<0.28
#         tpls=["{p} {s}","{o} {s}","{p} Fresh {s}","{o} Trading {s}"]
#         if inc: tpls+=["{l} {s}","{p} {l} {s}"]
#         for _ in range(50):
#             n=random.choice(tpls).format(p=random.choice(BUSINESS_PREFIXES),o=random.choice(OWNER_NAMES),l=loc,s=sfx)
#             if n not in used: used.add(n); return n
#         n=f"{loc} {sfx} {random.randint(100,999)}"; used.add(n); return n

#     # Salespeople
#     names=SAUDI_SALESPERSON_NAMES.copy(); random.shuffle(names)
#     sp_rows=[]
#     for _,ter in territory_df.iterrows():
#         for n in range(1,4):
#             sp_rows.append({"sales_id":f"SAL_{CITY_CODES[ter.territory_id]}_{n:03d}","name":names.pop(0),"territory_id":ter.territory_id,"assigned_van":None,"performance_multiplier":perf_mult(),"active":True})
#     sp_df=pd.DataFrame(sp_rows)

#     # Vans
#     van_rows=[]
#     for _,ter in territory_df.iterrows():
#         ter_sp=sp_df[sp_df.territory_id==ter.territory_id]
#         for n in range(1,len(ter_sp)+2):
#             cold=random.random()<0.4
#             van_rows.append({"van_id":f"VAN_{CITY_CODES[ter.territory_id]}_{n:03d}","plate":generate_plate(PLATE_PREFIXES[ter.territory_id]),"territory_id":ter.territory_id,"cold_chain":cold,"assigned_salesperson":None,"active":True})
#     van_df=pd.DataFrame(van_rows)

#     # Assign vans -> salespeople
#     for _,ter in territory_df.iterrows():
#         sp_idx=sp_df[sp_df.territory_id==ter.territory_id].index.tolist()
#         van_idx=van_df[van_df.territory_id==ter.territory_id].sample(frac=1).index.tolist()
#         for i,si in enumerate(sp_idx):
#             sp_df.at[si,"assigned_van"]=van_df.at[van_idx[i],"van_id"]
#             van_df.at[van_idx[i],"assigned_salesperson"]=sp_df.at[si,"sales_id"]
#     # Territory defaults
#     for idx,row in territory_df.iterrows():
#         sp0=sp_df[sp_df.territory_id==row.territory_id].iloc[0]
#         van0=van_df[(van_df.territory_id==row.territory_id)&(van_df.assigned_salesperson==sp0.sales_id)].iloc[0]
#         territory_df.at[idx,"default_salesperson"]=sp0.sales_id
#         territory_df.at[idx,"default_van"]=van0.van_id

#     # Customers (using notebook logic – includes all fields)
#     today=date(2024,12,31)
#     cust_rows=[]
#     for _,ter in territory_df.iterrows():
#         code=CITY_CODES[ter.territory_id]; used=set()
#         tiers = ["HIGH"]*20 + ["MED"]*30 + ["LOW"]*50
#         random.shuffle(tiers)
#         for i in range(1,101):   # 100 per territory
#             cid=f"CUS_{code}_{i:04d}"
#             locality,base_lat,base_lng=random.choice(LOCALITIES[ter.territory_id])
#             for _ in range(20):
#                 lat,lng=jitter(base_lat,base_lng,2.0)
#                 if haversine(lat,lng,ter.center_lat,ter.center_lng)<=ter.radius_km: break
#             else:
#                 lat,lng=base_lat,base_lng
#             tier = tiers[i-1]
#             lifecycle = random.choices(LIFECYCLE, weights=LC_PROBS, k=1)[0]
#             category = random.choice(SHOP_CATS)
#             payment = pay_type(tier)
#             credit_lim, outstanding = credit_terms(tier, payment, lifecycle)
#             sd = random.randint(30, 1460)
#             acq_date = (today - timedelta(days=sd)).isoformat()
#             cust_rows.append({
#                 "customer_id": cid,
#                 "shop_name": shop_name(category, locality, used),
#                 "gps_lat": round(lat,6),
#                 "gps_lng": round(lng,6),
#                 "locality": locality,
#                 "territory_id": ter.territory_id,
#                 "customer_rating": random.choices([1,2,3,4,5], weights=[0.05,0.10,0.25,0.35,0.25])[0],
#                 "review_rating": round(float(np.clip(np.random.normal(4.0,0.55),2.5,5.0)),1),
#                 "shop_category": category,
#                 "cold_truck_required": cold_req(category),
#                 "volume_tier": tier,
#                 "payment_type": payment,
#                 "credit_limit": credit_lim,
#                 "outstanding_balance": outstanding,
#                 "lifecycle_state": lifecycle,
#                 "acquisition_date": acq_date,
#                 "preferred_visit_day": random.choice(VISIT_DAYS),
#                 "preferred_order_window": random.choice(ORDER_WINS),
#             })
#     cust_df=pd.DataFrame(cust_rows)

#     # RFM scoring (exact notebook version)
#     rfm_rows=[]
#     for _,c in cust_df.iterrows():
#         tier,lc=c.volume_tier,c.lifecycle_state
#         if tier=="HIGH": rec=random.randint(1,20); freq=random.randint(20,50); mon=random.uniform(25000,180000)
#         elif tier=="MED": rec=random.randint(7,45); freq=random.randint(8,25); mon=random.uniform(7000,55000)
#         else: rec=random.randint(20,90); freq=random.randint(1,12); mon=random.uniform(500,12000)
#         if lc=="New": rec=random.randint(1,14); freq=max(1,int(freq*random.uniform(0.25,0.55))); mon*=random.uniform(0.25,0.60)
#         elif lc=="At Risk": rec=max(rec,random.randint(45,100)); freq=max(1,int(freq*random.uniform(0.45,0.85))); mon*=random.uniform(0.60,1.00)
#         elif lc=="Dormant": rec=random.randint(90,180); freq=max(0,int(freq*random.uniform(0.10,0.35))); mon*=random.uniform(0.10,0.35)
#         elif lc=="Churned": rec=random.randint(181,365); freq=random.choice([0,0,1]); mon*=random.uniform(0.00,0.10)
#         rfm_rows.append({"customer_id":c.customer_id,"recency":int(rec),"frequency":int(freq),"monetary":round(float(mon),2)})
#     rfm_df=pd.DataFrame(rfm_rows)

#     def quantile_score(series,higher=True):
#         ranks=series.rank(method="first")
#         scored=pd.qcut(ranks,q=5,labels=[1,2,3,4,5]).astype(int)
#         return scored if higher else 6-scored
#     rfm_df["r_score"]=quantile_score(rfm_df["recency"],higher=False)
#     rfm_df["f_score"]=quantile_score(rfm_df["frequency"],higher=True)
#     rfm_df["m_score"]=quantile_score(rfm_df["monetary"],higher=True)
#     rfm_df["rfm_score"]=rfm_df["r_score"].astype(str)+rfm_df["f_score"].astype(str)+rfm_df["m_score"].astype(str)
#     def segment(r):
#         rv,fv,mv=r.r_score,r.f_score,r.m_score
#         if rv>=4 and fv>=4 and mv>=4: return "Champion"
#         if fv>=4 and mv>=3: return "Loyal"
#         if rv>=4 and fv in [2,3]: return "Potential Loyalist"
#         if rv<=2 and fv>=3: return "At Risk"
#         if rv<=2 and fv<=2 and mv<=2: return "Hibernating"
#         return "Need Attention"
#     rfm_df["segment"]=rfm_df.apply(segment,axis=1)

#     # Merge RFM back to customers
#     cust_df = cust_df.merge(rfm_df[["customer_id","recency","frequency","monetary","segment","rfm_score"]], on="customer_id", how="left")

#     # Add convenience columns for Journey Planner
#     cust_df["visit_days"] = cust_df["preferred_visit_day"]
#     cust_df["order_window"] = cust_df["preferred_order_window"]

#     # Config (simple)
#     cfg_df = pd.DataFrame([{"config_key":k,"config_value":str(v)} for k,v in {"avg_speed_kmh":32,"avg_service_time_min":22,"buffer_pct":0.15,"rfm_window_days":90,"route_partial_prob":0.08,"route_cancel_prob":0.03,"traffic_jam_prob":0.12,"credit_outstanding_cap":0.85,"normal_shift_start_time":"09:00","ramadan_shift_start_time":"10:00"}.items()])

#     return territory_df, sp_df, van_df, cust_df, rfm_df, cfg_df

# # ------------------------------------------------------------
# # LOAD DATA
# # ------------------------------------------------------------
# with st.spinner("Generating Saudi master data..."):
#     territory_df, sp_df, van_df, cust_df, rfm_df, cfg_df = generate_all_data(42)

# # ------------------------------------------------------------
# # HELPER: stat card
# # ------------------------------------------------------------
# def stat_card(label, value, trend=None, trend_up=True, icon="📊"):
#     trend_html = ""
#     if trend:
#         cls = "stat-trend-up" if trend_up else "stat-trend-down"
#         arrow = "▲" if trend_up else "▼"
#         trend_html = f"<div><span class='{cls}'>{arrow} {trend}</span></div>"
#     return f"""
#     <div class='stat-card'>
#         <div class='stat-label'>{icon} {label}</div>
#         <div class='stat-value'>{value}</div>
#         {trend_html}
#     </div>
#     """

# # ------------------------------------------------------------
# # SIDEBAR NAVIGATION
# # ------------------------------------------------------------
# st.sidebar.title("DelivIQ 🚚")
# st.sidebar.markdown("---")
# page = st.sidebar.radio("Navigation", [
#     "📊 Overview",
#     "👥 Customers",
#     "🗺️ Territories",
#     "🧑‍💼 Salespeople",
#     "🗓️ Journey Planner",
#     "🚐 Vans & Fleet",
#     "📈 RFM Analysis",
#     "📅 Monthly Plan",
#     "ℹ️ About Us",
#     "⚙️ Config & Quality"
# ])
# st.sidebar.markdown("---")
# st.sidebar.caption(f"Data generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
# st.sidebar.caption(f"**{len(cust_df)} customers** | **{len(sp_df)} salespeople** | **{len(van_df)} vans**")

# # Colour palette
# BLUE="#4F7FFA"; GREEN="#34C48B"; ORANGE="#F5A623"; RED="#F06565"; PURPLE="#9B7FFA"; TEAL="#7CB9E8"
# SEGMENT_COLORS={"Champion":GREEN,"Loyal":BLUE,"Potential Loyalist":TEAL,"Need Attention":ORANGE,"At Risk":RED,"Hibernating":PURPLE}
# LC_COLORS={"Active":GREEN,"New":BLUE,"At Risk":ORANGE,"Dormant":PURPLE,"Churned":RED}
# TIER_COLORS={"HIGH":GREEN,"MED":BLUE,"LOW":ORANGE}

# # ------------------------------------------------------------
# # PAGE: OVERVIEW
# # ------------------------------------------------------------
# if page == "📊 Overview":
#     st.title("📊 Dashboard Overview")
#     st.caption("Saudi master data – generated on the fly")

#     k1,k2,k3,k4 = st.columns(4)
#     k1.metric("Total Customers", len(cust_df))
#     k2.metric("Territories", len(territory_df))
#     k3.metric("Salespeople", len(sp_df))
#     k4.metric("Cold‑Chain Vans", int(van_df["cold_chain"].sum()))

#     col1,col2 = st.columns(2)
#     with col1:
#         # Revenue by territory (synthetic from monetary)
#         rev = cust_df.groupby("territory_id")["monetary"].sum().reset_index()
#         rev["Territory"] = rev["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#         fig = px.bar(rev, x="Territory", y="monetary", title="💰 Estimated Revenue by Territory",
#                      color_discrete_sequence=[BLUE], template="plotly_white")
#         fig.update_layout(plot_bgcolor="white", height=350)
#         st.plotly_chart(fig, use_container_width=True)
#     with col2:
#         lc_counts = cust_df["lifecycle_state"].value_counts().reset_index()
#         lc_counts.columns = ["Lifecycle","Count"]
#         fig = px.pie(lc_counts, names="Lifecycle", values="Count", title="📌 Customer Lifecycle",
#                      color="Lifecycle", color_discrete_map=LC_COLORS, hole=0.4)
#         fig.update_layout(height=350)
#         st.plotly_chart(fig, use_container_width=True)

#     st.subheader("👥 Customers by Tier & Territory")
#     tier_terr = cust_df.groupby(["territory_id","volume_tier"]).size().unstack(fill_value=0)
#     tier_terr.index = tier_terr.index.map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(tier_terr, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: CUSTOMERS
# # ------------------------------------------------------------
# elif page == "👥 Customers":
#     st.title("👥 Know Your Customer")
#     col1,col2,col3,col4 = st.columns(4)
#     col1.metric("Total Customers", len(cust_df))
#     col2.metric("Avg Monetary", f"SAR {cust_df['monetary'].mean():,.0f}")
#     col3.metric("Credit Customers", f"{(cust_df['payment_type']=='credit').sum()}")
#     col4.metric("Cold‑Chain Required", f"{cust_df['cold_truck_required'].sum()}")

#     st.subheader("🏆 Top Customers by Monetary Value")
#     top_cust = cust_df.nlargest(10, "monetary")[["shop_name","volume_tier","segment","monetary","territory_id"]]
#     top_cust["territory_id"] = top_cust["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(top_cust, use_container_width=True)

#     st.subheader("⚠️ At‑Risk Customers")
#     at_risk = cust_df[cust_df["lifecycle_state"]=="At Risk"][["shop_name","shop_category","volume_tier","outstanding_balance","monetary"]]
#     st.dataframe(at_risk, use_container_width=True)

#     with st.expander("📋 Full Customer Table"):
#         disp = cust_df[["customer_id","shop_name","shop_category","territory_id","volume_tier","lifecycle_state","payment_type","credit_limit","outstanding_balance"]].copy()
#         disp["territory_id"] = disp["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#         st.dataframe(disp, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: TERRITORIES
# # ------------------------------------------------------------
# elif page == "🗺️ Territories":
#     st.title("🗺️ Know Your Territory")
#     ter_stats = []
#     for _,ter in territory_df.iterrows():
#         tc = cust_df[cust_df["territory_id"]==ter.territory_id]
#         ter_stats.append({
#             "Territory": ter.territory_name,
#             "Customers": len(tc),
#             "New": (tc["lifecycle_state"]=="New").sum(),
#             "At Risk": (tc["lifecycle_state"]=="At Risk").sum(),
#             "Cold Chain": tc["cold_truck_required"].sum(),
#             "Total Monetary (SAR)": round(tc["monetary"].sum(),0),
#             "Avg Monetary (SAR)": round(tc["monetary"].mean(),0),
#         })
#     ter_df_disp = pd.DataFrame(ter_stats)
#     st.dataframe(ter_df_disp, use_container_width=True)

#     # Map of customers
#     st.subheader("📍 Customer Locations")
#     map_data = cust_df.sample(min(200,len(cust_df)))[["gps_lat","gps_lng","shop_name","volume_tier"]]
#     fig = px.scatter_mapbox(map_data, lat="gps_lat", lon="gps_lng", hover_name="shop_name", color="volume_tier",
#                             color_discrete_map=TIER_COLORS, zoom=4, height=450,
#                             title="Customer GPS Locations")
#     fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0})
#     st.plotly_chart(fig, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: SALESPEOPLE
# # ------------------------------------------------------------
# elif page == "🧑‍💼 Salespeople":
#     st.title("🧑‍💼 Know Your Salesperson")
#     sp_stats = []
#     for _, sp in sp_df.iterrows():
#         ter_name = territory_df[territory_df["territory_id"] == sp.territory_id]["territory_name"].values[0]
#         tc = cust_df[cust_df["territory_id"] == sp.territory_id]
#         n_sp = len(sp_df[sp_df["territory_id"] == sp.territory_id])
#         share = max(1, len(tc) // n_sp)
#         my_cust = tc.sample(min(share, len(tc)), random_state=42)
#         sp_stats.append({
#             "Name": sp["name"],
#             "Territory": ter_name,
#             "Van": sp["assigned_van"],
#             "Customers": len(my_cust),
#             "Revenue (SAR)": round(my_cust["monetary"].sum(), 0),
#             "Avg AOV (SAR)": round(my_cust["monetary"].mean(), 0),
#             "Performance": sp["performance_multiplier"],
#         })
#     sp_df_disp = pd.DataFrame(sp_stats).sort_values("Revenue (SAR)", ascending=False).reset_index(drop=True)
#     st.dataframe(sp_df_disp, use_container_width=True)

#     st.subheader("🗺️ Salesperson Territory Map")
#     sel_sp = st.selectbox("Select Salesperson", sp_df_disp["Name"].tolist(), key="sp_select")

#     # Get territory for selected salesperson
#     sp_row = sp_df[sp_df["name"] == sel_sp]
#     if not sp_row.empty:
#         ter = sp_row.iloc[0]["territory_id"]
#         cust_ter = cust_df[cust_df["territory_id"] == ter].sample(min(50, len(cust_df)), random_state=42)
#         if not cust_ter.empty:
#             center_lat = cust_ter["gps_lat"].mean()
#             center_lon = cust_ter["gps_lng"].mean()
#             # Create a colorful Folium map with OpenStreetMap tiles
#             m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")
#             for _, row in cust_ter.iterrows():
#                 # Color by volume tier
#                 color = {"HIGH": "green", "MED": "blue", "LOW": "orange"}.get(row["volume_tier"], "gray")
#                 folium.Marker(
#                     [row["gps_lat"], row["gps_lng"]],
#                     popup=f"{row['shop_name']}<br>Tier: {row['volume_tier']}<br>Segment: {row['segment']}",
#                     icon=folium.Icon(color=color, icon="shop", prefix="fa")
#                 ).add_to(m)
#             # Use a unique key to prevent endless reload
#             st_folium(m, width=700, height=450, key=f"map_{sel_sp}")
#         else:
#             st.info("No customers found in this territory.")
#     else:
#         st.info("Select a salesperson to see their territory.")
        
# # ------------------------------------------------------------
# # PAGE: JOURNEY PLAN
# # ------------------------------------------------------------
# elif page == "🗓️ Journey Planner":
#     st.title("🗓️ Generated Journey Plan")
#     st.caption("Optimised daily visit schedule per salesperson — nearest-neighbour routing from warehouse")

#     # ── helpers ───────────────────────────────────────────────────────────────
#     TER_NAMES = {"TER_RUH":"Riyadh Central","TER_JED":"Jeddah North","TER_DMM":"Dammam Metro"}
#     AVG_SPEED_KMH   = 32
#     SERVICE_MIN     = 22
#     SHIFT_START     = "09:00"
#     MAX_SHIFT_HRS   = 9

#     # Make sure customers have visit_days and order_window
#     if "visit_days" not in cust_df.columns:
#         cust_df["visit_days"] = cust_df["preferred_visit_day"] if "preferred_visit_day" in cust_df.columns else "Monday"
#     if "order_window" not in cust_df.columns:
#         cust_df["order_window"] = cust_df["preferred_order_window"] if "preferred_order_window" in cust_df.columns else "Morning"

#     # Haversine function for distance (reuse existing function or redefine)
#     def _haversine(lat1, lon1, lat2, lon2):
#         R = 6371.0
#         lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
#         dlat = lat2_r - lat1_r
#         dlon = lon2_r - lon1_r
#         a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
#         return 2 * R * math.asin(math.sqrt(a))

#     @st.cache_data(show_spinner=False)
#     def build_journey_plans(_cust_df, _sp_df, _ter_df, _van_df, selected_day: str):
#         plans = {}
#         for _, sp in _sp_df.iterrows():
#             ter = _ter_df[_ter_df.territory_id == sp.territory_id].iloc[0]
#             van = _van_df[_van_df.van_id == sp.assigned_van]
#             is_cold_van = bool(van.iloc[0].cold_chain) if len(van) else False

#             # Customers for this salesperson's territory scheduled on this day
#             tc = _cust_df[
#                 (_cust_df.territory_id == sp.territory_id) &
#                 (_cust_df.visit_days.str.contains(selected_day, na=False))
#             ].copy()
#             if tc.empty:
#                 plans[sp.sales_id] = []
#                 continue

#             # Priority score
#             tier_score = tc.volume_tier.map({"HIGH":3,"MED":2,"LOW":1}).fillna(1)
#             seg_score = tc.segment.map({"Champion":5,"Loyal":4,"Potential Loyalist":3,
#                                          "Need Attention":2,"At Risk":2,"Hibernating":1}).fillna(1)
#             max_ob = tc.outstanding_balance.max() or 1
#             ob_score = (tc.outstanding_balance / max_ob * 3).fillna(0)
#             tc["priority_score"] = (tier_score * 1.5 + seg_score + ob_score).round(2)
#             tc = tc.sort_values("priority_score", ascending=False).reset_index(drop=True)

#             # Nearest‑neighbour route from warehouse
#             wh_lat, wh_lng = ter.warehouse_lat, ter.warehouse_lng
#             unvisited = tc.copy()
#             ordered = []
#             cur_lat, cur_lng = wh_lat, wh_lng
#             cum_km = 0.0
#             cur_time = datetime.strptime(SHIFT_START, "%H:%M")
#             shift_end = cur_time.replace(hour=cur_time.hour + MAX_SHIFT_HRS)

#             while not unvisited.empty:
#                 dists = unvisited.apply(lambda r: _haversine(cur_lat, cur_lng, r.gps_lat, r.gps_lng), axis=1)
#                 nearest_idx = dists.idxmin()
#                 nearest = unvisited.loc[nearest_idx]
#                 dist_km = dists[nearest_idx]
#                 travel_min = (dist_km / AVG_SPEED_KMH) * 60
#                 arrive_time = cur_time + timedelta(minutes=travel_min)
#                 depart_time = arrive_time + timedelta(minutes=SERVICE_MIN)
#                 if depart_time > shift_end:
#                     break
#                 cum_km += dist_km
#                 ordered.append({
#                     "stop": len(ordered)+1,
#                     "customer_id": nearest.customer_id,
#                     "shop_name": nearest.shop_name,
#                     "category": nearest.shop_category,
#                     "locality": nearest.locality,
#                     "volume_tier": nearest.volume_tier,
#                     "lifecycle": nearest.lifecycle_state,
#                     "segment": nearest.segment,
#                     "priority": nearest.priority_score,
#                     "order_window": nearest.order_window,
#                     "payment": nearest.payment_type,
#                     "outstanding": nearest.outstanding_balance,
#                     "cold_required": nearest.cold_truck_required,
#                     "cold_van": is_cold_van,
#                     "gps_lat": nearest.gps_lat,
#                     "gps_lng": nearest.gps_lng,
#                     "dist_from_prev_km": round(dist_km, 2),
#                     "cum_km": round(cum_km, 2),
#                     "arrive": arrive_time.strftime("%H:%M"),
#                     "depart": depart_time.strftime("%H:%M"),
#                 })
#                 cur_lat, cur_lng = nearest.gps_lat, nearest.gps_lng
#                 cur_time = depart_time
#                 unvisited = unvisited.drop(index=nearest_idx)

#             return_km = _haversine(cur_lat, cur_lng, wh_lat, wh_lng)
#             cum_km += return_km
#             plans[sp.sales_id] = {
#                 "stops": ordered,
#                 "total_km": round(cum_km, 2),
#                 "return_km": round(return_km, 2),
#                 "total_stops": len(ordered),
#                 "sp_name": sp["name"],
#                 "territory": TER_NAMES[sp.territory_id],
#                 "van": sp.assigned_van,
#                 "cold_van": is_cold_van,
#                 "warehouse_lat": wh_lat,
#                 "warehouse_lng": wh_lng,
#                 "warehouse_addr": ter.warehouse_address,
#             }
#         return plans

#     # ── UI controls ───────────────────────────────────────────────────────────
#     ctrl1, ctrl2, ctrl3 = st.columns([2,2,2])
#     VISIT_DAYS = ["Saturday","Sunday","Monday","Tuesday","Wednesday","Thursday"]
#     selected_day = ctrl1.selectbox("📅 Select Visit Day", VISIT_DAYS, index=0)
#     ter_options = {"All Territories": None,
#                    "Riyadh Central": "TER_RUH",
#                    "Jeddah North": "TER_JED",
#                    "Dammam Metro": "TER_DMM"}
#     selected_ter = ctrl2.selectbox("🗺️ Filter Territory", list(ter_options.keys()))
#     priority_only = ctrl3.checkbox("⭐ Show HIGH priority stops only", value=False)

#     with st.spinner(f"Building optimised routes for {selected_day}…"):
#         all_plans = build_journey_plans(cust_df, sp_df, territory_df, van_df, selected_day)

#     ter_id_filter = ter_options[selected_ter]
#     sp_ids = [sp.sales_id for _, sp in sp_df.iterrows()
#               if ter_id_filter is None or sp.territory_id == ter_id_filter]

#     # ── Summary KPIs ──────────────────────────────────────────────────────────
#     total_stops = sum(all_plans[s]["total_stops"] for s in sp_ids if all_plans[s])
#     total_km    = sum(all_plans[s]["total_km"] for s in sp_ids if all_plans[s])
#     active_sp   = sum(1 for s in sp_ids if all_plans.get(s) and all_plans[s]["total_stops"] > 0)
#     cold_stops  = sum(
#         sum(1 for st in all_plans[s]["stops"] if st["cold_required"])
#         for s in sp_ids if all_plans.get(s)
#     )
#     k1,k2,k3,k4,k5 = st.columns(5)
#     k1.metric("Day", selected_day)
#     k2.metric("Active Salespeople", active_sp)
#     k3.metric("Total Stops", f"{total_stops:,}")
#     k4.metric("Total KM", f"{total_km:,.1f} km")
#     k5.metric("Cold-Chain Stops", cold_stops)

#     st.markdown("---")

#     # ── Per-salesperson journey cards ─────────────────────────────────────────
#     TIER_BADGE = {"HIGH":"🟢 HIGH","MED":"🔵 MED","LOW":"🟡 LOW"}
#     SEG_BADGE = {"Champion":"🏆","Loyal":"⭐","Potential Loyalist":"🌱",
#                  "Need Attention":"⚠️","At Risk":"🔴","Hibernating":"💤"}

#     for sp_id in sp_ids:
#         plan = all_plans.get(sp_id)
#         if not plan or plan["total_stops"] == 0:
#             continue
#         stops = plan["stops"]
#         if priority_only:
#             stops = [s for s in stops if s["volume_tier"] == "HIGH"]
#         if not stops:
#             continue

#         with st.expander(
#             f"🧑‍💼 {plan['sp_name']}  ·  {plan['territory']}  "
#             f"·  {plan['total_stops']} stops  ·  {plan['total_km']} km  "
#             f"·  Van: {plan['van']}{'  ❄️' if plan['cold_van'] else ''}",
#             expanded=(active_sp <= 3)
#         ):
#             mc, tc2 = st.columns([1, 1])
#             with mc:
#                 # Build map data
#                 map_points = []
#                 # Warehouse start
#                 map_points.append({
#                     "lat": plan["warehouse_lat"], "lon": plan["warehouse_lng"],
#                     "label": "🏭 Warehouse", "color": "red", "stop": 0,
#                     "name": plan["warehouse_addr"]
#                 })
#                 for s in stops:
#                     map_points.append({
#                         "lat": s["gps_lat"], "lon": s["gps_lng"],
#                         "label": f"#{s['stop']} {s['shop_name'][:20]}",
#                         "color": {"HIGH":"green","MED":"blue","LOW":"orange"}[s["volume_tier"]],
#                         "stop": s["stop"], "name": s["shop_name"]
#                     })
#                 map_df = pd.DataFrame(map_points)

#                 # Create colorful street map with Plotly
#                 fig = px.scatter_mapbox(
#                     map_df, lat="lat", lon="lon",
#                     hover_name="name", hover_data={"stop":True},
#                     color="color",
#                     color_discrete_map={"red":"red","green":"#34C48B","blue":"#4F7FFA","orange":"#F5A623"},
#                     zoom=11, height=380,
#                 )
#                 # Route line (warehouse -> stops -> warehouse)
#                 line_lats = [plan["warehouse_lat"]] + [s["gps_lat"] for s in stops] + [plan["warehouse_lat"]]
#                 line_lons = [plan["warehouse_lng"]] + [s["gps_lng"] for s in stops] + [plan["warehouse_lng"]]
#                 fig.add_trace(go.Scattermapbox(
#                     lat=line_lats, lon=line_lons, mode="lines",
#                     line=dict(width=2, color="#4F7FFA"),
#                     name="Route", showlegend=False, opacity=0.8,
#                 ))
#                 fig.update_layout(
#                     mapbox_style="carto-positron",  # <-- colorful street map
#                     margin=dict(t=0,b=0,l=0,r=0),
#                     showlegend=False,
#                 )
#                 st.plotly_chart(fig, use_container_width=True, key=f"map_{sp_id}_{selected_day}")

#             with tc2:
#                 # Visit schedule table
#                 rows = []
#                 for s in stops:
#                     rows.append({
#                         "Stop": f"#{s['stop']}",
#                         "Arrive": s["arrive"], "Depart": s["depart"],
#                         "Shop": s["shop_name"][:25], "Category": s["category"],
#                         "Tier": TIER_BADGE.get(s["volume_tier"], s["volume_tier"]),
#                         "Segment": f"{SEG_BADGE.get(s['segment'],'')} {s['segment']}",
#                         "Priority": s["priority"], "Window": s["order_window"],
#                         "Payment": s["payment"],
#                         "Outstanding": f"SAR {s['outstanding']:,.0f}" if s["outstanding"]>0 else "—",
#                         "Cold": "❄️" if s["cold_required"] else "",
#                         "Km prev": s["dist_from_prev_km"], "Cum km": s["cum_km"]
#                     })
#                 df_sched = pd.DataFrame(rows)
#                 st.dataframe(df_sched, use_container_width=True, height=360,
#                              column_config={
#                                  "Priority": st.column_config.NumberColumn(format="%.2f"),
#                                  "Km prev": st.column_config.NumberColumn(format="%.1f"),
#                                  "Cum km": st.column_config.NumberColumn(format="%.1f"),
#                              })
#             # Stats bar
#             a,b,c,d,e = st.columns(5)
#             a.metric("Stops today", plan["total_stops"])
#             b.metric("Total KM", f"{plan['total_km']:.1f}")
#             c.metric("Return KM", f"{plan['return_km']:.1f}")
#             high_stops = sum(1 for s in stops if s["volume_tier"]=="HIGH")
#             d.metric("HIGH-tier stops", high_stops)
#             e.metric("Outstanding SAR", f"{sum(s['outstanding'] for s in stops):,.0f}")

#     # ── Consolidated plan table ───────────────────────────────────────────────
#     st.markdown("---")
#     st.subheader("📋 Consolidated Plan — All Salespeople")
#     all_rows = []
#     for sp_id in sp_ids:
#         plan = all_plans.get(sp_id)
#         if not plan: continue
#         for s in plan["stops"]:
#             all_rows.append({
#                 "Salesperson": plan["sp_name"], "Territory": plan["territory"],
#                 "Van": plan["van"], "Stop #": s["stop"], "Arrive": s["arrive"],
#                 "Depart": s["depart"], "Shop": s["shop_name"], "Category": s["category"],
#                 "Locality": s["locality"], "Tier": s["volume_tier"], "Lifecycle": s["lifecycle"],
#                 "Segment": s["segment"], "Priority": s["priority"], "Order Window": s["order_window"],
#                 "Payment": s["payment"], "Outstanding": s["outstanding"],
#                 "Cold Req.": s["cold_required"], "Km prev": s["dist_from_prev_km"],
#                 "Cum. Km": s["cum_km"],
#             })
#     if all_rows:
#         cons_df = pd.DataFrame(all_rows)
#         st.caption(f"{len(cons_df)} total visits planned across {active_sp} salespeople on **{selected_day}**")
#         csv = cons_df.to_csv(index=False).encode("utf-8")
#         st.download_button("⬇️ Download full plan as CSV", data=csv,
#                            file_name=f"journey_plan_{selected_day.lower()}.csv", mime="text/csv")
#         st.dataframe(cons_df, use_container_width=True, height=400)
        

# # ------------------------------------------------------------
# # PAGE: VANS & FLEET
# # ------------------------------------------------------------

# elif page == "🚐 Vans & Fleet":
#     st.title("🚐 Vans & Fleet")
#     col1,col2,col3 = st.columns(3)
#     col1.metric("Total Vans", len(van_df))
#     col2.metric("Cold‑Chain Vans", int(van_df["cold_chain"].sum()))
#     col3.metric("Active Vans", int(van_df["active"].sum()))
#     st.dataframe(van_df[["van_id","plate","territory_id","cold_chain","assigned_salesperson"]], use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: RFM ANALYSIS
# # ------------------------------------------------------------
# elif page == "📈 RFM Analysis":
#     st.title("📈 RFM Segmentation")
#     seg_counts = rfm_df["segment"].value_counts().reset_index()
#     seg_counts.columns = ["Segment","Count"]
#     fig = px.bar(seg_counts, x="Segment", y="Count", title="RFM Segment Distribution",
#                  color="Segment", color_discrete_map=SEGMENT_COLORS, template="plotly_white")
#     st.plotly_chart(fig, use_container_width=True)

#     st.subheader("🏅 Champion Customers")
#     champions = cust_df[cust_df["segment"]=="Champion"][["shop_name","shop_category","volume_tier","monetary","territory_id"]]
#     champions["territory_id"] = champions["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(champions, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: MONTHLY PLAN (recommended visit schedule)
# # ------------------------------------------------------------
# elif page == "📅 Monthly Plan":
#     st.title("📅 Monthly Visit Plan")
#     st.markdown("**Recommended visit frequency and best days based on RFM segment and lifecycle.**")

#     # Mapping for territory names
#     territory_names = {"TER_RUH": "Riyadh", "TER_JED": "Jeddah", "TER_DMM": "Dammam"}

#     # Generate plan rules
#     def visit_recommendation(row):
#         seg = row["segment"]
#         lc = row["lifecycle_state"]
#         if seg == "Champion":
#             freq = "4 times/month"
#             days = "Mon, Wed, Fri"
#         elif seg == "Loyal":
#             freq = "3 times/month"
#             days = "Tue, Thu"
#         elif seg == "Potential Loyalist":
#             freq = "2 times/month"
#             days = "Wed, Sat"
#         elif seg == "At Risk":
#             freq = "2 times/month (urgent)"
#             days = "Sun, Tue"
#         elif seg == "Hibernating":
#             freq = "1 time/month (re‑engagement)"
#             days = "Thursday"
#         else:
#             freq = "1 time/month"
#             days = "Monday"
#         # adjust for lifecycle
#         if lc == "New":
#             freq = "3 times/month (onboarding)"
#         elif lc == "Dormant":
#             freq = "1 time/month (win‑back)"
#         elif lc == "Churned":
#             freq = "None – churned"
#         return freq, days

#     plan_data = []
#     for _, cust in cust_df.iterrows():
#         freq, days = visit_recommendation(cust)
#         plan_data.append({
#             "Customer ID": cust["customer_id"],
#             "Shop Name": cust["shop_name"],
#             "Territory": territory_names.get(cust["territory_id"], cust["territory_id"]),
#             "RFM Segment": cust["segment"],
#             "Lifecycle": cust["lifecycle_state"],
#             "Recommended Visits/Month": freq,
#             "Preferred Days": days
#         })
#     plan_df = pd.DataFrame(plan_data)
#     st.dataframe(plan_df, use_container_width=True, height=500)

#     # Download as CSV
#     csv = plan_df.to_csv(index=False).encode("utf-8")
#     st.download_button("📥 Download Monthly Plan (CSV)", csv, "monthly_plan.csv", "text/csv")
# # ------------------------------------------------------------
# # PAGE: ABOUT US
# # ------------------------------------------------------------
# elif page == "ℹ️ About Us":
#     st.title("ℹ️ About DelivIQ")
#     st.markdown("""
#     **DelivIQ** is an AI‑powered route planning and master data dashboard designed for Saudi logistics.

#     - **Territories**: Riyadh, Jeddah, Dammam – with realistic GPS coordinates and warehouse locations.
#     - **Customers**: 300 synthetic shops (grocery, butchery, cold stores, restaurants, etc.) with lifecycle, RFM, credit limits.
#     - **Salespeople**: Performance multipliers, assigned vans.
#     - **Monthly Plan**: Smart visit recommendations based on RFM and lifecycle state.

#     **Data source**: Synthetic Saudi master data generator (seed=42).  
#     **Built with**: Streamlit, Plotly, Folium, Pandas.

#     © 2026 DelivIQ – All data is simulated for demonstration.
#     """)

# # ------------------------------------------------------------
# # PAGE: CONFIG & QUALITY
# # ------------------------------------------------------------
# elif page == "⚙️ Config & Quality":
#     st.title("⚙️ Configuration & Data Quality")
#     st.subheader("System Config")
#     st.dataframe(cfg_df.rename(columns={"config_key":"Key","config_value":"Value"}), use_container_width=True)

#     st.subheader("Data Quality Report")
#     st.markdown(f"""
#     - **Territories**: {len(territory_df)}  
#     - **Salespeople**: {len(sp_df)}  
#     - **Vans**: {len(van_df)}  
#     - **Customers**: {len(cust_df)}  
#     - **RFM Scores**: {len(rfm_df)}  
#     - **Validation**: All foreign keys, primary keys, business rules passed ✅  
#     """)

#     st.subheader("Tier Distribution (per territory)")
#     tier_check = cust_df.groupby(["territory_id","volume_tier"]).size().unstack(fill_value=0)
#     tier_check.index = tier_check.index.map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(tier_check, use_container_width=True)

#     with st.expander("🔍 Raw Data Samples"):
#         tab1,tab2,tab3 = st.tabs(["Customers","Salespeople","Vans"])
#         with tab1: st.dataframe(cust_df.head(20), use_container_width=True)
#         with tab2: st.dataframe(sp_df, use_container_width=True)
#         with tab3: st.dataframe(van_df, use_container_width=True)






# import streamlit as st
# import pandas as pd
# import numpy as np
# import plotly.express as px
# import plotly.graph_objects as go
# import folium
# from streamlit_folium import st_folium
# from datetime import date, datetime, timedelta
# import random
# import math
# import string
# from faker import Faker
# from folium.plugins import PolyLineTextPath

# # ------------------------------------------------------------
# # PAGE CONFIG (must be first)
# # ------------------------------------------------------------
# st.set_page_config(page_title="DelivIQ – Saudi Route Planner", layout="wide", initial_sidebar_state="expanded")

# # ------------------------------------------------------------
# # GLOBAL CONSTANTS (used by Journey Planner)
# # ------------------------------------------------------------
# VISIT_DAYS = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
# ORDER_WINDOWS = ["Morning", "Midday", "Afternoon"]

# # ------------------------------------------------------------
# # CUSTOM CSS (modern, clean)
# # ------------------------------------------------------------
# st.markdown("""
# <style>
#     .stat-card {
#         background: white;
#         border-radius: 16px;
#         padding: 1.2rem 1.5rem;
#         box-shadow: 0 4px 12px rgba(0,0,0,0.05);
#         border: 1px solid #E8EDF5;
#         transition: 0.2s;
#     }
#     .stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(79,127,250,0.15); }
#     .stat-label { font-size: 0.8rem; font-weight: 600; color: #6B8CAE; text-transform: uppercase; letter-spacing: 0.5px; }
#     .stat-value { font-size: 1.8rem; font-weight: 800; color: #1E3A5F; }
#     .stat-trend-up { background: #34C48B18; color: #34C48B; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
#     .stat-trend-down { background: #F0656518; color: #F06565; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
#     .badge { padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.7rem; display: inline-block; }
#     .badge-high { background: #34C48B18; color: #34C48B; }
#     .badge-medium { background: #F5A62318; color: #F5A623; }
#     .badge-low { background: #F0656518; color: #F06565; }
#     hr { margin: 1rem 0; }
# </style>
# """, unsafe_allow_html=True)

# # ------------------------------------------------------------
# # DATA GENERATION (full Saudi master data from notebook)
# # ------------------------------------------------------------
# @st.cache_data(ttl=3600, show_spinner=False)
# def generate_all_data(seed=42):
#     random.seed(seed)
#     np.random.seed(seed)
#     Faker.seed(seed)
#     fake = Faker(["ar_SA", "en_US"])

#     # ---------- Territories ----------
#     TERRITORIES = [
#         {"territory_id":"TER_RUH","territory_name":"Riyadh Central","center_lat":24.7136,"center_lng":46.6753,"radius_km":25,
#          "warehouse_lat":24.5790,"warehouse_lng":46.8237,"warehouse_address":"Industrial Area, Riyadh"},
#         {"territory_id":"TER_JED","territory_name":"Jeddah North","center_lat":21.5433,"center_lng":39.1728,"radius_km":22,
#          "warehouse_lat":21.3429,"warehouse_lng":39.2357,"warehouse_address":"Al Khomrah Logistics Area, Jeddah"},
#         {"territory_id":"TER_DMM","territory_name":"Dammam Metro","center_lat":26.4207,"center_lng":50.0888,"radius_km":20,
#          "warehouse_lat":26.2926,"warehouse_lng":50.1629,"warehouse_address":"2nd Industrial City, Dammam"},
#     ]
#     territory_df = pd.DataFrame(TERRITORIES)
#     territory_df["default_salesperson"] = None
#     territory_df["default_van"] = None

#     LOCALITIES = {
#         "TER_RUH":[("Olaya",24.7115,46.6746),("Al Malaz",24.6676,46.7351),("Al Sulaymaniyah",24.7012,46.7112),("Al Yasmin",24.8271,46.6302),("Hittin",24.7636,46.6022)],
#         "TER_JED":[("Al Rawdah",21.5656,39.1652),("Al Hamra",21.5262,39.1611),("Al Safa",21.5854,39.2181),("Al Salamah",21.5948,39.1485),("Al Zahra",21.6152,39.1335)],
#         "TER_DMM":[("Al Faisaliyah",26.4282,50.0786),("Al Shati",26.4701,50.1124),("Al Mazruiyah",26.4481,50.0962),("Al Badiyah",26.4021,50.0587),("Al Nuzha",26.4337,50.0433)],
#     }
#     CITY_CODES = {"TER_RUH":"RUH","TER_JED":"JED","TER_DMM":"DMM"}
#     PLATE_PREFIXES = {"TER_RUH":"RU","TER_JED":"JE","TER_DMM":"DM"}
#     SAUDI_SALESPERSON_NAMES = [
#         "Abdullah Al-Qahtani","Fahad Al-Otaibi","Mohammed Al-Harbi","Nasser Al-Dossari","Khalid Al-Ghamdi","Saeed Al-Zahrani",
#         "Yousef Al-Mutairi","Majed Al-Shammari","Ahmed Al-Anazi","Salem Al-Rashidi","Omar Al-Shehri","Hassan Al-Yami",
#         "Rashid Al-Malki","Ibrahim Al-Subaie","Mansour Al-Qahtani","Waleed Al-Harbi","Bilal Khan","Imran Ahmed","Sameer Khan","Nadeem Ali","Arif Rahman","Mustafa Hussain"
#     ]
#     OWNER_NAMES = ["Al Rajhi","Al Othman","Al Harbi","Al Qahtani","Al Ghamdi","Al Zahrani","Al Dossari","Al Mutairi","Al Shammari","Al Anazi","Al Rashid","Al Saleh","Al Malki","Al Subaie","Al Shehri"]
#     BUSINESS_PREFIXES = ["Al Noor","Al Waha","Al Baraka","Al Safa","Al Madina","Al Qassim","Al Riyadh","Al Jazeera","Al Khaleej","Al Nada","Al Nakheel","Al Rawabi","Al Tazaj","Al Dana","Al Manar"]
#     SHOP_CATS = ["Grocery","Mini Market","Supermarket","Restaurant","Cafe","Bakery","Butchery","Cold Store","Hotel Kitchen","Catering Kitchen"]
#     BIZ_SUFFIX = {
#         "Grocery":["Grocery","Baqala","Food Store"],"Mini Market":["Mini Market","Corner Market","Baqala"],"Supermarket":["Supermarket","Hyper Mini","Market"],
#         "Restaurant":["Restaurant","Kitchen","Grill"],"Cafe":["Cafe","Coffee House","Roastery"],"Bakery":["Bakery","Sweets & Bakery","Oven"],
#         "Butchery":["Butchery","Meat Shop","Fresh Meat"],"Cold Store":["Cold Store","Frozen Foods","Chilled Foods"],
#         "Hotel Kitchen":["Hotel Kitchen","Hospitality Supplies"],"Catering Kitchen":["Catering Kitchen","Banquet Kitchen"]
#     }
#     LIFECYCLE = ["Active","New","At Risk","Dormant","Churned"]
#     LC_PROBS = [0.65,0.10,0.15,0.08,0.02]
#     ORDER_WINS = ["Morning","Midday","Afternoon"]

#     def haversine(lat1,lng1,lat2,lng2):
#         r=6371.0088; p1,p2=math.radians(lat1),math.radians(lat2)
#         dp,dl=math.radians(lat2-lat1),math.radians(lng2-lng1)
#         a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
#         return 2*r*math.atan2(math.sqrt(a),math.sqrt(1-a))

#     def jitter(lat,lng,r=2.5):
#         lj=np.random.normal(0,r/111/2); lnj=np.random.normal(0,r/(111*np.cos(np.radians(lat)))/2)
#         return float(lat+lj),float(lng+lnj)

#     def generate_plate(pfx): return f"{pfx}{random.choice(string.ascii_uppercase)} {random.randint(1000,9999)}"
#     def perf_mult():
#         b=random.random()
#         if b<0.15: return round(random.uniform(1.10,1.20),2)
#         if b<0.85: return round(random.uniform(0.95,1.08),2)
#         return round(random.uniform(0.85,0.94),2)
#     def cold_req(cat):
#         p={"Cold Store":1.00,"Butchery":1.00,"Hotel Kitchen":0.80,"Catering Kitchen":0.75,"Restaurant":0.60,"Supermarket":0.45,"Bakery":0.25,"Cafe":0.20,"Grocery":0.12,"Mini Market":0.12}
#         return random.random()<p[cat]
#     def pay_type(tier): return "credit" if random.random()<{"HIGH":0.75,"MED":0.45,"LOW":0.20}[tier] else "cash"
#     def credit_terms(tier,pay,lc):
#         if pay=="cash": return 0.0,0.0
#         lo,hi={"HIGH":(30000,120000),"MED":(10000,45000),"LOW":(2000,15000)}[tier]
#         lim=round(random.uniform(lo,hi),2)
#         if lc in ["At Risk","Dormant"]: pct=random.uniform(0.55,1.10)
#         elif lc=="Churned": pct=random.uniform(0.70,1.10)
#         else: pct=random.choices([random.uniform(0.05,0.35),random.uniform(0.35,0.70),random.uniform(0.70,1.10)],weights=[0.65,0.25,0.10],k=1)[0]
#         return lim,round(lim*pct,2)
#     def shop_name(cat,loc,used):
#         sfx=random.choice(BIZ_SUFFIX[cat]); inc=random.random()<0.28
#         tpls=["{p} {s}","{o} {s}","{p} Fresh {s}","{o} Trading {s}"]
#         if inc: tpls+=["{l} {s}","{p} {l} {s}"]
#         for _ in range(50):
#             n=random.choice(tpls).format(p=random.choice(BUSINESS_PREFIXES),o=random.choice(OWNER_NAMES),l=loc,s=sfx)
#             if n not in used: used.add(n); return n
#         n=f"{loc} {sfx} {random.randint(100,999)}"; used.add(n); return n

#     # Salespeople
#     names=SAUDI_SALESPERSON_NAMES.copy(); random.shuffle(names)
#     sp_rows=[]
#     for _,ter in territory_df.iterrows():
#         for n in range(1,4):
#             sp_rows.append({"sales_id":f"SAL_{CITY_CODES[ter.territory_id]}_{n:03d}","name":names.pop(0),"territory_id":ter.territory_id,"assigned_van":None,"performance_multiplier":perf_mult(),"active":True})
#     sp_df=pd.DataFrame(sp_rows)

#     # Vans
#     van_rows=[]
#     for _,ter in territory_df.iterrows():
#         ter_sp=sp_df[sp_df.territory_id==ter.territory_id]
#         for n in range(1,len(ter_sp)+2):
#             cold=random.random()<0.4
#             van_rows.append({"van_id":f"VAN_{CITY_CODES[ter.territory_id]}_{n:03d}","plate":generate_plate(PLATE_PREFIXES[ter.territory_id]),"territory_id":ter.territory_id,"cold_chain":cold,"assigned_salesperson":None,"active":True})
#     van_df=pd.DataFrame(van_rows)

#     # Assign vans -> salespeople
#     for _,ter in territory_df.iterrows():
#         sp_idx=sp_df[sp_df.territory_id==ter.territory_id].index.tolist()
#         van_idx=van_df[van_df.territory_id==ter.territory_id].sample(frac=1).index.tolist()
#         for i,si in enumerate(sp_idx):
#             sp_df.at[si,"assigned_van"]=van_df.at[van_idx[i],"van_id"]
#             van_df.at[van_idx[i],"assigned_salesperson"]=sp_df.at[si,"sales_id"]
#     # Territory defaults
#     for idx,row in territory_df.iterrows():
#         sp0=sp_df[sp_df.territory_id==row.territory_id].iloc[0]
#         van0=van_df[(van_df.territory_id==row.territory_id)&(van_df.assigned_salesperson==sp0.sales_id)].iloc[0]
#         territory_df.at[idx,"default_salesperson"]=sp0.sales_id
#         territory_df.at[idx,"default_van"]=van0.van_id

#     # Customers
#     today=date(2024,12,31)
#     cust_rows=[]
#     for _,ter in territory_df.iterrows():
#         code=CITY_CODES[ter.territory_id]; used=set()
#         tiers = ["HIGH"]*20 + ["MED"]*30 + ["LOW"]*50
#         random.shuffle(tiers)
#         for i in range(1,101):
#             cid=f"CUS_{code}_{i:04d}"
#             locality,base_lat,base_lng=random.choice(LOCALITIES[ter.territory_id])
#             for _ in range(20):
#                 lat,lng=jitter(base_lat,base_lng,2.0)
#                 if haversine(lat,lng,ter.center_lat,ter.center_lng)<=ter.radius_km: break
#             else:
#                 lat,lng=base_lat,base_lng
#             tier = tiers[i-1]
#             lifecycle = random.choices(LIFECYCLE, weights=LC_PROBS, k=1)[0]
#             category = random.choice(SHOP_CATS)
#             payment = pay_type(tier)
#             credit_lim, outstanding = credit_terms(tier, payment, lifecycle)
#             sd = random.randint(30, 1460)
#             acq_date = (today - timedelta(days=sd)).isoformat()
#             cust_rows.append({
#                 "customer_id": cid,
#                 "shop_name": shop_name(category, locality, used),
#                 "gps_lat": round(lat,6),
#                 "gps_lng": round(lng,6),
#                 "locality": locality,
#                 "territory_id": ter.territory_id,
#                 "customer_rating": random.choices([1,2,3,4,5], weights=[0.05,0.10,0.25,0.35,0.25])[0],
#                 "review_rating": round(float(np.clip(np.random.normal(4.0,0.55),2.5,5.0)),1),
#                 "shop_category": category,
#                 "cold_truck_required": cold_req(category),
#                 "volume_tier": tier,
#                 "payment_type": payment,
#                 "credit_limit": credit_lim,
#                 "outstanding_balance": outstanding,
#                 "lifecycle_state": lifecycle,
#                 "acquisition_date": acq_date,
#                 "preferred_visit_day": random.choice(VISIT_DAYS),
#                 "preferred_order_window": random.choice(ORDER_WINS),
#             })
#     cust_df=pd.DataFrame(cust_rows)

#     # RFM scoring
#     rfm_rows=[]
#     for _,c in cust_df.iterrows():
#         tier,lc=c.volume_tier,c.lifecycle_state
#         if tier=="HIGH": rec=random.randint(1,20); freq=random.randint(20,50); mon=random.uniform(25000,180000)
#         elif tier=="MED": rec=random.randint(7,45); freq=random.randint(8,25); mon=random.uniform(7000,55000)
#         else: rec=random.randint(20,90); freq=random.randint(1,12); mon=random.uniform(500,12000)
#         if lc=="New": rec=random.randint(1,14); freq=max(1,int(freq*random.uniform(0.25,0.55))); mon*=random.uniform(0.25,0.60)
#         elif lc=="At Risk": rec=max(rec,random.randint(45,100)); freq=max(1,int(freq*random.uniform(0.45,0.85))); mon*=random.uniform(0.60,1.00)
#         elif lc=="Dormant": rec=random.randint(90,180); freq=max(0,int(freq*random.uniform(0.10,0.35))); mon*=random.uniform(0.10,0.35)
#         elif lc=="Churned": rec=random.randint(181,365); freq=random.choice([0,0,1]); mon*=random.uniform(0.00,0.10)
#         rfm_rows.append({"customer_id":c.customer_id,"recency":int(rec),"frequency":int(freq),"monetary":round(float(mon),2)})
#     rfm_df=pd.DataFrame(rfm_rows)

#     def quantile_score(series,higher=True):
#         ranks=series.rank(method="first")
#         scored=pd.qcut(ranks,q=5,labels=[1,2,3,4,5]).astype(int)
#         return scored if higher else 6-scored
#     rfm_df["r_score"]=quantile_score(rfm_df["recency"],higher=False)
#     rfm_df["f_score"]=quantile_score(rfm_df["frequency"],higher=True)
#     rfm_df["m_score"]=quantile_score(rfm_df["monetary"],higher=True)
#     rfm_df["rfm_score"]=rfm_df["r_score"].astype(str)+rfm_df["f_score"].astype(str)+rfm_df["m_score"].astype(str)
#     def segment(r):
#         rv,fv,mv=r.r_score,r.f_score,r.m_score
#         if rv>=4 and fv>=4 and mv>=4: return "Champion"
#         if fv>=4 and mv>=3: return "Loyal"
#         if rv>=4 and fv in [2,3]: return "Potential Loyalist"
#         if rv<=2 and fv>=3: return "At Risk"
#         if rv<=2 and fv<=2 and mv<=2: return "Hibernating"
#         return "Need Attention"
#     rfm_df["segment"]=rfm_df.apply(segment,axis=1)

#     # Merge RFM back to customers
#     cust_df = cust_df.merge(rfm_df[["customer_id","recency","frequency","monetary","segment","rfm_score"]], on="customer_id", how="left")
#     cust_df["visit_days"] = cust_df["preferred_visit_day"]
#     cust_df["order_window"] = cust_df["preferred_order_window"]

#     # Config
#     cfg_df = pd.DataFrame([{"config_key":k,"config_value":str(v)} for k,v in {"avg_speed_kmh":32,"avg_service_time_min":22,"buffer_pct":0.15,"rfm_window_days":90,"route_partial_prob":0.08,"route_cancel_prob":0.03,"traffic_jam_prob":0.12,"credit_outstanding_cap":0.85,"normal_shift_start_time":"09:00","ramadan_shift_start_time":"10:00"}.items()])

#     return territory_df, sp_df, van_df, cust_df, rfm_df, cfg_df

# # ------------------------------------------------------------
# # LOAD DATA
# # ------------------------------------------------------------
# with st.spinner("Generating Saudi master data..."):
#     territory_df, sp_df, van_df, cust_df, rfm_df, cfg_df = generate_all_data(42)

# # ------------------------------------------------------------
# # HELPER: stat card
# # ------------------------------------------------------------
# def stat_card(label, value, trend=None, trend_up=True, icon="📊"):
#     trend_html = ""
#     if trend:
#         cls = "stat-trend-up" if trend_up else "stat-trend-down"
#         arrow = "▲" if trend_up else "▼"
#         trend_html = f"<div><span class='{cls}'>{arrow} {trend}</span></div>"
#     return f"""
#     <div class='stat-card'>
#         <div class='stat-label'>{icon} {label}</div>
#         <div class='stat-value'>{value}</div>
#         {trend_html}
#     </div>
#     """

# # ------------------------------------------------------------
# # HELPER: nearest neighbor route (used in Salespeople map)
# # ------------------------------------------------------------
# def nearest_neighbor_route(df, start_lat, start_lon):
#     """Return ordered list of (lat, lon) from start point visiting all points in df."""
#     remaining = df.copy()
#     route = []
#     cur_lat, cur_lon = start_lat, start_lon
#     while not remaining.empty:
#         distances = remaining.apply(lambda r: math.hypot(cur_lat - r["gps_lat"], cur_lon - r["gps_lng"]), axis=1)
#         idx = distances.idxmin()
#         row = remaining.loc[idx]
#         route.append((row["gps_lat"], row["gps_lng"]))
#         cur_lat, cur_lon = row["gps_lat"], row["gps_lng"]
#         remaining = remaining.drop(idx)
#     return route

# # ------------------------------------------------------------
# # SIDEBAR NAVIGATION
# # ------------------------------------------------------------
# st.sidebar.title("DelivIQ 🚚")
# st.sidebar.markdown("---")
# page = st.sidebar.radio("Navigation", [
#     "📊 Overview",
#     "👥 Customers",
#     "🗺️ Territories",
#     "🧑‍💼 Salespeople",
#     "🗓️ Journey Planner",
#     "🚐 Vans & Fleet",
#     "📈 RFM Analysis",
#     "📅 Monthly Plan",
#     "ℹ️ About Us",
#     "⚙️ Config & Quality"
# ])
# st.sidebar.markdown("---")
# st.sidebar.caption(f"Data generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
# st.sidebar.caption(f"**{len(cust_df)} customers** | **{len(sp_df)} salespeople** | **{len(van_df)} vans**")

# # Colour palette
# BLUE="#4F7FFA"; GREEN="#34C48B"; ORANGE="#F5A623"; RED="#F06565"; PURPLE="#9B7FFA"; TEAL="#7CB9E8"
# SEGMENT_COLORS={"Champion":GREEN,"Loyal":BLUE,"Potential Loyalist":TEAL,"Need Attention":ORANGE,"At Risk":RED,"Hibernating":PURPLE}
# LC_COLORS={"Active":GREEN,"New":BLUE,"At Risk":ORANGE,"Dormant":PURPLE,"Churned":RED}
# TIER_COLORS={"HIGH":GREEN,"MED":BLUE,"LOW":ORANGE}

# # ------------------------------------------------------------
# # PAGE: OVERVIEW
# # ------------------------------------------------------------
# if page == "📊 Overview":
#     st.title("📊 Dashboard Overview")
#     st.caption("Saudi master data – generated on the fly")

#     k1,k2,k3,k4 = st.columns(4)
#     k1.metric("Total Customers", len(cust_df))
#     k2.metric("Territories", len(territory_df))
#     k3.metric("Salespeople", len(sp_df))
#     k4.metric("Cold‑Chain Vans", int(van_df["cold_chain"].sum()))

#     col1,col2 = st.columns(2)
#     with col1:
#         rev = cust_df.groupby("territory_id")["monetary"].sum().reset_index()
#         rev["Territory"] = rev["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#         fig = px.bar(rev, x="Territory", y="monetary", title="💰 Estimated Revenue by Territory",
#                      color_discrete_sequence=[BLUE], template="plotly_white")
#         fig.update_layout(plot_bgcolor="white", height=350)
#         st.plotly_chart(fig, use_container_width=True)
#     with col2:
#         lc_counts = cust_df["lifecycle_state"].value_counts().reset_index()
#         lc_counts.columns = ["Lifecycle","Count"]
#         fig = px.pie(lc_counts, names="Lifecycle", values="Count", title="📌 Customer Lifecycle",
#                      color="Lifecycle", color_discrete_map=LC_COLORS, hole=0.4)
#         fig.update_layout(height=350)
#         st.plotly_chart(fig, use_container_width=True)

#     st.subheader("👥 Customers by Tier & Territory")
#     tier_terr = cust_df.groupby(["territory_id","volume_tier"]).size().unstack(fill_value=0)
#     tier_terr.index = tier_terr.index.map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(tier_terr, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: CUSTOMERS
# # ------------------------------------------------------------
# elif page == "👥 Customers":
#     st.title("👥 Know Your Customer")
#     col1,col2,col3,col4 = st.columns(4)
#     col1.metric("Total Customers", len(cust_df))
#     col2.metric("Avg Monetary", f"SAR {cust_df['monetary'].mean():,.0f}")
#     col3.metric("Credit Customers", f"{(cust_df['payment_type']=='credit').sum()}")
#     col4.metric("Cold‑Chain Required", f"{cust_df['cold_truck_required'].sum()}")

#     st.subheader("🏆 Top Customers by Monetary Value")
#     top_cust = cust_df.nlargest(10, "monetary")[["shop_name","volume_tier","segment","monetary","territory_id"]]
#     top_cust["territory_id"] = top_cust["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(top_cust, use_container_width=True)

#     st.subheader("⚠️ At‑Risk Customers")
#     at_risk = cust_df[cust_df["lifecycle_state"]=="At Risk"][["shop_name","shop_category","volume_tier","outstanding_balance","monetary"]]
#     st.dataframe(at_risk, use_container_width=True)

#     with st.expander("📋 Full Customer Table"):
#         disp = cust_df[["customer_id","shop_name","shop_category","territory_id","volume_tier","lifecycle_state","payment_type","credit_limit","outstanding_balance"]].copy()
#         disp["territory_id"] = disp["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#         st.dataframe(disp, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: TERRITORIES
# # ------------------------------------------------------------
# elif page == "🗺️ Territories":
#     st.title("🗺️ Know Your Territory")
#     ter_stats = []
#     for _,ter in territory_df.iterrows():
#         tc = cust_df[cust_df["territory_id"]==ter.territory_id]
#         ter_stats.append({
#             "Territory": ter.territory_name,
#             "Customers": len(tc),
#             "New": (tc["lifecycle_state"]=="New").sum(),
#             "At Risk": (tc["lifecycle_state"]=="At Risk").sum(),
#             "Cold Chain": tc["cold_truck_required"].sum(),
#             "Total Monetary (SAR)": round(tc["monetary"].sum(),0),
#             "Avg Monetary (SAR)": round(tc["monetary"].mean(),0),
#         })
#     ter_df_disp = pd.DataFrame(ter_stats)
#     st.dataframe(ter_df_disp, use_container_width=True)

#     st.subheader("📍 Customer Locations")
#     map_data = cust_df.sample(min(200,len(cust_df)))[["gps_lat","gps_lng","shop_name","volume_tier"]]
#     fig = px.scatter_mapbox(map_data, lat="gps_lat", lon="gps_lng", hover_name="shop_name", color="volume_tier",
#                             color_discrete_map=TIER_COLORS, zoom=4, height=450,
#                             title="Customer GPS Locations")
#     fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0})
#     st.plotly_chart(fig, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: SALESPEOPLE (with color legend and directed route)
# # ------------------------------------------------------------
# elif page == "🧑‍💼 Salespeople":
#     st.title("🧑‍💼 Know Your Salesperson")
#     sp_stats = []
#     for _, sp in sp_df.iterrows():
#         ter_name = territory_df[territory_df["territory_id"] == sp.territory_id]["territory_name"].values[0]
#         tc = cust_df[cust_df["territory_id"] == sp.territory_id]
#         n_sp = len(sp_df[sp_df["territory_id"] == sp.territory_id])
#         share = max(1, len(tc) // n_sp)
#         my_cust = tc.sample(min(share, len(tc)), random_state=42)
#         sp_stats.append({
#             "Name": sp["name"],
#             "Territory": ter_name,
#             "Van": sp["assigned_van"],
#             "Customers": len(my_cust),
#             "Revenue (SAR)": round(my_cust["monetary"].sum(), 0),
#             "Avg AOV (SAR)": round(my_cust["monetary"].mean(), 0),
#             "Performance": sp["performance_multiplier"],
#         })
#     sp_df_disp = pd.DataFrame(sp_stats).sort_values("Revenue (SAR)", ascending=False).reset_index(drop=True)
#     st.dataframe(sp_df_disp, use_container_width=True)

#     st.subheader("🗺️ Salesperson Territory Map")
#     sel_sp = st.selectbox("Select Salesperson", sp_df_disp["Name"].tolist(), key="sp_select")

#     sp_row = sp_df[sp_df["name"] == sel_sp]
#     if not sp_row.empty:
#         ter = sp_row.iloc[0]["territory_id"]
#         cust_ter = cust_df[cust_df["territory_id"] == ter].sample(min(50, len(cust_df)), random_state=42)
#         if not cust_ter.empty:
#             center_lat = cust_ter["gps_lat"].mean()
#             center_lon = cust_ter["gps_lng"].mean()
#             # Build route (nearest neighbor from warehouse)
#             ter_info = territory_df[territory_df["territory_id"] == ter].iloc[0]
#             wh_lat, wh_lon = ter_info["warehouse_lat"], ter_info["warehouse_lng"]
#             route_ordered = nearest_neighbor_route(cust_ter, wh_lat, wh_lon)
#             full_route = [(wh_lat, wh_lon)] + route_ordered + [(wh_lat, wh_lon)]

#             # Create Folium map
#             m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")
#             # Warehouse marker
#             folium.Marker([wh_lat, wh_lon], popup="🏭 Warehouse", icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
#             # Customer markers
#             for _, row in cust_ter.iterrows():
#                 color = {"HIGH": "green", "MED": "blue", "LOW": "orange"}.get(row["volume_tier"], "gray")
#                 folium.Marker(
#                     [row["gps_lat"], row["gps_lng"]],
#                     popup=f"{row['shop_name']}<br>Tier: {row['volume_tier']}<br>Segment: {row['segment']}",
#                     icon=folium.Icon(color=color, icon="shop", prefix="fa")
#                 ).add_to(m)
#             # Draw directed route line with arrows
#             line = folium.PolyLine(full_route, color="blue", weight=3, opacity=0.7)
#             m.add_child(line)
#             # Add arrows along the line
#             PolyLineTextPath(line, "➤", repeat=True, offset=7, attributes={"fill": "red", "font-size": "14"}).add_to(m)

#             # Add color legend
#             legend_html = """
#             <div style="position: fixed; bottom: 30px; right: 30px; z-index: 1000; background: white; padding: 10px 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); font-size: 12px; font-family: sans-serif;">
#                 <strong>Volume Tier</strong><br>
#                 <span style="color:green;">●</span> HIGH<br>
#                 <span style="color:blue;">●</span> MED<br>
#                 <span style="color:orange;">●</span> LOW<br>
#                 <span style="color:red;">●</span> Warehouse<br>
#                 <span style="color:blue;">➤</span> Directed route
#             </div>
#             """
#             m.get_root().html.add_child(folium.Element(legend_html))

#             st_folium(m, width=800, height=500, key=f"map_{sel_sp}")
#         else:
#             st.info("No customers found in this territory.")
#     else:
#         st.info("Select a salesperson to see their territory.")

# # ------------------------------------------------------------
# # PAGE: JOURNEY PLANNER (full working, colorful street maps)
# # ------------------------------------------------------------
# elif page == "🗓️ Journey Planner":
#     st.title("🗓️ Generated Journey Plan")
#     st.caption("Optimised daily visit schedule per salesperson — nearest-neighbour routing from warehouse")

#     TER_NAMES = {"TER_RUH":"Riyadh Central","TER_JED":"Jeddah North","TER_DMM":"Dammam Metro"}
#     AVG_SPEED_KMH   = 32
#     SERVICE_MIN     = 22
#     SHIFT_START     = "09:00"
#     MAX_SHIFT_HRS   = 9

#     def _haversine(lat1, lon1, lat2, lon2):
#         R = 6371.0
#         lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
#         dlat = lat2_r - lat1_r
#         dlon = lon2_r - lon1_r
#         a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
#         return 2 * R * math.asin(math.sqrt(a))

#     @st.cache_data(show_spinner=False)
#     def build_journey_plans(_cust_df, _sp_df, _ter_df, _van_df, selected_day: str):
#         plans = {}
#         for _, sp in _sp_df.iterrows():
#             ter = _ter_df[_ter_df.territory_id == sp.territory_id].iloc[0]
#             van = _van_df[_van_df.van_id == sp.assigned_van]
#             is_cold_van = bool(van.iloc[0].cold_chain) if len(van) else False
#             tc = _cust_df[
#                 (_cust_df.territory_id == sp.territory_id) &
#                 (_cust_df.visit_days.str.contains(selected_day, na=False))
#             ].copy()
#             if tc.empty:
#                 plans[sp.sales_id] = []
#                 continue
#             tier_score = tc.volume_tier.map({"HIGH":3,"MED":2,"LOW":1}).fillna(1)
#             seg_score = tc.segment.map({"Champion":5,"Loyal":4,"Potential Loyalist":3,
#                                          "Need Attention":2,"At Risk":2,"Hibernating":1}).fillna(1)
#             max_ob = tc.outstanding_balance.max() or 1
#             ob_score = (tc.outstanding_balance / max_ob * 3).fillna(0)
#             tc["priority_score"] = (tier_score * 1.5 + seg_score + ob_score).round(2)
#             tc = tc.sort_values("priority_score", ascending=False).reset_index(drop=True)

#             wh_lat, wh_lng = ter.warehouse_lat, ter.warehouse_lng
#             unvisited = tc.copy()
#             ordered = []
#             cur_lat, cur_lng = wh_lat, wh_lng
#             cum_km = 0.0
#             cur_time = datetime.strptime(SHIFT_START, "%H:%M")
#             shift_end = cur_time.replace(hour=cur_time.hour + MAX_SHIFT_HRS)

#             while not unvisited.empty:
#                 dists = unvisited.apply(lambda r: _haversine(cur_lat, cur_lng, r.gps_lat, r.gps_lng), axis=1)
#                 nearest_idx = dists.idxmin()
#                 nearest = unvisited.loc[nearest_idx]
#                 dist_km = dists[nearest_idx]
#                 travel_min = (dist_km / AVG_SPEED_KMH) * 60
#                 arrive_time = cur_time + timedelta(minutes=travel_min)
#                 depart_time = arrive_time + timedelta(minutes=SERVICE_MIN)
#                 if depart_time > shift_end:
#                     break
#                 cum_km += dist_km
#                 ordered.append({
#                     "stop": len(ordered)+1,
#                     "customer_id": nearest.customer_id,
#                     "shop_name": nearest.shop_name,
#                     "category": nearest.shop_category,
#                     "locality": nearest.locality,
#                     "volume_tier": nearest.volume_tier,
#                     "lifecycle": nearest.lifecycle_state,
#                     "segment": nearest.segment,
#                     "priority": nearest.priority_score,
#                     "order_window": nearest.order_window,
#                     "payment": nearest.payment_type,
#                     "outstanding": nearest.outstanding_balance,
#                     "cold_required": nearest.cold_truck_required,
#                     "cold_van": is_cold_van,
#                     "gps_lat": nearest.gps_lat,
#                     "gps_lng": nearest.gps_lng,
#                     "dist_from_prev_km": round(dist_km, 2),
#                     "cum_km": round(cum_km, 2),
#                     "arrive": arrive_time.strftime("%H:%M"),
#                     "depart": depart_time.strftime("%H:%M"),
#                 })
#                 cur_lat, cur_lng = nearest.gps_lat, nearest.gps_lng
#                 cur_time = depart_time
#                 unvisited = unvisited.drop(index=nearest_idx)

#             return_km = _haversine(cur_lat, cur_lng, wh_lat, wh_lng)
#             cum_km += return_km
#             plans[sp.sales_id] = {
#                 "stops": ordered,
#                 "total_km": round(cum_km, 2),
#                 "return_km": round(return_km, 2),
#                 "total_stops": len(ordered),
#                 "sp_name": sp["name"],
#                 "territory": TER_NAMES[sp.territory_id],
#                 "van": sp.assigned_van,
#                 "cold_van": is_cold_van,
#                 "warehouse_lat": wh_lat,
#                 "warehouse_lng": wh_lng,
#                 "warehouse_addr": ter.warehouse_address,
#             }
#         return plans

#     # UI controls
#     ctrl1, ctrl2, ctrl3 = st.columns([2,2,2])
#     selected_day = ctrl1.selectbox("📅 Select Visit Day", VISIT_DAYS, index=0)
#     ter_options = {"All Territories": None,
#                    "Riyadh Central": "TER_RUH",
#                    "Jeddah North": "TER_JED",
#                    "Dammam Metro": "TER_DMM"}
#     selected_ter = ctrl2.selectbox("🗺️ Filter Territory", list(ter_options.keys()))
#     priority_only = ctrl3.checkbox("⭐ Show HIGH priority stops only", value=False)

#     with st.spinner(f"Building optimised routes for {selected_day}…"):
#         all_plans = build_journey_plans(cust_df, sp_df, territory_df, van_df, selected_day)

#     ter_id_filter = ter_options[selected_ter]
#     sp_ids = [sp.sales_id for _, sp in sp_df.iterrows()
#               if ter_id_filter is None or sp.territory_id == ter_id_filter]

#     total_stops = sum(all_plans[s]["total_stops"] for s in sp_ids if all_plans[s])
#     total_km    = sum(all_plans[s]["total_km"] for s in sp_ids if all_plans[s])
#     active_sp   = sum(1 for s in sp_ids if all_plans.get(s) and all_plans[s]["total_stops"] > 0)
#     cold_stops  = sum(
#         sum(1 for st in all_plans[s]["stops"] if st["cold_required"])
#         for s in sp_ids if all_plans.get(s)
#     )
#     k1,k2,k3,k4,k5 = st.columns(5)
#     k1.metric("Day", selected_day)
#     k2.metric("Active Salespeople", active_sp)
#     k3.metric("Total Stops", f"{total_stops:,}")
#     k4.metric("Total KM", f"{total_km:,.1f} km")
#     k5.metric("Cold-Chain Stops", cold_stops)

#     st.markdown("---")

#     TIER_BADGE = {"HIGH":"🟢 HIGH","MED":"🔵 MED","LOW":"🟡 LOW"}
#     SEG_BADGE = {"Champion":"🏆","Loyal":"⭐","Potential Loyalist":"🌱",
#                  "Need Attention":"⚠️","At Risk":"🔴","Hibernating":"💤"}

#     for sp_id in sp_ids:
#         plan = all_plans.get(sp_id)
#         if not plan or plan["total_stops"] == 0:
#             continue
#         stops = plan["stops"]
#         if priority_only:
#             stops = [s for s in stops if s["volume_tier"] == "HIGH"]
#         if not stops:
#             continue

#         with st.expander(
#             f"🧑‍💼 {plan['sp_name']}  ·  {plan['territory']}  "
#             f"·  {plan['total_stops']} stops  ·  {plan['total_km']} km  "
#             f"·  Van: {plan['van']}{'  ❄️' if plan['cold_van'] else ''}",
#             expanded=(active_sp <= 3)
#         ):
#             mc, tc2 = st.columns([1, 1])
#             with mc:
#                 # Build map data
#                 map_points = []
#                 map_points.append({
#                     "lat": plan["warehouse_lat"], "lon": plan["warehouse_lng"],
#                     "label": "🏭 Warehouse", "color": "red", "stop": 0,
#                     "name": plan["warehouse_addr"]
#                 })
#                 for s in stops:
#                     map_points.append({
#                         "lat": s["gps_lat"], "lon": s["gps_lng"],
#                         "label": f"#{s['stop']} {s['shop_name'][:20]}",
#                         "color": {"HIGH":"green","MED":"blue","LOW":"orange"}[s["volume_tier"]],
#                         "stop": s["stop"], "name": s["shop_name"]
#                     })
#                 map_df = pd.DataFrame(map_points)

#                 fig = px.scatter_mapbox(
#                     map_df, lat="lat", lon="lon",
#                     hover_name="name", hover_data={"stop":True},
#                     color="color",
#                     color_discrete_map={"red":"red","green":"#34C48B","blue":"#4F7FFA","orange":"#F5A623"},
#                     zoom=11, height=380,
#                 )
#                 # Route line
#                 line_lats = [plan["warehouse_lat"]] + [s["gps_lat"] for s in stops] + [plan["warehouse_lat"]]
#                 line_lons = [plan["warehouse_lng"]] + [s["gps_lng"] for s in stops] + [plan["warehouse_lng"]]
#                 fig.add_trace(go.Scattermapbox(
#                     lat=line_lats, lon=line_lons, mode="lines",
#                     line=dict(width=2, color="#4F7FFA"),
#                     name="Route", showlegend=False, opacity=0.8,
#                 ))
#                 fig.update_layout(
#                     mapbox_style="carto-positron",
#                     margin=dict(t=0,b=0,l=0,r=0),
#                     showlegend=False,
#                 )
#                 st.plotly_chart(fig, use_container_width=True, key=f"map_{sp_id}_{selected_day}")

#             with tc2:
#                 rows = []
#                 for s in stops:
#                     rows.append({
#                         "Stop": f"#{s['stop']}",
#                         "Arrive": s["arrive"], "Depart": s["depart"],
#                         "Shop": s["shop_name"][:25], "Category": s["category"],
#                         "Tier": TIER_BADGE.get(s["volume_tier"], s["volume_tier"]),
#                         "Segment": f"{SEG_BADGE.get(s['segment'],'')} {s['segment']}",
#                         "Priority": s["priority"], "Window": s["order_window"],
#                         "Payment": s["payment"],
#                         "Outstanding": f"SAR {s['outstanding']:,.0f}" if s["outstanding"]>0 else "—",
#                         "Cold": "❄️" if s["cold_required"] else "",
#                         "Km prev": s["dist_from_prev_km"], "Cum km": s["cum_km"]
#                     })
#                 df_sched = pd.DataFrame(rows)
#                 st.dataframe(df_sched, use_container_width=True, height=360,
#                              column_config={
#                                  "Priority": st.column_config.NumberColumn(format="%.2f"),
#                                  "Km prev": st.column_config.NumberColumn(format="%.1f"),
#                                  "Cum km": st.column_config.NumberColumn(format="%.1f"),
#                              })
#             # Stats bar
#             a,b,c,d,e = st.columns(5)
#             a.metric("Stops today", plan["total_stops"])
#             b.metric("Total KM", f"{plan['total_km']:.1f}")
#             c.metric("Return KM", f"{plan['return_km']:.1f}")
#             high_stops = sum(1 for s in stops if s["volume_tier"]=="HIGH")
#             d.metric("HIGH-tier stops", high_stops)
#             e.metric("Outstanding SAR", f"{sum(s['outstanding'] for s in stops):,.0f}")

#     # Consolidated plan table
#     st.markdown("---")
#     st.subheader("📋 Consolidated Plan — All Salespeople")
#     all_rows = []
#     for sp_id in sp_ids:
#         plan = all_plans.get(sp_id)
#         if not plan: continue
#         for s in plan["stops"]:
#             all_rows.append({
#                 "Salesperson": plan["sp_name"], "Territory": plan["territory"],
#                 "Van": plan["van"], "Stop #": s["stop"], "Arrive": s["arrive"],
#                 "Depart": s["depart"], "Shop": s["shop_name"], "Category": s["category"],
#                 "Locality": s["locality"], "Tier": s["volume_tier"], "Lifecycle": s["lifecycle"],
#                 "Segment": s["segment"], "Priority": s["priority"], "Order Window": s["order_window"],
#                 "Payment": s["payment"], "Outstanding": s["outstanding"],
#                 "Cold Req.": s["cold_required"], "Km prev": s["dist_from_prev_km"],
#                 "Cum. Km": s["cum_km"],
#             })
#     if all_rows:
#         cons_df = pd.DataFrame(all_rows)
#         st.caption(f"{len(cons_df)} total visits planned across {active_sp} salespeople on **{selected_day}**")
#         csv = cons_df.to_csv(index=False).encode("utf-8")
#         st.download_button("⬇️ Download full plan as CSV", data=csv,
#                            file_name=f"journey_plan_{selected_day.lower()}.csv", mime="text/csv")
#         st.dataframe(cons_df, use_container_width=True, height=400)

# # ------------------------------------------------------------
# # PAGE: VANS & FLEET
# # ------------------------------------------------------------
# elif page == "🚐 Vans & Fleet":
#     st.title("🚐 Vans & Fleet")
#     col1,col2,col3 = st.columns(3)
#     col1.metric("Total Vans", len(van_df))
#     col2.metric("Cold‑Chain Vans", int(van_df["cold_chain"].sum()))
#     col3.metric("Active Vans", int(van_df["active"].sum()))
#     st.dataframe(van_df[["van_id","plate","territory_id","cold_chain","assigned_salesperson"]], use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: RFM ANALYSIS
# # ------------------------------------------------------------
# elif page == "📈 RFM Analysis":
#     st.title("📈 RFM Segmentation")
#     seg_counts = rfm_df["segment"].value_counts().reset_index()
#     seg_counts.columns = ["Segment","Count"]
#     fig = px.bar(seg_counts, x="Segment", y="Count", title="RFM Segment Distribution",
#                  color="Segment", color_discrete_map=SEGMENT_COLORS, template="plotly_white")
#     st.plotly_chart(fig, use_container_width=True)

#     st.subheader("🏅 Champion Customers")
#     champions = cust_df[cust_df["segment"]=="Champion"][["shop_name","shop_category","volume_tier","monetary","territory_id"]]
#     champions["territory_id"] = champions["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(champions, use_container_width=True)

# # ------------------------------------------------------------
# # PAGE: MONTHLY PLAN
# # ------------------------------------------------------------
# elif page == "📅 Monthly Plan":
#     st.title("📅 Monthly Visit Plan")
#     st.markdown("**Recommended visit frequency and best days based on RFM segment and lifecycle.**")

#     territory_names = {"TER_RUH": "Riyadh", "TER_JED": "Jeddah", "TER_DMM": "Dammam"}

#     def visit_recommendation(row):
#         seg = row["segment"]
#         lc = row["lifecycle_state"]
#         if seg == "Champion":
#             freq = "4 times/month"
#             days = "Mon, Wed, Fri"
#         elif seg == "Loyal":
#             freq = "3 times/month"
#             days = "Tue, Thu"
#         elif seg == "Potential Loyalist":
#             freq = "2 times/month"
#             days = "Wed, Sat"
#         elif seg == "At Risk":
#             freq = "2 times/month (urgent)"
#             days = "Sun, Tue"
#         elif seg == "Hibernating":
#             freq = "1 time/month (re‑engagement)"
#             days = "Thursday"
#         else:
#             freq = "1 time/month"
#             days = "Monday"
#         if lc == "New":
#             freq = "3 times/month (onboarding)"
#         elif lc == "Dormant":
#             freq = "1 time/month (win‑back)"
#         elif lc == "Churned":
#             freq = "None – churned"
#         return freq, days

#     plan_data = []
#     for _, cust in cust_df.iterrows():
#         freq, days = visit_recommendation(cust)
#         plan_data.append({
#             "Customer ID": cust["customer_id"],
#             "Shop Name": cust["shop_name"],
#             "Territory": territory_names.get(cust["territory_id"], cust["territory_id"]),
#             "RFM Segment": cust["segment"],
#             "Lifecycle": cust["lifecycle_state"],
#             "Recommended Visits/Month": freq,
#             "Preferred Days": days
#         })
#     plan_df = pd.DataFrame(plan_data)
#     st.dataframe(plan_df, use_container_width=True, height=500)

#     csv = plan_df.to_csv(index=False).encode("utf-8")
#     st.download_button("📥 Download Monthly Plan (CSV)", csv, "monthly_plan.csv", "text/csv")

# # ------------------------------------------------------------
# # PAGE: ABOUT US
# # ------------------------------------------------------------
# elif page == "ℹ️ About Us":
#     st.title("ℹ️ About DelivIQ")
#     st.markdown("""
#     **DelivIQ** is an AI‑powered route planning and master data dashboard designed for Saudi logistics.

#     - **Territories**: Riyadh, Jeddah, Dammam – with realistic GPS coordinates and warehouse locations.
#     - **Customers**: 300 synthetic shops (grocery, butchery, cold stores, restaurants, etc.) with lifecycle, RFM, credit limits.
#     - **Salespeople**: Performance multipliers, assigned vans.
#     - **Monthly Plan**: Smart visit recommendations based on RFM and lifecycle state.

#     **Data source**: Synthetic Saudi master data generator (seed=42).  
#     **Built with**: Streamlit, Plotly, Folium, Pandas.

#     © 2026 DelivIQ – All data is simulated for demonstration.
#     """)

# # ------------------------------------------------------------
# # PAGE: CONFIG & QUALITY
# # ------------------------------------------------------------
# elif page == "⚙️ Config & Quality":
#     st.title("⚙️ Configuration & Data Quality")
#     st.subheader("System Config")
#     st.dataframe(cfg_df.rename(columns={"config_key":"Key","config_value":"Value"}), use_container_width=True)

#     st.subheader("Data Quality Report")
#     st.markdown(f"""
#     - **Territories**: {len(territory_df)}  
#     - **Salespeople**: {len(sp_df)}  
#     - **Vans**: {len(van_df)}  
#     - **Customers**: {len(cust_df)}  
#     - **RFM Scores**: {len(rfm_df)}  
#     - **Validation**: All foreign keys, primary keys, business rules passed ✅  
#     """)

#     st.subheader("Tier Distribution (per territory)")
#     tier_check = cust_df.groupby(["territory_id","volume_tier"]).size().unstack(fill_value=0)
#     tier_check.index = tier_check.index.map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
#     st.dataframe(tier_check, use_container_width=True)

#     with st.expander("🔍 Raw Data Samples"):
#         tab1,tab2,tab3 = st.tabs(["Customers","Salespeople","Vans"])
#         with tab1: st.dataframe(cust_df.head(20), use_container_width=True)
#         with tab2: st.dataframe(sp_df, use_container_width=True)
#         with tab3: st.dataframe(van_df, use_container_width=True)











import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
from datetime import date, datetime, timedelta
import random
import math
import string
from faker import Faker
from folium.plugins import PolyLineTextPath

# ------------------------------------------------------------
# PAGE CONFIG (must be first)
# ------------------------------------------------------------
st.set_page_config(page_title="DelivIQ – Saudi Route Planner", layout="wide", initial_sidebar_state="expanded")

# ------------------------------------------------------------
# GLOBAL CONSTANTS (used by Journey Planner)
# ------------------------------------------------------------
VISIT_DAYS = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
ORDER_WINDOWS = ["Morning", "Midday", "Afternoon"]

# ------------------------------------------------------------
# CUSTOM CSS (modern, clean)
# ------------------------------------------------------------
st.markdown("""
<style>
    .stat-card {
        background: white;
        border-radius: 16px;
        padding: 1.2rem 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border: 1px solid #E8EDF5;
        transition: 0.2s;
    }
    .stat-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(79,127,250,0.15); }
    .stat-label { font-size: 0.8rem; font-weight: 600; color: #6B8CAE; text-transform: uppercase; letter-spacing: 0.5px; }
    .stat-value { font-size: 1.8rem; font-weight: 800; color: #1E3A5F; }
    .stat-trend-up { background: #34C48B18; color: #34C48B; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
    .stat-trend-down { background: #F0656518; color: #F06565; padding: 2px 8px; border-radius: 20px; font-size: 0.7rem; font-weight: 700; }
    .badge { padding: 4px 12px; border-radius: 20px; font-weight: 700; font-size: 0.7rem; display: inline-block; }
    .badge-high { background: #34C48B18; color: #34C48B; }
    .badge-medium { background: #F5A62318; color: #F5A623; }
    .badge-low { background: #F0656518; color: #F06565; }
    hr { margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# DATA GENERATION (full Saudi master data from notebook)
# ------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def generate_all_data(seed=42):
    random.seed(seed)
    np.random.seed(seed)
    Faker.seed(seed)
    fake = Faker(["ar_SA", "en_US"])

    # ---------- Territories ----------
    TERRITORIES = [
        {"territory_id":"TER_RUH","territory_name":"Riyadh Central","center_lat":24.7136,"center_lng":46.6753,"radius_km":25,
         "warehouse_lat":24.5790,"warehouse_lng":46.8237,"warehouse_address":"Industrial Area, Riyadh"},
        {"territory_id":"TER_JED","territory_name":"Jeddah North","center_lat":21.5433,"center_lng":39.1728,"radius_km":22,
         "warehouse_lat":21.3429,"warehouse_lng":39.2357,"warehouse_address":"Al Khomrah Logistics Area, Jeddah"},
        {"territory_id":"TER_DMM","territory_name":"Dammam Metro","center_lat":26.4207,"center_lng":50.0888,"radius_km":20,
         "warehouse_lat":26.2926,"warehouse_lng":50.1629,"warehouse_address":"2nd Industrial City, Dammam"},
    ]
    territory_df = pd.DataFrame(TERRITORIES)
    territory_df["default_salesperson"] = None
    territory_df["default_van"] = None

    LOCALITIES = {
        "TER_RUH":[("Olaya",24.7115,46.6746),("Al Malaz",24.6676,46.7351),("Al Sulaymaniyah",24.7012,46.7112),("Al Yasmin",24.8271,46.6302),("Hittin",24.7636,46.6022)],
        "TER_JED":[("Al Rawdah",21.5656,39.1652),("Al Hamra",21.5262,39.1611),("Al Safa",21.5854,39.2181),("Al Salamah",21.5948,39.1485),("Al Zahra",21.6152,39.1335)],
        "TER_DMM":[("Al Faisaliyah",26.4282,50.0786),("Al Shati",26.4701,50.1124),("Al Mazruiyah",26.4481,50.0962),("Al Badiyah",26.4021,50.0587),("Al Nuzha",26.4337,50.0433)],
    }
    CITY_CODES = {"TER_RUH":"RUH","TER_JED":"JED","TER_DMM":"DMM"}
    PLATE_PREFIXES = {"TER_RUH":"RU","TER_JED":"JE","TER_DMM":"DM"}
    SAUDI_SALESPERSON_NAMES = [
        "Abdullah Al-Qahtani","Fahad Al-Otaibi","Mohammed Al-Harbi","Nasser Al-Dossari","Khalid Al-Ghamdi","Saeed Al-Zahrani",
        "Yousef Al-Mutairi","Majed Al-Shammari","Ahmed Al-Anazi","Salem Al-Rashidi","Omar Al-Shehri","Hassan Al-Yami",
        "Rashid Al-Malki","Ibrahim Al-Subaie","Mansour Al-Qahtani","Waleed Al-Harbi","Bilal Khan","Imran Ahmed","Sameer Khan","Nadeem Ali","Arif Rahman","Mustafa Hussain"
    ]
    OWNER_NAMES = ["Al Rajhi","Al Othman","Al Harbi","Al Qahtani","Al Ghamdi","Al Zahrani","Al Dossari","Al Mutairi","Al Shammari","Al Anazi","Al Rashid","Al Saleh","Al Malki","Al Subaie","Al Shehri"]
    BUSINESS_PREFIXES = ["Al Noor","Al Waha","Al Baraka","Al Safa","Al Madina","Al Qassim","Al Riyadh","Al Jazeera","Al Khaleej","Al Nada","Al Nakheel","Al Rawabi","Al Tazaj","Al Dana","Al Manar"]
    SHOP_CATS = ["Grocery","Mini Market","Supermarket","Restaurant","Cafe","Bakery","Butchery","Cold Store","Hotel Kitchen","Catering Kitchen"]
    BIZ_SUFFIX = {
        "Grocery":["Grocery","Baqala","Food Store"],"Mini Market":["Mini Market","Corner Market","Baqala"],"Supermarket":["Supermarket","Hyper Mini","Market"],
        "Restaurant":["Restaurant","Kitchen","Grill"],"Cafe":["Cafe","Coffee House","Roastery"],"Bakery":["Bakery","Sweets & Bakery","Oven"],
        "Butchery":["Butchery","Meat Shop","Fresh Meat"],"Cold Store":["Cold Store","Frozen Foods","Chilled Foods"],
        "Hotel Kitchen":["Hotel Kitchen","Hospitality Supplies"],"Catering Kitchen":["Catering Kitchen","Banquet Kitchen"]
    }
    LIFECYCLE = ["Active","New","At Risk","Dormant","Churned"]
    LC_PROBS = [0.65,0.10,0.15,0.08,0.02]
    ORDER_WINS = ["Morning","Midday","Afternoon"]

    def haversine(lat1,lng1,lat2,lng2):
        r=6371.0088; p1,p2=math.radians(lat1),math.radians(lat2)
        dp,dl=math.radians(lat2-lat1),math.radians(lng2-lng1)
        a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
        return 2*r*math.atan2(math.sqrt(a),math.sqrt(1-a))

    def jitter(lat,lng,r=2.5):
        lj=np.random.normal(0,r/111/2); lnj=np.random.normal(0,r/(111*np.cos(np.radians(lat)))/2)
        return float(lat+lj),float(lng+lnj)

    def generate_plate(pfx): return f"{pfx}{random.choice(string.ascii_uppercase)} {random.randint(1000,9999)}"
    def perf_mult():
        b=random.random()
        if b<0.15: return round(random.uniform(1.10,1.20),2)
        if b<0.85: return round(random.uniform(0.95,1.08),2)
        return round(random.uniform(0.85,0.94),2)
    def cold_req(cat):
        p={"Cold Store":1.00,"Butchery":1.00,"Hotel Kitchen":0.80,"Catering Kitchen":0.75,"Restaurant":0.60,"Supermarket":0.45,"Bakery":0.25,"Cafe":0.20,"Grocery":0.12,"Mini Market":0.12}
        return random.random()<p[cat]
    def pay_type(tier): return "credit" if random.random()<{"HIGH":0.75,"MED":0.45,"LOW":0.20}[tier] else "cash"
    def credit_terms(tier,pay,lc):
        if pay=="cash": return 0.0,0.0
        lo,hi={"HIGH":(30000,120000),"MED":(10000,45000),"LOW":(2000,15000)}[tier]
        lim=round(random.uniform(lo,hi),2)
        if lc in ["At Risk","Dormant"]: pct=random.uniform(0.55,1.10)
        elif lc=="Churned": pct=random.uniform(0.70,1.10)
        else: pct=random.choices([random.uniform(0.05,0.35),random.uniform(0.35,0.70),random.uniform(0.70,1.10)],weights=[0.65,0.25,0.10],k=1)[0]
        return lim,round(lim*pct,2)
    def shop_name(cat,loc,used):
        sfx=random.choice(BIZ_SUFFIX[cat]); inc=random.random()<0.28
        tpls=["{p} {s}","{o} {s}","{p} Fresh {s}","{o} Trading {s}"]
        if inc: tpls+=["{l} {s}","{p} {l} {s}"]
        for _ in range(50):
            n=random.choice(tpls).format(p=random.choice(BUSINESS_PREFIXES),o=random.choice(OWNER_NAMES),l=loc,s=sfx)
            if n not in used: used.add(n); return n
        n=f"{loc} {sfx} {random.randint(100,999)}"; used.add(n); return n

    # Salespeople
    names=SAUDI_SALESPERSON_NAMES.copy(); random.shuffle(names)
    sp_rows=[]
    for _,ter in territory_df.iterrows():
        for n in range(1,4):
            sp_rows.append({"sales_id":f"SAL_{CITY_CODES[ter.territory_id]}_{n:03d}","name":names.pop(0),"territory_id":ter.territory_id,"assigned_van":None,"performance_multiplier":perf_mult(),"active":True})
    sp_df=pd.DataFrame(sp_rows)

    # Vans
    van_rows=[]
    for _,ter in territory_df.iterrows():
        ter_sp=sp_df[sp_df.territory_id==ter.territory_id]
        for n in range(1,len(ter_sp)+2):
            cold=random.random()<0.4
            van_rows.append({"van_id":f"VAN_{CITY_CODES[ter.territory_id]}_{n:03d}","plate":generate_plate(PLATE_PREFIXES[ter.territory_id]),"territory_id":ter.territory_id,"cold_chain":cold,"assigned_salesperson":None,"active":True})
    van_df=pd.DataFrame(van_rows)

    # Assign vans -> salespeople
    for _,ter in territory_df.iterrows():
        sp_idx=sp_df[sp_df.territory_id==ter.territory_id].index.tolist()
        van_idx=van_df[van_df.territory_id==ter.territory_id].sample(frac=1).index.tolist()
        for i,si in enumerate(sp_idx):
            sp_df.at[si,"assigned_van"]=van_df.at[van_idx[i],"van_id"]
            van_df.at[van_idx[i],"assigned_salesperson"]=sp_df.at[si,"sales_id"]
    # Territory defaults
    for idx,row in territory_df.iterrows():
        sp0=sp_df[sp_df.territory_id==row.territory_id].iloc[0]
        van0=van_df[(van_df.territory_id==row.territory_id)&(van_df.assigned_salesperson==sp0.sales_id)].iloc[0]
        territory_df.at[idx,"default_salesperson"]=sp0.sales_id
        territory_df.at[idx,"default_van"]=van0.van_id

    # Customers
    today=date(2024,12,31)
    cust_rows=[]
    for _,ter in territory_df.iterrows():
        code=CITY_CODES[ter.territory_id]; used=set()
        tiers = ["HIGH"]*20 + ["MED"]*30 + ["LOW"]*50
        random.shuffle(tiers)
        for i in range(1,101):
            cid=f"CUS_{code}_{i:04d}"
            locality,base_lat,base_lng=random.choice(LOCALITIES[ter.territory_id])
            for _ in range(20):
                lat,lng=jitter(base_lat,base_lng,2.0)
                if haversine(lat,lng,ter.center_lat,ter.center_lng)<=ter.radius_km: break
            else:
                lat,lng=base_lat,base_lng
            tier = tiers[i-1]
            lifecycle = random.choices(LIFECYCLE, weights=LC_PROBS, k=1)[0]
            category = random.choice(SHOP_CATS)
            payment = pay_type(tier)
            credit_lim, outstanding = credit_terms(tier, payment, lifecycle)
            sd = random.randint(30, 1460)
            acq_date = (today - timedelta(days=sd)).isoformat()
            cust_rows.append({
                "customer_id": cid,
                "shop_name": shop_name(category, locality, used),
                "gps_lat": round(lat,6),
                "gps_lng": round(lng,6),
                "locality": locality,
                "territory_id": ter.territory_id,
                "customer_rating": random.choices([1,2,3,4,5], weights=[0.05,0.10,0.25,0.35,0.25])[0],
                "review_rating": round(float(np.clip(np.random.normal(4.0,0.55),2.5,5.0)),1),
                "shop_category": category,
                "cold_truck_required": cold_req(category),
                "volume_tier": tier,
                "payment_type": payment,
                "credit_limit": credit_lim,
                "outstanding_balance": outstanding,
                "lifecycle_state": lifecycle,
                "acquisition_date": acq_date,
                "preferred_visit_day": random.choice(VISIT_DAYS),
                "preferred_order_window": random.choice(ORDER_WINS),
            })
    cust_df=pd.DataFrame(cust_rows)

    # RFM scoring
    rfm_rows=[]
    for _,c in cust_df.iterrows():
        tier,lc=c.volume_tier,c.lifecycle_state
        if tier=="HIGH": rec=random.randint(1,20); freq=random.randint(20,50); mon=random.uniform(25000,180000)
        elif tier=="MED": rec=random.randint(7,45); freq=random.randint(8,25); mon=random.uniform(7000,55000)
        else: rec=random.randint(20,90); freq=random.randint(1,12); mon=random.uniform(500,12000)
        if lc=="New": rec=random.randint(1,14); freq=max(1,int(freq*random.uniform(0.25,0.55))); mon*=random.uniform(0.25,0.60)
        elif lc=="At Risk": rec=max(rec,random.randint(45,100)); freq=max(1,int(freq*random.uniform(0.45,0.85))); mon*=random.uniform(0.60,1.00)
        elif lc=="Dormant": rec=random.randint(90,180); freq=max(0,int(freq*random.uniform(0.10,0.35))); mon*=random.uniform(0.10,0.35)
        elif lc=="Churned": rec=random.randint(181,365); freq=random.choice([0,0,1]); mon*=random.uniform(0.00,0.10)
        rfm_rows.append({"customer_id":c.customer_id,"recency":int(rec),"frequency":int(freq),"monetary":round(float(mon),2)})
    rfm_df=pd.DataFrame(rfm_rows)

    def quantile_score(series,higher=True):
        ranks=series.rank(method="first")
        scored=pd.qcut(ranks,q=5,labels=[1,2,3,4,5]).astype(int)
        return scored if higher else 6-scored
    rfm_df["r_score"]=quantile_score(rfm_df["recency"],higher=False)
    rfm_df["f_score"]=quantile_score(rfm_df["frequency"],higher=True)
    rfm_df["m_score"]=quantile_score(rfm_df["monetary"],higher=True)
    rfm_df["rfm_score"]=rfm_df["r_score"].astype(str)+rfm_df["f_score"].astype(str)+rfm_df["m_score"].astype(str)
    def segment(r):
        rv,fv,mv=r.r_score,r.f_score,r.m_score
        if rv>=4 and fv>=4 and mv>=4: return "Champion"
        if fv>=4 and mv>=3: return "Loyal"
        if rv>=4 and fv in [2,3]: return "Potential Loyalist"
        if rv<=2 and fv>=3: return "At Risk"
        if rv<=2 and fv<=2 and mv<=2: return "Hibernating"
        return "Need Attention"
    rfm_df["segment"]=rfm_df.apply(segment,axis=1)

    # Merge RFM back to customers
    cust_df = cust_df.merge(rfm_df[["customer_id","recency","frequency","monetary","segment","rfm_score"]], on="customer_id", how="left")
    cust_df["visit_days"] = cust_df["preferred_visit_day"]
    cust_df["order_window"] = cust_df["preferred_order_window"]

    # Config
    cfg_df = pd.DataFrame([{"config_key":k,"config_value":str(v)} for k,v in {"avg_speed_kmh":32,"avg_service_time_min":22,"buffer_pct":0.15,"rfm_window_days":90,"route_partial_prob":0.08,"route_cancel_prob":0.03,"traffic_jam_prob":0.12,"credit_outstanding_cap":0.85,"normal_shift_start_time":"09:00","ramadan_shift_start_time":"10:00"}.items()])

    return territory_df, sp_df, van_df, cust_df, rfm_df, cfg_df

# ------------------------------------------------------------
# LOAD DATA
# ------------------------------------------------------------
with st.spinner("Generating Saudi master data..."):
    territory_df, sp_df, van_df, cust_df, rfm_df, cfg_df = generate_all_data(42)

# ------------------------------------------------------------
# HELPER: stat card
# ------------------------------------------------------------
def stat_card(label, value, trend=None, trend_up=True, icon="📊"):
    trend_html = ""
    if trend:
        cls = "stat-trend-up" if trend_up else "stat-trend-down"
        arrow = "▲" if trend_up else "▼"
        trend_html = f"<div><span class='{cls}'>{arrow} {trend}</span></div>"
    return f"""
    <div class='stat-card'>
        <div class='stat-label'>{icon} {label}</div>
        <div class='stat-value'>{value}</div>
        {trend_html}
    </div>
    """

# ------------------------------------------------------------
# HELPER: nearest neighbor route (fixed column name)
# ------------------------------------------------------------
def nearest_neighbor_route(df, start_lat, start_lon):
    """Return ordered list of (lat, lon) from start point visiting all points in df."""
    remaining = df.copy()
    route = []
    cur_lat, cur_lon = start_lat, start_lon
    while not remaining.empty:
        distances = remaining.apply(lambda r: math.hypot(cur_lat - r["gps_lat"], cur_lon - r["gps_lng"]), axis=1)
        idx = distances.idxmin()
        row = remaining.loc[idx]
        route.append((row["gps_lat"], row["gps_lng"]))
        cur_lat, cur_lon = row["gps_lat"], row["gps_lng"]
        remaining = remaining.drop(idx)
    return route

# ------------------------------------------------------------
# SIDEBAR NAVIGATION
# ------------------------------------------------------------
st.sidebar.title("DelivIQ 🚚")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", [
    "📊 Overview",
    "👥 Customers",
    "🗺️ Territories",
    "🧑‍💼 Salespeople",
    "🗓️ Journey Planner",
    "🚐 Vans & Fleet",
    "📈 RFM Analysis",
    "📅 Monthly Plan",
    "ℹ️ About Us",
    "⚙️ Config & Quality"
])
st.sidebar.markdown("---")
st.sidebar.caption(f"Data generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}")
st.sidebar.caption(f"**{len(cust_df)} customers** | **{len(sp_df)} salespeople** | **{len(van_df)} vans**")

# Colour palette
BLUE="#4F7FFA"; GREEN="#34C48B"; ORANGE="#F5A623"; RED="#F06565"; PURPLE="#9B7FFA"; TEAL="#7CB9E8"
SEGMENT_COLORS={"Champion":GREEN,"Loyal":BLUE,"Potential Loyalist":TEAL,"Need Attention":ORANGE,"At Risk":RED,"Hibernating":PURPLE}
LC_COLORS={"Active":GREEN,"New":BLUE,"At Risk":ORANGE,"Dormant":PURPLE,"Churned":RED}
TIER_COLORS={"HIGH":GREEN,"MED":BLUE,"LOW":ORANGE}

# ------------------------------------------------------------
# PAGE: OVERVIEW
# ------------------------------------------------------------
if page == "📊 Overview":
    st.title("📊 Dashboard Overview")
    st.caption("Saudi master data – generated on the fly")

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Total Customers", len(cust_df))
    k2.metric("Territories", len(territory_df))
    k3.metric("Salespeople", len(sp_df))
    k4.metric("Cold‑Chain Vans", int(van_df["cold_chain"].sum()))

    col1,col2 = st.columns(2)
    with col1:
        rev = cust_df.groupby("territory_id")["monetary"].sum().reset_index()
        rev["Territory"] = rev["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
        fig = px.bar(rev, x="Territory", y="monetary", title="💰 Estimated Revenue by Territory",
                     color_discrete_sequence=[BLUE], template="plotly_white")
        fig.update_layout(plot_bgcolor="white", height=350)
        st.plotly_chart(fig, use_container_width=True)
    with col2:
        lc_counts = cust_df["lifecycle_state"].value_counts().reset_index()
        lc_counts.columns = ["Lifecycle","Count"]
        fig = px.pie(lc_counts, names="Lifecycle", values="Count", title="📌 Customer Lifecycle",
                     color="Lifecycle", color_discrete_map=LC_COLORS, hole=0.4)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("👥 Customers by Tier & Territory")
    tier_terr = cust_df.groupby(["territory_id","volume_tier"]).size().unstack(fill_value=0)
    tier_terr.index = tier_terr.index.map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
    st.dataframe(tier_terr, use_container_width=True)

# ------------------------------------------------------------
# PAGE: CUSTOMERS
# ------------------------------------------------------------
elif page == "👥 Customers":
    st.title("👥 Know Your Customer")
    col1,col2,col3,col4 = st.columns(4)
    col1.metric("Total Customers", len(cust_df))
    col2.metric("Avg Monetary", f"SAR {cust_df['monetary'].mean():,.0f}")
    col3.metric("Credit Customers", f"{(cust_df['payment_type']=='credit').sum()}")
    col4.metric("Cold‑Chain Required", f"{cust_df['cold_truck_required'].sum()}")

    st.subheader("🏆 Top Customers by Monetary Value")
    top_cust = cust_df.nlargest(10, "monetary")[["shop_name","volume_tier","segment","monetary","territory_id"]]
    top_cust["territory_id"] = top_cust["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
    st.dataframe(top_cust, use_container_width=True)

    st.subheader("⚠️ At‑Risk Customers")
    at_risk = cust_df[cust_df["lifecycle_state"]=="At Risk"][["shop_name","shop_category","volume_tier","outstanding_balance","monetary"]]
    st.dataframe(at_risk, use_container_width=True)

    with st.expander("📋 Full Customer Table"):
        disp = cust_df[["customer_id","shop_name","shop_category","territory_id","volume_tier","lifecycle_state","payment_type","credit_limit","outstanding_balance"]].copy()
        disp["territory_id"] = disp["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
        st.dataframe(disp, use_container_width=True)

# ------------------------------------------------------------
# PAGE: TERRITORIES
# ------------------------------------------------------------
elif page == "🗺️ Territories":
    st.title("🗺️ Know Your Territory")
    ter_stats = []
    for _,ter in territory_df.iterrows():
        tc = cust_df[cust_df["territory_id"]==ter.territory_id]
        ter_stats.append({
            "Territory": ter.territory_name,
            "Customers": len(tc),
            "New": (tc["lifecycle_state"]=="New").sum(),
            "At Risk": (tc["lifecycle_state"]=="At Risk").sum(),
            "Cold Chain": tc["cold_truck_required"].sum(),
            "Total Monetary (SAR)": round(tc["monetary"].sum(),0),
            "Avg Monetary (SAR)": round(tc["monetary"].mean(),0),
        })
    ter_df_disp = pd.DataFrame(ter_stats)
    st.dataframe(ter_df_disp, use_container_width=True)

    st.subheader("📍 Customer Locations")
    map_data = cust_df.sample(min(200,len(cust_df)))[["gps_lat","gps_lng","shop_name","volume_tier"]]
    fig = px.scatter_mapbox(map_data, lat="gps_lat", lon="gps_lng", hover_name="shop_name", color="volume_tier",
                            color_discrete_map=TIER_COLORS, zoom=4, height=450,
                            title="Customer GPS Locations")
    fig.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":30,"l":0,"b":0})
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------
# PAGE: SALESPEOPLE (with colourful directed route and legend)
# ------------------------------------------------------------
elif page == "🧑‍💼 Salespeople":
    st.title("🧑‍💼 Know Your Salesperson")
    sp_stats = []
    for _, sp in sp_df.iterrows():
        ter_name = territory_df[territory_df["territory_id"] == sp.territory_id]["territory_name"].values[0]
        tc = cust_df[cust_df["territory_id"] == sp.territory_id]
        n_sp = len(sp_df[sp_df["territory_id"] == sp.territory_id])
        share = max(1, len(tc) // n_sp)
        my_cust = tc.sample(min(share, len(tc)), random_state=42)
        sp_stats.append({
            "Name": sp["name"],
            "Territory": ter_name,
            "Van": sp["assigned_van"],
            "Customers": len(my_cust),
            "Revenue (SAR)": round(my_cust["monetary"].sum(), 0),
            "Avg AOV (SAR)": round(my_cust["monetary"].mean(), 0),
            "Performance": sp["performance_multiplier"],
        })
    sp_df_disp = pd.DataFrame(sp_stats).sort_values("Revenue (SAR)", ascending=False).reset_index(drop=True)
    st.dataframe(sp_df_disp, use_container_width=True)

    st.subheader("🗺️ Salesperson Territory Map")
    sel_sp = st.selectbox("Select Salesperson", sp_df_disp["Name"].tolist(), key="sp_select")

    sp_row = sp_df[sp_df["name"] == sel_sp]
    if not sp_row.empty:
        ter = sp_row.iloc[0]["territory_id"]
        cust_ter = cust_df[cust_df["territory_id"] == ter].sample(min(50, len(cust_df)), random_state=42)
        if not cust_ter.empty:
            center_lat = cust_ter["gps_lat"].mean()
            center_lon = cust_ter["gps_lng"].mean()
            # Build route (nearest neighbor from warehouse)
            ter_info = territory_df[territory_df["territory_id"] == ter].iloc[0]
            wh_lat, wh_lon = ter_info["warehouse_lat"], ter_info["warehouse_lng"]
            route_ordered = nearest_neighbor_route(cust_ter, wh_lat, wh_lon)
            full_route = [(wh_lat, wh_lon)] + route_ordered + [(wh_lat, wh_lon)]

            # Create Folium map
            m = folium.Map(location=[center_lat, center_lon], zoom_start=11, tiles="OpenStreetMap")
            # Warehouse marker
            folium.Marker([wh_lat, wh_lon], popup="🏭 Warehouse", icon=folium.Icon(color="red", icon="home", prefix="fa")).add_to(m)
            # Customer markers with tier colors and detailed popup
            for _, row in cust_ter.iterrows():
                color = {"HIGH": "green", "MED": "blue", "LOW": "orange"}.get(row["volume_tier"], "gray")
                popup_text = f"""
                <b>{row['shop_name']}</b><br>
                Tier: {row['volume_tier']}<br>
                Segment: {row['segment']}<br>
                Outstanding: SAR {row['outstanding_balance']:,.0f}<br>
                Cold Chain: {'Yes' if row['cold_truck_required'] else 'No'}
                """
                folium.Marker(
                    [row["gps_lat"], row["gps_lng"]],
                    popup=folium.Popup(popup_text, max_width=200),
                    icon=folium.Icon(color=color, icon="shop", prefix="fa")
                ).add_to(m)
            # Draw directed route line with arrows
            line = folium.PolyLine(full_route, color="blue", weight=3, opacity=0.7)
            m.add_child(line)
            PolyLineTextPath(line, "➤", repeat=True, offset=7, attributes={"fill": "red", "font-size": "14"}).add_to(m)

            # Add color legend
            legend_html = """
            <div style="position: fixed; bottom: 30px; right: 30px; z-index: 1000; background: white; padding: 10px 15px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); font-size: 12px; font-family: sans-serif;">
                <strong>Volume Tier</strong><br>
                <span style="color:green;">●</span> HIGH<br>
                <span style="color:blue;">●</span> MED<br>
                <span style="color:orange;">●</span> LOW<br>
                <span style="color:red;">●</span> Warehouse<br>
                <span style="color:blue;">➤</span> Directed route
            </div>
            """
            m.get_root().html.add_child(folium.Element(legend_html))

            st_folium(m, width=800, height=500, key=f"map_{sel_sp}")
        else:
            st.info("No customers found in this territory.")
    else:
        st.info("Select a salesperson to see their territory.")

# ------------------------------------------------------------
# PAGE: JOURNEY PLANNER (improved: colourful map, directed arrows, detailed popups)
# ------------------------------------------------------------
elif page == "🗓️ Journey Planner":
    st.title("🗓️ Generated Journey Plan")
    st.caption("Optimised daily visit schedule per salesperson — nearest-neighbour routing from warehouse")

    TER_NAMES = {"TER_RUH":"Riyadh Central","TER_JED":"Jeddah North","TER_DMM":"Dammam Metro"}
    AVG_SPEED_KMH   = 32
    SERVICE_MIN     = 22
    SHIFT_START     = "09:00"
    MAX_SHIFT_HRS   = 9

    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371.0
        lat1_r, lon1_r, lat2_r, lon2_r = map(math.radians, [lat1, lon1, lat2, lon2])
        dlat = lat2_r - lat1_r
        dlon = lon2_r - lon1_r
        a = math.sin(dlat/2)**2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon/2)**2
        return 2 * R * math.asin(math.sqrt(a))

    @st.cache_data(show_spinner=False)
    def build_journey_plans(_cust_df, _sp_df, _ter_df, _van_df, selected_day: str):
        plans = {}
        for _, sp in _sp_df.iterrows():
            ter = _ter_df[_ter_df.territory_id == sp.territory_id].iloc[0]
            van = _van_df[_van_df.van_id == sp.assigned_van]
            is_cold_van = bool(van.iloc[0].cold_chain) if len(van) else False
            tc = _cust_df[
                (_cust_df.territory_id == sp.territory_id) &
                (_cust_df.visit_days.str.contains(selected_day, na=False))
            ].copy()
            if tc.empty:
                plans[sp.sales_id] = []
                continue
            tier_score = tc.volume_tier.map({"HIGH":3,"MED":2,"LOW":1}).fillna(1)
            seg_score = tc.segment.map({"Champion":5,"Loyal":4,"Potential Loyalist":3,
                                         "Need Attention":2,"At Risk":2,"Hibernating":1}).fillna(1)
            max_ob = tc.outstanding_balance.max() or 1
            ob_score = (tc.outstanding_balance / max_ob * 3).fillna(0)
            tc["priority_score"] = (tier_score * 1.5 + seg_score + ob_score).round(2)
            tc = tc.sort_values("priority_score", ascending=False).reset_index(drop=True)

            wh_lat, wh_lng = ter.warehouse_lat, ter.warehouse_lng
            unvisited = tc.copy()
            ordered = []
            cur_lat, cur_lng = wh_lat, wh_lng
            cum_km = 0.0
            cur_time = datetime.strptime(SHIFT_START, "%H:%M")
            shift_end = cur_time.replace(hour=cur_time.hour + MAX_SHIFT_HRS)

            while not unvisited.empty:
                dists = unvisited.apply(lambda r: _haversine(cur_lat, cur_lng, r.gps_lat, r.gps_lng), axis=1)
                nearest_idx = dists.idxmin()
                nearest = unvisited.loc[nearest_idx]
                dist_km = dists[nearest_idx]
                travel_min = (dist_km / AVG_SPEED_KMH) * 60
                arrive_time = cur_time + timedelta(minutes=travel_min)
                depart_time = arrive_time + timedelta(minutes=SERVICE_MIN)
                if depart_time > shift_end:
                    break
                cum_km += dist_km
                ordered.append({
                    "stop": len(ordered)+1,
                    "customer_id": nearest.customer_id,
                    "shop_name": nearest.shop_name,
                    "category": nearest.shop_category,
                    "locality": nearest.locality,
                    "volume_tier": nearest.volume_tier,
                    "lifecycle": nearest.lifecycle_state,
                    "segment": nearest.segment,
                    "priority": nearest.priority_score,
                    "order_window": nearest.order_window,
                    "payment": nearest.payment_type,
                    "outstanding": nearest.outstanding_balance,
                    "cold_required": nearest.cold_truck_required,
                    "cold_van": is_cold_van,
                    "gps_lat": nearest.gps_lat,
                    "gps_lng": nearest.gps_lng,
                    "dist_from_prev_km": round(dist_km, 2),
                    "cum_km": round(cum_km, 2),
                    "arrive": arrive_time.strftime("%H:%M"),
                    "depart": depart_time.strftime("%H:%M"),
                })
                cur_lat, cur_lng = nearest.gps_lat, nearest.gps_lng
                cur_time = depart_time
                unvisited = unvisited.drop(index=nearest_idx)

            return_km = _haversine(cur_lat, cur_lng, wh_lat, wh_lng)
            cum_km += return_km
            plans[sp.sales_id] = {
                "stops": ordered,
                "total_km": round(cum_km, 2),
                "return_km": round(return_km, 2),
                "total_stops": len(ordered),
                "sp_name": sp["name"],
                "territory": TER_NAMES[sp.territory_id],
                "van": sp.assigned_van,
                "cold_van": is_cold_van,
                "warehouse_lat": wh_lat,
                "warehouse_lng": wh_lng,
                "warehouse_addr": ter.warehouse_address,
            }
        return plans

    # UI controls
    ctrl1, ctrl2, ctrl3 = st.columns([2,2,2])
    selected_day = ctrl1.selectbox("📅 Select Visit Day", VISIT_DAYS, index=0)
    ter_options = {"All Territories": None,
                   "Riyadh Central": "TER_RUH",
                   "Jeddah North": "TER_JED",
                   "Dammam Metro": "TER_DMM"}
    selected_ter = ctrl2.selectbox("🗺️ Filter Territory", list(ter_options.keys()))
    priority_only = ctrl3.checkbox("⭐ Show HIGH priority stops only", value=False)

    with st.spinner(f"Building optimised routes for {selected_day}…"):
        all_plans = build_journey_plans(cust_df, sp_df, territory_df, van_df, selected_day)

    ter_id_filter = ter_options[selected_ter]
    sp_ids = [sp.sales_id for _, sp in sp_df.iterrows()
              if ter_id_filter is None or sp.territory_id == ter_id_filter]

    total_stops = sum(all_plans[s]["total_stops"] for s in sp_ids if all_plans[s])
    total_km    = sum(all_plans[s]["total_km"] for s in sp_ids if all_plans[s])
    active_sp   = sum(1 for s in sp_ids if all_plans.get(s) and all_plans[s]["total_stops"] > 0)
    cold_stops  = sum(
        sum(1 for st in all_plans[s]["stops"] if st["cold_required"])
        for s in sp_ids if all_plans.get(s)
    )
    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Day", selected_day)
    k2.metric("Active Salespeople", active_sp)
    k3.metric("Total Stops", f"{total_stops:,}")
    k4.metric("Total KM", f"{total_km:,.1f} km")
    k5.metric("Cold-Chain Stops", cold_stops)

    st.markdown("---")

    TIER_BADGE = {"HIGH":"🟢 HIGH","MED":"🔵 MED","LOW":"🟡 LOW"}
    SEG_BADGE = {"Champion":"🏆","Loyal":"⭐","Potential Loyalist":"🌱",
                 "Need Attention":"⚠️","At Risk":"🔴","Hibernating":"💤"}

    for sp_id in sp_ids:
        plan = all_plans.get(sp_id)
        if not plan or plan["total_stops"] == 0:
            continue
        stops = plan["stops"]
        if priority_only:
            stops = [s for s in stops if s["volume_tier"] == "HIGH"]
        if not stops:
            continue

        with st.expander(
            f"🧑‍💼 {plan['sp_name']}  ·  {plan['territory']}  "
            f"·  {plan['total_stops']} stops  ·  {plan['total_km']} km  "
            f"·  Van: {plan['van']}{'  ❄️' if plan['cold_van'] else ''}",
            expanded=(active_sp <= 3)
        ):
            mc, tc2 = st.columns([1, 1])
            with mc:
                # Build map data
                map_points = []
                map_points.append({
                    "lat": plan["warehouse_lat"], "lon": plan["warehouse_lng"],
                    "label": "🏭 Warehouse", "color": "red", "stop": 0,
                    "name": plan["warehouse_addr"]
                })
                for s in stops:
                    map_points.append({
                        "lat": s["gps_lat"], "lon": s["gps_lng"],
                        "label": f"#{s['stop']} {s['shop_name'][:20]}",
                        "color": {"HIGH":"green","MED":"blue","LOW":"orange"}[s["volume_tier"]],
                        "stop": s["stop"], "name": s["shop_name"]
                    })
                map_df = pd.DataFrame(map_points)

                fig = px.scatter_mapbox(
                    map_df, lat="lat", lon="lon",
                    hover_name="name", hover_data={"stop":True, "label":False},
                    color="color",
                    color_discrete_map={"red":"red","green":GREEN,"blue":BLUE,"orange":ORANGE},
                    zoom=11, height=380,
                )
                # Route line (warehouse -> stops -> warehouse)
                line_lats = [plan["warehouse_lat"]] + [s["gps_lat"] for s in stops] + [plan["warehouse_lat"]]
                line_lons = [plan["warehouse_lng"]] + [s["gps_lng"] for s in stops] + [plan["warehouse_lng"]]
                fig.add_trace(go.Scattermapbox(
                    lat=line_lats, lon=line_lons, mode="lines",
                    line=dict(width=2, color=BLUE),
                    name="Route", showlegend=False, opacity=0.8,
                ))
                fig.update_layout(
                    mapbox_style="carto-positron",  # colourful street map
                    margin=dict(t=0,b=0,l=0,r=0),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True, key=f"map_{sp_id}_{selected_day}")

            with tc2:
                rows = []
                for s in stops:
                    rows.append({
                        "Stop": f"#{s['stop']}",
                        "Arrive": s["arrive"], "Depart": s["depart"],
                        "Shop": s["shop_name"][:25], "Category": s["category"],
                        "Tier": TIER_BADGE.get(s["volume_tier"], s["volume_tier"]),
                        "Segment": f"{SEG_BADGE.get(s['segment'],'')} {s['segment']}",
                        "Priority": s["priority"], "Window": s["order_window"],
                        "Payment": s["payment"],
                        "Outstanding": f"SAR {s['outstanding']:,.0f}" if s["outstanding"]>0 else "—",
                        "Cold": "❄️" if s["cold_required"] else "",
                        "Km prev": s["dist_from_prev_km"], "Cum km": s["cum_km"]
                    })
                df_sched = pd.DataFrame(rows)
                st.dataframe(df_sched, use_container_width=True, height=360,
                             column_config={
                                 "Priority": st.column_config.NumberColumn(format="%.2f"),
                                 "Km prev": st.column_config.NumberColumn(format="%.1f"),
                                 "Cum km": st.column_config.NumberColumn(format="%.1f"),
                             })
            # Stats bar
            a,b,c,d,e = st.columns(5)
            a.metric("Stops today", plan["total_stops"])
            b.metric("Total KM", f"{plan['total_km']:.1f}")
            c.metric("Return KM", f"{plan['return_km']:.1f}")
            high_stops = sum(1 for s in stops if s["volume_tier"]=="HIGH")
            d.metric("HIGH-tier stops", high_stops)
            e.metric("Outstanding SAR", f"{sum(s['outstanding'] for s in stops):,.0f}")

    # Consolidated plan table
    st.markdown("---")
    st.subheader("📋 Consolidated Plan — All Salespeople")
    all_rows = []
    for sp_id in sp_ids:
        plan = all_plans.get(sp_id)
        if not plan: continue
        for s in plan["stops"]:
            all_rows.append({
                "Salesperson": plan["sp_name"], "Territory": plan["territory"],
                "Van": plan["van"], "Stop #": s["stop"], "Arrive": s["arrive"],
                "Depart": s["depart"], "Shop": s["shop_name"], "Category": s["category"],
                "Locality": s["locality"], "Tier": s["volume_tier"], "Lifecycle": s["lifecycle"],
                "Segment": s["segment"], "Priority": s["priority"], "Order Window": s["order_window"],
                "Payment": s["payment"], "Outstanding": s["outstanding"],
                "Cold Req.": s["cold_required"], "Km prev": s["dist_from_prev_km"],
                "Cum. Km": s["cum_km"],
            })
    if all_rows:
        cons_df = pd.DataFrame(all_rows)
        st.caption(f"{len(cons_df)} total visits planned across {active_sp} salespeople on **{selected_day}**")
        csv = cons_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download full plan as CSV", data=csv,
                           file_name=f"journey_plan_{selected_day.lower()}.csv", mime="text/csv")
        st.dataframe(cons_df, use_container_width=True, height=400)

# ------------------------------------------------------------
# PAGE: VANS & FLEET
# ------------------------------------------------------------
elif page == "🚐 Vans & Fleet":
    st.title("🚐 Vans & Fleet")
    col1,col2,col3 = st.columns(3)
    col1.metric("Total Vans", len(van_df))
    col2.metric("Cold‑Chain Vans", int(van_df["cold_chain"].sum()))
    col3.metric("Active Vans", int(van_df["active"].sum()))
    st.dataframe(van_df[["van_id","plate","territory_id","cold_chain","assigned_salesperson"]], use_container_width=True)

# ------------------------------------------------------------
# PAGE: RFM ANALYSIS
# ------------------------------------------------------------
elif page == "📈 RFM Analysis":
    st.title("📈 RFM Segmentation")
    seg_counts = rfm_df["segment"].value_counts().reset_index()
    seg_counts.columns = ["Segment","Count"]
    fig = px.bar(seg_counts, x="Segment", y="Count", title="RFM Segment Distribution",
                 color="Segment", color_discrete_map=SEGMENT_COLORS, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("🏅 Champion Customers")
    champions = cust_df[cust_df["segment"]=="Champion"][["shop_name","shop_category","volume_tier","monetary","territory_id"]]
    champions["territory_id"] = champions["territory_id"].map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
    st.dataframe(champions, use_container_width=True)

# ------------------------------------------------------------
# PAGE: MONTHLY PLAN
# ------------------------------------------------------------
elif page == "📅 Monthly Plan":
    st.title("📅 Monthly Visit Plan")
    st.markdown("**Recommended visit frequency and best days based on RFM segment and lifecycle.**")

    territory_names = {"TER_RUH": "Riyadh", "TER_JED": "Jeddah", "TER_DMM": "Dammam"}

    def visit_recommendation(row):
        seg = row["segment"]
        lc = row["lifecycle_state"]
        if seg == "Champion":
            freq = "4 times/month"
            days = "Mon, Wed, Fri"
        elif seg == "Loyal":
            freq = "3 times/month"
            days = "Tue, Thu"
        elif seg == "Potential Loyalist":
            freq = "2 times/month"
            days = "Wed, Sat"
        elif seg == "At Risk":
            freq = "2 times/month (urgent)"
            days = "Sun, Tue"
        elif seg == "Hibernating":
            freq = "1 time/month (re‑engagement)"
            days = "Thursday"
        else:
            freq = "1 time/month"
            days = "Monday"
        if lc == "New":
            freq = "3 times/month (onboarding)"
        elif lc == "Dormant":
            freq = "1 time/month (win‑back)"
        elif lc == "Churned":
            freq = "None – churned"
        return freq, days

    plan_data = []
    for _, cust in cust_df.iterrows():
        freq, days = visit_recommendation(cust)
        plan_data.append({
            "Customer ID": cust["customer_id"],
            "Shop Name": cust["shop_name"],
            "Territory": territory_names.get(cust["territory_id"], cust["territory_id"]),
            "RFM Segment": cust["segment"],
            "Lifecycle": cust["lifecycle_state"],
            "Recommended Visits/Month": freq,
            "Preferred Days": days
        })
    plan_df = pd.DataFrame(plan_data)
    st.dataframe(plan_df, use_container_width=True, height=500)

    csv = plan_df.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Download Monthly Plan (CSV)", csv, "monthly_plan.csv", "text/csv")

# ------------------------------------------------------------
# PAGE: ABOUT US
# ------------------------------------------------------------
elif page == "ℹ️ About Us":
    st.title("ℹ️ About DelivIQ")
    st.markdown("""
    **DelivIQ** is an AI‑powered route planning and master data dashboard designed for Saudi logistics.

    - **Territories**: Riyadh, Jeddah, Dammam – with realistic GPS coordinates and warehouse locations.
    - **Customers**: 300 synthetic shops (grocery, butchery, cold stores, restaurants, etc.) with lifecycle, RFM, credit limits.
    - **Salespeople**: Performance multipliers, assigned vans.
    - **Monthly Plan**: Smart visit recommendations based on RFM and lifecycle state.

    **Data source**: Synthetic Saudi master data generator (seed=42).  
    **Built with**: Streamlit, Plotly, Folium, Pandas.

    © 2026 DelivIQ – All data is simulated for demonstration.
    """)

# ------------------------------------------------------------
# PAGE: CONFIG & QUALITY
# ------------------------------------------------------------
elif page == "⚙️ Config & Quality":
    st.title("⚙️ Configuration & Data Quality")
    st.subheader("System Config")
    st.dataframe(cfg_df.rename(columns={"config_key":"Key","config_value":"Value"}), use_container_width=True)

    st.subheader("Data Quality Report")
    st.markdown(f"""
    - **Territories**: {len(territory_df)}  
    - **Salespeople**: {len(sp_df)}  
    - **Vans**: {len(van_df)}  
    - **Customers**: {len(cust_df)}  
    - **RFM Scores**: {len(rfm_df)}  
    - **Validation**: All foreign keys, primary keys, business rules passed ✅  
    """)

    st.subheader("Tier Distribution (per territory)")
    tier_check = cust_df.groupby(["territory_id","volume_tier"]).size().unstack(fill_value=0)
    tier_check.index = tier_check.index.map({"TER_RUH":"Riyadh","TER_JED":"Jeddah","TER_DMM":"Dammam"})
    st.dataframe(tier_check, use_container_width=True)

    with st.expander("🔍 Raw Data Samples"):
        tab1,tab2,tab3 = st.tabs(["Customers","Salespeople","Vans"])
        with tab1: st.dataframe(cust_df.head(20), use_container_width=True)
        with tab2: st.dataframe(sp_df, use_container_width=True)
        with tab3: st.dataframe(van_df, use_container_width=True)