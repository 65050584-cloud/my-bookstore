import asyncio
import edge_tts
import os

# ข้อความที่อยากให้ AI อ่าน
TEXT = "สวัสดีค่ะ ยินดีต้อนรับสู่ร้านหนังสือของเรา วันนี้มีนิยายสืบสวนสอบสวนมาใหม่หลายเล่มเลยค่ะ ลองแวะชมดูก่อนได้นะคะ"
VOICE = "th-TH-PremwadeeNeural" 

# กำหนดโฟลเดอร์ปลายทาง
SAVE_FOLDER = "static/uploads"
OUTPUT_AUDIO = f"{SAVE_FOLDER}/test_audio.mp3"
OUTPUT_SUB = f"{SAVE_FOLDER}/test_audio.vtt"

# ฟังก์ชันสำหรับแปลงตัวเลขเวลาของ AI ให้เป็นฟอร์แมต VTT (00:00:00.000)
def format_vtt_time(time_in_100ns):
    total_ms = int(time_in_100ns / 10000)
    hours = total_ms // 3600000
    minutes = (total_ms % 3600000) // 60000
    seconds = (total_ms % 60000) // 1000
    milliseconds = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

async def generate_audio_and_subs():
    if not os.path.exists(SAVE_FOLDER):
        os.makedirs(SAVE_FOLDER)
        print(f"📁 สร้างโฟลเดอร์ {SAVE_FOLDER} ให้แล้วครับ!")

    print(f"⏳ กำลังสร้างเสียง AI ({VOICE})...")
    
    communicate = edge_tts.Communicate(TEXT, VOICE)
    
    # เริ่มต้นสร้างเนื้อหาสำหรับไฟล์ Subtitle (VTT)
    vtt_content = "WEBVTT\n\n"
    
    with open(OUTPUT_AUDIO, "wb") as audio_file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                # บันทึกไฟล์เสียง
                audio_file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # สร้างข้อความ VTT แบบ Manual เลย
                start_time = format_vtt_time(chunk["offset"])
                end_time = format_vtt_time(chunk["offset"] + chunk["duration"])
                text = chunk["text"]
                vtt_content += f"{start_time} --> {end_time}\n{text}\n\n"

    # บันทึกไฟล์ VTT
    with open(OUTPUT_SUB, "w", encoding="utf-8") as sub_file:
        sub_file.write(vtt_content)
        
    print(f"✅ เสร็จแล้ว! เข้าไปดูไฟล์ในโฟลเดอร์ {SAVE_FOLDER} ได้เลยครับ")

if __name__ == "__main__":
    asyncio.run(generate_audio_and_subs())