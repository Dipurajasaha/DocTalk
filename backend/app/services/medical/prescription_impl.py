import requests
from urllib.parse import quote
import time
import fitz
from PIL import Image
import os
import json
import google.generativeai as genai
import re

# Configure Google API for Gemini: prefer `GOOGLE_API_KEY` then `GEMINI_API_KEY`.
_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if _API_KEY and _API_KEY not in ("YOUR_GOOGLE_API_KEY", "###"):
    genai.configure(api_key=_API_KEY)
    model = genai.GenerativeModel(os.getenv("GEMINI_TEXT_MODEL", "gemini-3-flash-preview"))
else:
    model = None

# --- New Configuration for Google Custom Search ---
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
CSE_ID = os.getenv("GOOGLE_CSE_ID", "")
# ----------------------------------------------------


def _has_google_search_config():
    key = (GOOGLE_API_KEY or "").strip()
    cse = (CSE_ID or "").strip()
    if not key or not cse:
        return False
    if key in ("YOUR_GOOGLE_API_KEY", "###"):
        return False
    if cse in ("YOUR_CSE_ID", "$###", "###"):
        return False
    return True


def text_format(text, language='en'):
    language_prompts = {
        'en': "Extract medicine name, dosage, and frequency from text. Also return the purpose of the medicine.",
        'bn': "টেক্সট থেকে ঔষধের নাম, ডোজ এবং গ্রহণের ফ্রিকোয়েন্সি বের করুন। ঔষধের উদ্দেশ্যও দিন।",
        'hi': "टेक्स्ट से दवा का नाम, खुराक और आवृत्ति निकालें। दवा का उद्देश्य भी बताएं।",
        'es': "Extraiga el nombre del medicamento, la dosis y la frecuencia del texto. También devuelva el propósito del medicamento.",
        'fr': "Extrayez le nom du médicament, la posologie et la fréquence du texte. Retournez également l'objectif du médicament.",
        'de': "Extrahieren Sie Medikamentenname, Dosierung und Häufigkeit aus dem Text. Geben Sie auch den Zweck des Medikaments zurück."
    }
    instruction = language_prompts.get(language, language_prompts['en'])
    prompt_text = f"""
    {instruction}
    Return as valid JSON format only, no other text:
    {{
        "medicine1_name": [
            {{
                "dosage": "string",
                "frequency": "string",
                "purpose": "string"
            }}
        ],
        "medicine2_name": [
            {{
                "dosage": "string",
                "frequency": "string",
                "purpose": "string"
            }}
        ]
    }}
    Don't extract any other information and return the text understandable for normal people.
    """
    if model is None:
        raise RuntimeError(
            "No LLM model configured. Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment "
            "or configure the google.generativeai client before invoking LLM functions."
        )
    try:
        response = model.generate_content([prompt_text, text])
        if response.text:
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            result_dict = json.loads(response_text)
            return result_dict
        else:
            return {}
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


def ocr_image(image_path, language='en'):
    language_prompts = {
        'en': "Extract medicine name, dosage, and frequency from image. Also return the purpose of the medicine.",
        'bn': "ছবি থেকে ঔষধের নাম, ডোজ এবং গ্রহণের ফ্রিকোয়েন্সি বের করুন। ঔষধের উদ্দেশ্যও দিন।",
        'hi': "छवि से दवा का नाम, खुराक और आवृत्ति निकालें। दवा का उद्देश्य भी बताएं।",
        'es': "Extraiga el nombre del medicamento, la dosis y la frecuencia de la imagen. También devuelva el propósito del medicamento.",
        'fr': "Extrayez le nom du médicament, la posologie et la fréquence de l'image. Retournez également l'objectif du médicament.",
        'de': "Extrahieren Sie Medikamentenname, Dosierung und Häufigkeit aus dem Bild. Geben Sie auch den Zweck des Medikaments zurück."
    }
    instruction = language_prompts.get(language, language_prompts['en'])
    if model is None:
        raise RuntimeError(
            "No LLM model configured. Set GOOGLE_API_KEY or GEMINI_API_KEY in the environment "
            "or configure the google.generativeai client before invoking LLM functions."
        )
    try:
        img = Image.open(image_path)
        prompt_text = f"""
        {instruction}
        Return as valid JSON format only, no other text:
        {{
            "medicine1_name": [
                {{
                    "dosage": "string",
                    "frequency": "string",
                    "purpose": "string"
                }}
            ],
            "medicine2_name": [
                {{
                    "dosage": "string",
                    "frequency": "string",
                    "purpose": "string"
                }}
            ]
        }}
        Don't extract any other information and return the text understandable for normal people.
        """
        response = model.generate_content([prompt_text, img])
        if response.text:
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            result_dict = json.loads(response_text)
            return result_dict
        else:
            return {}
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}


