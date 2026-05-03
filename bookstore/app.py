import os
import math
import uuid
from werkzeug.utils import secure_filename
from flask import Flask, render_template, request, redirect, session, url_for, jsonify
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer
print("⏳ AI Model is loading... Please wait.")
search_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
print("✅ AI Model Ready!")

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
def utility_processor():
    def get_cat_count(category_name, book_format="physical"):
        # ใช้ .contains กับ category ด้วย และใส่ [ ] ครอบ
        query = supabase.table("books").select("id", count="exact").contains("category", [category_name])
        
        # ค้นหา format ก็ใช้ .contains แบบเดิม
        if book_format:
            query = query.contains("format", [book_format])
            
        res = query.execute()
        return res.count if res.count else 0
        
    return dict(get_cat_count=get_cat_count)
# Route ฝั่งลูกค้า (Customer)
@app.route("/")
def home():
    res_latest = supabase.table("books").select("*").contains("format", ["physical"]).order("id", desc=True).limit(10).execute()
    res_recommend = supabase.table("books").select("*").contains("format", ["physical"]).order("price", desc=False).limit(10).execute()
    res_trending = supabase.table("books").select("*").contains("format", ["physical"]).order("price", desc=True).limit(10).execute()
    
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
    res_latest = supabase.table("books").select("*").contains("format", ["ebook"]).order("id", desc=True).limit(10).execute()
    latest_books = res_latest.data

    res_recommend = supabase.table("books").select("*").contains("format", ["ebook"]).order("price", desc=False).limit(10).execute()
    recommend_books = res_recommend.data

    res_trending = supabase.table("books").select("*").contains("format", ["ebook"]).order("price", desc=True).limit(10).execute()
    trending_books = res_trending.data

    res_free = supabase.table("books").select("*").contains("format", ["ebook"]).eq("price", 0).limit(10).execute()
    free_ebooks = res_free.data

    return render_template("ebooks.html", 
                           latest_books=latest_books, 
                           recommend_books=recommend_books,
                           trending_books=trending_books,
                           free_ebooks=free_ebooks)

@app.route('/all-ebooks')
def all_ebooks():
    page = request.args.get('page', 1, type=int)
    per_page = 12 # แสดงหน้าละ 12 เล่ม
    
    # ดึงข้อมูล (ก๊อปปี้ Logic การดึงข้อมูลเดิมของคุณมา)
    res = supabase.table("books").select("*").execute()
    all_items = res.data
    
    total_items = len(all_items)
    total_pages = math.ceil(total_items / per_page)
    
    # ตัดแบ่งข้อมูล
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_items[start:end]
    
    return render_template('all_ebooks.html', 
                           books=paginated_items, 
                           page=page, 
                           total_pages=total_pages)

@app.route("/magazines")
def magazines():
    res = supabase.table("books").select("*").contains("category", ["นิตยสาร"]).execute()
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
    res = supabase.table("books").select("*").contains("category", ["มังงะ"]).execute()
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

# =========================================
# หน้าแสดงรายการพรีออเดอร์ (ดึงเฉพาะหนังสือที่หมดสต๊อก)
# =========================================
@app.route('/preorder')
def preorder():
    # 1. ดึงรายการหนังสือพรีออเดอร์ปกติ
    res = supabase.table('books').select('*').lte('stock_quantity', 0).execute()
    preorder_list = res.data if res.data else []
    
    # 🌟 จุดที่แก้: เปลี่ยนมาใช้ session.get('user') ให้ตรงกับระบบ Login
    user_email = session.get('user') 
    pledged_book_ids = [] # สร้างลิสต์ว่างรอไว้
    
    if user_email:
        # ดึงจากตาราง logs
        log_res = supabase.table("preorder_logs").select("book_id").eq("user_email", user_email).execute()
        
        if log_res.data:
            pledged_book_ids = [item['book_id'] for item in log_res.data]
            
    # ส่งชื่อตัวแปร pledged_books ไปที่ HTML
    return render_template('preorder.html', 
                           preorder_list=preorder_list, 
                           pledged_books=pledged_book_ids)

