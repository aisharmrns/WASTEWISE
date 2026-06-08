import json
import mimetypes
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from html import escape
from textwrap import dedent

import streamlit as st
import pandas as pd

from gemini_service import (
    identify_food_with_gemini,
    generate_waste_suggestion_with_gemini
)

# =========================
# PAGE CONFIG (Cleaned Header Symbol)
# =========================
st.set_page_config(
    page_title="WasteWise",
    page_icon="⊞",
    layout="wide"
)

# =========================
# LOAD CSS
# =========================
def load_css(file_name: str):
    css_path = Path(__file__).parent / file_name
    if css_path.exists():
        st.markdown(
            f"<style>{css_path.read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True
        )
    else:
        st.sidebar.warning(f"CSS file not found: {file_name}. Using default styles.")

def render_html(html_code: str):
    """
    Render HTML safely without showing <div> tags as text.
    """
    st.markdown(
        dedent(html_code).strip(),
        unsafe_allow_html=True
    )

load_css("style.css")

# =========================
# HELPER FUNCTIONS
# =========================
def save_uploaded_image(uploaded_file, folder_name="uploaded_images") -> str:
    image_folder = Path(folder_name)
    image_folder.mkdir(exist_ok=True)

    original_name = getattr(uploaded_file, "name", "camera_image.jpg")
    file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{original_name}"
    image_path = image_folder / file_name

    with open(image_path, "wb") as file:
        file.write(uploaded_file.getbuffer())

    return str(image_path)

def estimate_cost(item_name: str, weight_kg: float) -> float:
    cost_per_kg = {
        "spinach": 6.00,
        "rice": 2.00,
        "carrot": 5.00,
        "fish": 20.00,
        "onion": 4.00,
        "chicken": 12.00,
        "beef": 25.00,
        "egg": 8.00,
        "tomato": 5.50,
        "cabbage": 4.50
    }
    item_key = item_name.lower().strip()
    rate = cost_per_kg.get(item_key, 6.00)
    return round(weight_kg * rate, 2)

def get_food_icon(item_name: str) -> str:
    """
    Returns crisp, monochromatic geometric text outlines matching an asset dashboard.
    """
    item = item_name.lower().strip()
    if "spinach" in item or "vegetable" in item: 
        return '<span style="border: 1px solid; border-radius: 4px; padding: 2px 8px; font-size: 14px;">[VEG]</span>'
    if "rice" in item: 
        return '<span style="border: 1px solid; border-radius: 50%; padding: 4px 8px; font-size: 14px;">(CARB)</span>'
    if "carrot" in item: 
        return '<span style="font-size: 18px; font-weight: 300;">▽ PRODUCT</span>'
    if "fish" in item: 
        return '<span style="letter-spacing: -1px; font-size: 14px;">&lt;══&gt; SEAFOOD</span>'
    if "onion" in item: 
        return '<span style="border: 1px solid; border-radius: 50%; padding: 6px; font-size: 14px;">○ BULB</span>'
    if "chicken" in item or "beef" in item: 
        return '<span style="border: 1px solid; padding: 2px 6px; font-size: 12px; font-weight: bold; letter-spacing: 0.05em;">PROTEIN</span>'
    if "tomato" in item: 
        return '<span style="font-size: 22px; font-weight: 100;">⊙ FRUIT</span>'
    
    return '<span style="border: 1px dashed; padding: 2px 6px; font-size: 13px;">[ITEM]</span>'

def normalize_confidence(value) -> int:
    try:
        if isinstance(value, str):
            value = value.replace("%", "").strip()
        value = int(float(value))
        return max(0, min(value, 100))
    except Exception:
        return 0

def sidebar_item(label: str, icon: str, page_name: str) -> str:
    active_class = "active" if st.session_state.page == page_name else ""
    url_page = quote(page_name)
    return f"""
    <a class="sidebar-item {active_class}" href="?page={url_page}" target="_self">
        <span class="sidebar-icon">{icon}</span>
        <span>{label}</span>
    </a>
    """

