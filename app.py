from flask import Flask, render_template, request, jsonify
import os
import pandas as pd
from catboost import CatBoostRegressor, Pool

# ---------------- Contacts (env-driven) ----------------
CONTACTS = []

def _add_contact(env_key, label, icon, href_prefix=""):
    v = os.getenv(env_key, "").strip()
    if not v:
        return
    href = v if v.startswith(("http://", "https://", "mailto:")) else (href_prefix + v)
    CONTACTS.append({"label": label, "href": href, "icon": icon})

_add_contact("CONTACT_GITHUB",   "GitHub",   "github")
_add_contact("CONTACT_LINKEDIN", "LinkedIn", "linkedin")
_add_contact("CONTACT_EMAIL",    "Email",    "envelope", href_prefix="mailto:")

# ---------------- App & paths ----------------
app = Flask(__name__, static_folder="static", template_folder="templates")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_CANDIDATES = [
    os.path.join(BASE_DIR, "models", "model_best_catboost.cbm"),
    os.path.join(BASE_DIR, "models", "model_catboost.cbm"),
]
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "clean_waste_mgmt.csv")

# ---------------- Lazy globals ----------------
_df = None
_cb = None
_DQ = [float("-inf"), 5000, 10000, 15000, float("inf")]  # default bins

CITIES  = ["Mumbai", "Delhi", "Bengaluru", "Chennai", "Kolkata"]
WASTE   = ["Plastic", "Organic", "E-Waste", "Construction", "Hazardous"]
METHODS = ["Recycling", "Composting", "Incineration", "Landfill"]

def load_data_and_model():
    """Lazy-load CSV + CatBoost model (fast healthz/homepage)."""
    global _df, _cb, _DQ, CITIES, WASTE, METHODS
    # data
    if _df is None and os.path.exists(DATA_PATH):
        df = pd.read_csv(DATA_PATH)
        _df = df
        if "City/District" in df:        CITIES  = sorted(df["City/District"].dropna().unique().tolist())
        if "Waste Type" in df:           WASTE   = sorted(df["Waste Type"].dropna().unique().tolist())
        if "Disposal Method" in df:      METHODS = sorted(df["Disposal Method"].dropna().unique().tolist())
        if "Population Density (People/km²)" in df:
            q = df["Population Density (People/km²)"].quantile([0.25, 0.5, 0.75]).values
            _DQ = [float("-inf"), float(q[0]), float(q[1]), float(q[2]), float("inf")]

    # model
    if _cb is None:
        mp = next((p for p in MODEL_CANDIDATES if os.path.exists(p)), None)
        if mp:
            m = CatBoostRegressor()
            m.load_model(mp)
            _cb = m

    return _df, _cb, _DQ

def density_bin(v: float) -> str:
    _, _, DQ = load_data_and_model()
    if v <= DQ[1]: return "Low"
    if v <= DQ[2]: return "Mid-Low"
    if v <= DQ[3]: return "Mid-High"
    return "High"

CAT_COLS = ["City/District","Waste Type","Disposal Method","Density_Bin","Waste_Method"]
NUM_KEEP = ["Waste Generated (Tons/Day)","Population Density (People/km²)","Municipal Efficiency Score (1-10)",
            "Cost of Waste Management (₹/Ton)","Awareness Campaigns Count","Landfill Capacity (Tons)","Year"]
ALL_COLS = CAT_COLS + NUM_KEEP

def predict_one(row: dict) -> float:
    _, cb, _ = load_data_and_model()
    if cb is None:
        raise RuntimeError("Model file not found on server. Place .cbm in models/")
    r = row.copy()
    r["Density_Bin"] = density_bin(r["Population Density (People/km²)"])
    r["Waste_Method"] = f'{r["Waste Type"]}|{r["Disposal Method"]}'
    X = pd.DataFrame([r], columns=ALL_COLS)
    pred = float(cb.predict(Pool(X, cat_features=CAT_COLS)))
    return max(0.0, min(100.0, pred))

def classify_score(p: float) -> tuple[str, str]:
    if p >= 65:  return "High", "success"
    if p >= 45:  return "Moderate", "warning"
    return "Low", "danger"

