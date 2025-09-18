import pandas as pd
import os

# paths
rel_path = "../data/raw/Waste_Management_and_Recycling_India.csv"
abs_path = r"C:\Users\krpra\Desktop\mini_hackatho\wmr_hackathon\data\raw\Waste_Management_and_Recycling_India.csv"
url_path = "https://raw.githubusercontent.com/MasteriNeuron/datasets/refs/heads/main/Waste_Management_and_Recycling_India.csv"

def load_data():
    if os.path.exists(rel_path):
        print("[INFO] using relative path")
        return pd.read_csv(rel_path)
    elif os.path.exists(abs_path):
        print("[INFO] using absolute path")
        return pd.read_csv(abs_path)
    else:
        print("[INFO] using URL path")
        return pd.read_csv(url_path)

if __name__ == "__main__":
    df = load_data()
    print("Shape:", df.shape)
    print("Columns:", df.columns.tolist()[:12])
    print(df.head(3))
