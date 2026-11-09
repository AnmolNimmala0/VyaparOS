import asyncio
import os
from decimal import Decimal

from pwdlib import PasswordHash
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.customer import Customer
from app.models.customer_ledger_entry import CustomerLedgerEntry
from app.models.inventory_balance import InventoryBalance
from app.models.inventory_movement import InventoryMovement
from app.models.product import Product
from app.models.product_alias import ProductAlias
from app.models.store import Store
from app.models.user import User

# ---------------------------------------------------------
# DEMO CONFIGURATION
# ---------------------------------------------------------

STORE_PHONE = "+910000000001"
OWNER_PHONE = "+910000000002"

OWNER_PASSWORD = os.getenv("DEMO_OWNER_PASSWORD", "Demo@12345")

password_hasher = PasswordHash.recommended()


# Prices are in paise. Quantities use Decimal.
PRODUCTS = [
    {
        "sku": "MAGGI-70",
        "name": "Maggi Noodles 70g",
        "description": "Instant noodles, 70 gram packet",
        "unit": "packet",
        "cost": 1200,
        "selling": 1400,
        "quantity": "40",
        "reorder": "10",
        "aliases": ["maggi", "मैगी", "maggi packet", "maggi ka packet"],
    },
    {
        "sku": "MILK-500",
        "name": "Milk 500ml",
        "description": "Toned milk, 500ml packet",
        "unit": "packet",
        "cost": 2600,
        "selling": 3000,
        "quantity": "30",
        "reorder": "10",
        "aliases": ["milk", "doodh", "दूध", "milk packet", "doodh packet"],
    },
    {
        "sku": "RICE-1KG",
        "name": "Rice 1kg",
        "description": "Regular rice",
        "unit": "kg",
        "cost": 4800,
        "selling": 6000,
        "quantity": "50",
        "reorder": "10",
        "aliases": ["rice", "chawal", "चावल", "chawal ek kilo"],
    },
    {
        "sku": "EGG-1",
        "name": "Egg",
        "description": "One egg",
        "unit": "piece",
        "cost": 500,
        "selling": 600,
        "quantity": "120",
        "reorder": "30",
        "aliases": ["egg", "anda", "अंडा", "eggs"],
    },
    {
        "sku": "BREAD-400",
        "name": "Bread",
        "description": "Regular bread loaf",
        "unit": "packet",
        "cost": 3500,
        "selling": 4000,
        "quantity": "20",
        "reorder": "5",
        "aliases": ["bread", "double roti", "ब्रेड", "bread packet"],
    },
    {
        "sku": "SUGAR-1KG",
        "name": "Sugar 1kg",
        "description": "White sugar",
        "unit": "kg",
        "cost": 4000,
        "selling": 4500,
        "quantity": "35",
        "reorder": "8",
        "aliases": ["sugar", "cheeni", "चीनी", "chini"],
    },
    {
        "sku": "ATTA-5KG",
        "name": "Wheat Flour 1kg",
        "description": "Wheat flour",
        "unit": "kg",
        "cost": 3400,
        "selling": 4200,
        "quantity": "25",
        "reorder": "5",
        "aliases": ["atta", "aata", "आटा", "wheat flour"],
    },
    {
        "sku": "OIL-1L",
        "name": "Cooking Oil 1L",
        "description": "Refined cooking oil",
        "unit": "bottle",
        "cost": 12500,
        "selling": 14000,
        "quantity": "18",
        "reorder": "5",
        "aliases": ["oil", "tel", "तेल", "cooking oil"],
    },
    {
        "sku": "BISCUIT-GLUCO",
        "name": "Glucose Biscuits",
        "description": "Glucose biscuit packet",
        "unit": "packet",
        "cost": 800,
        "selling": 1000,
        "quantity": "60",
        "reorder": "15",
        "aliases": ["biscuit", "biscuits", "glucose biscuit", "बिस्कुट"],
    },
    {
        "sku": "TEA-250",
        "name": "Tea 250g",
        "description": "Packaged tea powder",
        "unit": "packet",
        "cost": 9000,
        "selling": 10500,
        "quantity": "15",
        "reorder": "5",
        "aliases": ["tea", "chai patti", "चाय पत्ती", "chai"],
    },
    {
        "sku": "SOAP-1",
        "name": "Bathing Soap",
        "description": "Bathing soap bar",
        "unit": "piece",
        "cost": 1800,
        "selling": 2200,
        "quantity": "35",
        "reorder": "10",
        "aliases": ["soap", "sabun", "साबुन", "bath soap"],
    },
    {
        "sku": "COLA-750",
        "name": "Cold Drink 750ml",
        "description": "Carbonated soft drink",
        "unit": "bottle",
        "cost": 3500,
        "selling": 4000,
        "quantity": "24",
        "reorder": "6",
        "aliases": ["cold drink", "cola", "soft drink", "कोल्ड ड्रिंक"],
    },
    {
        "sku": "POTATO-1KG",
        "name": "Potato",
        "description": "Fresh potatoes",
        "unit": "kg",
        "cost": 2200,
        "selling": 2800,
        "quantity": "30",
        "reorder": "8",
        "aliases": ["potato", "aloo", "आलू", "alu"],
    },
    {
        "sku": "ONION-1KG",
        "name": "Onion",
        "description": "Fresh onions",
        "unit": "kg",
        "cost": 2800,
        "selling": 3500,
        "quantity": "25",
        "reorder": "8",
        "aliases": ["onion", "pyaz", "प्याज", "pyaaz"],
    },
    {
        "sku": "WATER-1L",
        "name": "Packaged Water 1L",
        "description": "One litre drinking water bottle",
        "unit": "bottle",
        "cost": 1200,
        "selling": 2000,
        "quantity": "40",
        "reorder": "10",
        "aliases": ["water", "paani", "पानी", "water bottle"],
    },
]


