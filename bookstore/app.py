import os
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from supabase import create_client, Client

app = Flask(__name__)
app.secret_key = "mysecret_key_1234" # เปลี่ยนเป็นคีย์ของคุณเอง

# สร้างโฟลเดอร์สำหรับเก็บรูปสลิปจำลอง (ถ้ายืนยันรันไฟล์นี้ มันจะสร้างโฟลเดอร์ให้อัตโนมัติ)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- ตั้งค่าการเชื่อมต่อ Supabase ---
SUPABASE_URL = "https://jpapplzlvkekcosbajie.supabase.co/"
SUPABASE_KEY = "sb_publishable_2eKzbUTWCaJ0as83yelDXA_FYsY1iGa"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# Route ฝั่งลูกค้า (Customer)
# =========================================================

@app.route("/")
def home():
    # หน้าแรกแสดงคละกันหรือเน้นเล่มก็ได้
    res_latest = supabase.table("books").select("*").order("id", desc=True).limit(10).execute()
    res_recommend = supabase.table("books").select("*").order("price", desc=False).limit(10).execute()
    res_trending = supabase.table("books").select("*").order("price", desc=True).limit(10).execute()
    
    return render_template("index.html", 
                           latest_books=res_latest.data, 
                           recommend_books=res_recommend.data, 
                           trending_books=res_trending.data)
# ----------------- ระบบค้นหา -----------------
@app.route("/search_suggestions")
def search_suggestions():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    
    res = supabase.table("books").select("id, title").ilike("title", f"%{query}%").limit(5).execute()
    return jsonify(res.data)

@app.route("/search")
def search():
    query = request.args.get("q", "").strip()
    if not query:
        return redirect(url_for("home"))
    
    res = supabase.table("books").select("*").ilike("title", f"%{query}%").execute()
    search_results = res.data
    
    return render_template("search_results.html", books=search_results, query=query)

# ----------------- หมวดหมู่สินค้า -----------------
@app.route("/ebooks")
def ebooks():
    res_latest = supabase.table("books").select("*").order("id", desc=True).limit(10).execute()
    latest_books = res_latest.data

    res_recommend = supabase.table("books").select("*").order("price", desc=False).limit(10).execute()
    recommend_books = res_recommend.data

    res_trending = supabase.table("books").select("*").order("price", desc=True).limit(10).execute()
    trending_books = res_trending.data

    res_free = supabase.table("books").select("*").eq("price", 0).limit(10).execute()
    free_ebooks = res_free.data

    return render_template("ebooks.html", 
                           latest_books=latest_books, 
                           recommend_books=recommend_books,
                           trending_books=trending_books,
                           free_ebooks=free_ebooks)

@app.route("/magazines")
def magazines():
    res = supabase.table("books").select("*").limit(30).execute()
    return render_template("magazines.html", magazines=res.data)

@app.route("/manga")
def manga():
    res = supabase.table("books").select("*").limit(20).execute()
    return render_template("manga.html", manga_list=res.data)

@app.route("/preorder")
def preorder():
    res = supabase.table("books").select("*").limit(20).execute()
    return render_template("preorder.html", preorder_list=res.data)

@app.route("/audiobooks")
def audiobooks():
    # กรองเฉพาะ format 'audiobook'
    res = supabase.table("books").select("*").eq("format", "audiobook").execute()
    return render_template("audiobook.html", audiobook_list=res.data)

@app.route("/all-ebooks")
def all_ebooks():
    response = supabase.table("books").select("*").order("id", desc=True).execute()
    return render_template("all_books.html", books=response.data)

@app.route("/all-books")
def all_books():
    # หน้า "หนังสือทั้งหมด" ให้แสดงเฉพาะแบบเล่ม (physical)
    res = supabase.table("books").select("*").eq("format", "physical").execute()
    return render_template("all_books.html", books=res.data)

# ----------------- รายละเอียดและตะกร้าสินค้า -----------------
@app.route("/book/<int:id>")
def detail(id):
    response = supabase.table("books").select("*").eq("id", id).maybe_single().execute()
    book = response.data
    
    if not book:
        return "ไม่พบข้อมูลหนังสือ", 404
        
    return render_template("detail.html", book=book)

@app.route("/add_to_cart/<int:id>")
def add_to_cart(id):
    qty = int(request.args.get("qty", 1))
    cart = session.get("cart", [])
    for _ in range(qty):
        cart.append(id)
        
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/cart")
def cart():
    cart_ids = session.get("cart", [])
    books = []
    total = 0
    
    if cart_ids:
        response = supabase.table("books").select("*").in_("id", cart_ids).execute()
        db_books = {b['id']: b for b in response.data}
        
        for b_id in cart_ids:
            if b_id in db_books:
                books.append(db_books[b_id])
                total += db_books[b_id]["price"]
                
    return render_template("cart.html", books=books, total=total)

@app.route("/remove_item/<int:id>")
def remove_item(id):
    cart = session.get("cart", [])
    cart = [book_id for book_id in cart if book_id != id]
    session["cart"] = cart
    return redirect(url_for("cart"))

@app.route("/clear_cart")
def clear_cart():
    session.pop("cart", None)
    return redirect(url_for("cart"))

# =========================================================
# ระบบสมาชิก (Auth)
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            response = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
            return redirect(url_for("login"))
        except Exception as e:
            return render_template("register.html", error="ไม่สามารถสมัครได้: " + str(e))
            
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        try:
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            session["user"] = response.user.email
            return redirect(url_for("home"))
        except Exception as e:
            return render_template("login.html", error="อีเมลหรือรหัสผ่านไม่ถูกต้อง")
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    supabase.auth.sign_out()
    session.pop("user", None)
    return redirect(url_for("home"))

