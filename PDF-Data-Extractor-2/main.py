from flask import Flask, render_template, request, send_file
import os
import pandas as pd
import re
import json
import base64
from dotenv import load_dotenv
import anthropic
import requests as http_requests
from pdf2image import convert_from_path
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils import get_column_letter
import io

load_dotenv()

# Initialize Anthropic client
client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    base_url="https://www.right.codes/claude-aws"
)


app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

ALLOWED_EXTENSIONS = {'pdf'}

SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY")


def send_wechat_notification(title, content):
    if not SERVERCHAN_KEY:
        print("Server酱 KEY 未配置，跳过推送")
        return
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        resp = http_requests.post(url, data=data, timeout=10)
        print(f"Server酱推送结果: {resp.status_code}")
    except Exception as e:
        print(f"Server酱推送失败: {e}")


def check_duplicates(data_list):
    seen = {}
    duplicates = []
    for i, entry in enumerate(data_list):
        key = (entry.get("单据编号"), entry.get("日期"), entry.get("品种"), entry.get("净重(吨)"))
        if key in seen:
            duplicates.append(f"第{i+1}条与第{seen[key]+1}条疑似重复（单据编号={key[0]}, 品种={key[2]}）")
        else:
            seen[key] = i
    return duplicates

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_product_name_from_invoice(pdf_path):
    # Step 1: Convert PDF to images
    images = convert_from_path(pdf_path, poppler_path=r"D:\pdf-excel\poppler-26.02.0\Library\bin")

    # Convert images to base64 for Claude
    image_content = []
    for img in images:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
        image_content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/png",
                "data": b64_data
            }
        })

    # Step 2: Prepare the prompt
    prompt = """你是一个智能单据数据提取助手。

请识别图片中的送货单内容，以有效的 JSON 数组格式返回结构化数据。

### 要求：
1. 每张送货单提取以下字段（严格使用这些字段名）：
   - 单据编号
   - 日期（格式：YYYY-MM-DD）
   - 送货车号
   - 送货单位
   - 收货单位
   - 序号
   - 品种
   - 总重(吨)（数字，保持原值）
   - 皮重(吨)（数字，保持原值）
   - 净重(吨)（数字，保持原值）
   - 单位
   - 送经办人
   - 收经办人
2. 如果图片中有多张送货单，每张单独一条记录
3. 缺失的字段填 null
4. 仔细辨认手写字和印刷字，确保数字和中文准确
5. 仅返回有效 JSON 数组，不要包含任何解释文字或代码块标记"""

    # Step 3: Send images + prompt to Claude
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": image_content + [{"type": "text", "text": prompt}]
        }]
    )

    return message.content[0].text

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400

    files = request.files.getlist('file')
    if not files or files[0].filename == '':
        return "No selected file", 400

    target_columns = [
        "单据编号", "日期", "送货车号", "送货单位", "收货单位",
        "序号", "品种", "总重(吨)", "皮重(吨)", "净重(吨)",
        "单位", "送经办人", "收经办人", "图片"
    ]

    all_data = []
    all_filepaths = []
    unrecognized_fields = []

    for file in files:
        if not allowed_file(file.filename):
            return f"文件 {file.filename} 不是PDF格式，仅支持PDF文件。", 400

        filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filepath)
        all_filepaths.append(filepath)

        try:
            result = extract_product_name_from_invoice(filepath)
            cleaned_json = re.sub(r"```(?:json)?\s*", "", result)
            cleaned_json = cleaned_json.strip().rstrip("`")
            data = json.loads(cleaned_json)
        except json.JSONDecodeError:
            send_wechat_notification(
                "单据识别失败",
                f"文件 **{file.filename}** 无法识别，请确认是否为有效的单据文件。"
            )
            return f"无法识别文件 {file.filename} 的内容，请确认是否为有效的单据文件。", 400
        except Exception as e:
            send_wechat_notification(
                "单据识别异常",
                f"文件 **{file.filename}** 识别出错：{str(e)}"
            )
            return f"识别文件 {file.filename} 失败：{str(e)}", 400

        if isinstance(data, list):
            for i, entry in enumerate(data):
                nulls = [k for k in target_columns[:-1] if entry.get(k) is None]
                if nulls:
                    unrecognized_fields.append(f"{file.filename} 第{i+1}条记录: {', '.join(nulls)}")
            all_data.extend(data)
        else:
            nulls = [k for k in target_columns[:-1] if data.get(k) is None]
            if nulls:
                unrecognized_fields.append(f"{file.filename}: {', '.join(nulls)}")
            all_data.append(data)

    duplicates = check_duplicates(all_data)

    issues = []
    if unrecognized_fields:
        issues.append("### 字段缺失\n" + "\n".join(f"- {w}" for w in unrecognized_fields))
    if duplicates:
        issues.append("### 疑似重复\n" + "\n".join(f"- {d}" for d in duplicates))

    if issues:
        filenames = ", ".join(f.filename for f in files)
        send_wechat_notification(
            "单据识别结果异常",
            f"上传文件：{filenames}\n\n" + "\n\n".join(issues)
        )

    df = pd.DataFrame(all_data)
    df["图片"] = ""

    for col in target_columns:
        if col not in df.columns:
            df[col] = None
    df = df[target_columns]

    name_output_file = "invoice_data.xlsx"
    excel_save_path = os.path.join(app.config['UPLOAD_FOLDER'], name_output_file)
    with pd.ExcelWriter(excel_save_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="送货单汇总", index=False)
        ws = writer.sheets["送货单汇总"]

        img_col = target_columns.index("图片") + 1
        img_col_letter = get_column_letter(img_col)

        row_idx = 2
        for filepath in all_filepaths:
            images = convert_from_path(filepath, poppler_path=r"D:\pdf-excel\poppler-26.02.0\Library\bin")
            for img in images:
                if row_idx > len(df) + 1:
                    break
                if img.width > img.height:
                    img = img.rotate(270, expand=True)
                img_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_page_{row_idx}.png")
                img.save(img_path, format="PNG")
                xl_img = XLImage(img_path)
                xl_img.width = 150
                xl_img.height = 200
                ws.row_dimensions[row_idx].height = 150
                ws.add_image(xl_img, f"{img_col_letter}{row_idx}")
                row_idx += 1

    return render_template(
        'result.html',
        warnings=unrecognized_fields,
        duplicates=duplicates,
        excel_file=name_output_file
    )


@app.route('/download/<filename>')
def download_file(filename):
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    return send_file(filepath, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