@app.route("/audiobook")
def audiobooks():
    # ดึงหนังสือเสียงทั้งหมดมาจากฐานข้อมูลก่อน
    res = supabase.table("books").select("*").contains("format", ["audiobook"]).execute()
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

@app.route("/audio_player/<int:book_id>")
def audio_player(book_id):
    # ดึงข้อมูลหนังสือเล่มนั้นจาก Supabase รวมถึง audio_url และ vtt_url
    res = supabase.table("books").select("*").eq("id", book_id).single().execute()
    book = res.data
    
    # ถ้าหาไม่เจอ หรือไม่มีไฟล์เสียง ให้เด้งกลับไปหน้าเดิม
    if not book or not book.get("audio_url"):
        return redirect(url_for("audiobooks"))
        
    return render_template("audio_player.html", book=book)

@app.route('/all-books')
def all_books():
    page = request.args.get('page', 1, type=int)
    per_page = 18 # แสดงหน้าละ 12 เล่ม
    
    # ดึงข้อมูล (ก๊อปปี้ Logic การดึงข้อมูลเดิมของคุณมา)
    res = supabase.table("books").select("*").execute()
    all_items = res.data
    
    total_items = len(all_items)
    total_pages = math.ceil(total_items / per_page)
    
    # ตัดแบ่งข้อมูล
    start = (page - 1) * per_page
    end = start + per_page
    paginated_items = all_items[start:end]
    
    return render_template('all_books.html', 
                           books=paginated_items, 
                           page=page, 
                           total_pages=total_pages)

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
    
    format_val = book.get('format') or []
    category_val = book.get('category') or []
    
    related_res = supabase.table("books") \
        .select("*") \
        .contains("format", format_val) \
        .contains("category", category_val) \
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
            supabase.table("notifications").insert({
                "type": "user",
                "message": f"🎉 ยินดีต้อนรับสมาชิกใหม่! {email} เพิ่งสมัครเข้ามา"
            }).execute()
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
            # 1. ยืนยันตัวตนกับระบบ Auth
            response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            # 2. เก็บอีเมลไว้ใน Session เหมือนเดิม
            session["user"] = response.user.email
            
            # 🌟 3. สิ่งที่เพิ่มมา: ดึงสิทธิ์ (Role) จากตารางผู้ใช้มาด้วย! 🌟
            user_data = supabase.table('users').select('role').eq('email', email).execute()
            
            # เช็คว่าถ้ามีข้อมูล ให้เก็บ Role ลง Session
            if user_data.data:
                session["role"] = user_data.data[0]['role']
            else:
                session["role"] = 'user' # กันเหนียว ถ้าหาไม่เจอให้เป็นแค่ user ธรรมดา

            # ปริ้นท์เช็คใน Terminal ว่าล็อกอินได้สิทธิ์อะไร
            print(f"🎉 Login สำเร็จ! อีเมล: {email} | สิทธิ์: {session.get('role')}")

            return redirect(url_for("home"))
            
        except Exception as e:
            print(f"❌ Login error: {e}")
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

    # 🌟 --- 4. สถิติใหม่ (ยอดขายรวม, รอตรวจสอบ, จำนวนสมาชิก) --- 🌟
    try:
        # ดึงออเดอร์ทั้งหมดมาบวกเลข
        all_orders_res = supabase.table("orders").select("total_price, status").execute()
        all_orders = all_orders_res.data
        
        total_sales = sum(o['total_price'] for o in all_orders if o['status'] == 'Completed')
        pending_count = sum(1 for o in all_orders if o['status'] == 'Pending')

        # นับจำนวนสมาชิก
        user_res = supabase.table("users").select("id").execute()
        user_count = len(user_res.data)
    except Exception as e:
        print(f"Error fetching stats: {e}")
        total_sales, pending_count, user_count = 0, 0, 0

    # ส่งตัวแปรทั้งหมดไปที่หน้าเว็บ
    return render_template("admin_dashboard.html", 
                           books=books, total_books=total_books, 
                           orders=orders, total_orders=total_orders,
                           chart_labels=chart_labels, chart_values=chart_values,
                           total_sales=total_sales, pending_count=pending_count, user_count=user_count)

