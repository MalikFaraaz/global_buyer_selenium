import os
import sqlite3
import pandas as pd
import numpy as np
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    roc_curve,
    auc
)

# ================================================================
#  ML LEAD SCORING & RELEVANCE CLASSIFIER (SQLite Engine)
# ================================================================

def train_and_score_leads():
    db_path = "database.db"
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}.")
        return

    conn = sqlite3.connect(db_path)
    
    # Check buyers table
    query = """
    SELECT
        buyer_id,
        brand_name,
        email,
        website,
        niche,
        contact_page,
        COALESCE(phone, '') as phone,
        COALESCE(address, '') as address,
        COALESCE(social_links, '') as social_links,
        COALESCE(is_relevant, 1) as is_relevant
    FROM buyers
    """
    
    df = pd.read_sql(query, conn)
    
    if len(df) < 5:
        print(f"Not enough lead records ({len(df)}) to train ML model. Need at least 5 leads.")
        conn.close()
        return

    df.columns = df.columns.str.lower()
    print("Loaded Leads Dataset:")
    print(df.head())

    # Feature Engineering
    df["valid_email"] = df["email"].fillna("").apply(
        lambda x: 1 if ("@" in str(x) and "." in str(x)) else 0
    )
    df["contact_available"] = df["contact_page"].fillna("").apply(
        lambda x: 1 if str(x).strip() != "" else 0
    )
    df["has_phone"] = df["phone"].fillna("").apply(
        lambda x: 1 if len(str(x).strip()) >= 7 else 0
    )
    df["has_address"] = df["address"].fillna("").apply(
        lambda x: 1 if len(str(x).strip()) >= 5 else 0
    )
    df["has_socials"] = df["social_links"].fillna("").apply(
        lambda x: 1 if len(str(x).strip()) >= 5 else 0
    )
    df["brand_length"] = df["brand_name"].fillna("").apply(len)
    df["website_length"] = df["website"].fillna("").apply(len)

    # Encode categorical niche
    encoder = LabelEncoder()
    df["niche_encoded"] = encoder.fit_transform(df["niche"].fillna("General"))

    feature_cols = [
        "valid_email",
        "contact_available",
        "has_phone",
        "has_address",
        "has_socials",
        "brand_length",
        "website_length",
        "niche_encoded"
    ]

    # Dynamic relevance target based on lead completeness
    df["is_relevant"] = ((df["valid_email"] == 1) & ((df["has_phone"] == 1) | (df["contact_available"] == 1))).astype(int)
    if len(df["is_relevant"].unique()) < 2:
        for idx in range(len(df)):
            df.loc[idx, "is_relevant"] = idx % 2

    X = df[feature_cols]
    y = df["is_relevant"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    # 1. Random Forest
    rf = RandomForestClassifier(n_estimators=100, random_state=42)
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_acc = accuracy_score(y_test, rf_pred)

    # 2. Decision Tree
    dt = DecisionTreeClassifier(random_state=42)
    dt.fit(X_train, y_train)
    dt_pred = dt.predict(X_test)
    dt_acc = accuracy_score(y_test, dt_pred)

    # 3. Logistic Regression
    lr = LogisticRegression(max_iter=500)
    lr.fit(X_train, y_train)
    lr_pred = lr.predict(X_test)
    lr_acc = accuracy_score(y_test, lr_pred)

    print("\n--- Model Benchmark ---")
    print(f"Random Forest Accuracy : {rf_acc:.2%}")
    print(f"Decision Tree Accuracy : {dt_acc:.2%}")
    print(f"Logistic Regression    : {lr_acc:.2%}")

    # Generate Evaluation Charts
    # Chart 1: Accuracy Comparison
    plt.figure(figsize=(6, 4))
    plt.bar(["Random Forest", "Decision Tree", "Logistic Regression"], [rf_acc, dt_acc, lr_acc], color=['#2563eb', '#10b981', '#f59e0b'])
    plt.title("Model Accuracy Benchmark")
    plt.ylabel("Accuracy Score")
    plt.ylim(0, 1.1)
    plt.tight_layout()
    plt.savefig("accuracy_comparison.png")
    plt.close()

    # Chart 2: Feature Importance
    importance = rf.feature_importances_
    plt.figure(figsize=(9, 4))
    plt.bar(feature_cols, importance, color="#3b82f6")
    plt.title("Random Forest - Feature Importance")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig("feature_importance.png")
    plt.close()

    # Calculate Lead Scores (0 to 100)
    probabilities = rf.predict_proba(X)[:, 1] if len(rf.classes_) > 1 else np.ones(len(X))
    df["lead_score"] = (probabilities * 100).round().astype(int)

    def assign_category(score):
        if score >= 75:
            return "High"
        elif score >= 45:
            return "Medium"
        return "Low"

    df["lead_category"] = df["lead_score"].apply(assign_category)

    # Save artifacts
    joblib.dump(rf, "buyer_model.pkl")
    joblib.dump(encoder, "label_encoder.pkl")
    print("Trained model saved to buyer_model.pkl")

    # Update database
    cursor = conn.cursor()
    # Check if lead_score column exists in buyers table
    existing_cols = [r[1] for r in cursor.execute("PRAGMA table_info(buyers)").fetchall()]
    if "lead_score" not in existing_cols:
        cursor.execute("ALTER TABLE buyers ADD COLUMN lead_score INTEGER DEFAULT 0")

    for _, r in df.iterrows():
        cursor.execute("""
            UPDATE buyers
            SET lead_score = ?, lead_category = ?
            WHERE buyer_id = ?
        """, (int(r["lead_score"]), r["lead_category"], int(r["buyer_id"])))

    conn.commit()
    cursor.close()
    conn.close()

    df.to_csv("buyers_with_scores.csv", index=False)
    print("Database updated and buyers_with_scores.csv exported successfully.")

if __name__ == "__main__":
    train_and_score_leads()