def pdf_to_text(file_path, language='en'):
    try:
        doc = fitz.open(file_path)
        text = ""
        for page in doc:
            text += page.get_text()
        result = text_format(text, language)
        return result
    except Exception:
        return {}


def ocr_pdf(file_path, language='en'):
    try:
        doc = fitz.open(file_path)
        all_medicines = {}
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap()
            image_path = f"page_{page_num}.png"
            pix.save(image_path)
            page_result = ocr_image(image_path, language)
            try:
                os.remove(image_path)
            except:
                pass
            if isinstance(page_result, dict):
                all_medicines.update(page_result)
        return all_medicines
    except Exception:
        return {}


def upload(file, language='en'):
    if file:
        file_ext = os.path.splitext(file.filename)[1].lower()
        try:
            if file_ext == ".pdf":
                text_result = pdf_to_text(file, language)
                if text_result and len(text_result) > 0:
                    return text_result
                else:
                    ocr_result = ocr_pdf(file, language)
                    return ocr_result
            elif file_ext in ('.png', '.jpg', '.jpeg'):
                return ocr_image(file, language)
            elif file_ext == ".txt":
                with open(file, "r") as f:
                    text_content = f.read()
                    return text_format(text_content, language)
            else:
                raise ValueError("Unsupported file format.")
        except Exception:
            return {}
    return {}


def search_google_for_links(query):
    if not _has_google_search_config():
        return []
    try:
        url = f"https://www.googleapis.com/customsearch/v1?key={GOOGLE_API_KEY}&cx={CSE_ID}&q={quote(query)}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        search_results = response.json()
        links = [item['link'] for item in search_results.get('items', [])]
        return links
    except requests.exceptions.RequestException:
        return []
    except Exception:
        return []


def extract_price_with_gemini(html_content, site_name, medicine_name):
    try:
        html_snippet = html_content[:30000]
        prompt_text = f"""
        Extract the price information for "{medicine_name}" from this pharmacy website HTML.
        Look for price patterns like ₹123, Rs. 456, $7.89, etc.
        Return as valid JSON format only:
        {{
            "price": numeric_value_only,
            "currency": "INR" or "USD",
            "product_name": "exact product name found"
        }}
        If no price found, return: {{"price": null}}
        Website: {site_name}
        HTML content: {html_snippet}
        """
        response = model.generate_content(prompt_text)
        if response.text:
            response_text = response.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
            elif response_text.startswith('```'):
                response_text = response_text.replace('```', '').strip()
            result_dict = json.loads(response_text)
            return result_dict
        else:
            return {"price": None}
    except json.JSONDecodeError:
        return {"price": None}


def extract_price_regex(html_content):
    try:
        price_patterns = [
            r'₹\\s*(\\d+(?:\\.\\d{2})?)',
            r'Rs\\.?\\s*(\\d+(?:\\.\\d{2})?)',
            r'"price":\\s*(\\d+(?:\\.\\d{2})?)',
            r'price.*?(\\d+(?:\\.\\d{2})?)',
            r'amount.*?(\\d+(?:\\.\\d{2})?)',
        ]
        for pattern in price_patterns:
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                for match in matches:
                    price = float(match)
                    if 10 <= price <= 10000:
                        return price
        return None
    except Exception:
        return None


