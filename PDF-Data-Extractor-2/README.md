# PDF Data Extractor

A Flask web application that extracts structured invoice data from PDF files using AI-powered text recognition and OCR technology.

---

## Features

- **Adaptive PDF Processing**: Automatically detects whether a PDF contains extractable text or requires OCR processing
- **AI-Powered Data Extraction**: Uses Google Gemini API to intelligently extract structured invoice data
- **Excel Export**: Generates multi-sheet Excel workbooks with invoice information and line items
- **Clean Web Interface**: Simple, modern UI for uploading PDFs and downloading results

## Installation

### Prerequisites

- Python 3.7+
- Tesseract OCR installed on your system
- Google Gemini API key

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yousseftarhri/PDF-Data-Extractor.git
cd PDF-Data-Extractor
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory:
```
GEMINI_API=your_gemini_api_key_here
```
### Usage
**1. Start the Flask server:**
```python main.py```

**2. Open your browser and navigate to http://localhost:5000**

**3. Upload a PDF invoice file through the web interface**

**4. The application will automatically:**
- Detect if the PDF has extractable text or requires OCR main.py:56-59 
- Extract text using the appropriate method 
- Send the text to Gemini API for structured data extraction 
- Generate an Excel file with two sheets: "Invoice Info" and "Items"
- Automatically download the Excel file