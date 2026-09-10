
from flask import Flask, render_template, request, redirect, session, send_from_directory
import psycopg2
import os
import random
from werkzeug.utils import secure_filename
from datetime import date


app = Flask(__name__)

app.secret_key = "stationery_secret_key"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="stationery_shop",
        user="postgres",
        password="Swarupa2005"
    )


# =========================================================
# UPLOAD SETTINGS
# =========================================================

UPLOAD_FOLDER = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "bills"
)

ALLOWED_EXTENSIONS = {
    "pdf",
    "jpg",
    "jpeg",
    "png"
}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


# =========================================================
# DATABASE CHECK / CUSTOMER COLUMNS
# =========================================================

def ensure_database_updates():
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            ALTER TABLE sales
            ADD COLUMN IF NOT EXISTS customer_name VARCHAR(150)
        """)

        cur.execute("""
            ALTER TABLE sales
            ADD COLUMN IF NOT EXISTS customer_mobile VARCHAR(15)
        """)

        conn.commit()

    except Exception:
        conn.rollback()

    finally:
        cur.close()
        conn.close()


ensure_database_updates()


# =========================================================
# LOGIN
# =========================================================

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                user_id,
                username,
                role
            FROM users
            WHERE username = %s
            AND password = %s
            """,
            (
                username,
                password
            )
        )

        user = cur.fetchone()

        cur.close()
        conn.close()

        if user:

            session["user_id"] = user[0]
            session["username"] = user[1]
            session["role"] = user[2]

            return redirect("/dashboard")

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*)
        FROM products
    """)

    total_products = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(quantity), 0)
        FROM products
    """)

    total_stock = cur.fetchone()[0]

    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM sales
        WHERE DATE(sale_date) = CURRENT_DATE
    """)

    today_sales = cur.fetchone()[0]

    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity,
            min_stock
        FROM products
        WHERE quantity <= min_stock
        ORDER BY quantity ASC, product_name ASC
    """)

    low_stock_products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "dashboard.html",
        total_products=total_products,
        total_stock=total_stock,
        today_sales=today_sales,
        low_stock_products=low_stock_products
    )


# =========================================================
# CATEGORIES
# =========================================================

@app.route("/categories", methods=["GET", "POST"])
def categories():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    message = None
    error = None

    if request.method == "POST":

        category_name = request.form.get(
            "category_name",
            ""
        ).strip()

        if not category_name:

            error = "Category name cannot be empty."

        else:

            try:

                cur.execute("""
                    SELECT category_id
                    FROM categories
                    WHERE LOWER(TRIM(category_name))
                    = LOWER(TRIM(%s))
                """, (category_name,))

                existing = cur.fetchone()

                if existing:

                    error = "This category already exists."

                else:

                    cur.execute("""
                        INSERT INTO categories
                        (
                            category_name
                        )
                        VALUES (%s)
                    """, (category_name,))

                    conn.commit()

                    message = "Category added successfully!"

            except Exception as e:

                conn.rollback()
                error = str(e)

    cur.execute("""
        SELECT
            category_id,
            category_name
        FROM categories
        ORDER BY category_id DESC
    """)

    categories_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "categories.html",
        categories=categories_list,
        message=message,
        error=error
    )


# =========================================================
# EDIT CATEGORY
# =========================================================