# หน้าดูออเดอร์ทั้งหมดแยกออกมา
# หน้าดูออเดอร์ทั้งหมดแยกออกมา
@app.route("/admin/orders")
def admin_orders():
    if not is_admin(): return redirect(url_for("home"))
    status_filter = request.args.get("status", "all")
    
    try:
        # 1. ดึงออเดอร์ตามสถานะที่แอดมินกดเลือก
        query = supabase.table("orders").select("*").order("id", desc=True)
        if status_filter == "pending":
            query = query.eq("status", "Pending")
        elif status_filter == "completed":
            query = query.eq("status", "Completed")
            
        orders = query.execute().data
        
        # 2. ดึงรายการหนังสือมายัดใส่ออเดอร์ (เหมือนหน้าฝั่งลูกค้าเป๊ะ!)
        if orders:
            order_ids = [o['id'] for o in orders]
            items_res = supabase.table("order_items").select("*").in_("order_id", order_ids).execute()
            all_items = items_res.data
            
            # ... โค้ดด้านบน ...
        for order in orders:
            # 1. ดึงรายการสินค้า (โค้ดเดิมของคุณต้องย่อหน้าเท่ากัน)
            items_res = supabase.table("order_items").select("*").eq("order_id", order["id"]).execute()
            order["order_items"] = items_res.data

            # 2. ส่วนที่เพิ่มใหม่ (ตรวจสอบว่ามี Space ด้านหน้า 8 ช่อง หรือ 2 Tab)
            if order.get("address_id"):
                addr_res = supabase.table("addresses").select("*").eq("id", order["address_id"]).execute()
                if addr_res.data:
                    addr = addr_res.data[0]
                    order["address_text"] = (
                        f"👤 {addr.get('full_name', 'ไม่ระบุชื่อ')} | 📞 {addr.get('phone', '-')}\n"
                        f"🏠 {addr.get('address_detail', '')} "
                        f"ต.{addr.get('sub_district', '')} อ.{addr.get('district', '')} "
                        f"จ.{addr.get('province', '')} {addr.get('postal_code', '')}"
                    )
                else:
                    order["address_text"] = "⚠️ ไม่พบข้อมูลที่อยู่"
            else:
                order["address_text"] = "❌ ไม่มีรหัสที่อยู่"
    # ... โค้ดถัดไป ...
                
    except Exception as e:
        print(f"Error fetching admin orders: {e}")
        orders = []

    return render_template("admin_orders.html", orders=orders, current_status=status_filter)

# หน้าดูหนังสือทั้งหมดแยกออกมา
@app.route('/admin/books')
def admin_books():
    # ตรวจสอบสิทธิ์ (ใช้โค้ดเช็ค Admin ของคุณแบบเดิมได้เลย)
    if 'user' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))

    search_query = request.args.get('q', '')
    page = request.args.get('page', 1, type=int) # รับว่ากำลังเปิดหน้าไหนอยู่ (ค่าเริ่มต้นคือหน้า 1)
    per_page = 12 # 📌 กำหนดจำนวนหนังสือต่อ 1 หน้า (แก้ตัวเลขได้ตามต้องการ)

    # 1. ดึงข้อมูลจากฐานข้อมูล
    if search_query:
        # ค้นหาชื่อหนังสือ
        res = supabase.table("books").select("*").ilike("title", f"%{search_query}%").execute()
    else:
        # ดึงทั้งหมด
        res = supabase.table("books").select("*").execute()

    all_books = res.data
    total_books = len(all_books)

    # 2. คำนวณจำนวนหน้าทั้งหมด
    total_pages = math.ceil(total_books / per_page)

    # 3. ตัดแบ่งข้อมูลให้เหลือเฉพาะหน้าที่จะแสดง (Slicing)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_books = all_books[start:end]

    return render_template('admin_books.html', 
                           books=paginated_books, # ส่งข้อมูลที่ตัดแล้วไปแทน
                           total_books=total_books,
                           search_query=search_query,
                           page=page,
                           total_pages=total_pages)