# =========================
# SESSION STATE INITIALIZATION
# =========================
if "waste_logs" not in st.session_state:
    st.session_state.waste_logs = pd.DataFrame({
        "Date": ["09 Jun", "09 Jun", "09 Jun", "09 Jun", "08 Jun", "08 Jun"],
        "Time": ["09:14", "10:32", "11:05", "13:48", "08:22", "14:10"],
        "Item": ["Spinach", "Rice", "Carrot", "Fish", "Spinach", "Onion"],
        "Weight (kg)": [2.40, 3.80, 1.20, 4.10, 1.60, 2.00],
        "Reason": ["Rotten", "Overproduced", "Expired", "Supply Waste", "Rotten", "Expired"],
        "Est. Cost (RM)": [14.40, 7.60, 6.00, 82.00, 9.60, 8.00],
        "Logged By": ["Ahmad R.", "Siti N.", "Ravi K.", "Ahmad R.", "Ahmad R.", "Siti N."],
        "AI Confidence": ["94%", "98%", "91%", "76%", "96%", "88%"]
    })

if "ai_result" not in st.session_state:
    st.session_state.ai_result = {
        "item": "Spinach",
        "category": "Leafy Vegetable",
        "confidence": 94,
        "condition": "unknown",
        "observation": "Spinach was also wasted on Monday and Thursday. Consider reducing order quantity by 30%."
    }

if "current_weight" not in st.session_state:
    st.session_state.current_weight = 2.40

# =========================
# PAGE NAVIGATION SETUP
# =========================
pages = ["Dashboard", "Log Waste", "History"]
current_page = st.query_params.get("page", "Dashboard")

if isinstance(current_page, list):
    current_page = current_page[0]

if current_page not in pages:
    current_page = "Dashboard"

st.session_state.page = current_page

# =========================
# SIDEBAR NAVIGATION
# =========================
with st.sidebar:
    render_html("""
    <div class="brand-box">
        <div class="brand-logo">★</div>
        <div class="brand-title">WasteWise</div>
        <div class="brand-subtitle">Kitchen Intelligence</div>
    </div>
    <div class="sidebar-divider"></div>
    <div class="sidebar-section-title">MONITOR</div>
    """)

    render_html(sidebar_item("Dashboard", "▦", "Dashboard"))
    render_html(sidebar_item("Log Waste", "+", "Log Waste"))
    render_html(sidebar_item("History", "↶", "History"))

    render_html("""
    <div class="sidebar-section-title">ANALYSE</div>
    <div class="sidebar-item disabled">
        <span class="sidebar-icon">▥</span>
        <span>Reports</span>
    </div>
    <div class="sidebar-item disabled">
        <span class="sidebar-icon">☼</span>
        <span>AI Insights</span>
    </div>
    <div class="sidebar-section-title">MANAGE</div>
    <div class="sidebar-item disabled">
        <span class="sidebar-icon">◇</span>
        <span>Inventory</span>
    </div>
    <div class="sidebar-item disabled">
        <span class="sidebar-icon">♧</span>
        <span>Staff</span>
    </div>
    """)