# =========================================================
# ส่วนของแอดมิน (Admin)
# =========================================================

def is_admin():
    # เปลี่ยนอีเมลตรงนี้เป็นอีเมลแอดมินของคุณ
    return session.get("user") == "admin@bookstore.com" 

# หน้า Dashboard หลัก
@app.route("/admin/dashboard")
def admin_dashboard():
    if not is_admin(): return redirect(url_for("home"))
        
    # --- 1. ข้อมูลหนังสือ (หน้า Dashboard โชว์แค่ 4 เล่มล่าสุด) ---
    res_books = supabase.table("books").select("*").order("id", desc=True).limit(4).execute()
    books = res_books.data
    total_books = len(supabase.table("books").select("id").execute().data)

    # --- 2. ข้อมูลคำสั่งซื้อ (หน้า Dashboard โชว์แค่ 5 รายการล่าสุด) ---
    res_orders = supabase.table("orders").select("*").order("id", desc=True).limit(5).execute()
    orders = res_orders.data
    total_orders = len(supabase.table("orders").select("id").execute().data)

    # --- 3. ข้อมูลกราฟ ---
    res_chart = supabase.table("orders").select("id, total_price").eq("status", "Completed").order("id", desc=True).limit(7).execute()
    chart_records = list(reversed(res_chart.data))
    chart_labels = [f"Order #{o['id']}" for o in chart_records]
    chart_values = [o['total_price'] for o in chart_records]
    
    return render_template("admin_dashboard.html", 
                           books=books, total_books=total_books, 
                           orders=orders, total_orders=total_orders,
                           chart_labels=chart_labels, chart_values=chart_values)

# หน้าดูออเดอร์ทั้งหมดแยกออกมา
@app.route("/admin/orders")
def admin_orders():
    if not is_admin(): return redirect(url_for("home"))
    status_filter = request.args.get("status", "all")
    
    query = supabase.table("orders").select("*").order("id", desc=True)
    if status_filter == "pending":
        query = query.eq("status", "Pending")
    elif status_filter == "completed":
        query = query.eq("status", "Completed")
        
    orders = query.execute().data
    return render_template("admin_orders.html", orders=orders, current_status=status_filter)

# หน้าดูหนังสือทั้งหมดแยกออกมา
@app.route("/admin/books")
def admin_books():
    if not is_admin(): return redirect(url_for("home"))
    books = supabase.table("books").select("*").order("id", desc=True).execute().data
    total_books = len(books)
    return render_template("admin_books.html", books=books, total_books=total_books)

@app.route("/admin/add_book", methods=["GET", "POST"])
def admin_add_book():
    if not is_admin(): return redirect(url_for("home"))
    msg = None
    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        stock = request.form.get("stock_quantity", 0) 
        try:
            supabase.table("books").insert({
                "title": title,
                "price": float(price),
                "stock_quantity": int(stock)
            }).execute()
            msg = "✅ เพิ่มหนังสือสำเร็จแล้ว!"
        except Exception as e:
            msg = f"❌ เกิดข้อผิดพลาด: {str(e)}"
    return render_template("admin_add_book.html", msg=msg)

@app.route("/admin/edit_book/<int:id>", methods=["GET", "POST"])
def admin_edit_book(id):
    if not is_admin(): return redirect(url_for("home"))
    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        stock = request.form.get("stock_quantity", 0) 
        
        supabase.table("books").update({
            "title": title,
            "price": float(price),
            "stock_quantity": int(stock)
        }).eq("id", id).execute()
        return redirect(url_for("admin_dashboard"))
        
    response = supabase.table("books").select("*").eq("id", id).execute()
    book = response.data[0] if response.data else None
    if not book: return redirect(url_for("admin_dashboard"))
    return render_template("admin_edit_book.html", book=book)

@app.route("/admin/delete_book/<int:id>")
def admin_delete_book(id):
    if not is_admin(): return redirect(url_for("home"))
    supabase.table("books").delete().eq("id", id).execute()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/users")
def admin_users():
    if not is_admin(): return redirect(url_for("home"))
    return render_template("admin_users.html")

# ----------------- ระบบชำระเงินจำลอง (Checkout) -----------------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not session.get("user"):
        return redirect(url_for("login"))
        
    cart_ids = session.get("cart", [])
    if not cart_ids:
        return redirect(url_for("cart"))

    res = supabase.table("books").select("id, price").in_("id", cart_ids).execute()
    db_books = {b['id']: b['price'] for b in res.data}
    total = sum(db_books.get(b_id, 0) for b_id in cart_ids)

    if request.method == "POST":
        file = request.files.get("slip_image")
        slip_url = ""
        
        if file and file.filename != "":
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            slip_url = f"/static/uploads/{filename}"

        supabase.table("orders").insert({
            "user_email": session["user"],
            "total_price": total,
            "status": "Pending",
            "slip_image_url": slip_url
        }).execute()

        session.pop("cart", None)
        return render_template("checkout_success.html") 

    return render_template("checkout.html", total=total)

@app.route("/admin/approve_order/<int:id>")
def admin_approve_order(id):
    if not is_admin(): return redirect(url_for("home"))
    supabase.table("orders").update({"status": "Completed"}).eq("id", id).execute()
    return redirect(url_for("admin_dashboard"))

if __name__ == "__main__":
    app.run(debug=True)