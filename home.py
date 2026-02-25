import os
import time
import io
import concurrent.futures  # 🚀 新增：用來啟用多執行緒（並行處理）
from flask import Flask, request, render_template_string, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags

app = Flask(__name__)

# ================= 🔧 全域參數設定區域 🔧 =================
OUTPUT_LIGHT_FILENAME = "hasselblad_output_light.jpg"
OUTPUT_DARK_FILENAME = "hasselblad_output_dark.jpg"

INPUT_TEMP_FILENAME = "temp_uploaded_image.jpg" 
LOGO_FILENAME = "logo.jpg"
FAVICON_FILENAME = "favicon.jpg"

FONT_FILENAME = "Inter_28pt-Light.ttf"  

# --- 主題顏色設定 ---
THEMES = {
    'light': {
        'bg_color': 'white',               
        'logo_rgb': (135, 135, 135),       
        'text_hex': "#6E6E6E"              
    },
    'dark': {
        'bg_color': '#000000',             
        'logo_rgb': (220, 220, 220),       
        'text_hex': "#A0A0A0"              
    }
}

# ✅ 完全保留你辛苦調整的完美版面參數
LOGO_THRESHOLD = 240               
BORDER_SIDE_RATIO = 0.026          
BORDER_BOTTOM_RATIO = 0.14         
LOGO_WIDTH_RATIO = 0.25            
FONT_SIZE_RATIO = 0.014             
TEXT_LETTER_SPACING_RATIO = 0.002  
SPACING_IMAGE_TO_LOGO_RATIO = 0.16 
SPACING_LOGO_TO_TEXT_RATIO = 0.045 
# ========================================================


def process_jpg_logo(jpg_path, target_color_rgb):
    """將白底黑字 JPG 去背並上色"""
    img = Image.open(jpg_path).convert("RGBA")
    datas = img.getdata()
    newData = []
    threshold = LOGO_THRESHOLD
    for item in datas:
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            newData.append((255, 255, 255, 0))
        else:
            newData.append((target_color_rgb[0], target_color_rgb[1], target_color_rgb[2], 255))
    img.putdata(newData)
    return img

def get_auto_exif_string(img):
    """自動從圖片解析 EXIF 資訊"""
    try:
        exif_data = img.getexif()
        if not exif_data:
            return "SHOT ON HASSELBLAD" 

        exif = {}
        for k, v in exif_data.items():
            if k in ExifTags.TAGS:
                exif[ExifTags.TAGS[k]] = v
        
        try:
            exif_ifd = exif_data.get_ifd(0x8769) 
            for k, v in exif_ifd.items():
                if k in ExifTags.TAGS:
                    exif[ExifTags.TAGS[k]] = v
        except Exception:
            pass

        model = str(exif.get('Model', '')).strip()
        lens = str(exif.get('LensModel', '')).strip()

        f_number = exif.get('FNumber')
        f_stop = f"F {float(f_number):.1f}".replace('.0', '') if f_number else ""

        exposure_time = exif.get('ExposureTime')
        shutter = ""
        if exposure_time:
            val = float(exposure_time)
            if val >= 1:
                shutter = f"{val:g} SEC"
            else:
                shutter = f"1/{int(round(1/val))} SEC"

        iso_val = exif.get('ISOSpeedRatings')
        iso_str = f"ISO {iso_val}" if iso_val else ""

        parts = [p for p in [f_stop, shutter, iso_str, model, lens] if p]
        
        if not parts:
            return "SHOT ON HASSELBLAD"
            
        return " | ".join(parts)
        
    except Exception as e:
        print(f"⚠️ 讀取 EXIF 時發生錯誤: {e}")
        return "SHOT ON HASSELBLAD"

