import os
import uuid
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
SUPABASE_URL = "https://jpapplzlvkekcosbajie.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpwYXBwbHpsdmtla2Nvc2JhamllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEyMjg4NDUsImV4cCI6MjA4NjgwNDg0NX0.ZYLW5yNuHwyfVFLh3LRZ4QbM3SkfQPuiy_XbiXy1or4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ========================================================
# ฟังก์ชันนี้จะถูกส่งไปให้ทุกหน้าเว็บ (HTML) เรียกใช้ได้อัตโนมัติ
@app.context_processor
def inject_category_counts():
    # แก้บรรทัดนี้ให้รับ book_format=None เพิ่มเข้ามา
    def get_cat_count(cat_name, book_format=None):
        query = supabase.table("books").select("id", count="exact").ilike("category", f"%{cat_name}%")
        
        # ถ้ามีการส่งค่า format (เช่น ebook) มา ให้กรองเพิ่มก่อนนับ
        if book_format:
            query = query.eq("format", book_format)
            
        res = query.execute()
        return res.count if res.count else 0
        
    return dict(get_cat_count=get_cat_count)
# Route ฝั่งลูกค้า (Customer)
@app.route("/")
def home():
    # เพิ่ม .eq("format", "physical") เพื่อให้หน้าแรกโชว์เฉพาะหนังสือเล่ม
    res_latest = supabase.table("books").select("*").eq("format", "physical").order("id", desc=True).limit(10).execute()
    res_recommend = supabase.table("books").select("*").eq("format", "physical").order("price", desc=False).limit(10).execute()
    res_trending = supabase.table("books").select("*").eq("format", "physical").order("price", desc=True).limit(10).execute()
    
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
    # เพิ่ม .eq("format", "ebook") เข้าไปในทุกบรรทัดย่อย
    res_latest = supabase.table("books").select("*").eq("format", "ebook").order("id", desc=True).limit(10).execute()
    latest_books = res_latest.data

    res_recommend = supabase.table("books").select("*").eq("format", "ebook").order("price", desc=False).limit(10).execute()
    recommend_books = res_recommend.data

    res_trending = supabase.table("books").select("*").eq("format", "ebook").order("price", desc=True).limit(10).execute()
    trending_books = res_trending.data

    res_free = supabase.table("books").select("*").eq("format", "ebook").eq("price", 0).limit(10).execute()
    free_ebooks = res_free.data

    return render_template("ebooks.html", 
                           latest_books=latest_books, 
                           recommend_books=recommend_books,
                           trending_books=trending_books,
                           free_ebooks=free_ebooks)

@app.route("/all-ebooks")
def all_ebooks():
    # ดึงเฉพาะ E-book ทั้งหมดมาแสดงแบบตาราง
    res = supabase.table("books").select("*").eq("format", "ebook").execute()
    return render_template("all_ebooks.html", books=res.data)

@app.route("/magazines")
def magazines():
    res = supabase.table("books").select("*").ilike("category", "%นิตยสาร%").execute()
    books = res.data
    
    # 2. รับค่าจาก URL ทั้งตัวกรองและตัวเรียงลำดับ
    selected_categories = request.args.getlist("category") 
    price_filter = request.args.get("price") 
    sort_by = request.args.get("sort", "latest") # <--- รับค่าเรียงลำดับตรงนี้
    
    # 3. กรองตาม "หมวดหมู่ย่อย"
    if selected_categories:
        filtered_books = []
        for book in books:
            book_cat = str(book.get("category", ""))
            if any(cat in book_cat for cat in selected_categories):
                filtered_books.append(book)
        books = filtered_books 
        
    # 4. กรองตาม "ราคา"
    if price_filter:
        if price_filter == "0-100":
            books = [b for b in books if b.get("price", 0) < 100]
        elif price_filter == "100-300":
            books = [b for b in books if 100 <= b.get("price", 0) <= 300]
        elif price_filter == "301-500":
            books = [b for b in books if 301 <= b.get("price", 0) <= 500]
        elif price_filter == "500-up":
            books = [b for b in books if b.get("price", 0) > 500]

    # 5. เรียงลำดับข้อมูล (Sort)
    if sort_by == "price_asc":
        books.sort(key=lambda x: x.get("price", 0))
    elif sort_by == "price_desc":
        books.sort(key=lambda x: x.get("price", 0), reverse=True)
    else:
        books.sort(key=lambda x: x.get("id", 0), reverse=True)
        
    # 6. ส่งค่าทั้งหมดไปหน้าเว็บ
    return render_template("magazines.html", 
                           magazines=books, 
                           selected_categories=selected_categories, 
                           price_filter=price_filter,
                           sort_by=sort_by)