@app.route(
    "/edit-category/<int:category_id>",
    methods=["GET", "POST"]
)
def edit_category(category_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":

        category_name = request.form.get(
            "category_name",
            ""
        ).strip()

        if not category_name:

            cur.close()
            conn.close()

            return (
                "Category name cannot be empty.",
                400
            )

        try:

            cur.execute("""
                SELECT category_id
                FROM categories
                WHERE LOWER(TRIM(category_name))
                = LOWER(TRIM(%s))
                AND category_id != %s
            """, (
                category_name,
                category_id
            ))

            existing = cur.fetchone()

            if existing:

                cur.close()
                conn.close()

                return (
                    "This category already exists.",
                    400
                )

            cur.execute("""
                UPDATE categories
                SET category_name = %s
                WHERE category_id = %s
            """, (
                category_name,
                category_id
            ))

            conn.commit()

        except Exception as e:

            conn.rollback()

            cur.close()
            conn.close()

            return str(e), 400

        cur.close()
        conn.close()

        return redirect("/categories")

    cur.execute("""
        SELECT
            category_id,
            category_name
        FROM categories
        WHERE category_id = %s
    """, (category_id,))

    category = cur.fetchone()

    cur.close()
    conn.close()

    if category is None:
        return "Category not found", 404

    return render_template(
        "edit_category.html",
        category=category
    )


# =========================================================
# DELETE CATEGORY
# =========================================================

@app.route(
    "/delete-category/<int:category_id>",
    methods=["POST"]
)
def delete_category(category_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM categories
            WHERE category_id = %s
        """, (category_id,))

        conn.commit()

    except psycopg2.errors.ForeignKeyViolation:

        conn.rollback()

        cur.close()
        conn.close()

        return (
            "This category cannot be deleted because "
            "products are already using this category.",
            400
        )

    except Exception as e:

        conn.rollback()

        cur.close()
        conn.close()

        return str(e), 400

    cur.close()
    conn.close()

    return redirect("/categories")


# =========================================================
# PRODUCTS
# =========================================================

@app.route("/products", methods=["GET", "POST"])
def products():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    message = None
    error = None

    if request.method == "POST":

        product_name = request.form.get(
            "product_name",
            ""
        ).strip()

        category_id = request.form.get(
            "category_id"
        )

        quantity = request.form.get(
            "quantity"
        )

        purchase_price = request.form.get(
            "purchase_price"
        )

        selling_price = request.form.get(
            "selling_price"
        )

        min_stock = request.form.get(
            "min_stock"
        )

        try:

            if not product_name:

                error = "Product name cannot be empty."

            elif not category_id:

                error = "Please select a category."

            elif not quantity:

                error = "Quantity is required."

            elif not purchase_price:

                error = "Purchase price is required."

            elif not selling_price:

                error = "Selling price is required."

            elif not min_stock:

                error = "Minimum stock is required."

            elif float(quantity) < 0:

                error = "Quantity cannot be negative."

            elif float(purchase_price) < 0:

                error = "Purchase price cannot be negative."

            elif float(selling_price) < 0:

                error = "Selling price cannot be negative."

            elif float(min_stock) < 0:

                error = "Minimum stock cannot be negative."

            elif float(selling_price) < float(purchase_price):

                error = (
                    "Selling price should not be less "
                    "than purchase price."
                )

            else:

                cur.execute("""
                    INSERT INTO products
                    (
                        product_name,
                        category_id,
                        quantity,
                        purchase_price,
                        selling_price,
                        min_stock
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    product_name,
                    category_id,
                    quantity,
                    purchase_price,
                    selling_price,
                    min_stock
                ))

                conn.commit()

                message = "Product added successfully!"

        except Exception as e:

            conn.rollback()
            error = str(e)

    cur.execute("""
        SELECT
            p.product_id,
            p.product_name,
            c.category_name,
            p.quantity,
            p.purchase_price,
            p.selling_price,
            p.min_stock
        FROM products p
        LEFT JOIN categories c
            ON p.category_id = c.category_id
        ORDER BY p.product_id DESC
    """)

    products_list = cur.fetchall()

    cur.execute("""
        SELECT
            category_id,
            category_name
        FROM categories
        ORDER BY category_name
    """)

    categories_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "products.html",
        products=products_list,
        categories=categories_list,
        message=message,
        error=error
    )


# =========================================================
# EDIT PRODUCT
# =========================================================

