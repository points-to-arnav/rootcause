#!/usr/bin/env python3
"""
Generate sample_data/retail_demo.xlsx for AskData / RootCause.
Planted Storyline:
- Date range: 2025-01-01 to 2026-08-31.
- In August 2026, total revenue falls ~15-20% MoM.
- Driven by Electronics in West region falling ~75% due to inventory stockout (stock_on_hand=0).
- Top 5 declining products are all Electronics.

Planted Data-Quality Issues:
- ~3% of Customers have missing (NULL) region.
- ~30 duplicated Sales rows (identical or duplicate order_id).
- ~20 negative quantities in Sales.
- ~2% of order_date stored as text 'DD/MM/YYYY'.
- ~10 Sales rows with product_id not in Products table (orphan keys).
- A few outlier amounts (~10x typical).
"""

import os
import random
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np

def generate_retail_data():
    random.seed(42)
    np.random.seed(42)

    os.makedirs("sample_data", exist_ok=True)
    output_path = "sample_data/retail_demo.xlsx"

    # 1. Products (120 products)
    categories = {
        "Electronics": ["Smartphones", "Laptops", "Headphones", "Monitors", "Accessories"],
        "Home": ["Furniture", "Kitchen", "Bedding", "Lighting"],
        "Apparel": ["Men's Wear", "Women's Wear", "Footwear", "Athletic"],
        "Grocery": ["Beverages", "Snacks", "Pantry", "Organic"],
        "Sports": ["Fitness", "Outdoor", "Team Sports", "Cycling"]
    }

    products = []
    prod_id = 101
    for cat, subcats in categories.items():
        for subcat in subcats:
            count = 6 if cat == "Electronics" else 5
            for i in range(count):
                name = f"{cat[:4]}-{subcat[:4]}-{i+1:02d} {subcat[:-1] if subcat.endswith('s') else subcat}"
                cost = round(random.uniform(20.0, 500.0 if cat == "Electronics" else 150.0), 2)
                markup = random.uniform(1.3, 1.8)
                list_price = round(cost * markup, 2)
                products.append({
                    "product_id": f"P{prod_id:04d}",
                    "product_name": name,
                    "category": cat,
                    "sub_category": subcat,
                    "unit_cost": cost,
                    "list_price": list_price
                })
                prod_id += 1

    df_products = pd.DataFrame(products)

    # 2. Customers (800 customers)
    regions = ["North", "South", "East", "West"]
    cust_types = ["Retail", "Wholesale", "Corporate"]
    first_names = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
                   "Diya", "Saanvi", "Ananya", "Aadhya", "Pari", "Chiara", "Riya", "Myra", "Anvi", "Fatima",
                   "John", "Emily", "Michael", "Sarah", "David", "Jessica", "James", "Emma", "Daniel", "Olivia"]
    last_names = ["Sharma", "Verma", "Patel", "Mehta", "Singh", "Kumar", "Iyer", "Nair", "Reddy", "Gupta",
                  "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

    customers = []
    for cid in range(1, 801):
        fn = random.choice(first_names)
        ln = random.choice(last_names)
        # Plant ~3% missing regions
        region = None if random.random() < 0.03 else random.choice(regions)
        signup = date(2024, 1, 1) + timedelta(days=random.randint(0, 700))
        customers.append({
            "customer_id": f"C{cid:04d}",
            "customer_name": f"{fn} {ln}",
            "region": region,
            "customer_type": random.choice(cust_types),
            "signup_date": signup
        })

    df_customers = pd.DataFrame(customers)

    # 3. Sales (~18,000 orders spanning 2025-01-01 to 2026-08-31)
    start_date = date(2025, 1, 1)
    end_date = date(2026, 8, 31)
    total_days = (end_date - start_date).days + 1

    prod_lookup = {p["product_id"]: p for p in products}
    cust_lookup = {c["customer_id"]: c for c in customers}
    cust_ids = [c["customer_id"] for c in customers]
    prod_ids = [p["product_id"] for p in products]

    sales = []
    order_num = 10001

    # Baseline daily orders ~25-35 with slight growth
    for day_idx in range(total_days):
        dt = start_date + timedelta(days=day_idx)
        year, month = dt.year, dt.month

        # Base daily order count with mild seasonal trend
        base_count = int(24 + (day_idx / total_days) * 8 + 4 * np.sin(day_idx / 30.0))

        # August 2026 shock: West Electronics drops sharply
        is_aug_2026 = (year == 2026 and month == 8)
        if is_aug_2026:
            base_count = int(base_count * 0.90)  # Slight general cooling

        for _ in range(base_count):
            cid = random.choice(cust_ids)
            c_region = cust_lookup[cid]["region"]
            pid = random.choice(prod_ids)
            p_cat = prod_lookup[pid]["category"]

            # Plant the drop: In August 2026, if customer is West and product is Electronics, drop 95% (stockout)
            if is_aug_2026 and c_region == "West" and p_cat == "Electronics":
                if random.random() > 0.05:
                    continue  # Stockout! Skipped order

            qty = random.randint(1, 5)
            unit_price = prod_lookup[pid]["list_price"]
            discount = random.choice([0.0, 0.05, 0.10, 0.15, 0.20])
            amount = round(qty * unit_price * (1.0 - discount), 2)

            sales.append({
                "order_id": f"ORD-{order_num:06d}",
                "order_date": dt,
                "customer_id": cid,
                "product_id": pid,
                "quantity": qty,
                "unit_price": unit_price,
                "discount_pct": discount,
                "amount": amount
            })
            order_num += 1

    df_sales = pd.DataFrame(sales)

    # Apply planted data quality issues to Sales:
    # A. Plant ~20 negative quantities
    neg_indices = random.sample(range(len(df_sales)), 20)
    for idx in neg_indices:
        df_sales.at[idx, "quantity"] = -abs(df_sales.at[idx, "quantity"])

    # B. Plant ~10 orphan product IDs (not in products table)
    orphan_indices = random.sample(range(len(df_sales)), 10)
    for idx in orphan_indices:
        df_sales.at[idx, "product_id"] = "P9999"

    # C. Plant ~5 outlier amounts (~10x)
    outlier_indices = random.sample(range(len(df_sales)), 5)
    for idx in outlier_indices:
        df_sales.at[idx, "amount"] = round(df_sales.at[idx, "amount"] * 10.5, 2)

    # D. Plant ~30 duplicate rows (append duplicates of existing rows)
    dupes = df_sales.sample(30, random_state=42).copy()
    df_sales = pd.concat([df_sales, dupes], ignore_index=True)

    # E. Plant ~2% order_date stored as string 'DD/MM/YYYY'
    text_date_indices = random.sample(range(len(df_sales)), int(len(df_sales) * 0.02))
    df_sales["order_date"] = df_sales["order_date"].astype(object)
    for idx in text_date_indices:
        d_val = df_sales.at[idx, "order_date"]
        if isinstance(d_val, (date, datetime)):
            df_sales.at[idx, "order_date"] = d_val.strftime("%d/%m/%Y")

    # 4. Inventory (Monthly snapshots for all products across regions)
    inventory = []
    month_ends = pd.date_range(start="2025-01-31", end="2026-08-31", freq="ME")

    for me in month_ends:
        me_date = me.date()
        is_aug_2026_end = (me_date.year == 2026 and me_date.month == 8)

        for p in products:
            pid = p["product_id"]
            p_cat = p["category"]

            for reg in regions:
                reorder = 25
                # Stockout: West Electronics top products have stock_on_hand = 0 at August 2026 month end!
                if is_aug_2026_end and reg == "West" and p_cat == "Electronics":
                    stock = 0
                else:
                    stock = random.randint(15, 120)

                inventory.append({
                    "product_id": pid,
                    "snapshot_date": me_date,
                    "warehouse_region": reg,
                    "stock_on_hand": stock,
                    "reorder_level": reorder
                })

    df_inventory = pd.DataFrame(inventory)

    # 5. Returns (~4% of orders)
    returns = []
    return_reasons = ["Defective", "Late Delivery", "Wrong Item", "Buyer Remorse"]
    ret_id = 1
    sampled_orders = df_sales.sample(frac=0.042, random_state=42)

    for _, row in sampled_orders.iterrows():
        o_date = row["order_date"]
        if isinstance(o_date, str):
            try:
                dt_clean = datetime.strptime(o_date, "%d/%m/%Y").date()
            except Exception:
                dt_clean = date(2026, 1, 1)
        else:
            dt_clean = o_date

        ret_date = dt_clean + timedelta(days=random.randint(2, 14))
        refund = row["amount"]
        returns.append({
            "return_id": f"RET-{ret_id:05d}",
            "order_id": row["order_id"],
            "return_date": ret_date,
            "reason": random.choice(return_reasons),
            "refund_amount": refund
        })
        ret_id += 1

    df_returns = pd.DataFrame(returns)

    # Write to Excel with multiple sheets
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_sales.to_excel(writer, sheet_name="Sales", index=False)
        df_customers.to_excel(writer, sheet_name="Customers", index=False)
        df_products.to_excel(writer, sheet_name="Products", index=False)
        df_inventory.to_excel(writer, sheet_name="Inventory", index=False)
        df_returns.to_excel(writer, sheet_name="Returns", index=False)

    print(f"[OK] Generated {output_path}")
    print(f"   - Sales: {len(df_sales)} rows")
    print(f"   - Customers: {len(df_customers)} rows")
    print(f"   - Products: {len(df_products)} rows")
    print(f"   - Inventory: {len(df_inventory)} rows")
    print(f"   - Returns: {len(df_returns)} rows")

if __name__ == "__main__":
    generate_retail_data()