@app.route("/manga")
def manga():
    # 1. ดึงหนังสือมังงะทั้งหมด
    res = supabase.table("books").select("*").ilike("category", "%มังงะ%").execute()
    books = res.data
    
    # 2. รับค่าจาก URL ทั้งตัวกรองและตัวเรียงลำดับ
    selected_categories = request.args.getlist("category") 
    price_filter = request.args.get("price") 
    sort_by = request.args.get("sort", "latest") # <--- รับค่าเรียงลำดับตรงนี้
    
    # 3. กรองตาม "หมวดหมู่ย่อย"
    if selected_categories:
        filtered_books = []
        for book in books:
            book_cat = str(book.get("category", ""))
            if any(cat in book_cat for cat in selected_categories):
                filtered_books.append(book)
        books = filtered_books 
        
    # 4. กรองตาม "ราคา"
    if price_filter:
        if price_filter == "0-100":
            books = [b for b in books if b.get("price", 0) < 100]
        elif price_filter == "100-300":
            books = [b for b in books if 100 <= b.get("price", 0) <= 300]
        elif price_filter == "301-500":
            books = [b for b in books if 301 <= b.get("price", 0) <= 500]
        elif price_filter == "500-up":
            books = [b for b in books if b.get("price", 0) > 500]

    # 5. เรียงลำดับข้อมูล (Sort)
    if sort_by == "price_asc":
        books.sort(key=lambda x: x.get("price", 0))
    elif sort_by == "price_desc":
        books.sort(key=lambda x: x.get("price", 0), reverse=True)
    else:
        books.sort(key=lambda x: x.get("id", 0), reverse=True)
        
    # 6. ส่งค่าทั้งหมดไปหน้าเว็บ
    return render_template("manga.html", 
                           manga_list=books, 
                           selected_categories=selected_categories, 
                           price_filter=price_filter,
                           sort_by=sort_by)

@app.route("/preorder")
def preorder():
    try:
        # ดึงสินค้าพรีออเดอร์
        # ตรวจสอบให้แน่ใจว่าคอลัมน์ 'status' มีอยู่จริงใน Supabase
        res = supabase.table("books").select("*").eq("status", "Pre-order").execute()
        books = res.data
    except Exception as e:
        print(f"Error fetching preorder: {e}")
        books = [] # ถ้าดึงไม่ได้ ให้เป็นรายการว่างๆ หน้าเว็บจะได้ไม่ Traceback

    sort_by = request.args.get("sort", "latest")
    
    # การเรียงลำดับ (เหมือนหน้าอื่นๆ)
    if sort_by == "price_asc":
        books.sort(key=lambda x: x.get("price", 0))
    elif sort_by == "price_desc":
        books.sort(key=lambda x: x.get("price", 0), reverse=True)
    else:
        books.sort(key=lambda x: x.get("id", 0), reverse=True)
        
    return render_template("preorder.html", preorder_list=books, sort_by=sort_by)