@app.route(
    "/edit-product/<int:product_id>",
    methods=["GET", "POST"]
)
def edit_product(product_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":

        product_name = request.form.get(
            "product_name",
            ""
        ).strip()

        category_id = request.form.get(
            "category_id"
        )

        quantity = request.form.get(
            "quantity"
        )

        purchase_price = request.form.get(
            "purchase_price"
        )

        selling_price = request.form.get(
            "selling_price"
        )

        min_stock = request.form.get(
            "min_stock"
        )

        try:

            if not product_name:
                raise ValueError(
                    "Product name cannot be empty."
                )

            if not category_id:
                raise ValueError(
                    "Please select a category."
                )

            if not quantity:
                raise ValueError(
                    "Quantity is required."
                )

            if not purchase_price:
                raise ValueError(
                    "Purchase price is required."
                )

            if not selling_price:
                raise ValueError(
                    "Selling price is required."
                )

            if not min_stock:
                raise ValueError(
                    "Minimum stock is required."
                )

            if float(quantity) < 0:
                raise ValueError(
                    "Quantity cannot be negative."
                )

            if float(purchase_price) < 0:
                raise ValueError(
                    "Purchase price cannot be negative."
                )

            if float(selling_price) < float(purchase_price):
                raise ValueError(
                    "Selling price should not be less "
                    "than purchase price."
                )

            if float(min_stock) < 0:
                raise ValueError(
                    "Minimum stock cannot be negative."
                )

            cur.execute("""
                UPDATE products
                SET
                    product_name = %s,
                    category_id = %s,
                    quantity = %s,
                    purchase_price = %s,
                    selling_price = %s,
                    min_stock = %s
                WHERE product_id = %s
            """, (
                product_name,
                category_id,
                quantity,
                purchase_price,
                selling_price,
                min_stock,
                product_id
            ))

            conn.commit()

        except Exception as e:

            conn.rollback()

            cur.close()
            conn.close()

            return str(e), 400

        cur.close()
        conn.close()

        return redirect("/products")

    cur.execute("""
        SELECT
            product_id,
            product_name,
            category_id,
            quantity,
            purchase_price,
            selling_price,
            min_stock
        FROM products
        WHERE product_id = %s
    """, (product_id,))

    product = cur.fetchone()

    cur.execute("""
        SELECT
            category_id,
            category_name
        FROM categories
        ORDER BY category_name
    """)

    categories_list = cur.fetchall()

    cur.close()
    conn.close()

    if product is None:
        return "Product not found", 404

    return render_template(
        "edit_product.html",
        product=product,
        categories=categories_list
    )


# =========================================================
# DELETE PRODUCT
# =========================================================

@app.route(
    "/delete-product/<int:product_id>",
    methods=["POST"]
)
def delete_product(product_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM products
            WHERE product_id = %s
        """, (product_id,))

        conn.commit()

    except psycopg2.errors.ForeignKeyViolation:

        conn.rollback()

        cur.close()
        conn.close()

        return (
            "This product cannot be deleted because "
            "it is already used in sales, stock or purchases.",
            400
        )

    except Exception as e:

        conn.rollback()

        cur.close()
        conn.close()

        return str(e), 400

    cur.close()
    conn.close()

    return redirect("/products")


# =========================================================
# SUPPLIERS / DEALERS
# =========================================================

@app.route("/suppliers", methods=["GET", "POST"])
def suppliers():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    message = None
    error = None

    if request.method == "POST":

        supplier_name = request.form.get(
            "supplier_name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        if not supplier_name:

            error = (
                "Dealer / Supplier name "
                "cannot be empty."
            )

        elif phone and not phone.isdigit():

            error = (
                "Phone number should contain "
                "only digits."
            )

        elif phone and len(phone) != 10:

            error = (
                "Phone number must contain "
                "exactly 10 digits."
            )

        else:

            try:

                cur.execute("""
                    SELECT supplier_id
                    FROM suppliers
                    WHERE LOWER(TRIM(supplier_name))
                    = LOWER(TRIM(%s))
                """, (supplier_name,))

                existing_supplier = cur.fetchone()

                if existing_supplier:

                    error = (
                        "This dealer / supplier "
                        "already exists."
                    )

                else:

                    cur.execute("""
                        INSERT INTO suppliers
                        (
                            supplier_name,
                            phone,
                            address
                        )
                        VALUES (%s, %s, %s)
                    """, (
                        supplier_name,
                        phone if phone else None,
                        address if address else None
                    ))

                    conn.commit()

                    message = (
                        "Dealer added successfully!"
                    )

            except Exception as e:

                conn.rollback()
                error = str(e)

    cur.execute("""
        SELECT
            supplier_id,
            supplier_name,
            phone,
            address
        FROM suppliers
        ORDER BY supplier_id DESC
    """)

    suppliers_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "suppliers.html",
        suppliers=suppliers_list,
        message=message,
        error=error
    )


# =========================================================
# EDIT SUPPLIER
# =========================================================

@app.route(
    "/edit-supplier/<int:supplier_id>",
    methods=["GET", "POST"]
)
def edit_supplier(supplier_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":

        supplier_name = request.form.get(
            "supplier_name",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        address = request.form.get(
            "address",
            ""
        ).strip()

        if not supplier_name:

            cur.close()
            conn.close()

            return (
                "Dealer / Supplier name "
                "cannot be empty.",
                400
            )

        if phone and not phone.isdigit():

            cur.close()
            conn.close()

            return (
                "Phone number should contain "
                "only digits.",
                400
            )

        if phone and len(phone) != 10:

            cur.close()
            conn.close()

            return (
                "Phone number must contain "
                "exactly 10 digits.",
                400
            )

        try:

            cur.execute("""
                SELECT supplier_id
                FROM suppliers
                WHERE LOWER(TRIM(supplier_name))
                = LOWER(TRIM(%s))
                AND supplier_id != %s
            """, (
                supplier_name,
                supplier_id
            ))

            existing_supplier = cur.fetchone()

            if existing_supplier:

                cur.close()
                conn.close()

                return (
                    "This dealer / supplier "
                    "already exists.",
                    400
                )

            cur.execute("""
                UPDATE suppliers
                SET
                    supplier_name = %s,
                    phone = %s,
                    address = %s
                WHERE supplier_id = %s
            """, (
                supplier_name,
                phone if phone else None,
                address if address else None,
                supplier_id
            ))

            conn.commit()

        except Exception as e:

            conn.rollback()

            cur.close()
            conn.close()

            return str(e), 400

        cur.close()
        conn.close()

        return redirect("/suppliers")

    cur.execute("""
        SELECT
            supplier_id,
            supplier_name,
            phone,
            address
        FROM suppliers
        WHERE supplier_id = %s
    """, (supplier_id,))

    supplier = cur.fetchone()

    cur.close()
    conn.close()

    if supplier is None:

        return (
            "Dealer / Supplier not found.",
            404
        )

    return render_template(
        "edit_supplier.html",
        supplier=supplier
    )


# =========================================================
# DELETE SUPPLIER
# =========================================================

@app.route(
    "/delete-supplier/<int:supplier_id>",
    methods=["POST"]
)
def delete_supplier(supplier_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            DELETE FROM suppliers
            WHERE supplier_id = %s
        """, (supplier_id,))

        conn.commit()

    except psycopg2.errors.ForeignKeyViolation:

        conn.rollback()

        cur.close()
        conn.close()

        return (
            "This dealer cannot be deleted because "
            "it is already used in Stock In, "
            "Dealer Purchases or Orders.",
            400
        )

    except Exception as e:

        conn.rollback()

        cur.close()
        conn.close()

        return str(e), 400

    cur.close()
    conn.close()

    return redirect("/suppliers")


# =========================================================
# STOCK IN
# =========================================================

@app.route("/stock-in", methods=["GET", "POST"])
def stock_in():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    selected_product_id = request.args.get(
        "product_id"
    )

    message = None
    error = None

    if request.method == "POST":

        product_id = request.form.get(
            "product_id"
        )

        supplier_id = request.form.get(
            "supplier_id"
        )

        quantity = request.form.get(
            "quantity"
        )

        purchase_price = request.form.get(
            "purchase_price"
        )

        try:

            if not product_id:
                raise ValueError(
                    "Please select a product."
                )

            if not supplier_id:
                raise ValueError(
                    "Please select a supplier."
                )

            if not quantity:
                raise ValueError(
                    "Quantity is required."
                )

            if not purchase_price:
                raise ValueError(
                    "Purchase price is required."
                )

            quantity_value = int(quantity)

            purchase_price_value = float(
                purchase_price
            )

            if quantity_value <= 0:
                raise ValueError(
                    "Quantity must be greater than 0."
                )

            if purchase_price_value < 0:
                raise ValueError(
                    "Purchase price cannot be negative."
                )

            cur.execute("""
                SELECT product_id
                FROM products
                WHERE product_id = %s
            """, (product_id,))

            product_exists = cur.fetchone()

            if not product_exists:

                raise ValueError(
                    "Selected product not found."
                )

            cur.execute("""
                INSERT INTO stock_in
                (
                    product_id,
                    supplier_id,
                    quantity,
                    purchase_price
                )
                VALUES (%s, %s, %s, %s)
            """, (
                product_id,
                supplier_id,
                quantity_value,
                purchase_price_value
            ))

            cur.execute("""
                UPDATE products
                SET
                    quantity = quantity + %s,
                    purchase_price = %s
                WHERE product_id = %s
            """, (
                quantity_value,
                purchase_price_value,
                product_id
            ))

            conn.commit()

            message = "Stock added successfully!"

        except Exception as e:

            conn.rollback()
            error = str(e)

    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity
        FROM products
        ORDER BY product_name
    """)

    products_list = cur.fetchall()

    cur.execute("""
        SELECT
            supplier_id,
            supplier_name
        FROM suppliers
        ORDER BY supplier_name
    """)

    suppliers_list = cur.fetchall()

    cur.execute("""
        SELECT
            si.stock_in_id,
            p.product_name,
            COALESCE(s.supplier_name, 'N/A'),
            si.quantity,
            si.purchase_price,
            si.stock_in_date
        FROM stock_in si
        JOIN products p
            ON si.product_id = p.product_id
        LEFT JOIN suppliers s
            ON si.supplier_id = s.supplier_id
        ORDER BY si.stock_in_id DESC
    """)

    stock_records = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "stock_in.html",
        products=products_list,
        suppliers=suppliers_list,
        stock_records=stock_records,
        selected_product_id=selected_product_id,
        message=message,
        error=error
    )


# =========================================================
# SALES / BILLING
# =========================================================

@app.route("/sales", methods=["GET", "POST"])
def sales():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    message = None
    error = None
    sale_id = None

    if request.method == "POST":

        product_ids = request.form.getlist(
            "product_id"
        )

        quantities = request.form.getlist(
            "quantity"
        )

        payment_method = request.form.get(
            "payment_method",
            "Cash"
        )

        customer_name = request.form.get(
            "customer_name",
            ""
        ).strip()

        customer_mobile = request.form.get(
            "customer_mobile",
            ""
        ).strip()

        if customer_mobile:

            if (
                not customer_mobile.isdigit()
                or len(customer_mobile) != 10
            ):

                return render_template(
                    "sales.html",
                    products=[],
                    sales_history=[],
                    message=None,
                    error="Customer mobile must contain exactly 10 digits.",
                    sale_id=None
                )

        items = []

        try:

            for i in range(
                len(product_ids)
            ):

                if (
                    product_ids[i]
                    and quantities[i]
                ):

                    quantity_value = int(
                        quantities[i]
                    )

                    if quantity_value <= 0:

                        raise ValueError(
                            "Quantity must be greater than 0."
                        )

                    items.append({
                        "product_id": int(
                            product_ids[i]
                        ),
                        "quantity": quantity_value
                    })

            if not items:

                raise ValueError(
                    "Please add at least one product."
                )

            total_amount = 0

            sale_items = []

            for item in items:

                product_id = item["product_id"]
                quantity = item["quantity"]

                cur.execute("""
                    SELECT
                        product_name,
                        quantity,
                        purchase_price,
                        selling_price
                    FROM products
                    WHERE product_id = %s
                    FOR UPDATE
                """, (product_id,))

                product = cur.fetchone()

                if product is None:

                    raise ValueError(
                        "Product not found."
                    )

                product_name = product[0]

                available_stock = product[1]

                purchase_price = product[2]

                selling_price = product[3]

                if quantity > available_stock:

                    raise ValueError(
                        f"{product_name}: Only "
                        f"{available_stock} items "
                        f"available in stock."
                    )

                item_total = (
                    quantity * selling_price
                )

                total_amount += item_total

                sale_items.append({
                    "product_id": product_id,
                    "product_name": product_name,
                    "quantity": quantity,
                    "selling_price": selling_price,
                    "purchase_price": purchase_price
                })

            cur.execute("""
                INSERT INTO sales
                (
                    total_amount,
                    payment_method,
                    customer_name,
                    customer_mobile
                )
                VALUES (%s, %s, %s, %s)
                RETURNING sale_id
            """, (
                total_amount,
                payment_method,
                customer_name if customer_name else None,
                customer_mobile if customer_mobile else None
            ))

            sale_id = cur.fetchone()[0]

            for item in sale_items:

                cur.execute("""
                    INSERT INTO sale_details
                    (
                        sale_id,
                        product_id,
                        quantity,
                        selling_price,
                        purchase_price
                    )
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    sale_id,
                    item["product_id"],
                    item["quantity"],
                    item["selling_price"],
                    item["purchase_price"]
                ))

                cur.execute("""
                    UPDATE products
                    SET quantity = quantity - %s
                    WHERE product_id = %s
                """, (
                    item["quantity"],
                    item["product_id"]
                ))

            conn.commit()

            message = (
                f"Sale successful! "
                f"Bill #{sale_id} "
                f"= ₹{total_amount:.2f}"
            )

        except Exception as e:

            conn.rollback()

            error = str(e)
            sale_id = None

    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity,
            purchase_price,
            selling_price
        FROM products
        ORDER BY product_name
    """)

    products_list = cur.fetchall()

    cur.execute("""
        SELECT
            sale_id,
            sale_date,
            total_amount,
            payment_method,
            customer_name,
            customer_mobile
        FROM sales
        ORDER BY sale_id DESC
        LIMIT 20
    """)

    sales_history = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "sales.html",
        products=products_list,
        sales_history=sales_history,
        message=message,
        error=error,
        sale_id=sale_id
    )


# =========================================================
# PRINT BILL
# =========================================================

@app.route("/print_bill/<int:sale_id>")
def print_bill(sale_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            sale_id,
            sale_date,
            total_amount,
            payment_method,
            customer_name,
            customer_mobile
        FROM sales
        WHERE sale_id = %s
    """, (sale_id,))

    sale = cur.fetchone()

    if sale is None:

        cur.close()
        conn.close()

        return "Bill not found", 404

    cur.execute("""
        SELECT
            p.product_name,
            sd.quantity,
            sd.selling_price,
            (
                sd.quantity * sd.selling_price
            ) AS item_total
        FROM sale_details sd
        JOIN products p
            ON sd.product_id = p.product_id
        WHERE sd.sale_id = %s
        ORDER BY sd.sale_detail_id
    """, (sale_id,))

    sale_items = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "print_bill.html",
        sale=sale,
        sale_items=sale_items
    )