def city_avg(city: str) -> float | None:
    df, _, _ = load_data_and_model()
    if df is None: return None
    if "Recycling Rate (%)" not in df: return None
    m = df.loc[df["City/District"] == city, "Recycling Rate (%)"].mean()
    return float(m) if pd.notna(m) else None

# ---------------- Routes ----------------
@app.get("/healthz")
def healthz():
    return "ok", 200

@app.get("/")
def index():
    charts = all(os.path.exists(os.path.join(BASE_DIR,"static", f))
                 for f in ["eda_city_top10.png","eda_method.png","eda_year.png"])
    return render_template("index.html",
                           cities=CITIES, waste=WASTE, methods=METHODS,
                           charts_exist=charts, prediction=None,
                           contacts=CONTACTS)

@app.post("/predict")
def predict():
    f = request.form
    row = {
        "City/District": f.get("city") or CITIES[0],
        "Waste Type": f.get("waste_type") or WASTE[0],
        "Disposal Method": f.get("method") or METHODS[0],
        "Waste Generated (Tons/Day)": float(f.get("waste_gen", 3000)),
        "Population Density (People/km²)": float(f.get("pop_density", 10000)),
        "Municipal Efficiency Score (1-10)": float(f.get("eff_score", 7)),
        "Cost of Waste Management (₹/Ton)": float(f.get("cost", 2500)),
        "Awareness Campaigns Count": float(f.get("campaigns", 10)),
        "Landfill Capacity (Tons)": float(f.get("capacity", 60000)),
        "Year": float(f.get("year", 2021)),
    }
    try:
        pred = round(predict_one(row), 1)
        label, badge = classify_score(pred)
    except Exception as e:
        pred, label, badge = None, "Model missing", "danger"

    cavg = city_avg(row["City/District"])
    compare = {}
    for m in ["Recycling","Composting","Incineration","Landfill"]:
        r2 = row.copy(); r2["Disposal Method"] = m
        try:
            compare[m] = round(predict_one(r2), 1)
        except:
            compare[m] = None

    charts = all(os.path.exists(os.path.join(BASE_DIR,"static", f))
                 for f in ["eda_city_top10.png","eda_method.png","eda_year.png"])

    return render_template("index.html",
        cities=CITIES, waste=WASTE, methods=METHODS, charts_exist=charts,
        prediction=pred, pred_badge=badge, pred_label=label,
        city_avg=round(cavg,1) if cavg is not None else None,
        inputs=row, compare=compare,
        density_bin=density_bin(row["Population Density (People/km²)"]),
        contacts=CONTACTS
    )

@app.post("/api/predict")
def api_predict():
    data = request.get_json(force=True) or {}
    row = {
        "City/District": data.get("city") or CITIES[0],
        "Waste Type": data.get("waste_type") or WASTE[0],
        "Disposal Method": data.get("method") or METHODS[0],
        "Waste Generated (Tons/Day)": float(data.get("waste_gen", 3000)),
        "Population Density (People/km²)": float(data.get("pop_density", 10000)),
        "Municipal Efficiency Score (1-10)": float(data.get("eff_score", 7)),
        "Cost of Waste Management (₹/Ton)": float(data.get("cost", 2500)),
        "Awareness Campaigns Count": float(data.get("campaigns", 10)),
        "Landfill Capacity (Tons)": float(data.get("capacity", 60000)),
        "Year": float(data.get("year", 2021)),
    }
    try:
        pred = round(predict_one(row), 1)
        label, badge = classify_score(pred)
        d_bin = density_bin(row["Population Density (People/km²)"])
        compare = {}
        for m in ["Recycling","Composting","Incineration","Landfill"]:
            r2 = row.copy(); r2["Disposal Method"] = m
            compare[m] = round(predict_one(r2), 1)
        return jsonify({
            "prediction": pred, "label": label, "badge": badge,
            "density_bin": d_bin, "compare": compare,
            "city_avg": round(city_avg(row["City/District"]),1) if city_avg(row["City/District"]) is not None else None
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
