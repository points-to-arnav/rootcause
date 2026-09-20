import os
import random
import datetime
import pandas as pd

def generate_ecommerce_workbook(output_path: str):
    random.seed(101)
    
    # 1. Customers Sheet
    regions = ["North", "South", "East", "West", "Central"]
    segments = ["Consumer", "Corporate", "Home Office"]
    customers = []
    for i in range(1, 301):
        cid = f"CUST-{i:04d}"
        first_names = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth", "David", "Barbara", "Richard", "Susan"]
        last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez"]
        name = f"{random.choice(first_names)} {random.choice(last_names)}"
        customers.append({
            "customer_id": cid,
            "customer_name": name,
            "region": random.choice(regions) if random.random() > 0.03 else None,  # intentional 3% null for DQ
            "segment": random.choice(segments),
            "signup_date": (datetime.date(2025, 1, 1) + datetime.timedelta(days=random.randint(0, 365))).isoformat()
        })
    df_customers = pd.DataFrame(customers)

    # 2. Products Sheet
    categories = {
        "Technology": [
            ("MacBook Pro 16", 2499.0, 1800.0),
            ("Dell XPS 15", 1899.0, 1400.0),
            ("Wireless Noise Cancelling Headphones", 299.0, 150.0),
            ("UltraWide 34 Monitor", 799.0, 520.0),
            ("Mechanical Keyboard RGB", 149.0, 75.0),
            ("Ergonomic Wireless Mouse", 89.0, 45.0)
        ],
        "Office Supplies": [
            ("Standing Desk Converter", 349.0, 210.0),
            ("Mesh Executive Chair", 429.0, 260.0),
            ("LED Desk Lamp with Wireless Charging", 59.0, 25.0),
            ("Paper Shredder Heavy Duty", 119.0, 65.0),
            ("Document Scanner Portable", 199.0, 110.0)
        ],
        "Furniture": [
            ("Solid Oak Executive Desk", 899.0, 550.0),
            ("Ergonomic High-Back Chair", 499.0, 290.0),
            ("4-Tier Bookshelf Industrial", 189.0, 95.0),
            ("Filing Cabinet Locking", 159.0, 80.0)
        ]
    }

    products = []
    pid_counter = 1
    prod_lookup = []
    for cat, items in categories.items():
        for pname, price, cost in items:
            pid = f"PROD-{pid_counter:03d}"
            products.append({
                "product_id": pid,
                "product_name": pname,
                "category": cat,
                "unit_price": price,
                "cost_price": cost
            })
            prod_lookup.append((pid, price, cost, cat))
            pid_counter += 1
    df_products = pd.DataFrame(products)

    # 3. Orders Sheet
    start_date = datetime.date(2025, 1, 1)
    end_date = datetime.date(2026, 8, 31)
    delta_days = (end_date - start_date).days

    orders = []
    order_id = 10001
    
    for day_offset in range(delta_days + 1):
        cur_date = start_date + datetime.timedelta(days=day_offset)
        # 5 to 15 orders per day
        daily_order_count = random.randint(5, 15)
        
        # Planted drop: In August 2026, Technology in West region drops sharply
        is_aug_2026 = (cur_date.year == 2026 and cur_date.month == 8)

        for _ in range(daily_order_count):
            cust = random.choice(customers)
            pid, price, cost, cat = random.choice(prod_lookup)

            # Suppress Technology in West during August 2026
            if is_aug_2026 and cat == "Technology" and cust["region"] == "West":
                if random.random() < 0.85:
                    continue  # 85% drop in West Technology orders

            qty = random.choices([1, 2, 3, 4, 5], weights=[60, 25, 10, 3, 2])[0]
            discount = random.choice([0.0, 0.05, 0.10, 0.15]) if random.random() < 0.25 else 0.0
            sales_amt = round(qty * price * (1.0 - discount), 2)
            
            orders.append({
                "order_id": f"ORD-{order_id}",
                "order_date": cur_date.isoformat(),
                "customer_id": cust["customer_id"],
                "product_id": pid,
                "quantity": qty,
                "unit_price": price,
                "discount_pct": discount,
                "sales_amount": sales_amt,
                "payment_method": random.choice(["Credit Card", "PayPal", "Bank Transfer", "Apple Pay"])
            })
            order_id += 1

    df_orders = pd.DataFrame(orders)

    # Save to Excel
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_orders.to_excel(writer, sheet_name="Orders", index=False)
        df_customers.to_excel(writer, sheet_name="Customers", index=False)
        df_products.to_excel(writer, sheet_name="Products", index=False)

    print(f"Generated Excel workbook: {output_path} ({len(df_orders)} orders, {len(df_customers)} customers, {len(df_products)} products)")

def generate_csv_sales(output_path: str):
    random.seed(42)
    start_date = datetime.date(2026, 1, 1)
    end_date = datetime.date(2026, 8, 31)
    delta_days = (end_date - start_date).days

    cities = ["New York", "San Francisco", "London", "Tokyo", "Berlin", "Singapore"]
    categories = ["Electronics", "Fashion", "Groceries", "Books", "Home & Kitchen"]

    rows = []
    tid = 50000
    for day_offset in range(delta_days + 1):
        cur_date = start_date + datetime.timedelta(days=day_offset)
        daily_count = random.randint(8, 20)
        for _ in range(daily_count):
            cat = random.choice(categories)
            city = random.choice(cities)
            qty = random.randint(1, 5)
            base_price = {"Electronics": 250, "Fashion": 70, "Groceries": 35, "Books": 20, "Home & Kitchen": 85}[cat]
            revenue = round(qty * base_price * random.uniform(0.9, 1.2), 2)
            
            rows.append({
                "transaction_id": f"TXN-{tid}",
                "transaction_date": cur_date.isoformat(),
                "city": city,
                "product_category": cat,
                "units_sold": qty,
                "revenue": revenue,
                "customer_satisfaction": random.randint(3, 5)
            })
            tid += 1

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"Generated CSV dataset: {output_path} ({len(df)} rows)")

if __name__ == "__main__":
    generate_ecommerce_workbook("sample_orders.xlsx")
    generate_csv_sales("sample_sales.csv")