# =========================
# DASHBOARD PAGE
# =========================
if st.session_state.page == "Dashboard":
    col_title, col_button = st.columns([4, 1])

    with col_title:
        st.title("Dashboard")
        st.caption("Monday, 9 June 2025 · Kitchen Block A")

    with col_button:
        render_html("<div style='padding-top:18px;'></div>")
        if st.button("+ Log Waste", type="primary", use_container_width=True):
            st.query_params["page"] = "Log Waste"
            st.rerun()

    logs = st.session_state.waste_logs

    total_waste = logs["Weight (kg)"].sum()
    total_events = len(logs)
    top_item = logs.groupby("Item")["Weight (kg)"].sum().idxmax()
    estimated_loss = logs["Est. Cost (RM)"].sum()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        render_html(f"""
        <div class="kpi-card">
            <div class="kpi-label">Total Waste Today</div>
            <div class="kpi-value">{total_waste:.1f} <span class="unit">kg</span></div>
            <div class="badge-down">↓ 12% vs yesterday</div>
        </div>
        """)

    with col2:
        render_html(f"""
        <div class="kpi-card">
            <div class="kpi-label">Waste Events</div>
            <div class="kpi-value">{total_events}</div>
            <div class="badge-neutral">Same as yesterday</div>
        </div>
        """)

    with col3:
        render_html(f"""
        <div class="kpi-card">
            <div class="kpi-label">Top Wasted Item</div>
            <div class="kpi-value small-kpi-value">{top_item}</div>
            <div class="badge-up">3.2 kg this week</div>
        </div>
        """)

    with col4:
        render_html(f"""
        <div class="kpi-card">
            <div class="kpi-label">Est. Cost Loss</div>
            <div class="kpi-value">RM {estimated_loss:.0f}</div>
            <div class="badge-down">↓ RM 18 saved</div>
        </div>
        """)

    render_html("<div class='section-space'></div>")

    left, right = st.columns([1.3, 1], gap="large")

    with left:
        render_html("""
        <div class="card-header">
            <div class="card-title">Waste by Category — Today</div>
            <div class="card-sub">By weight (kg)</div>
        </div>
        """)

        category_data = logs.groupby("Reason")["Weight (kg)"].sum().reset_index()
        st.bar_chart(category_data, x="Reason", y="Weight (kg)", color="#97C459", height=220)

        render_html("<div class='section-space'></div>")
        render_html("""
        <div class="card-header">
            <div class="card-title">7-Day Trend</div>
            <div class="card-sub">Daily waste in kg</div>
        </div>
        """)

        trend_data = pd.DataFrame({
            "Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "Waste (kg)": [11.2, 12.5, 10.6, 14.3, 11.8, 10.9, 8.6]
        })
        st.bar_chart(trend_data, x="Day", y="Waste (kg)", color="#C0DD97", height=200)

    with right:
        render_html("""
        <div class="card-header">
            <div class="card-title">Waste Breakdown</div>
            <div class="card-sub">By reason, today</div>
        </div>
        """)

        breakdown = logs.groupby("Reason")["Weight (kg)"].sum().reset_index()
        breakdown.columns = ["Reason", "kg"]
        st.dataframe(breakdown, use_container_width=True, hide_index=True)

        render_html("<div class='section-space'></div>")
        render_html("""
        <div class="card-header">
            <div class="card-title">AI Suggestions</div>
            <div class="card-sub">Generated using Gemini</div>
        </div>
        """)

        if st.button("Generate AI Suggestions", type="primary", use_container_width=True):
            logs_text = st.session_state.waste_logs.to_string(index=False)
            with st.spinner("Generating suggestions using Gemini..."):
                st.session_state.ai_suggestion = generate_waste_suggestion_with_gemini(logs_text)

        if "ai_suggestion" in st.session_state:
            safe_suggestion = escape(st.session_state.ai_suggestion).replace("\n", "<br>")
            render_html(f"""
            <div class="ai-box">
                <b>Gemini Recommendation</b><br>
                {safe_suggestion}
            </div>
            """)
        else:
            render_html("""
            <div class="ai-box">
                <b>[Optimization] Order less spinach this week</b><br>
                Spinach wasted 3x this week — reduce by 40% to cut RM 28 in losses.
            </div>
            <div class="warning-box">
                <b>[Logistics] Check fridge temperature in Block A</b><br>
                Rotten waste up 18% — possible cold chain issue detected.
            </div>
            """)

    render_html("<div class='section-space'></div>")
    render_html("""
    <div class="card-header">
        <div class="card-title">Recent Waste Logs</div>
        <div class="card-sub">Today's entries</div>
    </div>
    """)
    st.dataframe(logs, use_container_width=True, hide_index=True)