# --- 哈蘇官網風格前端 ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hasselblad Camera Mark</title>
    <link rel="icon" type="image/jpeg" href="/favicon">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400&display=swap" rel="stylesheet">
    <style>
        body {
            background-color: #000000;
            color: #ffffff;
            font-family: 'Inter', sans-serif;
            margin: 0;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        .sidebar {
            width: 30%;
            padding: 4rem 3rem;
            background-color: #050505;
            border-right: 1px solid #3a3a3a;
            display: flex;
            flex-direction: column;
            box-sizing: border-box;
            z-index: 10;
        }
        .brand-logo {
            height: 24px;
            object-fit: contain;
            object-position: left;
            margin-bottom: 4rem;
            opacity: 0.9;
        }
        .main-gallery {
            width: 70%;
            background-color: #111;
            display: flex;
            flex-direction: column; 
            align-items: center;
            justify-content: center;
            box-sizing: border-box;
            padding: 2rem;
            position: relative;
        }
        
        .form-group { margin-bottom: 2.5rem; width: 100%; }
        label {
            display: block;
            margin-bottom: 0.5rem;
            font-size: 0.75rem;
            letter-spacing: 0.1em;
            color: #888;
            text-transform: uppercase;
        }
        
        input[type="file"] { color: #aaa; font-size: 0.85em; padding: 10px 0; }
        input[type="file"]::file-selector-button {
            background: transparent; color: #fff; border: 1px solid #555;
            padding: 8px 16px; margin-right: 15px; cursor: pointer;
            transition: all 0.3s; font-family: 'Inter', sans-serif; letter-spacing: 0.05em;
        }
        input[type="file"]::file-selector-button:hover { border-color: #fff; background: #fff; color: #000; }

        .btn-group { display: flex; flex-direction: column; gap: 15px; margin-top: 1rem; }
        .btn {
            background: transparent; color: #fff; border: 1px solid #fff;
            padding: 14px 20px; font-size: 0.8rem; letter-spacing: 0.15em;
            text-transform: uppercase; cursor: pointer; transition: all 0.4s ease;
            text-align: center; text-decoration: none;
        }
        .btn:hover { background: #fff; color: #000; }
        
        .compare-wrapper {
            position: relative;
            display: inline-block;
            max-height: 75vh; 
            max-width: 90%;
            box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08), 0 20px 50px rgba(0,0,0,0.8);
            opacity: 0;
            animation: fadeIn 0.8s forwards;
            margin-bottom: 30px; 
        }
        .compare-img {
            display: block;
            max-height: 75vh;
            max-width: 100%;
            width: auto;
            height: auto;
        }
        .compare-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 50%;
            height: 100%;
            overflow: hidden;
        }
        .compare-overlay img {
            display: block;
            height: 100%;
            max-width: none;
        }
        .compare-slider {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            margin: 0;
            opacity: 0; 
            cursor: ew-resize;
            z-index: 10;
        }
        .compare-handle {
            position: absolute;
            top: 0;
            left: 50%;
            bottom: 0;
            width: 2px;
            background: rgba(255, 255, 255, 0.8);
            pointer-events: none;
            transform: translateX(-50%);
            z-index: 5;
            box-shadow: 0 0 15px rgba(0,0,0,0.8);
        }
        .compare-handle::after {
            content: '';
            position: absolute;
            top: 50%;
            left: 50%;
            width: 44px;
            height: 44px;
            background: rgba(0, 0, 0, 0.6);
            border: 2px solid rgba(255, 255, 255, 0.9);
            border-radius: 50%;
            transform: translate(-50%, -50%);
            backdrop-filter: blur(4px);
        }
        .compare-handle::before {
            content: '◄  ►';
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            color: #fff;
            font-size: 11px;
            letter-spacing: -1px;
            z-index: 2;
        }

        .download-controls {
            display: flex;
            justify-content: center;
            gap: 20px;
            width: 100%;
            opacity: 0;
            animation: fadeIn 0.8s forwards 0.2s;
        }
        .download-btn {
            padding: 8px 18px;
            font-size: 0.65rem; 
            letter-spacing: 0.15em;
            text-transform: uppercase;
            text-decoration: none;
            transition: all 0.3s ease;
            border: 1px solid transparent;
        }
        
        .btn-theme-light { background: #fff; color: #000; border-color: #fff; }
        .btn-theme-light:hover { background: transparent; color: #fff; border-color: #fff; }
        .btn-theme-dark { background: transparent; color: #aaa; border-color: #555; }
        .btn-theme-dark:hover { background: #fff; color: #000; border-color: #fff; }

        .empty-state { color: #444; font-weight: 200; letter-spacing: 0.1em; text-transform: uppercase; }

        @keyframes fadeIn { to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <img src="/web-logo" class="brand-logo" alt="Brand Logo">
        
        <form action="/" method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label>CAMERA MARK</label>
                <p style="font-size: 0.7rem; color: #555; margin-bottom: 10px;">Upload</p>
                <input type="file" name="image" accept="image/*">
            </div>
            
            {% if error_msg %}
            <div style="color: #ff5555; font-size: 0.75rem; letter-spacing: 0.1em; margin-bottom: 15px;">⚠️ {{ error_msg }}</div>
            {% endif %}

            <div class="btn-group">
                <button type="submit" class="btn">Generate</button>
            </div>
        </form>
    </div>

    <div class="main-gallery">
        {% if show_preview %}
            <div class="compare-wrapper">
                <img src="/image/dark?t={{ timestamp }}" class="compare-img" id="base-img" alt="Dark Edition">
                <div class="compare-overlay" id="compare-overlay">
                    <img src="/image/light?t={{ timestamp }}" id="overlay-img" alt="Light Edition">
                </div>
                <div class="compare-handle" id="compare-handle"></div>
                <input type="range" min="0" max="100" value="50" class="compare-slider" id="compare-slider">
            </div>

            <div class="download-controls">
                <a href="/download/light" class="download-btn btn-theme-light">Download Light</a>
                <a href="/download/dark" class="download-btn btn-theme-dark">Download Dark</a>
            </div>
        {% else %}
            <div class="empty-state">Studio is ready</div>
        {% endif %}
    </div>

    <script>
        {% if show_preview %}
        const slider = document.getElementById('compare-slider');
        const overlay = document.getElementById('compare-overlay');
        const handle = document.getElementById('compare-handle');
        const baseImg = document.getElementById('base-img');
        const overlayImg = document.getElementById('overlay-img');

        function syncImgWidth() {
            overlayImg.style.width = baseImg.getBoundingClientRect().width + 'px';
        }

        if (baseImg.complete) { syncImgWidth(); } 
        else { baseImg.onload = syncImgWidth; }
        window.addEventListener('resize', syncImgWidth);

        slider.addEventListener('input', function(e) {
            const val = e.target.value;
            overlay.style.width = val + '%';
            handle.style.left = val + '%';
        });
        {% endif %}
    </script>
</body>
</html>
"""

def add_frame_with_logo(img, text_info, logo_path, theme_key):
    theme = THEMES[theme_key]
    w, h = img.size
    
    long_edge = max(w, h)
    border_side = int(long_edge * BORDER_SIDE_RATIO)
    border_bottom = int(long_edge * BORDER_BOTTOM_RATIO)

    new_w = w + border_side * 2
    new_h = h + border_side + border_bottom

    new_img = Image.new('RGB', (new_w, new_h), theme['bg_color'])
    new_img.paste(img, (border_side, border_side))

    draw = ImageDraw.Draw(new_img)

    try:
        info_font = ImageFont.truetype(FONT_FILENAME, int(long_edge * FONT_SIZE_RATIO))
    except Exception:
        info_font = ImageFont.load_default()

    logo_y_end = 0

    if os.path.exists(logo_path):
        logo = process_jpg_logo(logo_path, theme['logo_rgb'])
        logo_w = int(long_edge * LOGO_WIDTH_RATIO)
        aspect = logo.height / logo.width
        logo_h = int(logo_w * aspect)
        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        
        logo_x = int((new_w - logo_w) / 2)
        logo_y = h + border_side + int(border_bottom * SPACING_IMAGE_TO_LOGO_RATIO)
        
        new_img.paste(logo, (logo_x, logo_y), logo)
        logo_y_end = logo_y + logo_h
    else:
        fallback_font = info_font
        fallback_text = "[ Logo Not Found ]"
        logo_w = draw.textlength(fallback_text, font=fallback_font)
        logo_x = (new_w - logo_w) / 2
        logo_y = h + border_side + int(border_bottom * SPACING_IMAGE_TO_LOGO_RATIO)
        draw.text((logo_x, logo_y), fallback_text, fill="red", font=fallback_font)
        logo_y_end = logo_y + int(long_edge * FONT_SIZE_RATIO)

    letter_spacing = int(long_edge * TEXT_LETTER_SPACING_RATIO)

    total_text_w = 0
    for char in text_info:
        total_text_w += draw.textlength(char, font=info_font) + letter_spacing
    if len(text_info) > 0:
        total_text_w -= letter_spacing 

    start_x = (new_w - total_text_w) / 2
    text_y = logo_y_end + int(border_bottom * SPACING_LOGO_TO_TEXT_RATIO)

    current_x = start_x
    for char in text_info:
        draw.text((current_x, text_y), char, fill=theme['text_hex'], font=info_font)
        current_x += draw.textlength(char, font=info_font) + letter_spacing

    return new_img

@app.route('/favicon')
def serve_favicon():
    if os.path.exists(FAVICON_FILENAME):
        return send_file(FAVICON_FILENAME, mimetype='image/jpeg')
    return "", 404

@app.route('/web-logo')
def serve_web_logo():
    if os.path.exists(LOGO_FILENAME):
        web_logo = process_jpg_logo(LOGO_FILENAME, (255, 255, 255))
        bbox = web_logo.getbbox()
        if bbox:
            web_logo = web_logo.crop(bbox)
        img_io = io.BytesIO()
        web_logo.save(img_io, 'PNG') 
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    return "", 404

# 🚀 執行任務的輔助函數，用於多執行緒
def process_and_save_frame(img, exif_str, theme):
    filename = OUTPUT_LIGHT_FILENAME if theme == 'light' else OUTPUT_DARK_FILENAME
    framed_img = add_frame_with_logo(img, exif_str, LOGO_FILENAME, theme)
    # 💡 存檔優化：quality=95 與 subsampling=0 (高畫質+極速壓縮)
    framed_img.save(filename, quality=100, subsampling=0)

@app.route('/', methods=['GET', 'POST'])
def index():
    show_preview = False
    has_temp_img = os.path.exists(INPUT_TEMP_FILENAME)
    error_msg = None 
    
    if request.method == 'POST':
        file = request.files.get('image')

        # 防呆邏輯：若無檔案且無暫存則報錯，有暫存則自動帶入
        if not file or file.filename == '':
            if has_temp_img:
                use_temp = True
            else:
                use_temp = False
                error_msg = "PLEASE SELECT AN IMAGE FIRST."
        else:
            use_temp = False

        if not error_msg:
            try:
                if use_temp and has_temp_img:
                    img_orig = Image.open(INPUT_TEMP_FILENAME)
                else:
                    img_orig = Image.open(file)
                    
                    exif_bytes = img_orig.info.get('exif', b'')
                    
                    if img_orig.mode in ('RGBA', 'P'):
                        img_orig = img_orig.convert('RGB')
                    
                    if exif_bytes:
                        img_orig.save(INPUT_TEMP_FILENAME, exif=exif_bytes)
                    else:
                        img_orig.save(INPUT_TEMP_FILENAME)
                    has_temp_img = True 

                extracted_exif_string = get_auto_exif_string(img_orig)

                if img_orig.mode in ('RGBA', 'P'):
                    img_orig = img_orig.convert('RGB')

                # 翻轉並修正 EXIF 寫入的方向
                img_orig = ImageOps.exif_transpose(img_orig)
                
                # 🚀 雙核並行運算：同時處理「亮色版」與「暗色版」
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 派發兩個任務同時執行
                    future_light = executor.submit(process_and_save_frame, img_orig, extracted_exif_string, 'light')
                    future_dark = executor.submit(process_and_save_frame, img_orig, extracted_exif_string, 'dark')
                    
                    # 等待兩個工人都做完
                    concurrent.futures.wait([future_light, future_dark])

                show_preview = True
                
            except Exception as e:
                error_msg = f"PROCESSING FAILED: {str(e)}"

    return render_template_string(HTML_TEMPLATE, 
                                  show_preview=show_preview, 
                                  timestamp=int(time.time()),
                                  has_temp_img=has_temp_img,
                                  error_msg=error_msg)

@app.route('/image/<theme>')
def get_image(theme):
    filename = OUTPUT_LIGHT_FILENAME if theme == 'light' else OUTPUT_DARK_FILENAME
    if os.path.exists(filename):
        return send_file(filename, mimetype='image/jpeg')
    return "Image not found", 404

@app.route('/download/<theme>')
def download_image(theme):
    filename = OUTPUT_LIGHT_FILENAME if theme == 'light' else OUTPUT_DARK_FILENAME
    if os.path.exists(filename):
        theme_name = "Light" if theme == 'light' else "Dark"
        dl_name = f'Hasselblad_{theme_name}_{int(time.time())}.jpg'
        return send_file(filename, mimetype='image/jpeg', as_attachment=True, download_name=dl_name)
    return "File not found", 404

import os
import time
import io
import concurrent.futures
from flask import Flask, request, render_template_string, send_file
from PIL import Image, ImageDraw, ImageFont, ImageOps, ExifTags

app = Flask(__name__)

# ================= 🔧 全域參數設定區域 🔧 =================
OUTPUT_LIGHT_FILENAME = "hasselblad_output_light.jpg"
OUTPUT_DARK_FILENAME = "hasselblad_output_dark.jpg"
# 🚀 新增：預覽用的輕量化圖片路徑
PREVIEW_LIGHT_FILENAME = "preview_light.jpg"
PREVIEW_DARK_FILENAME = "preview_dark.jpg"

INPUT_TEMP_FILENAME = "temp_uploaded_image.jpg" 
LOGO_FILENAME = "logo.jpg"
FAVICON_FILENAME = "favicon.jpg"

FONT_FILENAME = "Inter_28pt-Light.ttf"  

THEMES = {
    'light': {'bg_color': 'white', 'logo_rgb': (135, 135, 135), 'text_hex': "#6E6E6E"},
    'dark': {'bg_color': '#000000', 'logo_rgb': (220, 220, 220), 'text_hex': "#A0A0A0"}
}

LOGO_THRESHOLD = 240               
BORDER_SIDE_RATIO = 0.026          
BORDER_BOTTOM_RATIO = 0.14         
LOGO_WIDTH_RATIO = 0.25            
FONT_SIZE_RATIO = 0.014             
TEXT_LETTER_SPACING_RATIO = 0.002  
SPACING_IMAGE_TO_LOGO_RATIO = 0.16 
SPACING_LOGO_TO_TEXT_RATIO = 0.045 
# ========================================================

def process_jpg_logo(jpg_path, target_color_rgb):
    img = Image.open(jpg_path).convert("RGBA")
    datas = img.getdata()
    newData = []
    threshold = LOGO_THRESHOLD
    for item in datas:
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            newData.append((255, 255, 255, 0))
        else:
            newData.append((target_color_rgb[0], target_color_rgb[1], target_color_rgb[2], 255))
    img.putdata(newData)
    return img

def get_auto_exif_string(img):
    try:
        exif_data = img.getexif()
        if not exif_data: return "SHOT ON HASSELBLAD" 
        exif = {ExifTags.TAGS[k]: v for k, v in exif_data.items() if k in ExifTags.TAGS}
        try:
            exif_ifd = exif_data.get_ifd(0x8769) 
            for k, v in exif_ifd.items():
                if k in ExifTags.TAGS: exif[ExifTags.TAGS[k]] = v
        except Exception: pass
        model = str(exif.get('Model', '')).strip()
        lens = str(exif.get('LensModel', '')).strip()
        f_number = exif.get('FNumber')
        f_stop = f"F {float(f_number):.1f}".replace('.0', '') if f_number else ""
        exposure_time = exif.get('ExposureTime')
        shutter = ""
        if exposure_time:
            val = float(exposure_time)
            shutter = f"{val:g} SEC" if val >= 1 else f"1/{int(round(1/val))} SEC"
        iso_val = exif.get('ISOSpeedRatings')
        iso_str = f"ISO {iso_val}" if iso_val else ""
        parts = [p for p in [f_stop, shutter, iso_str, model, lens] if p]
        return " | ".join(parts) if parts else "SHOT ON HASSELBLAD"
    except Exception as e:
        return "SHOT ON HASSELBLAD"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hasselblad Camera Mark</title>
    <link rel="icon" type="image/jpeg" href="/favicon">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@200;300;400&display=swap" rel="stylesheet">
    <style>
        body { background-color: #000000; color: #ffffff; font-family: 'Inter', sans-serif; margin: 0; display: flex; height: 100vh; overflow: hidden; }
        .sidebar { width: 30%; padding: 4rem 3rem; background-color: #050505; border-right: 1px solid #3a3a3a; display: flex; flex-direction: column; box-sizing: border-box; z-index: 10; }
        .brand-logo { height: 24px; object-fit: contain; object-position: left; margin-bottom: 4rem; opacity: 0.9; }
        .main-gallery { width: 70%; background-color: #111; display: flex; flex-direction: column; align-items: center; justify-content: center; box-sizing: border-box; padding: 2rem; position: relative; }
        .form-group { margin-bottom: 2.5rem; width: 100%; }
        label { display: block; margin-bottom: 0.5rem; font-size: 0.75rem; letter-spacing: 0.1em; color: #888; text-transform: uppercase; }
        input[type="file"] { color: #aaa; font-size: 0.85em; padding: 10px 0; }
        input[type="file"]::file-selector-button { background: transparent; color: #fff; border: 1px solid #555; padding: 8px 16px; margin-right: 15px; cursor: pointer; transition: all 0.3s; font-family: 'Inter', sans-serif; letter-spacing: 0.05em; }
        input[type="file"]::file-selector-button:hover { border-color: #fff; background: #fff; color: #000; }
        .btn { background: transparent; color: #fff; border: 1px solid #fff; padding: 14px 20px; font-size: 0.8rem; letter-spacing: 0.15em; text-transform: uppercase; cursor: pointer; transition: all 0.4s ease; text-align: center; text-decoration: none; }
        .btn:hover { background: #fff; color: #000; }
        .compare-wrapper { position: relative; display: inline-block; max-height: 75vh; max-width: 90%; box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.08), 0 20px 50px rgba(0,0,0,0.8); opacity: 0; animation: fadeIn 0.8s forwards; margin-bottom: 30px; }
        .compare-img { display: block; max-height: 75vh; max-width: 100%; width: auto; height: auto; }
        .compare-overlay { position: absolute; top: 0; left: 0; width: 50%; height: 100%; overflow: hidden; }
        .compare-overlay img { display: block; height: 100%; max-width: none; }
        .compare-slider { position: absolute; top: 0; left: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: ew-resize; z-index: 10; }
        .compare-handle { position: absolute; top: 0; left: 50%; bottom: 0; width: 2px; background: rgba(255, 255, 255, 0.8); pointer-events: none; transform: translateX(-50%); z-index: 5; box-shadow: 0 0 15px rgba(0,0,0,0.8); }
        .compare-handle::after { content: ''; position: absolute; top: 50%; left: 50%; width: 44px; height: 44px; background: rgba(0, 0, 0, 0.6); border: 2px solid rgba(255, 255, 255, 0.9); border-radius: 50%; transform: translate(-50%, -50%); backdrop-filter: blur(4px); }
        .compare-handle::before { content: '◄  ►'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #fff; font-size: 11px; letter-spacing: -1px; z-index: 2; }
        .download-controls { display: flex; justify-content: center; gap: 20px; width: 100%; opacity: 0; animation: fadeIn 0.8s forwards 0.2s; }
        .download-btn { padding: 8px 18px; font-size: 0.65rem; letter-spacing: 0.15em; text-transform: uppercase; text-decoration: none; transition: all 0.3s ease; border: 1px solid transparent; }
        .btn-theme-light { background: #fff; color: #000; border-color: #fff; }
        .btn-theme-light:hover { background: transparent; color: #fff; border-color: #fff; }
        .btn-theme-dark { background: transparent; color: #aaa; border-color: #555; }
        .btn-theme-dark:hover { background: #fff; color: #000; border-color: #fff; }
        .empty-state { color: #444; font-weight: 200; letter-spacing: 0.1em; text-transform: uppercase; }
        @keyframes fadeIn { to { opacity: 1; } }
    </style>
</head>
<body>
    <div class="sidebar">
        <img src="/web-logo" class="brand-logo" alt="Brand Logo">
        <form action="/" method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label>CAMERA MARK</label>
                <p style="font-size: 0.7rem; color: #555; margin-bottom: 10px;">Upload</p>
                <input type="file" name="image" accept="image/*">
            </div>
            {% if error_msg %}<div style="color: #ff5555; font-size: 0.75rem; letter-spacing: 0.1em; margin-bottom: 15px;">⚠️ {{ error_msg }}</div>{% endif %}
            <div class="btn-group"><button type="submit" class="btn">Generate</button></div>
        </form>
    </div>
    <div class="main-gallery">
        {% if show_preview %}
            <div class="compare-wrapper">
                <img src="/preview/dark?t={{ timestamp }}" class="compare-img" id="base-img" alt="Dark Preview">
                <div class="compare-overlay" id="compare-overlay">
                    <img src="/preview/light?t={{ timestamp }}" id="overlay-img" alt="Light Preview">
                </div>
                <div class="compare-handle" id="compare-handle"></div>
                <input type="range" min="0" max="100" value="50" class="compare-slider" id="compare-slider">
            </div>
            <div class="download-controls">
                <a href="/download/light" class="download-btn btn-theme-light">Download Light (HQ)</a>
                <a href="/download/dark" class="download-btn btn-theme-dark">Download Dark (HQ)</a>
            </div>
        {% else %}
            <div class="empty-state">Studio is ready</div>
        {% endif %}
    </div>
    <script>
        {% if show_preview %}
        const slider = document.getElementById('compare-slider');
        const overlay = document.getElementById('compare-overlay');
        const handle = document.getElementById('compare-handle');
        const baseImg = document.getElementById('base-img');
        const overlayImg = document.getElementById('overlay-img');
        function syncImgWidth() { overlayImg.style.width = baseImg.getBoundingClientRect().width + 'px'; }
        if (baseImg.complete) { syncImgWidth(); } else { baseImg.onload = syncImgWidth; }
        window.addEventListener('resize', syncImgWidth);
        slider.addEventListener('input', function(e) { const val = e.target.value; overlay.style.width = val + '%'; handle.style.left = val + '%'; });
        {% endif %}
    </script>
</body>
</html>
"""

def add_frame_with_logo(img, text_info, logo_path, theme_key):
    theme = THEMES[theme_key]
    w, h = img.size
    long_edge = max(w, h)
    border_side = int(long_edge * BORDER_SIDE_RATIO)
    border_bottom = int(long_edge * BORDER_BOTTOM_RATIO)
    new_w = w + border_side * 2
    new_h = h + border_side + border_bottom
    new_img = Image.new('RGB', (new_w, new_h), theme['bg_color'])
    new_img.paste(img, (border_side, border_side))
    draw = ImageDraw.Draw(new_img)
    try:
        info_font = ImageFont.truetype(FONT_FILENAME, int(long_edge * FONT_SIZE_RATIO))
    except:
        info_font = ImageFont.load_default()
    if os.path.exists(logo_path):
        logo = process_jpg_logo(logo_path, theme['logo_rgb'])
        logo_w = int(long_edge * LOGO_WIDTH_RATIO)
        aspect = logo.height / logo.width
        logo_h = int(logo_w * aspect)
        logo = logo.resize((logo_w, logo_h), Image.Resampling.LANCZOS)
        logo_x = int((new_w - logo_w) / 2)
        logo_y = h + border_side + int(border_bottom * SPACING_IMAGE_TO_LOGO_RATIO)
        new_img.paste(logo, (logo_x, logo_y), logo)
        logo_y_end = logo_y + logo_h
    else:
        logo_y_end = h + border_side + int(border_bottom * SPACING_IMAGE_TO_LOGO_RATIO)

    letter_spacing = int(long_edge * TEXT_LETTER_SPACING_RATIO)
    total_text_w = sum([draw.textlength(char, font=info_font) for char in text_info]) + (len(text_info)-1)*letter_spacing
    current_x = (new_w - total_text_w) / 2
    text_y = logo_y_end + int(border_bottom * SPACING_LOGO_TO_TEXT_RATIO)
    for char in text_info:
        draw.text((current_x, text_y), char, fill=theme['text_hex'], font=info_font)
        current_x += draw.textlength(char, font=info_font) + letter_spacing
    return new_img

# 🚀 修改：同時生成原圖與預覽圖
def process_and_save_all(img, exif_str, theme):
    # 1. 處理高品質原圖
    hq_filename = OUTPUT_LIGHT_FILENAME if theme == 'light' else OUTPUT_DARK_FILENAME
    hq_framed = add_frame_with_logo(img, exif_str, LOGO_FILENAME, theme)
    hq_framed.save(hq_filename, quality=100, subsampling=0)
    
    # 2. 🚀 生成輕量化預覽圖 (固定長邊 1600px)
    preview_filename = PREVIEW_LIGHT_FILENAME if theme == 'light' else PREVIEW_DARK_FILENAME
    prev_w, prev_h = img.size
    prev_ratio = 1600 / max(prev_w, prev_h)
    if prev_ratio < 1:
        img_small = img.resize((int(prev_w * prev_ratio), int(prev_h * prev_ratio)), Image.Resampling.LANCZOS)
    else:
        img_small = img
    
    preview_framed = add_frame_with_logo(img_small, exif_str, LOGO_FILENAME, theme)
    preview_framed.save(preview_filename, quality=85, subsampling=0)

@app.route('/favicon')
def serve_favicon():
    if os.path.exists(FAVICON_FILENAME): return send_file(FAVICON_FILENAME, mimetype='image/jpeg')
    return "", 404

@app.route('/web-logo')
def serve_web_logo():
    if os.path.exists(LOGO_FILENAME):
        web_logo = process_jpg_logo(LOGO_FILENAME, (255, 255, 255))
        bbox = web_logo.getbbox()
        if bbox: web_logo = web_logo.crop(bbox)
        img_io = io.BytesIO()
        web_logo.save(img_io, 'PNG') 
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')
    return "", 404

# 🚀 新增：預覽圖路由
@app.route('/preview/<theme>')
def get_preview(theme):
    filename = PREVIEW_LIGHT_FILENAME if theme == 'light' else PREVIEW_DARK_FILENAME
    if os.path.exists(filename): return send_file(filename, mimetype='image/jpeg')
    return "Not found", 404

@app.route('/', methods=['GET', 'POST'])
def index():
    show_preview = False
    has_temp_img = os.path.exists(INPUT_TEMP_FILENAME)
    error_msg = None 
    if request.method == 'POST':
        file = request.files.get('image')
        if not file or file.filename == '':
            if has_temp_img: use_temp = True
            else: use_temp = False; error_msg = "PLEASE SELECT AN IMAGE FIRST."
        else: use_temp = False
        if not error_msg:
            try:
                img_orig = Image.open(INPUT_TEMP_FILENAME if use_temp else file)
                if not use_temp:
                    exif_bytes = img_orig.info.get('exif', b'')
                    if img_orig.mode in ('RGBA', 'P'): img_orig = img_orig.convert('RGB')
                    img_orig.save(INPUT_TEMP_FILENAME, exif=exif_bytes)
                
                extracted_exif_string = get_auto_exif_string(img_orig)
                if img_orig.mode in ('RGBA', 'P'): img_orig = img_orig.convert('RGB')
                img_orig = ImageOps.exif_transpose(img_orig)
                
                # 🚀 並行處理
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    f1 = executor.submit(process_and_save_all, img_orig, extracted_exif_string, 'light')
                    f2 = executor.submit(process_and_save_all, img_orig, extracted_exif_string, 'dark')
                    concurrent.futures.wait([f1, f2])
                show_preview = True
            except Exception as e: error_msg = f"PROCESSING FAILED: {str(e)}"
    return render_template_string(HTML_TEMPLATE, show_preview=show_preview, timestamp=int(time.time()), has_temp_img=has_temp_img, error_msg=error_msg)

@app.route('/image/<theme>')
def get_image(theme):
    filename = OUTPUT_LIGHT_FILENAME if theme == 'light' else OUTPUT_DARK_FILENAME
    if os.path.exists(filename): return send_file(filename, mimetype='image/jpeg')
    return "Image not found", 404

@app.route('/download/<theme>')
def download_image(theme):
    filename = OUTPUT_LIGHT_FILENAME if theme == 'light' else OUTPUT_DARK_FILENAME
    if os.path.exists(filename):
        dl_name = f'Hasselblad_{theme.capitalize()}_{int(time.time())}.jpg'
        return send_file(filename, mimetype='image/jpeg', as_attachment=True, download_name=dl_name)
    return "File not found", 404

if __name__ == '__main__':
    #app.run(host='0.0.0.0', port=5000)
    app.run(debug=True, port=5000)