@app.route("/audiobook")
def audiobooks():
    # ดึงหนังสือเสียงทั้งหมดมาจากฐานข้อมูลก่อน
    res = supabase.table("books").select("*").eq("format", "audiobook").execute()
    books = res.data
    
    # รับค่าที่ผู้ใช้ติ๊กเลือกตัวกรองมาจาก URL
    selected_categories = request.args.getlist("category") # รับเป็นรายการ (List) เพราะติ๊กได้หลายอัน
    price_filter = request.args.get("price") # รับค่าช่วงราคา
    
    # นำมากรอง "หมวดหมู่" (ถ้ามีการติ๊กเลือก)
    if selected_categories:
        filtered_books = []
        for book in books:
            # ดึงข้อมูล category ของหนังสือเล่มนั้นมาเช็ค (ถ้าไม่มีให้เป็นข้อความว่างๆ ป้องกัน Error)
            book_cat = str(book.get("category", ""))
            # ถ้ามีคำที่ติ๊กเลือก ซ่อนอยู่ในหมวดหมู่ของหนังสือ ให้เก็บเล่มนี้ไว้
            if any(cat in book_cat for cat in selected_categories):
                filtered_books.append(book)
        books = filtered_books # อัปเดตรายการหนังสือที่ผ่านการกรองแล้ว
        
    # กรอง "ราคา" 
    if price_filter:
        if price_filter == "0-100":
            books = [b for b in books if b.get("price", 0) < 100]
        elif price_filter == "100-300":
            books = [b for b in books if 100 <= b.get("price", 0) <= 300]
        elif price_filter == "301-500":
            books = [b for b in books if 301 <= b.get("price", 0) <= 500]
        elif price_filter == "500-up":
            books = [b for b in books if b.get("price", 0) > 500]
            
    # ส่งรายการหนังสือ พร้อมกับ "สถานะตัวกรอง" กลับไปให้หน้าเว็บเพื่อโชว์ว่าติ๊กอะไรค้างไว้
    return render_template("audiobook.html", 
                           audiobook_list=books, 
                           selected_categories=selected_categories, 
                           price_filter=price_filter)

@app.route("/all-books")
def all_books():
    # หน้า "หนังสือทั้งหมด" ให้แสดงเฉพาะแบบเล่ม (physical)
    res = supabase.table("books").select("*").eq("format", "physical").execute()
    return render_template("all_books.html", books=res.data)

@app.route("/category")
def category_page():
    cat_name = request.args.get("name")
    # เพิ่มการรับค่า format (เช่น ebook หรือ physical) จาก URL
    book_format = request.args.get("format") 
    
    if cat_name:
        search_term = f"%{cat_name}%"
        # เริ่มสร้าง Query
        query = supabase.table("books").select("*").ilike("category", search_term)
        
        # ถ้าใน URL มีการส่ง &format=ebook มา ให้กรองเพิ่ม
        if book_format:
            query = query.eq("format", book_format)
            
        res = query.execute()
        books = res.data
    else:
        books = []
    
    display_name = cat_name if cat_name else "ไม่ระบุ"
    # ถ้าเป็น ebook อาจจะแต่งชื่อหัวข้อเพิ่ม เช่น "อีบุ๊กนิยาย"
    if book_format == 'ebook':
        display_name = f"อีบุ๊ก{display_name}"
        
    return render_template("category.html", books=books, category_name=display_name)

# ----------------- รายละเอียดและตะกร้าสินค้า -----------------
@app.route("/book/<int:id>")
def detail(id):
    # ดึงข้อมูลหนังสือเล่มปัจจุบัน
    response = supabase.table("books").select("*").eq("id", id).maybe_single().execute()
    book = response.data
    
    if not book:
        return "ไม่พบข้อมูลหนังสือ", 404
    
    # ดึงสินค้าที่เกี่ยวข้องทั้งหมด (เอา limit ออก)
    related_res = supabase.table("books") \
        .select("*") \
        .eq("format", book.get('format')) \
        .ilike("category", f"%{book.get('category')}%") \
        .neq("id", id) \
        .execute()
    
    related_books = related_res.data
        
    return render_template("detail.html", book=book, related_books=related_books)

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
    # ตรวจสอบก่อนว่าเป็นแอดมินหรือไม่ (อ้างอิงจากระบบเดิมของคุณ)
    if session.get("user") != "admin@bookstore.com":
        return redirect(url_for("login"))
    return render_template("admin_users.html")