# =========================================================
# DEALER PURCHASES
# =========================================================

@app.route(
    "/dealer-purchases",
    methods=["GET", "POST"]
)
def dealer_purchases():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    message = None
    error = None

    if request.method == "POST":

        saved_bill_filename = None

        try:

            supplier_id = request.form.get(
                "supplier_id"
            )

            bill_number = request.form.get(
                "bill_number",
                ""
            ).strip()

            bill_date = request.form.get(
                "bill_date"
            )

            stock_received_date = request.form.get(
                "stock_received_date"
            )

            amount_paid_text = request.form.get(
                "amount_paid",
                "0"
            ).strip()

            payment_date = request.form.get(
                "payment_date"
            ) or None

            payment_method = request.form.get(
                "payment_method",
                ""
            ).strip()

            payment_reference = request.form.get(
                "payment_reference",
                ""
            ).strip()

            notes = request.form.get(
                "notes",
                ""
            ).strip()

            if not supplier_id:

                raise ValueError(
                    "Please select a dealer / supplier."
                )

            if not bill_number:

                raise ValueError(
                    "Bill number cannot be empty."
                )

            if not bill_date:

                raise ValueError(
                    "Please select bill date."
                )

            if not stock_received_date:

                raise ValueError(
                    "Please select stock received date."
                )

            try:

                amount_paid = float(
                    amount_paid_text or 0
                )

            except ValueError:

                raise ValueError(
                    "Amount paid must be a valid number."
                )

            if amount_paid < 0:

                raise ValueError(
                    "Amount paid cannot be negative."
                )

            product_ids = request.form.getlist(
                "product_id"
            )

            quantities = request.form.getlist(
                "quantity"
            )

            purchase_prices = request.form.getlist(
                "purchase_price"
            )

            purchase_items = []

            total_amount = 0

            for i in range(
                len(product_ids)
            ):

                product_id = product_ids[i].strip()

                quantity_text = quantities[i].strip()

                price_text = purchase_prices[i].strip()

                if not product_id:
                    continue

                if not quantity_text:

                    raise ValueError(
                        "Quantity is required for "
                        "every selected product."
                    )

                if not price_text:

                    raise ValueError(
                        "Purchase price is required for "
                        "every selected product."
                    )

                try:

                    quantity = int(
                        quantity_text
                    )

                except ValueError:

                    raise ValueError(
                        "Quantity must be a valid number."
                    )

                try:

                    purchase_price = float(
                        price_text
                    )

                except ValueError:

                    raise ValueError(
                        "Purchase price must be "
                        "a valid number."
                    )

                if quantity <= 0:

                    raise ValueError(
                        "Quantity must be greater than 0."
                    )

                if purchase_price < 0:

                    raise ValueError(
                        "Purchase price cannot be negative."
                    )

                cur.execute("""
                    SELECT product_name
                    FROM products
                    WHERE product_id = %s
                """, (product_id,))

                product = cur.fetchone()

                if product is None:

                    raise ValueError(
                        "Selected product was not found."
                    )

                item_total = (
                    quantity * purchase_price
                )

                total_amount += item_total

                purchase_items.append({
                    "product_id": int(product_id),
                    "quantity": quantity,
                    "purchase_price": purchase_price
                })

            if not purchase_items:

                raise ValueError(
                    "Please add at least one "
                    "purchased product."
                )

            if amount_paid > total_amount:

                raise ValueError(
                    "Amount paid cannot be greater "
                    "than total amount."
                )

            if amount_paid == 0:

                payment_status = "Unpaid"

            elif amount_paid < total_amount:

                payment_status = "Partial"

            else:

                payment_status = "Paid"

            # -----------------------------------------
            # BILL FILE UPLOAD
            # -----------------------------------------

            bill_file = request.files.get(
                "bill_file"
            )

            if bill_file and bill_file.filename:

                if not allowed_file(
                    bill_file.filename
                ):

                    raise ValueError(
                        "Bill file must be PDF, JPG, JPEG or PNG."
                    )

                safe_bill_number = secure_filename(
                    bill_number
                )

                extension = os.path.splitext(
                    bill_file.filename
                )[1].lower()

                random_number = random.randint(
                    1000,
                    9999
                )

                saved_bill_filename = (
                    f"purchase_bill_"
                    f"{safe_bill_number}_"
                    f"{supplier_id}_"
                    f"{random_number}"
                    f"{extension}"
                )

                bill_file.save(
                    os.path.join(
                        UPLOAD_FOLDER,
                        saved_bill_filename
                    )
                )

            cur.execute("""
                INSERT INTO purchases
                (
                    supplier_id,
                    bill_number,
                    bill_date,
                    stock_received_date,
                    total_amount,
                    amount_paid,
                    payment_status,
                    payment_date,
                    payment_method,
                    payment_reference,
                    bill_file,
                    notes
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                RETURNING purchase_id
            """, (
                supplier_id,
                bill_number,
                bill_date,
                stock_received_date,
                total_amount,
                amount_paid,
                payment_status,
                payment_date,
                payment_method,
                payment_reference,
                saved_bill_filename,
                notes
            ))

            purchase_id = cur.fetchone()[0]

            for item in purchase_items:

                cur.execute("""
                    INSERT INTO purchase_details
                    (
                        purchase_id,
                        product_id,
                        quantity,
                        purchase_price
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    purchase_id,
                    item["product_id"],
                    item["quantity"],
                    item["purchase_price"]
                ))

                cur.execute("""
                    UPDATE products
                    SET
                        quantity = quantity + %s,
                        purchase_price = %s
                    WHERE product_id = %s
                """, (
                    item["quantity"],
                    item["purchase_price"],
                    item["product_id"]
                ))

            conn.commit()

            message = (
                f"Dealer purchase saved successfully! "
                f"Purchase #{purchase_id} "
                f"= ₹{total_amount:.2f}"
            )

        except Exception as e:

            conn.rollback()

            if saved_bill_filename:

                file_path = os.path.join(
                    UPLOAD_FOLDER,
                    saved_bill_filename
                )

                if os.path.exists(file_path):

                    try:
                        os.remove(file_path)
                    except Exception:
                        pass

            error = str(e)

    cur.execute("""
        SELECT
            supplier_id,
            supplier_name
        FROM suppliers
        ORDER BY supplier_name
    """)

    suppliers_list = cur.fetchall()

    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity,
            purchase_price,
            selling_price
        FROM products
        ORDER BY product_name
    """)

    products_list = cur.fetchall()

    cur.execute("""
        SELECT
            p.purchase_id,
            s.supplier_name,
            p.bill_number,
            p.bill_date,
            p.stock_received_date,
            p.total_amount,
            p.amount_paid,
            p.payment_status,
            p.payment_method,
            p.bill_file
        FROM purchases p
        JOIN suppliers s
            ON p.supplier_id = s.supplier_id
        ORDER BY p.purchase_id DESC
    """)

    purchases_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "dealer_purchases.html",
        suppliers=suppliers_list,
        products=products_list,
        purchases=purchases_list,
        message=message,
        error=error
    )


