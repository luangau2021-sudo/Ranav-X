import streamlit as st


def load_global_styles():
    st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;600;700&display=swap');
html,body,[class*="css"]{font-family:'Be Vietnam Pro',sans-serif;}
section[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#0f2027 0%,#203a43 50%,#2c5364 100%);}
section[data-testid="stSidebar"] *{color:white!important;}
.alert-danger {background:#ff4b4b18;border-left:4px solid #ff4b4b;border-radius:8px;padding:10px 14px;margin:5px 0;}
.alert-warning{background:#ffa50018;border-left:4px solid #ffa500;border-radius:8px;padding:10px 14px;margin:5px 0;}
.alert-success{background:#21c35418;border-left:4px solid #21c354;border-radius:8px;padding:10px 14px;margin:5px 0;}
.alert-info   {background:#1a73e818;border-left:4px solid #1a73e8;border-radius:8px;padding:10px 14px;margin:5px 0;}
.step-box     {background:#f0f4ff;border-radius:8px;padding:8px 14px;margin:4px 0;
               border-left:3px solid #2a5298;font-size:.88rem;}
.summary-bar  {background:linear-gradient(90deg,#1a1a2e,#16213e);color:white;
               border-radius:10px;padding:12px 18px;margin:8px 0;font-size:.9rem;}
.legend-grad  {display:flex;align-items:center;gap:8px;font-size:.82rem;margin:6px 0;}
.grad-bar     {height:14px;width:220px;border-radius:7px;
               background:linear-gradient(to right,#1a73e8,#43a047,#fdd835,#fb8c00,#b71c1c);}
.reroute-box  {background:#fff8e1;border:2px solid #ffa500;border-radius:12px;padding:14px;margin:10px 0;}
.compare-table{width:100%;border-collapse:collapse;font-size:.88rem;margin:10px 0;}
.compare-table th{background:#1a1a2e;color:white;padding:10px 12px;text-align:center;font-weight:600;}
.compare-table td{padding:9px 12px;text-align:center;border-bottom:1px solid #e8eaf0;vertical-align:middle;}
.compare-table tr:hover td{background:#f5f7ff;}
.tag-fastest {background:#fff3e0;border:2px solid #ff9800;border-radius:20px;padding:3px 10px;font-weight:700;color:#e65100;white-space:nowrap;}
.tag-safest  {background:#e8f5e9;border:2px solid #43a047;border-radius:20px;padding:3px 10px;font-weight:700;color:#1b5e20;white-space:nowrap;}
.tag-balanced{background:#e3f2fd;border:2px solid #1976d2;border-radius:20px;padding:3px 10px;font-weight:700;color:#0d47a1;white-space:nowrap;}
.tag-other   {background:#f3f4f6;border:2px solid #9e9e9e;border-radius:20px;padding:3px 10px;font-weight:600;color:#555;white-space:nowrap;}
.risk-low    {color:#2e7d32;font-weight:700;}
.risk-mid    {color:#f57c00;font-weight:700;}
.risk-high   {color:#c62828;font-weight:700;}
.compare-winner{background:linear-gradient(90deg,#fffde7,#fff9c4);border-left:4px solid #ffc107;}
/* GPS IoT widget */
.iot-panel{border-radius:16px;padding:20px 24px;margin:10px 0;transition:all .3s;}
.iot-safe   {background:#f1f8e9;border:2.5px solid #43a047;}
.iot-warning{background:#fffde7;border:2.5px solid #f9a825;}
.iot-danger {background:#fff5f5;border:2.5px solid #e53935;}
.iot-led{width:56px;height:56px;border-radius:50%;flex-shrink:0;transition:background .4s,box-shadow .4s;}
.iot-led-safe   {background:#43a047;box-shadow:0 0 22px #43a047;}
.iot-led-warning{background:#f9a825;box-shadow:0 0 22px #f9a825;}
.iot-led-danger {background:#e53935;box-shadow:0 0 28px #e53935;}
.gps-badge{display:inline-flex;align-items:center;gap:6px;background:#e3f2fd;
           border:1.5px solid #1976d2;border-radius:20px;padding:4px 12px;font-size:.82rem;font-weight:600;}
.gps-dot{width:9px;height:9px;border-radius:50%;background:#1976d2;animation:gpspulse 1.4s infinite;}
@keyframes gpspulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(1.4)}}
</style>
""", unsafe_allow_html=True)