@app.route("/admin/add_book", methods=["GET", "POST"])
def admin_add_book():
    if not is_admin(): return redirect(url_for("home"))

    msg = ""
    if request.method == "POST":
        title = request.form.get("title")
        price = request.form.get("price")
        stock_quantity = request.form.get("stock_quantity")
        
        # --- 🌟 ระบบจัดการรูปภาพ ---
        image_url = "" # ค่าเริ่มต้นถ้าไม่ได้อัปรูป
        
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file.filename != '':
                # 1. จัดการชื่อไฟล์ให้ปลอดภัย
                filename = secure_filename(file.filename)
                # 2. ใส่รหัสสุ่ม (UUID) นำหน้าชื่อไฟล์ ป้องกันชื่อไฟล์ซ้ำกัน
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                # 3. เซฟรูปลงโฟลเดอร์ static/uploads/
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(filepath)
                # 4. สร้าง Path เพื่อเอาไปเซฟลง Database
                image_url = f"/static/uploads/{unique_name}"

        try:
            # เพิ่มข้อมูลลง Supabase (รวม image_url ด้วย)
            supabase.table("books").insert({
                "title": title,
                "price": float(price),
                "stock_quantity": int(stock_quantity),
                "image_url": image_url
            }).execute()
            msg = f"เพิ่มหนังสือ '{title}' พร้อมรูปปกเรียบร้อยแล้ว!"
        except Exception as e:
            msg = f"❌ เกิดข้อผิดพลาด: {e}"

    return render_template("admin_add_book.html", msg=msg)

@app.route("/admin/edit_book/<int:id>", methods=["GET", "POST"])
def admin_edit_book(id):
    if not is_admin(): return redirect(url_for("home"))
    
    if request.method == "POST":
        title = request.form.get("title")
        price = float(request.form.get("price"))
        stock_quantity = int(request.form.get("stock_quantity"))
        
        # 1. เตรียมข้อมูลพื้นฐาน
        update_data = {
            "title": title,
            "price": price,
            "stock_quantity": stock_quantity
        }
        
        # 2. จัดการรูปภาพ (ถ้ามีการอัปโหลดมาใหม่)
        if 'image_file' in request.files:
            file = request.files['image_file']
            if file.filename != '':
                filename = secure_filename(file.filename)
                unique_name = f"{uuid.uuid4().hex}_{filename}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                file.save(filepath)
                
                # เพิ่ม path รูปใหม่เข้าไปในข้อมูลที่จะอัปเดต
                update_data["image_url"] = f"/static/uploads/{unique_name}"

        # 3. อัปเดตข้อมูลทั้งหมดโดยอ้างอิงจากตัวแปร id
        supabase.table("books").update(update_data).eq("id", id).execute()
        
        return redirect(url_for("admin_books"))
        
    # ดึงข้อมูลเล่มเดิมมาโชว์ในฟอร์ม
    res = supabase.table("books").select("*").eq("id", id).execute()
    book = res.data[0] if res.data else None
    
    return render_template("admin_edit_book.html", book=book)

@app.route("/admin/delete_book/<int:id>")
def admin_delete_book(id):
    if not is_admin(): return redirect(url_for("home"))
    supabase.table("books").delete().eq("id", id).execute()
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/users")
def admin_users():
    # ตรวจสอบสิทธิ์แอดมิน
    if not is_admin(): return redirect(url_for("home"))
    
    try:
        # 1. ดึงข้อมูล Users ทั้งหมด
        res_users = supabase.table("users").select("*").order("id", desc=True).execute()
        users = res_users.data
        
        # 2. ดึงข้อมูลออเดอร์ล่าสุด 4 รายการ (Recent Orders)
        res_orders = supabase.table("orders").select("id, user_email, total_price").order("id", desc=True).limit(4).execute()
        recent_orders = res_orders.data
        
        # 3. นับจำนวนออเดอร์ Pending และ Completed (Tasks)
        res_all_orders = supabase.table("orders").select("status").execute()
        all_orders = res_all_orders.data
        pending_count = sum(1 for o in all_orders if o['status'] == 'Pending')
        completed_count = sum(1 for o in all_orders if o['status'] == 'Completed')
        
    except Exception as e:
        print(f"Error fetching data for admin users page: {e}")
        users, recent_orders, pending_count, completed_count = [], [], 0, 0

    # ส่งตัวแปรทั้งหมดไปที่หน้าเว็บ
    return render_template("admin_users.html", 
                           users=users, 
                           recent_orders=recent_orders,
                           pending_count=pending_count,
                           completed_count=completed_count)