# =========================================================
# VIEW DEALER BILL
# =========================================================

@app.route("/dealer-bill/<path:filename>")
def dealer_bill(filename):

    if "user_id" not in session:
        return redirect("/")

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )


# =========================================================
# ORDER LIST
# =========================================================

@app.route("/orders")
def orders():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            po.order_id,
            s.supplier_name,
            po.order_date,
            po.expected_date,
            po.status,
            po.notes,
            COALESCE(
                SUM(
                    pod.quantity * pod.expected_price
                ),
                0
            ) AS total_amount
        FROM purchase_orders po
        JOIN suppliers s
            ON po.supplier_id = s.supplier_id
        LEFT JOIN purchase_order_details pod
            ON po.order_id = pod.order_id
        GROUP BY
            po.order_id,
            s.supplier_name,
            po.order_date,
            po.expected_date,
            po.status,
            po.notes
        ORDER BY po.order_id DESC
    """)

    orders_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "orders.html",
        orders=orders_list
    )


# =========================================================
# NEW DEALER ORDER
# =========================================================

@app.route(
    "/new-order",
    methods=["GET", "POST"]
)
def new_order():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    message = None
    error = None

    if request.method == "POST":

        try:

            supplier_id = request.form.get(
                "supplier_id"
            )

            expected_date = request.form.get(
                "expected_date"
            )

            notes = request.form.get(
                "notes",
                ""
            ).strip()

            if not supplier_id:

                raise ValueError(
                    "Please select a dealer / supplier."
                )

            if not expected_date:

                raise ValueError(
                    "Please select expected date."
                )

            product_ids = request.form.getlist(
                "product_id"
            )

            quantities = request.form.getlist(
                "quantity"
            )

            expected_prices = request.form.getlist(
                "expected_price"
            )

            order_items = []

            for i in range(
                len(product_ids)
            ):

                product_id = product_ids[i].strip()

                quantity_text = (
                    quantities[i].strip()
                )

                price_text = (
                    expected_prices[i].strip()
                    if i < len(expected_prices)
                    else ""
                )

                if not product_id:
                    continue

                if not quantity_text:

                    raise ValueError(
                        "Quantity is required for "
                        "every selected product."
                    )

                try:

                    quantity = int(
                        quantity_text
                    )

                except ValueError:

                    raise ValueError(
                        "Quantity must be a valid number."
                    )

                if quantity <= 0:

                    raise ValueError(
                        "Quantity must be greater than 0."
                    )

                try:

                    expected_price = float(
                        price_text or 0
                    )

                except ValueError:

                    raise ValueError(
                        "Expected price must be "
                        "a valid number."
                    )

                if expected_price < 0:

                    raise ValueError(
                        "Expected price cannot be negative."
                    )

                cur.execute("""
                    SELECT product_id
                    FROM products
                    WHERE product_id = %s
                """, (product_id,))

                product_exists = cur.fetchone()

                if not product_exists:

                    raise ValueError(
                        "Selected product was not found."
                    )

                order_items.append({
                    "product_id": int(product_id),
                    "quantity": quantity,
                    "expected_price": expected_price
                })

            if not order_items:

                raise ValueError(
                    "Please add at least one product."
                )

            cur.execute("""
                INSERT INTO purchase_orders
                (
                    supplier_id,
                    expected_date,
                    notes
                )
                VALUES (%s, %s, %s)
                RETURNING order_id
            """, (
                supplier_id,
                expected_date,
                notes
            ))

            order_id = cur.fetchone()[0]

            for item in order_items:

                cur.execute("""
                    INSERT INTO purchase_order_details
                    (
                        order_id,
                        product_id,
                        quantity,
                        expected_price
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    order_id,
                    item["product_id"],
                    item["quantity"],
                    item["expected_price"]
                ))

            conn.commit()

            return redirect("/orders")

        except Exception as e:

            conn.rollback()

            error = str(e)

    cur.execute("""
        SELECT
            supplier_id,
            supplier_name
        FROM suppliers
        ORDER BY supplier_name
    """)

    suppliers_list = cur.fetchall()

    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity,
            purchase_price,
            selling_price
        FROM products
        ORDER BY product_name
    """)

    products_list = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "new_order.html",
        suppliers=suppliers_list,
        products=products_list,
        message=message,
        error=error
    )


# =========================================================
# COMPLETE ORDER
# =========================================================

@app.route(
    "/complete-order/<int:order_id>",
    methods=["POST"]
)
def complete_order(order_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            UPDATE purchase_orders
            SET status = 'Completed'
            WHERE order_id = %s
        """, (order_id,))

        conn.commit()

    except Exception as e:

        conn.rollback()

        cur.close()
        conn.close()

        return str(e), 400

    cur.close()
    conn.close()

    return redirect("/orders")


