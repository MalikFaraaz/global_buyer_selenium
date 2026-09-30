import pandas as pd
import re
import oracledb


# Oracle Connection

conn = oracledb.connect(
    user="sys",
    password="5678910",
    dsn="localhost:1521/ORCL",
    mode=oracledb.AUTH_MODE_SYSDBA
)

query = """
SELECT
buyer_id,
brand_name,
email,
website,
niche,
contact_page
FROM buyers
"""

df = pd.read_sql(query, conn)

df.columns = df.columns.str.lower()

print("Total Records:", len(df))

# ------------------------
# TEXT CLEANING FUNCTION
# ------------------------

def clean_text(text):

    if pd.isna(text):
        return ""

    text = str(text).lower()

    text = re.sub(r'[^a-zA-Z0-9 ]', ' ', text)

    text = re.sub(r'\s+', ' ', text)

    return text.strip()

# Clean Brand
df["brand_clean"] = df["brand_name"].apply(clean_text)

# Clean Niche
df["niche_clean"] = df["niche"].apply(clean_text)

# ------------------------
# EMAIL VALIDATION
# ------------------------

def valid_email(email):

    if pd.isna(email):
        return False

    email = str(email).strip()

    if "@" in email and "." in email:
        return True

    return False

df["valid_email"] = df["email"].apply(valid_email)

# ------------------------
# REMOVE DUPLICATES
# ------------------------

before = len(df)

df = df.drop_duplicates(subset=["website"])

after = len(df)

print("Duplicates Removed:", before - after)

# ------------------------
# LABEL RELEVANT BUYERS
# ------------------------

relevant_keywords = [
    "headwear",
    "clothing",
    "fashion",
    "streetwear",
    "apparel",
    "sportswear",
    "gym wear",
    "activewear",
    "cap",
    "hat",
    "hoodie",
    "t shirt",
    "jacket"
]

def label_buyer(row):

    score = 0

    niche = str(row["niche_clean"]).lower()
    brand = str(row["brand_clean"]).lower()

    if any(k in niche for k in relevant_keywords):
        score += 2

    if any(k in brand for k in relevant_keywords):
        score += 2

    if row["valid_email"]:
        score += 1

    return 1 if score >= 2 else 0

df["lead_label"] = df.apply(label_buyer, axis=1)



# ------------------------
# SAVE CLEAN FILE
# ------------------------

df.to_csv("clean_buyers.csv", index=False)

print("Clean Dataset Saved")

print(df[[
    "brand_name",
    "brand_clean",
    "email",
    "valid_email",
    "lead_label"
]].head())




df["relevance_reason"] = df["lead_label"].apply(
    lambda x: "Relevant" if x == 1 else "Not Relevant"
)

df["score_reason"] = df["valid_email"].apply(
    lambda x: "Valid Email" if x else "Invalid Email"
)



cursor = conn.cursor()

updated = 0

for _, row in df.iterrows():

    relevance_reason = "Relevant" if row["lead_label"] == 1 else "Not Relevant"

    score_reason = "Valid Email" if row["valid_email"] else "Invalid Email"

    cursor.execute("""
UPDATE buyers
SET
    is_relevant=:1,
    relevance_reason=:2,
    score_reason=:3
WHERE buyer_id=:4
""",
(
    int(row["lead_label"]),
    row["relevance_reason"],
    row["score_reason"],
    int(row["buyer_id"])
))

    updated += cursor.rowcount

conn.commit()

print("Rows Updated:", updated)

cursor.close()
conn.close()

print("Oracle Database Updated Successfully")