# ----------------- ระบบชำระเงินจำลอง (Checkout) -----------------
@app.route("/shipping", methods=["GET", "POST"])
def shipping():
    # บังคับว่าต้องล็อกอินก่อนถึงจะกรอกที่อยู่และสั่งของได้
    if not session.get("user"):
        return redirect(url_for("login"))
        
    # ตรวจสอบว่ามีของในตะกร้าไหม ถ้าไม่มีให้เด้งกลับไปหน้าตะกร้า
    cart_ids = session.get("cart", [])
    if not cart_ids:
        return redirect(url_for("cart"))

    if request.method == "POST":
        # รับค่าจากฟอร์มหน้าเว็บ
        address_data = {
            "full_name": request.form.get("full_name"),
            "phone": request.form.get("phone"),
            "address_detail": request.form.get("address_detail"),
            "sub_district": request.form.get("sub_district"),
            "district": request.form.get("district"),
            "province": request.form.get("province"),
            "postal_code": request.form.get("postal_code"),
            "user_email": session.get("user")
        }
        
        # บันทึกที่อยู่ลงฐานข้อมูล Supabase
        try:
            res = supabase.table("addresses").insert(address_data).execute()
            
            if res.data:
                session['current_address_id'] = res.data[0]['id']
                return redirect(url_for("checkout"))
                
        except Exception as e:
            # ถ้าพัง มันจะพ่นข้อความ Error สีแดงๆ ออกมาที่หน้าเว็บให้เราอ่านได้เลย
            return f"<div style='padding: 50px; text-align: center; color: red;'><h2>เกิดข้อผิดพลาดจาก Supabase</h2><p>{str(e)}</p></div>"
            
    return render_template("shipping.html")

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    if not session.get("user"):
        return redirect(url_for("login"))
        
    cart_ids = session.get("cart", [])
    if not cart_ids:
        return redirect(url_for("cart"))

    # คำนวณยอดรวมจากตะกร้า
    res = supabase.table("books").select("id, price").in_("id", cart_ids).execute()
    db_books = {b['id']: b['price'] for b in res.data}
    total = sum(db_books.get(b_id, 0) for b_id in cart_ids)

    if request.method == "POST":
        file = request.files.get("slip_image")
        slip_url = ""
        
        # --- อัปโหลดรูปลง SUPABASE แทนโฟลเดอร์ Local ---
        if file and file.filename != "":
            # สร้างชื่อไฟล์ใหม่แบบสุ่ม ป้องกันชื่อไฟล์ซ้ำกัน
            file_extension = file.filename.split(".")[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # อัปโหลดขึ้น Supabase Storage (ในแฟ้ม slips ที่เราเพิ่งสร้าง)
            file_bytes = file.read()
            supabase.storage.from_("slips").upload(
                path=unique_filename, 
                file=file_bytes, 
                file_options={"content-type": file.content_type}
            )
            
            # ดึง URL สาธารณะของรูปภาพ
            slip_url = supabase.storage.from_("slips").get_public_url(unique_filename)

        # --- บันทึกข้อมูลออเดอร์ลงตาราง orders ---
        address_id = session.get('current_address_id') # ดึงไอดีที่อยู่ที่ได้จากหน้า Shipping
        
        supabase.table("orders").insert({
            "user_email": session["user"],
            "total_price": total,
            "status": "Pending",
            "slip_image_url": slip_url,
            "address_id": address_id  # <--- ลิงก์ที่อยู่จัดส่งเข้ากับออเดอร์นี้
        }).execute()

        # ล้างตะกร้าสินค้า
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