CUSTOMERS = [
    {
        "name": "Rahul Sharma",
        "phone": "+910000000011",
        "notes": "Regular customer",
        "credit_paise": 12500,
        "repayment_paise": 5000,
    },
    {
        "name": "Priya Verma",
        "phone": "+910000000012",
        "notes": "Nearby resident",
        "credit_paise": 8500,
        "repayment_paise": 0,
    },
    {
        "name": "Amit Kumar",
        "phone": "+910000000013",
        "notes": "Regular customer",
        "credit_paise": 0,
        "repayment_paise": 0,
    },
    {
        "name": "Neha Singh",
        "phone": "+910000000014",
        "notes": "Regular customer",
        "credit_paise": 22000,
        "repayment_paise": 10000,
    },
]


# ---------------------------------------------------------
# SEED FUNCTIONS
# ---------------------------------------------------------

async def get_or_create_store(session):
    store = await session.scalar(
        select(Store).where(Store.phone == STORE_PHONE)
    )

    if store:
        print("Store already exists.")
        return store

    store = Store(
        name="Sharma General Store",
        phone=STORE_PHONE,
        address="Jaipur, Rajasthan",
        preferred_language="hi",
    )
    session.add(store)
    await session.flush()

    print("Created demo store.")
    return store


async def get_or_create_owner(session, store):
    owner = await session.scalar(
        select(User).where(User.phone == OWNER_PHONE)
    )

    if owner:
        if owner.store_id != store.id:
            raise ValueError(
                "The demo owner phone already belongs to another store."
            )
        print("Owner already exists.")
        return owner

    owner = User(
        store_id=store.id,
        name="Demo Store Owner",
        phone=OWNER_PHONE,
        password_hash=password_hasher.hash(OWNER_PASSWORD),
        role="owner",
        is_active=True,
    )
    session.add(owner)
    await session.flush()

    print("Created demo owner.")
    return owner