@app.route("/admin/user_list")
def admin_user_list():
    if not session.get("user") or session.get("user") != "admin@bookstore.com":
        return redirect(url_for("login"))
    
    # ดึงข้อมูลจากตาราง users เหมือนเดิมครับ
    try:
        response = supabase.table("users").select("*").execute()
        db_users = response.data
    except Exception as e:
        db_users = []
        print(f"Error fetching users: {e}")
        
    return render_template("admin_user_list.html", users=db_users)

# ==========================================
# หน้าการแจ้งเตือน (Notifications) - เวอร์ชัน 4 กล่อง
# ==========================================
@app.route("/admin/notifications")
def admin_notifications():
    if not is_admin(): return redirect(url_for("home"))
    
    notifications = []
    try:
        # 1. แจ้งเตือนทั่วไป (ลำดับเดิม)
        res = supabase.table("notifications").select("*").order("created_at", desc=True).execute()
        notifications = res.data if res.data else []
        
        # 2. เช็คสต๊อกใกล้หมด
        res_books = supabase.table("books").select("title, stock_quantity").gt("stock_quantity", 0).lt("stock_quantity", 5).execute()
        if res_books.data:
            for book in res_books.data:
                notifications.insert(0, {"type": "stock", "message": f"⚠️ '{book['title']}' ใกล้หมด! (เหลือ {book['stock_quantity']} เล่ม)", "created_at": "ระบบ"})
        
        # 3. เช็คพรีออเดอร์ครบเป้า
        res_pre = supabase.table("books").select("title, preorder_current, preorder_target").lte("stock_quantity", 0).execute()
        if res_pre.data:
            for book in res_pre.data:
                current = int(book.get("preorder_current") or 0)
                target = int(book.get("preorder_target") or 5)
                if current >= target:
                    notifications.insert(0, {"type": "preorder_success", "message": f"🎉 พรีออเดอร์ '{book['title']}' ครบเป้า! ({current}/{target})", "created_at": "ระบบ"})
    except Exception as e:
        print(f"Error: {e}")
        
    return render_template("admin_notifications.html", notifications=notifications)