# =========================
# LOG WASTE PAGE
# =========================
elif st.session_state.page == "Log Waste":
    st.title("Log Waste Entry")
    st.caption("Monday, 9 June 2025 · Kitchen Block A")

    render_html("""
    <div class="step-wrap">
        <div class="step-dot done">3</div>
        <div class="step-line"></div>
        <div class="step-dot done">2</div>
        <div class="step-line"></div>
        <div class="step-dot active">3</div>
        <div class="step-line"></div>
        <div class="step-dot pending">4</div>
        <div class="step-line"></div>
        <div class="step-dot pending">5</div>
    </div>
    <div class="step-labels">
        <span class="done-lbl">Camera</span>
        <span class="done-lbl">Weight</span>
        <span class="active-lbl">AI Review</span>
        <span>Reason</span>
        <span>Save</span>
    </div>
    """)

    left, right = st.columns([1, 1], gap="large")

    with left:
        render_html("""
        <div class="card-header">
            <div class="card-title">Camera / Image Input</div>
            <div class="card-sub">Upload image or capture image for Gemini detection</div>
        </div>
        """)

        input_method = st.radio("Image input method", ["Upload Image", "Use Camera"], horizontal=True)
        image_file = st.file_uploader("Upload food waste image", type=["jpg", "jpeg", "png"]) if input_method == "Upload Image" else st.camera_input("Take food waste photo")

        if image_file is None:
            render_html("""
            <div class="camera-box">
                <div>
                    <div class="camera-icon">[ SENSOR ]</div>
                    Point camera at food item<br>
                    Upload or capture image to run AI detection
                </div>
                <div class="ai-live-badge">System: Awaiting image stream...</div>
            </div>
            """)
        else:
            image_path = save_uploaded_image(image_file)
            st.session_state.current_image_path = image_path
            st.image(image_path, caption="Food waste image", use_container_width=True)

            if st.button("Run Gemini Food Identification", type="primary", use_container_width=True):
                with st.spinner("Gemini is identifying the food item..."):
                    st.session_state.ai_result = identify_food_with_gemini(image_path)
                st.success("AI identification completed.")

        render_html("<div class='section-space'></div>")
        render_html("""
        <div class="card-header">
            <div class="card-title">Scale Reading</div>
            <div class="card-sub">HX711 · Load Cell</div>
        </div>
        """)

        weight_kg = st.number_input(
            "Weight reading (kg)",
            min_value=0.00,
            max_value=100.00,
            value=float(st.session_state.current_weight),
            step=0.10
        )
        st.session_state.current_weight = weight_kg

        render_html(f"""
        <div class="scale-box">
            <div>
                <div class="scale-number">{weight_kg:.3f} <span class="scale-unit">kg</span></div>
                <div class="scale-tare">Tare: 0.000 kg</div>
            </div>
            <div class="scale-stable">STATUS: STABLE</div>
        </div>
        """)

        render_html("<div class='section-space'></div>")
        render_html("""
        <div class="card-header">
            <div class="card-title">Select Waste Reason</div>
        </div>
        """)
        
        reason = st.radio("Waste reason", ["[CAT-1] Spoilage / Rotten", "[CAT-2] Overproduced", "[CAT-3] Expired Inventory", "[CAT-4] Supply Chain Defect"], label_visibility="collapsed")

        render_html("<div class='section-space'></div>")
        render_html("""
        <div class="card-header">
            <div class="card-title">Additional Notes</div>
        </div>
        """)
        notes = st.text_area("Notes", placeholder="e.g. Found at back of fridge, expired 2 days ago", label_visibility="collapsed", height=90)

    with right:
        ai_result = st.session_state.ai_result
        detected_item = ai_result.get("item", "Unknown")
        detected_category = ai_result.get("category", "Unknown")
        confidence = normalize_confidence(ai_result.get("confidence", 0))
        condition = ai_result.get("condition", "unknown")
        observation = ai_result.get("observation", "No observation provided.")

        cost = estimate_cost(detected_item, weight_kg)
        
        icon = get_food_icon(detected_item)

        current_time = datetime.now().strftime("%I:%M %p")

        render_html(f"""
        <div class="ai-panel">
            <div class="ai-panel-top">
                <div class="card-title">AI Identification</div>
                <span class="ai-badge">{confidence}% confidence</span>
            </div>
            <div class="ai-image-box">{icon}</div>
            <div class="ai-item-name">{escape(str(detected_item))}</div>
            <div class="conf-bar-wrap">
                <div class="conf-bar">
                    <div class="conf-fill" style="width:{confidence}%;"></div>
                </div>
                <span class="conf-label">{confidence}%</span>
            </div>
            <div class="detail-row"><span class="detail-label">Category</span><span class="detail-value">{escape(str(detected_category))}</span></div>
            <div class="detail-row"><span class="detail-label">Condition</span><span class="detail-value">{escape(str(condition))}</span></div>
            <div class="detail-row"><span class="detail-label">Weight</span><span class="detail-value">{weight_kg:.3f} kg</span></div>
            <div class="detail-row"><span class="detail-label">Logged at</span><span class="detail-value mono">{current_time}</span></div>
            <div class="detail-row"><span class="detail-label">Est. cost</span><span class="detail-value">RM {cost:.2f}</span></div>
            <div class="detail-row no-border"><span class="detail-label">Staff</span><span class="detail-value">Ahmad R.</span></div>
        </div>
        """)

        render_html("<div class='section-space'></div>")
        render_html(f"""
        <div class="warning-box">
            <b>AI Observation</b><br>
            {escape(str(observation))}
        </div>
        """)

    render_html("<div class='section-space'></div>")
    col_cancel, col_save = st.columns([1, 2])

    with col_cancel:
        if st.button("&lt; Cancel", use_container_width=True):
            st.query_params["page"] = "Dashboard"
            st.rerun()

    with col_save:
        if st.button("Confirm & Save to Database", type="primary", use_container_width=True):
            clean_reason = reason.split(" ", 1)[1].replace(" / Spoiled", "")
            
            new_record = {
                "Date": datetime.now().strftime("%d %b"),
                "Time": datetime.now().strftime("%H:%M"),
                "Item": detected_item,
                "Weight (kg)": round(weight_kg, 2),
                "Reason": clean_reason,
                "Est. Cost (RM)": estimate_cost(detected_item, weight_kg),
                "Logged By": "Ahmad R.",
                "AI Confidence": f"{confidence}%"
            }

            st.session_state.waste_logs = pd.concat(
                [pd.DataFrame([new_record]), st.session_state.waste_logs],
                ignore_index=True
            )
            st.success("System: Waste transaction log finalized successfully.")

# =========================
# HISTORY PAGE
# =========================
elif st.session_state.page == "History":
    col_title, col_button = st.columns([4, 1])

    with col_title:
        st.title("Waste History")
        st.caption("Monday, 9 June 2025 · Kitchen Block A")

    with col_button:
        render_html("<div style='padding-top:18px;'></div>")
        csv = st.session_state.waste_logs.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="Export CSV Data",
            data=csv,
            file_name="wastewise_history.csv",
            mime="text/csv",
            use_container_width=True
        )

    logs = st.session_state.waste_logs

    render_html("""
    <div class="card-header">
        <div class="card-title">Waste Log History</div>
        <div class="card-sub">All logged entries · Sorted by latest</div>
    </div>
    """)

    search = st.text_input("Search item or reason", placeholder="e.g. Spinach, Rotten...")

    if search:
        filtered_logs = logs[
            logs.apply(lambda row: search.lower() in row.astype(str).str.lower().to_string(), axis=1)
        ]
    else:
        filtered_logs = logs

    st.dataframe(filtered_logs, use_container_width=True, hide_index=True)