def get_controlled_substance_info(name):
    controlled_info = {
        'morphine': {'price_range': '500-2000', 'note': 'Prescription required, hospital/clinic only'},
        'oxycodone': {'price_range': '800-3000', 'note': 'Prescription required, hospital/clinic only'},
        'codeine': {'price_range': '200-800', 'note': 'Prescription required, limited availability'},
        'fentanyl': {'price_range': '1000-5000', 'note': 'Hospital use only, strict prescription'},
        'tramadol': {'price_range': '100-500', 'note': 'Prescription required'},
        'hydrocodone': {'price_range': '600-2500', 'note': 'Prescription required, hospital/clinic only'},
        'norco': {'price_range': '400-1200', 'note': 'Prescription required, contains hydrocodone'},
        'vicodin': {'price_range': '400-1200', 'note': 'Prescription required, contains hydrocodone'}
    }
    for substance, info in controlled_info.items():
        if substance.lower() in name.lower():
            price_range = info['price_range'].split('-')
            estimated_price = (float(price_range[0]) + float(price_range[1])) / 2
            return {
                estimated_price: f"Note: {info['note']} - Estimated price range: ₹{info['price_range']}"
            }
    return {750.0: "Note: Controlled substance - Prescription required, contact healthcare provider"}


def get_estimated_price(name):
    medicine_prices = {
        'paracetamol': 25.0,
        'acetaminophen': 30.0,
        'ibuprofen': 45.0,
        'aspirin': 20.0,
        'cetirizine': 35.0,
        'loratadine': 40.0,
        'amoxicillin': 85.0,
        'azithromycin': 120.0,
        'ciprofloxacin': 95.0,
        'metformin': 55.0,
        'atorvastatin': 110.0,
        'amlodipine': 75.0,
        'omeprazole': 65.0,
        'pantoprazole': 70.0,
        'ranitidine': 50.0,
        'diclofenac': 60.0,
        'prednisolone': 80.0,
        'salbutamol': 90.0,
    }
    name_lower = name.lower()
    for med_name, price in medicine_prices.items():
        if med_name in name_lower:
            return price
    for med_name, price in medicine_prices.items():
        if med_name in name_lower or name_lower in med_name:
            return price * 1.2
    return 100.0


def get_online_price(name):
    encoded_name = quote(name)
    controlled_substances = ['morphine', 'oxycodone', 'codeine', 'fentanyl', 'tramadol', 'hydrocodone', 'norco', 'vicodin']
    is_controlled = any(substance.lower() in name.lower() for substance in controlled_substances)
    if is_controlled:
        return get_controlled_substance_info(name)
    search_query = f'"{name}" price india buy online inurl:netmeds OR inurl:1mg OR inurl:pharmeasy OR inurl:apollopharmacy'
    google_links = search_google_for_links(search_query)
    default_links = [
        f'https://www.1mg.com/search/all?name={encoded_name}',
        f'https://pharmeasy.in/search/all?name={encoded_name}',
        f'https://www.netmeds.com/catalogsearch/result?q={encoded_name}',
        f'https://www.apollopharmacy.in/search-medicines/{encoded_name}'
    ]
    all_links = list(dict.fromkeys(google_links + default_links))
    result = {}
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    for url in all_links[:5]:
        try:
            response = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
            if response.status_code == 200:
                site_name = url.split('/')[2]
                price_info = extract_price_with_gemini(response.text, site_name, name)
                if price_info and price_info.get('price'):
                    price = float(price_info['price'])
                    if price >= 10:
                        result[price] = url
                else:
                    fallback_price = extract_price_regex(response.text)
                    if fallback_price and fallback_price >= 10:
                        result[fallback_price] = url
        except requests.exceptions.RequestException:
            pass
        except Exception:
            pass
        time.sleep(1)
    if not result:
        estimated_price = get_estimated_price(name)
        if estimated_price:
            result[estimated_price] = f"https://www.1mg.com/search/all?name={encoded_name}"
    return result


def search_price(medicine):
    try:
        price_dict = get_online_price(medicine)
        if not price_dict:
            return None, None
        min_price = min(price_dict.keys())
        best_link = price_dict[min_price]
        return min_price, best_link
    except Exception:
        return None, None


__all__ = [
    "text_format",
    "ocr_image",
    "pdf_to_text",
    "ocr_pdf",
    "upload",
    "search_price",
    "extract_price_with_gemini",
    "extract_price_regex",
    "get_estimated_price",
    "get_online_price",
]