# ----------------- ระบบชำระเงินจำลอง (Checkout) -----------------
@app.route("/shipping", methods=["GET", "POST"])
def shipping():
    # บังคับล็อกอิน
    user_email = session.get("user")
    if not user_email:
        return redirect(url_for("login"))
        
    cart_ids = session.get("cart", [])
    if not cart_ids:
        return redirect(url_for("cart"))

    # ดึงที่อยู่ล่าสุดที่ลูกค้าคนนี้เคยบันทึกไว้ในตาราง addresses
    try:
        address_res = supabase.table("addresses").select("*").eq("user_email", user_email).order("id", desc=True).limit(1).execute()
        saved_address = address_res.data[0] if address_res.data else None
    except:
        saved_address = None

    if request.method == "POST":
        address_option = request.form.get("address_option")

        if address_option == "saved" and saved_address:
            # ใช้ที่อยู่เดิมที่ดึงมาได้ ไม่ต้องเพิ่มลงฐานข้อมูลใหม่
            session['current_address_id'] = saved_address['id']
            return redirect(url_for("checkout"))
            
        else:
            # ผู้ใช้เลือกกรอกที่อยู่ใหม่ ให้บันทึกลงตาราง
            address_data = {
                "full_name": request.form.get("full_name"),
                "phone": request.form.get("phone"),
                "address_detail": request.form.get("address_detail"),
                "sub_district": request.form.get("sub_district"),
                "district": request.form.get("district"),
                "province": request.form.get("province"),
                "postal_code": request.form.get("postal_code"),
                "user_email": user_email
            }
            try:
                res = supabase.table("addresses").insert(address_data).execute()
                if res.data:
                    # เก็บ ID ที่อยู่ใหม่เข้า Session
                    session['current_address_id'] = res.data[0]['id']
                return redirect(url_for("checkout"))
            except Exception as e:
                return f"<div style='padding: 50px; text-align: center; color: red;'><h2>เกิดข้อผิดพลาดจาก Supabase</h2><p>{str(e)}</p></div>"

    # โยนตัวแปร saved_address ไปให้ HTML แสดงผลกล่อง "ที่อยู่เดิม"
    return render_template("shipping.html", address=saved_address)

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
        address_id = session.get('current_address_id')
        
       # 1. บันทึกบิลหลักก่อน และรับค่า order_id กลับมา
        order_res = supabase.table("orders").insert({
            "user_email": session["user"],
            "total_price": total,
            "status": "Pending",
            "slip_image_url": slip_url,
            "address_id": address_id
        }).execute()

        # --- 🌟 โค้ดที่เพิ่มใหม่: ส่งแจ้งเตือนแอดมิน ---
        supabase.table("notifications").insert({
            "type": "order",
            "message": f"📦 มีคำสั่งซื้อใหม่! จาก {session['user']} รอตรวจสอบสลิป"
        }).execute()
        # ---------------------------------------

        # 2. นำของในตะกร้ามาบันทึกลงตาราง order_items
        if order_res.data:
            new_order_id = order_res.data[0]['id'] # ได้ ID ของบิลที่เพิ่งสร้าง
            
            # นับจำนวนหนังสือแต่ละเล่มในตะกร้า (เผื่อซื้อเล่มซ้ำ)
            from collections import Counter
            item_counts = Counter(cart_ids)
            
            # ดึงชื่อหนังสือจากฐานข้อมูลเพื่อเตรียมเซฟ
            res_books = supabase.table("books").select("id, title, price").in_("id", list(item_counts.keys())).execute()
            db_books_info = {b['id']: b for b in res_books.data}
            
            order_items_data = []
            for b_id, qty in item_counts.items():
                if b_id in db_books_info:
                    book_info = db_books_info[b_id]
                    order_items_data.append({
                        "order_id": new_order_id,
                        "book_title": book_info['title'],
                        "price": book_info['price'],
                        "quantity": qty
                    })
            
            # ยัดรายการหนังสือทั้งหมดลงตาราง order_items ทีเดียว!
            if order_items_data:
                supabase.table("order_items").insert(order_items_data).execute()

        # ล้างตะกร้าสินค้า
        session.pop("cart", None)
        return render_template("checkout_success.html")

    return render_template("checkout.html", total=total)

@app.route("/admin/approve_order/<int:order_id>")
def admin_approve_order(order_id):
    if not is_admin(): return redirect(url_for("home"))

    try:
        # 1. ดึงรายการสินค้าโดยใช้ book_title แทน
        items_res = supabase.table("order_items").select("book_title, quantity").eq("order_id", order_id).execute()
        items = items_res.data

        if items:
            for item in items:
                b_title = item['book_title']
                qty_bought = item['quantity']

                # 2. ค้นหาหนังสือในตาราง books ด้วย "ชื่อหนังสือ" (title)
                book_res = supabase.table("books").select("id, stock_quantity").eq("title", b_title).execute()
                
                # ถ้าเจอหนังสือชื่อนี้ในระบบ
                if book_res.data:
                    book_data = book_res.data[0] # ดึงข้อมูลเล่มที่ค้นเจอมา
                    b_id = book_data['id']
                    current_stock = book_data.get('stock_quantity', 0)
                    
                    # คำนวณสต๊อกใหม่ (ห้ามติดลบ)
                    new_stock = max(0, current_stock - qty_bought)

                    # 3. อัปเดตสต๊อกกลับไปที่ตาราง books
                    supabase.table("books").update({"stock_quantity": new_stock}).eq("id", b_id).execute()
                    print(f"📦 ตัดสต๊อก '{b_title}': {current_stock} -> {new_stock}")

        # 4. เปลี่ยนสถานะออเดอร์เป็น completed
        supabase.table("orders").update({"status": "completed"}).eq("id", order_id).execute()
        
    except Exception as e:
        print(f"❌ พังตรงนี้: {e}")

    return redirect(url_for("admin_orders"))