async def seed_products(session, store):
    for item in PRODUCTS:
        product = await session.scalar(
            select(Product).where(
                Product.store_id == store.id,
                Product.sku == item["sku"],
            )
        )

        if not product:
            product = Product(
                store_id=store.id,
                name=item["name"],
                description=item["description"],
                sku=item["sku"],
                unit=item["unit"],
                cost_price_paise=item["cost"],
                selling_price_paise=item["selling"],
                is_active=True,
            )
            session.add(product)
            await session.flush()
            print(f"Created product: {product.name}")

        # Add aliases only if they do not already exist.
        for alias in item["aliases"]:
            normalized = alias.strip().casefold()

            existing_alias = await session.scalar(
                select(ProductAlias).where(
                    ProductAlias.store_id == store.id,
                    ProductAlias.normalized_alias == normalized,
                )
            )

            if existing_alias:
                if existing_alias.product_id != product.id:
                    raise ValueError(
                        f"Alias '{alias}' is already assigned "
                        "to a different product."
                    )
                continue

            session.add(
                ProductAlias(
                    store_id=store.id,
                    product_id=product.id,
                    alias=alias,
                    normalized_alias=normalized,
                    language="hi" if any(
                        "\u0900" <= char <= "\u097f" for char in alias
                    ) else "hinglish",
                )
            )

        # Create the opening balance once.
        balance = await session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.store_id == store.id,
                InventoryBalance.product_id == product.id,
            )
        )

        if not balance:
            opening_quantity = Decimal(item["quantity"])

            balance = InventoryBalance(
                store_id=store.id,
                product_id=product.id,
                quantity=opening_quantity,
                reorder_level=Decimal(item["reorder"]),
            )
            session.add(balance)

            # Record the corresponding opening movement.
            session.add(
                InventoryMovement(
                    store_id=store.id,
                    product_id=product.id,
                    movement_type="OPENING",
                    quantity_delta=opening_quantity,
                    note=f"DEMO_SEED:OPENING:{item['sku']}",
                )
            )
            print(f"Created opening stock: {product.name}")


async def seed_customers(session, store):
    for item in CUSTOMERS:
        customer = await session.scalar(
            select(Customer).where(
                Customer.store_id == store.id,
                Customer.phone == item["phone"],
            )
        )

        if not customer:
            customer = Customer(
                store_id=store.id,
                name=item["name"],
                phone=item["phone"],
                notes=item["notes"],
                is_active=True,
            )
            session.add(customer)
            await session.flush()
            print(f"Created customer: {customer.name}")

        # Stable notes make each ledger entry identifiable on reruns.
        credit_marker = f"DEMO_SEED:CREDIT:{item['phone']}"
        repayment_marker = f"DEMO_SEED:REPAYMENT:{item['phone']}"

        existing_credit = await session.scalar(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.store_id == store.id,
                CustomerLedgerEntry.customer_id == customer.id,
                CustomerLedgerEntry.note == credit_marker,
            )
        )

        if item["credit_paise"] > 0 and not existing_credit:
            session.add(
                CustomerLedgerEntry(
                    store_id=store.id,
                    customer_id=customer.id,
                    entry_type="CREDIT",
                    amount_paise=item["credit_paise"],
                    note=credit_marker,
                )
            )

        existing_repayment = await session.scalar(
            select(CustomerLedgerEntry).where(
                CustomerLedgerEntry.store_id == store.id,
                CustomerLedgerEntry.customer_id == customer.id,
                CustomerLedgerEntry.note == repayment_marker,
            )
        )

        if item["repayment_paise"] > 0 and not existing_repayment:
            session.add(
                CustomerLedgerEntry(
                    store_id=store.id,
                    customer_id=customer.id,
                    entry_type="REPAYMENT",
                    amount_paise=item["repayment_paise"],
                    note=repayment_marker,
                )
            )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

async def main():
    async with AsyncSessionLocal() as session, session.begin():
        store = await get_or_create_store(session)
        await get_or_create_owner(session, store)
        await seed_products(session, store)
        await seed_customers(session, store)

    print("\nDemo store seeded successfully.")
    print(f"Owner phone: {OWNER_PHONE}")
    print("Owner password: configured by DEMO_OWNER_PASSWORD or default")
    print("Products:", len(PRODUCTS))
    print("Customers:", len(CUSTOMERS))


if __name__ == "__main__":
    asyncio.run(main())