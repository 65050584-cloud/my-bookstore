import asyncio
import edge_tts
import os
import re  
from supabase import create_client, Client

# ---------------------------------------------------------
# 1. ตั้งค่าการเชื่อมต่อ Supabase (ก๊อปจาก app.py มาใส่ได้เลย)
# ---------------------------------------------------------
SUPABASE_URL = "https://jpapplzlvkekcosbajie.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpwYXBwbHpsdmtla2Nvc2JhamllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzEyMjg4NDUsImV4cCI6MjA4NjgwNDg0NX0.ZYLW5yNuHwyfVFLh3LRZ4QbM3SkfQPuiy_XbiXy1or4" # <--- ก๊อป KEY ยาวๆ จาก app.py มาใส่
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

VOICE = "th-TH-PremwadeeNeural" 
SAVE_FOLDER = "static/uploads"

def format_vtt_time(time_in_100ns):
    total_ms = int(time_in_100ns / 10000)
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

async def generate_audio_for_book(book_id):
    print(f"🔍 กำลังค้นหาข้อมูลหนังสือ ID: {book_id}...")
    
    # 2. ดึงข้อมูลหนังสือจาก Supabase
    res = supabase.table("books").select("*").eq("id", book_id).single().execute()
    book = res.data

    if not book or not book.get("description"):
        print(f"❌ ไม่พบหนังสือ ID {book_id} หรือเล่มนี้ยังไม่มี description ครับ")
        return

    # -------- แก้ไขตรงนี้ --------
    raw_text = book["description"]
    
    # 1. ลบเครื่องหมายคำพูด
    clean_text = raw_text.replace("“", "").replace("”", "").replace('"', "")
    
    # 2. ไม้ตาย: เปลี่ยนช่องว่างแปลกๆ ทุกชนิด (รวมถึง \xa0) ให้กลายเป็นช่องว่างปกติช่องเดียว
    clean_text = re.sub(r'\s+', ' ', clean_text)
    
    # 3. ตัดเอาแค่ 500 ตัวอักษร และลบช่องว่างหัวท้าย
    text_to_read = clean_text[:500].strip() 
    
    print(f"📖 กำลังให้ AI อ่าน: {text_to_read}")

    if not os.path.exists(SAVE_FOLDER):
        os.makedirs(SAVE_FOLDER)

    # 3. ตั้งชื่อไฟล์ตาม ID หนังสือ (เช่น book_1.mp3)
    audio_path = f"{SAVE_FOLDER}/book_{book_id}.mp3"
    vtt_path = f"{SAVE_FOLDER}/book_{book_id}.vtt"

    communicate = edge_tts.Communicate(text_to_read, VOICE)
    vtt_content = "WEBVTT\n\n"

    # 4. สร้างไฟล์เสียงและไฟล์ VTT
    with open(audio_path, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_time = format_vtt_time(chunk["offset"])
                end_time = format_vtt_time(chunk["offset"] + chunk["duration"])
                vtt_content += f"{start_time} --> {end_time}\n{chunk['text']}\n\n"

    with open(vtt_path, "w", encoding="utf-8") as sub_file:
        sub_file.write(vtt_content)

    print("✅ สร้างไฟล์เสียงสำเร็จ! กำลังอัปเดตฐานข้อมูล...")

    # 5. อัปเดตลิงก์ไฟล์กลับลงไปในตาราง books
    supabase.table("books").update({
        "audio_url": f"/{audio_path}",
        "vtt_url": f"/{vtt_path}",
        "is_audiobook": True
    }).eq("id", book_id).execute()

    print(f"🎉 เสร็จสมบูรณ์! ตอนนี้หนังสือเล่ม {book_id} พร้อมให้ทดลองฟังบนเว็บแล้ว")

if __name__ == "__main__":
    import sys
    # เพิ่ม 2 บรรทัดนี้เพื่อแก้บั๊กการเชื่อมต่อบน Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    TARGET_BOOK_ID = 2 
    asyncio.run(generate_audio_for_book(TARGET_BOOK_ID))