@app.route('/admin/delete_user/<user_id>', methods=['POST'])
def delete_user(user_id):
    # 1. เช็คสิทธิ์ก่อนว่าใช่ Admin จริงไหม (เพื่อความปลอดภัย)
    if 'user' not in session or session.get('role') != 'admin':
        return redirect('/') 

    try:
        # 2. สั่งลบข้อมูล user คนนั้นออกจากฐานข้อมูล Supabase
        supabase.table('users').delete().eq('id', user_id).execute()
        
        # (ออปชันเสริม) ถ้ามีระบบแจ้งเตือน flash message ก็ให้มันทำงานตรงนี้
        # flash('ลบผู้ใช้งานเรียบร้อยแล้ว', 'success')
        
    except Exception as e:
        print(f"Error deleting user: {e}")
        
    # 3. ลบเสร็จแล้ว ให้เด้งกลับมาที่หน้าตารางผู้ใช้เหมือนเดิม
    return redirect('/admin/users')

@app.route('/admin/add_user', methods=['POST'])
def admin_add_user():
    # 1. เช็คว่าใช่ Admin หรือเปล่า
    if 'user' not in session or session.get('role') != 'admin':
        return redirect('/')

    # 2. รับค่าจากฟอร์ม Popup
    email = request.form.get('email')
    password = request.form.get('password')

    try:
        # 3. สั่งสร้างผู้ใช้ใหม่ในระบบ Auth (เดี๋ยว Trigger ในฐานข้อมูลจะทำงานต่อเอง!)
        supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        # --- 🌟 โค้ดที่เพิ่มใหม่: ส่งแจ้งเตือนแอดมิน ---
        supabase.table("notifications").insert({
            "type": "user",
            "message": f"🎉 แอดมินได้เพิ่มสมาชิกใหม่: {email} เข้าสู่ระบบ"
        }).execute()
        # ---------------------------------------       
    except Exception as e:
        print(f"Error adding user: {e}")

    # 4. เสร็จแล้วเด้งกลับมาที่หน้าตาราง
    return redirect('/admin/users')

@app.route('/admin/edit_user', methods=['POST'])
def edit_user():
    # เช็คสิทธิ์ Admin
    if 'user' not in session or session.get('role') != 'admin':
        return redirect('/')

    # รับค่า ID และ Role ใหม่จากฟอร์ม
    user_id = request.form.get('user_id')
    new_role = request.form.get('role')

    print(f"👉 กำลังอัปเดต User ID: {user_id} ให้เป็นตำแหน่ง: {new_role}") 

    try:
        # สั่งอัปเดต
        res = supabase.table('users').update({'role': new_role}).eq('id', user_id).execute()
        print(f"✅ อัปเดตสำเร็จ: {res}")
    except Exception as e:
        print(f"❌ โค้ดพัง! สาเหตุ: {e}")

    return redirect('/admin/users')

@app.route("/my_orders")
def my_orders():
    if not session.get("user"):
        return redirect(url_for("login"))
        
    user_email = session.get("user")
    
    try:
        # 1. ดึงออเดอร์ทั้งหมดของคนนี้
        res = supabase.table("orders").select("*").eq("user_email", user_email).order("id", desc=True).execute()
        orders = res.data
        
        # 2. ดึงรายการหนังสือ (order_items) มายัดใส่แต่ละออเดอร์
        if orders:
            order_ids = [o['id'] for o in orders]
            # ดึง items ทั้งหมดที่เป็นของออเดอร์ในลิสต์
            items_res = supabase.table("order_items").select("*").in_("order_id", order_ids).execute()
            all_items = items_res.data
            
            # จัดกลุ่มไอเทมใส่เข้าไปในออเดอร์แต่ละใบ
            for order in orders:
                order['order_items'] = [item for item in all_items if item['order_id'] == order['id']]
                
    except Exception as e:
        print(f"Error fetching my orders: {e}")
        orders = []

    return render_template("my_orders.html", orders=orders)

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if not session.get("user"):
        return redirect(url_for("login"))
    
    user_email = session.get("user")
    
    if request.method == "POST":
        # รับค่าจากฟอร์มแก้ไขที่อยู่
        full_name = request.form.get("full_name")
        phone = request.form.get("phone")
        address_detail = request.form.get("address_detail")
        sub_district = request.form.get("sub_district")
        district = request.form.get("district")
        province = request.form.get("province")
        postal_code = request.form.get("postal_code")
        
        # เช็คว่าเคยมีที่อยู่หรือยัง
        res = supabase.table("addresses").select("id").eq("user_email", user_email).execute()
        
        addr_data = {
            "user_email": user_email,
            "full_name": full_name,
            "phone": phone,
            "address_detail": address_detail,
            "sub_district": sub_district,
            "district": district,
            "province": province,
            "postal_code": postal_code
        }
        
        if res.data:
            # มีแล้วให้ Update
            supabase.table("addresses").update(addr_data).eq("user_email", user_email).execute()
        else:
            # ยังไม่มีให้ Insert
            supabase.table("addresses").insert(addr_data).execute()
            
        return redirect(url_for("profile", msg="อัปเดตข้อมูลเรียบร้อยแล้ว!"))

    # ดึงข้อมูลมาโชว์ในหน้าเว็บ
    user_res = supabase.table("users").select("*").eq("email", user_email).single().execute()
    addr_res = supabase.table("addresses").select("*").eq("user_email", user_email).execute()
    
    address = addr_res.data[0] if addr_res.data else {}
    
    return render_template("profile.html", user=user_res.data, address=address, msg=request.args.get("msg"))

# =========================================
# ระบบเพิ่มยอดพรีออเดอร์ (เมื่อมีคนกดจอง)
# =========================================
@app.route("/pledge/<int:book_id>", methods=["POST"])
def pledge_preorder(book_id):
    # 1. เช็คว่าลูกค้า Login หรือยัง
    user_email = session.get('user')
    
    if not user_email:
        # ถ้ายังไม่ Login ให้เด้งไปหน้า Login ก่อน
        return redirect(url_for("login"))

    # 2. เช็คจาก Database ว่า Email นี้ เคยจองเล่มนี้ไปหรือยัง? (กันสแปมของจริง)
    check_res = supabase.table("preorder_logs") \
        .select("*") \
        .eq("user_email", user_email) \
        .eq("book_id", book_id) \
        .execute()
    
    if check_res.data:
        # ถ้าเคยกดจองแล้ว ให้เด้งกลับหน้าเดิม
        return redirect(url_for("preorder"))

    # 3. บันทึกข้อมูลการจองลงตาราง preorder_logs
    preorder_data = {
        "user_email": user_email,
        "book_id": book_id
    }
    supabase.table("preorder_logs").insert(preorder_data).execute()

    # 4. ไปบวกเลขยอดจองในตาราง books เพิ่มขึ้น 1
    book_res = supabase.table("books").select("preorder_current").eq("id", book_id).single().execute()
    if book_res.data:
        current_count = book_res.data.get("preorder_current") or 0
        supabase.table("books").update({"preorder_current": current_count + 1}).eq("id", book_id).execute()

    return redirect(url_for("preorder"))

# ----------------- ระบบค้นหาอัจฉริยะ (AI Search) -----------------
@app.route("/search_ai")
def search_ai():
    query = request.args.get('q', '').strip()
    if not query:
        return redirect(url_for("home"))

    try:
        # 1. แปลงคำค้นหาของลูกค้าเป็นตัวเลข (Vector 384 มิติ)
        query_vector = search_model.encode(query).tolist()
        
        # 2. ส่งไปค้นหาใน Supabase ผ่านฟังก์ชัน match_books ที่เราสร้างไว้ใน SQL Editor
        res = supabase.rpc('match_books', {
            'query_embedding': query_vector,
            'match_threshold': 0.2, # ปรับความกว้างของการค้นหา (0.1 กว้างมาก, 0.5 แม่นยำสูง)
            'match_count': 10       # เอามาโชว์ 10 เล่ม
        }).execute()
        
        search_results = res.data if res.data else []
        
    except Exception as e:
        print(f"❌ AI Search Error: {e}")
        search_results = []

    # ใช้หน้า search_results.html เดิมโชว์ผลลัพธ์ได้เลย
    return render_template("search_results.html", books=search_results, query=query, is_ai=True)

if __name__ == "__main__":
    # Render ต้องการพอร์ตจาก Environment Variable
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)