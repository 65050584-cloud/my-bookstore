from sentence_transformers import SentenceTransformer
from supabase import create_client, Client

# --- ตั้งค่า Supabase ---
SUPABASE_URL = "https://jpapplzlvkekcosbajie.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpwYXBwbHpsdmtla2Nvc2JhamllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEyMjg4NDUsImV4cCI6MjA4NjgwNDg0NX0.ZYLW5yNuHwyfVFLh3LRZ4QbM3SkfQPuiy_XbiXy1or4"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# โหลดโมเดลมาไว้ในเครื่อง (รันครั้งแรกจะช้านิดหน่อยเพื่อโหลดโมเดล)
print("⏳ กำลังโหลดโมเดล AI เข้าเครื่อง...")
model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2') 

def update_all_books():
    books = supabase.table("books").select("id, title, description").execute()
    
    for book in books.data:
        content = f"{book['title']} {book.get('description', '')}"
        print(f"🤖 กำลังประมวลผล: {book['title']}")
        
        # แปลงเป็นตัวเลข (Vector)
        vector = model.encode(content).tolist()
        
        # อัปเดตลง Supabase
        supabase.table("books").update({"embedding": vector}).eq("id", book['id']).execute()
        print(f"✅ สำเร็จ!")

if __name__ == "__main__":
    update_all_books()