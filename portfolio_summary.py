
import csv
from pathlib import Path

# Find the inventory file.
inventory_file = Path(__file__).parent / "data" / "inventory.csv"

total_invested = 0
known_cost_cards = 0
missing_cost_cards = 0

# Read each card in the inventory.
with inventory_file.open(newline="", encoding="utf-8-sig") as file:
    cards = csv.DictReader(file)

    for card in cards:
        purchase = card["purchase_total"].strip()

        if purchase:
            total_invested += float(purchase)
            known_cost_cards += 1
        else:
            missing_cost_cards += 1

# Display the results.
print("PROSPECT EDGE - PORTFOLIO SUMMARY")
print("---------------------------------")
print(f"Known purchase costs: ${total_invested:.2f}")
print(f"Cards with purchase costs: {known_cost_cards}")
print(f"Cards missing purchase costs: {missing_cost_cards}")
print()
print("Note: Grading costs and other expenses are not included yet.")