# =========================================================
# CANCEL ORDER
# =========================================================

@app.route(
    "/cancel-order/<int:order_id>",
    methods=["POST"]
)
def cancel_order(order_id):

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            UPDATE purchase_orders
            SET status = 'Cancelled'
            WHERE order_id = %s
        """, (order_id,))

        conn.commit()

    except Exception as e:

        conn.rollback()

        cur.close()
        conn.close()

        return str(e), 400

    cur.close()
    conn.close()

    return redirect("/orders")


# =========================================================
# REPORTS
# =========================================================

@app.route("/reports")
def reports():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    current_date = date.today()

    try:

        selected_month = int(
            request.args.get(
                "month",
                current_date.month
            )
        )

        selected_year = int(
            request.args.get(
                "year",
                current_date.year
            )
        )

        if (
            selected_month < 1
            or selected_month > 12
        ):

            selected_month = current_date.month

        if (
            selected_year < 2000
            or selected_year > current_date.year + 10
        ):

            selected_year = current_date.year

    except (
        TypeError,
        ValueError
    ):

        selected_month = current_date.month
        selected_year = current_date.year

    # -----------------------------------------
    # TODAY SALES
    # -----------------------------------------

    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM sales
        WHERE DATE(sale_date) = CURRENT_DATE
    """)

    today_sales = cur.fetchone()[0]

    # -----------------------------------------
    # TOTAL SALES
    # -----------------------------------------

    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM sales
    """)

    total_sales = cur.fetchone()[0]

    # -----------------------------------------
    # TOTAL PURCHASES
    # -----------------------------------------

    cur.execute("""
        SELECT COALESCE(SUM(total_amount), 0)
        FROM purchases
    """)

    total_purchases = cur.fetchone()[0]

    # -----------------------------------------
    # TOTAL PAID
    # -----------------------------------------

    cur.execute("""
        SELECT COALESCE(SUM(amount_paid), 0)
        FROM purchases
    """)

    total_paid = cur.fetchone()[0]

    # -----------------------------------------
    # OUTSTANDING
    # -----------------------------------------

    cur.execute("""
        SELECT COALESCE(
            SUM(total_amount - amount_paid),
            0
        )
        FROM purchases
    """)

    outstanding_amount = cur.fetchone()[0]

    # -----------------------------------------
    # TOTAL PROFIT
    # -----------------------------------------

    cur.execute("""
        SELECT COALESCE(
            SUM(
                sd.quantity *
                (
                    sd.selling_price
                    - sd.purchase_price
                )
            ),
            0
        )
        FROM sale_details sd
    """)

    total_profit = cur.fetchone()[0]

    # -----------------------------------------
    # LOW STOCK
    # -----------------------------------------

    cur.execute("""
        SELECT
            product_id,
            product_name,
            quantity,
            min_stock
        FROM products
        WHERE quantity <= min_stock
        ORDER BY quantity ASC
    """)

    low_stock_products = cur.fetchall()

    # -----------------------------------------
    # STOCK REPORT
    # -----------------------------------------

    cur.execute("""
        SELECT
            p.product_id,
            p.product_name,
            COALESCE(c.category_name, 'N/A'),
            p.quantity,
            p.purchase_price,
            p.selling_price,
            p.min_stock
        FROM products p
        LEFT JOIN categories c
            ON p.category_id = c.category_id
        ORDER BY p.product_name ASC
    """)

    stock_report = cur.fetchall()

    # -----------------------------------------
    # TOP PRODUCTS
    # -----------------------------------------

    cur.execute("""
        SELECT
            p.product_name,
            COALESCE(
                SUM(sd.quantity),
                0
            ) AS total_quantity,
            COALESCE(
                SUM(
                    sd.quantity
                    * sd.selling_price
                ),
                0
            ) AS sales_amount
        FROM sale_details sd
        JOIN products p
            ON sd.product_id = p.product_id
        GROUP BY
            p.product_id,
            p.product_name
        ORDER BY total_quantity DESC
        LIMIT 10
    """)

    top_products = cur.fetchall()

    # -----------------------------------------
    # RECENT SALES
    # -----------------------------------------

    cur.execute("""
        SELECT
            s.sale_id,
            s.sale_date,
            s.total_amount,
            s.payment_method
        FROM sales s
        ORDER BY s.sale_id DESC
        LIMIT 10
    """)

    recent_sales = cur.fetchall()

    # -----------------------------------------
    # RECENT PURCHASES
    # -----------------------------------------

    cur.execute("""
        SELECT
            p.purchase_id,
            sup.supplier_name,
            p.bill_number,
            p.bill_date,
            p.total_amount,
            p.amount_paid,
            p.payment_status
        FROM purchases p
        JOIN suppliers sup
            ON p.supplier_id = sup.supplier_id
        ORDER BY p.purchase_id DESC
        LIMIT 10
    """)

    recent_purchases = cur.fetchall()

    # -----------------------------------------
    # MONTHLY SALES SUMMARY
    # -----------------------------------------

    cur.execute("""
        SELECT
            COALESCE(SUM(total_amount), 0),
            COUNT(*)
        FROM sales
        WHERE sale_date >= make_date(
            %s,
            %s,
            1
        )
        AND sale_date <
            make_date(
                %s,
                %s,
                1
            )
            + INTERVAL '1 month'
    """, (
        selected_year,
        selected_month,
        selected_year,
        selected_month
    ))

    monthly_summary = cur.fetchone()

    monthly_sales = monthly_summary[0]

    monthly_bill_count = monthly_summary[1]

    # -----------------------------------------
    # DATE-WISE MONTHLY SALES
    # -----------------------------------------

    cur.execute("""
        SELECT
            DATE(sale_date) AS sale_day,
            COUNT(*) AS bill_count,
            COALESCE(
                SUM(total_amount),
                0
            ) AS day_total
        FROM sales
        WHERE sale_date >= make_date(
            %s,
            %s,
            1
        )
        AND sale_date <
            make_date(
                %s,
                %s,
                1
            )
            + INTERVAL '1 month'
        GROUP BY DATE(sale_date)
        ORDER BY sale_day DESC
    """, (
        selected_year,
        selected_month,
        selected_year,
        selected_month
    ))

    monthly_sales_details = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "reports.html",
        today_sales=today_sales,
        total_sales=total_sales,
        total_purchases=total_purchases,
        total_paid=total_paid,
        outstanding_amount=outstanding_amount,
        total_profit=total_profit,
        low_stock_products=low_stock_products,
        stock_report=stock_report,
        top_products=top_products,
        recent_sales=recent_sales,
        recent_purchases=recent_purchases,
        selected_month=selected_month,
        selected_year=selected_year,
        monthly_sales=monthly_sales,
        monthly_bill_count=monthly_bill_count,
        monthly_sales_details=monthly_sales_details
    )


# =========================================================
# LOW STOCK
# =========================================================

@app.route("/low-stock")
def low_stock():

    if "user_id" not in session:
        return redirect("/")

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            p.product_id,
            p.product_name,
            c.category_name,
            p.quantity,
            p.min_stock,
            p.purchase_price,
            p.selling_price
        FROM products p
        LEFT JOIN categories c
            ON p.category_id = c.category_id
        WHERE p.quantity <= p.min_stock
        ORDER BY
            p.quantity ASC,
            p.product_name ASC
    """)

    low_stock_products = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "low_stock.html",
        low_stock_products=low_stock_products
    )


# =========================================================
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/")


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )

